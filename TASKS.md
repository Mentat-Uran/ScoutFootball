# 任务路线图

当前状态：Pipeline 端到端可运行，评分系统处于真实影响力标签和训练目标重构前的校准阶段。`PROBLEMS.md` 中记录的 Pearson 误算、无 holdout、ST/W quality 绕路、availability 出勤捷径、球队聚合被高分钟球员拉拽和 holdout 覆盖不透明等问题，已经完成第一轮代码级防护；仍需用新口径重新跑完整优化并做 2526 holdout 误差复盘。P0 代码级改进（特征矩阵、缺失字段、finishing shrinkage、coverage 置信度、出勤诊断、位置内指标）和 P1 展示增强（mplsoccer、3 个核心页面、低置信度提示）已完成。本轮新增：Football-Data 10 赛季重建脚本、真实标签数据契约（`truth_labels.py`）、2526 评估 N/A 球队过滤、评分模型卡（`MODEL_CARD.md`）。

本路线图吸收 `advise.md` 的建议，但只采纳适合 ScoutLab 当前数据现实的部分：优先做展示增强、StatsBomb 事件动作价值、评分验证和模型评估，不把后续更新变成更多爬虫。

## 顶层架构

ScoutLab 的长期形态是本地优先的足球数据研究平台，而不是数据抓取集合。后续架构扩展为十层：前七层解决当前可落地的评分、事件价值、评估和展示，第八到第十层扩展到球探工作流、预测校准和空间/视频研究。

1. 数据与合规层：继续使用本地缓存、DuckDB 和 Parquet；Transfermarkt 只允许手动或授权导入；FBref 只作为受限低频补充源。
2. 标准事实层：把比赛、球队、球员、阵容、事件、赛季统计、身价和联赛强度统一到 raw/silver/gold/models/reports/logs 分层。
3. 跨供应商标准化层：先定义 ScoutLab 内部 event/tracking schema，再对齐 SPADL、atomic-SPADL、Common Data Format、kloppy/floodlight 抽象；短期不急加依赖。
4. 事件动作价值层：以 StatsBomb Open Data 为第一主源，新增 `src/scoutlab/action_value/`，形成 StatsBomb events -> SPADL/atomic-SPADL -> xT -> VAEP/Atomic-VAEP 的演进路线。
5. 球员真值与评分层：综合真实标签、赛季统计、xG/xA、xT/VAEP、出勤可靠性、联赛强度、年龄和趋势；训练目标必须引入真实球员标签，不能只优化球队积分相关性。
6. 评估与模型卡层：建立 `EVALUATION.md`、`MODEL_CARD.md`、位置内指标、跨位置总榜指标、误差分析、数据覆盖说明和模型运行登记。
7. 产品可视化与 API 层：Streamlit 保持本地只读；Plotly/mplsoccer 继续用于交互图和足球专用图；FastAPI 只暴露本地只读产物。
8. 球探决策层：围绕真实标签、低置信度球员和误差案例建立 watchlist、shortlist、人工审阅队列和可复现报告。
9. 比分预测与概率校准层：保持 Independent Poisson 作为基线，后续升级 Dixon-Coles + time decay，并用 log loss、Brier score、RPS 做对照。
10. 空间/视频/离球研究层：只在有合规样例数据后研究 StatsBomb 360、Metrica/open tracking、space control、xG+、off-ball value 或强化学习。

## 采纳边界

立即采纳：

- mplsoccer 作为可视化增强库。
- socceraction 思路作为事件动作价值层的主要参考。
- xT 作为 VAEP 前的第一版可落地动作价值模型。
- VAEP 论文作为评分解释和动作价值建模的理论核心。
- PlayeRank 的角色内、多维度评分思路，作为位置内指标和球探解释模板参考。
- 2026 combined rating 论文的 top-down + bottom-up 评分框架，作为真实标签层和评分目标重构参考。
- Dixon-Coles 作为比分预测第二主线，但优先级低于球员评分。
- xG finishing signal 使用样本量 shrinkage，禁止简单用 `goals - xG` 判定射术。
- StatsBomb Open Data 的引用要求进入数据源 license manifest。

暂缓采纳：

