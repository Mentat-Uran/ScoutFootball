# ScoutFootball 能力真相表

> 审计快照：2026-07-31，分支 `codex/integration`。本文只描述本地仓库可核验状态，不证明线上部署当前可达，也不把计划、样例或估算写成生产能力。球员评分的专项缺陷、目标产品和分阶段门禁见 [`PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md`](PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md)。

项目属性以 [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md) 为准：本地优先、MIT 开放源代码、个人维护、非盈利。本表中的桌面、容器、API 或可选协作能力不代表 SaaS、商业版、企业支持或营收计划。

## 状态定义

| 状态 | 定义 |
| --- | --- |
| 已交付 | 代码、入口和相应测试/产物存在，能明确说明适用边界 |
| 部分交付 | 主路径存在，但覆盖、契约、测试、发布或完整数据仍缺一项以上 |
| 样例/实验 | 只适合演示、研究或候选比较，不能代表完整赛事/人群/生产能力 |
| 本地状态 | 只保存在浏览器或同机服务，不是云同步、组织审计或跨设备协作 |
| 计划 | 文档或代码入口存在，但尚未满足交付定义 |
| 未核验 | 本次审计无法以当前运行时或网络环境复现，不能据此作当前承诺 |

## 一页结论

- 仓库已经是一个跨数据、模型、API、静态前端、桌面包装和世界杯场景的完整原型，不是空壳。
- 产品宽度显著超过旧文档的"7 个分析视图 + 4 个世界杯视图"：当前 HTML 中可见 24 个顶层 `data-view` 目标（含 P1 新增的 `workflow` 和 `versions`）。
- 当前焦点已收敛为本地个人球员评分研究。关键缺口不是"有没有更多功能"，而是评分目标语义、独立标签、canonical 身份、数据粒度、跨位置校准、不确定性、active rating 新鲜度和可重放研究闭环。
- 当前 41 个模型运行中没有可复核运行；29,723 条标签全部为模型体系衍生的 `expert_tier`，独立合格监督标签为 0。现有评分只能保持“部分交付/研究候选”，不能写成已验证的球员能力真值。
- 当前评分文件早于当前特征矩阵；最新候选因训练时 feature manifest hash 与现行 hash 不一致而不可复核。`scoutfootball research-health` 已用 `storage_health`、`lineage_health`、`model_reviewability`、`active_rating_freshness`、`research_readiness` 五层 fail-closed verdict 替代顶层 `ok`，并附带 `feature_coverage` 与 `data_grain` 证据 section；任何一层失败都会让评分系统明确进入 `not_ready`/`unavailable`，不再被隐藏为 `ok`。
- 浏览器球探工作区、战术工程和部分世界杯输入仍是本地状态；动作价值下钻仍只有 3 场比赛、94 条球员—比赛证据记录，并非 tracking；预计名单和模拟结果不是官方实时事实。
- 2026-07-29 在当前锁定 `uv` 运行时执行 `scoutfootball validate`，31/31 检查通过；该结果只覆盖当前文件、schema、部分唯一键和 lineage，不证明标签独立、模型语义正确或评分新鲜。

## 仓库规模快照

| 对象 | 本地观察 | 判断 |
| --- | ---: | --- |
| FastAPI 路由装饰器 | 202 | 产品契约面较宽，必须自动盘点和分域 |
| 静态前端顶层视图 | 24 | 旧 README 的 7+4 口径已过时；P1 新增 `workflow` + `versions` |
| Python `test_*.py` 文件 | 151 | 单元/集成基础较强，但不替代独立模型验证或完整测试实际完成 |
| 前端 Node 测试文件 | 4 | 有纯 JS 回归基础，覆盖面仍有限 |
| `frontend/app.js` | 29,845 个物理行 / 1.52 MiB | 高变更耦合风险，应按研究领域拆分 |
| `frontend/index.html` | 2,838 个物理行 / 205 KiB | 导航、模板和内容高度集中 |
| `src/scoutfootball/api.py` | 14,338 个物理行 / 537 KiB | 数据装配单体过大 |
| `src/scoutfootball/api_server.py` | 2,586 个物理行 / 93 KiB | 路由面需要分域和生成式文档 |
| `docs/TASKS.md` | 约 230 KiB | 活跃队列与历史交付日志混合 |
| `docs/CODEX_CONTINUOUS_STATE.md` | 约 318 KiB | 大量滚动状态不适合作为当前真源 |

这些数字是复杂度信号，不是产品成功指标。

## 产品能力清单

