# 期货市场高频交易项目使用说明

这个项目用于毕业设计《期货市场高频交易的研究与实现》。当前主线实验对象是上海期货交易所白银 `AG` 主力连续合约的 Tick 数据，项目重点不是实盘下单，而是完成：

- Tick 数据清洗与拼接
- 基于 Level-1 盘口的保守撮合回测
- 趋势、OBI、组合策略和自适应趋势策略对比
- 参数搜索、训练/测试切分、walk-forward 验证
- 蒙特卡洛风险评估
- 按波动率、趋势、流动性、日夜盘分层分析

目前项目没有完成螺纹钢 `RB` 的完整分析，也没有完成 CTP/SimNow 联调。论文里建议把这两点写成未展开或未来工作。

## 1. 运行环境

建议使用 Python 3.10 以上版本。项目主要依赖：

- `pandas`
- `numpy`

如果本机还没有安装依赖，在项目根目录执行：

```powershell
pip install pandas numpy
```

项目根目录是：

```powershell
E:\code\High-Frequency-Trading
```

后面所有命令都建议先进入这个目录：

```powershell
cd E:\code\High-Frequency-Trading
```

## 2. 项目目录结构

```text
High-Frequency-Trading/
+-- src/                         原始 AG 主力连续 Tick CSV 文件
+-- data/                        清洗后的统一数据
+-- outputs/                     实验输出结果
+-- backtestengine.py            回测撮合和手续费模型
+-- tick_strategy_base.py        策略基类和通用开平仓逻辑
+-- baseline_strategies.py       基准策略：纯动量、纯 OBI
+-- combined_obi_momentum_strategy.py
|                                OBI + 动量组合策略
+-- adaptive_trend_strategy.py   最终使用的自适应趋势策略
+-- clean_ag_continuous.py       原始 Tick 数据清洗脚本
+-- main_ag_experiment.py        基础策略对比、参数搜索、walk-forward
+-- main_adaptive_ag_experiment.py
|                                自适应趋势策略候选参数比较
+-- main_ag_final_strategy.py    最终策略回测和蒙特卡洛
+-- main_ag_stratified_analysis.py
|                                分层分析
+-- metrics.py                   收益、回撤、胜率等指标计算
+-- monte_carlo.py               蒙特卡洛重采样工具
+-- optimizer.py                 UCB 参数优化器，目前未接入主实验流程
```

## 3. 一次性跑通项目

如果只是想从头到尾生成主要结果，按下面顺序执行。

### 第一步：清洗原始 Tick 数据

原始数据放在 `src/` 目录，文件名类似：

```text
ag主力连续_20260401.csv
ag主力连续_20260402.csv
...
```

执行：

```powershell
python clean_ag_continuous.py --pattern "ag主力连续_*.csv"
```

输出文件：

```text
data/ag_202604_cleaned.csv
```

这个文件是后续所有 AG 实验的统一输入。它包含：

- `datetime`：Tick 时间
- `last_price`：最新价
- `volume`：累计成交量
- `amount`：累计成交额
- `bid_price1`、`bid_volume1`：买一价和买一量
- `ask_price1`、`ask_volume1`：卖一价和卖一量
- `tick_volume`：当前 Tick 新增成交量
- `tick_amount`：当前 Tick 新增成交额

如果 `data/ag_202604_cleaned.csv` 已经存在，可以跳过这一步。

### 第二步：跑基础策略实验

```powershell
python main_ag_experiment.py
```

这个脚本会做三件事：

- 在训练集上搜索组合策略参数
- 对比 `pure_momentum`、`pure_obi`、`obi_momentum`
- 做 walk-forward 日期滚动验证

输出目录：

```text
outputs/ag_202604/
```

主要结果文件：

- `ag_param_search_summary.csv`：候选参数在训练集上的表现
- `ag_strategy_comparison.csv`：趋势跟随、均值反转、纯 OBI、组合策略的训练/测试对比
- `ag_walk_forward_summary.csv`：walk-forward 验证结果
- `ag_best_test_trade_log.csv`：最佳参数在测试集上的逐笔交易记录
- `ag_best_params.csv`：选出的最佳参数

如果只是想快速试跑，不想等太久，可以抽样运行：

