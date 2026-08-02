# ScoutFootball 球员高阶评分算法说明

## 目标

ScoutFootball 的球员评分不应只衡量热度或直接进攻产出，而应输出一个可解释、可回溯、位置感知的球探综合评分。新版算法把球员能力拆成出勤可靠性、进攻贡献、防守贡献、控球推进、效率质量和门将专属表现，并用同位置百分位减少固定阈值封顶带来的失真。

当前仓库里的数据覆盖不均衡，因此算法分两层落地：

1. 当前可运行层：使用 FBref 标准表、Football-Data 比赛结果、StatsBomb Open Data 样本和已生成的 Parquet 特征。
2. 增强层：接入 Understat、更多 FBref 标准/补充表或后续授权数据后，启用 xG、xA、npxG、xGChain、xGBuildup、传球、防守和门将高阶字段。

文档中的“目标字段”不得被理解为当前已经全量入库。实现时必须按字段存在性启用指标，缺失字段保留 `has_source_metric=false`，不能伪造高阶数据。

## 当前数据盘点

已确认的本地数据：

| 数据层 | 文件或表 | 覆盖 | 可用于评分的字段 |
|---|---:|---:|---|
| DuckDB | `fact_match` | 5,330 场比赛 | 比分、射门、射正、犯规、角球、黄红牌、赔率、联赛、赛季 |
| DuckDB | `fact_event_statsbomb` | 3 场样本，11,871 事件，69 名有事件球员 | 传球、带球、射门、xG、压迫、夺回、对抗、封堵、拦截、解围、门将事件、坐标 |
| Parquet | `data/raw/fbref/player_stats_big5_3seasons.parquet` | 8,595 行，约 4,321 名球员 | 出场、首发、分钟、进球、助攻、点球、黄牌、红牌、每 90 分钟 G/A |
| Parquet | `data/gold/feature_store/player_value_metrics.parquet` | 10 名样本球员 | xG、xT、传球、传球成功率、防守动作、对抗、推进带球 |
| Parquet | `data/gold/feature_store/team_features.parquet` | 119 支球队 | 进失球、射门、射正、胜平负、射正率 |

结论：当前全量球员层只能稳定计算出勤和基础进攻；严肃的防守、控球、xT、xG 和门将评分只能先在 StatsBomb 样本或后续新增数据上启用。全量评分必须降级为“标准表版本”，并明确低置信度。

## 总公式

新版最终评分：

```text
最终评分 = 位置基础分 × 样本可靠性系数 × 联赛强度系数 × 球队环境修正
```

其中：

```text
位置基础分 =
  出勤角色分 × W_availability
+ 进攻贡献分 × W_attack
+ 防守贡献分 × W_defense
+ 控球推进分 × W_possession
+ 效率质量分 × W_quality
```

门将不套用普通球员公式：

```text
门将基础分 =
  出勤角色分 × W_availability
+ 扑救表现分 × W_shot_stopping
+ 禁区控制分 × W_box_control
+ 出球组织分 × W_distribution
+ 稳定纪律分 × W_stability
```

所有分项统一映射到 0-100。优先使用“同赛季、同联赛、同细分位置”的百分位；样本太小时回退到“同赛季、同细分位置”；仍不足时回退到位置组或全库分布。

## 球队积分校准与优化目标

球员评分和球队赛季积分不是同一个量纲。球员评分聚合后的 `team_strength` 表示阵容强度，不再直接当作赛季积分解释；积分预测必须经过只在训练赛季拟合的单调校准层：

```text
pred_points = intercept_train + slope_train × team_strength
slope_train = std(actual_points_train) / std(team_strength_train)
intercept_train = mean(actual_points_train) - slope_train × mean(team_strength_train)
```

v1.3.1-dev 在全局校准后加入训练集联赛残差 offset：

