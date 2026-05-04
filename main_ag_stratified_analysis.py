from pathlib import Path
from collections import OrderedDict
import argparse

import numpy as np
import pandas as pd

from adaptive_trend_strategy import AdaptiveTrendStrategy
from backtestengine import BacktestEngine
from futures_config import AG_CONFIG
from main_ag_final_strategy import FINAL_PARAMS
from metrics import calculate_metrics, metrics_to_frame, trade_log_to_frame


DATA_PATH = Path("data") / "ag_202604_cleaned.csv"
REPORT_DIR = Path("outputs") / "ag_202604_stratified"

USE_COLUMNS = [
    "datetime",
    "last_price",
    "volume",
    "amount",
    "bid_price1",
    "bid_volume1",
    "ask_price1",
    "ask_volume1",
    "tick_volume",
    "tick_amount",
]


def load_market_data(path=DATA_PATH, every_nth=1):
    market_data = pd.read_csv(path, usecols=USE_COLUMNS)
    market_data["datetime"] = pd.to_datetime(market_data["datetime"], errors="coerce")
    market_data = market_data.dropna(subset=["datetime"])
    market_data = market_data.sort_values("datetime")
    if every_nth > 1:
        market_data = market_data.iloc[::every_nth].copy()
    market_data["date"] = market_data["datetime"].dt.date.astype(str)
    return market_data.reset_index(drop=True)


def split_by_date(market_data, train_ratio=0.7):
    dates = sorted(market_data["date"].unique())
    split_idx = max(1, int(len(dates) * train_ratio))
    train_dates = set(dates[:split_idx])
    test_dates = set(dates[split_idx:])
    return (
        market_data[market_data["date"].isin(train_dates)].copy(),
        market_data[market_data["date"].isin(test_dates)].copy(),
    )


def build_engine():
    return BacktestEngine(data_path=None, **AG_CONFIG.to_engine_kwargs())


def run_final_strategy(market_data):
    backtest_engine = build_engine()
    strategy_params = dict(FINAL_PARAMS)
    strategy_params.pop("label", None)
    strategy = AdaptiveTrendStrategy(engine=backtest_engine, **strategy_params)

    for tick_record in market_data[USE_COLUMNS].to_dict("records"):
        backtest_engine.current_tick = tick_record
        strategy.on_tick(tick_record)

    strategy.force_close_at_end()
    return strategy


def add_regime_features(market_data, train_data):
    enriched = market_data.copy()
    enriched["log_return"] = np.log(enriched["last_price"]).diff().fillna(0.0)
    enriched["spread"] = (enriched["ask_price1"] - enriched["bid_price1"]).clip(lower=0.0)
    enriched["depth"] = enriched["bid_volume1"] + enriched["ask_volume1"]
    enriched["session_regime"] = np.where(
        (enriched["datetime"].dt.time >= pd.Timestamp("21:00:00").time())
        | (enriched["datetime"].dt.time <= pd.Timestamp("02:30:00").time()),
        "night",
        "day",
    )

    vol_window = 3600
    trend_window = 3600
    fast_window = 1200
    slow_window = 7200

    enriched["realized_volatility"] = (
        enriched["log_return"].rolling(vol_window, min_periods=300).std().fillna(0.0)
    )
    enriched["directional_move"] = (
        enriched["log_return"].rolling(trend_window, min_periods=300).sum().abs().fillna(0.0)
    )
    enriched["trend_strength"] = enriched["directional_move"] / (enriched["realized_volatility"] + 1e-9)
    enriched["liquidity_score"] = enriched["depth"] / (enriched["spread"] + 1.0)

    enriched["fast_ma"] = enriched["last_price"].rolling(fast_window, min_periods=fast_window).mean()
    enriched["slow_ma"] = enriched["last_price"].rolling(slow_window, min_periods=slow_window).mean()
    enriched["trend_gap"] = (enriched["fast_ma"] - enriched["slow_ma"]).abs()

    train_dates = set(train_data["date"].astype(str).unique())
    train_slice = enriched[enriched["date"].isin(train_dates)]

    threshold_map = {
        "volatility_regime": _quantile_thresholds(train_slice["realized_volatility"]),
        "trend_regime": _quantile_thresholds(train_slice["trend_strength"]),
        "liquidity_regime": _quantile_thresholds(train_slice["liquidity_score"]),
    }
    enriched["volatility_regime"] = _bucketize(
        enriched["realized_volatility"], threshold_map["volatility_regime"], ["low", "mid", "high"]
    )
    enriched["trend_regime"] = _bucketize(
        enriched["trend_strength"], threshold_map["trend_regime"], ["weak", "medium", "strong"]
    )
    enriched["liquidity_regime"] = _bucketize(
        enriched["liquidity_score"], threshold_map["liquidity_regime"], ["low", "mid", "high"]
    )
    return enriched


