# EVALUATION.md — 评分系统评估报告

## 数据切分

| 项目 | 值 |
|---|---|
| 切分方式 | 按赛季时间切分（3-fold CV + holdout） |
| 总球员数 | 30,483（含多赛季） |
| 参数数量 | 77 |

### 3-Fold CV 设计

| Fold | 训练赛季 | 测试赛季 | 训练球员 | 测试球员 |
|---|---|---|---|---|
| Fold 1 | 1617–2223（7 赛季） | 2324 | 21,692 | 2,774 |
| Fold 2 | 1617–2324（8 赛季） | 2425 | 24,466 | 2,772 |
| Fold 3 | 1617–2425（9 赛季） | 2526 | 27,238 | 3,245 |

## 优化器配置

| 参数 | 值 |
|---|---|
| 优化器 | `adamw_composite_objective` |
| 设备 | CUDA (RTX 5070 Ti) |
| 随机种子 | 42（稳定性测试另用 143, 244） |
| 参数数量 | 77 |
| 种群大小 | 8 |
| 迭代步数 | 150 |
| 学习率 | 0.05 |
| 软排名温度 | 4.0 |
| 初始化缩放 | 0.35 |
| 早停耐心 | 25 |

## 组合目标权重

| 维度 | 权重 | 说明 |
|---|---|---|
| Spearman rank correlation | 0.50 | 排序一致性 |
| NDCG@20 | 0.20 | Top-20 排名质量 |
| 位置内排序一致性 | 0.15 | 同位置球员相对排序 |
| 极端样本惩罚 | 0.10 | 防止极端高估/低估 |
| 先验正则 | 0.05 | 参数平滑 |

## 核心指标

### Holdout 结果（2526 赛季）

| 指标 | Baseline | Optimized | 提升 |
|---|---|---|---|
| Spearman | 0.618 | **0.740** | +0.122 |
| Pearson | 0.619 | **0.744** | +0.125 |
| Rank loss | 0.382 | **0.260** | -0.122 |
| Z-MSE | 0.762 | **0.512** | -0.250 |
| Calibration MAE | 11.0 | **6.85** | -4.15 |
| Team coverage | 0.938 | 0.938 | — |
| Teams matched | 90/96 | 90/96 | — |

### 3-Fold CV 结果

| Fold | 测试赛季 | Baseline test Spearman | Optimized test Spearman | 提升 | Optimized test Pearson |
|---|---|---|---|---|---|
| Fold 1 | 2324 | 0.442 | 0.662 | +0.220 | 0.687 |
| Fold 2 | 2425 | 0.595 | **0.792** | +0.198 | 0.766 |
| Fold 3 | 2526 | 0.575 | 0.701 | +0.126 | 0.705 |
| **平均** | — | **0.537** | **0.718** | **+0.181** | **0.719** |

### 训练集指标

| 指标 | Fold 1 | Fold 2 | Fold 3 |
|---|---|---|---|
| Baseline train Spearman | 0.376 | 0.404 | 0.469 |
| Optimized train Spearman | 0.673 | 0.656 | 0.700 |
| Optimized train Pearson | 0.677 | 0.674 | 0.703 |

### 参数稳定性（3 seeds）

| Seed | Train Spearman | Test Spearman |
|---|---|---|
| 42 | 0.655 | 0.740 |
| 143 | 0.655 | 0.735 |
| 244 | 0.655 | 0.737 |
| **Mean** | **0.655** | **0.737** |
| **Std** | **0.000** | **0.002** |

## 特征重要性

| 特征 | Spearman 下降 | 说明 |
|---|---|---|
| assists_p90 | 0.133 | 助手 p90（最重要） |
| npg_p90 | 0.072 | 非点球进球 p90 |
| minutes | 0.048 | 总分钟数 |
| g_a_volume | 0.039 | 进球+助攻总量 |
| matches | 0.037 | 比赛场次 |
| starts | 0.024 | 首发场次 |
| npg_trend | 0.007 | 进球趋势 |

## 2526 赛季联赛级指标

