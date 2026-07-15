# 任务路线图

当前状态：Pipeline 端到端可运行，评分系统处于真实影响力标签和训练目标重构前的校准阶段。最新 v1.3 GPU 优化产物已生成（2026-06-09 23:05，本地 `optimized_params_meta.json`）：2526 holdout Spearman=0.737/Pearson=0.742（baseline 0.621/0.618），raw spread ratio=0.336，train-fitted global points spread ratio=0.985，points MAE=11.55，points bias=-6.47，team coverage=0.990。v1.3 解决了整体分布压缩，但暴露出联赛截距偏差：Serie A -16.6、Ligue 1 -11.3、La Liga -11.2、Premier League +5.8、Bundesliga +1.8。2026-06-09 已完成 v1.3.1-dev 代码级改进：新增训练集联赛残差 offset 和 league-bias loss；只读复算显示当前参数下 points MAE 可从 11.55 降到 9.44，但完整 GPU 重跑仍待执行。2026-06-10 已新增 v1.3.2-dev 代码入口：优化器支持可选 `player_truth_labels.parquet` 球员真值标签锚定损失，`scoutfootball train-rating-nn` 支持监督式 sklearn MLP 候选模型并写入 `data/models/player_rating_nn/`；当前真值标签表仍为空，因此 NN 路径会跳过，默认评分产物未被替换。

本路线图吸收 `advise.md` 的建议，但只采纳适合 ScoutFootball 当前数据现实的部分：优先做展示增强、StatsBomb 事件动作价值、评分验证和模型评估，不把后续更新变成更多爬虫。

## 顶层架构

ScoutFootball 的长期形态是本地优先的足球数据研究平台，而不是数据抓取集合。后续架构扩展为十层：前七层解决当前可落地的评分、事件价值、评估和展示，第八到第十层扩展到球探工作流、预测校准和空间/视频研究。

1. 数据与合规层：继续使用本地缓存、DuckDB 和 Parquet；Transfermarkt 只允许手动或授权导入；FBref 只作为受限低频补充源。
2. 标准事实层：把比赛、球队、球员、阵容、事件、赛季统计、身价和联赛强度统一到 raw/silver/gold/models/reports/logs 分层。
3. 跨供应商标准化层：先定义 ScoutFootball 内部 event/tracking schema，再对齐 SPADL、atomic-SPADL、Common Data Format、kloppy/floodlight 抽象；短期不急加依赖。
4. 事件动作价值层：以 StatsBomb Open Data 为第一主源，新增 `src/scoutfootball/action_value/`，形成 StatsBomb events -> SPADL/atomic-SPADL -> xT -> VAEP/Atomic-VAEP 的演进路线。
5. 球员真值与评分层：综合真实标签、赛季统计、xG/xA、xT/VAEP、出勤可靠性、联赛强度、年龄和趋势；训练目标必须引入真实球员标签，不能只优化球队积分相关性。
6. 评估与模型卡层：建立 `EVALUATION.md`、`MODEL_CARD.md`、位置内指标、跨位置总榜指标、误差分析、数据覆盖说明和模型运行登记。
7. 产品可视化与 API 层：Streamlit 保持本地只读；`frontend/` 静态工作台保留 Liquid Glass 风格并作为长期产品壳；Plotly/mplsoccer/ECharts 继续用于交互图和足球专用图；新增电子战术板作为本地战术演示、动画和导出工作台；FastAPI 只暴露本地只读产物。
8. 球探决策层：围绕真实标签、低置信度球员、误差案例和战术备注建立 watchlist、shortlist、人工审阅队列和可复现报告。
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
- 电子战术板先采纳浏览器本地工作台思路：标准化球场坐标、可拖拽球员/足球、箭头/区域/标签、轨迹/关键帧/步骤式动画、演示播放、PNG/PDF/WebM 导出、本地 JSON 工程。
- Dixon-Coles 作为比分预测第二主线，但优先级低于球员评分。
- xG finishing signal 使用样本量 shrinkage，禁止简单用 `goals - xG` 判定射术。
- StatsBomb Open Data 的引用要求进入数据源 license manifest。

暂缓采纳：

- kloppy 作为 v1.0 之后的跨供应商 event/tracking 数据标准化方案。
- floodlight 只参考 Game/Team/Player/Event/Frame/Segment 抽象，不直接引入。
- Common Data Format 作为 schema 对照和验证参考，短期不改变当前 Parquet 主干。
- xG+ / possession-level shot probability 作为远期研究方向。
- StatsBomb 360、Metrica/open tracking、SoccerNet/video 作为远期空间/视频研究方向。
- 战术板 MP4 导出、本地 ffmpeg、视频叠画、tracking 数据导入、3D/门后视角和实时协作放到战术板核心画布稳定之后。
- 神经网络评分器只作为真实标签层完成后的候选模型；当前只落地监督式 MLP 实验入口，没有球员级标签、缺失字段标记和 baseline 对比前，不进入默认评分产物。
- Opta、Wyscout、SkillCorner、TRACAB 等商业或 tracking 数据源不进入近期计划。

不采纳：

- 新增绕过反爬或验证码的爬虫。
- 把 StatsBomb 小样本事件能力写成全量球员评分能力。
- 在浏览器端执行训练、爬取、视频批量转码或重型模型推理。
- 用 Top N 位置配额替代真实影响力校准。
- 只用球队积分相关性训练神经网络，并把它写成球员真实能力模型。
- 在没有 tracking 样例、标签和评估 baseline 前，直接把强化学习、GCN、Transformer 写成默认评分架构。

## 调研参考