def _quantile_thresholds(series):
    clean_series = series.replace([np.inf, -np.inf], np.nan).dropna()
    if clean_series.empty:
        return 0.0, 0.0
    return (
        float(clean_series.quantile(0.33)),
        float(clean_series.quantile(0.67)),
    )


def _bucketize(series, thresholds, labels):
    low, high = thresholds
    bucket = pd.Series(index=series.index, dtype="object")
    valid = series.replace([np.inf, -np.inf], np.nan)
    bucket.loc[valid <= low] = labels[0]
    bucket.loc[(valid > low) & (valid <= high)] = labels[1]
    bucket.loc[valid > high] = labels[2]
    bucket = bucket.fillna("unknown")
    return bucket


def summarize_trade_frame(trade_df):
    if trade_df.empty:
        return {
            "trade_count": 0,
            "total_pnl": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "win_rate": 0.0,
            "average_net_profit": 0.0,
            "average_holding_ticks": 0.0,
            "timeout_rate": 0.0,
            "take_profit_count": 0,
            "stop_loss_count": 0,
            "timeout_count": 0,
            "force_close_count": 0,
        }

    ordered = trade_df.sort_values("entry_time").copy()
    equity_curve = ordered["net_profit"].cumsum().to_numpy(dtype=float)
    returns = ordered["net_profit"].to_numpy(dtype=float)
    wins = ordered[ordered["net_profit"] > 0]
    close_reason_counts = ordered["close_reason"].value_counts()

    if len(equity_curve) < 2:
        sharpe = 0.0
    else:
        std = np.std(np.diff(equity_curve), ddof=1)
        sharpe = 0.0 if std == 0 else float(np.mean(np.diff(equity_curve)) / std * np.sqrt(len(equity_curve) - 1))

    running_max = np.maximum.accumulate(equity_curve) if len(equity_curve) else np.array([0.0])
    max_drawdown = float(np.max(running_max - equity_curve)) if len(equity_curve) else 0.0
    wins_count = int(len(wins))

    return {
        "trade_count": int(len(ordered)),
        "total_pnl": float(ordered["net_profit"].sum()),
        "max_drawdown": max_drawdown,
        "sharpe_ratio": sharpe,
        "win_rate": float(wins_count / len(ordered)),
        "average_net_profit": float(ordered["net_profit"].mean()),
        "average_holding_ticks": float(ordered["holding_ticks"].mean()),
        "timeout_rate": float(close_reason_counts.get("timeout", 0) / len(ordered)),
        "take_profit_count": int(close_reason_counts.get("take_profit", 0)),
        "stop_loss_count": int(close_reason_counts.get("stop_loss", 0)),
        "timeout_count": int(close_reason_counts.get("timeout", 0)),
        "force_close_count": int(close_reason_counts.get("force_close", 0)),
    }