```text
global_pred_points = intercept_train + slope_train × team_strength
league_residual_mean[L] = mean(actual_points_train - global_pred_points | league=L)
league_offset[L] = clip(
  league_residual_mean[L] × n_league_train / (n_league_train + prior_n),
  -offset_cap,
  +offset_cap
)
pred_points_calibrated = global_pred_points + league_offset[league]
```

holdout/test 只能复用训练集的 `slope_train`、`intercept_train` 和 `league_offset`，不能用测试集积分重新拟合。输出报告必须同时保留：

```text
raw_team_strength
pred_points_global
pred_points_league_offset
pred_points_calibrated
raw_spread_ratio = std(raw_team_strength) / std(actual_points)
points_spread_ratio = std(pred_points_calibrated) / std(actual_points)
points_MAE / points_RMSE / points_bias
```

v1.3-dev 复合目标：

```text
loss =
  0.42 × soft_rank_loss(Spearman/Pearson)
+ 0.16 × soft_NDCG@20_loss
+ 0.12 × position_consistency_loss
+ 0.16 × calibrated_points_regression_loss
+ 0.10 × points_distribution_matching_loss
+ 0.14 × tail_calibration_loss(title/relegation teams)
+ 0.08 × league_bias_loss
+ 0.05 × player_score_extreme_guardrail
+ w_truth × player_truth_anchor_loss
+ 0.04 × prior_regularization
```

其中 `player_score_extreme_guardrail` 只约束球员评分离群，不能用来解决强队/弱队积分尾部误差；尾部误差由 calibrated points regression、distribution matching 和 tail calibration 负责；联赛整体高估/低估由 train-fitted league offset 和 `league_bias_loss` 负责。

v1.3.2-dev 新增可选球员真值标签锚定：

```text
player_truth_anchor_loss =
  0.55 × z_mse(player_rating, truth_label_value)
+ 0.45 × (1 - corr_soft_rank(player_rating, truth_label_value))
```

该项只在 `player_truth_labels.parquet` 能通过 `rating_feature_matrix.parquet` 解析到足够 `player_id -> player_name/season` 匹配时启用；默认阈值是 `--min-truth-labels 50`。当前本地真值标签表为空，因此该项在实际训练中自动跳过。它的目的不是替代球队积分监督，而是在有人工/身价/奖项标签后，把优化器从纯球队层代理信号拉回球员层真实影响力。

## 位置细分

旧版只分 FW、MF、DF、GK，职责过粗。新版至少使用以下细分位置：

| 子位置 | 来源位置规则 | 说明 |
|---|---|---|
| ST | `FW` 且更偏中路，或无更细信息时的纯 FW | 中锋 |
| W | `FW,MF`、`MF,FW`，或事件位置显示边路前场 | 边锋/边前卫 |
| AM | `MF,FW` 且进攻三区触球和关键传球占比高 | 前腰 |
| CM | `MF` 默认 | 中前卫/组织中场 |
| DM | `MF,DF` 或防守三区接球、拦截、夺回占比高 | 后腰 |
| FB | `DF,MF`、边路防守位置 | 边后卫/翼卫 |
| CB | `DF` 默认 | 中卫 |
| GK | `GK` | 门将 |

当前 FBref 标准表只有粗位置字符串，不能稳定区分 ST/W/AM/CM/DM/FB/CB。没有事件或阵型位置时，先用确定性降级规则：

```text
GK -> GK
DF,MF or MF,DF -> FB/DM 待定，默认 FB
FW,MF or MF,FW -> W/AM 待定，默认 W
FW -> ST
DF -> CB
MF -> CM
```

若 StatsBomb 事件或 lineups 中有更细位置，则优先使用事件位置，并记录 `position_source`。

## 分项权重

| 维度 | ST | W | AM | CM | DM | FB | CB |
|---|---:|---:|---:|---:|---:|---:|---:|
| 出勤角色 | 15% | 12% | 12% | 14% | 14% | 15% | 16% |
| 进攻贡献 | 38% | 30% | 28% | 16% | 8% | 10% | 5% |
| 防守贡献 | 8% | 10% | 10% | 18% | 30% | 28% | 42% |
| 控球推进 | 14% | 25% | 28% | 32% | 28% | 27% | 20% |
| 效率质量 | 25% | 23% | 22% | 20% | 20% | 20% | 17% |