- 开源项目：[`socceraction`](https://socceraction.readthedocs.io/en/stable/index.html)、[`StatsBomb Open Data`](https://github.com/statsbomb/open-data)、[`mplsoccer`](https://mplsoccer.readthedocs.io/)、[`kloppy`](https://kloppy.pysport.org/)、[`floodlight`](https://floodlight.readthedocs.io/en/latest/)、[`Common Data Format`](https://www.cdf.football/)。
- 战术板案例：[`Tactico`](https://tactico.pro/) 的浏览器战术板、阵型/定位球预设和 MP4/WebM/GIF 导出；[`DrawTactics`](https://drawtactics.com/animated-tactics-board) 的路径动画、时间轴、easing 和 WebM 30fps 导出；[`TacticSlate`](https://tacticslate.com/football-tactic-board) 的离线优先、球员名/号码/角色、ghost silhouettes、PNG/PDF/WebM 和 2D/3D；[`Coach Tactic Board`](https://apps.apple.com/us/app/coach-tactic-board-soccer/id834813357) 与 [`Soccer Tactic Board`](https://play.google.com/store/apps/details?id=com.jenda.footballboard) 的自由画笔、训练器材、球员资料、文件夹和导入/导出；[`Metrica Tactical Boards`](https://www.metrica-sports.com/help-center/tactical-boards) 的球员 ID、区域、轨迹、门后视角、timeline slide 和 telestration 工作流；[`FC Tactix`](https://teloframe.com/features/tactics-board)、[`TacticalPad`](https://www.tacticalpad.com/en-us/new/index.php) 与 [`TacticalBoards`](https://tacticalboards.com/) 的 2D/3D、协作、导出和训练计划能力。
- 学术主线：[`VAEP`](https://arxiv.org/abs/1802.07127)、[`xT vs VAEP`](https://tomdecroos.github.io/reports/xt_vs_vaep.pdf)、[`PlayeRank`](https://arxiv.org/abs/1802.04987)、[`combined player rating`](https://link.springer.com/article/10.1186/s40537-026-01369-w)、[`xG finishing bias`](https://arxiv.org/abs/2401.09940)、[`Dixon-Coles`](https://research-information.bris.ac.uk/en/publications/modelling-association-football-scores-and-inefficiencies-in-the-f/)。
- 架构结论：近中期以 StatsBomb -> internal actions -> xT -> VAEP 和真实球员标签为主线；跨供应商 schema、tracking/video、xG+、off-ball value 和强化学习只作为 P6 之后的扩展，不抢 P0-P4。

## 当前不足总览（不含电子战术板）

以下条目是当前项目除 P1.5 电子战术板以外仍存在的功能不足、数据缺口和验证缺口，后续迭代不能只盯战术板：

- [x] **评分监督标签独立性审计（2026-07-13）**：新增 `source-policy-v1`，将当前由 `optimized_score` 派生的 `expert_tier` 明确排除在 NN 训练和 optimizer truth-anchor 之外；CLI `audit-truth-labels`、`GET /reports/truth-labels` 与报告页展示可用/排除的来源计数。当前本地 29,723 行均为 `expert_tier`，因此监督路径必须保持跳过，不能再报告其 NN holdout 为独立验证。
- [x] **Understat 历史评分覆盖（2026-07-14）**：`players_10seasons.parquet` 的 Big Five 赛季聚合统计现可作为明确标记的 Understat season proxy 接入 `player_match` 与 `rating_feature_matrix`；FBref 重叠赛季优先，RFPL 因缺少对应球队积分目标被排除。基于当前本地快照，内存验证将评分矩阵从 8,141 行扩展到 26,678 行，覆盖 1617–2526 的十个赛季；生成产物仍需显式执行 `build-features`。
- [x] **历史代理出勤可观测性（2026-07-14）**：评分优化器不再将 Understat 的 `games` 当成 `starts`。没有首发字段的行使用重新归一化的分钟/出场/角色稳定性出勤分和中性首发可靠性；模型运行 `meta.json` 记录来源、赛季、行数及可观测首发行数，避免把历史代理误解为完整出勤数据。
- [x] **优化器可选来源降级审计（2026-07-14）**：FBref misc/shooting 与 Understat 的 Parquet 缺失或读取错误不再中断训练准备；依赖字段回退到显式缺失处理，`meta.json` 记录 loaded/missing/unreadable 来源状态和错误类型。FBref 标准表与 Football-Data 结果保持必需，读取失败仍会中止，避免把不完整输入伪装成完整训练。
- [x] **优化器运行时预检（2026-07-14）**：新增 `scoutfootball optimizer-preflight --data-dir data`，只读检查必需/可选 Parquet、pandas/PyArrow 与 PyTorch，并以非零退出码阻止不完整环境开始训练；PyTorch 现为显式 `optimizer` extra，可用 `uv sync --extra optimizer` 复现安装。
- [x] **监督标签时间审计（2026-07-14）**：`audit-truth-labels` 与 API 报告现区分合格来源中的赛季内快照、赛后快照、无效日期和无效赛季；赛后标签不再能被误读为当季可用监督证据。
- **评分校准仍未闭环**：v1.3.1-dev 的 train-fitted league residual offset 和 league-bias loss 代码已写入，但完整 GPU 重跑、CV、稳定性、feature importance 和 Barcelona/Real Madrid/Burnley 等误差复盘仍待执行。
- **强队/降级队偏差仍需复盘**：当前模型仍记录强队系统性低估和降级队高估，不能只用整体 Spearman/Pearson 宣称球员真实水平已解决。
- **世界杯模块仍是混合/样例视图**：世界杯赛程、名单、对比和出线页还没有全量官方阵容、更多联赛评分覆盖、国家队阵容 API 和低覆盖分层说明，不能写成完整真实后端能力。
- [x] **预计名单阵容结构诊断**：世界杯球队前景、名单 API 与赛前简报现在按 GK/CB/FB/DM/CM/AM/W/ST 提供预计征召快照的位置数量、评分覆盖和规划深度标记；该诊断明确不是官方 26 人名单、首发、伤病或战术建议。
- [x] **预计名单双队位置对照**：世界杯对比页新增逐位置人数、目标、评分覆盖和两队差值表，并由只读 API 提供同一版本化契约；它只对照本地预计征召快照，不判定位置优劣或给出首发建议。
- [x] **预计名单比较本地导出**：双队位置深度对照现可导出浏览器本地 JSON 或带公式注入防护的 CSV，保留快照边界与限制说明，不写入服务器状态。
- **前端 API 联调不完整**：球员页还缺搜索、分页、完整 player profile 指标、报告导出；身价页还缺 value-fairness OOF report 细分；比赛预测页还缺统一 prediction service、模型版本、Brier/log loss/RPS 和校准状态。
- **报告页信息不足**：model-run registry 列表端点展示基础指标、依赖版本、输入 hash、误差案例和复现命令；详情端点提供 feature_importance parquet 级数据、params_summary min/max 和 data_attribution；前端展开时异步加载详情端点。数据归属面板展示 /license 端点的归属信息，模型运行对比视图支持选择两个 run 对比 holdout 指标。
- **动作价值仍是样本能力**：`player_value_metrics.parquet` 只代表 StatsBomb 事件价值样本；P2 产物尚未完成全量 internal actions/xT/VAEP 管线、socceraction 依赖评估和公开图表 attribution。
- **数据合规和 license manifest 不完整**：所有本地 Parquet/报告/导出物仍需要统一记录来源、许可、可公开展示边界、更新时间和 StatsBomb Open Data 引用要求。
- **安全和部署边界未闭环**：前端已做 escaping/sanitizer、CSP meta tag、SRI（echarts CDN）、X-Content-Type-Options 安全头、浏览器级 XSS/CSV 回归测试；可配置 CORS 和非本机部署说明仍待实现。
- **球探工作流增强中**：watchlist/shortlist/review queue 只读契约已存在，审阅状态流转、watchlist diff、shortlist notes 和结构化 shortlist dossier 持久化（前端 localStorage + 后端 opt-in ScoutingWorkspaceStore）以及球探报告导出（CSV/JSON 8 段）已实现；真实标签回灌仍待实现。
- [x] **短名单决策包导出**：球探页可将当前 shortlist 与浏览器本地 dossier 导出为 JSON 或带公式注入防护的 CSV；按优先级和评分排序，并明确不构成服务端审计、转会指令或跨设备同步。
- [x] **对比到短名单工作流**：球员对比现可导出版本化 JSON，并可将任一比较对象加入浏览器本地 shortlist，再进入既有决策包导出；不写入服务端或宣称转会建议。
- [x] **短名单战术板交接**：球探页可将当前浏览器本地 shortlist 作为带 dossier 上下文的球员标记创建到战术板；明确不构成确认首发或转会建议。
- [x] **预测报告本地导出**：比赛预测页可导出当前已加载的模型、概率、预期进球、置信区间和覆盖上下文为 JSON/CSV；明确不是保证、投注指令或实时比赛情报。
- [x] **动作价值到球探上下文**：动作价值研究档案导出可并列包含浏览器本地 shortlist dossier，并显式标记为不可与 xT/VAEP/比赛样本相加的决策注释。
- [x] **预测报告证据快照**：预测 JSON/CSV 可并列记录已独立加载的交锋/近期状态及势头查询摘要；它们显式不可与赛前概率相加或改写模型输出，缺失或旧对阵异步结果不会被推断或串入报告。
- [x] **预测到战术板证据交接**：通用赛前方案的版本化 decision pack 现可保留已加载的交锋/趋势和势头摘要，并强制标记为不可改写概率的独立上下文；导入时限制字段和值域，不生成阵容、可用性或战术结论。
- [x] **动作价值到评分候选桥接**：动作价值档案现可查询并导出严格的姓名、球队、赛季一致评分候选；没有共享稳定 ID 时仍要求人工确认，姓名单独匹配、自动 shortlist 或合并模型分数均被禁止。
- [x] **淘汰赛对阵赛前简报**：已填入双方球队的本地淘汰赛卡片可直接进入带轮次和临时状态上下文的赛前简报；未确定胜者席位明确返回 not-ready，不猜测对手或宣布官方赛程。
- [x] **淘汰赛本地赛果复盘**：API 录入赛果前保存独立的 Bradley-Terry 对阵概率快照；完成卡片可显示并导出本地结果与该快照的方向对照。旧/导入赛果没有快照时明确返回 `snapshot_not_recorded`，不从赛后概率反推赛前判断，也不把单场对照描述为模型评估或官方赛果。
- [x] **淘汰赛本地复盘总览与状态边界**：`/knockout/reviews` 汇总已完成本地赛果的快照覆盖与方向对照，并支持页面 JSON 导出；淘汰赛状态准确标为本地应用 API 持久化，手动导入导出不代表浏览器同步、跨设备自动同步或官方赛果。
- [x] **锦标赛状态安全导入、完整性诊断与变更清单**：导入前新增只读预览，显示小组赛果增删改、淘汰赛完成数和可能丢失的赛前快照，并以最多 20 条逐场赛果及淘汰赛记录清单说明替换影响；页面仅在当前编码预览成功后才启用确认导入。可解码但不一致的状态会返回最多 20 条赛程、比分或淘汰赛诊断且不写入、不修复、不部分导入本地状态。
- [x] **小组出线席位影响卡**：`/world-cup/tournament/qualification-impact` 对当前所选小组返回本地积分下的前二、第三名跨组排名、最佳第三八席切线、剩余场次和暂定状态；页面紧邻积分表展示，不将未完赛或本地录入结果描述为官方出线结论或比赛预测。
- [x] **资格影响 CLI 与本地快照**：`scoutfootball tournament qualification --group A [--json]` 复用同一纯 Python 解释；页面可下载当前加载的版本化本地 JSON，不写入服务端、不创建审计记录，也不改变官方赛果或预测边界。
- [x] **小组同分决胜可解释性**：`/world-cup/tournament/tiebreak-diagnostics` 显示积分、净胜球和进球均相同的本地同分簇，以及相互交手赛果是否已完整录入；未完整时页面明确其展示顺序暂定。同步修复 Python 随机化 `hash()` 造成的跨进程同分排序漂移，公平竞赛分和抽签仍不建模。
- [x] **同分决胜离线 CLI**：`scoutfootball tournament tiebreaks --group A [--json]` 输出与 API 相同的本地同分簇和相互交手完整性解释，仅读取状态，不把暂定顺序表述为官方排名。
- **比分预测仍是 baseline**：Independent Poisson 和 Dixon-Coles 可用，回测对比页（`/predictions/backtest`）已实现 log_loss/brier/rps 指标对比、isotonic 校准效果展示和 per-fold 趋势图（ECharts）。Decay 参数调优已实现（`tune-predictions` CLI + `tune_dixon_coles_decay()` 网格搜索 + `/predictions/tuning` API + 前端面板）。Bootstrap 置信区间已实现（`bootstrap_prediction_confidence()` + `/predictions/{home}/{away}` 的 `confidence_intervals` 字段 + 前端区间显示）。Form-weighted DC 预测已实现（`fit_dixon_coles_with_form()` + `?model=form` 端点 + 前端模型选择器）。集成预测已实现（`ensemble_prediction()` + `?model=ensemble` 端点 + 前端 Ensemble 选项和 per-model 分解表）。校准漂移监控已实现（`compute_calibration_drift()` + `/predictions/drift` 端点 + 前端漂移面板含 STABLE/DRIFT 状态和窗口表）。In-play 比赛势头预测已实现（`compute_momentum()` + `/predictions/{home}/{away}/momentum` 端点 + 前端 ECharts 时间线可视化，支持任意比分/分钟查询剩余比赛结果概率）。Ensemble 最优权重回测和低比分校准细化仍可进一步优化。
- **跨供应商标准化仍停留在规划**：internal event/tracking schema、DATA_CONTRACTS、kloppy/floodlight/CDF 对照、schema validation fixture 和空数据行为测试仍待补。
- **空间/视频/离球研究没有进入默认能力**：StatsBomb 360、Metrica/open tracking、space control、off-ball value、xG+、GCN/Transformer/RL 都只能在有合规样例、baseline 和模型卡后启动。

## 已完成

- [x] **候选名单与观察名单来源溯源（Shortlist & Watchlist Source Provenance）**（2026-07-16，Round 87）：修复候选名单/观察名单 toggle 函数中的静默数据丢失 bug，新增多来源溯源追踪。仅前端改动（`frontend/app.js` + `tests/unit/test_frontend_security.py`），无后端/API 变更。**问题**：`togglePlayerShortlist` 和 `togglePlayerWatchlist` 原本基于 `player.key` 二元 add-or-remove——球员一旦在名单中，任何来自不同来源（如 gap-target 面板 vs 仪表盘 vs riser/decliner）的 △ 点击都会直接移除该条目，静默丢弃原有来源信息。随着 Round 86 引入 `cross_scouting_dashboard` / `cross_scouting_dashboard_batch` reason code（与既有 `cross_scouting_gap_target` / `cross_scouting_style_match` / `trajectory_signal` / `cluster_recruit_fit` 并列），这成为高概率 UX 陷阱。**修复**：(1) 两个 toggle 函数现跟踪 `reason_codes` 数组（与旧版 `reason_code` 字符串并存）。当球员已在名单中且新 reason code 不同时，追加到数组（累积溯源）而非移除条目；当同一 reason code 再次 toggle 时从数组移除该 code，数组为空时才移除条目（保留 toggle-off UX）；无 reason code 时仍按旧版直接 toggle。`reason_code` 字段同步设为数组首个值，向后兼容。(2) 新增 helper：`_entryReasonCodes(entry)` 返回 codes 数组（读取时迁移旧版字符串）、`_normalizeEntryReasonCodes(entry)` 修改条目以填充 `reason_codes` 并同步 `reason_code`、`_renderReasonCodePills(entry)` 将每个 code 渲染为 `status-pill status-low` span（通过 `escapeHtml` 转义）。(3) 返回类型从 `boolean` 改为 `{added, reason_codes, source_change: "added"|"merged"|"removed"}`；使用布尔返回值的两个调用方（cluster_recruit_fit wiring 13214/13230 行）改为 `result.added`。(4) 观察名单和候选名单渲染改为调用 `_renderReasonCodePills(player)` 而非内联单个 `reason_code` 字符串，所有累积来源均以 pill 可见。(5) Review queue CSV 导出新增 `reason_codes` 列（管道符连接）；候选名单决策包 JSON 新增 `reason_codes` 数组字段，CSV 新增 `reason_codes` 列（管道符连接）。(6) Review queue 行 meta 和搜索 haystack 更新以包含所有 reason codes。**9 个新前端安全回归测试** 在 `TestShortlistProvenanceSecurity` 类中：helper 定义、normalize helper 定义、pills 使用 escapeHtml、两个 toggle 函数返回 `source_change` 含 `"merged"` 值、两个 toggle 函数推入 `reason_codes` 数组、观察名单/候选名单渲染使用 pills、CSV 导出含管道符连接 `reason_codes` 列。`node --check frontend/app.js` clean；ruff clean；104 个前端安全测试通过（95 旧 + 9 新）；跨 team_style + player_intel + api_json_cleaning + api_empty_data + api_endpoints 共 505 个测试通过。

- [x] **球探仪表盘交接接入（Scouting Dashboard Handoff Wiring）**（2026-07-16，Round 86）：闭合 Round 85 仪表盘工作流环，将仪表盘候选人行直接接入候选名单（△）和对比托盘（◇）交接流，并新增批量"加入所有缺口目标候选人到候选名单"按钮。仅前端改动（`frontend/app.js` + `tests/unit/test_frontend_security.py`），无后端/API 变更。(1) **`_wireCrossScoutingActionButtons` 泛化为三类型**——原函数使用 `type === "targets" ? ... : ...` 二元三目仅处理 `targets` 和 `style`；现新增第三个 `dashboard` 类型，使用 `data-cs-dash-short` / `data-cs-dash-compare` 属性、`cross_scouting_dashboard` reason code 和 `csDashShort` / `csDashCompare` dataset 键。新 helper `_reRenderCrossScoutingSection(type, team, season, minMinutes, topN, excludeSameLeague, positionGroup, maxPositions, usePositionWeights)` 分发 toggle 后重渲染到正确函数（`_renderScoutingTargets` / `_renderCrossScoutingDashboard` / `_renderScoutingStyleMatch`），保持 wiring 函数可读。现有 `targets` 和 `style` 调用方仍传 8 参数；新 `maxPositions` / `usePositionWeights` 默认 `undefined`，仅 `dashboard` 分支使用（`style` 分支在 `undefined` 时回退到复选框）。(2) **仪表盘候选人行新增 △ / ◇ 按钮**——`_renderCrossScoutingDashboard` 在缺口目标汇总表（top 3 位置，按钮操作每个缺口的头号候选人）和 per-position 风格匹配表（各 top 3 候选人，按钮操作该候选人）均新增 `actions-cell` 列。每个按钮使用 `escapeAttr(pKey)` 处理 `data-cs-dash-*` 属性值，`escapeHtml(t('cross_scouting_add_shortlist'))` / `escapeHtml(t('cross_scouting_add_compare'))` 处理 title；△ 按钮通过 `isInPlayerShortlist(pKey)` 反映 `active` 类。渲染后调用 `_wireCrossScoutingActionButtons(wrap, "dashboard", team, season, minMinutes, topN, excludeSameLeague, "", maxPositions, usePositionWeights)` 激活按钮。(3) **批量"加入所有缺口目标候选人"按钮**——新 handler `_wireCrossScoutingDashboardBatch(wrap, team, season, minMinutes, topN, maxPositions, usePositionWeights)` 将每个缺口位置的头号候选人加入候选名单，使用独立 `cross_scouting_dashboard_batch` reason code，跳过已在名单中的球员。仅当存在至少一个新候选人时渲染按钮（`hasBatchCandidates` guard）。状态通过头部下方 `#cs-dash-batch-status` 文本行呈现（使用 `textContent`，绝不用 `alert()`）——显示 `cross_scouting_dashboard_batch_added`（"Added {n} candidates" / "已加入 {n} 名候选"）或 `cross_scouting_dashboard_batch_none`（"No new candidates to add" / "无可加入的新候选"）。批量添加后重渲染仪表盘以刷新 △ active 状态。**3 个新 i18n 键**（zh + en）：`cross_scouting_dashboard_batch_add`、`cross_scouting_dashboard_batch_added`（含 `{n}` 占位符）、`cross_scouting_dashboard_batch_none`。**6 个新前端安全回归测试** 在 `TestScoutingDashboardHandoffSecurity` 类中：`test_dashboard_short_button_uses_escape_attr`、`test_dashboard_compare_button_uses_escape_attr`、`test_dashboard_batch_button_label_escaped`、`test_dashboard_batch_reason_code_present`、`test_dashboard_single_reason_code_present`、`test_dashboard_batch_handler_no_alert`（锁定 textContent-vs-alert 不变式）。`node --check frontend/app.js` clean；ruff clean；95 个前端安全测试通过（89 旧 + 6 新）；2360 个单元测试通过（2 skipped，`test_position_distribution.py` 的 torch 循环导入为既有问题已 ignore）；21 个 API 集成测试通过。

- [x] **球探仪表盘多位置扩展（Scouting Dashboard Multi-Position Expansion）**（2026-07-16，Round 85）：将 Round 84 前端-only 仪表盘（通过 `Promise.all` 并行调用 targets + 单个 CM 风格匹配）升级为后端聚合端点，单请求内扇出多位置风格匹配。(1) **后端 `compute_scouting_dashboard()`**——`features/team_style.py` 新函数（5225-5319 行）复用 `compute_scouting_targets()` 识别位置缺口，然后对 top `max_positions`（钳制 1-8）缺口位置调用 `compute_scouting_target_style_match()`（可选 `use_position_weights`）。返回统一 dict 含 `gap_targets`（含候选人的完整缺口上下文）、`position_style_matches`（per-position 风格匹配结果）、`n_gaps`、`n_positions_matched`、`max_positions`、`use_position_weights` 和非加性 `disclaimer`。每个风格匹配项含 `target_player`（球队该位置当前首发）和 `candidates`（跨联赛风格相似球员）。描述性叠加，不构成转会建议。(2) **API `GET /teams/{team}/scouting-dashboard`**——`api.py` 新 `get_scouting_dashboard()` 包装器（lazy import、`load_player_ratings()`、`_clean_json_value()` 序列化、空数据保护），在 `api_server.py` 中以 `max_positions` 作为 `Query(ge=1, le=8)`、`use_position_weights` 作为 bool query param 注册。(3) **前端重写**——`_renderCrossScoutingDashboard(team, season, minMinutes, topN, maxPositions, usePositionWeights)` 改为调用单个 `fetchScoutingDashboard()` helper；渲染含球队名 + `n_gaps`/`n_matched`/weighted 徽章 + CSV/JSON 导出按钮的头部、缺口目标汇总表（top 3 位置 + 深度缺口 pill + 头号候选人）和每个匹配位置一个风格匹配区块（top 3 候选人 + 相似度 pill + 球队当前首发参照）。`_lastCrossScoutingData` 缓存扩展 `dashboard` slot；`_csFindCandidateByKey` 扩展搜索 dashboard 数据的 `gap_targets` 和 `position_style_matches`；`_exportCrossScoutingCSV`/`_exportCrossScoutingJSON` 扩展 `dashboard` 分支（CSV 导出两段：缺口目标 + per-position 风格匹配）。`index.html` 仪表盘面板新增 `max_positions` `<select>`（1-8，默认 3）和 `use_position_weights` 复选框。5 个新 i18n 键（zh + en）。所有新增 `innerHTML` template-literal 赋值均使用 `escapeHtml()`。12 个新单元测试（空 / 球队未找到 / 基本 / max_positions 钳制 / 风格匹配有位置 / 匹配位置是缺口子集 / use_position_weights 标志 / disclaimer / 无 mutation / top_n 传播 / 空球队 / exclude_same_league 标志）。`node --check` clean；ruff clean；89 个前端安全测试通过；完整 pytest 套件通过。

- [x] **多球员球探套件（Multi-Player Scouting Suite）**（2026-07-16，Round 84）：扩展 Round 82/83 球探基础，3 个相互关联的功能覆盖后端、API 和前端。(1) **位置加权风格匹配**——在 `features/team_style.py` 新增 `_POSITION_STYLE_WEIGHTS` 常量，将 8 个位置组（GK/CB/FB/DM/CM/AM/W/ST）分别映射到 `_STYLE_FEATURES`（npg_p90/assists_p90/defense_composite/possession_composite）的 4 维权重向量（每行和为 1.0）。`compute_scouting_target_style_match()` 新增 `use_position_weights: bool = False` 参数；开启后目标向量与候选人向量均按位置权重逐元素相乘再做余弦相似度，将两者旋转到同一加权空间。响应新增 `weighted`（bool）和 `position_weights`（dict | null）字段；`style_vector` 仍上报原始未加权值以保留可解释性。权重设计突出位置关键维度（如 ST: npg=0.50/assists=0.25/def=0.10/pos=0.15；CB: def=0.50/pos=0.30/npg=0.10/assists=0.10）。`GET /teams/{team}/scouting-style-match/{position_group}` 接受 `use_position_weights=true` 查询参数。(2) **多球员对比 cap 5→6**——`compute_multi_player_comparison()`（`player_intel.py`）现接受 2–6 名球员（原 2–5），`_MULTI_COMPARE_MAX = 6`。`GET /players/compare-multi` guard 从 `> 5` 改为 `> 6`，`max_allowed: 6`。前端 `_CROSS_SCOUTING_COMPARE_MAX = 6` 替换 compare tray 中硬编码的 `2`；`_renderCompareTray` 在 `>= 2` 球员时启用对比按钮（原 `=== 2`），满员时显示上限提示；`_addToCompareTray` 和 `_wireCrossScoutingActionButtons` 中的对比按钮 guard 均使用新常量。(3) **球探仪表盘聚合面板**——新前端函数 `_renderCrossScoutingDashboard(team, season, minMinutes, topN)` 通过 `Promise.all` 并行调用 `fetchScoutingTargets` 和 `fetchScoutingStyleMatch(team, "CM", ...)`，渲染统一报告卡，含两个并排区块：top 3 缺口位置（含深度缺口 pill + 头号候选人姓名/球队/评分）和 top 3 CM 风格匹配候选人（含相似度 pill）。CM 作为默认风格匹配位置因其最为通用；其他位置用户应使用上方专属面板。`index.html` 在 compare tray 之后新增 HTML 面板（球队输入 + 仪表盘按钮 + 结果 div）。新 helper `fetchPlayerComparisonMulti(names, season)` 调用 `GET /players/compare-multi?names=A,B,C`。`_renderCompareTrayResult(names)` 重写为消费 multi-compare API，渲染 4 张表：百分位矩阵（per-dimension per-player 百分位 + status-pill 着色）、综合排名（rank/name/avg-percentile）、指标排名（per-metric per-player 原始值）、两两相似度矩阵（N×N，对角线 1.0）。**后端测试**：`test_team_style.py` 新增 7 个测试（默认未加权、加权标志 + 权重字典、加权改变排名（自定义 Attacker ST / Defender ST / Target ST fixture）、加权无 mutation、加权无效位置）+ `test_player_intel.py` 2 个更新（cap 测试 6→7 球员，新 `test_multi_compare_six_players_ok` 验证 6×6 两两矩阵含 1.0 对角线）。**前端**：11 个新 i18n 键（zh + en）含 `cross_scouting_style_weighted`、`cross_scouting_dashboard_btn/title/loading/no_data/depth/targets/style`；更新 `cross_scouting_compare_max` 文本 "2 players"→"6 players"、`cross_scouting_compare_need_two` "需要选择 2 名球员"→"至少选择 2 名球员" / "Select 2 players"→"Select at least 2 players"。所有新增 `innerHTML` template-literal 赋值均使用 `escapeHtml()` 处理动态内容。`node --check frontend/app.js` clean；ruff clean；89 个前端安全测试通过；完整 pytest 套件通过（`test_position_distribution.py` 的 torch 循环导入为既有问题，已 ignore）。

- [x] **球探决策包与候选名单交接（Scouting Decision Pack & Shortlist Handoff）**（2026-07-16，Round 83）：闭合球探工作流环，将 Round 82 跨球探候选人结果通过 3 个相互关联的前端功能接入候选名单交接、结果导出和球员对比，全部在 `#view-scouting` 跨球探面板内完成，无 Python/API 代码改动，所有变更在 `frontend/app.js` 和 `frontend/index.html` 内。(1) **球探目标 → 候选名单交接**——在 `_renderScoutingTargets`（reason_code: `cross_scouting_gap_target`）和 `_renderScoutingStyleMatch`（reason_code: `cross_scouting_style_match`）的候选人行新增 `△`（U+25B3）候选名单切换按钮，镜像 Round 72 riser/decliner → shortlist 模式。因 API 不返回 `player_id`，使用 `player_name` 作为候选名单键；调用 `togglePlayerShortlist({key, name, team, position, rating, reason_code})` 后重渲染当前结果区块以更新 `active` 类，并调用 `renderScouting()` 刷新候选名单面板。(2) **跨球探结果 CSV/JSON 导出**——在所有 3 个结果区块（depth / targets / style）新增 `data-cs-export` 按钮。新函数 `_exportCrossScoutingCSV(type)` 和 `_exportCrossScoutingJSON(type)` 从模块级缓存 `_lastCrossScoutingData = {depth, targets, style}`（每个 render 函数填充）读取数据。CSV 使用现有 `csvCell()` helper 防公式注入（前缀 `[=+\-@\t\r]` 加 `'`），含 `\uFEFF` BOM（Excel UTF-8 兼容）、`# header` 注释、列头、数据行、`# Limitations` 段落和 `# Exported` 时间戳。JSON 包裹源数据并附 `schema`/`version`/`exported_at`/`storage_scope`/`limitations` 元数据。两种格式均含非加性 disclaimer 和 browser-local-download 存储范围说明。新 helper `_downloadCrossScoutingFile(content, filename, mimeType)` 处理 Blob 下载。(3) **球探目标 → 球员对比交接**——在候选人行的候选名单按钮旁新增 `◇`（U+25C7）对比按钮。新数组 `_crossScoutingCompareTray`（max 2 球员）含 `_addToCompareTray(player)` / `_clearCompareTray()` / `_renderCompareTray()` 函数。对比托盘渲染在新 HTML 元素 `#cross-scouting-compare-tray`（在 `index.html` 中 style-match 结果 div 之后新增）内，含 per-player chip（姓名 + 球队 + 移除按钮）、"对比" 按钮（<2 球员时禁用）、"清空" 按钮和 <2 球员时的提示。选满 2 人后点击"对比"，`_renderCompareTrayResult(nameA, nameB)` 调用现有 `fetchPlayerComparison(a, b)` API 并内联渲染指标对比表。`_wireCrossScoutingActionButtons(wrap, type, team, season, ...)` 同时为指定结果区块 wire 候选名单和对比按钮，用 `_csFindCandidateByKey(key, type)` 从缓存数据查找候选人对象；`_wireCrossScoutingExportButtons(wrap)` wire 导出按钮。**11 个新 i18n 键**（zh + en）：`cross_scouting_col_actions` / `cross_scouting_add_shortlist` / `cross_scouting_add_compare` / `cross_scouting_compare_tray` / `cross_scouting_compare_clear` / `cross_scouting_compare_run` / `cross_scouting_compare_need_two` / `cross_scouting_compare_max` / `cross_scouting_export_csv` / `cross_scouting_export_json` / `cross_scouting_export_no_data`。所有新增 `innerHTML` template-literal 赋值均使用 `escapeHtml()` / `escapeAttr()` 处理动态内容。`node --check frontend/app.js` clean；89 个前端安全测试通过；跨 team_style + frontend_security 共 498 个测试通过（无回归）。

- [x] **跨联赛球队深度对比与球探目标推荐（Cross-League Team Depth & Scouting Target Recommendation）**（2026-07-16，Round 82）：3 个相互关联的描述性功能在 `features/team_style.py` 中扩展位置组深度画像（Round 77）到跨队对比和球探目标推荐，全部为非加性解释叠加，不修改预测模型或构成转会指令。(1) **跨联赛球队深度对比**——`compute_cross_league_team_depth()` 对给定赛季中的两支球队，使用 `_team_position_depth` 和 `_compute_position_depth_stats` 辅助函数构建 per-position-group 深度统计（n_players / total_minutes / 分数 min/median/max/mean/std / depth_label shallow<2 / adequate 2-3 / deep≥4），然后按位置分配 `advantage` 标志（team_a / team_b / even，使用 0.5 分均分阈值）并呈现 `complementary_positions`（较弱方仍有 adequate 深度 ≥2 球员的位置）。`GET /teams/cross-league-depth` 端点（team_a / team_b 均为 Query min_length=1，season，min_player_minutes Query ge=0.0）。请求球队不存在时返回 `team_a_not_found` / `team_b_not_found` 而非 `no_data`。(2) **球探目标推荐**——`compute_scouting_targets()` 复用 `compute_position_gap_report` 识别目标球队的缺口（shallow / low_quality / missing），然后对每个缺口位置扫描来自其他联赛的球员：(a) 参与缺口位置组，(b) 满足 `min_player_minutes`（默认 500.0），(c) 分数 ≥ 缺口阈值（shallow/missing 缺口用候选人本联赛该位置 p60，low_quality 缺口用球队均分），(d) 位于本联赛该位置 top quartile（p75）。返回 per-gap 块含 `gap_type`、`team_score`、`threshold` 和 `candidates` 列表（按分数降序，cap 在 `top_n` 默认 10，钳制到 1–50）；`exclude_same_league`（默认 true）过滤掉目标球队联赛的球员。`GET /teams/{team}/scouting-targets` 端点。(3) **风格匹配球探**——`compute_scouting_target_style_match()` 对目标球队和特定位置组，计算球队分钟加权 4 维风格向量（`_STYLE_FEATURES`: npg_p90 / assists_p90 / defense_composite / possession_composite），然后按同样 4 维向量的余弦相似度排列其他联赛的候选人（同样的分钟阈值 + top_n cap + exclude_same_league）。校验位置在 `_POSITION_GROUPS` 内（未知返回 `invalid_position`）。返回 `target_player`（球队该位置按分钟最高的球员）、`target_style_vector` 和 `candidates` 含 per-player `similarity`（0–1）、`style_vector` 和 `minutes`。`GET /teams/{team}/scouting-style-match/{position_group}` 端点。开发期 bug 修复：`_league_position_percentiles` 辅助函数缺少 `compute_scouting_targets` 引用的 `p60` 键——在返回字典中加入 `round(float(np.percentile(scores, 60)), 2)`，与 p25/p50/p75/p90/n_players 并列。同时移除了 `compute_scouting_targets` 中未使用的 `team_work` 变量（ruff F841）。**API 层**：`api.py` 新增 3 个 GET 函数（`get_cross_league_team_depth`、`get_scouting_targets`、`get_scouting_target_style_match`），均使用 lazy import、`load_player_ratings()`、`_clean_json_value()` 序列化和空数据保护；在 `api_server.py` 中以 `team_a`/`team_b` 作为 Query(min_length=1)、`min_player_minutes` 作为 Query(ge=0.0)、`top_n` 作为 Query(ge=1, le=50) 注册。**前端**：在 `#view-scouting` 中 style-fit 面板之后新增 Cross-League Scouting 面板，含 3 个子区块共享 season / min_minutes / top_n 输入——深度对比（team_a + team_b 输入 + "对比深度" 按钮 + position_comparison 表含 advantage pill + complementary positions 表）、球探目标（球队输入 + exclude_same_league 复选框 + "推荐目标" 按钮 + per-gap 块含候选人表）、风格匹配（球队输入 + position_group `<select>` 8 选项 + exclude 复选框 + "风格匹配" 按钮 + 目标球员信息 + 风格向量 + 候选人表含 similarity pill）。33 个新 i18n 键（zh + en）。所有 17 个新 HTML element ID 在 index.html 和 app.js 中均验证存在。**36 个新单元测试** 在 `test_team_style.py` 中跨 `compute_cross_league_team_depth`（12：空 / 缺球队名 / 无 position 列 / team_a 未找到 / team_b 未找到 / 基本 / advantage 标志 / complementary / 跨联赛 / 同联赛 / 字段 / 赛季过滤 / disclaimer / 无 mutation）、`compute_scouting_targets`（10：空 / 球队未找到 / 基本 / shallow 缺口有候选人 / 候选人字段 / 排除同联赛 / top_n / 钳制 top_n / disclaimer / 无 mutation）、`compute_scouting_target_style_match`（12：无效位置 / 空 / 球队位置未找到 / 基本 / 目标球员字段 / 候选人降序 / 候选人字段 / 排除同联赛 / top_n / disclaimer / 无 mutation）。全部 team_style 测试通过；ruff clean；`node --check frontend/app.js` clean。用合成数据端到端验证：深度返回 8 个位置，目标返回 4 个缺口含候选人，风格匹配返回 5 个候选人含 similarity 分数。

- [x] **联赛赛季投影与状态分析套件（League Season Projection & Form Analysis Suite）**（2026-07-16，Round 81）：3 个相互关联的描述/预测功能在联赛-赛季层面工作，填补项目此前只有比赛级和球员级分析、缺少赛季级投影的空白。三者全部位于新模块 `features/season_projection.py`（约 720 行），共享一个由赛季内 PPG 推导的 Bradley-Terry 强度估计；全部为相对 Dixon-Coles 预测模型的非加性解释叠加，绝不修改持久化模型产物。(1) **联赛状态表**——`compute_league_form_table()` 对联赛-赛季中每支球队构建 last-N（默认 6，钳制到 1–30）近期状态汇总：时间顺序 form string（如 "WWDLW"）、W/D/L 计数、PPG、0–100 状态评分、趋势标签（rising/declining/stable，近期半段 vs 早期半段 PPG，阈值 0.3）、主/客 PPG 拆分和进失球。球队按 PPG 降序排列。(2) **赛程难度评级**——`compute_fixture_difficulty()` 对每支球队最近 N 场（默认 10，钳制到 1–30）使用 Bradley-Terry 期望积分模型计算回溯赛程难度评级：log1p 强度来自赛季内 PPG 加 0.25 主场优势 logit，平局强度按 `exp(-|delta|) * 0.28` 缩放。每场比赛含期望积分、实际积分和难度标签（very_hard/hard/moderate/easy/very_easy）。请求球队在过滤后数据中不存在时返回 `team_not_found`（而非 `no_data`）。(3) **赛季投影**——`compute_season_projection()` 假设标准双循环赛制（每对相遇两次，主客各一场；剩余赛程由已赛配对的补集推断）对剩余赛季进行 Monte Carlo 模拟。通过 `random_seed` 可复现（使用 `np.random.default_rng`），`num_simulations` 钳制到 100–10000（默认 1000）。每队报告：当前积分/已赛场次、平均最终积分、平均最终排名、排名分布（仅含模拟中实际出现的排名）、夺冠概率、top-N 概率（默认 top_n=4）和降级概率（默认 relegation_slots=3）。球队按 `(avg_position, avg_final_points, team)` 升序排列。三个函数均返回 `disclaimer` 字段明确赛季内/Bradley-Terry/非 DC 边界。开发期 bug 修复：将不存在的 `pd.errors.mode("ignore")` 替换为 `warnings.catch_warnings()` + `warnings.simplefilter("ignore")`，用于 `_filter_results` 中的 `pd.to_datetime` 调用。**API 层**：`api.py` 新增 3 个 GET 函数（`get_league_form_table`、`get_fixture_difficulty`、`get_season_projection`），均使用 lazy import、try/except + `logger.warning` 和 `_clean_json_value()` 序列化，在 `api_server.py` 中作为静态路由注册在 `{team}` 参数路由之前：`GET /league/form-table`（league / season / last_n 1–30）、`GET /league/fixture-difficulty`（league / season / team / upcoming_n 1–30）、`GET /league/season-projection`（league / season / num_simulations 100–10000 / random_seed 0–2B / top_n 1–20 / relegation_slots 0–10）。**前端**：新增 League 视图（`view-league`）和导航按钮（图标 ⊞），4 个 article——特性 hero 含指标条（球队数 / 最高 PPG / 冠军概率）、过滤面板（赛季/联赛/last_n 下拉 + 刷新按钮）、状态表面板（8 列表，W/D/L form string pill 着色）、赛程难度面板（球队输入 + 查询按钮 + 每队赛程表含难度 pill）、赛季投影面板（模拟次数下拉 + 投影按钮 + 7 列表含夺冠/top-N/降级概率 pill + 非加性 disclaimer）。~50 个新 i18n 键（zh + en）。**安全修复**：4 处新增 template-literal `innerHTML` 赋值用 `escapeHtml()` 包裹，满足 `test_no_innerhtml_without_escape`。**45 个新单元测试** 在 `test_season_projection.py` 跨 `TestComputeLeagueFormTable`（12）、`TestComputeFixtureDifficulty`（10）、`TestComputeSeasonProjection`（17）、`TestMissingColumns`（3）——覆盖空/None DataFrame、错误赛季/联赛/球队、字段存在性、排序、钳制（last_n/upcoming_n/num_simulations）、同 seed 决定性、概率和为 1、无输入 mutation、disclaimer 存在、自定义 team_strengths、relegation_slots=0。全部 45 个新测试通过；跨 7 个测试文件共 564 个测试通过；ruff clean；`node --check frontend/app.js` clean。用真实数据端到端验证：Premier League 2425 状态表（20 队）、Arsenal 赛程难度、赛季投影同 seed 可复现、2526 赛季投影（Arsenal 冠军概率 1.0 with 300 sims）。

- [x] **联赛动作分布层（League Action Distribution Layer）**（2026-07-15，Round 80）：3 个相互关联的描述性功能将 per-90 动作分解（Round 78-79）从球队层面提升到联赛层面，克隆 Round 74-75 的风格分布/演化模板（4 个风格合成指标扩展为 7 个细粒度动作特征），全部为非加性解释叠加，不修改预测模型。新增 `_build_team_action_profiles_full()` 辅助函数按 (team, season, league) 三元组分组（区别于 Round 79 的 `_build_team_action_profiles` 仅按 team 分组丢失时间/联赛上下文）：(1) **联赛动作分布图集**——`compute_league_action_atlas()` 在 `features/team_style.py` 对 7 个 `_ACTION_FEATURES`（tackles_p90 / interceptions_p90 / crosses_p90 / fouls_drawn_p90 / fouls_p90 / g_a_volume / npg_p90）的每一个计算直方图（n_bins 3-20，显式 `np.linspace` bin edges，min==max 时退化为单个 bin）、四分位数（Q1/median/Q3/IQR，`np.percentile`）和离群值（标准化维度上 z-score 绝对值 ≥ 2.0 的球队，按 |z| 降序，每项带 team/league/season/value/z_score/direction）。`GET /teams/action-atlas` 端点（season / league / n_bins 3-20 / min_player_minutes 参数，静态路由注册在 `{team}` 参数路由之前）。(2) **联赛动作演化**——`compute_league_action_evolution()` 按 season 分组计算每个动作的中位数和均值，跨赛季对每个动作通过 `_linear_slope_and_r2()`（n<2 保护）拟合最小二乘斜率。返回 per-season 汇总（season/n_teams/median/mean/std/min/max per action）和 per-dimension slope/delta/r_squared/evolution_label。需要 ≥2 个赛季，否则返回 `insufficient_seasons`。evolution_label 通过 `_drift_label()` 使用 5% 相对阈值（rising/falling/stable）。`GET /teams/action-evolution` 端点（league / min_player_minutes 参数）。(3) **跨联赛动作对比**——`compute_cross_league_action_comparison()` 按 league 分组计算每个联赛在 7 个动作上的 mean/median/std/min/max，然后按动作 mean 降序排列联赛并分配 `quality_tier`（top/middle/bottom，≤2 联赛时 top/bottom）。返回 `leagues` 汇总列表 + per-dimension `rankings` 列表。`GET /teams/cross-league-action` 端点（season / min_player_minutes 参数）。全部为非加性解释叠加，不修改预测模型、不预测比赛结果或排名联赛整体质量。**38 个新单元测试**：12 个 league_action_atlas（空输入/基本/action_features 列表/维度字段/n_bins/n_bins 钳制/联赛过滤/赛季过滤/min_minutes 过高/离群值检测/disclaimer/无 mutation/单队退化单 bin）+ 12 个 league_action_evolution（空输入/赛季不足/基本/维度字段/per_season 字段/action_features 列表/上升标签/下降标签/联赛过滤/disclaimer/无 mutation/min_minutes 过高）+ 14 个 cross_league_action（空输入/基本/联赛列表/联赛字段/维度排名/两联赛分层/排名降序/action_features 列表/赛季过滤/min_minutes 过高/disclaimer/无 mutation/单联赛）。新增 `_build_multi_season_action_df()` 测试 fixture 在基础 action_df 上扩展 2 个赛季（2425, 2324）并设置 rising-tackles / falling-fouls 模式以覆盖漂移标签。全部 334 个 team_style 测试通过（296 旧 + 38 新），ruff clean，node --check clean。前端 teams 视图新增 League Action Distribution & Cross-League 面板：联赛/赛季 2 个输入 + 按钮 + 3 个结果 div，3 个 fetch helper，1 个 init 函数（按钮 + 双输入 Enter 键，Promise.all 并行 render），3 个 render 函数（图集含 per-dimension 直方图条 + min/Q1/median/Q3/max/IQR 头 + 离群值 pill、演化含 per-dimension 斜率/Δ/R²/标签-pill 表 + 逐赛季中位值矩阵、跨联赛含 per-action 排名表含 rank/league/mean/median/teams/tier-pill）。2 个新 i18n 键（zh + en）。

- [x] **球队级动作签名层（Team-Level Action Signature Layer）**（2026-07-15，Round 79）：3 个相互关联的描述性功能将 Round 78 的 per-90 动作分解从位置组层面提升到球队层面，并克隆 Round 74 的联赛百分位模板（4 个风格合成指标扩展为 7 个细粒度动作特征），全部为非加性解释叠加，不修改预测模型：(1) **球队动作画像**——`compute_team_action_profile()` 在 `features/team_style.py` 复用 `_compute_position_action_stats()` 辅助函数（该函数是通用的，可作用于任意分组 DataFrame，不限于位置组）对每个球队计算 7 个 `_ACTION_FEATURES`（tackles_p90 / interceptions_p90 / crosses_p90 / fouls_drawn_p90 / fouls_p90 / g_a_volume / npg_p90）的分钟加权均值。`_build_team_action_profiles()` 辅助函数按 team 分组并对每个组应用分钟阈值过滤，`_pick_team_action_profile()` 实现大小写不敏感的球队查找。响应包含按 total_minutes 降序排列的 teams 列表和 `action_features` 列表。`GET /teams/action-profile` 端点（league / season / min_player_minutes 参数，静态路由注册在 `{team}` 参数路由之前）。(2) **联赛动作百分位**——`compute_league_action_percentiles()` 克隆 Round 74 的 `compute_league_style_percentiles` 模板，对目标球队的 7 个动作特征计算百分位（0-100，tie-handled average ranks: rank = count_below + 0.5 * count_equal, pct = 100 * rank / n_pop），附 quartile 标签（top ≥75 / upper_mid ≥50 / lower_mid ≥25 / bottom <25）和群体 min/median/max/mean。返回 target dict 含 action_values / population_means / population_stds。`GET /teams/{team}/action-percentiles` 端点（league / season / min_player_minutes 参数）。(3) **球队动作相似度**——`compute_team_action_similarity()` 对目标球队计算 7 维动作向量，按余弦相似度降序排列其他球队，附原始向量的欧氏距离作为参考。每个近邻包含 n_players 和 total_minutes 上下文。top_n 钳制到 max(1, min(int(top_n), len(neighbors)))。`GET /teams/{team}/action-similarity` 端点（league / season / top_n / min_player_minutes 参数）。全部为非加性解释叠加，不修改预测模型、不预测比赛结果或排名球队质量。**38 个新单元测试**：12 个 team_action_profile（空输入/基本/字段/action_features 列表/联赛过滤/赛季过滤/大小写不敏感/无动作列/disclaimer/无 mutation/min_minutes 过高/按分钟降序）+ 13 个 league_action_percentiles（空输入/缺失球队/球队未找到/基本/quartile 标签/百分位范围/群体统计/联赛过滤/赛季过滤/disclaimer/无 mutation/target 字段/两队群体）+ 13 个 team_action_similarity（空输入/缺失球队/球队未找到/基本/余弦范围/按余弦降序/排除自身/top_n/联赛过滤/目标向量/disclaimer/无 mutation/近邻字段）。全部 296 个 team_style 测试通过（258 旧 + 38 新），ruff clean，node --check clean。前端 teams 视图新增 Team Action 面板：联赛/赛季/球队 3 个输入 + 按钮 + 3 个结果 div，3 个 fetch helper，1 个 init 函数（按钮 + 3 输入 Enter 键，Promise.all 并行 render），3 个 render 函数（动作画像含球队/球员数/分钟 + 7 个动作列、动作百分位含动作/值/百分位/quartile-pill/min/median/max、动作相似度含目标动作向量 + cosine/distance/players/minutes 近邻表）。2 个新 i18n 键（zh + en）。

- [x] **位置组动作画像与趋势叠加（Per-Position-Group Action Profile & Trend Overlay）**（2026-07-15，Round 78）：3 个相互关联的描述性功能扩展位置组分析（Round 76-77）到细粒度 per-90 动作分解和跨赛季趋势标签维度，将 4 个风格合成指标（npg_p90/assists_p90/defense_composite/possession_composite）分解为 7 个细粒度 per-90 动作并加入跨赛季趋势标签：(1) **位置组动作画像**——`compute_position_action_profile()` 在 `features/team_style.py` 对每个标准位置组（GK/CB/FB/DM/CM/AM/W/ST，过滤低于 `min_player_minutes` 默认 500.0 的球员）计算 7 个 `_ACTION_FEATURES`（tackles_p90 / interceptions_p90 / crosses_p90 / fouls_drawn_p90 / fouls_p90 / g_a_volume / npg_p90）的分钟加权均值。响应中包含 `action_features` 列表和 `missing_positions`（无合格球员的位置组）。`GET /positions/action-profile` 端点（league / season / min_player_minutes 参数，静态路由注册在 `{position_group}` 参数路由之前）。(2) **基于动作的位置组相似度**——`compute_action_based_position_similarity()` 对目标位置组，计算所有位置组的 7 维动作向量，然后按余弦相似度降序排列其他位置组，附原始向量的欧氏距离作为参考。校验位置在 `_POSITION_GROUPS` 内（未知返回 `invalid_position`、数据缺失或低于分钟阈值返回 `position_not_found`）。返回 `target_action_vector` + `target_action_vector_labels` + `neighbors` 列表。`GET /positions/{position_group}/action-similarity` 端点（league / season / min_player_minutes 参数）。(3) **位置组趋势叠加**——`compute_position_trend_overlay()` 对每个标准位置组计算 `_TREND_FEATURES`（npg_trend / def_trend / pos_trend，评分管线的跨赛季提升指标）的分钟加权均值，并为每个维度分配 `trend_label`（improving >0.05 / declining <-0.05 / stable |val|<0.05）。返回 per-position-group 的 `dimensions` 列表，每项含 feature/value/trend_label。`GET /positions/trend-overlay` 端点（league / season / min_player_minutes 参数，静态路由注册在 `{position_group}` 参数路由之前）。全部为非加性解释叠加，不修改预测模型、不预测未来趋势或排名位置质量。**37 个新单元测试**：12 个 action_profile（空输入/基本/字段/action_features 列表/missing_positions/联赛过滤/赛季过滤/大小写不敏感/无动作列/disclaimer/无 mutation/min_minutes 过高）+ 13 个 action_similarity（空输入/无效位置/位置未找到/基本/目标向量/余弦降序/排除自身/近邻字段/大小写不敏感/联赛过滤/赛季过滤/disclaimer/无 mutation）+ 12 个 trend_overlay（空输入/基本/提升标签/下滑标签/稳定标签/维度结构/missing_positions/联赛过滤/赛季过滤/无趋势列/disclaimer/无 mutation）。全部 258 个 team_style 测试通过（221 旧 + 37 新），ruff clean，node --check clean。前端 teams 视图新增 Position Action Profile & Trends 面板：联赛/赛季/位置 3 个输入 + 按钮 + 3 个结果 div，3 个 fetch helper，1 个 init 函数（按钮 + 3 输入 Enter 键，Promise.all 并行 render），3 个 render 函数（动作画像含位置/球员数/分钟 + 7 个动作列 + missing positions、动作相似度含目标动作向量 + cosine/distance/players 近邻表、趋势叠加含位置/球员数 + 3 个趋势维度含 value + improving/declining/stable status-pill）。2 个新 i18n 键（zh + en）。

- [x] **位置组深度画像与跨联赛对比（Per-Position-Group Depth Profile & Cross-League Comparison）**（2026-07-15，Round 77）：3 个相互关联的描述性功能扩展位置组风格分析（Round 76）到阵容深度画像、跨联赛质量对比和球队级缺口报告维度：(1) **位置组深度画像**——`compute_position_depth_profile()` 在 `features/team_style.py` 对每个标准位置组（GK/CB/FB/DM/CM/AM/W/ST，过滤低于 `min_player_minutes` 默认 500.0 的球员）计算 n_players、total_minutes、分数分布（min/median/max/mean/std/p25/p75）、分钟分布（median/mean）、分钟加权风格均值（attack/creation/defense/possession）和 depth_label（shallow <2 / adequate 2-3 / deep ≥4）。无球员的位置组列入 `missing_positions`。`GET /positions/depth-profile` 端点（league / season / min_player_minutes 参数，路由注册在 `{position_group}` 参数路由之前）。(2) **跨联赛位置组对比**——`compute_cross_league_position_comparison()` 对目标位置组按联赛分组计算深度统计，按 mean score 降序排列，分配 quality_tier（top/middle/bottom，≤2 联赛时 top/bottom）。校验位置在 8 个标准组内（未知返回 `invalid_position`、数据缺失返回 `position_not_found`）。`GET /positions/{position_group}/cross-league` 端点（season / min_player_minutes 参数）。(3) **球队位置缺口报告**——`compute_position_gap_report()` 对目标球队计算 per-position-group 深度统计，与联赛 p40/p60 百分位对比识别缺口（shallow <2 球员 / low_quality mean < p40 / missing 无球员）和优势（deep ≥4 球员且 mean ≥ p60）。球队未找到返回 `team_not_found`。`GET /teams/{team}/position-gap-report` 端点（season / min_player_minutes 参数）。全部为非加性解释叠加，不修改预测模型或推荐转会。**39 个新单元测试**：12 个 depth_profile（空输入/无 position 列/基本/字段/depth 标签/missing_positions/联赛过滤/赛季过滤/大小写不敏感/分数分布/disclaimer/无 mutation/min_minutes 过高）+ 13 个 cross_league（空输入/无效位置/位置未找到/基本/均值降序/质量分层/字段/PL vs La Liga/大小写不敏感/赛季过滤/disclaimer/无 mutation）+ 14 个 gap_report（空输入/球队未找到/基本/shallow 缺口/missing 位置/low_quality 缺口/deep 优势/adequate 无缺口无优势/字段/gap 字段/大小写不敏感/赛季过滤/disclaimer/无 mutation）。全部 221 个 team_style 测试通过（182 旧 + 39 新），ruff clean，node --check clean。前端 teams 视图新增 Position Depth 面板：联赛/赛季/位置/球队 4 个输入 + 按钮 + 3 个结果 div，3 个 fetch helper，1 个 init 函数（按钮 + 4 输入 Enter 键，Promise.all 并行 render），3 个 render 函数（深度画像含位置/球员数/mean/median/range/σ/attack/defense/depth_label pill + missing positions、跨联赛对比含 rank/league/players/mean/median/attack/defense/quality_tier pill + best/worst league + score_spread、缺口报告含 gap/strength summary cards + gap positions 表 + strength positions 表）。2 个新 i18n 键（zh + en）。

- [x] **位置组风格演化（Per-Position-Group Style Evolution）**（2026-07-15，Round 76）：3 个相互关联的描述性功能扩展球队风格漂移分析（Round 75）到位置组维度，复用 rating matrix 的 position_group 列（GK/CB/FB/DM/CM/AM/W/ST）：(1) **位置组风格演化**——`compute_position_style_evolution()` 在 `features/team_style.py` 对每个有 ≥2 赛季分钟加权聚合（过滤低于 `min_player_minutes` 默认 500.0 的球员）的标准位置组，跨赛季对 4 个风格维度（npg_p90/assists_p90/defense_composite/possession_composite）拟合最小二乘斜率。返回 per-position-group 块含 per-dimension slope/delta/r_squared/mean/evolution_label（rising/falling/stable，5% 相对阈值）/per_season（含 n_players）。赛季数 <2 的位置组列入 `skipped_positions`。`GET /positions/style-evolution` 端点（league / min_player_minutes 参数）。(2) **单位置组风格漂移**——`compute_position_style_drift()` 对单个位置组跨赛季计算同样的 slope/delta/r_squared/drift_label/per_season。校验位置在 8 个标准组内（未知返回 `invalid_position`、数据缺失返回 `position_not_found`、<2 赛季返回 `insufficient_seasons`）。`GET /positions/{position_group}/style-drift` 端点。(3) **位置组漂移近邻**——`compute_position_style_drift_neighbors()` 为每个有 ≥2 赛季的位置组计算 4 维漂移向量（每维斜率），按余弦相似度降序排列其他位置组，附欧氏距离。`GET /positions/{position_group}/style-drift-neighbors` 端点。全部为非加性解释叠加，不修改预测模型或排名位置质量。**42 个新单元测试**：12 个 evolution（空输入/无 position 列/基本/skipped_positions/维度字段/逐赛季 n_players/赛季排序/ST 上升标签/CB 防守上升/CM 稳定/联赛过滤/disclaimer/无 mutation）+ 16 个 drift（空输入/无 position/无效位置/位置未找到/赛季不足/基本/维度字段/逐赛季排序/上升标签/下降标签/稳定标签/大小写不敏感/联赛过滤/逐赛季 n_players/disclaimer/无 mutation）+ 14 个 drift_neighbors（空输入/无 position/无效位置/位置未找到/基本/相似度降序/排除自身/相似度范围/漂移向量/GK 靠近 ST/n_candidates/大小写不敏感/联赛过滤/disclaimer/无 mutation）。全部 182 个 team_style 测试通过（138 旧 + 42 新 + 2 fixture），ruff clean，node --check clean。前端 teams 视图新增 Position Style 面板：位置/联赛输入 + 按钮 + 3 个结果 div，3 个 fetch helper，1 个 init 函数（按钮 + 双输入 Enter 键，Promise.all 并行 render），3 个 render 函数（演化含 per-position-group 维度表 + 逐赛季值 + skipped positions、漂移轨迹含 per-dimension 斜率/Δ/R²/标签 pill + 逐赛季值含 n_players、漂移近邻含相似度百分比/距离/n_seasons + 目标漂移向量）。2 个新 i18n 键（zh + en）。

- [x] **跨赛季风格漂移（Cross-Season Style Drift）**（2026-07-15，Round 75）：3 个相互关联的描述性功能扩展球队风格分析（Round 71-74）到跨赛季时间维度：(1) **单队风格漂移轨迹**——`compute_team_style_drift()` 在 `features/team_style.py` 对目标球队的 4 个风格维度（npg_p90/assists_p90/defense_composite/possession_composite）跨赛季计算最小二乘斜率、净变化 delta（最新 - 最早）、R² 一致性分数和逐赛季值，并附 drift_label（rising/falling/stable，5% 相对阈值）。需要至少 2 个赛季的画像。`GET /teams/{team}/style-drift` 端点（league / min_minutes_total 参数）。(2) **联赛风格演化**——`compute_league_style_evolution()` 在 `features/team_style.py` 按赛季分组计算每个风格维度的中位数和均值，再跨赛季拟合斜率，输出 per-season 汇总（n_teams/median/mean/std/min/max）和 evolution_label。`GET /teams/style-evolution` 端点（league / min_minutes_total 参数）。(3) **风格漂移近邻**——`compute_style_drift_neighbors()` 在 `features/team_style.py` 为每个有 ≥2 赛季的球队计算 4 维漂移向量（每维斜率），按余弦相似度降序排列其他球队，附欧氏距离。`GET /teams/{team}/style-drift-neighbors` 端点（league / top_n 1-50 / min_seasons ≥2 / min_minutes_total 参数）。全部为描述性叠加，不预测未来风格或排名球队质量。**36 个新单元测试**：13 个 drift（空输入/球队未找到/赛季不足/基本/维度字段/逐赛季排序/上升标签/下降标签/稳定标签/大小写不敏感/联赛过滤/disclaimer/无 mutation）+ 9 个 evolution（空输入/赛季不足/基本/per_season 字段/维度字段/赛季排序/联赛过滤/disclaimer/无 mutation）+ 14 个 drift_neighbors（空输入/球队未找到/赛季不足/基本/相似度降序/top_n cap/top_n 钳制/大小写不敏感/排除自身/相似度范围/漂移向量/Riser2 最近邻/disclaimer/无 mutation）。全部 138 个 team_style 测试通过（101 旧 + 36 新 + 1 fixture），ruff clean，node --check clean。前端 teams 视图新增 Style Drift 面板：球队/联赛/近邻数输入 + 一键并行触发三个 render（漂移轨迹含 per-dimension 斜率/Δ/R²/标签 pill + 逐赛季值、联赛演化含中位/均值斜率表 + 逐赛季中位值矩阵、漂移近邻含相似度表 + 目标漂移向量）。2 个新 i18n 键（zh + en）。

- [x] **联赛风格图集（Style Atlas）**（2026-07-15，Round 74）：3 个相互关联的描述性功能扩展球队风格聚类（Round 71-73）到联赛级分布视图：(1) **风格近邻**——`compute_style_neighbors()` 在 `features/team_style.py` 对所有球队风格画像（分钟加权 4 维 npg_p90/assists_p90/defense_composite/possession_composite）相对联赛群体标准化，按余弦相似度降序排列其他球队，附带标准化向量的欧氏距离。当聚类成功时，每个近邻带 cluster_id / cluster_label / same_cluster 标记，目标球队的簇上下文也一并返回。`GET /teams/{team}/style-neighbors` 端点（season / league / top_n 1-50 / n_clusters 2-8 / min_minutes_total 参数）。(2) **联赛百分位**——`compute_league_style_percentiles()` 在 `features/team_style.py` 计算目标球队在 4 个风格维度上的百分位（0-100，平均排名处理 ties），并附 quartile 标签（top/upper_mid/lower_mid/bottom）和群体 min/median/max/mean。`GET /teams/{team}/style-percentiles` 端点。(3) **联赛风格图集**——`compute_style_atlas()` 在 `features/team_style.py` 为每个风格维度生成直方图（n_bins 3-20，显式 bin edges）、四分位数（Q1/median/Q3/IQR）和离群值（|z|≥2.0 的球队，按 z 绝对值降序）。`GET /teams/style-atlas` 端点。全部为描述性叠加，不预测比赛结果或排名球队质量。**34 个新单元测试**：16 个 neighbors（空输入/球队未找到/基本/排序/top_n cap/top_n 钳制/大小写不敏感/target 画像/簇上下文/同簇标记/距离非负/相似度范围/disclaimer/无 mutation/season 过滤）+ 10 个 percentiles（空输入/球队未找到/基本/百分位范围 0-100/quartile 标签/进攻高分/群体统计/大小写不敏感/disclaimer/无 mutation）+ 10 个 atlas（空输入/基本/维度字段/直方图总数/n_bins 钳制/离群值 z-score/四分位一致性/season 过滤/disclaimer/无 mutation）。前端 teams 视图新增 Style Atlas 面板：球队/赛季/联赛/近邻数输入 + 一键并行触发三个 render（近邻表、百分位表含进度条、图集含直方图和离群值 pill）。8 个新 i18n 键（zh + en）。

- [x] **战术风格碰撞诊断套件**（2026-07-15，Round 73）：2 个相互关联的诊断功能，把球队风格聚类（Round 71-72）接入比赛预测视图：(1) **簇间相似度矩阵**——`compute_cluster_similarity_matrix()` 在 `features/team_style.py` 复用 `compute_team_style_clusters()` 获得簇质心，计算 N×N 余弦相似度矩阵（对称、对角线为 1.0），并附带上三角 `pairs` 列表（按相似度降序），每对带启发式 clash 标签（similar ≥0.75 / complementary ≥0.25 / contrasting <0.25）。`GET /teams/style-clusters/similarity` 端点（season / league / n_clusters 2-8 / min_minutes_total 参数）。前端 teams 视图在簇表下方新增 ECharts 热力图（簇 A × 簇 B，颜色从红→黄→绿映射 -1 到 1）+ 簇对表（簇A/簇B/相似度/关系 status-pill）。(2) **比赛风格碰撞诊断**——`compute_style_matchup()` 在 `features/team_style.py` 计算两支球队的分钟加权风格画像，相对联赛群体标准化，输出：per-dimension 优势判定（home/away/even，使用 0.15σ 阈值）、整体风格距离（标准化向量欧氏距离）、比赛剧本分类（asymmetric/open_game/defensive_battle/possession_duel/balanced，基于双方标准化向量的进攻/防守/控球方向），以及可选的簇上下文（home_cluster/away_cluster/cluster_similarity/cluster_clash）。**严格非加性解释叠加**：明确不修改 Dixon-Coles/Poisson 概率模型，胜负概率仍是唯一真值来源。`GET /teams/style-matchup` 端点（home_team / away_team / season / league / n_clusters / min_minutes_total 参数）。前端 matches 视图在势头面板后新增风格碰撞面板：双方风格画像快照（进攻/创造/防守/控球原始值）+ 风格距离和比赛剧本 pill（按剧本类型着色）+ 维度对比表（维度/主队/客队/Δσ/优势 status-pill）+ 簇上下文块（同簇/相似/互补/对立）+ 非加性 disclaimer。**27 个新单元测试**：9 个 similarity_matrix（空输入/基本/对角线为 1/对称/值域/上三角 pairs/pairs 字段/insufficient_teams/disclaimer/无 mutation）+ 12 个 style_matchup（空输入/球队未找到/基本/维度字段/大小写不敏感/进攻 vs 防守优势/风格距离非负/比赛剧本值/画像含原始和标准化值/簇上下文/同簇相似度/disclaimer/无 mutation）。全部 67 个 team_style 测试通过，ruff clean，node --check clean。前端：2 个新 HTML 面板、2 个 fetch 函数、2 个 render 函数（含 ECharts 热力图）、8 个新 i18n 键（zh + en）。

- [x] **球员上升/下滑观察 + 球队风格聚类 + 球探报告职业轨迹**（2026-07-14，Round 71）：3 个相互关联的球探洞察：(1) **Riser/Decliner watchlist**——`compute_riser_decliner_watchlist()` 在 `player_intel.py` 扫描完整 rating matrix 寻找处于最陡上升或下降职业轨迹的球员。使用 `optimized_score` 对赛季索引的**最小二乘斜率**（`np.polyfit(x, y, 1)[0]`）作为核心信号，过滤最少 2 个赛季且最新赛季 ≥300 分钟的球员；risers 按斜率降序、decliners 按斜率升序排列。`GET /scouting/risers-decliners` 端点支持 season / top_n / riser_threshold / decliner_threshold / min_seasons / min_minutes_latest 查询参数。前端 scouting 视图新增双栏面板：risers（绿色表头）和 decliners（红色表头）各自显示球员/球队/位置/评分/Δ 列，Δ 列用 status-pill 着色显示轨迹斜率。(2) **球队风格聚类**——新模块 `features/team_style.py` 将球员级风格组合特征（`npg_p90`/`assists_p90`/`defense_composite`/`possession_composite`）按分钟加权聚合到 team-season 级别（复用 `get_team_strength` 的 minutes-weighted aggregation 模式），然后对标准化特征运行 **k-means 聚类**（lazy sklearn import、空/退化数据防御性处理）。启发式簇标签（attacking/defensive/possession-heavy/counter-attacking/creative/direct/open/low-scoring/balanced）基于每个质心中主导特征方向推导。`GET /teams/style-clusters` 端点支持 season / league / n_clusters（2-8）/ min_minutes_total 参数。前端 teams 视图新增面板：ECharts 散点图（X=npg_p90，Y=defense_composite，按簇着色）+ 簇汇总表（cluster_id/label/n_teams/teams 列）。返回 status 包含 ok/insufficient_teams/sklearn_unavailable/no_data 防御状态。(3) **职业轨迹接入球探报告导出**——`exportPlayerScoutingReportCSV()` 从 8 节扩展到 9 节，新增第 9 节包含职业轨迹指标（n_seasons/career_avg_score/peak_score/trajectory_slope/score_consistency_std/career_minutes_total）和逐赛季弧线表（season/team/league/position_group/score/minutes/npg_p90/assists_p90）。JSON 导出自动包含新字段。**33 个新单元测试**：14 个 riser/decliner（空输入/基本分类/斜率方向/单赛季排除/低分钟排除/平球员排除/字段完整性/排序/top_n cap/n_scanned 计数/自定义阈值/disclaimer/无 mutation/thresholds 回显），19 个 team-style（profiles 6 + clusters 13：基本/可复现/n_clusters 边界/insufficient_teams/sklearn_unavailable/cluster 字段/cluster_id 分配/disclaimer/feature stats/排序/无 mutation/sequential IDs/season 过滤）。全部 1944 单元测试通过，ruff clean，node --check clean。前端：2 个新 HTML 面板、2 个 fetch 函数、2 个 render 函数（含 ECharts 散点图）、2 个 init 函数（含 Enter 键支持）、26 个新 i18n 键（zh + en）。

- [x] **球员职业智能套件 + 角色匹配启发式修复**（2026-07-14，Round 70）：4 个相互关联的功能 + 1 个关键 bug 修复：(1) `compute_career_trajectory()` 在 `player_intel.py`——完整职业弧线分析取代旧的 3 赛季趋势：peak 检测（满足 900 分钟下限的最佳赛季，回退到最高分赛季）、development phase 标签（prospect/prime/decline 相对 peak ±1 赛季）、year-over-year deltas、position transitions、career 汇总指标（n_seasons/career_avg/peak/min/max/consistency_std/trajectory_slope/career_minutes_total）。空输入返回带 disclaimer 的空轨迹，不伪造缺失赛季。(2) `compute_role_fit_scores()` 在 `player_intel.py`——**5 次迭代修复 Bellingham→CB 98.0 的角色匹配 bug**。最终方案：球员 z-score 向量与**位置质心**（该位置所有球员的均值 z 向量，相对整体 rated 群体 z-score）的**余弦相似度**，映射到 0–100。只使用 4 个角色区分特征（`npg_p90`/`assists_p90`/`defense_composite`/`possession_composite`），排除 `optimized_score` 和 `minutes`（质量/可用性维度会让精英球员在每个位置都高分）。使用等权重而非 per-position 权重（质心已编码位置画像，零权重特征会在欧氏距离中被静默丢弃）。样本 <5 时返回 `insufficient_samples` 置信度。验证：Bellingham→AM(97.0)、Haaland→ST(98.4)、Alisson→GK(99.9)、De Bruyne→AM(99.5)、van Dijk→GK(92.2)/CB(86.2)。(3) `compute_peer_benchmark()` 在 `player_intel.py`——按位置 + 联赛 tier + 分钟档分组（无年龄依赖，因 rating matrix 无可靠出生年份），返回 percentile rank、与组均值的 delta、组样本量。(4) `compute_pairwise_similarity()` 在 `player_intel.py`——多人对比的相似度矩阵，复用 `find_similar_players` 的 z-score 余弦距离。API 层：4 个新 GET 端点含 5 分钟 TTL 缓存：`GET /players/{name}/career`、`GET /players/{name}/role-fit`、`GET /players/{name}/peer-benchmark`、`GET /players/compare?names=`。前端：4 个新面板含 ECharts 折线图（职业轨迹）、雷达图（角色匹配）、柱状图（peer benchmark）、热力图（相似度矩阵）、完整 zh/en i18n。Bug 修复：3 个 `innerHTML = ` 模板字符串改为 `[...].join("")` 模式以满足前端安全测试（test_no_innerhtml_without_escape）。32 个新单元测试覆盖 model 函数、API 缓存和边界情况。ruff clean、node --check clean、32 个 player_intel 测试通过。

- [x] **回测评分卡 + 预测异常检测 + 球队表现档案**（2026-07-14，Round 69）：3 个相互关联的功能：(1) `compute_backtest_report_card()` 在 `backtests.py`——6 维度评分卡评估整体回测质量：accuracy（25%）、calibration（20%）、discrimination（20%）、sharpness（15%）、confidence_alignment（10%）、stability（10%）。每个维度返回 0–100 分数、权重和评估标签；总分=加权平均，通过 `_grade_from_score()` 映射到 A/B/C/D/F 字母等级。stability 使用时间拆分半比较（早期 vs 晚期 by `match_date`）惩罚漂移。`_assessment_from_grade()` 提供人类可读的总结。(2) `compute_prediction_anomalies()` 在 `backtests.py`——检测 5 种异常类型：`high_entropy`（Shannon entropy ≥ 阈值，默认 0.95）、`overconfident_wrong`（高置信但错误）、`underconfident_correct`（低置信但正确）、`outlier_confidence_high`（conf ≥ 0.95）、`outlier_confidence_low`（conf < 0.10）。每个异常按置信度和正确性分严重等级（critical/high/medium/low）。可配置阈值（`high_entropy_threshold`、`overconfidence_threshold`、`underconfidence_threshold`、`outlier_high_threshold`、`outlier_low_threshold`、`max_anomalies`）。(3) `compute_team_performance_profile()` 在 `backtests.py`——单队表现档案含主客场拆分、overperformer/underperformer/aligned 分类（实际 vs 预测胜率）、常见比分（Top 5 按频率）、最差预测（最高 Brier）、最佳预测（正确中最低 Brier）。少于 `min_matches`（默认 5）返回 None。API 层：3 个新 GET 端点含 5 分钟 TTL 缓存、DC-decay fallback Poisson、`actual_outcome` 合成：`GET /predictions/calibration/report-card`、`GET /predictions/calibration/anomalies`（6 个 Query 参数）、`GET /predictions/calibration/team-profile`（team, top_n, min_matches）。前端：3 个新面板含 ECharts 雷达图（6 维度评分卡）和饼图（异常严重性分布）、完整 zh/en i18n（各 ~80 键）、球队档案文本输入框支持 Enter 键。48 个新单元测试覆盖 model 函数、API 缓存、边界情况和阈值校验。ruff clean、node --check clean、1814 测试通过（0 失败）。

- [x] **回测交互可视化 + 预测连胜分析**（2026-07-14，Round 68）：4 个相互关联的功能：(1) 预测连胜分析——`compute_prediction_streaks()` 在 `backtests.py` 追踪连续正确/错误预测，按置信度阈值分类中断类型（upset=高置信错误、recovery=低置信正确、neutral=中等置信），报告最长连胜/连败、中断率、时间线；`get_prediction_streaks()` API + `GET /predictions/calibration/streaks` 端点含 5 分钟 TTL 缓存和 DC-decay fallback；(2) 可靠性图增强——`compute_reliability_diagram()` 新增 MCE（最大校准误差）、calibration_slope/intercept、per_outcome_calibration（每个 outcome 独立的 slope/intercept/n_bins）、n_bins_used/n_predictions；(3) 5 个 ECharts 交互可视化——temporal validation（双 Y 轴折线图：左轴 Brier/RPS/LogLoss，右轴准确率/置信度）、probability heatmap（home_bin × away_bin 矩阵 + visualMap 颜色映射准确率）、CI plot（散点图按正确/错误分色）、feature importance（Top 15 水平柱状图 + LinearGradient）、drift heatmap（时间窗口 × 置信度分桶 + Brier 颜色映射）；(4) 连胜分析前端面板——统计卡片网格（n_matches/current streak/longest/break rates/avg lengths）+ 双 Y 轴组合图（柱状图正=正确连胜负=错误连胜 + 折线图置信度 + markPoint 标记 upset/recovery 中断）。32 个新单元测试覆盖连胜计算（20 tests：字段/长度递增/upset/recovery/neutral 分类/中断率/max_points 截断/空 df/缺失列/无效阈值/match_date 排序/actual_outcome 合成/None outcome/可复现）、API（5 tests：not_available/ok/actual 合成/缓存/自定义阈值）、可靠性图增强（7 tests：MCE/slope/intercept/per_outcome/n_bins_used/MCE≥ECE/完美校准 slope≈1/单桶 fallback）。

- [x] **对阵图分享/导入 + 打印/PDF 导出套件**（2026-07-12，Round 13）：2 个相互关联的功能：(1) 锦标赛状态导出/导入——`export_wc_tournament_state()` 在 `api.py` 将完整 TournamentState（matches + results + knockout）序列化为 JSON 后用 base64url 编码，返回 `format`/`schema_version`/`state_size`/`encoded`/`exported_at` 元数据；`import_wc_tournament_state(encoded)` 在 `api.py` 解码 base64url JSON、验证 schema 版本（必须 1.x）、重建 TournamentState 并持久化到 `DEFAULT_STATE_PATH`，自动处理缺失的 base64 padding，无效输入返回 `decode_failed`/`invalid_state` 错误码；`GET /world-cup/tournament/export` + `POST /world-cup/tournament/import` 端点；前端对阵图面板新增"分享"按钮（导出编码字符串→显示在只读 textarea 含复制和下载 JSON 按钮）和"导入"按钮（textarea 粘贴编码 + 从文件加载 + 导入后自动刷新所有锦标赛数据）；(2) 对阵图打印/PDF 导出——`@media print` CSS 规则在 `style.css`：A4 横向、1cm 边距、隐藏所有非对阵图内容（`body * { visibility: hidden }` + `#wc-ko-bracket-panel * { visibility: visible }`）、展开水平滚动容器、白底黑字打印友好配色、隐藏按钮和输入框、`page-break-inside: avoid` 防止比赛卡片跨页断裂、打印专属标题 header；前端新增"🖨"打印按钮调用 `window.print()`。19 个单元测试覆盖导出（ok 状态/必需字段/base64url 格式/编码可解码/schema 版本匹配/状态大小匹配/含 72 场比赛/含结果/含对阵图）和导入（导出→导入 round-trip/持久化到磁盘/返回比赛数/返回 schema 版本/无效 base64 错误/无效 JSON 错误/不兼容 schema 错误/空字符串错误/含对阵图 round-trip/无 padding 兼容）。全部 97 个淘汰赛相关测试通过，ruff + node --check 通过。

- [x] **淘汰赛情景分析 + 小组赛批量模拟器套件**（2026-07-12，Round 12）：2 个相互关联的功能：(1) `compute_knockout_scenarios()` 在 `worldcup/data.py`——给定淘汰赛对阵图概览、球队实力 dict 和指定球队，计算该球队在每个淘汰赛阶段的夺冠概率变化（当前基线 + "若赢得下一场"的条件概率 + 后续轮次若到达的投影概率），使用蒙特卡洛模拟（默认 5000 次，可复现种子）和 `force_winner` 参数强制指定球队在特定比赛获胜，重新模拟其余比赛推导条件夺冠概率；自动检测已淘汰球队（在完赛比赛中失利）返回 0 概率和空场景列表，未在对阵图中的球队返回 error 状态；辅助函数 `_mc_championship_probability()` 支持强制胜者参数用于条件分析；(2) `simulate_group_stage()` 在 `worldcup/data.py`——批量模拟所有未完赛的小组赛比赛（random 模式均匀 1/3 胜/平/负，strength 模式用 Bradley-Terry 加权 + 28% 平局基线），每次模拟后计算完整积分表和晋级球队，统计每队的晋级概率和小组第一概率，返回最可能小组第一列表（12 组各一个）和全 48 队的晋级概率排序；无剩余比赛时返回确定性结果；(3) `get_wc_knockout_scenarios(team)` API + `GET /world-cup/tournament/knockout/scenarios/{team}` 端点 + `get_wc_group_stage_simulation(mode, num_simulations)` API + `GET /world-cup/tournament/group-simulation` 端点；(4) 前端锦标赛视图新增"小组赛模拟器"面板（模式选择 random/strength + 模拟次数选择 500/1000/3000 + 模拟按钮 + 最可能小组第一 pills + Top 20 出线概率条形图含颜色编码）和淘汰赛对阵图面板新增"夺冠情景分析"功能（球队下拉框从 R32 填入球队动态生成 + 分析按钮 + 场景表格显示每轮对手/胜率/夺冠若胜概率 + 可关闭的覆盖面板）。21 个单元测试覆盖淘汰赛情景（无对阵图/未在对阵图/有对阵图返回场景/next_match 含对手和胜率/等实力 50-50/夺冠若胜≥基线/夺冠若负=0/可复现种子/disclaimer/字段完整性/已淘汰球队返回 0）和小组赛模拟器（无剩余比赛确定性/random 模式/strength 模式/概率范围/最可能小组第一覆盖 12 组/可复现种子/disclaimer/实力模式偏好强队/全 48 队在列表中/概率与频率一致）。全部 72 个淘汰赛相关测试通过，ruff + node --check 通过。

- [x] **锦标赛投影集成与静态快照导出套件**（2026-07-12，Round 11）：3 个相互关联的功能：(1) `project_knockout_probabilities()` 在 `worldcup/data.py`——接收 `get_knockout_overview()` 的对阵图概览和球队实力 dict，为每场双方已填入且未完赛的比赛用 Bradley-Terry 模型（`_knockout_match_prob`）计算 home/away 胜率，完赛比赛返回已知胜者概率 1.0/0.0，TBD 比赛返回 None；当所有 R32 比赛双方已填入时，运行蒙特卡洛模拟（默认 10000 次，可复现种子），模拟中尊重已完赛比赛的已知胜者，推导各队夺冠概率并按降序排列返回 Top 16；(2) `get_wc_knockout_probabilities()` API + `GET /world-cup/tournament/knockout/probabilities` 端点——从当前 tournament state 读取对阵图概览，使用 `_get_wc_enriched_squads()` 获取球队实力，调用投影函数返回 per-match 胜率和夺冠赔率，无对阵图时返回 error 状态含指引；(3) 静态锦标赛快照导出——`export_static_frontend_data.py` 的 `export_worldcup()` 新增 `tournament_summary.json`（调用 `get_wc_tournament_summary()`）和 `knockout_bracket.json`（调用 `get_wc_knockout_bracket()`）用于 API 不可用时的离线 fallback；前端新增 `fetchWcKnockoutProbabilities()` 函数自动获取投影数据，对阵图面板新增夺冠概率表（Top 8 球队带进度条）和 per-match 胜率条（ready-for-input 卡片下方显示 home% vs away% 双色条），apply/clear/generate 操作后自动失效缓存并重新获取。12 个单元测试覆盖无对阵图、per-match 胜率（31 场/R32 填入/后续轮 TBD）、等实力 50-50、强弱偏差、完赛已知胜者、夺冠概率（蒙特卡洛/尊重已完赛/可复现种子/disclaimer/字段完整性/无 R32 时不计算）。全部 1300+ 单元测试通过，ruff + node --check 通过。
- [x] **世界杯淘汰赛对阵图套件**（2026-07-12，Round 10）：5 个相互关联的功能：(1) `scoutfootball.worldcup.tournament` 淘汰赛阶段引擎扩展——`TournamentState.knockout` 字段 + `knockout_match_by_id()` 方法，`KNOCKOUT_ROUNDS` 常量定义 5 轮（R32 16 场→R16 8 场→QF 4 场→SF 2 场→Final 1 场=31 场），`_seed_knockout_r32()` 按 12 小组第一（按积分/GD/GF 排序）配对 12 小组第二（互补顺序强对弱）+ 4 场剩余配对最佳第三名 vs 最强剩余第二，`_build_knockout_rounds()` 构建 31 场比赛（R32 填入球队，后续轮次 home/away=None 含 "Winner R32-01" 种子标签），`generate_knockout_bracket()` 从 `determine_advancing_teams()` 生成完整对阵图含 provisional 标志和 champion=None，`apply_knockout_result()` 记录比分判定胜负（平局需 `penalties_winner`，支持 `decided_by` 为 regular/penalties），`_advance_winner()` 自动将胜者填入下一轮 home（奇数位置）或 away（偶数位置）slot，`clear_knockout_result()` + `_cascade_clear_downstream()` 递归清空依赖该胜者的下游比赛，`get_knockout_overview()` 返回 generated/provisional/champion/current_round/completed_matches/total_matches/rounds 摘要，`state_to_dict`/`state_from_dict` 序列化 knockout 字段，`reset_state()` 清空 knockout；(2) `scoutfootball tournament knockout` CLI 含 4 个子命令（generate/show/apply/clear）支持 `--state-path`/`--json`/`--penalties-winner`，show 按轮分组显示比分和胜者；(3) 4 个 FastAPI 端点（`GET /world-cup/tournament/knockout`、`POST /world-cup/tournament/knockout/generate`、`POST /world-cup/tournament/knockout/result`、`DELETE /world-cup/tournament/knockout/result`）写操作持久化到 DEFAULT_STATE_PATH；(4) 前端"锦标赛"视图新增淘汰赛对阵图面板——"Generate Bracket"按钮、横向滚动轮次列布局、champion 横幅、provisional 标志、比赛卡片三态（completed 显示比分+胜者+clear 按钮 / not-ready 显示 TBD 灰色 / ready-for-input 显示比分输入框+apply 按钮）；(5) 39 个单元测试覆盖生成（31 场/轮次计数/provisional/R32 填入/后续轮 TBD/champion=None）、apply（主客胜/平局需点球/点球胜/无效点球胜者/负比分/重复结果/未找到/无对阵图/自动晋级/home-away slot）、clear（清除/级联清除下游/无结果拒绝/清除决赛清除冠军）、完整锦标赛进程（31 场完成/冠军产生/R16 填入）、overview（无对阵图/已生成/当前轮推进/rounds 结构）、持久化（state_to_dict/round-trip/空 knockout）、reset、match ID 唯一性和格式。全部 1300+ 单元测试通过，ruff + node --check 通过。
- [x] **世界杯锦标赛模拟器套件**（2026-07-12）：5 个相互关联的功能：(1) `scoutfootball.worldcup.tournament` 纯 Python 锦标赛状态引擎（48 队 12 组 72 场小组赛，`TournamentState`/`GroupStanding`/`TeamScenarios` dataclass，`init_state`/`apply_result`/`clear_result`/`reset_state`/`compute_group_standings` 含完整 FIFA 平局规则——积分→净胜球→进球→H2H 积分→H2H 净胜球→H2H 进球，仅在所有平局球队互赛完成时才应用 H2H，`compute_best_thirds` 跨 12 组排名前 8 第三名，`determine_advancing_teams` 12 小组第一+12 小组第二+8 最佳第三名=32 强含 provisional 标志，`compute_team_scenarios` 枚举剩余赛程排列并报告晋级概率，`state_to_dict`/`state_from_dict`/`save_state`/`load_state` 含 `SCHEMA_VERSION=1.0.0` 持久化，默认路径 `data/reports/worldcup/tournament_state.json`）；(2) `scoutfootball tournament` CLI 含 7 个子命令（show/standings/apply/clear/reset/scenarios/matches）支持 `--state-path`/`--json`/`--group`/`--pending`/`--force`；(3) 7 个 FastAPI 端点 `/world-cup/tournament/*`（summary/standings/matches/scenarios/result POST/result DELETE/reset），写操作持久化到 DEFAULT_STATE_PATH；(4) 前端"锦标赛"视图含小组选择器、实时积分表、比分录入表单（apply/clear）、晋级球队面板（含 provisional 标志）、出线情景面板，中英双语 i18n；(5) 57 个单元测试覆盖 init/apply/clear/reset/standings/tiebreakers/advancing/best-thirds/scenarios/summary/persistence/edge cases。全部 1300+ 单元测试和 14 集成测试通过，ruff + node --check 通过。
- [x] **相似球员搜索增强套件**（2026-07-12）：3 个相互关联的功能 + 1 个 bug 修复 + 1 个前端增强：(1) 位置加权特征向量（`_POSITION_FEATURE_WEIGHTS` 表在 `api.py` 为 8 个位置组 GK/CB/FB/DM/CM/AM/W/ST 定义 per-position 权重，权重在 z-score 后、cosine 相似度前缩放特征向量，使与位置更相关的维度携带更多信号——如 ST 权重 Attack=3.0/Defense=0.5，CB 权重 Defense=3.0/Attack=0.5，GK 权重 Attack=0.0；`_position_weights()` 对未知位置回退到均匀权重；活跃权重在响应中作为 `feature_weights` 暴露）；(2) 跨位置相似度模式（新增 `same_position_only` 参数，默认 True 保持向后兼容；当 False 时每个球员先对自己的位置组 z-score，再合并到跨位置池，使不同位置的画像可比较——CM 的 above-average CM attack 可与 ST 的 above-average ST attack 对比；strengths/weaknesses 的百分位阈值在跨位置模式下也使用 per-position 排名）；(3) 联赛 + 最少分钟数过滤器（新增 `league` 不区分大小写和 `min_minutes` 参数约束候选池；目标球员始终从完整数据集解析，支持跨联赛球探场景——"找与这位英超球员相似的西甲球员"；当目标被过滤出池时，其 z-score 使用池统计量计算，确保相似度计算正确）；(4) Bug 修复——目标向量与池成员解耦（重构目标 z-score 计算不再依赖目标在过滤后的池中，修复 league/min_minutes 过滤器可能排除目标并导致回退到使用第一行作为目标的潜在 bug）；(5) API 端点 `GET /players/{name}/similar` 新增 `same_position_only`/`league`/`min_minutes` 查询参数，响应包含 `feature_weights` 和 `filters` 字段；(6) 前端相似度面板新增控件栏（同位置复选框显示目标位置组、联赛文本输入、最少分钟数数字输入、Apply 按钮），跨位置候选显示位置徽章，特征权重可折叠披露控件，错误消息区分 pool_too_small/zero_vector/no_data 状态。25 个新单元测试通过（位置权重、跨位置模式、联赛过滤、分钟过滤、组合过滤、过滤器回显、目标排除、零向量边界、严格过滤池过小）。
- [x] **比赛势头预测套件**（2026-07-12）：3 个相互关联的功能 + 1 个端点 + 1 个前端可视化：(1) In-play 比赛势头模型（`MomentumPoint` + `MatchMomentum` dataclass + `compute_momentum()` 在 `match_prediction.py`，基于赛前 lambdas 和当前比分/分钟，使用独立 Poisson 计算剩余时间进球分布，推导每分钟胜/平/负概率，按 `minute_step` 生成从当前分钟到比赛结束的时间线）；(2) 单点概率查询（`update_probability_at_scoreline()` 便捷包装器，给定当前比分和分钟返回剩余比赛结果概率三元组）；(3) `GET /predictions/{home}/{away}/momentum` 端点（`get_match_momentum()` 获取赛前 DC lambdas 并计算完整势头时间线，支持 `home_goals`/`away_goals`/`minute` 查询参数）；(4) 前端比赛预测页新增势头时间线可视化面板（比分/分钟输入控件、Update 按钮、当前概率摘要、ECharts 折线图三条线 home_win/draw/away_win 随时间变化，x 轴分钟 y 轴 0-100%）。31 个新单元测试覆盖势头计算、单点查询、边界条件和异常路径。
- [x] **集成预测与校准漂移监控套件**（2026-07-12）：2 个相互关联的功能 + 2 个端点 + 2 个前端增强：(1) 集成预测（`EnsemblePrediction` dataclass + `ensemble_prediction()` 在 `match_prediction.py`，按权重混合多个 PoissonPrediction 的比分矩阵和 lambdas，`optimize_ensemble_weights()` 网格搜索最优 Poisson/DC/Form 权重最小化 RPS）；(2) 校准漂移监控（`CalibrationDriftReport` dataclass + `compute_calibration_drift()` 在 `backtests.py`，按时间窗口分割预测数据，计算每窗口 RPS/Brier/LogLoss，检测最新窗口相对历史均值的相对变化是否超阈值）；(3) `GET /predictions/{home}/{away}?model=ensemble` 端点（`get_ensemble_prediction()` 拟合三个模型并混合，返回 blended 预测 + per-model 分解）；(4) `GET /predictions/drift` 端点（`get_calibration_drift()` 读取 backtest 产物计算漂移，5 分钟 TTL 缓存）；(5) 前端模型选择器新增 Ensemble 选项 + 集成模型分解表（per-model 权重和概率）；(6) 前端 backtest 视图新增校准漂移监控面板（STABLE/DRIFT 状态 pill、窗口表、最新窗口高亮、相对变化显示）。29 个新单元测试通过。
- [x] **比赛预测增强套件**（2026-07-12）：3 个相互关联的功能 + 2 个增强：(1) Bootstrap 置信区间（`bootstrap_prediction_confidence()` 在 `match_prediction.py`，对 fixture-level 数据有放回重采样，每个 bootstrap 样本重新拟合 DC 模型，收集 home_win/draw/away_win/home_lambda/away_lambda 分布，返回 `PredictionConfidenceInterval` 含百分位区间）；(2) 基于近期状态的 DC 匹配权重（`compute_form_weights()` 计算每场比赛的滚动 form 权重，`fit_dixon_coles_with_form()` 便捷包装器，`fit_dixon_coles()` 新增 `match_weights` 参数）；(3) Form-weighted 预测 API（`GET /predictions/{home}/{away}?model=form` 端点，`get_form_weighted_prediction()` 使用 form-weighted DC + tuned decay）；(4) 前端置信区间显示（概率条内联区间 + 校准区详细区间块）；(5) 球队对比雷达增强（颜色编码面积填充 + 维度差异表）。24 个新单元测试通过。
- [x] **预测模型校准与调优套件**（2026-07-11）：4 个相互关联的功能 + 1 个修复：(1) Dixon-Coles decay 网格搜索自动调优（`tune_dixon_coles_decay()` 在 `backtests.py`，9 个候选 decay 值 × 时间序列交叉验证，按 RPS/Brier/LogLoss 选取最优，返回 `DecayTuningResult` 含 per-candidate 指标和 comparison_table）；(2) CLI `tune-predictions` 命令（支持 `--metric`、`--n-splits`、`--run-backtest` 参数，`--run-backtest` 时自动用最优 decay 生成全套 backtest 产物——Poisson/DC no-decay/DC best-decay predictions + metrics JSON + isotonic calibration report）；(3) `GET /predictions/tuning` API 端点（读取 `decay_tuning_results.json`，5 分钟 TTL 缓存，not_available 状态含指引）；(4) 前端 backtest 视图新增"Decay 参数调优"面板（展示候选对比表、高亮 BEST decay、显示半衰期天数、中英双语）；(5) 修复 `pipeline.py` decay 硬编码 0.005——新增 `_resolve_dc_decay()` 优先从调优产物读取最优值，无产物时回退到论文推荐值。18 个新单元测试通过。
- [x] **球探智能与球员相似度套件**（2026-07-11）：4 个相互关联的功能 + 1 个 bug 修复：(1) 球员相似度搜索全栈实现（`find_similar_players()` 基于 6 维 z-score 特征向量 + 余弦相似度，`GET /players/{name}/similar` 端点，前端球员档案底部相似球员面板 + CSV 导出，点击卡片可切换球员）；(2) 真值标签回灌闭环（`LabelSource.SCOUTING_REVIEW` 新增枚举值，`workspace_to_truth_labels()` 将 workspace 的 review.statuses approved/rejected 转换为 truth labels，CLI `import-truth-labels --workspace` 命令支持从 workspace JSON 导入并合并到 parquet，合并时移除同 player_id 的旧 scouting_review 标签避免重复）；(3) 球队实力雷达 6 维增强（`get_team_comparison()` 雷达从 GK/DEF/MID/ATT/Overall 5 维扩展到 6 维，新增 Depth 维度量化阵容深度）；(4) Bug 修复 `get_player_comparison()` position_percentiles 契约不一致（原错误按 `{"dimensions": [...]}` list 形态处理，实际是 `{dim_key: {label, percentile}}` dict 形态，导致 pct_comparison 始终为空）。58 个新/更新单元测试通过，ruff + node check 通过。
- [x] **模型信任与数据归属套件**（2026-07-11）：4 个相互关联的功能：(1) 报告页接入详情端点（`fetchModelRunDetail` 异步加载 `/reports/model-runs/{run_id}`，首次展开时渲染 feature_importance parquet 级数据、params_summary 含 min/max、data_attribution 含 StatsBomb 归属）；(2) 数据归属合规面板（`_renderDataAttributionPanel` 渲染 `/license` 端点返回的 `license_attribution` dict，展示数据源标签、StatsBomb 归属高亮、各数据源许可和链接）；(3) 模型运行对比视图（`_populateRunComparisonSelects` + `renderRunComparison` 支持选择两个 run 对比 holdout 指标，含 optimized/baseline × test/train 四组 split、delta 着色和 overfit gap 对比）；(4) Backtest per-fold 可视化（`_renderBacktestFoldChart` 使用 ECharts 折线图展示各模型各折的 log_loss/brier/rps 趋势）。i18n 中英文同步。
- [x] **模型评估与赛事前景套件**（2026-07-11）：5 个相互关联的功能：(1) World Cup team outlook 前端接线完成（`renderWcOutlook` 渲染小组名次概率、淘汰赛投影路径、夺冠概率、阵容强度分解；修复 `projected_opponent`→`opponent`、`advance_probability`→`win_probability`、`quarter_final`→`quarter_finals`、`group_teams` dict 列表字段名不匹配）；(2) Prediction backtest comparison 全栈实现（`get_backtest_comparison` API 读取 CLI 回测产物，构建 log_loss/brier/rps 指标对比表含 winner 选取、分折明细、isotonic 校准报告；`GET /predictions/backtest` 端点；前端 backtest 视图含指标对比表、分折明细、校准效果面板；5 分钟 TTL 缓存）；(3) Model-run provenance 测试补全（依赖版本、train/test seasons、position_metrics、error_cases）；(4) 修复 matches 视图模型对比死代码；(5) 修复 wc_knockout 视图接线。21 个新测试，975+ 总测试通过。
- [x] **世界杯淘汰赛对阵表预测器**（2026-07-11）：新增 `simulate_knockout()` 函数，使用 Bradley-Terry 强度模型和 Monte Carlo 模拟（10,000 次迭代）预测从 32 强到决赛的完整淘汰赛对阵表。包括每场比赛的胜率、逐轮晋级预测和夺冠概率排名。新增 `GET /world-cup/knockout` API 端点；前端新增"淘汰赛"视图含对阵表卡片（5 轮纵列，高亮预测胜者）和夺冠概率表（Top 16）。支持中英双语和移动端单列降级。24 个单元测试覆盖胜率计算、种子配对、模拟可复现性和空数据路径。
- [x] **模型运行血缘登记**（2026-07-12）：`save_model_run()` 现在记录版本化 dataset snapshot input hash 与 feature-manifest hash/version/time；`/model-runs`、`/reports/model-runs/{run_id}` 和报告界面均显示血缘，旧运行明确标注为未记录而不伪造可复现性。
- [x] **世界杯赛前比赛简报**（2026-07-12，Round 17）：新增版本化 `GET /world-cup/match-briefings/{home}/{away}`，把现有强度比 Poisson 预测、阵容评分覆盖/强度构成/Top rated players、来源和限制合成单一只读契约；静态导出写入 `match_briefings.json`。世界杯对比页可加载简报并直接创建浏览器本地战术方案，导出保留模型和 local-artifact 边界。官方首发、实时伤停、市场赔率和战术结论均不在本能力覆盖范围内。
- [x] **世界杯赛程简报入口**（2026-07-12，Round 18）：小组赛赛程新增每场“赛前简报”按钮和可点击行；它会先获取双方阵容、预测及简报，再进入对比页和本地战术方案交接。离线缓存不存在匹配简报时显示不可用，不合成概率或阵容内容。
- [x] **世界杯简报本地报告导出**（2026-07-12，Round 19）：比赛简报支持版本化 JSON 和公式注入防护的 CSV 下载，包含预测、阵容评分覆盖、Top rated players、来源、限制及浏览器本地存储范围；导出不写入服务端、不创建共享链接。
- [x] **战术板简报血缘预览**（2026-07-12，Round 20）：战术板 schema 升级至 1.3.0，受限 decision-pack provenance 保存世界杯简报 schema/version/source；JSON 导出预览显示该引用，方便将战术工程与本地简报导出核对，仍不增加同步或服务端写入。
- [x] **世界杯简报输入快照**（2026-07-12，Round 21）：简报新增 `input_snapshot`，只在模型运行已记录时传递评分 run ID/input hash/feature manifest hash，否则明确 `not_recorded`；同时记录固定强度比 Poisson 的版本、最大比分矩阵和主场修正。世界杯战术方案会转写该快照到 decision-pack provenance。
- [x] **球探工作区服务端持久化**（2026-07-11，v1.0.3）：新增 `ScoutingWorkspaceStore` 服务端持久化层，支持 `PUT/GET /scouting-workspaces/{id}`、`/scouting-workspaces/latest`、`/scouting-workspaces/capabilities` 端点。使用 If-Match 乐观并发控制（revision 版本号）、原子写入、不可变备份和 loopback 访问控制。
- [x] **H2H 近期状态趋势增强**（2026-07-11，v1.0.3）：新增 `compute_form_trend()` 函数，计算 momentum（近期 vs 较早期 PPG 差值）、form_rating（0-100 综合评分）、trend_label（improving/declining/stable）、进球/失球趋势、clean_sheets、failed_to_score 和累积积分 sparkline 数据。前端新增 form trend 卡片含评分条、趋势徽章和 SVG sparkline。空数据和异常路径均有零状态降级。
- [x] **球员球探报告导出**（2026-07-11，v1.0.3）：将单行球员 CSV 导出替换为多段球探报告，支持 CSV 和 JSON 两种格式，覆盖 profile、radar、position_percentiles、xT_summary、3-season trend、low_confidence_reasons、scouting_notes、season_history 八个 section。修复 `position_percentiles` 字段名 bug（API 返回复数 dict，前端读单数 undefined）和 radar label bug（Volume/Overall → Reliability/Impact）。
- [x] **球员对比 CSV 导出**（2026-07-11，v1.0.3）：对比结果面板新增导出 CSV 按钮，下载多段 CSV 覆盖球员 profiles、radar 维度、stats 对比和位置百分位对比。
- [x] **比赛交锋记录视图**（2026-07-11）：新增 `GET /predictions/{home}/{away}/h2h` API 端点，从 `combined_results.parquet` 计算 H2H 交锋史、两队近期 form 和汇总统计。前端比赛预测页新增"交锋记录"section 含比例条、交锋表、战绩对比；没有直接交锋时仍展示近期状态，移动端单列降级。静态导出 `h2h_pairs.json`（40 对）。比赛表与规范化结果使用 TTL 缓存，单次查询从约 3.3 秒降至约 0.06 秒；API 限制查询条数，别名查询通过 `queried_home_result` 保证胜负视角正确。同步修复 `load_player_rolling`/`load_team_rolling` 永久 lru_cache 过期问题（迁移到 TTL 缓存），删除未使用的 `/prediction/{home}/{away}` 单数别名端点。
- [x] **搜索建议端点**（2026-07-10）：新增 `GET /search?q=&type=&limit=` 端点，前缀优先+子串回退匹配球员和球队，支持 type 过滤和 limit 上限 25。前端新增 SearchTypeahead 组件，接入球员搜索、球员对比、球队对比共 5 个输入框，支持键盘导航和防抖。
- [x] **TTL 缓存迁移**（2026-07-10）：将 `_load_all_player_ratings`、`load_model_meta`、`load_league_metrics`、`load_player_value_metrics` 和 `_wc_cache` 从永久 lru_cache 迁移到 TTL 缓存（默认 300 秒，可通过 `SCOUTFOOTBALL_CACHE_TTL_SECONDS` 环境变量配置），支持 `force_refresh` 参数，修复模型重训后 API 返回过期数据的问题。
- [x] **静态对比 fallback 数据**（2026-07-10）：扩展 `scripts/export_static_frontend_data.py` 新增 `compare` 导出段，生成 `player_compare_pairs.json` 和 `team_compare_pairs.json`；前端静态回退映射支持 compare 端点的离线 pair 查找。
- [x] **CI 修复**（2026-07-10）：ci.yml 增加 `frontend/action-value-explorer.js` 语法检查，测试 glob 改为 `frontend/tests/*.test.js`。
- [x] **球队实力分析面板**（2026-07-10）：新增 `GET /teams/strength` API，按分钟加权聚合球员评分到球队级别，返回整体评分、位置组（GK/DEF/MID/ATT）实力分布、核心球员和置信度分布；新增前端"球队"视图含排名表、球队详情卡和位置组对比堆叠柱状图；静态导出脚本同步生成 `team_strength.json`。
- [x] **修复 scouting queue 重复计算**（2026-07-10）：`get_review_queue`/`get_watchlist`/`get_shortlist` 原各自独立调用 `build_scouting_queues`，现通过 `_get_scouting_queues()` 缓存复用。
- [x] **修复 api_server.py Path 导入位置**（2026-07-10）：`Path` 原在文件底部局部导入但被上部代码使用，现移至文件顶部。
- [x] **增加 MP4 导出上传大小限制**（2026-07-10）：`tactical-board/export/mp4` 原无上传大小限制，现限制 50MB。
- [x] **修复 pipeline.py DC 校准死代码**（2026-07-10）：原 `if hg < ...: pass  # Could track log-loss here` 占位代码，现实现实际比分 log-loss 计算并写入校准报告。
- [x] **球员对比工具**（2026-07-10）：新增 `GET /players/compare` API，支持双球员雷达叠加、位置百分位对比和关键指标差异表；新增前端"对比"视图含搜索输入、ECharts 雷达图和指标对比表。
- [x] **修复 VAEP player_id → player_name 映射**（2026-07-10）：从 xT 数据和 events_all.parquet 构建 player_id → player_name 映射，回填 VAEP 数据中缺失的球员名称，使动作价值页能显示球员名而非原始 ID。
- [x] **修复校准缓存失效问题**（2026-07-10）：`get_prediction_calibration()` 原用 `@lru_cache(maxsize=1)` 永久缓存，模型重新训练后返回过期数据；现改为 5 分钟 TTL 缓存，支持 `force_refresh` 参数。
- [x] **球队对比工具**（2026-07-10）：新增 `GET /teams/compare` API，支持双球队位置组雷达叠加、位置组差异表和核心球员对比；前端"球队"视图新增球队对比输入区和雷达图。
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
- [x] Pipeline 端到端：`scoutfootball ingest` -> `scoutfootball build-features` -> `scoutfootball train`。
- [x] 数据验证入口：`scoutfootball validate`。
- [x] FastAPI 只读入口：`scoutfootball serve`。
- [x] Streamlit 多页工作台入口，当前含总览、分析页、P1 页面、世界杯页、球探队列页和动作价值样本页。
- [x] `frontend/` 静态 Liquid Glass 前端原型：总览、球员、身价、比赛预测、球探、动作价值、报告 7 个视图。
- [x] `frontend/` 电子战术板第一切片：本地画布、归一化坐标、基础对象、阵型预设、本地 JSON 工程和 localStorage 保存已落地。
- [x] `frontend/` 电子战术板 PNG 静态导出和 WebM 动画导出已实现；动画时间轴、PDF 导出、报告嵌入和数据分析联动仍待实现。
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
- [x] Dixon-Coles 比分预测核心实现：`fit_dixon_coles`、`predict_match_dc`、`DixonColesModel` 类，Pipeline 集成和 data_loader 集成。
- [x] 战术板增强：drawing tool buttons（select/arrow/zone/text）、文本标注类型、曲线箭头渲染、触控支持（iPad/Safari）、循环动画、项目/帧删除按钮。
- [x] 战术板导出：PNG 静态导出、WebM 动画导出（canvas.captureStream + MediaRecorder）、版本迁移。
- [x] 战术板增强：定位球模板（角球、任意球、边线球、点球、门球等）、自动保存和恢复。
- [x] 球员列表增强：分页、排序、联赛筛选。
- [x] 球员对比百分位表：同位置 percentile 对比表。
- [x] 身价偏离分析：value-fairness OOF 残差、联赛/位置偏差、年龄散点分析。
- [x] 球探队列增强：审阅状态流转（review_status）、watchlist diff、shortlist notes，以及版本化 shortlist dossier（优先级、建议、目标角色、理由与风险）。
- [x] Bug 修复：26 个 bug（6 critical、9 warning、11 minor），测试总数 582。
- [x] 前端安全加固：CSP meta tag、SRI（echarts CDN）、X-Content-Type-Options 安全头、浏览器级 XSS/CSV 回归测试。
- [x] v1.0.0 发布准备：版本号统一、CHANGELOG.md、scripts/demo.sh、README 安装文档和已知限制、世界杯页 SAMPLE DATA 标记、前端 DEMO 横幅。
- [x] 桌面应用打包：Electron + PyInstaller，macOS arm64 构建成功（221MB .dmg），前端打包进 app.asar，后端在 extraResources，自动更新通过 electron-updater + GitHub releases。
- [x] Release workflow 修复：删除 `package.json` `publish` 块解决 GH_TOKEN 错误、修复 Windows `Join-Path` 语法、添加 `-p never`、pipeline 步骤改为 `continue-on-error`。
- [x] 测试环境修复：清理损坏的 torch 命名空间包（25 个测试从 FAILED 恢复）、添加 httpx dev 依赖修复集成测试、`api_server.py` 版本号从硬编码 `0.2.0` 改为 `__version__`。
- [x] MP4 导出通过后端 ffmpeg 转换实现（`/tactical-board/capabilities` 和 `/tactical-board/export/mp4` 端点）。
- [x] 前端 Data Status 页面字段名修复（`a.name` → `a.label`，`a.modified` → `a.updated_at`）。
- [x] `/license` 端点字段名修复（`modified` → `updated_at`）。
- [x] `/predictions/meta` 端点添加顶层字段别名（`status`、`model_type`、`num_teams`、`train_rows`、`coverage`），修复前端 match 视图始终显示 "no artifact" 的 bug。
- [x] 前端 match 视图 calibration 部分修复：从正确的嵌套对象读取 rho、home_advantage、coverage、brier、rps 等字段。
- [x] 前端报告页增强：显示 Dixon-Coles 模型状态和 rho 参数。
- [x] 新增 8 个测试文件（104 个新测试）：action_value/schema、calibration、match_prediction、scouting_queue、cross_provider_schema、prediction_summary、tactical_board_api、backtests。
- [x] P6 跨供应商 schema 参考文档：SPADL 兼容性、kloppy/floodlight/CDF 评估已写入 DATA_CONTRACTS.md。
- [x] P2 socceraction 依赖评估文档已写入 DATA_CONTRACTS.md。
- [x] DATA_CONTRACTS.md 补充 `/license`、`/value-summary`、`/predictions/meta` 端点文档。
- [x] Streamlit 球探队列页增强：联赛/位置/置信度筛选、排序、CSV 导出、标签页分栏、置信度分布统计。

## P0：评分系统真实影响力校准

目标：先修训练目标，再扩展评分模型。当前球队积分相关性会偏向出勤、CM 和 GK，不能单独作为球员影响力标签。

- [x] 完成第一轮反出勤捷径 guardrail：availability cap 下调、ST/W quality cap、holdout 评估、稳健球队聚合、team coverage 报告。
- [x] 重建 Football-Data 10 赛季 `combined_results.parquet`，保留 2526 alias patch，并输出 raw CSV 总行数、active Parquet 行数、league-season 覆盖和输入 hash。
- [x] 用新 aggregation/cap 口径重新跑 GPU 优化，生成新的 `optimized_params.npy`、`optimized_params_meta.json`、holdout predictions、league metrics、calibration 和 feature importance。（2026-06-09，3-fold CV 有效 fold 平均 test Spearman=0.717）
- [x] 复盘 `PROBLEMS.md` 中的误差案例：Everton（+0.9 ✓）、Stuttgart（+3.8 ✓）、Rennes（-0.4 ✓）、Napoli（-35.9 ✗）、Real Madrid（-29.7 ✗）、Arsenal（-15.9 ✗），记录新旧排名变化和仍未解决原因。强队系统性低估根因：评分聚合上限约 55-60，实际强队积分 80-90。
- [x] 增加出勤捷径诊断报告：minutes/starts/matches/availability 置换重要性、按位置 availability 权重、球队聚合权重分布。
- [x] 修复 GPU 优化器 `build_matched_results()` 中的 alias 匹配：集成 `normalize_team_name()` + 重音符号去除 + 12 个新 alias。（2026-06-09）
- [x] 修复 Bundesliga 联赛标签 NaN 问题：评分侧 Bundesliga 球队的 league 字段为 "nan"，已在数据构建时替换。（2026-06-09）
- [x] 补充 Football-Data 2526 赛季数据：已下载 1,751 场比赛，combined_results.parquet 从 5,330 行增至 7,081 行。（2026-06-09）
- [x] 完成 v1.3-dev 优化器目标函数重构：区分 raw team strength 与 calibrated season points，新增训练集拟合积分校准层、积分回归损失、1D 分布匹配损失、争冠/降级尾部校准损失；`--soft-rank-temperature` 已贯穿 Spearman/NDCG/位置一致性，NDCG 改为 soft discount 可微目标。
- [x] 用 v1.3-dev 目标完整重跑 GPU optimizer，生成新的 `optimized_params.npy`、`optimized_params_meta.json`、`rating_holdout_predictions.parquet`、CV/stability/feature importance。结果：排序保持（Spearman 0.737），points spread 接近真实分布（0.985），但 points MAE 仍 11.55 且联赛截距偏差明显。
- [x] 完成 v1.3.1-dev 代码改进：训练集联赛残差 offset（可通过 `--disable-league-calibration` 关闭）、`league_bias_weight` 训练损失、holdout predictions 输出 global points / league offset / final calibrated points。
- [x] 完成 v1.3.2-dev 代码改进：新增 `--truth-label-weight`、`--min-truth-labels`、`--disable-truth-label-anchor`，通过 `rating_feature_matrix.parquet` 桥接 `player_id -> player_name/season` 后，把球员真值标签作为可选 z-score + rank anchor loss；标签为空或匹配少于阈值时自动禁用。
- [ ] 用 v1.3.1-dev 目标完整重跑 GPU optimizer，重新生成 `optimized_params.npy`、`optimized_params_meta.json`、`rating_holdout_predictions.parquet`、CV/stability/feature importance，并复盘 Barcelona/Real Madrid/Burnley、Serie A/La Liga/Ligue 1 联赛截距偏差是否改善。
- [ ] 有足够球员真值标签后，用 v1.3.2-dev 目标完整重跑 GPU optimizer，并把 truth-anchor 的 holdout 效果、位置内指标和误差案例写入 `EVALUATION.md`。
- [x] 对 coverage 低于 0.90 的 league-season 禁止输出强排序结论，只允许作为低置信度诊断样本；该规则仍适用于五大联赛以外的 2526 division 和后续新增数据。
- [x] 定义真实标签层级：Transfermarkt 手动导入、权威奖项、国际/俱乐部出场级别、专家分档、位置内人工校准集。
- [x] 新增标签数据契约和校验脚本，输出 `data/gold/feature_store/player_truth_labels.parquet`。
- [x] 标签契约必须包含 `label_source`、`label_confidence`、`as_of_date`、`position_scope`、`manual_review_flag`，并区分身价代理、奖项荣誉、专家分档和人工校准。
- [x] 新增评分特征矩阵契约，输出可复用的 `rating_feature_matrix.parquet` 或等价产物，包含数值特征、位置/联赛类别、数据源覆盖、缺失字段标记、输入文件 hash 和 feature manifest。
- [x] 修正缺失高阶字段处理：防守、控球、xT/VAEP、门将字段缺失时必须有 missing flag 和中性/低置信度 fallback，不能把缺失值 0 当成真实低能力。
- [x] 重写优化目标：组合 Spearman/NDCG、位置内排序、跨联赛校准、年龄/趋势合理性、极端样本惩罚。
- [x] 用新组合目标在 GPU 服务器重跑完整优化，生成新的 `optimized_params.npy`、holdout predictions、league metrics、calibration 和 feature importance。
- [x] 复盘 `PROBLEMS.md` 中的误差案例：Everton、Stuttgart、Hoffenheim、Rennes、Napoli、Real Madrid、Arsenal、PSG，记录新旧排名变化和仍未解决原因。
- [x] 保留球队结果相关性作为辅助校验，不再作为主目标。
- [x] 定义神经网络准入门槛：必须先有球员真实标签、时间切分、当前优化器 baseline、位置内/跨位置指标、误差案例复盘和低置信度规则；不允许只用球队积分监督训练默认模型。
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
- [x] 新增 `src/scoutfootball/viz/pitch.py`，封装球场、坐标、shot map、pass map、heatmap 基础图。
- [x] 在 Streamlit 增加"位置内榜单"和"跨位置总榜"切换。
- [x] 修复 Streamlit `st.Page` 入口路径，支持从仓库根目录执行 `uv run streamlit run src/scoutfootball/app/streamlit_app.py`。
- [x] 用 `frontend/index.html`、`frontend/style.css`、`frontend/app.js` 重构静态前端，保留 Liquid Glass 风格并补齐主要产品视图。
- [x] **统一分析台前端风格**（2026-07-12）：将浅/深主题、导航、筛选控件、数据卡、表格、排行榜和状态 pill 收敛到统一的场地数据台 Liquid Glass token；新增可见焦点环、跳至主内容链接、`aria-current="page"` 活动导航、语义化主题状态和 `prefers-reduced-motion` 降级；纯静态服务、前端语法、Node 测试和 Python 契约验证通过，发布前仍需在目标浏览器做最终视觉回归。
- [x] 增加低置信度提示：分钟不足、数据源缺失、位置重判不确定、事件样本不足。
- [x] 前端图标统一为几何 Unicode 符号（◎ ◇ € △ □ ⌁ ▣ ⬡ ⊕ ⟷ ⊞），无 emoji。
- [x] 身价页 API 无数据时显示 DEMO 标记，避免静默展示假数据。
- [x] 修正 DuckDB 文件名不匹配（`scoutfootball.duckdb` → `scoutlab.duckdb`）。
- [x] 顶部栏新增 API 连接状态指示器（OK/OFFLINE）。
- [x] `fetchRatings()` 按位置分组计算客户端 radar 百分位，球员列表加载后即有真实 radar 数据。
- [x] 后端容错加固：DuckDB 读取 fallback、`_safe_read_parquet`、numpy 类型序列化、异常捕获。
- [x] 给 README 加截图说明和 demo 复现步骤（前端视图表 + 数据复现命令；实际截图待补充）。
- [x] 前端安全加固：API/本地 JSON 字符串进入 `innerHTML` 前统一 HTML/attribute escaping，CSV 导出增加公式注入防护，战术板 JSON 导入增加 schema sanitizer、对象/帧数量上限和导入大小限制。

### 前端长期功能和后端配套

中长期顺序、阶段门槛和非目标见 `docs/ROADMAP.md`；本文件继续作为唯一任务状态真源。

- [x] 全局数据状态页读取 artifact registry，显示产物更新时间、行数、数据源类型、联赛覆盖率和 confidence gate 已实现。
- [x] artifact registry、更新时间、行数、data source label、license attribution 与 confidence gate 已接入。
- [x] 球员画像页接入 player profile API：模糊搜索、分页、位置/赛季过滤、CSV 导出、xT 摘要、置信度原因、评分快照历史已实现。
- [x] 球员画像页补完整个人信息卡：赛季趋势、低置信度原因、数据来源、位置百分位、缺失字段列表已实现。
- [x] 球员列表补 watchlist/shortlist/战术板操作：每行 3 个动作按钮（□/△/◎），localStorage 存储已实现。
- [x] 身价偏离页接入 value-fairness API：OOF 残差、联赛/位置偏差、年龄曲线、Transfermarkt 导入提示已实现。
- [x] 身价页补价格带筛选、年龄曲线散点图、同位置同年龄对比表、Transfermarkt 导入提示已实现。
- [x] 比赛预测页统一 Score Matrix 和 Match Prediction 后端逻辑：模型对比（Poisson vs Dixon-Coles）、log-loss、coverage gate 已实现。
- [x] 比赛预测页补校准视图：Dixon-Coles 参数、coverage gate 警告、低比分分析、Brier/RPS 指标已实现。
- [x] 球探页接入 review queue/watchlist/shortlist 只读契约；当前优先读取 `data/reports/scouting/*.parquet`，缺失时从评分产物派生只读队列。
- [x] 动作价值页接入 15,062 行 xT + VAEP 产物；仍明确标注为 StatsBomb 样本，不写成全量联赛能力。
- [x] 动作价值页补 StatsBomb Open Data attribution 已实现。
- [x] 报告页接入 model-run registry：展开/折叠详情、复制命令、依赖版本显示已实现。
- [x] model-run registry 已展示 `run_id`、`input_hash`、随机种子、参数、训练/测试切分、Spearman/Pearson 和特征重要性。
- [x] 报告页补完整模型运行详情：参数完整列表、随机种子、训练/测试赛季切分、特征重要性 Top 5 已实现。
- [x] FastAPI 增加 typed read-only endpoints：`/artifacts`、`/players/{player_name}`、`/ratings/snapshots`、`/predictions/{home}/{away}`、`/predictions/meta`、`/review-queue`、`/watchlist`、`/shortlist`、`/action-values`、`/reports/model-runs`；兼容旧路由别名。
- [x] 前端浏览器级安全回归测试已完成：XSS 测试覆盖恶意球员名/队名/报告 run_id/战术板标题/CSV 公式注入。
- [x] 前端已补 CSP meta tag、SRI（echarts CDN）和 X-Content-Type-Options 安全头；CORS 已支持 SCOUTFOOTBALL_CORS_ORIGINS 环境变量配置。
- [x] 世界杯页接入真实评分数据：球员名与评分匹配、覆盖率摘要、未匹配球员 N/A 显示已实现。

### P1.1：球探与动作价值恢复和稳定化（2026-06-23）

- [x] 恢复侧栏"球探"和"动作价值"入口，移除临时 `display:none`。
- [x] 修复球探 `player_name` 契约错配，保留 reason/status/note/date/snapshot 字段。
- [x] 球探增加搜索、状态筛选、显式快照、复核队列 CSV 导出，并合并球员页 localStorage 手动选择。
- [x] 修复动作价值旧字段与现行 `xt_per_90`/`vaep_per_90` 契约错配及未定义变量异常。
- [x] 动作价值增加 xT/VAEP 切换、赛事/分钟/搜索筛选、摘要、小样本提示和战术板能力门控。
- [x] 修复纯静态服务器 404 阻断 `frontend/data/` 回退的问题。
- [x] 增加 `test_frontend_feature_contracts.py`，覆盖入口、字段、静态回退和工作台控件。
- [x] review queue 已分页，每页 50 条，避免一次渲染 9000+ 条记录。
- [x] API 状态 pill 区分 LIVE / STATIC / OFFLINE；静态 fallback 成功时明确标识 STATIC。
- [x] API 和静态缓存均不可用时显示加载失败。
- [x] NaN/undefined 数值显示已加防护。
- [x] 世界杯页状态 pill 已动态化。
- [ ] 将球探/动作价值真实浏览器流程加入 CI，覆盖 API、静态、空数据和移动断点。
- [x] 建立版本化 scouting workspace v1.1 导入/导出和审计字段：支持 workspace ID、revision、时间戳、导入预览、同键冲突检测、安全合并和显式替换；仍不增加生产写 API。
- [x] 增加显式启用的本地 scouting workspace 持久化：v1.x 校验、仅回环访问、`If-Match` 乐观并发、原子写入、更新前不可变备份，以及前端保存/加载和冲突预览；不开放默认远程写入。
- [x] 补齐 VAEP `player_id -> player_name/team/season` 映射与未映射覆盖率。
- [x] 动作价值多维下钻：球队/赛季/赛事/分钟/搜索联合筛选，筛选选项动态聚合，身份覆盖率摘要，未映射球员回退显示 ID（`frontend/action-value-explorer.js`）。
- [x] 动作价值球员研究档案：`GET /action-values/players/{player_id}/context` 将 xT 球员—球队—赛季行、VAEP 球员—球队生涯行与版本化比赛样例并列返回；前端详情弹窗支持离线回退和 JSON 导出，并强制显示 `direct_numeric_comparison: false` / `additive: false`，不生成跨模型合并排名。
- [x] 增加 3 场跟踪样本的球员→比赛→动作证据下钻：pass/carry/shot、目标区域、时间段、高价值动作坐标，以及 API/静态回退和样本外边界提示。
- [ ] 生成可版本化的全量比赛级动作产物，补比赛日期/分钟/赛事覆盖和置信区间；在评分融合前完成时间切分与独立评估。3 场样本重算的 xT 不得与完整聚合榜直接比较或相加。

### P1.2：测试与静态导出可靠性（2026-06-23）

- [x] 新增 API JSON 清理回归测试：覆盖 `_clean_json_value` 对 numpy.int64/float64/bool_/inf/NaN 的序列化。
- [x] 新增静态 frontend JSON 契约测试：验证 `frontend/data/` 下各 JSON 文件为合法 JSON dict/list，不含 repr 字符串。
- [x] 新增空数据处理测试：验证 API 和前端对空数据集的降级显示。
- [x] 修复 BUG-001：`scripts/export_static_frontend_data.py` 不再静默使用 `str(obj)` fallback 写入非法 JSON；dataclass/Pydantic response 必须经过 JSON-safe serializer。
- [x] `frontend/data/health.json` 和 `frontend/data/players_list.json` 已从 repr 字符串修复为合法 JSON dict。
- [ ] 完整浏览器 CI 未完成（当前仅有 Node 语法检查和单元测试，无 Selenium/Playwright）。

验收：

- `uv run ruff check .`
- `uv run pytest`
- `uv run streamlit run src/scoutfootball/app/streamlit_app.py`
- `node --check frontend/app.js`
- `node --check frontend/tactical-board.js`
- `python3 -m http.server 8600 --directory frontend`
- 三个 Streamlit 核心页面、Streamlit 总览页、Streamlit 球探队列页、Streamlit 动作价值样本页和静态 Liquid Glass 工作台已完成；截图、更多 API 指标和世界杯页的真实产物联调待补充。

## P1.5：电子战术板、战术演示和动画导出

目标：把 `frontend/` 从静态分析工作台扩展为可用于教练讲解、赛前演示和报告嵌入的电子战术板。该阶段只做本地轻量产品能力，不进入模型训练，也不替代 P2/P3 的动作价值和评分主线。

### 调研结论

- Tactico 把战术板放进完整教练工作流：100+ 阵型、定位球预设、关键帧动画、球物理、MP4/WebM/GIF 导出、球员评价、训练课日历、实时协作、语音和回放链接。
- DrawTactics 强调路径动画：先放阵型和球，再画球员/足球运动路径，支持直线/贝塞尔曲线、step-based 和 timing-based 两种动画模式、时间轴 scrubber、7 种 easing、WebM 30fps 和自定义裁切。
- TacticSlate 强调离线优先和演示：球员名/号码/角色/队色、箭头/曲线/虚线/highlight/connectors、逐帧 duration、ghost silhouettes、IndexedDB autosave、JSON 备份、PNG/PDF/WebM，以及 2D/3D 切换。
- Coach Tactic Board/Soccer Tactic Board 类移动端产品覆盖现实白板常用能力：多线型画笔、自由笔、文字、矩形/区域、训练器材、全场/半场/任意球/角球/点球场景、球员名/号码/位置/照片、拖拽换人、文件夹、PDF/图片导出、横竖屏和导入/导出。
- Metrica Tactical Boards 更偏视频分析/叠画：给球员加 ID、区域和轨迹、动画球员移动、门后视角定位球，把战术板作为 timeline slide，并可和 Field Radar、telestration、tracking 工作流结合。
- FC Tactix/TacticalPad 类专业工具提示远期上限：2D/3D 同步视图、多人协作、live presence、PNG/GIF/MP4 导出、session planning、跨设备和多运动支持；这些只作为远期参考，不能抢当前本地轻量切片。

### 第一切片：本地战术板画布

- [x] 在 `frontend/` 增加"战术板"视图，保留 Liquid Glass 风格，但画布区域要像工作台，不做营销页。
- [x] 建立标准化球场坐标系：`x`/`y` 使用 0-100 归一化，支持 11v11、7v7、5v5、半场、定位球和门后视角预留。
- [x] 支持基础对象：主队/客队球员、门将、足球、教练标记、箭头、折线、曲线路径、区域、多边形、文本标签、编号和颜色。
- [x] 支持阵型预设：4-3-3、4-2-3-1、3-5-2、4-4-2、5-3-2、定位球模板，并允许从当前球员/队伍数据生成初始名单但不强依赖后端。
- [x] 支持选择、拖拽、复制、删除、锁定、图层顺序、撤销/重做、缩放、适配屏幕和键盘快捷键。
- [x] 定义本地 JSON 工程 schema：`board_id`、`title`、`sport`、`pitch_type`、`objects`、`layers`、`frames`、`version`、`created_at`、`updated_at`、`source_attribution`。
- [x] 将工程保存为浏览器本地存储 + 可下载 JSON；后端持久化先不做，避免把前端原型误写成正式数据产品。
- [x] JSON 工程导入/读取/保存已走 schema sanitizer：限制对象数、帧数、文本长度、导入文件大小、坐标范围和对象类型，避免把任意本地 JSON 直接渲染到页面。

### 对标功能池（待实现，不代表当前能力）

#### A. 白板与绘图体验

- [x] 自由画笔：pen 模式收集鼠标路径点，支持颜色、粗细、撤销；eraser 模式删除点击对象。
- [x] 线型工具：箭头支持 solid/dashed/dotted/run/pass/shot/dribble 七种线型；曲线、贝塞尔曲线已实现。
- [x] 图形工具：矩形（rect）、椭圆（ellipse）已实现，支持填充色和边框色；多边形、扇形、阴影区域仍待实现。
- [x] 文字工具：文本标注类型已实现（text annotation）；可拖拽文本框、帧备注、coach notes、字体大小和颜色仍待完善。
- [x] 选择工具：复制（Ctrl+D）、镜像（Ctrl+M）、主队/客队整体镜像已实现；框选、多选、锁定、隐藏、粘贴、旋转、缩放、对齐、分布、前置/后置和层级排序仍待实现。
- [x] 网格与吸附：showGrid 显示 10 单位球场网格，snapToGrid 移动时按 5 单位吸附。
- [x] 画布导航：触控支持（iPad/Safari 基础触控）已实现；缩放、平移、适配屏幕、全屏、移动端双指缩放和键盘快捷键仍待完善。
- [x] 白板状态：path 对象通过 frame visibility 控制每帧显示已实现。

#### B. 球队、球员和棋子模型

- [x] 红蓝两队/主客队同时显示：single/both/transition 三种模式，攻防方向箭头已实现。
- [x] 球衣与棋子外观：circle/square/triangle/diamond 4 种形状，size 1-5，opacity 0.3-1.0 已实现。
- [x] 球衣号码编辑：双击球员棋子弹出号码输入框（0-99），Enter/blur 确认，更新后重绘。
- [x] 球员信息 hover card：悬停显示姓名、号码、球队、位置、替补标记已实现。
- [x] 球员详情 click panel：双击球员打开浮动面板，可编辑姓名/号码/位置/球队/形状/大小/透明度/备注已实现。
- [x] 替补席与换人：bench 对象类型已实现，场外显示为小圆虚线框，拖拽到场上与同队球员交换位置。
- [x] 训练器材对象：锥桶（cone）、标志碟（marker）、杆（pole）、梯子（ladder）、迷你门（minigoal）5 种器材已实现。
- [x] 足球对象增强：多球创建、拖拽轨迹、球权指示器（home/away 色点）已实现。
- [x] 重叠对象处理：重复点击同位置循环选择重叠对象，置顶/置底按钮已实现。
- [x] 队伍模板：saveTeamTemplate/loadTeamTemplate/listTeamTemplates，localStorage 存储已实现。

#### C. 场景、阵型和模板

- [x] 场地类型扩展：11v11、7v7、5v5、半场、训练场、空白白板 6 种球场模式已实现。
- [x] 预设阵型扩展：新增 3-4-3、3-4-2-1、4-1-4-1、4-3-1-2、4-2-2-2、4-5-1、5-4-1 共 7 种阵型。
- [x] 定位球模板：角球近门柱、角球二点、任意球人墙、边线球、点球、门球 build-up、开球套路和防定位球站位。
- [x] 训练模板：rondo、压迫演练、反击、传控 4 种训练模板已实现，含球员、区域和箭头对象。
- [x] 文件夹/项目管理：删除按钮（项目/帧）已实现；按对手、比赛、训练课、主题、日期、标签和作者组织战术板、复制项目、复制帧、另存为模板仍待实现。
- [x] 教学模式：所有阵型/定位球/训练模板已添加 coaching points，演示模式显示教练笔记叠加。

### 第二切片：战术演示和动画时间轴

- [x] 增加 Animate mode：循环播放已实现；关键帧、步骤帧、帧时长、播放/暂停/单步、时间轴 scrubber 仍待实现。
- [x] 支持 step-based 和 timing-based 两种动画模式，step 模式全局步进时长 500-3000ms 已实现。
- [x] 支持对象路径插值：多段线性/Bezier 路径、路径编辑模式、路径可视化已实现。
- [x] 支持 Bezier 路径、4 种 easing、delay/pause、自动控制点计算已实现。
- [x] 支持 ghost silhouettes：动画模式下显示上一帧/下一帧球员半透明位置（ghostOpacity 可调）。
- [x] 支持 trails：动画播放时显示球员/球移动尾迹（渐隐圆点），球拖拽时显示轨迹。
- [x] 支持帧内对象可见性：visibleFrom/visibleTo 字段控制对象在哪些帧显示。
- [x] 支持动画事件标记：press/pass/shot/turnover/overlap/underlap/third-man/cover 8 种类型已实现。
- [x] 支持战术片段结构：phase/trigger/roles 字段 + phase 图标 + phase 过滤已实现。
- [x] 支持演示模式：全屏播放、自动播放动画、帧备注叠加、ESC 退出已实现。
- [x] 动画只在浏览器里播放；浏览器不运行训练、爬虫、批量视频转码或模型推理。

### 第三切片：导出、报告和后端契约

- [x] 支持 PNG 静态导出：当前画布、透明/球场背景、16:9/1:1/9:16 裁切。
- [x] 支持 PDF 导出：通过浏览器打印窗口导出当前画布为可打印 PDF。
- [x] 支持 WebM 动画导出：优先用 `canvas.captureStream` + `MediaRecorder`；导出失败时给出清晰降级提示。
- [x] MP4 导出只作为可选本地后端能力：需检测 ffmpeg 是否存在，输出到 `data/reports/tactical_exports/`，没有 ffmpeg 时不报错，只保留 WebM。（已实现 `/tactical-board/capabilities` 和 `/tactical-board/export/mp4` 端点）
- [x] GIF 导出已通过 gif.js 实现，并保留 WebM 为主要动画格式。
- [x] 导出裁切和版式：full/half-left/half-right/center-16:9/square-1:1 裁切 + 透明背景已实现。
- [x] 打印模式：多帧 PDF + 备注 + 球员图例 + source attribution 已实现。
- [ ] 分享方式：本地 JSON 文件、浏览器下载、剪贴板图片、只读演示链接（后置）、报告页嵌入；云同步和公开分享默认不做。
- [x] 支持 JSON 工程基础导入/导出，并在导入时清洗 schema。
- [x] 版本不兼容时走迁移或只读打开，避免旧工程静默丢字段。
- [x] JSON 工程补 migration registry（1.0.0->1.2.0）、validateProject/roundTripTest、损坏文件处理已实现；1.2.0 增加受限的赛前决策包 metadata。
- [ ] 后续 FastAPI read-only endpoint 可设计为 `/tactical-boards`、`/tactical-boards/{id}`、`/tactical-boards/{id}/exports`，但第一阶段不急于实现写入 API。
- [x] 战术板嵌入报告页：Board Snapshots 列表、coaching notes 预览、点击加载已实现。

### 第四切片：数据分析联动

- [x] 从球员画像页发送球员到战术板，自动带入姓名、号码、位置和评分数据已实现。
- [x] 从比赛预测页创建赛前方案：主客队阵型、实际已加载的预测概率/比分矩阵、模型版本和 coverage 写入版本化决策包；请求不可用时明确记录 `not_loaded`，不写入占位概率。
- [x] 从 P2 动作价值产物读取样例 xT 热区作为背景参考，并保留 StatsBomb attribution；不写成全量动作价值战术建议。
- [x] 从 watchlist/shortlist 读取备注，生成战术角色说明（位置/层级/工作量）已实现。
- [x] 从国家队/世界杯页创建队伍模板：4-3-3 阵型 + 球员姓名/号码已实现。
- [x] 支持战术板上显示球员评分 badge（颜色编码：绿/黄/红），可通过按钮切换显示/隐藏。
- [x] xT 热区背景层：action values 页 'Show on Tactical Board' 按钮，蓝红色标，StatsBomb 归属已实现。
- [x] 公开导出物如果包含 StatsBomb Open Data 或其他衍生数据，必须带 data source attribution。（前端已自动更新 source_attribution，导出已包含 attribution 文字）
- [x] 含预测输出的 JSON 工程导出预览显示模型、model run id 或 local artifact snapshot、输入 hash（如可用）及本地存储边界。

### 第五切片：质量、安全和兼容性

- [ ] 战术板所有导入字段继续走 `TACTICAL_BOARD.sanitizeProject()`，新增对象类型必须同步 sanitizer、schema 文档和 fixture。
- [x] 战术板浏览器回归测试：10 个新测试覆盖恶意标题/球员名/超大 JSON/损坏 JSON/重复 ID/超出坐标/过多对象/旧 schema 已实现。
- [x] 赛前决策包 Node 合约测试覆盖真实预测、未加载时不写入回退概率、受限 metadata 的导入导出和字段上限。
- [x] 支持桌面鼠标、触控板、iPad/Safari 基础触控；移动端只读查看和编辑能力可以后置。
- [x] 无障碍基础：25+ aria-label、Tab/Enter/Escape 键盘导航、焦点环、团队图例、导出预览已实现。
- [x] 性能边界：200 对象/60 帧警告、FPS 计数器、Simplify 按钮已实现。
- [x] 自动保存和恢复：编辑后防抖保存、本地存储失败提示、导入前备份当前项目。

验收：

- `node --check frontend/app.js`
- `node --check frontend/tactical-board.js`
- `python3 -m http.server 8600 --directory frontend`
- 手动验证桌面和移动宽度下：对象不溢出、文本不重叠、画布非空、拖拽/撤销/播放/导出可用，红蓝两队、号码修改、hover 信息卡和自由画笔至少完成一个稳定切片。
- JSON 工程 round-trip：创建 -> 导出 -> 重新导入 -> 对象、帧、备注一致。
- PNG 和 WebM 导出至少在本机浏览器通过；MP4 没有 ffmpeg 时必须优雅降级。
- README、TASKS、AGENTS 同步说明该功能是否已实现，不得把未接入后端的 mock 数据写成正式能力。

## P2：StatsBomb 事件动作价值层

目标：先用公开事件数据完成一条可复现的动作价值链路，不引入商业数据源。

- [x] 盘点 `events_all.parquet` 字段和坐标覆盖，写入事件数据覆盖说明。
- [x] 新增 `src/scoutfootball/action_value/` 模块：`spadl_adapter.py`、`xt.py`、`aggregate.py`。
- [x] 第一版只做 StatsBomb events -> internal actions -> xT；internal actions 需记录 provider action id、坐标系、方向、动作结果、前后状态和 source coverage。
- [x] 输出 internal actions schema 文档，并说明它和 SPADL/atomic-SPADL、Common Data Format 的字段映射关系。
- [x] 输出 `data/gold/feature_store/player_action_value.parquet`。
- [x] 生成球员 xT 排行榜、球队 xT 热区图、球员传球/带球推进价值图。
- [x] 基于仓库跟踪的 3 场事件样本提供比赛级证据 API、静态快照和前端下钻；明确样本重算 xT 与完整聚合产物不可直接比较。
- [x] 新增版本化 `player_match_action_value_sample.parquet`（94 条 player-team-match 行）及 manifest：保留比赛日期、赛事、赛季、比分、动作数、估算分钟、正负 xT 与输入 hash；通过 `scoutfootball action-value-matches` 可复算，`/action-values/matches` 和 `frontend/data/action_value_matches.json` 只公开当前 3 场样本，不能代表完整赛事覆盖。
- [x] 评估 socceraction 作为依赖的可维护性，优先复用其 SPADL/xT/VAEP 能力。（评估结果写入 DATA_CONTRACTS.md Section 11）
- [x] 明确 StatsBomb 数据引用要求：公开展示研究或图表时必须注明数据源。（api.py `_STATSBOMB_ATTRIBUTION` + 前端 `attribution_required` 已实现）

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

- [x] 把 xT 聚合结果接入评分解释层：xT_per_90、percentile、contribution 已实现。
- [x] VAEP 已在 xT 稳定后实现；当前 6,771 行球员赛季数据，身份映射与前端下钻仍需继续完善。
- [x] 各维度置信度：position_explanation 每维度包含 confidence level 已实现。
- [x] 按位置输出进攻/防守/控球/出勤/质量解释：position_explanation API 字段已实现。
- [x] 新增第一版神经网络候选模型入口：`src/scoutfootball/models/player_rating_nn.py` 使用现有 scikit-learn MLPRegressor，读取 `rating_feature_matrix.parquet` 和 `player_truth_labels.parquet`，按赛季时间切分，并与 `player_ratings_optimized` baseline 对比。
- [x] 新增 `scoutfootball train-rating-nn` 和 `scoutfootball train` 中的 `player_rating_nn` 候选状态输出；当前标签为空时写出 skipped metrics，不生成可用模型结论。
- [x] 神经网络产物写入 `data/models/player_rating_nn/`，保存 metrics、predictions 和 model pickle；当前只是监督式候选入口，不替换当前评分器。
- [ ] 有足够标签后升级浅层神经网络结构：数值特征 + 位置/联赛 embedding 或 one-hot 对照 + dropout/weight decay，不直接替换当前评分器。
- [ ] 神经网络训练目标升级为多任务结构：球员标签排序/回归为主，球队赛季积分相关性为辅助，另加跨联赛校准、年龄趋势合理性和极端样本惩罚。
- [x] NN feature manifest：feature columns、data hash、hyperparameters、metrics、baseline 对比已实现。
- [x] 建立评分回归测试：位置/联赛多样性、GK 范围、攻防权重、低分钟球员 6 个测试已实现。
- [x] 输出 ALGORITHM.md v2.1：评分公式、位置权重、联赛系数、Dixon-Coles、NN 候选、数据流、已知限制已实现。

验收：

- 新旧评分有可解释对比。
- 神经网络候选模型只有在 holdout、位置内指标、低置信度样本和误差案例均优于或至少不劣于当前优化器时，才允许进入默认展示。
- Top 100、位置内 Top 20、弱联赛顶端样本、低分钟球员均有审查报告。
- `MODEL_CARD.md` 更新。

## P4：模型评估文档和报告层

目标：把"能跑"升级为"可评估、可复现、可解释"。

### EVALUATION.md

- [x] 说明数据切分方式：按赛季时间切分（train/test split），明确 holdout 赛季范围。
- [x] 记录 baselines：league average、Independent Poisson、简单 percentile 聚合。
- [x] 记录核心指标：Spearman rank correlation（位置内 + 跨位置）、NDCG、MAE、RMSE。
- [x] 记录误差案例：Top 100 中出勤捷径球员、弱联赛高估样本、低分钟高方差球员、位置误判案例。
- [x] 按位置输出 metrics：GK、CB、FB、DM、CM、AM、W、ST 分别报告。
- [ ] 若存在神经网络候选模型，必须与当前 PyTorch 权重优化器、v3 默认权重和简单 percentile baseline 同一时间切分对比。
- [x] 对 value_fairness 增加 OOF 残差、联赛偏差、年龄段偏差分析。
- [x] 对比分预测增加 log loss、Brier score、RPS、低比分场景单独报告已实现（/predictions/calibration 端点）。
- [x] 建立模型运行登记：/reports/model-runs/{run_id} 端点返回完整 run 详情已实现。

### MODEL_CARD.md

- [x] 说明数据源：FBref、Understat、Football-Data、StatsBomb Open Data、Club Elo、Transfermarkt（手动导入）、Capology（手动导入）。
- [x] 说明标签定义：当前评分目标是什么、真实标签来源（手动导入、奖项、专家分档）、标签覆盖范围。
- [x] 说明适用边界：当前模型覆盖哪些联赛/位置/赛季、哪些场景可以信任、哪些场景结果不可靠。
- [x] 说明已知偏差：出勤偏差（CM/GK 偏高）、联赛强度偏差（弱联赛顶端样本）、位置偏差、年龄偏差、数据缺失偏差。
- [x] 说明不可用场景：单场评分、实时交易建议、青训选材、伤病预测、合同谈判。
- [x] 每次训练保存 feature manifest：SHA256 hash、hyperparameters、metrics 已实现。
- [ ] 每次公开图表或报告保存 data source attribution，尤其是 StatsBomb Open Data 衍生产物。

验收：

- `scoutfootball train` 产出模型报告或报告输入数据。
- `EVALUATION.md` 和 `MODEL_CARD.md` 能解释当前模型能做什么、不能做什么、误差在哪。

## P5：比分预测升级

目标：把比分预测从可运行 baseline 升级为可比较模型族，但不抢球员评分主线资源。

- [x] 保留 baseline_0: league average 已在代码中保留。
- [x] 保留 baseline_1: Independent Poisson 已在代码中保留。
- [x] 新增 `baseline_2: Dixon-Coles` 核心实现：`fit_dixon_coles`、`predict_match_dc`、`DixonColesModel` 类已实现，Pipeline 集成（`run_weekly_train`、`_save_dixon_coles_artifacts`）和 data_loader 集成（`load_score_prediction_dc`）已完成。
- [x] Dixon-Coles 时间衰减和低比分校准：pipeline 已接入 `half_life_days=180` 参数，校准报告输出低比分实际分布。
- [x] 建立低比分校准报告：Brier 分解、校准图数据、联赛覆盖率已实现。
- [x] 增加概率校准页：calibration plot、Brier 分解、低比分分析、联赛校准已实现。

验收：

- 三档模型同一时间切分、同一指标对比。
- Dixon-Coles 只有在优于 baseline 且校准合理时才进入默认展示。

## P6：跨供应商标准化与开放格式层

目标：让 ScoutFootball 未来可以接入更多 event/tracking 数据，但当前不新增商业数据源，不改变 DuckDB + Parquet 主干。

- [x] 设计 ScoutFootball internal match/event/tracking schema，字段至少覆盖 match metadata、team/player identity、period/time、coordinates、action type、outcome、freeze frame 可选字段和 source attribution。（schemas/match.py 已实现 InternalMatch/InternalEvent/TrackingFrame/InternalLineup）
- [x] 写 docs/DATA_CONTRACTS.md：StatsBomb events、internal actions、SPADL 映射、所有 parquet schema、API 契约已实现。
- [x] 评估 kloppy：作为直接依赖、离线转换工具或暂不接入三种方案都要给出依赖风险、坐标转换风险和测试成本。（评估结果写入 DATA_CONTRACTS.md Section 10.2）
- [ ] 参考 floodlight 的 Game/Team/Player/Event/Frame/Segment 抽象，但只有在 tracking 样例数据进入仓库后才考虑代码接入。
- [x] 新增 data source license manifest：前端 license 页面展示 6 个数据源的许可证、引用要求和 URL；后端 /license 端点返回 attribution 数据。
- [ ] 所有 event/tracking schema 变更必须有 fixture、schema validation 和空数据行为测试。

验收：

- 文档能解释未来如何接入 StatsBomb 360、Metrica/open tracking 或授权 provider，而不影响当前 pipeline。
- 没有合规数据源时，该层只保留 schema 和转换实验，不进入默认训练。

## P7：球探决策与人工校准层

目标：把评分系统从“给分”推进到“可审阅的球探工作流”，同时为真实标签层提供人工闭环。

- [x] 新增人工审阅队列：低置信度球员、弱联赛顶端样本、位置重判不确定样本、误差案例球员自动进入 review queue；审阅状态流转（review_status）已实现。
- [x] 设计 watchlist/shortlist 数据契约，字段包括 `player_id`、`reason_code`、`rating_snapshot_id`、`confidence_level`、`review_status`、`reviewer_note`、`as_of_date`；默认放在 `data/reports/scouting/*.parquet`，缺失时可由评分产物派生只读结果。
- [x] 将 Transfermarkt 手动导入、奖项、专家分档、人工校准集统一进入 `player_truth_labels.parquet`，并保留标签来源和置信度。（transfermarkt_manual.py 已实现 `snapshot_to_truth_labels()`）
- [x] Streamlit 已只读展示 review queue；写入型人工标注继续使用本地 CSV/Parquet，不直接放进生产页面。
- [x] 每轮评分优化后输出 watchlist diff：新增、移除、置信度变化、排名变化和触发原因。

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
PYTHONPATH=src uv run python -m scoutfootball info
PYTHONPATH=src uv run python -m scoutfootball validate
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
| StatsBomb | 无特殊要求，但下载量大（~1000+ 场事件） | 稳定网络环境，使用 `scoutfootball ingest --sources statsbomb` |
| Transfermarkt-datasets | 无特殊要求，但 DuckDB 文件 ~500MB | 手动下载 DuckDB 放到 `data/raw/transfermarkt_datasets/` |
| API-Football | 需要 API Key（环境变量 `API_FOOTBALL_KEY`） | 任意环境，免费 100 请求/天 |

运行 soccerdata 相关适配器时需设置环境变量：
```bash
SOCCERDATA_DIR=./data/soccerdata uv run python -m scoutfootball ingest --sources fbref
```

## Recent autonomous delivery

- [x] **Conservative Transfermarkt identity resolution (2026-07-14):** The dated local snapshot import now converts only deterministic name/team/season or unique-name/season matches into canonical rating-matrix IDs. Ambiguous names, team conflicts, and no-candidate rows stay out of supervision and are retained in a local JSON review report, exposed by `GET /reports/transfermarkt-identities` and the reports panel.
- [x] **Dated Transfermarkt label intake (2026-07-14):** Local CSV/Parquet snapshots now enter `player_truth_labels.parquet` through `import-transfermarkt-truth-labels`. The preview validates without writing, preserves source `snapshot_date` by default, reports source-scoped replacement, rating-matrix name/season coverage, and temporal eligibility; re-imports never delete other label sources. The reports UI now shows post-season snapshot counts alongside source-policy eligibility.