def summarize_tick_profile(enriched_data, regime_col):
    rows = []
    for regime, subset in enriched_data.groupby(regime_col):
        if regime == "unknown":
            continue
        rows.append(
            {
                "layer": regime_col,
                "regime": regime,
                "tick_count": int(len(subset)),
                "tick_share": float(len(subset) / len(enriched_data)),
                "avg_spread": float(subset["spread"].mean()),
                "avg_depth": float(subset["depth"].mean()),
                "avg_volatility": float(subset["realized_volatility"].mean()),
                "avg_trend_strength": float(subset["trend_strength"].mean()),
                "avg_liquidity_score": float(subset["liquidity_score"].mean()),
            }
        )
    return rows


def summarize_trade_regimes(trade_log, enriched_data, regime_col):
    regime_map = enriched_data[["datetime", regime_col]].copy()
    regime_map["datetime"] = pd.to_datetime(regime_map["datetime"], errors="coerce")

    annotated = trade_log.copy()
    annotated["entry_time"] = pd.to_datetime(annotated["entry_time"], errors="coerce")
    annotated = annotated.merge(
        regime_map,
        left_on="entry_time",
        right_on="datetime",
        how="left",
    )
    annotated = annotated.drop(columns=["datetime"])
    annotated[regime_col] = annotated[regime_col].fillna("unknown")

    rows = []
    for regime, subset in annotated.groupby(regime_col):
        if regime == "unknown":
            continue
        metrics = summarize_trade_frame(subset)
        metrics.update(
            {
                "layer": regime_col,
                "regime": regime,
                "entry_trade_share": float(len(subset) / len(annotated)) if len(annotated) else 0.0,
            }
        )
        rows.append(metrics)
    return rows, annotated


def parse_args():
    parser = argparse.ArgumentParser(description="Run stratified regime analysis for the final AG strategy.")
    parser.add_argument("--data-path", default=str(DATA_PATH), help="Cleaned AG CSV path.")
    parser.add_argument("--report-dir", default=str(REPORT_DIR), help="Output directory.")
    parser.add_argument("--every-nth", type=int, default=1, help="Use every Nth tick for smoke tests.")
    return parser.parse_args()


def main():
    args = parse_args()
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    market_data = load_market_data(Path(args.data_path), every_nth=max(1, args.every_nth))
    train_data, test_data = split_by_date(market_data)
    enriched_data = add_regime_features(market_data, train_data)

    strategy = run_final_strategy(market_data)
    full_trade_log = trade_log_to_frame(strategy.trade_log)

    tick_profile_rows = []
    trade_regime_rows = []
    annotated_trade_frames = []
    for regime_col in ["volatility_regime", "trend_regime", "liquidity_regime", "session_regime"]:
        tick_profile_rows.extend(summarize_tick_profile(enriched_data, regime_col))
        regime_rows, annotated = summarize_trade_regimes(full_trade_log, enriched_data, regime_col)
        trade_regime_rows.extend(regime_rows)
        annotated_trade_frames.append(
            annotated.assign(layer=regime_col)
        )

    tick_profile_df = pd.DataFrame(tick_profile_rows)
    trade_regime_df = pd.DataFrame(trade_regime_rows)
    annotated_trades_df = pd.concat(annotated_trade_frames, ignore_index=True) if annotated_trade_frames else pd.DataFrame()

    tick_profile_df.to_csv(report_dir / "ag_stratified_tick_profile.csv", index=False, encoding="utf-8-sig")
    trade_regime_df.to_csv(report_dir / "ag_stratified_trade_summary.csv", index=False, encoding="utf-8-sig")
    annotated_trades_df.to_csv(report_dir / "ag_stratified_annotated_trades.csv", index=False, encoding="utf-8-sig")

    overall_metrics = calculate_metrics(strategy)
    metrics_to_frame({"full_strategy": overall_metrics}).to_csv(
        report_dir / "ag_stratified_overall_metrics.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print(f"overall_metrics={overall_metrics}")
    print(f"tick_profile_rows={len(tick_profile_df)}")
    print(f"trade_regime_rows={len(trade_regime_df)}")
    print(f"reports saved to {report_dir}")


if __name__ == "__main__":
    main()