| 联赛 | 球队数 | Spearman | Pearson | Coverage |
|---|---|---|---|---|
| Serie A | 19 | 0.918 | 0.946 | 0.95 |
| Ligue 1 | 18 | 0.889 | 0.900 | 1.00 |
| Bundesliga | 14 | 0.886 | 0.876 | 0.778 |
| Premier League | 20 | 0.781 | 0.800 | 1.00 |
| La Liga | 19 | 0.654 | 0.809 | 0.95 |

## 2526 赛季误差案例

### 系统性低估：顶级强队

| 球队 | 联赛 | 预测 | 实际 | 误差 |
|---|---|---|---|---|
| Barcelona | La Liga | 56.3 | 94 | -37.7 |
| Real Madrid | La Liga | 52.6 | 86 | -33.4 |
| Inter | Serie A | 55.5 | 87 | -31.5 |
| Bayern Munich | Bundesliga | 59.4 | 89 | -29.6 |
| Arsenal | Premier League | 58.0 | 85 | -27.0 |
| Napoli | Serie A | 50.2 | 76 | -25.8 |
| Paris SG | Ligue 1 | 53.6 | 76 | -22.4 |

### 系统性高估：降级区球队

| 球队 | 联赛 | 预测 | 实际 | 误差 |
|---|---|---|---|---|
| Burnley | Premier League | 46.9 | 22 | +24.9 |
| Wolves | Premier League | 43.8 | 20 | +23.8 |
| Metz | Ligue 1 | 38.8 | 17 | +21.8 |
| Heidenheim | Bundesliga | 46.7 | 26 | +20.7 |
| Pisa | Serie A | 35.3 | 18 | +17.3 |

### 用户关注球队

| 球队 | 联赛 | 预测 | 实际 | 误差 |
|---|---|---|---|---|
| Everton | Premier League | 54.0 | 49 | +5.0 |
| Stuttgart | Bundesliga | 55.8 | 62 | -6.2 |
| Rennes | Ligue 1 | 49.1 | 59 | -9.9 |
| Napoli | Serie A | 50.2 | 76 | -25.8 |
| Real Madrid | La Liga | 52.6 | 86 | -33.4 |
| Arsenal | Premier League | 58.0 | 85 | -27.0 |

## 球队覆盖率（2526）

| 联赛 | 目标球队 | 评分侧球队 | 匹配球队 | Coverage |
|---|---|---|---|---|
| Premier League | 20 | 34 | 20 | 1.00 |
| Ligue 1 | 18 | 27 | 18 | 1.00 |
| La Liga | 20 | 31 | 19 | 0.95 |
| Serie A | 20 | 40 | 19 | 0.95 |
| Bundesliga | 18 | 26 | 14 | 0.778 |
| RFPL | 0 | 33 | 0 | N/A |

Bundesliga 有 4 队未匹配（Köln、Gladbach、Parma、St Pauli），已在 alias 中修复。RFPL（俄超）33 队在评分侧但无 Football-Data 目标。

## 球队聚合配置

| 参数 | 值 | 说明 |
|---|---|---|
| Minutes cap | 1,500 | 出勤上限 |
| Core minutes | 450 | 核心轮换阈值 |
| Core scale | 180 | 核心轮换缩放 |
| Capped minutes blend | 0.55 | 上限分钟权重 |
| Core rotation blend | 0.45 | 核心轮换权重 |

## Coverage 置信度规则

| 级别 | 条件 | 允许结论 |
|---|---|---|
| HIGH | coverage ≥ 0.90 | 强排序结论 |
| MEDIUM | 0.70 ≤ coverage < 0.90 | 诊断性结论 |
| LOW | coverage < 0.70 | 禁止强排序，仅低置信度诊断 |

## 模型运行登记

| 运行时间 | 设备 | Holdout Spearman | 2526 Coverage | 备注 |
|---|---|---|---|---|
| 20260609T133831Z | GPU | 0.740 | 0.938 | alias 修复后首次有效 2526 holdout |

## 待完成

- [ ] 重跑 GPU 优化器（alias 修复后）验证 Bundesliga coverage 提升
- [ ] 补充位置内指标的数值报告
- [ ] 补充跨位置总榜指标
- [ ] 补充 value_fairness OOF 残差分析
- [ ] 补充比分预测 log loss/Brier/RPS 报告
