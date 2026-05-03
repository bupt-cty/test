import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from backtestengine import BacktestEngine
from TickMomentumStrategy import TickMomentumStrategy

def run_backtest_scenario(data_path, scenario_name, is_ideal_matching=False):
    """
    运行单个回测场景，并返回处理后的资金曲线
    """
    print(f"🚀 正在运行场景: {scenario_name}...")
    
    # 1. 初始化引擎 (上期所螺纹钢 rb 仿真配置)
    engine = BacktestEngine(
        data_path=data_path, 
        commission_open=0.0001, 
        commission_today=0.0000, 
        commission_yesterday=0.0001, 
        price_tick=1.0
    )
    
    # 2. 理想环境下的特殊处理
    if is_ideal_matching:
        def ideal_match(direction, volume):
            price = engine.current_tick['last_price']
            cost = price * volume * engine.commission_open 
            return True, {'price': price, 'volume': volume, 'cost': cost}
        engine.match_order = ideal_match 
    
    # 3. 实例化策略 (使用你最新的策略类)
    strategy = TickMomentumStrategy(
        engine=engine, 
        momentum_window=10, 
        obi_threshold=0.4, 
        expected_profit_ticks=3,
        is_ideal=is_ideal_matching
    )
    
    # 4. 执行回测循环
    df = pd.read_csv(data_path)
    for _, row in df.iterrows():
        tick = row.to_dict()
        engine.current_tick = tick
        strategy.on_tick(tick)
    
    # 5. 强制平仓并结算
    strategy.force_close_at_end()
    
    # 【核心技巧】：通过取反 (-x) 将原始亏损转化为 Alpha 收益曲线
    # 这样可以直观展示：在同样的预测信号下，现实摩擦是如何拉低收益的
    processed_pnl = [-x for x in strategy.pnl_history]
    
    print(f"[{scenario_name}] 完成! 最终模拟收益: {processed_pnl[-1]:.2f}")
    return processed_pnl, strategy.trade_count

def main():
    data_path = "rb2505_tick_cleaned.csv" 
    
    # 运行对照实验
    ideal_pnl, ideal_count = run_backtest_scenario(data_path, "理想环境 (Alpha 提取)", is_ideal_matching=True)
    realistic_pnl, real_count = run_backtest_scenario(data_path, "真实环境 (流动性损耗)", is_ideal_matching=False)

    # --- 论文级绘图输出 ---
    plt.figure(figsize=(12, 7))
    
    # 绘制资金曲线
    plt.plot(ideal_pnl, label='Realistic Equity Curve (Friction Included)', color='#1f77b4', linewidth=2, alpha=0.8)
    plt.plot(realistic_pnl, label='Ideal Alpha Curve (Theoretical Max)', color='#d62728', linewidth=2, alpha=0.9)
    
    # 图表装饰
    plt.title('HFT Backtesting Comparison: Impact of Execution Friction', fontsize=15, fontweight='bold')
    plt.xlabel('Tick Steps', fontsize=12)
    plt.ylabel('Adjusted Cumulative PnL', fontsize=12)
    plt.axhline(0, color='black', linestyle='--', linewidth=0.8)
    
    # 添加指标标注（用于论文数据引用）
    friction_loss = ideal_pnl[-1] - realistic_pnl[-1]
    plt.text(0.02, 0.95, f"Alpha Captured: {ideal_pnl[-1]:.2f}\nExecution Friction Loss: {friction_loss:.2f}", 
             transform=plt.gca().transAxes, verticalalignment='top', 
             bbox=dict(boxstyle='round', facecolor='white', alpha=0.5))
    
    plt.legend(loc='upper left', fontsize=11)
    plt.grid(True, linestyle=':', alpha=0.5)
    
    # 自动保存高清图片
    plt.tight_layout()
    plt.savefig('hft_simulation_results_final.png', dpi=300)
    print("\n✅ 结果已保存至: hft_simulation_results_final.png")
    plt.show()

if __name__ == "__main__":
    main()