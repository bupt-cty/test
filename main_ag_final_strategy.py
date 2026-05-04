from pathlib import Path

import pandas as pd

from adaptive_trend_strategy import AdaptiveTrendStrategy
from backtestengine import BacktestEngine
from futures_config import AG_CONFIG
from metrics import calculate_metrics, metrics_to_frame, trade_log_to_frame
from monte_carlo import bootstrap_trade_paths, save_monte_carlo_outputs, summarize_simulations


DATA_PATH = Path("data") / "ag_202604_cleaned.csv"
REPORT_DIR = Path("outputs") / "ag_202604_final"

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

FINAL_PARAMS = {
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
    "trade_direction": "both",
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


def split_by_date(market_data, train_ratio=0.7):
    dates = sorted(market_data["date"].unique())
    split_idx = max(1, int(len(dates) * train_ratio))
    train_dates = set(dates[:split_idx])
    test_dates = set(dates[split_idx:])
    return market_data[market_data["date"].isin(train_dates)].copy(), market_data[market_data["date"].isin(test_dates)].copy()


def build_engine():
    return BacktestEngine(data_path=None, **AG_CONFIG.to_engine_kwargs())


def run_strategy(market_data):
    backtest_engine = build_engine()
    strategy_params = dict(FINAL_PARAMS)
    strategy_label = strategy_params.pop("label")
    strategy_instance = AdaptiveTrendStrategy(engine=backtest_engine, **strategy_params)

    for tick_record in market_data[USE_COLUMNS].to_dict("records"):
        backtest_engine.current_tick = tick_record
        strategy_instance.on_tick(tick_record)

    strategy_instance.force_close_at_end()
    performance_metrics = calculate_metrics(strategy_instance)
    performance_metrics["strategy"] = "adaptive_trend"
    performance_metrics["param_label"] = strategy_label
    performance_metrics["tick_count"] = len(market_data)
    performance_metrics["start"] = str(market_data["datetime"].min()) if len(market_data) else ""
    performance_metrics["end"] = str(market_data["datetime"].max()) if len(market_data) else ""
    return strategy_instance, performance_metrics


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    market_data = load_market_data()
    train_data, test_data = split_by_date(market_data)

    train_strategy, train_metrics = run_strategy(train_data)
    test_strategy, test_metrics = run_strategy(test_data)
    full_strategy, full_metrics = run_strategy(market_data)

    metrics_to_frame({
        "train": train_metrics,
        "test": test_metrics,
        "full": full_metrics,
    }).to_csv(REPORT_DIR / "ag_final_metrics.csv", index=False, encoding="utf-8-sig")

    trade_log_to_frame(test_strategy.trade_log).to_csv(
        REPORT_DIR / "ag_final_test_trade_log.csv",
        index=False,
        encoding="utf-8-sig",
    )
    trade_log_to_frame(full_strategy.trade_log).to_csv(
        REPORT_DIR / "ag_final_full_trade_log.csv",
        index=False,
        encoding="utf-8-sig",
    )

    monte_carlo_paths = bootstrap_trade_paths(
        pd.read_csv(REPORT_DIR / "ag_final_test_trade_log.csv")["net_profit"].astype(float).to_numpy(),
        n_simulations=3000,
        block_size=5,
        seed=42,
    )
    monte_carlo_summary = summarize_simulations(monte_carlo_paths)
    save_monte_carlo_outputs(monte_carlo_paths, monte_carlo_summary, REPORT_DIR, prefix="ag_final_test")

    pd.DataFrame([FINAL_PARAMS]).to_csv(REPORT_DIR / "ag_final_params.csv", index=False, encoding="utf-8-sig")

    print("train_metrics:", train_metrics)
    print("test_metrics:", test_metrics)
    print("full_metrics:", full_metrics)
    print(f"reports saved to {REPORT_DIR}")


if __name__ == "__main__":
    main()
