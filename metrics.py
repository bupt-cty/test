import numpy as np
import pandas as pd


def max_drawdown(equity_curve):
    if not equity_curve:
        return 0.0
    curve = np.asarray(equity_curve, dtype=float)
    running_max = np.maximum.accumulate(curve)
    drawdowns = running_max - curve
    return float(np.max(drawdowns))


def sharpe_ratio(equity_curve):
    if len(equity_curve) < 3:
        return 0.0

    returns = np.diff(np.asarray(equity_curve, dtype=float))
    std = np.std(returns, ddof=1)
    if std == 0:
        return 0.0
    return float(np.mean(returns) / std * np.sqrt(len(returns)))


def trade_log_to_frame(trade_log):
    columns = [
        'entry_time',
        'exit_time',
        'direction',
        'entry_price',
        'exit_price',
        'gross_profit',
        'entry_cost',
        'exit_cost',
        'total_cost',
        'net_profit',
        'holding_ticks',
        'close_reason',
        'equity_after_trade',
    ]
    return pd.DataFrame(trade_log, columns=columns)


def calculate_metrics(strategy):
    trade_df = trade_log_to_frame(getattr(strategy, 'trade_log', []))
    pnl_history = getattr(strategy, 'pnl_history', [])
    total_pnl = float(getattr(strategy, 'total_pnl', 0.0))

    if trade_df.empty:
        return {
            'total_pnl': total_pnl,
            'max_drawdown': max_drawdown(pnl_history),
            'sharpe_ratio': sharpe_ratio(pnl_history),
            'trade_count': 0,
            'win_rate': 0.0,
            'average_net_profit': 0.0,
            'average_win': 0.0,
            'average_loss': 0.0,
            'profit_loss_ratio': 0.0,
            'gross_profit_sum': 0.0,
            'gross_loss_sum': 0.0,
            'total_cost': 0.0,
            'cost_to_gross_profit': 0.0,
            'average_holding_ticks': 0.0,
            'take_profit_count': 0,
            'stop_loss_count': 0,
            'timeout_count': 0,
            'force_close_count': 0,
            'timeout_rate': 0.0,
        }

    wins = trade_df[trade_df['net_profit'] > 0]
    losses = trade_df[trade_df['net_profit'] < 0]
    close_reason_counts = trade_df['close_reason'].value_counts()
    gross_profit_sum = float(wins['net_profit'].sum())
    gross_loss_sum = float(abs(losses['net_profit'].sum()))
    average_win = float(wins['net_profit'].mean()) if not wins.empty else 0.0
    average_loss = float(abs(losses['net_profit'].mean())) if not losses.empty else 0.0
    total_cost = float(trade_df['total_cost'].sum())
    raw_gross_profit = float(trade_df['gross_profit'].clip(lower=0).sum())

    return {
        'total_pnl': total_pnl,
        'max_drawdown': max_drawdown(pnl_history),
        'sharpe_ratio': sharpe_ratio(pnl_history),
        'trade_count': int(len(trade_df)),
        'win_rate': float(len(wins) / len(trade_df)),
        'average_net_profit': float(trade_df['net_profit'].mean()),
        'average_win': average_win,
        'average_loss': average_loss,
        'profit_loss_ratio': float(average_win / average_loss) if average_loss > 0 else 0.0,
        'gross_profit_sum': gross_profit_sum,
        'gross_loss_sum': gross_loss_sum,
        'total_cost': total_cost,
        'cost_to_gross_profit': float(total_cost / raw_gross_profit) if raw_gross_profit > 0 else 0.0,
        'average_holding_ticks': float(trade_df['holding_ticks'].mean()),
        'take_profit_count': int(close_reason_counts.get('take_profit', 0)),
        'stop_loss_count': int(close_reason_counts.get('stop_loss', 0)),
        'timeout_count': int(close_reason_counts.get('timeout', 0)),
        'force_close_count': int(close_reason_counts.get('force_close', 0)),
        'timeout_rate': float(close_reason_counts.get('timeout', 0) / len(trade_df)),
    }


def metrics_to_frame(metrics_by_name):
    rows = []
    for scenario, values in metrics_by_name.items():
        row = {'scenario': scenario}
        row.update(values)
        rows.append(row)
    return pd.DataFrame(rows)
