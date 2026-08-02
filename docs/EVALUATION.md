# EVALUATION.md — 评分系统评估报告

> 本文历史表格仍不是独立球员能力真值。当前 active 神经候选和研究门禁的最新事实见下方 2026-08-02 记录；`research_health=not_ready` 时不得把评分写成已验证的球员能力。

最新计算口径：历史 v1.3 GPU 重跑仍保留供比较；2026-08-02 已完成 CUDA MLP/Set Transformer 候选比较。MLP active run 为 `20260802T-gpu-mlp-activated-candidate`，holdout Spearman=0.6820、MAE=11.0139、RMSE=14.2681、R²=0.2581，使用 RTX 5070 Ti。该评估的目标是球队赛季积分代理，不是独立球员能力标签；Set Transformer 同切分未优于 MLP。当前标签表有 17 行 post-season 奖项 benchmark，时间可用于因果训练的独立行数仍为 0。

Docker 本地服务已重建并验证：容器 `healthy`，首页、`/health`、`/ratings/meta`、`/reports/model-training`、`/ratings` 和缓存后的 `/health/research` 均返回 200。研究健康报告增加 300 秒进程缓存、并发刷新锁和启动预热；需重算时使用 `/health/research?force_refresh=true`。

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
| 学习率 | 0.035 |
| 软排名温度 | 4.0 |
| 初始化缩放 | 0.35 |
| 早停耐心 | 25 |

## 组合目标权重

| 维度 | 权重 | 说明 |
|---|---|---|
| Spearman/Pearson soft rank | 0.42 | 排序一致性 |
| Soft NDCG@20 | 0.16 | Top-20 排名质量 |
| 位置内排序一致性 | 0.12 | 同位置球员相对排序 |
| 积分回归校准 | 0.16 | calibrated points 距离 |
| 积分分布匹配 | 0.10 | 预测/真实积分分布形状 |
| 争冠/降级尾部校准 | 0.14 | 顶端和底端球队误差 |
| 联赛平均残差惩罚 | 0.08 | v1.3.1-dev 新增，完整重跑待执行 |
| 球员评分离群 guardrail | 0.05 | 防止球员评分异常离群 |
| 球员真值标签锚定 | 0.08（启用时） | v1.3.2-dev 新增；当前标签为空，训练时跳过 |
| 先验正则 | 0.04 | 参数平滑 |

## 核心指标

### Holdout 结果（2526 赛季）

| 指标 | Baseline | Optimized | 提升 |
|---|---|---|---|
| Spearman | 0.621 | **0.737** | +0.116 |
| Pearson | 0.618 | **0.742** | +0.124 |
| Rank loss | 0.379 | **0.263** | -0.116 |
| Z-MSE | 0.764 | **0.516** | -0.248 |
| Calibration MAE | 10.39 | **7.88** | -2.52 |
| Raw spread ratio | 0.265 | **0.336** | +0.071 |
| Global points spread ratio | 0.875 | **0.985** | +0.110 |
| Points MAE | 11.84 | **11.55** | -0.29 |
| Team coverage | 0.990 | 0.990 | — |
| Teams matched | 95/96 | 95/96 | — |

v1.3.1-dev 只读复算：使用训练集联赛 residual offset 后，当前参数 points MAE=9.44，points RMSE=11.54。该结果尚未经过完整重新训练。

### 3-Fold CV 结果

| Fold | 测试赛季 | Baseline test Spearman | Optimized test Spearman | 提升 | Optimized test Pearson |
|---|---|---|---|---|---|
| Fold 1 | 2324 | 0.442 | 0.629 | +0.187 | 0.659 |
| Fold 2 | 2425 | 0.595 | **0.767** | +0.173 | 0.748 |
| Fold 3 | 2526 | 0.583 | 0.686 | +0.103 | 0.687 |
| **平均** | — | **0.540** | **0.694** | **+0.154** | **0.698** |

### 训练集指标

| 指标 | Fold 1 | Fold 2 | Fold 3 |
|---|---|---|---|
| Baseline train Spearman | 0.376 | 0.404 | 0.469 |
| Optimized train Spearman | 0.628 | 0.629 | 0.659 |
| Optimized train Pearson | 0.641 | 0.646 | 0.666 |

### 参数稳定性（3 seeds）

| Seed | Train Spearman | Test Spearman |
|---|---|---|
| 42 | 0.618 | 0.716 |
| 143 | 0.633 | 0.715 |
| 244 | 0.618 | 0.716 |
| **Mean** | **0.623** | **0.716** |
| **Std** | **0.007** | **0.001** |

## 特征重要性