门将权重：

| 维度 | GK |
|---|---:|
| 出勤角色 | 20% |
| 扑救表现 | 35% |
| 禁区控制 | 15% |
| 出球组织 | 20% |
| 稳定纪律 | 10% |

这些权重是 MVP 初值，不是训练得到的最终参数。后续若有标签任务，应通过时间序列验证校准权重，而不是手工长期固定。

## 百分位评分

固定满分阈值容易把顶级球员全部压到 100。新版默认使用百分位评分：

```text
percentile_score(metric, group) = percentile_rank(metric within group) × 100
```

分组优先级：

```text
season + league + sub_position
season + sub_position
position_group
global
```

最低样本数建议：

```text
同联赛同位置样本 >= 60：使用该组
同赛季同位置样本 >= 120：使用该组
否则回退到位置组分布
```

对越低越好的指标使用反向百分位：

```text
inverse_percentile_score(metric) = 100 - percentile_score(metric)
```

对小样本比率指标使用贝叶斯/经验收缩：

```text
收缩后比率 = (success + prior_rate × k) / (attempts + k)
```

其中 `k` 由指标稳定性决定。传球成功率可取 100-200 次尝试；射门转化率、对抗成功率可取 30-80 次尝试。

## 每 90 分钟指标

所有每 90 分钟指标必须使用分钟数计算：

```text
stat_p90 = stat / max(minutes, 1) × 90
```

不能使用 `进球 / 出场场次 × 90`。只有在确知每场踢满 90 分钟时，按场次近似才成立；球员评分里不能默认满勤满时间。

当前 StatsBomb 样本脚本用 `unique_matches × 90` 近似分钟数，只适合作为样本演示。正式实现应从阵容、换人和出场时间表生成球员分钟数。

## 样本可靠性系数

旧版阶梯惩罚会让 19 场和 20 场、29 场和 30 场出现不合理跳变。新版改为连续函数：

```text
分钟可靠性 = 0.5 + 0.5 × min(minutes / 1800, 1)
首发可靠性 = 0.85 + 0.15 × min(starts / max(matches, 1) / 0.60, 1)
样本可靠性系数 = 分钟可靠性 × 首发可靠性
```

对于未提供 `starts` 的历史赛季代理（当前为 Understat），系统不把出场数冒充为首发数，也不把缺失解释为零首发。出勤分只在分钟、出场和角色稳定性之间重新归一化，首发可靠性保持中性值 1.0；这些数据可参与历史球队层验证，但不能作为首发可靠性证据。

含义：

| 分钟 | 分钟可靠性 |
|---:|---:|
| 0 | 0.50 |
| 450 | 0.625 |
| 900 | 0.75 |
| 1350 | 0.875 |
| 1800+ | 1.00 |

短时间高产球员仍可得高分项，但最终分会被样本可靠性压回合理区间。

## 出勤角色分

出勤不是单纯“踢得多就强”，而是可用性和角色稳定性的信号：

```text
出勤角色分 =
  minutes_share_score × 0.45
+ start_rate_score × 0.25
+ availability_score × 0.20
+ role_stability_score × 0.10
```

当前可用字段：

```text
minutes_share_score = min(minutes / team_max_minutes, 1) × 100
start_rate_score = starts / max(matches, 1) × 100
availability_score = min(matches / team_matches, 1) × 100
```

增强字段：

```text
role_stability_score = 100 - percentile_score(position_entropy)
```

如果没有球队赛季总场次，则默认 Big 5 联赛赛季为 38 场；杯赛或欧战不能套用 38 场。

## 进攻贡献分

进攻贡献衡量创造和终结机会的总量，不再与效率分重复。

优先字段：