| 领域 | 当前能力 | 状态 | 证据边界 / 下一门槛 |
| --- | --- | --- | --- |
| 数据流水线 | `ingest`、`build-features`、`train`、验证和多类导出入口 | 已交付 | 当前工作区全部已登记来源已有本地保留/删除政策；上游快照日期、陈旧度与来源主张审计仍须逐项保留证据 |
| 本地数据层 | raw/silver/gold/models/reports/logs，DuckDB + Parquet | 已交付 | 当前锁定 `uv` 运行时的 21 个关键 Parquet 已通过内容级 preflight；每次数据或运行时变更后仍须重新检查，且这不替代来源、快照与许可审计 |
| 球员评分 | 球队积分代理优化器、覆盖/可用性约束、holdout 指标、模型运行登记、候选评分快照与本地准入/拒绝/晋级/回滚 | 部分交付 | 当前 41 个运行无 reviewable 候选，active rating 早于当前特征矩阵；默认特征未实际使用 xT/VAEP，角色、身份、跨位置校准和独立真值均未完成。只能作为研究候选，不能解释为已验证能力真值 |
| 评分研究健康门禁 | `scoutfootball research-health` CLI、`GET /health/research`、`evaluation.research_health` 五层 fail-closed verdict（storage/lineage/model_reviewability/active_rating_freshness/research_readiness）+ `feature_coverage`/`data_grain` 证据；`lineage_health` 现覆盖完整链路：评分文件 → 激活模型运行 → 训练 args 摘要 → feature manifest hash ↔ 当前 manifest → `source_lineage[i].input_hash` ↔ 当前 source parquet | 已交付 | 五层任一失败即整体 `not_ready`/`unavailable`，不再被顶层 `ok` 隐藏；source parquet 漂移即使 manifest 未重建也会被标为 `stale`；不证明评分语义正确，只如实呈现当前可发布性 |
| Synthetic fallback 隔离 | `data_loader.frame_is_synthetic`/`assert_real_frame` + `SyntheticDataError`；`get_player_profile` CSV 拒绝 synthetic、JSON 路径打 `data_mode=synthetic`；`get_player_ratings`/`get_value_summary` 同步标记 | 已交付 | Demo 数据进入 API 时必须显式标记；研究/评估/导出路径拒绝 synthetic；不阻止 UI 在 synthetic 下展示，但用户能立即看到状态 |
| Canonical 身份风险审计 | `scoutfootball audit-identity` CLI、`evaluation.identity_audit` 四维只读扫描（player_id 格式分布、同名不同 ID、多队赛季转会、跨源对齐缺口）；`ratings.identity_audit` capability | 已交付的诊断 | 只读扫描 `player_match.parquet`，不解决冲突、不修改任何产物；任一风险 present 即 verdict=`risks_present`；不证明身份层已 canonical，只如实呈现 PRS-1 R-005 风险面供维护者人工复核 |
| PRS-1 身份/粒度/cohort 内核 | `identity_registry`（append-only 决策账本 + 5 CLI 子命令）、`canonical_resolver`（`resolve_canonical_ids` 纯函数 + `load_resolved_player_match`/`load_resolved_player_ratings` 派生视图 + source-stable `unresolved:<source>:<id>` fallback + `canonical_match_ambiguous` 标记）、`identity_suggest`（精确标准化名称匹配 + 人工复核入口）、`grain`（`EvidenceGrain`/`ObservationType`/`MissingReason` typed enums + 只读 grain/missingness 审计 + ACTUAL_ZERO 部分检测）、`role_system`（`RoleFamily` 8 位置族 + `classify_role_family` 纯函数 + 只读审计）、`cohort`（`CohortDefinition` frozen dataclass + `preview_cohort` + `cohort_hash`/`membership_hash` 双哈希 + CLI `cohort-preview`）；API 层 `_infer_evidence_grain` 在 4 个评分/价值端点响应中标记 `evidence_grain` 防止 season-proxy 误读为 match-level | 已交付 | PRS-1 verified（2026-07-31）。当前 30,483 行 legacy 评分表中 7 行 resolved、1,640 行 `canonical_match_ambiguous=True`、其余保持 `unresolved:<source>:<id>` 或 `unresolved:unknown:missing`——unresolved 是诚实默认不是失败。registry 仅含 10 条 statsbomb→understat 人工确认映射，未自动跨源对齐。cohort_hash 仅依赖定义，membership_hash 依赖定义+数据。grain audit 在 `rating_feature_matrix.parquet` 上报告 27,598 行的 match/season_proxy/aggregate 三类分布。角色体系 v1 不自动创造 DM、不替换 `POSITION_GROUP_MAP`。不证明评分语义正确，只提供 PRS-2/PRS-3 可复用的身份/粒度/cohort 基础设施 |
| PRS-2 B0 透明 baseline | `scoutfootball baseline-b0` CLI、`evaluation.baseline_b0` 模块（`compute_b0_baseline` + `B0_DIMENSIONS` 角色特定维度定义 + 向量化百分位 + bootstrap 排名区间）；`ratings.baseline_b0` capability | 已交付的诊断 | PRS-2 B0 是角色内等权百分位 baseline，不是球员能力最终判断。当前在 22,956 行上评分（GK 1,996 / CB 9,014 / CM 6,499 / ST 5,447 + UNKNOWN 3,791 不评分）。GK 为 availability-only 占位（gk_provisional），不消费外场防守代理。cross_position_comparable=False。B0_DIMENSIONS 只引用 rating_feature_matrix 当前实际存在的列（goals/assists/npxg/xa/tackles/interceptions/passes/minutes_played/starts）。read-only；不修改任何 parquet 产物 |
| PRS-2 B1 专家权重 baseline | `scoutfootball baseline-b1` CLI、`evaluation.baseline_b1` 模块（`compute_b1_baseline` + `B1_WEIGHTS` v1.0 版本化角色权重 + 缺失下权重再归一化 + bootstrap 排名区间）；`ratings.baseline_b1` capability | 已交付的诊断 | PRS-2 B1 在 B0 角色内百分位之上替换等权为版本化专家权重（B1_WEIGHTS v1.0：ST finishing=0.55/attacking=0.25/availability=0.20；CB defending=0.50/possession=0.20/availability=0.30；CM possession=0.40/creation=0.30/availability=0.30；AM creation=0.50/finishing=0.30/availability=0.20；W attacking=0.60/availability=0.40；GK availability=1.0 占位）。权重和=1.0 是显式专家选择而非优化器 softmax 输出。缺失维度下权重自动再归一化（CB 缺 possession 时 defending/availability→0.625/0.375）；全核心维度缺失时 score=50.0、confidence=low，权重不被应用。B1 复用 B0_DIMENSIONS，与 B0 唯一差异是聚合方式（等权→加权），任何 B1 vs B0 分数差异归因于权重选择。GK 权重集为 availability=1.0 故 B1==B0，仍为 gk_provisional。当前在 22,956 行上评分，真实数据 ST top-1 Ollie Watkins score=98.20 rank_interval p5=1/p50=1/p95=2。每条 B1DimensionScore 记录 weight+effective_weight+contribution 可手工复算。cross_position_comparable=False。read-only；不修改 rating_feature_matrix.parquet |
| PRS-2 B2 分钟收缩 baseline | `scoutfootball baseline-b2` CLI、`evaluation.baseline_b2` 模块（`compute_b2_baseline` + 经验贝叶斯收缩 + stable_core prior + bootstrap 排名区间）；`ratings.baseline_b2` capability | 已交付的诊断 | PRS-2 B2 在 B0 之上叠加基于 minutes_played 的经验贝叶斯收缩：`b2_score = w * prior_mean + (1 - w) * b0_score`，`w = reference_minutes / (reference_minutes + minutes_played)`，默认 `reference_minutes=900`（10 场 full match）。低出场球员被向角色先验收缩（90 min 球员 w≈0.91，3000 min 球员 w≈0.23）。prior_mean 取角色池 stable core（minutes >= reference_minutes）的分钟加权 B0 均值，无 stable core 时 fallback 到全池简单均值。当前在 22,956 行上评分，所有角色池均有 stable core（无 fallback）。真实数据示例：1 分钟 ST 球员 b0=0.00→b2=58.17（向 prior 收缩）；Salah/Watkins/Kane 等 3000+ 分钟球员 b2 与 b0 差距 < 9 分（轻度收缩）。GK 仍为 gk_provisional。cross_position_comparable=False。read-only；不修改任何 parquet 产物 |
| PRS-MODEL-011 B1 权重敏感性诊断 | `scoutfootball weight-sensitivity` CLI、`evaluation.sensitivity` 模块（`compute_weight_sensitivity_report` + 乘法扰动 + 重归一化 + 4 指标稳定性测量）；`ratings.weight_sensitivity` capability | 已交付的诊断 | PRS-2 切片 PRS-MODEL-011（2026-07-31）。在 B1 之上叠加只读诊断，量化排名对专家权重选择的依赖程度。对每个角色的每个维度权重应用可配置的扰动 delta（默认 `(-0.20, -0.10, 0.10, 0.20)`，乘法扰动 `w' = w * (1+delta)`），重归一化后重新计算 B1 分数，通过四个互补指标衡量排名稳定性：`spearman_correlation`（rank 上的 Pearson，无 scipy 依赖，n<2 或零方差返回 1.0 避免假警报）、`mean_abs_rank_shift`、`max_abs_rank_shift`、`top_n_overlap`（默认 N=10）。每维度独立扰动，不探索联合扰动空间；扰动后权重钳位到 0；当扰动使所有权重归零（如单维度 role 应用 delta=-1.0）时跳过并报告 `all_weights_zero`。复用 `baseline_b1._vectorised_weighted_scores` 保证扰动分数与 B1 baseline 字节级一致。read-only；不修改 `B1_WEIGHTS`、特征矩阵或任何 parquet 产物；不参与 fail-closed verdict（敏感性指标是信号不是门禁，高敏感维度不一定是缺陷，可能反映刻意的专家判断）。真实数据 smoke test：5 个 role family 全部产生报告，CB role `defending` 维度被标记为 most sensitive（min_spearman≈0.998），GK 因单维度 trivially stable。已接入 `research-health` 报告 `weight_sensitivity` 证据 section |
| PRS-MODEL-012 B2 分钟门槛敏感性诊断 | `scoutfootball minutes-sensitivity` CLI、`evaluation.minutes_sensitivity` 模块（`compute_minutes_sensitivity_report` + 绝对分钟扰动 + 复合效应 + 4 指标稳定性测量）；`ratings.minutes_sensitivity` capability | 已交付的诊断 | PRS-2 切片 PRS-MODEL-012（2026-07-31）。在 B2 之上叠加只读诊断，量化排名对 `reference_minutes` 参数选择的依赖程度。对 B2 的 `reference_minutes` 应用可配置的绝对分钟扰动（默认 `(-600, -300, -150, 150, 300, 600)`），重新计算 B2 分数。与 PRS-MODEL-011 不同，`reference_minutes` 扰动有复合效应：收缩权重 `w`、`stable_core` 成员、`prior_mean` 三者同时变化。通过四个互补指标衡量排名稳定性：`spearman_correlation`、`mean_abs_rank_shift`、`max_abs_rank_shift`、`top_n_overlap`（默认 N=10）。每条扰动报告 `perturbed_reference_minutes`、`prior_source`、`stable_core_count` 以便观察门槛变化是否触发 prior fallback 路径切换。B0 分数在所有扰动中保持不变（不依赖 reference_minutes），只有收缩和先验变化。复用 `baseline_b2._compute_prior_mean` 和 `_apply_shrinkage` 保证扰动分数与 B2 baseline 字节级一致。read-only；不修改特征矩阵、B2 参数或任何 parquet 产物；不参与 fail-closed verdict（敏感性指标是信号不是门禁）。真实数据 smoke test：5 个 role family 全部产生报告，CB role 在 delta=-600 时 min_spearman≈0.956（最敏感），GK 在 delta=-600 时 min_spearman≈0.944；所有角色 top-5 overlap ≥ 0.80。已接入 `research-health` 报告 `minutes_sensitivity` 证据 section |
| NN 评分 | `train-rating-nn` 监督式候选入口 | 样例/实验 | 只有独立合格标签、时间外 holdout 并优于 baseline 后才可晋级 |
| 评价标签 | schema、来源政策、手动 Transfermarkt 快照导入与保守身份复核 | 部分交付 | 当前 29,723 行全部为 `expert_tier`，独立合格标签为 0；不得把模型衍生标签当外部真值；PRS-3 标签账本 v1 已落地（见下行），但维护者实际标注的独立评价集仍为空 |
| PRS-3 个人评价标签账本 v1 | `scoutfootball label-append`/`label-revoke`/`label-list`/`label-stats`/`label-audit` CLI、`evaluation.label_ledger` 模块（append-only JSONL `data/gold/label_ledger/decisions.jsonl` + `human_pairwise_preference`/`human_tier` 两类标签 + `active_labels`/`label_independence_audit`/`label_stats`）；`ratings.label_ledger` capability | 已交付的诊断 | PRS-3 切片 1（2026-07-31）。账本只追加不修改：revoke 通过新增 `action=revoked` 记录、re-annotation 通过 `supersedes_decision_id` 实现。`label_independence_audit` 排除 `model_derived` 标签、检查 pairwise 不自比、observation_window 合法、evidence 非空。当前账本为空（维护者尚未实际标注）；审计只保证结构性不变量，不证明评价者真正盲标或证据正确；不修改任何 parquet 产物 |
| PRS-3 标签复核队列诊断 | `scoutfootball label-review-queue` CLI、`evaluation.label_review_queue` 模块（`build_review_queue` + `detect_pairwise_conflicts`/`detect_tier_conflicts`/`low_confidence_queue`/`retest_queue` + `--tier-conflict-threshold`/`--evidence-min-chars`/`--max-age-days` 阈值）；`ratings.label_review_queue` capability | 已交付的诊断 | PRS-3 切片 2 PRS-LABEL-005（2026-07-31）。在 label_ledger 之上叠加只读诊断，识别四类需要维护者注意的 active 标签子集：pairwise preference contradiction（同 pair 相反偏好）、tier rating conflict（同球员同角色同赛季 tier 极差 ≥ 阈值，默认 2）、low confidence/thin evidence（confidence=low 或 evidence < 30 字符）、aged retest（recorded_at 距今 > 180 天）。空账本返回 0/0/0/0；不参与 fail-closed verdict（诊断而非门禁，空队列不意味系统就绪）；已接入 `research-health` 报告 `label_review_queue` 证据 section；不修改 ledger 文件 |
| PRS-3 标签稳定性诊断 | `scoutfootball label-stability` CLI、`evaluation.label_stability` 模块（`build_stability_report` + `compute_retest_pairs`/`compute_annotator_agreement` + `--tier-tolerance` 阈值）；`ratings.label_stability` capability | 已交付的诊断 | PRS-3 切片 3 PRS-LABEL-006（2026-07-31）。在 label_ledger 之上叠加只读诊断，量化维护者标注的稳定性。(1) `retest_pairs`：通过 `supersedes_decision_id` 链追踪 re-annotation 对（original → retest），对比两者标签值是否一致——pairwise 比较 first/second/tie 方向，tier 比较 `|original_tier - retest_tier| <= tier_tolerance`（默认 1）。(2) `annotator_agreement`：按业务键（pairwise 为 sorted player pair + cohort + role + season，tier 为 canonical_player_id + cohort + role + season）分组所有 confirmed 记录，只报告有 ≥ 2 个不同 `decided_by` 的组。空账本返回 0/0/0/0；不参与 fail-closed verdict（稳定性指标是信号不是门禁，空报告不意味标签正确或监督就绪）；已接入 `research-health` 报告 `label_stability` 证据 section；不修改 ledger 文件 |
| 球员身价（Market Value） | `GET /market-value/summary`、`GET /market-value/players`、`GET /market-value/players/{player_name}` 三个只读端点；从本地 `data/raw/transfermarkt_manual/` 读取 `player_profiles.csv` + `player_market_value.csv`（或 `player_latest_market_value.csv`）并在 API 层 join；响应携带 `source_name`/`source_uri`/`license_boundary`/`currency` 来源归因；fail-closed 空状态返回 `status="no_data"` + `checked_paths` | 已交付 | Transfermarkt 身价是主观估计不是市场成交价；仅个人本地使用，不可再分发；当前 33,420 行快照覆盖 33,420 名球员（latest 2025-09-11），不等于实时或全量；position/position_group 未映射到 `RoleFamily`；前端尚未接入身价视图 |
| 比赛预测 | Independent Poisson、Dixon-Coles 基线、概率矩阵与校准展示 | 已交付的基线 | 不是投注建议；需按联赛/时间/阵容覆盖持续校准 |
| 动作价值 | xT/VAEP 聚合、分页、来源标记、比赛证据下钻 | 部分交付 | 本地 footer 报告聚合 9,951 行；下钻仅有 3 场比赛、94 条球员—比赛证据记录，不能写成 tracking 或全量联赛 |
| 球员画像/对比 | 百分位、趋势、雷达、导出和低置信度原因 | 已交付 | 结论强度必须服从字段覆盖、联赛和样本量 |
| 球探工作区 | review/watch/shortlist、备注、决策档案、版本化导入导出、冲突预览 | 已交付的本地工作流 | 默认浏览器本地；同机 loopback 持久化需显式开启；不是组织云协作 |
| 战术板 | 本地工程、对象/图层/帧、动画、导入清洗、多格式导出、可选 ffmpeg | 已交付的本地工具 | 浏览器下载不等于服务器保存；本地视频叠画/追踪导入有研究门槛，实时云协作不在当前章程范围内 |
| 世界杯赛程/阵容 | 赛程、球队、比较、概率、淘汰赛/赛事分析 | 部分交付 | 数据快照和覆盖必须显示；预计征召不等于官方最终名单 |
| 世界杯赛前简报 | 从赛程打开来源受限简报、JSON/安全 CSV 下载、战术计划联动 | 已交付的本地/静态流程 | `recorded/not_recorded`、输入快照和模型边界必须端到端保留 |
| 世界杯 Core 契约复用 | 7 个 artifact 通过 `worldcup/contracts.py` 复用 Core `DataContract`/`SnapshotInfo`/`LineageEntry`；5 类事实类型（official_roster/expected_callup/injury_report/rating_coverage/model_probability）；`GET /world-cup/contracts` registry 端点；`TournamentState` 1.1.0 嵌入 contract，1.0.0 向后兼容 | 已交付 | 满足 P1 退出门槛第 4 条"世界杯包与招募/比赛包复用 Core，没有复制身份/快照/导出逻辑" |
| 招募决策简报（Recruitment Brief） | `scoutfootball.recruitment-brief` v1.0.0 schema、BriefStore 版本化本地存储（`If-Match` 乐观并发）、备份/恢复/diff、`POST /recruitment/briefs`（create）、`GET /recruitment/briefs/{id}/backups`/`/diff`/`/restore`、前端 `versions` 视图时间线 | 已交付的本地工作流 | 默认浏览器本地 + 同机 loopback 文件持久化；不是组织云协作；API 仅暴露 create（`expected_revision=0`），更新/删除走 store 直连或 CLI |
| 招募决策档案（Decision Dossier） | `scoutfootball.recruitment-decision-dossier` v1.0.0 schema、DossierStore 版本化存储、状态机（draft→decided/rejected/superseded）、证据/反证/比较/风险条目、`POST /recruitment/dossiers`、备份/恢复/diff 端点 | 已交付的本地工作流 | 与 brief 共享 Core 契约；决策只能由维护者带决策文本确认后切换；不是自动评分晋级 |
| 对手赛前简报（Opposition Briefing） | `scoutfootball.opposition-briefing` v1.0.0 schema、BriefingStore 版本化存储、分节事实分级（official/recorded/estimated/unknown）、`POST /opposition/briefs`、备份/恢复/diff 端点 | 已交付的本地工作流 | 从赛程打开来源受限简报；`recorded/not_recorded` 边界必须端到端保留；不是官方实时球队新闻 |
| 对手赛后复盘（Post-Match Review） | `scoutfootball.opposition-post-match-review` v1.0.0 schema、ReviewStore 版本化存储、假设验证/证伪模式/新问题、`POST /opposition/reviews`、备份/恢复/diff 端点 | 已交付的本地工作流 | 与 briefing 共享 Core 契约；复盘结论必须标注事实分级和证据来源；不是自动视频分析 |
| 决策工作流导航 + 版本恢复 | 前端 `workflow` 视图：基于已加载 brief/briefing/dossier/review 状态推断可执行下一步、阻断原因和缺失证据；前端 `versions` 视图：四类记录的备份时间线、字段级 diff、`If-Match` 恢复、可移植离线包导出 | 已交付的本地工作流 | P1 E2E 覆盖 versions 视图冒烟、workflow 视图冒烟、四类 artifact（brief/briefing/dossier/review）的 diff+restore 往返（2026-07-25）；P1+ E2E 覆盖 dossier/review 的条目级编辑（supporting_evidence / risks / hypothesis_results 的新增、编辑、移除、客户端校验阻断：缺失 ID、重复 ID、非法枚举）（2026-07-25） |
| 世界杯可复现 demo 快照 | `scripts/demo_snapshot/export_worldcup_demo_snapshot.py` 导出 6 JSON + manifest + README，`--check` 验证 hash 一致性 | 已交付的本地流程 | 剥离 volatile timestamp keys（`generated_at`/`updated_at`/`created_at`/`recorded_at`/`as_of`）后计算 SHA-256；当前 6/6 文件 hash 一致；维护者数据变更后需重新导出 |
| 静态前端 | 24 个顶层视图、API/静态 fallback、离线状态 | 部分交付 | 静态路径映射不是全路由覆盖；静态 manifest 陈旧度和契约一致性需自动门禁 |
| API | 只读分析接口及有限、显式开启的本地工作区写入 | 已交付/部分交付 | 202 个路由装饰器过宽；需要分域、schema registry、弃用策略和 API/静态一致性 |
| Streamlit | 15 页研究/运维工作台 | 已交付 | 与主静态产品的职责需要收敛，避免双重产品真源 |
| 桌面/容器 | Electron/PyInstaller、Docker/GHCR/发布配置 | 部分交付 | 跨平台构建、签名、回滚和最终资产需在每次发布中独立确认 |
| 云部署 | README 记录 Vercel/Render 路径 | 未核验 | 本次不把文档 URL 当成当前可达证明；发布需要实际健康检查和访问确认 |