- kloppy 作为 v1.0 之后的跨供应商 event/tracking 数据标准化方案。
- floodlight 只参考 Game/Team/Player/Event/Frame/Segment 抽象，不直接引入。
- Common Data Format 作为 schema 对照和验证参考，短期不改变当前 Parquet 主干。
- xG+ / possession-level shot probability 作为远期研究方向。
- StatsBomb 360、Metrica/open tracking、SoccerNet/video 作为远期空间/视频研究方向。
- 神经网络评分器只作为真实标签层完成后的候选模型；没有球员级标签、缺失字段标记和 baseline 对比前，不进入默认评分产物。
- Opta、Wyscout、SkillCorner、TRACAB 等商业或 tracking 数据源不进入近期计划。

不采纳：

- 新增绕过反爬或验证码的爬虫。
- 把 StatsBomb 小样本事件能力写成全量球员评分能力。
- 用 Top N 位置配额替代真实影响力校准。
- 只用球队积分相关性训练神经网络，并把它写成球员真实能力模型。
- 在没有 tracking 样例、标签和评估 baseline 前，直接把强化学习、GCN、Transformer 写成默认评分架构。

## 调研参考

- 开源项目：[`socceraction`](https://socceraction.readthedocs.io/en/stable/index.html)、[`StatsBomb Open Data`](https://github.com/statsbomb/open-data)、[`mplsoccer`](https://mplsoccer.readthedocs.io/)、[`kloppy`](https://kloppy.pysport.org/)、[`floodlight`](https://floodlight.readthedocs.io/en/latest/)、[`Common Data Format`](https://www.cdf.football/)。
- 学术主线：[`VAEP`](https://arxiv.org/abs/1802.07127)、[`xT vs VAEP`](https://tomdecroos.github.io/reports/xt_vs_vaep.pdf)、[`PlayeRank`](https://arxiv.org/abs/1802.04987)、[`combined player rating`](https://link.springer.com/article/10.1186/s40537-026-01369-w)、[`xG finishing bias`](https://arxiv.org/abs/2401.09940)、[`Dixon-Coles`](https://research-information.bris.ac.uk/en/publications/modelling-association-football-scores-and-inefficiencies-in-the-f/)。
- 架构结论：近中期以 StatsBomb -> internal actions -> xT -> VAEP 和真实球员标签为主线；跨供应商 schema、tracking/video、xG+、off-ball value 和强化学习只作为 P6 之后的扩展，不抢 P0-P4。

## 已完成

- [x] 五类核心数据源接入：FBref、Football-Data、Understat、StatsBomb Open Data、Club Elo。
- [x] 本地缓存扩展到 10 赛季级别：Football-Data 原始 CSV 合计 68,953 行，Understat 为 31,902 个球员赛季行；当前活动 `combined_results.parquet` 为 5,330 行，需重建 10 赛季合并 Parquet。
- [x] FBref 5 赛季标准、射门、misc 表均为 14,356 行。
- [x] StatsBomb Open Data 当前缓存 126 场比赛、11,871 条事件。
- [x] 六个新适配器：SofaScore、SoFIFA、WhoScored、Capology、API-Football、Transfermarkt-datasets。
- [x] FBref 扩展：+5 联赛（葡超/荷甲/土超/苏超/比甲）+7 种 stat_type（passing/defense/possession/gca/playing_time/keeper/keeper_adv）。
- [x] Football-Data 扩展：5→18 联赛代码，10 赛季。
- [x] Understat 扩展：+RFPL，6 联赛×10 赛季。
- [x] StatsBomb 批量 events+lineups 下载+合并脚本。
- [x] IngestConfig 集中配置：15 联赛×10 赛季，YAML/JSON 可覆盖。
- [x] Pipeline 配置驱动重构，新增 4 个数据源 handler。
- [x] 跨源球员 ID 对齐：composite key + fuzzy match + 球队名规范化。
- [x] Pipeline 端到端：`scoutlab ingest` -> `scoutlab build-features` -> `scoutlab train`。
- [x] 数据验证入口：`scoutlab validate`。
- [x] FastAPI draft 入口：`scoutlab serve`。
- [x] Streamlit MVP 入口和多页可视化骨架。
- [x] Poisson 比分预测 baseline。
- [x] `value_fairness` OOF 训练产物。
- [x] PyTorch GPU 评分优化器和远程 GPU 计算脚本。
- [x] 粗位置角色重判、CM/后场/GK 权重上限、较强联赛强度曲线。
- [x] 评分优化器 holdout 化：优化只用训练赛季，评估输出 holdout Spearman/Pearson、rank loss、校准分箱、联赛分层和 overfit gap。
- [x] 修复 Pearson 指标误算，避免把 `spearmanr()` 的 p-value 当 Pearson。
- [x] 修复 ST/W quality 绕路：ST/W quality cap 生效，ST attack 不再被额外压死。
- [x] 降低 availability cap：所有位置 availability 上限收敛到 0.18-0.20，CM/DM/FB/CB/GK 不再允许用 0.30-0.36 的出勤权重主导评分。
- [x] 球队赛季聚合从纯分钟加权改为 capped minutes + core rotation 的稳健聚合，避免评分层和球队层重复奖励原始出勤。
- [x] CLI 和远程 GPU API 均按 capped position weights 报告权重，并输出 team aggregation 配置元数据。
- [x] 评估报告新增 team coverage：按 league-season 输出目标球队数、评分侧球队数、匹配球队数和覆盖率，避免把 2526 数据缺口误判成模型错误。
- [x] 重新生成 `player_ratings_optimized.parquet`。
- [x] 将 `advise.md` 融入未来架构和实施策略文档。

## P0：评分系统真实影响力校准

目标：先修训练目标，再扩展评分模型。当前球队积分相关性会偏向出勤、CM 和 GK，不能单独作为球员影响力标签。

- [x] 完成第一轮反出勤捷径 guardrail：availability cap 下调、ST/W quality cap、holdout 评估、稳健球队聚合、team coverage 报告。
- [x] 重建 Football-Data 10 赛季 `combined_results.parquet`，保留 2526 alias patch，并输出 raw CSV 总行数、active Parquet 行数、league-season 覆盖和输入 hash。
- [ ] 用新 aggregation/cap 口径重新跑 GPU 优化，生成新的 `optimized_params.npy`、`optimized_params_meta.json`、holdout predictions、league metrics、calibration 和 feature importance。
- [ ] 复盘 `PROBLEMS.md` 中的误差案例：Everton、Stuttgart、Hoffenheim、Rennes、Napoli、Real Madrid、Arsenal、PSG，记录新旧排名变化和仍未解决原因。
- [x] 增加出勤捷径诊断报告：minutes/starts/matches/availability 置换重要性、按位置 availability 权重、球队聚合权重分布。
- [x] 直接修补 2526 五大联赛测试集队名，使 Premier League、La Liga、Bundesliga、Serie A、Ligue 1 的 holdout coverage 均达到 1.00。
- [x] 对 coverage 低于 0.90 的 league-season 禁止输出强排序结论，只允许作为低置信度诊断样本；该规则仍适用于五大联赛以外的 2526 division 和后续新增数据。
- [x] 定义真实标签层级：Transfermarkt 手动导入、权威奖项、国际/俱乐部出场级别、专家分档、位置内人工校准集。
- [x] 新增标签数据契约和校验脚本，输出 `data/gold/feature_store/player_truth_labels.parquet`。
- [x] 标签契约必须包含 `label_source`、`label_confidence`、`as_of_date`、`position_scope`、`manual_review_flag`，并区分身价代理、奖项荣誉、专家分档和人工校准。
- [x] 新增评分特征矩阵契约，输出可复用的 `rating_feature_matrix.parquet` 或等价产物，包含数值特征、位置/联赛类别、数据源覆盖、缺失字段标记、输入文件 hash 和 feature manifest。
- [x] 修正缺失高阶字段处理：防守、控球、xT/VAEP、门将字段缺失时必须有 missing flag 和中性/低置信度 fallback，不能把缺失值 0 当成真实低能力。
- [ ] 重写优化目标：组合 Spearman/NDCG、位置内排序、跨联赛校准、年龄/趋势合理性、极端样本惩罚。
- [ ] 保留球队结果相关性作为辅助校验，不再作为主目标。
- [ ] 定义神经网络准入门槛：必须先有球员真实标签、时间切分、当前优化器 baseline、位置内/跨位置指标、误差案例复盘和低置信度规则；不允许只用球队积分监督训练默认模型。
- [x] 补全 2526 Football-Data 覆盖或在报告中剔除积分 N/A 球队，避免把数据缺口误判为模型错误。
- [x] 将位置内榜单和跨位置总榜拆成两个视图。
- [x] 给 GK、CB、FB、DM、CM、AM、W、ST 建立位置内指标和解释模板。
- [x] 对 finishing 使用 shrinkage，避免小样本 `goals - xG` 过度放大。
- [x] 输出评分模型卡，说明数据覆盖、权重、偏差、不可解释区域和低置信度球员。

验收：

- `uv run pytest tests/unit/test_rating_optimizer_validation.py`
- 生成新的评分产物和 holdout 报告。
- README、AGENTS、TASKS、MODEL_CARD 同步更新。

## P1：展示增强和可解释产品层

目标：先让当前评分、xG/xA、趋势和比赛事件变得可读，提升项目展示价值。

### 核心交付（3 个可截图页面）

- [x] **球员雷达/排名页**：球员雷达图（pizza chart），位置内 percentile，位置内 Top 20 榜单，球员详情卡（评分趋势、xG/xA、出勤、联赛强度调整）。
- [x] **身价偏离榜**：实际身价 vs 模型预测身价散点图，高估/低估 Top 20 列表，联赛和年龄段筛选。
- [x] **比赛预测页**：即将进行的比赛列表，主/客/平概率，比分分布图，模型置信度提示。

### 其他增强

- [x] 引入 mplsoccer 依赖并保持 Plotly 现有交互图不回退。
- [x] 新增 `src/scoutlab/viz/pitch.py`，封装球场、坐标、shot map、pass map、heatmap 基础图。
- [ ] 在 Streamlit 增加"位置内榜单"和"跨位置总榜"切换。
- [x] 增加低置信度提示：分钟不足、数据源缺失、位置重判不确定、事件样本不足。
- [ ] 给 README 加 3–5 张截图（球员雷达、身价偏离、比赛预测、Top 100 榜单、详情页），并写一段"如何复现 demo 数据"的说明。

验收：

- `uv run ruff check .`
- `uv run pytest`
- `uv run streamlit run src/scoutlab/app/streamlit_app.py`
- 三个核心页面已完成，截图和 demo 复现说明待补充。

## P2：StatsBomb 事件动作价值层

目标：先用公开事件数据完成一条可复现的动作价值链路，不引入商业数据源。

- [ ] 盘点 `events_all.parquet` 字段和坐标覆盖，写入事件数据覆盖说明。
- [ ] 新增 `src/scoutlab/action_value/` 模块：`spadl_adapter.py`、`xt.py`、`vaep.py`、`aggregate.py`。
- [ ] 第一版只做 StatsBomb events -> internal actions -> xT；internal actions 需记录 provider action id、坐标系、方向、动作结果、前后状态和 source coverage。
- [ ] 输出 internal actions schema 文档，并说明它和 SPADL/atomic-SPADL、Common Data Format 的字段映射关系。
- [ ] 输出 `data/gold/feature_store/player_action_value.parquet`。
- [ ] 生成球员 xT 排行榜、球队 xT 热区图、球员传球/带球推进价值图。
- [ ] 评估 socceraction 作为依赖的可维护性，优先复用其 SPADL/xT/VAEP 能力。
- [ ] 明确 StatsBomb 数据引用要求：公开展示研究或图表时必须注明数据源。

验收：

- 事件动作价值产物可由命令重复生成。
- 单元测试覆盖坐标转换、动作类型映射、xT 聚合。
- 文档明确该层当前只覆盖 StatsBomb 样本，不代表全量联赛球员能力。

## P3：评分模型重构

目标：把传统赛季统计评分升级为可解释的混合球探评分。

计划评分结构：

```text
player_rating =
  season_stats_score
+ xg_xa_score
+ action_value_score
+ availability_reliability
+ league_strength_adjustment
+ age_trend_adjustment
+ confidence_adjustment
```

- [ ] 把 xT 聚合结果接入评分解释层，不直接替换当前评分。
- [ ] VAEP 在 xT 稳定后再做，不抢先实现。
- [ ] 明确各维度置信度：赛季统计、事件动作、xG/xA、联赛强度、位置映射。
- [ ] 按位置输出进攻、防守、控球、推进、终结、可靠性解释。
- [ ] 在真实标签层和特征缺失标记稳定后，新增浅层神经网络候选模型实验：数值特征 + 位置/联赛 embedding + dropout/weight decay，不直接替换当前评分器。
- [ ] 神经网络训练目标使用多任务结构：球员标签排序/回归为主，球队赛季积分相关性为辅助，另加跨联赛校准、年龄趋势合理性和极端样本惩罚。
- [ ] 神经网络产物写入 `data/models/player_rating_nn/`，保存 feature manifest、参数、随机种子、输入 hash、训练/holdout 指标和与 `player_ratings_optimized` 的对比。
- [ ] 建立评分回归测试，防止 CM/GK/出勤捷径再次主导 Top 100。
- [ ] 输出 `ALGORITHM.md` 的实现对齐版本。

验收：

- 新旧评分有可解释对比。
- 神经网络候选模型只有在 holdout、位置内指标、低置信度样本和误差案例均优于或至少不劣于当前优化器时，才允许进入默认展示。
- Top 100、位置内 Top 20、弱联赛顶端样本、低分钟球员均有审查报告。
- `MODEL_CARD.md` 更新。

## P4：模型评估文档和报告层

目标：把"能跑"升级为"可评估、可复现、可解释"。

### EVALUATION.md

- [ ] 说明数据切分方式：按赛季时间切分（train/test split），明确 holdout 赛季范围。
- [ ] 记录 baselines：league average、Independent Poisson、简单 percentile 聚合。
- [ ] 记录核心指标：Spearman rank correlation（位置内 + 跨位置）、NDCG、MAE、RMSE。
- [ ] 记录误差案例：Top 100 中出勤捷径球员、弱联赛高估样本、低分钟高方差球员、位置误判案例。
- [ ] 按位置输出 metrics：GK、CB、FB、DM、CM、AM、W、ST 分别报告。
- [ ] 若存在神经网络候选模型，必须与当前 PyTorch 权重优化器、v3 默认权重和简单 percentile baseline 同一时间切分对比。
- [ ] 对 value_fairness 增加 OOF 残差、联赛偏差、年龄段偏差分析。
- [ ] 对比分预测增加 log loss、Brier score、RPS，低比分场景（0-0、1-0、0-1、1-1）单独报告。
- [ ] 建立 `data/reports/model_runs/` 或等价模型运行登记：保存 dataset snapshot、输入 hash、参数、随机种子、依赖版本、指标和误差案例摘要。

### MODEL_CARD.md

- [x] 说明数据源：FBref、Understat、Football-Data、StatsBomb Open Data、Club Elo、Transfermarkt（手动导入）、Capology（手动导入）。
- [x] 说明标签定义：当前评分目标是什么、真实标签来源（手动导入、奖项、专家分档）、标签覆盖范围。
- [x] 说明适用边界：当前模型覆盖哪些联赛/位置/赛季、哪些场景可以信任、哪些场景结果不可靠。
- [x] 说明已知偏差：出勤偏差（CM/GK 偏高）、联赛强度偏差（弱联赛顶端样本）、位置偏差、年龄偏差、数据缺失偏差。
- [x] 说明不可用场景：单场评分、实时交易建议、青训选材、伤病预测、合同谈判。
- [ ] 每次训练保存 feature manifest、参数、随机种子、输入文件 hash。
- [ ] 每次公开图表或报告保存 data source attribution，尤其是 StatsBomb Open Data 衍生产物。

验收：

- `scoutlab train` 产出模型报告或报告输入数据。
- `EVALUATION.md` 和 `MODEL_CARD.md` 能解释当前模型能做什么、不能做什么、误差在哪。

## P5：比分预测升级

目标：把比分预测从可运行 baseline 升级为可比较模型族，但不抢球员评分主线资源。

- [ ] 保留 `baseline_0: league average`。
- [ ] 保留 `baseline_1: Independent Poisson`。
- [ ] 新增 `baseline_2: Dixon-Coles + time decay`。
- [ ] 建立低比分校准报告，重点看 0-0、1-0、0-1、1-1。
- [ ] 增加概率校准和回测页。

验收：

- 三档模型同一时间切分、同一指标对比。
- Dixon-Coles 只有在优于 baseline 且校准合理时才进入默认展示。

## P6：跨供应商标准化与开放格式层

目标：让 ScoutLab 未来可以接入更多 event/tracking 数据，但当前不新增商业数据源，不改变 DuckDB + Parquet 主干。

- [ ] 设计 ScoutLab internal match/event/tracking schema，字段至少覆盖 match metadata、team/player identity、period/time、coordinates、action type、outcome、freeze frame 可选字段和 source attribution。
- [ ] 写 `docs/DATA_CONTRACTS.md` 或等价文档，说明 StatsBomb events、internal actions、SPADL/atomic-SPADL、Common Data Format 之间的映射。
- [ ] 评估 kloppy：作为直接依赖、离线转换工具或暂不接入三种方案都要给出依赖风险、坐标转换风险和测试成本。
- [ ] 参考 floodlight 的 Game/Team/Player/Event/Frame/Segment 抽象，但只有在 tracking 样例数据进入仓库后才考虑代码接入。
- [ ] 新增 data source license manifest，记录每个本地数据产物的来源、许可/引用要求、可公开展示边界和更新时间。
- [ ] 所有 event/tracking schema 变更必须有 fixture、schema validation 和空数据行为测试。

验收：

- 文档能解释未来如何接入 StatsBomb 360、Metrica/open tracking 或授权 provider，而不影响当前 pipeline。
- 没有合规数据源时，该层只保留 schema 和转换实验，不进入默认训练。

## P7：球探决策与人工校准层

目标：把评分系统从“给分”推进到“可审阅的球探工作流”，同时为真实标签层提供人工闭环。

- [ ] 新增人工审阅队列：低置信度球员、弱联赛顶端样本、位置重判不确定样本、误差案例球员自动进入 review queue。
- [ ] 设计 watchlist/shortlist 数据契约，字段包括 `player_id`、`reason_code`、`rating_snapshot_id`、`confidence_level`、`review_status`、`reviewer_note`、`as_of_date`。
- [ ] 将 Transfermarkt 手动导入、奖项、专家分档、人工校准集统一进入 `player_truth_labels.parquet`，并保留标签来源和置信度。
- [ ] Streamlit 后续只读展示 review queue；写入型人工标注先用本地 CSV/Parquet 管理，不直接放进生产页面。
- [ ] 每轮评分优化后输出 watchlist diff：新增、移除、置信度变化、排名变化和触发原因。

验收：

- 评分变化能被人工复核追踪，真实标签可以回灌 P0/P3。
- 不把人工标签和模型预测混在同一字段里。

## P8：空间/视频/离球远期研究层

目标：记录更深研究方向，但只在 P2/P4/P6 稳定且数据合规后启动。

- [ ] StatsBomb 360 freeze-frame：先做 shot/pass context 可视化，再考虑空间占优或接球可达性特征。
- [ ] Metrica/open tracking：只用公开样例验证 schema、坐标和帧级数据管线，不写成全量 tracking 能力。
- [ ] xG+ / possession-level shot probability：作为控球过程威胁模型，必须先有 possession segmentation 和 baseline。
- [ ] off-ball value / space control：需要 tracking 或 freeze-frame 支撑，不能用普通事件数据硬推。
- [ ] 强化学习、GCN、Transformer 只作为研究实验；必须先有标签、baseline、离线评估、可解释报告和模型卡。

启动条件：

- P2 事件动作价值层稳定。
- P4 评估文档稳定。
- P6 schema 和 license manifest 稳定。
- 有合规数据源或明确的本地样例数据。

## 通用实施策略

- 每个阶段只交付一个稳定切片：数据契约、实现、测试、文档同步。
- 新增数据源前先写合规和缓存边界。
- 新增模型前先写 baseline 和评估指标。
- 新增可视化前先确认数据粒度、置信度和空状态。
- 不把计划中的模块写成已实现能力。
- 文档状态必须跟代码和本地数据文件一致。

## 通用验证命令

```bash
uv run ruff check .
uv run pytest
PYTHONPATH=src uv run python -m scoutlab info
PYTHONPATH=src uv run python -m scoutlab validate
```

## 爬虫运行环境说明

部分数据源需要特定运行环境，无法在无头 macOS 环境下运行：

| 数据源 | 运行要求 | 建议环境 |
| --- | --- | --- |
| FBref (soccerdata) | 需要 Chrome + Selenium (undetected-chromedriver) | Windows GPU 服务器 |
| WhoScored | 需要 Chrome + Selenium | Windows GPU 服务器 |
| SofaScore | 需要 Chrome + Selenium | Windows GPU 服务器 |
| SoFIFA | 需要 Chrome + Selenium | Windows GPU 服务器 |
| Capology | 需要 ScraperFC + Chrome | Windows GPU 服务器 |
| StatsBomb | 无特殊要求，但下载量大（~1000+ 场事件） | 稳定网络环境，运行 `scripts/fetch_statsbomb_full.py` |
| Transfermarkt-datasets | 无特殊要求，但 DuckDB 文件 ~500MB | 手动下载 DuckDB 放到 `data/raw/transfermarkt_datasets/` |
| API-Football | 需要 API Key（环境变量 `API_FOOTBALL_KEY`） | 任意环境，免费 100 请求/天 |

运行 soccerdata 相关脚本时需设置环境变量：
```bash
SOCCERDATA_DIR=./data/soccerdata uv run python scripts/fetch_fbref_10seasons.py
```