| 指标 | ST | W | AM | CM | DM | FB | CB |
|---|---:|---:|---:|---:|---:|---:|---:|
| npxG_p90 | 高 | 高 | 中 | 低 | 低 | 低 | 低 |
| xA_p90 | 中 | 高 | 高 | 中 | 低 | 中 | 低 |
| shots_p90 | 高 | 中 | 中 | 低 | 低 | 低 | 低 |
| key_pass_p90 | 中 | 高 | 高 | 中 | 低 | 中 | 低 |
| box_touch_p90 | 高 | 高 | 中 | 低 | 低 | 中 | 中 |
| goals_non_penalty_p90 | 高 | 中 | 中 | 低 | 低 | 低 | 低 |
| assists_p90 | 中 | 中 | 高 | 中 | 低 | 中 | 低 |

当前 FBref 标准表只有进球、助攻、点球和 G/A，因此全量 fallback：

```text
进攻贡献分 =
  percentile_score(non_penalty_goals_p90) × role_goal_weight
+ percentile_score(assists_p90) × role_assist_weight
+ percentile_score(non_penalty_goals + assists per season) × role_volume_weight
```

fallback 权重：

| 子位置 | 非点球进球 p90 | 助攻 p90 | 赛季 G+A 总量 |
|---|---:|---:|---:|
| ST | 45% | 15% | 40% |
| W | 30% | 30% | 40% |
| AM | 20% | 40% | 40% |
| CM | 15% | 35% | 50% |
| DM | 10% | 25% | 65% |
| FB | 10% | 45% | 45% |
| CB | 20% | 20% | 60% |

有 Understat 或 StatsBomb shot 数据时，实际进球要降权，npxG 和 xA 升权，减少短期 finishing 运气影响。

## 防守贡献分

防守分必须来自防守行为，纪律只作为扣分项。旧版“纪律分混 50 分”不能衡量防守能力。

目标公式：

```text
防守贡献分 =
  防守动作量分 × W_actions
+ 对抗质量分 × W_duels
+ 夺回与压迫分 × W_recoveries
+ 防线保护分 × W_protection
- 纪律扣分
```

目标字段：

| 指标 | 说明 |
|---|---|
| tackles_p90 | 抢断或铲断 |
| interceptions_p90 | 拦截 |
| clearances_p90 | 解围 |
| blocks_p90 | 封堵 |
| pressures_p90 | 压迫 |
| ball_recoveries_p90 | 夺回球权 |
| duel_win_rate | 总对抗成功率 |
| aerial_win_rate | 空中对抗成功率 |
| dribbled_past_p90 | 被过次数，反向评分 |
| fouls_committed_p90 | 犯规率，反向评分 |
| cards_p90 | 黄红牌纪律扣分 |

位置权重：

| 子位置 | 动作量 | 对抗质量 | 夺回压迫 | 防线保护 | 纪律 |
|---|---:|---:|---:|---:|---:|
| ST | 20% | 20% | 45% | 5% | -10% |
| W | 20% | 15% | 50% | 5% | -10% |
| AM | 20% | 15% | 50% | 5% | -10% |
| CM | 25% | 20% | 35% | 10% | -10% |
| DM | 25% | 25% | 25% | 15% | -10% |
| FB | 30% | 25% | 20% | 15% | -10% |
| CB | 25% | 30% | 10% | 25% | -10% |

当前可落地的 StatsBomb 样本字段包括 `Duel`、`Pressure`、`Ball Recovery`、`Block`、`Interception`、`Clearance`、`Dribbled Past`、`Foul Committed` 和牌类字段。全量 FBref 标准表没有这些字段时，防守贡献分不得用黄红牌冒充，应设置为位置中位数 50，并记录：

```text
defense_source = "missing_standard_table"
defense_confidence = "low"
```

纪律扣分：

```text
纪律扣分 = min(15, yellow_p90 × 8 + red_p90 × 35 + fouls_committed_p90 × 1.5)
```

纪律只扣分，不作为正向防守能力来源。

## 控球推进分