## 当前 24 个静态前端视图

| 组 | 视图 |
| --- | --- |
| 决策工作流 | 工作流导航、版本与备份 |
| 核心分析 | 总览、球员、对比、身价、比赛、球队、联赛、球探、动作价值、报告、战术板 |
| 世界杯 | 赛程、阵容、球队对比、概率、淘汰赛、赛事中心 |
| 质量与治理 | 许可、数据、校准、回测、帮助 |

导航数量不再继续扩张，除非新视图无法作为现有黄金工作流的步骤、详情或标签页表达，并同时给出契约、静态策略、空状态、移动端和 E2E。

## 本地产物观察

本次用当前系统 Python/PyArrow 读取 footer 得到以下元数据：

| 文件 | footer 行数 | 解释 |
| --- | ---: | --- |
| `data/raw/statsbomb_open/matches_all.parquet` | 2,187 | 与部分旧文档“空文件”说法冲突 |
| `data/gold/feature_store/player_action_value.parquet` | 9,951 | 与旧文档的 15,062 行说法冲突 |
| `data/gold/feature_store/player_truth_labels.parquet` | 29,723 | 包含 `label_source`，但来源分布未在本次成功解码 |
| `data/gold/feature_store/player_match_action_value_sample.parquet` | 94 | 仅比赛证据样例，不是完整联赛 |

