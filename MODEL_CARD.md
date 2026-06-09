# ScoutFootball 球员评分模型卡

## 模型概述

ScoutFootball 球员评分模型输出位置感知的球员赛季综合评分，覆盖 Big 5 联赛（英超、西甲、德甲、意甲、法甲）2016/17–2025/26 赛季。模型将球员能力拆解为出勤可靠性、进攻贡献、防守贡献、控球推进、效率质量等维度，按位置组分配不同权重，经联赛强度和球队环境修正后输出最终评分。

**当前版本：v1.3.1-dev（联赛校准目标代码已更新，完整 GPU 重跑待执行；不可用于正式球探决策）**

## 数据源

| 数据源 | 覆盖范围 | 当前行数 | 评分用途 | 合规边界 |
|---|---|---|---|---|
| FBref 标准表 | 5 赛季 Big 5，standard/shooting/misc | 14,356 行/表 | 出勤、基础进攻、纪律 | 低频缓存，不绕反爬 |
| Football-Data | 4 赛季（2223–2526），5 个联赛 | 7,081 行 | 球队比赛结果、积分 | 公开数据 |
| Understat | 10 赛季，6 个联赛 | 31,902 球员赛季行 | xG/xA 补充 | 缓存+限速 |
| StatsBomb Open Data | 126 场比赛 | 11,871 事件 | 事件层指标 | 公开展示须注明来源 |

## 标签定义

模型训练目标为**球队赛季积分的排序与校准辅助监督**：

- 排序目标：Spearman/Pearson soft rank + soft NDCG@20。
- 球员解释目标：位置内核心指标一致性 + v3 prior 正则 + 球员评分离群 guardrail。
- 积分校准目标：训练集拟合的单调 affine 校准层，把 raw team strength 映射为 season points，并优化积分回归、1D 分布匹配、争冠/降级尾部球队误差和联赛平均残差。

**标签局限**：无球员级真实标签，球队积分 ≠ 球员影响力，强队系统性低估，降级队系统性高估。

**校准边界**：积分校准层只能在训练赛季拟合，holdout/test 必须复用训练集 `slope/intercept` 和训练集联赛 residual offset；不能用测试集实际积分重新拟合。

## 当前指标

以下指标来自 v1.3 GPU 重跑结果（2026-06-09 23:05，本地 `optimized_params_meta.json`）。v1.3.1-dev 新增的 league-bias loss 尚未完整重跑。

### Holdout（2526 赛季）

| 指标 | Baseline | Optimized | 提升 |
|---|---|---|---|
| Spearman | 0.621 | **0.737** | +0.116 |
| Pearson | 0.618 | **0.742** | +0.124 |
| Raw spread ratio | 0.265 | **0.336** | +0.071 |
| Global points spread ratio | 0.875 | **0.985** | +0.110 |
| Points MAE | 11.84 | **11.55** | -0.29 |
| Coverage | 0.990 | 0.990 | — |

只读验证：在不重新训练参数的前提下，使用 v1.3.1-dev 的 train-fitted league residual offset，当前参数的 holdout points MAE 从 11.55 降到 9.44；该结果需要完整 GPU 重跑后再写成正式指标。

### 3-Fold CV 平均

| 指标 | Baseline | Optimized | 提升 |
|---|---|---|---|
| Test Spearman | 0.540 | **0.694** | +0.154 |
| Test Pearson | 0.530 | **0.698** | +0.168 |

### 参数稳定性（3 seeds）

Test Spearman: mean=0.716, std=0.001

### 特征重要性

| 特征 | Spearman 下降 |
|---|---|
| assists_p90 | 0.109 |
| minutes | 0.073 |
| npg_p90 | 0.059 |

## 已知偏差

1. **联赛截距偏差**：v1.3 全局积分校准后，Serie A (-16.6)、Ligue 1 (-11.3)、La Liga (-11.2) 整体低估，Premier League (+5.8) 整体高估。
2. **强队仍低估**：Barcelona (-25.1), Real Madrid (-27.6), Inter (-18.5)。全局 spread 已修复，但联赛和顶端截距仍不足。
3. **降级队改善但未消失**：Burnley 从 baseline +31.5 改到 +18.9，Wolves 从 +25.8 改到 +12.5。
4. **出勤偏差仍存在**：minutes 是第二重要置换特征（Spearman drop 0.073），matches drop 0.032。
5. **防守/控球维度缺失**：全量球员大量使用位置中位数 fallback。

## 适用边界

可以用于：球员赛季综合评分排序草稿、同联赛同位置粗略比较、阵容深度诊断。

不可用于：单场评分、转会决策、青训评估、伤病预测、合同谈判、跨联赛精确排名、战术适配评估。

## 版本历史

### v1.3.1-dev（2026-06-09）

- 新增 train-fitted league residual offset：输出 `pred_points_global`、`pred_points_league_offset`、`pred_points_calibrated`。
- 新增 `league_bias_weight` 训练损失，惩罚训练集同联赛 calibrated points 平均残差。
- 新增 `--league-calibration-prior-n`、`--league-calibration-cap`、`--disable-league-calibration`。
- 只读验证：当前 v1.3 参数 points MAE 11.55 -> 9.44；完整重跑待执行。

### v1.3（2026-06-09）

- 新增 train-fitted team points calibration：raw team strength 与 season points 分离。
- 复合目标新增 points regression、distribution matching、tail calibration 三类积分校准损失。
- NDCG@20 改为 soft discount 可微目标，`--soft-rank-temperature` 贯穿 Spearman/NDCG/位置一致性。
- AdamW 训练循环新增 warmup + cosine decay、梯度裁剪；默认学习率从 0.05 降至 0.035。
- 输出 `pred_points_calibrated`、points MAE/RMSE/bias、raw spread ratio 和 points spread ratio。
- 完整 GPU 重跑已完成；主要残留问题从“全局分布压缩”转为“联赛截距偏差”。

### v1.2（2026-06-09）

- 首次有效 2526 holdout：Spearman=0.740, Pearson=0.744
- 3-fold CV 平均 test Spearman=0.718
- 修复 alias 匹配（重音符号去除 + 8+4 个新 alias）
- 补充 Football-Data 2526 赛季数据（1,751 场比赛）
- 新增特征重要性分析（assists_p90 最重要）
- 新增参数稳定性报告（3 seeds, std=0.002）
- 新增联赛级指标（Serie A 0.918, Bundesliga 0.886）

### v1.1（2026-06-09）

- 3-fold CV 结果（Fold 1 Spearman=0.655, Fold 2=0.778, Fold 3 N/A）
- 误差案例分析（2425 赛季）
- 识别 alias 问题和 Football-Data 2526 缺失

### v1.0（2026-06-05）

- 初始模型卡
- PyTorch 位置-维度权重优化器
- Smoke test：Spearman 0.573
