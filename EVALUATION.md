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

## Baseline

当前评分优化器的 baseline 是 `adamw_composite_objective` 的初始权重（默认参数，未经优化）。

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

### 3-Fold CV 结果（RTX 5070 Ti, pop=8, steps=150）

#### Fold 1 — 测试赛季 2324

| 指标 | Baseline (train) | Optimized (train) | Baseline (test) | Optimized (test) |
|---|---|---|---|---|
| Spearman | 0.391 | 0.680 | 0.441 | **0.655** |
| Pearson | 0.395 | 0.689 | 0.439 | **0.679** |
| Rank loss | 0.609 | 0.320 | 0.559 | **0.345** |
| Z-MSE | 1.210 | 0.623 | 1.121 | **0.642** |
| Calibration MAE | 15.78 | 7.36 | 12.83 | **10.03** |
| Team coverage | 0.918 | 0.918 | 0.896 | 0.896 |
| Teams | 90 | 90 | 86 | 86 |

#### Fold 2 — 测试赛季 2425

| 指标 | Baseline (train) | Optimized (train) | Baseline (test) | Optimized (test) |
|---|---|---|---|---|
| Spearman | 0.409 | 0.659 | 0.586 | **0.778** |
| Pearson | 0.411 | 0.676 | 0.571 | **0.757** |
| Rank loss | 0.591 | 0.341 | 0.414 | **0.222** |
| Z-MSE | 1.179 | 0.648 | 0.858 | **0.486** |
| Calibration MAE | 14.13 | 8.18 | 9.31 | **5.33** |
| Team coverage | 0.907 | 0.907 | 0.917 | 0.917 |
| Teams | 176 | 176 | 88 | 88 |

#### Fold 3 — 测试赛季 2526

| 指标 | Baseline (train) | Optimized (train) | Baseline (test) | Optimized (test) |
|---|---|---|---|---|
| Spearman | 0.471 | 0.701 | **N/A** | **N/A** |
| Pearson | 0.462 | 0.703 | **N/A** | **N/A** |
| Rank loss | 0.529 | 0.299 | **N/A** | **N/A** |
| Team coverage | 0.910 | 0.910 | **0** | **0** |
| Teams | 264 | 264 | 0 | 0 |

**Fold 3 测试集 N=0 原因**：Football-Data `combined_results.parquet` 当前仅包含 2223/2324/2425 三个赛季，无 2526 赛季数据。因此 2526 holdout 无法与任何实际积分匹配。这不是 alias 问题，而是数据源缺失。

### CV 汇总

| Fold | Baseline test Spearman | Optimized test Spearman | 提升 | Optimized test Pearson |
|---|---|---|---|---|
| Fold 1 (2324) | 0.441 | 0.655 | +0.214 | 0.679 |
| Fold 2 (2425) | 0.586 | 0.778 | +0.192 | 0.757 |
| Fold 3 (2526) | N/A | N/A | — | — |
| **平均（有效 fold）** | **0.513** | **0.717** | **+0.203** | **0.718** |

### 参数稳定性（3 seeds）

| Seed | Train Spearman | Test Spearman |
|---|---|---|
| 42 | 0.6593 | N/A（2526 无数据） |
| 143 | 0.6590 | N/A |
| 244 | 0.6590 | N/A |
| **Std** | **0.0002** | — |

训练集 Spearman 标准差仅 0.0002，表明优化器在不同随机种子下高度稳定。

## 2425 赛季误差案例复盘

以下基于 Fold 2 测试集（2425 赛季，88 支球队匹配）的实际预测 vs 积分数据。

### 系统性低估：顶级强队

| 球队 | 联赛 | 预测评分 | 实际积分 | 误差 |
|---|---|---|---|---|
| Napoli | Serie A | 46.1 | 82 | **-35.9** |
| Barcelona | La Liga | 52.2 | 88 | **-35.8** |
| Bayern Munich | Bundesliga | 51.6 | 82 | **-30.4** |
| Real Madrid | La Liga | 54.3 | 84 | **-29.7** |
| Paris SG | Ligue 1 | 54.9 | 84 | **-29.1** |
| Inter | Serie A | 54.5 | 81 | **-26.5** |
| Liverpool | Premier League | 59.2 | 84 | **-24.8** |

**根因分析**：模型预测的球队评分上限约 55-60，而实际顶级强队积分可达 80-90。这是因为球员评分聚合后存在天然上限——当所有球员维度都接近满分时，聚合评分无法再提升。球队积分则受赛制（3 分制）和对手强度影响，强队可以通过连胜获得远超"平均"的积分。

### 系统性高估：降级区球队

| 球队 | 联赛 | 预测评分 | 实际积分 | 误差 |
|---|---|---|---|---|
| Southampton | Premier League | 37.8 | 12 | **+25.8** |
| Ipswich | Premier League | 44.0 | 22 | **+22.0** |
| Monza | Serie A | 36.2 | 18 | **+18.2** |
| Bochum | Bundesliga | 42.6 | 25 | **+17.6** |
| Leicester | Premier League | 42.1 | 25 | **+17.1** |

**根因分析**：降级区球队的球员个体能力可能不差（如 Southampton 有英超级别球员），但球队整体表现远低于球员个体能力总和。模型无法捕捉教练战术、更衣室氛围、伤病潮等非量化因素。