```powershell
python main_ag_experiment.py --every-nth 50 --report-dir outputs/ag_202604_smoke
```

`--every-nth 50` 表示每 50 条 Tick 取一条，结果不能用于论文正式结论，只适合检查代码能不能跑通。

### 第三步：跑自适应趋势策略参数比较

```powershell
python main_adaptive_ag_experiment.py
```

这个脚本会比较多组自适应趋势策略参数，例如：

- `ma_10m_60m`
- `ma_30m_120m`
- `swing_trend`
- `ma_30m_120m_wide`

输出目录：

```text
outputs/ag_202604_adaptive/
```

主要结果文件：

- `adaptive_param_comparison.csv`：所有候选参数的训练/测试表现
- `adaptive_best_test_trade_log.csv`：最佳参数测试集逐笔交易
- `adaptive_best_test_metrics.csv`：最佳参数测试集指标
- `adaptive_best_params.csv`：最佳参数配置

### 第四步：跑最终策略

```powershell
python main_ag_final_strategy.py
```

这是目前最适合论文主结果引用的入口。它使用 `main_ag_final_strategy.py` 中的 `FINAL_PARAMS`，分别跑：

- 训练集
- 测试集
- 全样本

并且会对测试集逐笔收益做蒙特卡洛重采样。

输出目录：

```text
outputs/ag_202604_final/
```

主要结果文件：

- `ag_final_metrics.csv`：训练集、测试集、全样本核心指标
- `ag_final_test_trade_log.csv`：测试集逐笔交易记录
- `ag_final_full_trade_log.csv`：全样本逐笔交易记录
- `ag_final_test_monte_carlo_paths.csv`：蒙特卡洛模拟路径
- `ag_final_test_monte_carlo_summary.csv`：蒙特卡洛汇总结果
- `ag_final_params.csv`：最终策略参数

论文里最常用的是：

```text
outputs/ag_202604_final/ag_final_metrics.csv
outputs/ag_202604_final/ag_final_test_monte_carlo_summary.csv
outputs/ag_202604_final/ag_final_test_trade_log.csv
```

### 第五步：跑分层分析

```powershell
python main_ag_stratified_analysis.py
```

这个脚本会分析最终策略在哪些市场环境下表现更好或更差。分层维度包括：

- 波动率：`volatility_regime`
- 趋势强度：`trend_regime`
- 流动性：`liquidity_regime`
- 交易时段：`session_regime`，即日盘/夜盘

输出目录：

```text
outputs/ag_202604_stratified/
```

主要结果文件：

- `ag_stratified_tick_profile.csv`：不同市场环境下 Tick 本身的统计特征
- `ag_stratified_trade_summary.csv`：不同市场环境下交易表现
- `ag_stratified_annotated_trades.csv`：带有分层标签的逐笔交易
- `ag_stratified_overall_metrics.csv`：最终策略整体指标

这个部分很适合写进论文的“策略适用市场环境分析”。

## 4. 推荐论文实验顺序

论文或答辩展示时，建议按下面顺序讲：

1. 数据来源与清洗  
   对应 `clean_ag_continuous.py` 和 `data/ag_202604_cleaned.csv`。

2. 回测引擎和交易成本模型  
   对应 `backtestengine.py`。说明买入用卖一价、卖出用买一价，并考虑手续费。

3. 基线策略对比  
   对应 `baseline_strategies.py`、`combined_obi_momentum_strategy.py` 和 `main_ag_experiment.py`。这里同时保留趋势跟随和均值反转版本，方便回应开题报告中的两个子策略承诺。

4. 参数搜索与样本外验证  
   对应 `ag_param_search_summary.csv`、`ag_strategy_comparison.csv`、`ag_walk_forward_summary.csv`。

5. 最终策略结果  
   对应 `adaptive_trend_strategy.py` 和 `main_ag_final_strategy.py`。

6. 蒙特卡洛风险评估  
   对应 `monte_carlo.py` 和 `ag_final_test_monte_carlo_summary.csv`。

7. 分层分析  
   对应 `main_ag_stratified_analysis.py`，说明策略更适合哪些市场状态。

## 5. 每个核心模块是干什么的

### `clean_ag_continuous.py`

负责把 `src/` 目录下每天一个的原始 Tick 文件合并成一个干净的数据文件。