| 特征 | Spearman 下降 | 说明 |
|---|---|---|
| assists_p90 | 0.109 | 助攻 p90（最重要） |
| minutes | 0.073 | 总分钟数，出勤捷径仍存在 |
| npg_p90 | 0.059 | 非点球进球 p90 |
| g_a_volume | 0.056 | 进球+助攻总量 |
| matches | 0.032 | 比赛场次 |
| starts | 0.020 | 首发场次 |
| npg_trend | 0.002 | 进球趋势 |

## 2526 赛季联赛级指标

| 联赛 | 球队数 | Spearman | Pearson | Coverage |
|---|---|---|---|---|
| Serie A | 20 | 0.890 | 0.928 | 1.00 |
| Ligue 1 | 18 | 0.863 | 0.890 | 1.00 |
| Bundesliga | 17 | 0.850 | 0.879 | 0.944 |
| Premier League | 20 | 0.786 | 0.799 | 1.00 |
| La Liga | 20 | 0.692 | 0.829 | 1.00 |

联赛 points bias（global calibration）：Serie A -16.6、Ligue 1 -11.3、La Liga -11.2、Premier League +5.8、Bundesliga +1.8。v1.3.1-dev 的训练集联赛 offset 在只读复算中可降低这些整体偏差，但仍需完整重跑。

## 2526 赛季误差案例

### 系统性低估：顶级强队

| 球队 | 联赛 | 预测 | 实际 | 误差 |
|---|---|---|---|---|
| Real Madrid | La Liga | 58.4 | 86 | -27.6 |
| Barcelona | La Liga | 68.9 | 94 | -25.1 |
| Napoli | Serie A | 52.2 | 76 | -23.8 |
| Roma | Serie A | 51.2 | 73 | -21.8 |
| Inter | Serie A | 68.5 | 87 | -18.5 |
| Arsenal | Premier League | 73.7 | 85 | -11.3 |
| Bayern Munich | Bundesliga | 78.5 | 89 | -10.5 |

### 系统性高估：降级区球队

| 球队 | 联赛 | 预测 | 实际 | 误差 |
|---|---|---|---|---|
| Burnley | Premier League | 40.9 | 22 | +18.9 |
| Wolves | Premier League | 32.5 | 20 | +12.5 |
| Heidenheim | Bundesliga | 39.3 | 26 | +13.3 |
| Wolfsburg | Bundesliga | 38.8 | 29 | +9.8 |
| Metz | Ligue 1 | 18.0 | 17 | +1.0 |

### 用户关注球队

| 球队 | 联赛 | 预测 | 实际 | 误差 |
|---|---|---|---|---|
| Everton | Premier League | 62.4 | 49 | +13.4 |
| Stuttgart | Bundesliga | 57.8 | 62 | -4.2 |
| Rennes | Ligue 1 | 48.5 | 59 | -10.5 |
| Napoli | Serie A | 52.2 | 76 | -23.8 |
| Real Madrid | La Liga | 58.4 | 86 | -27.6 |
| Arsenal | Premier League | 73.7 | 85 | -11.3 |

## 球队覆盖率（2526）

| 联赛 | 目标球队 | 评分侧球队 | 匹配球队 | Coverage |
|---|---|---|---|---|
| Premier League | 20 | 34 | 20 | 1.00 |
| Ligue 1 | 18 | 27 | 18 | 1.00 |
| La Liga | 20 | 31 | 20 | 1.00 |
| Serie A | 20 | 40 | 20 | 1.00 |
| Bundesliga | 18 | 26 | 17 | 0.944 |
| RFPL | 0 | 33 | 0 | N/A |

Bundesliga 仍有 1 队未匹配；RFPL（俄超）33 队在评分侧但无 Football-Data 目标，不能参与球队积分监督。

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

## 神经网络候选状态

`scoutfootball train-rating-nn` 已实现监督式 sklearn MLP 候选模型，训练输入为 `rating_feature_matrix.parquet` 和 `player_truth_labels.parquet`，并与 `player_ratings_optimized` baseline 同切分对比。2026-06-10 本地 smoke run 结果为 `skipped: 0 resolved labels, need at least 10`；因此当前没有 NN holdout 指标，也不能把 NN 写成默认评分能力。

## 待完成

- [ ] 重跑 GPU 优化器（alias 修复后）验证 Bundesliga coverage 提升
- [ ] 有足够 `player_truth_labels.parquet` 后，重跑 v1.3.2-dev truth-anchor optimizer 并报告球员级 holdout 指标
- [ ] 有足够 `player_truth_labels.parquet` 后，训练 `player_rating_nn`，并与当前优化器、v3 默认权重和简单 percentile baseline 同切分对比
- [ ] 补充位置内指标的数值报告
- [ ] 补充跨位置总榜指标
- [ ] 补充 value_fairness OOF 残差分析
- [ ] 补充比分预测 log loss/Brier/RPS 报告