控球分衡量球员在球权中的处理、推进和连接能力，不再使用 G90/A90 代理。

目标公式：

```text
控球推进分 =
  传球质量分 × W_passing
+ 推进价值分 × W_progression
+ 持球抗压分 × W_pressure
+ 球权安全分 × W_security
+ 参与度分 × W_involvement
```

目标字段：

| 指标 | 说明 |
|---|---|
| pass_completion_rate | 传球成功率，需按传球难度/区域解释 |
| passes_p90 | 传球参与度 |
| progressive_passes_p90 | 渐进传球 |
| forward_pass_rate | 向前传球比例 |
| key_passes_p90 | 关键传球 |
| xT_pass_p90 | 传球带来的 xT |
| carries_p90 | 带球次数 |
| progressive_carries_p90 | 渐进带球 |
| xT_carry_p90 | 带球带来的 xT |
| miscontrols_p90 | 停球失误，反向评分 |
| dispossessed_p90 | 被断球，反向评分 |
| under_pressure_success_rate | 受压下处理成功率 |
| final_third_touches_p90 | 进攻三区触球 |
| box_entries_p90 | 进入禁区的传球或带球 |

当前 StatsBomb 样本可计算传球完成率、前向传球比例、xT、推进带球、触球区域、误控和被断球。全量 FBref 标准表缺少控球字段时，控球推进分设为位置中位数 50，并记录低置信度；不能用进球助攻替代。

## 效率质量分

效率质量分衡量机会质量、终结质量和决策质量，不能重复计算 G+A。

目标公式：

```text
效率质量分 =
  机会质量分 × W_chance_quality
+ 终结质量分 × W_finishing
+ 创造质量分 × W_creation_quality
+ 决策质量分 × W_decision
```

优先字段：

| 指标 | 说明 |
|---|---|
| npxG_per_shot | 非点球射门质量 |
| goals_minus_npxG | 终结超额，需收缩 |
| xA_per_key_pass | 关键传球质量 |
| shot_conversion_rate | 射门转化率，需收缩 |
| xT_per_touch | 单次触球推进价值 |
| turnover_rate | 丢失球权率，反向评分 |
| progressive_action_success_rate | 推进动作成功率 |

没有 xG/xA 时的 fallback：

```text
效率质量分 =
  percentile_score(non_penalty_goals_p90) × 0.35
+ percentile_score(assists_p90) × 0.25
+ inverse_percentile_score(turnover_proxy) × 0.15
+ position_median × 0.25
```

当前全量 FBref 标准表没有 turnover proxy，因此 fallback 中后两项必须降级为位置中位数；这会降低 `quality_confidence`。

对 `goals_minus_npxG`、射门转化率、助攻转化率必须做样本收缩，不能让 200 分钟进 4 球的球员直接进入顶级效率。

## 门将评分

门将单独建模，不能套普通球员公式。

目标字段：

| 维度 | 指标 |
|---|---|
| 扑救表现 | save_pct、PSxG-GA、saves_p90、goals_prevented_p90 |
| 禁区控制 | crosses_claimed_rate、sweeper_actions_p90、high_claims_p90 |
| 出球组织 | pass_completion_rate、long_pass_completion_rate、launch_success_rate、xT_pass_p90 |
| 稳定性 | errors_to_shot、errors_to_goal、cards_p90、availability_volatility |

当前数据只有 StatsBomb 样本中的 `Goal Keeper` 事件和 FBref 标准表的 GK 粗位置，不足以严肃评估门将。当前全量门将评分只能输出出勤角色分和低置信度占位；门将高阶分项必须等门将专属数据补齐后启用。

## 联赛强度与球队环境

旧版只用 UEFA 国家系数，不足以表达联赛和球队环境。新版拆成两层：

```text
环境系数 = 联赛强度系数 × 球队环境修正
```

联赛强度系数优先使用 Club Elo 聚合：

