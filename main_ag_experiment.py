from pathlib import Path

import argparse
import pandas as pd

from backtestengine import BacktestEngine
from baseline_strategies import PureMomentumStrategy, PureOBIStrategy
from futures_config import AG_CONFIG
from metrics import calculate_metrics, metrics_to_frame, trade_log_to_frame
from combined_obi_momentum_strategy import TickMomentumStrategy


DATA_PATH = Path("data") / "ag_202604_cleaned.csv"
REPORT_DIR = Path("outputs") / "ag_202604"

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


BASE_PARAMS = {
    "expected_profit_ticks": 8,
    "stop_loss_ticks": 4,
    "max_holding_ticks": 300,
    "is_mean_reversion": False,
    "min_depth": 5,
    "max_spread": 8.0,
}


PARAM_CANDIDATES = [
    {
        "label": "base_trend",
        "momentum_window": 90,
        "obi_threshold": 0.5,
        "entry_threshold": 2.0,
        "obi_weight": 2.0,
        **BASE_PARAMS,
    },
    {
        "label": "fast_trend",
        "momentum_window": 30,
        "obi_threshold": 0.4,
        "entry_threshold": 1.5,
        "obi_weight": 2.0,
        **BASE_PARAMS,
    },
    {
        "label": "slow_trend",
        "momentum_window": 180,
        "obi_threshold": 0.6,
        "entry_threshold": 3.0,
        "obi_weight": 2.0,
        **BASE_PARAMS,
    },
    {
        "label": "tight_exit",
        "momentum_window": 60,
        "obi_threshold": 0.5,
        "entry_threshold": 2.0,
        "obi_weight": 2.0,
        **{**BASE_PARAMS, "expected_profit_ticks": 6, "stop_loss_ticks": 3, "max_holding_ticks": 180},
    },
    {
        "label": "wide_exit",
        "momentum_window": 120,
        "obi_threshold": 0.5,
        "entry_threshold": 2.5,
        "obi_weight": 2.0,
        **{**BASE_PARAMS, "expected_profit_ticks": 12, "stop_loss_ticks": 6, "max_holding_ticks": 600},
    },
    {
        "label": "mean_reversion",
        "momentum_window": 90,
        "obi_threshold": 0.5,
        "entry_threshold": 2.0,
        "obi_weight": 2.0,
        **{**BASE_PARAMS, "is_mean_reversion": True},
    },
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


def build_engine():
    return BacktestEngine(data_path=None, **AG_CONFIG.to_engine_kwargs())


def build_strategy(strategy_name, backtest_engine, params):
    strategy_params = {**BASE_PARAMS, **params}
    strategy_params.pop("label", None)

    if strategy_name == "pure_momentum":
        return PureMomentumStrategy(
            engine=backtest_engine,
            momentum_window=strategy_params["momentum_window"],
            entry_threshold=strategy_params["entry_threshold"],
            is_ideal=False,
            expected_profit_ticks=strategy_params["expected_profit_ticks"],
            stop_loss_ticks=strategy_params["stop_loss_ticks"],
            max_holding_ticks=strategy_params["max_holding_ticks"],
            is_mean_reversion=False,
            min_depth=strategy_params["min_depth"],
            max_spread=strategy_params["max_spread"],
        )
    if strategy_name == "pure_mean_reversion":
        return PureMomentumStrategy(
            engine=backtest_engine,
            momentum_window=strategy_params["momentum_window"],
            entry_threshold=strategy_params["entry_threshold"],
            is_ideal=False,
            expected_profit_ticks=strategy_params["expected_profit_ticks"],
            stop_loss_ticks=strategy_params["stop_loss_ticks"],
            max_holding_ticks=strategy_params["max_holding_ticks"],
            is_mean_reversion=True,
            min_depth=strategy_params["min_depth"],
            max_spread=strategy_params["max_spread"],
        )
    if strategy_name == "pure_obi":
        return PureOBIStrategy(
            engine=backtest_engine,
            obi_threshold=strategy_params["obi_threshold"],
            is_ideal=False,
            expected_profit_ticks=strategy_params["expected_profit_ticks"],
            stop_loss_ticks=strategy_params["stop_loss_ticks"],
            max_holding_ticks=strategy_params["max_holding_ticks"],
            is_mean_reversion=False,
            min_depth=strategy_params["min_depth"],
            max_spread=strategy_params["max_spread"],
        )
    if strategy_name == "obi_mean_reversion":
        return PureOBIStrategy(
            engine=backtest_engine,
            obi_threshold=strategy_params["obi_threshold"],
            is_ideal=False,
            expected_profit_ticks=strategy_params["expected_profit_ticks"],
            stop_loss_ticks=strategy_params["stop_loss_ticks"],
            max_holding_ticks=strategy_params["max_holding_ticks"],
            is_mean_reversion=True,
            min_depth=strategy_params["min_depth"],
            max_spread=strategy_params["max_spread"],
        )
    if strategy_name == "obi_momentum":
        is_mean_reversion = strategy_params.pop("is_mean_reversion", False)
        return TickMomentumStrategy(
            engine=backtest_engine,
            is_ideal=False,
            is_mean_reversion=is_mean_reversion,
            **strategy_params,
        )
    if strategy_name == "obi_momentum_mean_reversion":
        strategy_params.pop("is_mean_reversion", None)
        return TickMomentumStrategy(
            engine=backtest_engine,
            is_ideal=False,
            is_mean_reversion=True,
            **strategy_params,
        )
    raise ValueError(f"Unknown strategy: {strategy_name}")


def run_strategy(market_data, strategy_name, params):
    backtest_engine = build_engine()
    strategy = build_strategy(strategy_name, backtest_engine, params)

    for tick_record in market_data[USE_COLUMNS].to_dict("records"):
        backtest_engine.current_tick = tick_record
        strategy.on_tick(tick_record)

    strategy.force_close_at_end()
    performance_metrics = calculate_metrics(strategy)
    performance_metrics["strategy"] = strategy_name
    performance_metrics["param_label"] = params.get("label", "default")
    performance_metrics["tick_count"] = len(market_data)
    performance_metrics["start"] = str(market_data["datetime"].min()) if len(market_data) else ""
    performance_metrics["end"] = str(market_data["datetime"].max()) if len(market_data) else ""
    return strategy, performance_metrics


def split_train_test_by_date(market_data, train_ratio=0.7):
    dates = sorted(market_data["date"].unique())
    split_idx = max(1, int(len(dates) * train_ratio))
    train_dates = set(dates[:split_idx])
    test_dates = set(dates[split_idx:])
    return market_data[market_data["date"].isin(train_dates)].copy(), market_data[market_data["date"].isin(test_dates)].copy()


def walk_forward_date_folds(df):
    dates = sorted(df["date"].unique())
    folds = [
        ("fold_1", dates[:7], dates[7:11]),
        ("fold_2", dates[:11], dates[11:15]),
        ("fold_3", dates[:15], dates[15:]),
    ]
    for fold_name, train_dates, test_dates in folds:
        if not train_dates or not test_dates:
            continue
        yield (
            fold_name,
            df[df["date"].isin(set(train_dates))].copy(),
            df[df["date"].isin(set(test_dates))].copy(),
        )


def score_for_selection(metrics):
    if metrics["trade_count"] < 5:
        return -1e9
    return (
        metrics["total_pnl"]
        - 0.8 * metrics["max_drawdown"]
        + 10.0 * metrics["win_rate"]
        - 5.0 * metrics["timeout_rate"]
    )


def run_param_search(train_data):
    rows = []
    best = None
    for params in PARAM_CANDIDATES:
        _, performance_metrics = run_strategy(train_data, "obi_momentum", params)
        performance_metrics["selection_score"] = score_for_selection(performance_metrics)
        rows.append(performance_metrics)
        if best is None or performance_metrics["selection_score"] > best[1]["selection_score"]:
            best = (params, performance_metrics)
        print(
            f"param={params['label']} pnl={performance_metrics['total_pnl']:.2f} "
            f"dd={performance_metrics['max_drawdown']:.2f} trades={performance_metrics['trade_count']} "
            f"score={performance_metrics['selection_score']:.2f}"
        )
    return best[0], pd.DataFrame(rows)


def run_strategy_comparison(train_data, test_data, best_params):
    rows = []
    strategies = [
        "pure_momentum",
        "pure_mean_reversion",
        "pure_obi",
        "obi_mean_reversion",
        "obi_momentum",
        "obi_momentum_mean_reversion",
    ]
    for split_name, split_data in [("train", train_data), ("test", test_data)]:
        for strategy_name in strategies:
            _, performance_metrics = run_strategy(split_data, strategy_name, best_params)
            performance_metrics["split"] = split_name
            performance_metrics["logic_type"] = (
                "mean_reversion" if "mean_reversion" in strategy_name else "trend_following"
            )
            rows.append(performance_metrics)
            print(
                f"{split_name} {strategy_name}: pnl={performance_metrics['total_pnl']:.2f}, "
                f"trades={performance_metrics['trade_count']}, win={performance_metrics['win_rate']:.2%}"
            )
    return pd.DataFrame(rows)


def run_walk_forward(market_data, best_params):
    rows = []
    for fold_name, train_data, test_data in walk_forward_date_folds(market_data):
        for split_name, split_data in [("train", train_data), ("test", test_data)]:
            _, performance_metrics = run_strategy(split_data, "obi_momentum", best_params)
            performance_metrics["fold"] = fold_name
            performance_metrics["split"] = split_name
            rows.append(performance_metrics)
            print(
                f"{fold_name} {split_name}: pnl={performance_metrics['total_pnl']:.2f}, "
                f"trades={performance_metrics['trade_count']}, win={performance_metrics['win_rate']:.2%}"
            )
    return pd.DataFrame(rows)


def save_best_trade_log(test_data, best_params):
    strategy, _ = run_strategy(test_data, "obi_momentum", best_params)
    trade_log_to_frame(strategy.trade_log).to_csv(
        REPORT_DIR / "ag_best_test_trade_log.csv",
        index=False,
        encoding="utf-8-sig",
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Run AG 202604 strategy experiments.")
    parser.add_argument("--data-path", default=str(DATA_PATH), help="Cleaned AG CSV path.")
    parser.add_argument("--report-dir", default=str(REPORT_DIR), help="Report output directory.")
    parser.add_argument(
        "--every-nth",
        type=int,
        default=1,
        help="Use every Nth tick. Keep 1 for final results; use 20/50 for quick smoke tests.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    global REPORT_DIR
    REPORT_DIR = Path(args.report_dir)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    market_data = load_market_data(Path(args.data_path), every_nth=max(1, args.every_nth))
    train_data, test_data = split_train_test_by_date(market_data)

    print(f"data rows={len(market_data)}, days={market_data['date'].nunique()}")
    print(f"train rows={len(train_data)}, days={train_data['date'].nunique()}")
    print(f"test rows={len(test_data)}, days={test_data['date'].nunique()}")

    best_params, param_df = run_param_search(train_data)
    param_df.to_csv(REPORT_DIR / "ag_param_search_summary.csv", index=False, encoding="utf-8-sig")

    comparison_df = run_strategy_comparison(train_data, test_data, best_params)
    comparison_df.to_csv(REPORT_DIR / "ag_strategy_comparison.csv", index=False, encoding="utf-8-sig")

    walk_forward_df = run_walk_forward(market_data, best_params)
    walk_forward_df.to_csv(REPORT_DIR / "ag_walk_forward_summary.csv", index=False, encoding="utf-8-sig")

    save_best_trade_log(test_data, best_params)
    metrics_to_frame({"best_params": best_params}).to_csv(
        REPORT_DIR / "ag_best_params.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print(f"best_params={best_params}")
    print(f"reports saved to {REPORT_DIR}")


if __name__ == "__main__":
    main()
