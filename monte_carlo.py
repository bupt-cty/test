import math
from pathlib import Path

import numpy as np
import pandas as pd


def max_drawdown_from_curve(equity_curve):
    if len(equity_curve) == 0:
        return 0.0
    curve = np.asarray(equity_curve, dtype=float)
    running_max = np.maximum.accumulate(curve)
    drawdowns = running_max - curve
    return float(np.max(drawdowns))


def load_trade_returns(trade_log_path):
    trade_df = pd.read_csv(trade_log_path)
    if trade_df.empty:
        raise ValueError(f"trade log is empty: {trade_log_path}")
    if 'net_profit' not in trade_df.columns:
        raise ValueError("trade log must contain a net_profit column")
    returns = trade_df['net_profit'].astype(float).to_numpy()
    return returns, trade_df


def bootstrap_trade_paths(trade_returns, n_simulations=2000, block_size=3, seed=42):
    rng = np.random.default_rng(seed)
    n_trades = len(trade_returns)
    if n_trades == 0:
        raise ValueError("trade_returns is empty")

    if block_size < 1:
        block_size = 1

    n_blocks = math.ceil(n_trades / block_size)
    records = []

    for sim_id in range(n_simulations):
        sampled = []
        for _ in range(n_blocks):
            start_idx = int(rng.integers(0, n_trades))
            for offset in range(block_size):
                sampled.append(trade_returns[(start_idx + offset) % n_trades])
        sampled = np.asarray(sampled[:n_trades], dtype=float)
        equity_curve = np.cumsum(sampled)

        records.append({
            'simulation_id': sim_id,
            'final_pnl': float(equity_curve[-1]),
            'max_drawdown': max_drawdown_from_curve(equity_curve),
            'mean_trade_pnl': float(np.mean(sampled)),
            'win_rate': float(np.mean(sampled > 0)),
            'loss_rate': float(np.mean(sampled < 0)),
        })

    return pd.DataFrame(records)


def summarize_simulations(sim_df):
    if sim_df.empty:
        return {}

    final_pnl = sim_df['final_pnl']
    max_dd = sim_df['max_drawdown']

    return {
        'simulation_count': int(len(sim_df)),
        'final_pnl_mean': float(final_pnl.mean()),
        'final_pnl_std': float(final_pnl.std(ddof=1)),
        'final_pnl_p05': float(final_pnl.quantile(0.05)),
        'final_pnl_p50': float(final_pnl.quantile(0.50)),
        'final_pnl_p95': float(final_pnl.quantile(0.95)),
        'prob_positive_final_pnl': float((final_pnl > 0).mean()),
        'max_drawdown_mean': float(max_dd.mean()),
        'max_drawdown_p95': float(max_dd.quantile(0.95)),
    }


def save_monte_carlo_outputs(sim_df, summary, output_dir, prefix="obi_momentum"):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sim_df.to_csv(output_dir / f"{prefix}_monte_carlo_paths.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([summary]).to_csv(output_dir / f"{prefix}_monte_carlo_summary.csv", index=False, encoding="utf-8-sig")