```text
league_strength = median(team_elo in league-season)
league_strength_factor = clamp((league_strength / EPL_baseline_elo) ^ alpha, 0.88, 1.08)
```

没有 Club Elo 时才回退到 UEFA 国家系数：

```text
uefa_factor = ln(country_coefficient) / ln(england_coefficient)
```

球队环境修正用于减少强队体系红利和弱队核心低估：

```text
team_attack_context = percentile_score(team_goals_for_p90 or team_xG_for_p90)
team_defense_context = percentile_score(team_shots_against_p90 or team_xG_against_p90)
team_possession_context = percentile_score(team_possession or team_pass_volume)
```

进攻球员：

```text
球队环境修正 = 1 - beta_attack × (team_attack_context - 50) / 100
```

防守球员：

```text
球队环境修正 = 1 + beta_defense × (team_defense_pressure_context - 50) / 100
```

建议范围：

```text
0.94 <= 球队环境修正 <= 1.06
```

当前 `team_features.parquet` 有进球、失球、射门、射正和胜率，可先用这些字段做弱版本球队环境修正。没有 xG 和控球率时，不要声称使用了 xG/possession 环境校正。

## 当前实现建议

按现有数据，最务实的实现顺序：

1. 修正 per90 公式：所有每 90 分钟指标统一用 `minutes` 计算。
2. 把阶梯出场惩罚改为连续样本可靠性系数。
3. 把 FW/MF/DF/GK 映射升级为 ST/W/AM/CM/DM/FB/CB/GK，并记录映射来源和置信度。
4. 全量 FBref 评分改为同位置百分位，不再使用固定满分阈值。
5. 防守分和控球分在缺少真实字段时回退到 50，并显式标记低置信度，不再用黄红牌或 G/A 冒充。
6. StatsBomb 样本评分启用事件指标：xG、xT、传球、推进、压迫、夺回、对抗、封堵、拦截、解围、门将事件。
7. 接入 Understat 后，把进攻和效率质量从 G/A fallback 升级为 npxG、xA、npxG+xA、xGChain、xGBuildup。
8. 接入更多防守/传球表后，再对全量 4,321 名球员启用严肃高阶评分。

## 输出字段

评分结果至少应输出：

| 字段 | 说明 |
|---|---|
| `player_id` / `player_name` | 球员标识 |
| `team_id` / `team_name` | 球队标识 |
| `season` / `league` | 赛季和联赛 |
| `sub_position` | ST/W/AM/CM/DM/FB/CB/GK |
| `position_source` | 位置来源：fbref、statsbomb_lineup、event_inferred |
| `overall_score` | 最终评分 |
| `base_score` | 环境和可靠性修正前评分 |
| `availability_score` | 出勤角色分 |
| `attack_score` | 进攻贡献分 |
| `defense_score` | 防守贡献分 |
| `possession_score` | 控球推进分 |
| `quality_score` | 效率质量分 |
| `sample_reliability` | 样本可靠性系数 |
| `league_strength_factor` | 联赛强度系数 |
| `team_context_factor` | 球队环境修正 |
| `score_confidence` | high / medium / low |
| `missing_metric_flags` | 缺失关键字段列表 |

`overall_score` 不能单独展示为“球员水平真值”。界面和报告必须同时展示分项、置信度和缺失字段。

## 评分等级

评分等级只在 `score_confidence != low` 时使用：

| 评分范围 | 等级 | 说明 |
|---:|---|---|
| 90+ | 顶级 | 同位置同环境下极少数顶尖表现 |
| 80-89 | 优秀 | 明显高于同位置主力平均 |
| 70-79 | 良好 | 稳定正贡献球员 |
| 60-69 | 可用 | 合格轮换或局部强项明显 |
| 50-59 | 平均 | 同位置中位附近 |
| <50 | 低于平均 | 需要结合样本和角色复核 |

低置信度评分只能作为排序草稿，不能作为球探结论。

## 数据与合规边界

