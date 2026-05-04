from pathlib import Path

import pandas as pd

from adaptive_trend_strategy import AdaptiveTrendStrategy
from backtestengine import BacktestEngine
from futures_config import AG_CONFIG
from metrics import calculate_metrics, metrics_to_frame, trade_log_to_frame


DATA_PATH = Path("data") / "ag_202604_cleaned.csv"
REPORT_DIR = Path("outputs") / "ag_202604_adaptive"

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


PARAM_CANDIDATES = [
    {
        "label": "ma_10m_60m",
        "fast_window": 1200,
        "slow_window": 7200,
        "entry_threshold": 8.0,
        "exit_threshold": 2.0,
        "expected_profit_ticks": 200,
        "stop_loss_ticks": 50,
        "trailing_start_ticks": 80,
        "trailing_stop_ticks": 35,
        "max_holding_ticks": 36000,
        "cooldown_ticks": 600,
    },
    {
        "label": "ma_30m_120m",
        "fast_window": 3600,
        "slow_window": 14400,
        "entry_threshold": 15.0,
        "exit_threshold": 4.0,
        "expected_profit_ticks": 400,
        "stop_loss_ticks": 80,
        "trailing_start_ticks": 120,
        "trailing_stop_ticks": 50,
        "max_holding_ticks": 72000,
        "cooldown_ticks": 1200,
    },
    {
        "label": "ma_60m_240m",
        "fast_window": 7200,
        "slow_window": 28800,
        "entry_threshold": 25.0,
        "exit_threshold": 6.0,
        "expected_profit_ticks": 700,
        "stop_loss_ticks": 120,
        "trailing_start_ticks": 180,
        "trailing_stop_ticks": 80,
        "max_holding_ticks": 120000,
        "cooldown_ticks": 2400,
    },
    {
        "label": "swing_trend",
        "fast_window": 2400,
        "slow_window": 21600,
        "entry_threshold": 20.0,
        "exit_threshold": 3.0,
        "expected_profit_ticks": 900,
        "stop_loss_ticks": 100,
        "trailing_start_ticks": 250,
        "trailing_stop_ticks": 90,
        "max_holding_ticks": 160000,
        "cooldown_ticks": 1800,
    },
    {
        "label": "swing_trend_wide_stop",
        "fast_window": 2400,
        "slow_window": 21600,
        "entry_threshold": 20.0,
        "exit_threshold": 3.0,
        "expected_profit_ticks": 1200,
        "stop_loss_ticks": 150,
        "trailing_start_ticks": 300,
        "trailing_stop_ticks": 120,
        "max_holding_ticks": 180000,
        "cooldown_ticks": 1800,
    },
    {
        "label": "swing_trend_slow",
        "fast_window": 3600,
        "slow_window": 28800,
        "entry_threshold": 20.0,
        "exit_threshold": 4.0,
        "expected_profit_ticks": 1200,
        "stop_loss_ticks": 150,
        "trailing_start_ticks": 300,
        "trailing_stop_ticks": 120,
        "max_holding_ticks": 180000,
        "cooldown_ticks": 2400,
    },
    {
        "label": "swing_trend_short_only",
        "fast_window": 2400,
        "slow_window": 21600,
        "entry_threshold": 20.0,
        "exit_threshold": 3.0,
        "expected_profit_ticks": 1200,
        "stop_loss_ticks": 150,
        "trailing_start_ticks": 300,
        "trailing_stop_ticks": 120,
        "max_holding_ticks": 180000,
        "cooldown_ticks": 1800,
        "trade_direction": "short",
    },
    {
        "label": "ma_30m_120m_short_only",
        "fast_window": 3600,
        "slow_window": 14400,
        "entry_threshold": 15.0,
        "exit_threshold": 4.0,
        "expected_profit_ticks": 600,
        "stop_loss_ticks": 120,
        "trailing_start_ticks": 180,
        "trailing_stop_ticks": 80,
        "max_holding_ticks": 120000,
        "cooldown_ticks": 1200,
        "trade_direction": "short",
    },
    {
        "label": "ma_30m_120m_wide",
        "fast_window": 3600,
        "slow_window": 14400,
        "entry_threshold": 15.0,
        "exit_threshold": 4.0,
        "expected_profit_ticks": 800,
        "stop_loss_ticks": 150,
        "trailing_start_ticks": 220,
        "trailing_stop_ticks": 90,
        "max_holding_ticks": 160000,
        "cooldown_ticks": 1200,
    },
    {
        "label": "tight_adaptive",
        "fast_window": 900,
        "slow_window": 5400,
        "entry_threshold": 6.0,
        "exit_threshold": 1.5,
        "expected_profit_ticks": 120,
        "stop_loss_ticks": 35,
        "trailing_start_ticks": 45,
        "trailing_stop_ticks": 18,
        "max_holding_ticks": 24000,
        "cooldown_ticks": 500,
    },
]