此前审计环境曾报 `OSError: Repetition level histogram size mismatch`，但 2026-07-17
在当前锁定 `uv` 运行时对 `preflight --target key` 的 21 个关键产物完成了内容级
解码、schema 与抽样校验，未发现不可读文件。该检查只说明本次本地输入可读，不把
footer、mtime 或这一次运行写成来源新鲜度、许可完整性或永久数据健康结论。数据、
依赖或运行时变更后必须重新运行 preflight；若再次失败，先记录 writer、schema、
row-group、hash 和最小复现，只有完成备份及行数、schema、统计和来源不变校验后，
才可考虑重写文件。

## 真实性分类

### 可直接陈述

- 仓库存在本地流水线、API、静态工作台、Streamlit、桌面和容器构建路径。
- 球探工作区支持版本化本地导入导出与冲突预览。
- 世界杯赛程可以进入赛前简报，并将有来源的输入交给战术计划。
- 模型与导出已有部分来源、覆盖、快照和 lineage 字段。
- 招募 brief/dossier 和对手 briefing/review 四类决策记录有版本化本地存储、备份/恢复/diff 端点，且四类 artifact 的 diff+restore 往返均已通过真实浏览器 E2E（2026-07-25）。工作流视图的 OFFLINE blocker 推断、LIVE 状态契约（四类 artifact 的 create-*/*-missing 推断与 API 计数双向一致）与字段级 evidence gap 推断（complete/incomplete brief、classified/unclassified briefing 的 brief-gap-*/briefing-tier-* 推断与记录内容一致）均已通过真实浏览器 E2E（2026-07-25）。versions 视图支持从工具栏起草全部四类决策档案（brief / briefing / dossier / review，draft 状态），其中 dossier / review 支持从工作流视图跳转时携带 pre-fill 自动打开对话框与预选关联字段（2026-07-25）。versions 视图支持编辑已存在的 decision dossier / post-match review 的顶层字段（title / notes / human_opinion / recommendation / status / decision / decision_note）与状态推进（draft → decided / finalized），客户端校验 decision/status 一致性，409 revision conflict 时保持对话框打开让维护者刷新后重试（2026-07-25）。versions 视图支持条目级编辑 dossier 的 supporting_evidence / counter_evidence / comparisons / risks 和 review 的 hypothesis_results / falsified_patterns / new_questions / supporting_evidence / counter_evidence：新增/编辑/移除条目、全列表替换语义、客户端校验缺失 ID / 重复 ID / 非法枚举（fact_tier / severity / outcome），且 9 条条目级编辑往返 E2E 均已通过真实浏览器验证（2026-07-25）。两个完整决策工作流导航 E2E 已通过真实浏览器验证（2026-07-27）：工作流 A（recruitment brief → dossier）和工作流 B（opposition briefing → review）从空 store 出发，依次经过工作流视图推断 → 创建 brief/briefing → 工作流视图状态转印 → 创建 dossier/review（含 pre-fill）→ 工作流视图显示 draft gap → 编辑 dossier/review 推进到 decided/finalized → 工作流视图清除 draft gap 的完整导航链。工作流 C（数据与模型发布）与 A/B 不同构：A/B 是前端 UI 驱动的决策工作流（适用 Playwright E2E），C 是 CLI 驱动的数据/模型发布工作流（`validate` → `build-features` → `train`/`optimize_ratings_gpu.py` → `model-admission` → `promote-model-run`/`reject-model-run`/`rollback-model-run`），不适用浏览器 E2E；其覆盖由三层构成：(1) 单元测试覆盖各组件逻辑（`test_model_run_lifecycle.py` promote/rollback/reject/discard 各路径、`test_model_admission.py` 8 项 evidence 检查 + chain-of-custody、`test_optimizer_validation_gate.py` GPU optimizer 验证门禁、`test_phase10.py` 31 项 pre-training validation）；(2) integration smoke 覆盖 CLI 退出码（`test_pipeline_e2e.py` 的 `info`/`validate`/`build-features`/`train` 四命令）；(3) 真实端到端执行证据（WORKFLOW_LOG.md 参考工作流 2，2026-07-19 维护者实际执行 `optimize_ratings_gpu.py → model-admission → promote → rollback` 完整链路，sha256 字节级验证可逆性）。