- StatsBomb Open Data 可作为事件流主源，但公开数据覆盖有限。
- Football-Data.co.uk 可用于球队和比赛环境，不提供球员细项。
- Understat 可作为 xG/xA 补充源，必须缓存、限速、校验字段。
- FBref 只作为低频标准表或补充源，不作为 advanced 主源。
- Transfermarkt 不允许自动抓取，只能做本地 CSV/Parquet 手动或授权导入。
- 不公开分发受限制的原始缓存。

## 比赛预测模型

### 独立泊松基线

最简比赛预测模型，假设主队和客队进球独立服从泊松分布：

```text
home_lambda = league_home_rate × home_attack_strength × away_defense_strength
away_lambda = league_away_rate × away_attack_strength × home_defense_strength

P(home=i, away=j) = Poisson(i, home_lambda) × Poisson(j, away_lambda)
```

强度参数通过贝叶斯收缩估计：

```text
team_strength = (team_goals + smoothing × league_rate) / (team_matches + smoothing)
```

### Dixon-Coles 模型

在独立泊松基础上，Dixon-Coles (1997) 引入 rho 参数修正低比分相关性：

```text
log(lambda_home) = log(mu) + alpha_home + beta_away + gamma
log(lambda_away) = log(mu) + alpha_away + beta_home
```

其中 `mu` 为联赛场均进球，`alpha` 为攻击参数，`beta` 为防守参数，`gamma` 为主场优势。

低比分修正函数 tau：

```text
tau(0,0) = 1 - lambda_home × lambda_away × rho
tau(1,0) = 1 + lambda_home × rho
tau(0,1) = 1 + lambda_away × rho
tau(1,1) = 1 - rho
tau(x,y) = 1  (其他比分)
```

rho 通常为负值（约 -0.13），表示低比分正相关。

时间衰减权重（可选）：

```text
weight(match) = 0.5 ^ (days_since_most_recent / half_life_days)
```

通过 L-BFGS-B 最大似然估计参数，约束 rho ∈ [-1, 0]。

### 校准评估

比赛预测模型使用以下校准指标：

| 指标 | 说明 |
|---|---|
| log_loss_exact | 精确比分对数损失 |
| brier_1x2 | 胜平负 Brier 分数 |
| rps_1x2 | 排序概率分数（Ranked Probability Score）|
| brier_reliability | Brier 可靠性分解 - 校准误差 |
| brier_resolution | Brier 分辨力 - 区分不同结果的能力 |
| brier_uncertainty | Brier 不确定性 - 结果本身的不确定性 |

低比分校准重点关注 Dixon-Coles tau 修正的四个桶：0-0、1-0、0-1、1-1。

### Poisson vs Dixon-Coles 对比

| 维度 | 独立泊松 | Dixon-Coles |
|---|---|---|
| 低比分精度 | 较差，低估 0-0 和 1-1 | 通过 rho 修正改善 |
| 计算复杂度 | O(n) 闭式解 | 需要数值优化 |
| 时间衰减 | 不支持 | 支持半衰期衰减 |
| 参数数 | 2n + 2 | 2n + 3（含 rho）|
| 适用场景 | 快速基线 | 正式预测 |

## 神经网络候选模型

球员评分优化器可选使用神经网络替代遗传算法：

```text
architecture: MLP(input_dim -> 128 -> 64 -> 32 -> 1)
activation: ReLU + LayerNorm
optimizer: AdamW
loss: composite_objective (同上)
regularization: L2 + dropout
```

NN 模型输入为 `rating_feature_matrix.parquet` 中的标准化特征向量，输出单个优化评分。当前已实现并比较两类 GPU 候选：共享球员编码的 MLP，以及对球队球员集合做注意力聚合的 Set Transformer。两者都复用优化器的复合目标、先验正则、时间切分和早停门禁；Set Transformer 结构上更适合阵容集合，但不能仅凭结构复杂度替换 MLP。

训练使用时间序列分割验证，避免未来数据泄漏。NN 候选模型与遗传算法优化器并行运行，通过 holdout 指标（Spearman、Pearson、NDCG、校准 MAE）比较选择更优模型。

