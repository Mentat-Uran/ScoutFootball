# EVALUATION.md — 评分系统评估报告

## 数据切分

| 项目 | 值 |
|---|---|
| 切分方式 | 按赛季时间切分（train/test split） |
| 训练赛季 | 1617, 1718, 1819, 1920, 2021, 2122, 2223, 2324, 2425（9 赛季） |
| 测试赛季 | 2526（1 赛季） |
| 训练球员数 | 13,782 |
| 测试球员数 | 3,245 |
| 总球员数 | 30,483（含多赛季） |

## Baseline

| Baseline | 说明 |
|---|---|
| `baseline_0` | 联赛平均值（league average） |
| `baseline_1` | 简单 percentile 聚合 |
| `baseline_2` | Independent Poisson（比分预测） |

当前评分优化器的 baseline 是 `adamw_composite_objective` 的初始权重（pop_size=3, 40 步迭代前的默认参数）。

## 优化器配置

| 参数 | 值 |
|---|---|
| 优化器 | `adamw_composite_objective` |
| 设备 | MPS (Apple Silicon) / CUDA (RTX 5070 Ti) |
| 随机种子 | 42 |
| 参数数量 | 77 |
| 种群大小 | 3 |
| 迭代步数 | 40（本地）/ 更多（GPU） |
| 学习率 | 0.05 |
| 软排名温度 | 4.0 |
| 初始化缩放 | 0.35 |
| 早停耐心 | 15 |

## 组合目标权重

| 维度 | 权重 | 说明 |
|---|---|---|
| Spearman rank correlation | 0.50 | 排序一致性 |
| NDCG@20 | 0.20 | Top-20 排名质量 |
| 位置内排序一致性 | 0.15 | 同位置球员相对排序 |
| 极端样本惩罚 | 0.10 | 防止极端高估/低估 |
| 先验正则 | 0.05 | 参数平滑 |

## 核心指标

### 本地优化结果（MPS, pop=3, steps=40）

| 指标 | Baseline (train) | Optimized (train) | Baseline (test) | Optimized (test) |
|---|---|---|---|---|
| Spearman | 0.411 | 0.672 | N/A | N/A |
| Pearson | 0.397 | 0.659 | N/A | N/A |
| Rank loss | 0.589 | 0.328 | N/A | N/A |
| Z-MSE | 1.206 | 0.681 | N/A | N/A |
| Calibration MAE | 14.72 | 8.30 | N/A | N/A |
| Team coverage | 0.745 | 0.745 | N/A | N/A |
| Players | 13,782 | 13,782 | 3,245 | 3,245 |

**注意：** 本地测试集（2526）指标为 N/A，因为 Football-Data 2526 赛季球队名 alias 未完全匹配，导致 team_coverage=0。GPU 服务器已修补 alias 并获得有效测试集指标。

### GPU 服务器优化结果（RTX 5070 Ti, 2026-06-05）

| 指标 | 值 |
|---|---|
| Holdout Spearman | 0.7952 |
| Holdout Pearson | 0.6251 |
| Overfit gap | 0.0537 |
| 联赛分布 | EPL 11, Bundesliga 8, La Liga 5（均衡） |
| 位置分布 | CM 28, ST 2（需改善） |

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

## 位置内指标

当前已建立 GK/CB/FB/DM/CM/AM/W/ST 各位置的核心维度：

| 位置 | 核心维度 |
|---|---|
| GK | 扑救、出击、传球、稳定性 |
| CB | 防守、空中对抗、传球、位置感 |
| FB | 防守、助攻、跑动、传中 |
| DM | 防守、拦截、传球、覆盖 |
| CM | 传球、控球、防守、推进 |
| AM | 创造力、射门、传球、推进 |
| W | 速度、盘带、传中、射门 |
| ST | 射门、xG、空中对抗、跑动 |

## 已知偏差

1. **出勤偏差：** CM/GK 倾向高估（availability cap 已降到 0.18-0.20）
2. **联赛强度偏差：** 弱联赛顶端样本被压低，但仍需真实身价校准
3. **位置偏差：** CM 质量权重过高（0.54），ST 攻击权重过低（0.086）—— 需位置多样性约束
4. **数据缺失偏差：** 防守/控球/xT/VAEP/门将高阶字段缺失时用 missing flag + 中性 fallback
5. **Finishing 信号：** `goals - xG` 使用经验贝叶斯收缩（K=50），小样本不过度放大

## 误差案例

以下球队在 2526 holdout 中存在显著误差（需 GPU 重跑后复盘）：

| 球队 | 问题 |
|---|---|
| Everton | 出勤捷径导致高估 |
| Stuttgart | 弱联赛顶端样本 |
| Hoffenheim | 弱联赛顶端样本 |
| Rennes | 弱联赛顶端样本 |
| Napoli | 联赛强度偏差 |
| Real Madrid | 明星球员出勤偏差 |
| Arsenal | 球队聚合被高分钟球员拉拽 |
| PSG | 弱联赛顶端样本 |

## Coverage 置信度规则

| 级别 | 条件 | 允许结论 |
|---|---|---|
| HIGH | coverage ≥ 0.90 | 强排序结论 |
| MEDIUM | 0.70 ≤ coverage < 0.90 | 诊断性结论 |
| LOW | coverage < 0.90 | 禁止强排序，仅低置信度诊断 |

## 模型运行登记

本地运行存储在 `data/models/runs/<timestamp>/`，每个运行包含：
- `meta.json`：参数、种子、输入 hash、指标、位置内指标、误差案例摘要
- `optimized_params.npy`：优化后的 77 维参数向量

当前本地有 12 个运行记录（均为小规模本地测试，metrics 为 NaN）。

## 待完成

- [ ] GPU 服务器重跑完整优化（需 Windows RTX 5070 Ti）
- [ ] 复盘误差案例（Everton/Stuttgart/Rennes/Napoli/Real Madrid/Arsenal/PSG）
- [ ] 补充位置内指标的数值报告
- [ ] 补充跨位置总榜指标
- [ ] 补充 value_fairness OOF 残差分析
- [ ] 补充比分预测 log loss/Brier/RPS 报告