它会做：

- 检查必要字段是否存在
- 把 `TradingDay`、`UpdateTime`、`UpdateMillisec` 合成真正的 `datetime`
- 修正夜盘日期
- 过滤非交易时段
- 删除重复 Tick
- 过滤无效盘口，例如卖一价小于等于买一价
- 计算每个 Tick 的新增成交量和新增成交额

### `backtestengine.py`

负责模拟订单成交，是整个项目的“交易所撮合简化版”。

核心逻辑：

- 买入时按 `ask_price1` 成交
- 卖出时按 `bid_price1` 成交
- 如果一档盘口数量不够，会按最小变动价位继续向下一档虚拟穿透
- 开仓、平今、平昨可以使用不同手续费率
- 每次成交返回成交价、成交量和手续费

注意：当前模型是研究用的简化模型，不是真实交易所撮合系统。

### `tick_strategy_base.py`

所有 Tick 策略的基类。它提供了很多通用功能：

- 当前持仓状态
- 开仓和平仓
- 止盈、止损、超时平仓
- OBI 指标计算
- 交易成本过滤
- 逐笔交易日志记录
- 收益曲线记录

后面的具体策略只需要关心“什么时候开仓”和“什么时候平仓”。

### `baseline_strategies.py`

基准策略文件，用于做对照实验。

里面主要有：

- `PureMomentumStrategy`：只看价格动量
- `PureOBIStrategy`：只看买卖盘不平衡 OBI

它们不一定是最终策略，但很重要，因为论文需要证明最终策略不是凭空来的，而是比简单基准更合理。

### `combined_obi_momentum_strategy.py`

组合策略文件，把价格动量和 OBI 合在一起。

大致思想：

- 价格短期上涨，说明有动量
- 买盘明显强于卖盘，说明盘口支持上涨
- 两者同时满足时，更倾向于开多
- 反向条件满足时，更倾向于开空

`main_ag_experiment.py` 会用它和两个基准策略做对比。

### `adaptive_trend_strategy.py`

当前最终策略的核心实现。

它使用快慢均线判断趋势，并加入：

- 入场阈值
- 出场阈值
- 止盈
- 止损
- 移动止损
- 最大持仓 Tick 数
- 冷却时间
- 流动性过滤

最终策略参数写在 `main_ag_final_strategy.py` 的 `FINAL_PARAMS` 中。

### `main_ag_experiment.py`

基础实验入口。

它会：

- 读取清洗后的 AG 数据
- 按日期切分训练集和测试集
- 在训练集上做候选参数搜索
- 比较趋势跟随、均值反转、纯 OBI、OBI 均值反转、OBI+动量组合策略
- 做 walk-forward 验证
- 输出 CSV 结果

适合用于论文里的“基线对比”和“参数选择过程”。如果均值反转结果不好，也可以作为负结果分析：说明在当前 AG Tick 样本和交易成本约束下，短周期反转信号没有趋势类信号稳定。

### `main_adaptive_ag_experiment.py`

自适应趋势策略候选参数比较入口。

它会测试多组人工设计的参数组合，分别计算训练集和测试集表现，再根据训练集评分选出最佳参数。

适合用于说明最终策略参数是怎样筛出来的。

### `main_ag_final_strategy.py`

最终实验入口，也是最建议正式跑的脚本。

它会：

- 使用固定最终参数 `FINAL_PARAMS`
- 跑训练集、测试集、全样本
- 保存逐笔交易日志
- 对测试集收益做蒙特卡洛模拟
- 输出最终指标

论文主结果建议主要引用这个脚本的输出。

### `main_ag_stratified_analysis.py`

分层分析入口。

它先给每个 Tick 打标签，例如：

- 高波动、中波动、低波动
- 强趋势、中趋势、弱趋势
- 高流动性、中流动性、低流动性
- 日盘、夜盘

然后把交易记录映射回这些市场环境，统计策略在哪些情况下更赚钱、在哪些情况下风险更高。

### `metrics.py`

绩效指标工具。

它会计算：