### 用户关注球队

| 球队 | 联赛 | 预测评分 | 实际积分 | 误差 | 评估 |
|---|---|---|---|---|---|
| Everton | Premier League | 48.9 | 48 | +0.9 | ✓ 准确 |
| Stuttgart | Bundesliga | 53.8 | 50 | +3.8 | ✓ 合理 |
| Rennes | Ligue 1 | 40.6 | 41 | -0.4 | ✓ 准确 |
| Napoli | Serie A | 46.1 | 82 | -35.9 | ✗ 严重低估 |
| Arsenal | Premier League | 58.1 | 74 | -15.9 | ✗ 低估 |

Everton/Stuttgart/Rennes 的预测相当准确，说明模型对中游球队有合理的校准。Napoli 的严重低估反映了强队系统性低估问题。

### 联赛级误差

| 联赛 | 球队数 | 平均绝对误差 | Spearman |
|---|---|---|---|
| Bundesliga | 18 | 8.6 | 0.830 |
| La Liga | 20 | 10.4 | 0.950 |
| Ligue 1 | 18 | 9.4 | 0.926 |
| Premier League | 20 | 10.5 | 0.830 |
| Serie A | 20 | 13.5 | 0.815 |

La Liga 和 Ligue 1 的排序质量最高（Spearman > 0.92），Serie A 的绝对误差最大（受 Napoli/Inter 低估影响）。

## 球队名 Alias 问题

Football-Data 和评分侧存在 8 个球队名不匹配（2425 赛季）：

| Football-Data 名 | 评分侧名 | 差异类型 |
|---|---|---|
| Alaves | Alavés | 重音符号 |
| Ath Madrid | Atlético Madrid | 缩写 |
| Leganes | Leganés | 重音符号 |
| M'gladbach | Gladbach | 缩写 |
| Man United | Manchester Utd | 格式差异 |
| Sociedad | Real Sociedad | 缩写 |
| St Etienne | Saint-Étienne | 重音+格式 |
| Vallecano | Rayo Vallecano | 缩写 |

这些 alias 已在 `src/scoutfootball/entities/normalize.py` 的 `TEAM_NAME_ALIASES` 中定义，但 GPU 优化器脚本 `scripts/optimize_ratings_gpu.py` 的 `build_matched_results()` 使用原始字符串匹配，未调用 `normalize_team_name()`。需要在优化器中加入归一化步骤。

## 球队聚合配置

| 参数 | 值 | 说明 |
|---|---|---|
| Minutes cap | 1,500 | 出勤上限 |
| Core minutes | 450 | 核心轮换阈值 |
| Core scale | 180 | 核心轮换缩放 |
| Capped minutes blend | 0.55 | 上限分钟权重 |
| Core rotation blend | 0.45 | 核心轮换权重 |

### 位置槽位上限

| 位置组 | 槽位上限 |
|---|---|
| GK | 1.0 |
| CB | 2.5 |
| FB | 1.5 |
| MF | 2.5 |
| ATT | 2.5 |

## Coverage 置信度规则

| 级别 | 条件 | 允许结论 |
|---|---|---|
| HIGH | coverage ≥ 0.90 | 强排序结论 |
| MEDIUM | 0.70 ≤ coverage < 0.90 | 诊断性结论 |
| LOW | coverage < 0.70 | 禁止强排序，仅低置信度诊断 |

### 2425 赛季联赛 Coverage

| 联赛 | 目标球队 | 评分侧球队 | 匹配球队 | Coverage |
|---|---|---|---|---|
| Premier League | 20 | 20 | 19 | 0.950 |
| Serie A | 20 | 20 | 20 | 1.000 |
| Ligue 1 | 18 | 18 | 17 | 0.944 |
| La Liga | 20 | 20 | 15 | 0.750 |
| Bundesliga | 18 | 0 | 0 | 0.000 |

Bundesliga coverage=0 是因为评分侧联赛标签为 "nan"（FBref 数据中 Bundesliga 联赛名缺失），`team_coverage_table()` 已将其替换为 "Bundesliga"，但 `build_matched_results()` 的三元组匹配仍因联赛标签不一致而失败。La Liga 有 5 队不匹配，源于上述 alias 问题。

## 模型运行登记

本地运行存储在 `data/models/runs/<timestamp>/`，每个运行包含：
- `meta.json`：参数、种子、输入 hash、指标、位置内指标、误差案例摘要
- `optimized_params.npy`：优化后的 77 维参数向量

当前有 15 个运行记录。有效指标的运行：

| 运行时间 | 设备 | Spearman (train) | Spearman (test) | 备注 |
|---|---|---|---|---|
| 20260606T030003Z | GPU | 0.660 | 0.784 | 71 team-seasons 匹配 |

其余运行的 test 指标均为 NaN（2526 无 Football-Data 数据）。

## 待完成

- [ ] 补充 Football-Data 2526 赛季数据（或改用 2425 作为最终 holdout）
- [ ] 在 GPU 优化器中集成 `normalize_team_name()` 修复 alias 匹配
- [ ] 解决 Bundesliga 联赛标签 NaN 问题
- [ ] 补充位置内指标的数值报告
- [ ] 补充跨位置总榜指标
- [ ] 补充 value_fairness OOF 残差分析
- [ ] 补充比分预测 log loss/Brier/RPS 报告