## 真实标签集成

真实标签（truth labels）通过 `player_truth_labels.parquet` 提供人工/身价/奖项级别的球员工影响力锚定：

```text
player_truth_anchor_loss =
  0.55 × z_mse(player_rating, truth_label_value)
+ 0.45 × (1 - corr_soft_rank(player_rating, truth_label_value))
```

集成条件：
- 需要通过 `rating_feature_matrix.parquet` 解析到 player_id → player_name/season 匹配
- 默认阈值：`--min-truth-labels 50`
- 只接收 `source_policy=independent` 且通过时间门禁的标签；`expert_tier` 派生标签始终排除
- 当前标签表含 17 行手工赛季奖项 benchmark，但均为赛季结束后标签，因此时间可用于因果训练的独立行数仍为 0

目的：在有满足时间边界的人工/身价/奖项标签后，把优化器从纯球队层代理信号拉回球员层真实影响力。当前 17 行只能作为 post-season benchmark，不能证明球员能力真值，也不会让 `research_health` 自动变成 `ready`。

## 数据流

```text
原始数据层
  FBref 标准表 ──────────┐
  Football-Data ─────────┤
  StatsBomb Open Data ───┤
  Understat (可选) ──────┤
  Transfermarkt (手动) ──┘
         │
         v
特征工程层
  player_match.parquet     (球员比赛级特征)
  team_match.parquet       (球队比赛级特征)
  team_features.parquet    (球队赛季特征)
  player_truth_labels.parquet (真实标签)
         │
         v
评分优化层
  optimize_ratings_gpu.py  (遗传算法/NN 优化)
  rating_feature_matrix.parquet (特征矩阵)
  optimized_params.npy     (优化参数)
         │
         v
产物层
  player_ratings_optimized.parquet (最终评分)
  optimized_params_meta.json (元数据)
  models/runs/<run_id>/   (模型运行注册)
         │
         v
预测层
  fit_independent_poisson() → Poisson 基线
  fit_dixon_coles()         → Dixon-Coles 模型
  predict_match() / predict_match_dc()
  dc_calibration_detail.parquet (校准报告)
         │
         v
服务层
  api.py (FastAPI 服务)
  api_server.py (路由定义)
  frontend/ (前端展示)
```

## 已知局限

1. **数据覆盖不均衡**：全量球员层只能稳定计算出勤和基础进攻；防守、控球、xT、xG 和门将评分只能在 StatsBomb 样本或后续新增数据上启用。
2. **位置映射粗糙**：FBref 标准表只有粗位置字符串（FW/MF/DF/GK），无法稳定区分 ST/W/AM/CM/DM/FB/CB，需要事件或阵型位置补充。
3. **门将评分不足**：当前数据只有 StatsBomb 样本中的 Goal Keeper 事件和 FBref 标准表的 GK 粗位置，不足以严肃评估门将。
4. **缺少 xG/xA**：全量 FBref 标准表没有 xG、xA、npxG 字段，进攻和效率质量只能使用进球/助攻 fallback。
5. **防守数据缺失**：全量 FBref 标准表没有抢断、拦截、解围等防守行为字段，防守贡献分只能降级为位置中位数 50。
6. **控球推进数据缺失**：没有传球、带球、渐进传球等字段，控球推进分只能降级为位置中位数 50。
7. **真实标签为空**：当前本地真值标签表为空，球员真实标签锚定损失自动跳过。
8. **比赛预测校准**：Dixon-Coles 模型在低比分区域（0-0、1-0、0-1、1-1）需要持续监控校准误差。
9. **联赛覆盖有限**：比赛结果数据主要覆盖欧洲五大联赛，非五大联赛球队强度可能被低估。
10. **Transfermarkt 限制**：不允许自动抓取，只能做本地手动导入，身价数据更新频率受限。

## 版本

文档版本：v2.1
最后更新：2026-06-11