### 必须带限定词

- “全量”只能指某个已验证产物的完整行集，不能指全球、完整联赛或完整赛季覆盖。
- “阵容”要区分官方名单、记录到的数据、预计征召和占位内容。
- “持久化”要区分浏览器 localStorage、同机文件、服务端数据库和云同步。
- “模型改进”必须说明相同输入、相同时间切分、baseline、误差和是否已晋级。
- “部署成功”必须有目标 URL、版本、访问策略和实际健康检查。

### 当前不能陈述

- 不能称动作价值比赛证据为全量联赛能力。
- 不能称 NN 候选为默认评分模型。
- 不能称预计世界杯名单为官方实时球队新闻。
- 不能称浏览器工作区为跨设备或多人审计系统。
- 不能因 workflow 生成 placeholder 或允许失败继续，就称发布资产已通过验证。

## 工程与发布缺口

| 缺口 | 当前观察 | 目标状态 |
| --- | --- | --- |
| 真实浏览器 E2E | 2026-07-27 起 `tests/e2e/` 提供 Playwright + 系统 Chrome 的 smoke + workflow + decision-workflow 覆盖（LIVE/STATIC/OFFLINE/空数据/低覆盖/字段缺失/移动阅读/导入安全/versions 冒烟/workflow 冒烟/workflow OFFLINE blocker/workflow LIVE 状态契约/workflow 字段级 evidence gap 推断（complete/incomplete brief、classified/unclassified briefing）/recruitment brief diff+restore 往返/opposition briefing diff+restore 往返/recruitment dossier diff+restore 往返/opposition review diff+restore 往返/versions 视图创建按钮可见性/versions 视图起草 dossier round-trip/versions 视图起草 review round-trip/versions 视图起草 brief round-trip/versions 视图起草 briefing round-trip/workflow → versions 创建跳转 pre-fill/versions 视图编辑按钮可见性/versions 视图编辑 dossier round-trip/versions 视图编辑 dossier 状态推进到 decided/versions 视图编辑 dossier 客户端校验阻断/versions 视图编辑 dossier 冲突恢复/versions 视图编辑 review round-trip/versions 视图编辑 review 状态推进到 finalized/versions 视图编辑 dossier 新增 supporting_evidence 条目往返/versions 视图编辑 dossier 移除 supporting_evidence 条目往返/versions 视图编辑 dossier 编辑已存在 supporting_evidence 条目往返/versions 视图编辑 dossier 缺失 evidence_id 客户端校验阻断/versions 视图编辑 dossier 重复 evidence_id 客户端校验阻断/versions 视图编辑 dossier 非法 fact_tier 客户端校验阻断/versions 视图编辑 dossier 新增 risk 条目往返/versions 视图编辑 review 新增 hypothesis_result 条目往返/versions 视图编辑 review 移除 hypothesis_result 条目往返/workflow A recruitment brief → dossier 完整导航路径/workflow B opposition briefing → review 完整导航路径），通过 `-m e2e` 显式运行 | 工作流 A 与 B 完整导航路径已覆盖；工作流 C（数据与模型发布）与 A/B 不同构，是 CLI 流程而非前端 UI 工作流，不适用浏览器 E2E，已有三层覆盖：单元测试（`test_model_run_lifecycle.py` + `test_model_admission.py` + `test_optimizer_validation_gate.py` + `test_phase10.py`）、integration smoke（`test_pipeline_e2e.py` 四命令退出码）、真实端到端执行证据（WORKFLOW_LOG.md 参考工作流 2，2026-07-19 sha256 字节级验证可逆性） |
| 发布 fail-open | 2026-07-17 G0-B 已清理关键发布/数据 workflow 的 `continue-on-error`、`|| true` 和成功 placeholder | 关键验证失败即停止；仅非关键上传可明确容错 |
| 签名与跨平台 | 签名发现被禁用，平台状态在文档间有漂移 | 每个平台独立构建、签名/未签名声明、安装与回滚证据 |
| 静态新鲜度 | 已以本地 release 导出刷新 `frontend/data_manifest.json`；检查器同时核对文件清单、大小、去重和汇总元数据。`npm run build:sites` 与 CI 在复制 STATIC 快照前均会失败关闭 | 自动重新生成、来源/快照 SLO 与跨产物一致性仍留给 C1；门禁不会把旧快照写成新数据 |
| 契约维护 | `project_manifest.json` 与 [`REFERENCE_INDEX.md`](REFERENCE_INDEX.md) 由同一生成器产出；`--check` 同时校验机器清单和人读索引，并在 CI lint job 失败关闭 | schema registry + compatibility tests + C1 的来源/快照 SLO 强制 |
| 模块边界 | API/前端核心文件仍高度集中；[`ADR-0001`](adr/0001-core-module-boundaries.md) 已固定 facade、领域边界、首个低耦合 seam 和每次拆分的验证门槛 | 仅在已选参考工作流的契约/E2E 通过后，一次拆分一个领域 seam |
| 任务真源 | `TASKS.md` 顶部仅保留当前队列；历史交付记录归档在 [`history/TASKS-2026-07-17.md`](history/TASKS-2026-07-17.md)，且有链接/真源边界检查 | 新历史记录按版本归档，不能覆盖当前节点状态 |

## 当前验收优先级

1. 章程、个人参考工作流和实际输入的数据权利边界一致。
2. 标准运行时中所有关键 Parquet 可读、schema 可验证、统计可重算；发布关键步骤 fail-closed。
3. 来源、许可、快照、身份、契约和模型运行的统一能力登记。
4. 已声明支持的参考工作流完成真实浏览器 E2E、低覆盖/失败状态和静态/API 同契约验证。
5. 只有前置门槛通过后才开始新的顶层功能或空间/视频实验；多人云协作不在当前章程范围内。

长期顺序见 [`ROADMAP.md`](ROADMAP.md)，市场与产品判断见 [`FOOTBALL_TOOLING_LANDSCAPE_2026.md`](FOOTBALL_TOOLING_LANDSCAPE_2026.md)。