- `total_pnl`：总收益
- `max_drawdown`：最大回撤
- `sharpe_ratio`：夏普比率，这里是基于收益序列的简化计算
- `trade_count`：交易次数
- `win_rate`：胜率
- `average_net_profit`：平均每笔净收益
- `profit_loss_ratio`：盈亏比
- `total_cost`：总交易成本
- `timeout_rate`：超时平仓比例

### `monte_carlo.py`

蒙特卡洛工具。

它不是重新模拟行情，而是对已经发生的逐笔交易收益进行重采样，生成很多条可能的收益路径，用来估计：

- 最终收益均值
- 最终收益 5%、50%、95% 分位数
- 最终收益为正的概率
- 最大回撤均值
- 最大回撤 95% 分位数

### `optimizer.py`

UCB 参数优化器。

这个文件实现了 Upper Confidence Bound 思想，用于在有限计算次数下选择更值得尝试的参数组合。不过当前 AG 主线实验没有真正调用它。

论文写作时建议二选一：

- 补充一个 UCB 参数搜索实验
- 或者把 UCB 写成“已实现的探索模块，未纳入最终主实验”

## 6. 输出文件怎么看

### 指标表

例如：

```text
outputs/ag_202604_final/ag_final_metrics.csv
```

重点看这些列：

- `scenario`：训练集、测试集或全样本
- `total_pnl`：总收益
- `max_drawdown`：最大回撤
- `sharpe_ratio`：收益稳定性指标
- `trade_count`：交易次数
- `win_rate`：胜率
- `average_net_profit`：平均每笔净收益
- `total_cost`：总手续费成本
- `cost_to_gross_profit`：成本占毛利润比例

### 逐笔交易表

例如：

```text
outputs/ag_202604_final/ag_final_test_trade_log.csv
```

重点看这些列：

- `entry_time`：开仓时间
- `exit_time`：平仓时间
- `direction`：多单或空单
- `entry_price`：开仓成交价
- `exit_price`：平仓成交价
- `gross_profit`：扣成本前收益
- `total_cost`：本笔交易总成本
- `net_profit`：扣成本后收益
- `holding_ticks`：持仓 Tick 数
- `close_reason`：平仓原因

### 蒙特卡洛汇总表

例如：

```text
outputs/ag_202604_final/ag_final_test_monte_carlo_summary.csv
```

重点看：

- `prob_positive_final_pnl`：模拟路径最终盈利的概率
- `final_pnl_p05`：较差 5% 情况下的最终收益
- `final_pnl_p50`：中位数收益
- `final_pnl_p95`：较好 5% 情况下的最终收益
- `max_drawdown_p95`：较极端情况下的最大回撤

## 7. 常见问题

### 运行时提示找不到数据文件

先确认是否存在：

```text
data/ag_202604_cleaned.csv
```

如果不存在，先运行：

```powershell
python clean_ag_continuous.py --pattern "ag主力连续_*.csv"
```

### 清洗脚本提示没有匹配到文件

检查 `src/` 目录里的文件名。如果文件名不是 `ag主力连续_*.csv`，需要改 `--pattern` 参数。

例如：

```powershell
python clean_ag_continuous.py --pattern "*.csv"
```

### 正式跑很慢怎么办

先用抽样模式测试：

```powershell
python main_ag_experiment.py --every-nth 50 --report-dir outputs/ag_202604_smoke
python main_ag_stratified_analysis.py --every-nth 50 --report-dir outputs/ag_202604_stratified_smoke
```

确认没问题后，再去掉 `--every-nth` 跑正式结果。

### 为什么有些结果亏损

这是正常的。高频策略对交易成本非常敏感，论文不一定要证明所有策略都赚钱。更重要的是说明：

- 简单策略在真实成本下可能失效
- 成本模型会显著影响结果
- 最终策略经过筛选、测试和风险评估后更稳健

### 当前项目最适合在论文里怎么表述

建议表述为：

> 本文以上海期货交易所白银主力连续合约 Tick 数据为研究对象，构建了基于 Level-1 盘口的事件驱动回测框架，在考虑手续费、买卖价差和盘口流动性约束的基础上，对动量、盘口不平衡和自适应趋势策略进行了样本内参数筛选、样本外验证、蒙特卡洛风险评估和市场状态分层分析。

不要写成已经完成真实 CTP 实盘交易，也不要写成策略对所有期货品种普遍有效。