COMMON_PARAMS = {
    "is_ideal": False,
    "min_depth": 5,
    "max_spread": 8.0,
    "min_tick_volume": 1,
    "obi_threshold": 0.0,
    "obi_weight": 0.0,
}


def load_market_data(path=DATA_PATH):
    market_data = pd.read_csv(path, usecols=USE_COLUMNS)
    market_data["datetime"] = pd.to_datetime(market_data["datetime"], errors="coerce")
    market_data = market_data.dropna(subset=["datetime"])
    market_data = market_data.sort_values("datetime")
    market_data["date"] = market_data["datetime"].dt.date.astype(str)
    return market_data.reset_index(drop=True)


def split_train_test_by_date(market_data, train_ratio=0.7):
    dates = sorted(market_data["date"].unique())
    split_idx = max(1, int(len(dates) * train_ratio))
    train_dates = set(dates[:split_idx])
    test_dates = set(dates[split_idx:])
    return market_data[market_data["date"].isin(train_dates)].copy(), market_data[market_data["date"].isin(test_dates)].copy()


def build_engine():
    return BacktestEngine(data_path=None, **AG_CONFIG.to_engine_kwargs())


def run_strategy(market_data, params):
    backtest_engine = build_engine()
    strategy_params = dict(params)
    label = strategy_params.pop("label")
    strategy = AdaptiveTrendStrategy(engine=backtest_engine, **strategy_params, **COMMON_PARAMS)

    for tick_record in market_data[USE_COLUMNS].to_dict("records"):
        backtest_engine.current_tick = tick_record
        strategy.on_tick(tick_record)

    strategy.force_close_at_end()
    performance_metrics = calculate_metrics(strategy)
    performance_metrics["strategy"] = "adaptive_trend"
    performance_metrics["param_label"] = label
    performance_metrics["tick_count"] = len(market_data)
    performance_metrics["start"] = str(market_data["datetime"].min()) if len(market_data) else ""
    performance_metrics["end"] = str(market_data["datetime"].max()) if len(market_data) else ""
    return strategy, performance_metrics


def score(metrics):
    if metrics["trade_count"] < 3:
        return -1e9
    return metrics["total_pnl"] - 0.5 * metrics["max_drawdown"] + 20.0 * metrics["win_rate"]


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    market_data = load_market_data()
    train_df, test_df = split_train_test_by_date(market_data)

    rows = []
    best = None
    for params in PARAM_CANDIDATES:
        _, train_metrics = run_strategy(train_df, params)
        _, test_metrics = run_strategy(test_df, params)
        train_metrics["split"] = "train"
        test_metrics["split"] = "test"
        train_metrics["selection_score"] = score(train_metrics)
        test_metrics["selection_score"] = score(test_metrics)
        rows.extend([train_metrics, test_metrics])
        if best is None or train_metrics["selection_score"] > best[1]["selection_score"]:
            best = (params, train_metrics)
        print(
            f"{params['label']}: train_pnl={train_metrics['total_pnl']:.2f}, "
            f"test_pnl={test_metrics['total_pnl']:.2f}, "
            f"train_trades={train_metrics['trade_count']}, test_trades={test_metrics['trade_count']}"
        )

    result_df = pd.DataFrame(rows)
    result_df.to_csv(REPORT_DIR / "adaptive_param_comparison.csv", index=False, encoding="utf-8-sig")

    best_params = best[0]
    best_strategy, best_test_metrics = run_strategy(test_df, best_params)
    trade_log_to_frame(best_strategy.trade_log).to_csv(
        REPORT_DIR / "adaptive_best_test_trade_log.csv",
        index=False,
        encoding="utf-8-sig",
    )
    metrics_to_frame({"adaptive_best_test": best_test_metrics}).to_csv(
        REPORT_DIR / "adaptive_best_test_metrics.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame([best_params]).to_csv(REPORT_DIR / "adaptive_best_params.csv", index=False, encoding="utf-8-sig")

    print(f"best_params={best_params}")
    print(f"best_test_metrics={best_test_metrics}")
    print(f"reports saved to {REPORT_DIR}")


if __name__ == "__main__":
    main()
