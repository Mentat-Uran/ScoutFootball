# AGENTS.md

你是一个务实的 AI 开发助手。回答和开发都要直接、准确、可验证。

## 当前项目状态

Pipeline 端到端可运行：`scoutfootball ingest` -> `scoutfootball build-features` -> `scoutfootball train`。当前文档真源是 `docs/TASKS.md`，用户说明是 `README.md`，算法解释以 `docs/ALGORITHM.md` 和 `docs/MODEL_CARD.md` 为准。

本地缓存当前可验证状态：

- FBref：5 赛季标准、射门、misc 表均为 14,356 行。
- Football-Data：`data/raw/football_data/combined_results.parquet` 当前为 4 赛季（2223–2526）、5 个联赛、7,081 行。2526 赛季数据已补充。8 个球队名 alias 不匹配已修复（重音符号去除 + 12 个新 alias）。
- Understat：10 赛季、6 个联赛，`players_10seasons.parquet` 当前为 31,902 个球员赛季行。
- StatsBomb Open Data：`big5_matches.parquet` 当前为 126 场比赛，`events_all.parquet` 当前为 11,871 条事件；`matches_all.parquet` 当前为空表，不要把它当 matches 真源。
- 评分产物：`player_ratings_optimized.parquet` 当前为 30,483 行。
- GPU 优化结果（2026-06-09，alias 修复后）：2526 holdout Spearman=0.740/Pearson=0.744（baseline 0.618/0.619），3-fold CV 平均 test Spearman=0.718/Pearson=0.719。Fold 1（2324）Spearman=0.662，Fold 2（2425）Spearman=0.792，Fold 3（2526）Spearman=0.701。参数稳定性 3 seeds std=0.002。特征重要性：assists_p90 > npg_p90 > minutes。强队系统性低估（Barcelona -37.7, Real Madrid -33.4），降级队高估（Burnley +24.9）。
- 评分特征矩阵：`rating_feature_matrix.parquet`（8,141 行）+ `rating_feature_matrix_manifest.json`，含缺失字段标记、数据源覆盖标记和位置内中位数 fallback。
- Coverage 置信度规则：HIGH/MEDIUM/LOW 三级，coverage < 0.90 禁止强排序结论。
- 出勤捷径诊断报告：置换重要性、位置 availability 权重、球队聚合权重分布、出勤驱动球员识别。
- 位置内指标：GK/CB/FB/DM/CM/AM/W/ST 各位置核心维度、percentile rank 和中文解释模板。
- Finishing shrinkage：经验贝叶斯收缩，K=50，小样本射门不过度放大。
- mplsoccer 集成：`src/scoutfootball/viz/pitch.py` 封装球场、shot map、pass map、heatmap、pizza chart。
- 低置信度提示：分钟不足、数据缺失、位置重判不确定、联赛 coverage 低。
- Streamlit 当前为 15 页工作台：总览、5 个分析页、3 个 P1 展示页、4 个世界杯页、1 个球探队列页和 1 个动作价值样本页；总览页已接入 artifact/model-run 读取，球探页已接入 review queue/watchlist/shortlist 读取，动作价值页已接入 `player_value_metrics.parquet` 样本。
- `frontend/` 静态 Liquid Glass 前端已重构为 7 视图分析工作台：总览、球员、身价、比赛预测、球探、动作价值、报告。所有导航图标统一使用几何 Unicode 符号（◎ ◇ € △ □ ⌁ ▣ ⬡ ⊕ ⟷ ⊞），无 emoji。总览、球员画像、身价、比赛预测、球探、动作价值和报告页已改为读取 FastAPI 本地产物；身价页 API 无数据时显示 DEMO 标记；顶部栏有 API 连接状态指示器（OK/OFFLINE）；`fetchRatings()` 按位置分组计算客户端 radar 百分位，球员列表加载后即有真实 radar 数据；API/本地 JSON 字符串进入 HTML 前已统一转义，CSV 导出有公式注入防护；世界杯页仍含样例/混合数据，不能写成全量真实后端。
- `data_loader.py` 已加固：DuckDB 读取异常时正确 fallback 到 Parquet；新增 `_safe_read_parquet` 辅助函数，corrupt Parquet 文件不会导致 500；6 个数据加载函数已改用安全读取。
- `api.py` 已加固：`_clean_json_value` 支持 numpy.int64/float64/bool_ 和 inf；`get_match_prediction` 捕获所有异常类型；内联 NaN 清理代码已合并到 `_clean_json_value`。
- 电子战术板 P1.5 已落地：`frontend/` 本地画布、归一化坐标、基础对象、阵型预设、本地 JSON 工程、localStorage 保存和 schema 清洗后的导入/导出。新增：绘图工具（自由画笔/线条/矩形/椭圆）、文字注释、曲线箭头、触摸手势支持、循环动画、对象删除按钮。动画时间轴、PDF 导出、报告嵌入、MP4、视频叠画和 tracking 导入仍未实现，不能写成现有能力。PNG 静态导出、WebM 动画导出和版本迁移已实现。
- Dixon-Coles 比分预测模型已实现：`fit_dixon_coles()` 已接入 pipeline 和 `data_loader.py`，7 个单元测试覆盖参数拟合与预测。
- 前端安全加固：`index.html` 增加 CSP meta tag、echarts CDN 加 SRI integrity、HTTP 响应增加 `X-Content-Type-Options: nosniff`；浏览器级 XSS/CSV 回归测试已完成。
- 测试 warnings 清理：`conftest.py` 新增 matplotlib backend fixture 避免 GUI 警告，`pyproject.toml` 增加 `filterwarnings` 配置。
- Bug 修复：26 个 bug 已修复（6 critical、9 warning、11 minor），测试总数 605+。
- 身价偏离分析：value-fairness OOF 残差、联赛/位置偏差、年龄散点分析已实现。
- 球探队列增强：审阅状态流转（review_status）、watchlist diff、shortlist notes 已落地。
- 球员对比百分位表：同位置 percentile 对比表已实现。
- WebM 动画导出：`canvas.captureStream` + `MediaRecorder` 已实现，失败时有降级提示。
- 定位球模板：角球近门柱、角球二点、任意球人墙、边线球、点球、门球 build-up 等模板已实现。
- 球员列表增强：分页、排序、联赛筛选已实现。

新增适配器（已实现，部分需特定环境运行）：
- SofaScore、SoFIFA、WhoScored、Capology：需要 Chrome + Selenium，建议在 Windows GPU 服务器运行。
- API-Football：需要 `API_FOOTBALL_KEY` 环境变量，无 Key 时优雅降级。
- Transfermarkt-datasets：需手动下载 DuckDB 文件放到 `data/raw/transfermarkt_datasets/`。
- FBref 扩展联赛 + 7 种新 stat_type：需要 Chrome + Selenium，建议在 Windows GPU 服务器运行。
- StatsBomb 批量下载：无特殊要求，但下载量大，需稳定网络环境。
- 运行 soccerdata 脚本需设置 `SOCCERDATA_DIR=./data/soccerdata`。

评分系统仍处于校准阶段：

- PyTorch GPU 优化器和远程 GPU 计算脚本已存在。
- 优化目标已从纯 Spearman/Pearson 改为组合目标：Spearman(0.42) + soft NDCG@20(0.16) + 位置内排序一致性(0.12) + 训练集积分回归校准(0.16) + 积分分布匹配(0.10) + 争冠/降级尾部校准(0.14) + 训练集联赛平均残差惩罚(0.08) + 球员评分离群 guardrail(0.05) + 可选球员真值标签锚定(默认 0.08，标签不足时禁用) + 先验正则(0.04)；各权重可通过命令行参数覆盖。v1.3 GPU 重跑已完成：2526 holdout Spearman=0.737/Pearson=0.742，points spread ratio=0.985，points MAE=11.55；主要残留问题是联赛截距偏差。v1.3.1-dev 已新增 train-fitted league residual offset 和 league-bias loss，只读复算可把当前参数 points MAE 从 11.55 降到 9.44，完整 GPU 重跑待执行。v1.3.2-dev 已新增 truth-anchor optimizer 入口和 `scoutfootball train-rating-nn` 监督式 MLP 候选；当前 `player_truth_labels.parquet` 为空，所以 NN 路径只输出 skipped 状态，不替换默认评分。
- 模型运行登记已实现：每次优化后保存到 `data/models/runs/<timestamp>/`，含 optimized_params.npy + meta.json（参数、种子、输入 hash、指标、位置内指标、误差案例摘要）。
- 神经网络准入门槛已写入 `docs/MODEL_CARD.md`：必须先有球员真实标签、时间切分、baseline 对比、位置内指标、误差案例复盘；禁止纯球队积分监督训练。当前已实现 `src/scoutfootball/models/player_rating_nn.py` 作为监督式 sklearn MLP 候选入口，但因本地标签为空不会产出可用模型。
- 当前评分层优先做角色、联赛、真实影响力校准，不再把 Top N 配额作为主目标。
- 已加入粗位置角色重判、较强联赛强度曲线、holdout 评估、Pearson 指标修复、ST/W quality cap。
- 已把所有位置 availability cap 降到 0.18-0.20，CM/DM/FB/CB/GK 不能再用 0.30-0.36 的出勤权重主导评分。
- 球队赛季评分聚合已从纯分钟加权改为 capped minutes + core rotation 的稳健聚合，避免评分层和球队层重复奖励原始出勤。
- 评估报告已输出 team coverage，按 league-season 显示目标球队数、评分侧球队数、匹配球队数和覆盖率；覆盖不足时不能强行解释榜单。
- 2526 五大联赛测试集已直接修补 Football-Data 与评分侧的球队名 alias，Premier League、La Liga、Bundesliga、Serie A、Ligue 1 holdout coverage 已到 1.00。
- 球队积分相关性会偏向出勤、CM 和 GK，不能单独作为球员影响力标签。
- 弱联赛顶端样本已被压低，但仍需真实身价、奖项、专家标签或人工分档校准跨联赛等级。
- FBref 粗位置只能保守重判，仍需要 StatsBomb、阵型或人工位置增强。
- `player_value_metrics.parquet` 只有 StatsBomb 事件价值样本，不能当作全量联赛动作价值；`player_truth_labels.parquet` 已有空表模板和 schema 契约（`truth_labels.py`），待手动填充真实标签数据。
- 评估流程已增加 N/A 球队过滤：`build_matched_results()` 和 `build_team_target_tensors()` 自动剔除积分 NaN/inf 球队，`evaluate_params()` 报告剔除数量。
- 评分模型卡 `docs/MODEL_CARD.md` 已输出，记录数据源、标签定义、适用边界、已知偏差和不可用场景。
- 神经网络评分器只能作为真实标签层完成后的候选实验；没有球员级标签、特征缺失标记、时间切分和 baseline 对比前，不要把 MLP/深度模型写成默认评分能力。`scoutfootball train-rating-nn` 当前应被描述为候选入口和 skipped smoke，而不是已训练模型。
- `docs/PROBLEMS.md` 中记录的问题只能算完成第一轮代码级防护；完整结论必须重新跑 GPU 优化和 2526 holdout 误差复盘后再写。
- GPU 重跑已完成（2026-06-09，alias 修复后，RTX 5070 Ti）：2526 holdout Spearman=0.740/Pearson=0.744（baseline 0.618，提升 +0.122）。3-fold CV 平均 test Spearman=0.718/Pearson=0.719。Fold 1（2324）Spearman=0.662，Fold 2（2425）Spearman=0.792，Fold 3（2526）Spearman=0.701。参数稳定性 3 seeds std=0.002。特征重要性：assists_p90 > npg_p90 > minutes。强队系统性低估（Barcelona -37.7, Real Madrid -33.4），降级队高估（Burnley +24.9）。alias 已修复（12 个新 alias + 重音符号去除），Bundesliga coverage 0.778 待重跑验证。

## 后续架构方向

未来更新按十层推进。前七层是当前主干，第八到第十层分别扩展到球探工作流、预测校准和空间/视频研究，需在 P0-P4 稳定后逐步推进：

1. 数据与合规层：本地缓存、DuckDB、Parquet、手动导入和数据质量日志。
2. 标准事实层：比赛、球队、球员、阵容、事件、赛季统计、身价、联赛强度。
3. 跨供应商标准化层：internal event/tracking schema，对齐 SPADL、atomic-SPADL、Common Data Format、kloppy/floodlight 思路；短期不急加依赖。
4. 事件动作价值层：StatsBomb events -> internal actions -> SPADL/atomic-SPADL -> xT -> VAEP/Atomic-VAEP。
5. 球员真值与评分层：真实标签 + 赛季统计 + xG/xA + xT/VAEP + 出勤可靠性 + 联赛强度 + 年龄/趋势 + 置信度。
6. 评估与模型卡层：`docs/EVALUATION.md`、`docs/MODEL_CARD.md`、position-wise metrics、误差分析、模型运行登记。
7. 产品可视化与 API 层：Streamlit + Plotly + mplsoccer + FastAPI 只读产物 + 电子战术板。
8. 球探决策层：watchlist、shortlist、人工标签审阅、低置信度复核队列、战术备注。
9. 比分预测与概率校准层：league average -> Independent Poisson -> Dixon-Coles + time decay -> calibration。
10. 空间/视频/离球研究层：StatsBomb 360、Metrica/open tracking、space control、xG+、off-ball value，必须依赖合规样例数据。

外部调研依据：

- socceraction：SPADL/atomic-SPADL、xT、VAEP、Atomic-VAEP 的主要参考。
- StatsBomb Open Data：事件层第一主源；公开展示衍生产物必须注明数据来源。
- mplsoccer：足球专用可视化库，当前已接入。
- 电子战术板案例：Tactico、DrawTactics、TacticSlate、Coach Tactic Board、Soccer Tactic Board、Metrica Tactical Boards、FC Tactix、TacticalPad、TacticalBoards；共同特征是阵型/球员拖拽、红蓝双队、球衣号码/姓名/角色、hover 或点击球员信息、自由画笔/橡皮擦、箭头/区域/轨迹、训练器材、关键帧或路径动画、演示播放、PNG/PDF/WebM/MP4/GIF 导出、分享、文件夹/模板、2D/3D 或视频叠画工作流。
- kloppy、floodlight、Common Data Format：只作为跨供应商 event/tracking schema 的远期参考。
- VAEP、xT vs VAEP、PlayeRank、combined player rating、xG finishing bias 和 Dixon-Coles 论文：分别对应动作价值、模型比较、角色内评分、混合评分、终结能力 shrinkage 和比分预测 baseline。

## 当前优先级

1. P0：评分系统真实影响力标签和训练目标重构。
   - 近期先重建 Football-Data 10 赛季合并 Parquet，再用新 availability cap 和稳健球队聚合重跑 GPU optimizer，并复盘 Everton/Stuttgart/Rennes/Napoli/Real Madrid/Arsenal/PSG 等误差案例。
   - 随后引入 Transfermarkt 手动导入、奖项、专家分档或人工校准集作为球员真实影响力标签，并补齐特征矩阵、缺失字段标记和神经网络准入门槛。
2. P1：展示增强和可解释产品层，优先接入 mplsoccer。核心交付：球员雷达/排名页、身价偏离榜、比赛预测页 3 个可截图 Streamlit 页面，README 加 3–5 张截图和 demo 复现说明。
   - 同步维护 `frontend/` Liquid Glass 静态工作台；保持其 UI 风格，但后续必须用 FastAPI/Parquet 契约替换 mock 数据。
3. P1.5：电子战术板、战术演示和动画导出。画布/JSON/绘图工具/文字注释/曲线箭头/触摸支持/循环动画/删除按钮已落地；后续要按 `docs/TASKS.md` 的对标功能池推进，包括关键帧/步骤式动画、演示播放、PNG/PDF/WebM 导出；MP4/GIF、视频叠画、tracking 导入、2D/3D 同步和实时协作后置。
4. P2：StatsBomb 事件动作价值层，先 xT，后 VAEP。
5. P3：评分模型重构，把 action value 作为增强维度接入；真实标签层稳定后，神经网络只能先作为候选模型与当前优化器同口径对比。
6. P4：模型评估文档和模型卡。补 `docs/EVALUATION.md`（Spearman、时间切分、baseline、误差案例）和 `docs/MODEL_CARD.md`（数据源、标签定义、适用边界、偏差、不可用场景）。
7. P5：Dixon-Coles 比分预测升级（`fit_dixon_coles` 已实现基础版，待接入校准和 time decay）。
8. P6：跨供应商标准化和开放格式层，先做 schema、license manifest 和转换实验，不改变当前 pipeline。
9. P7：球探决策与人工校准层，把真实标签、低置信度样本、误差案例和战术备注纳入 review queue、watchlist、shortlist。
10. P8：空间/视频/离球研究层，StatsBomb 360、Metrica/open tracking、xG+、off-ball value、强化学习只作为远期方向。

除战术板外，当前规划必须继续保留这些缺口：真实球员标签仍为空、v1.3.1-dev 完整 GPU 重跑和误差复盘未做、世界杯页仍是样例/混合数据、前端 player/value/prediction/report 只读契约还不完整、动作价值仍是 StatsBomb 样本、球探人工标注回灌未实现、概率校准仍未完成、跨供应商 schema 与 tracking/video 研究仍停留在后续阶段。

## 开发原则

- 数据处理必须可复现、可缓存、可校验。
- ETL 必须幂等，不能依赖不可控的实时网页状态。
- 模型必须有 baseline、时间切分、指标和误差分析。
- 新增模型前先写评估指标，新增长期数据源前先写合规边界。
- 不把计划中的模块写成已实现能力。
- 不把 StatsBomb 小样本事件能力写成全量联赛能力。
- Transfermarkt 只允许手动或授权导入。
- FBref 只作为受限低频补充源，不绕过验证码或反爬。
- 公开展示 StatsBomb 数据产物时必须注明数据源。
- 新增公开图表、报告或导出产物前，必须确认 data source attribution 和可公开展示边界。
- 新增电子战术板导出前，必须明确导出物是否包含真实数据、StatsBomb Open Data 或模型衍生产物；包含时必须保留 source attribution。
- 电子战术板第一阶段只允许浏览器本地画布、JSON 工程和轻量导出；不要在浏览器端执行训练、爬取、批量视频转码或重型模型推理。
- 前端凡是把 API、Parquet 派生 JSON、本地 JSON、demo 字符串或用户导入字段写入 `innerHTML`，必须先使用现有 escaping/sanitizer；CSV 导出必须走 `csvCell()`；战术板导入/保存/读取必须走 `TACTICAL_BOARD.sanitizeProject()`。
- `goals - xG` 不能直接当射术；必须用样本量 shrinkage 或低置信度标记。
- Top N 位置配额不能替代真实影响力校准。
- availability 只是可靠性/样本量信号，不是球员能力本身；未经真实标签验证，不要把 availability cap 提回 0.25 以上。
- 球队赛季聚合不得回退为 raw minutes weighted mean；如果要改 aggregation，必须同时输出 holdout、联赛分层、误差案例和出勤置换重要性。
- 报告 position weights 时必须使用 capped weights，不要把 raw softmax 权重当作实际模型权重。
- 缺失的防守、控球、xT/VAEP、门将高阶字段必须用 missing flag 和低置信度 fallback 表达，不能把缺失值 0 当成真实低能力。
- 新增神经网络或其他复杂模型前，先定义标签、评估指标和 baseline；只用球队积分相关性训练的模型不能作为球员真实能力模型。
- 如果实现神经网络候选模型，必须保留当前评分优化器为 baseline，保存 feature manifest、参数、随机种子、输入 hash、holdout 指标、位置内指标和误差案例对比。
- 强化学习、GCN、Transformer、off-ball value、xG+ 或 tracking/video 模型不能在缺少合规样例数据、标签、baseline 和模型卡时进入默认能力。
- kloppy、floodlight、Common Data Format 当前只作为 schema 和转换参考；未进入对应 phase 前不要直接加入 `pyproject.toml`。
- 对 team coverage 低于 0.90 的 league-season，只能输出低置信度诊断，不要写成完整联赛排名或前四预测结论。
- 如果用户要求测试评分优化器，先在当前电脑小规模运行；未经用户明确允许，不要调用 Windows 5070 Ti 服务器。
- Dixon-Coles 是比分预测第二主线，不能抢在评分系统 P0/P1/P2 前面。
- 战术板 MP4 导出、本地 ffmpeg、视频 telestration、tracking 数据导入、3D/门后视角和实时协作，必须在 P1.5 画布模型、动画 schema、导出降级和报告 attribution 稳定后再进入实现。

## 模块约定

- 现有包根目录是 `src/scoutfootball/`。
- 现有命令入口是 `src/scoutfootball/__main__.py`。
- 现有 pipeline 入口是 `src/scoutfootball/pipeline.py`。
- 新增事件动作价值模块时使用 `src/scoutfootball/action_value/`。
- 新增 internal actions schema 优先写入 `src/scoutfootball/action_value/schema.py` 或 `src/scoutfootball/schemas/`，并同步 `docs/DATA_CONTRACTS.md`。
- 新增神经网络评分候选模型时优先使用 `src/scoutfootball/models/player_rating_nn.py` 或同级模块；训练脚本只做薄入口，不把核心逻辑堆在 `scripts/`。
- 新增模型运行登记优先写入 `data/reports/model_runs/` 或 `data/models/runs/`，必须保存 dataset snapshot、输入 hash、参数、随机种子、依赖版本和指标。
- 新增球探人工校准数据优先写入 `data/gold/feature_store/player_truth_labels.parquet`、`data/reports/review_queue/` 或等价本地产物；不要把人工标签和模型预测写进同一字段。
- 新增足球专用图表时优先扩展 `src/scoutfootball/viz/`，不要把绘图逻辑堆进 Streamlit 页面。
- `frontend/` 是静态产品壳：保留 `frontend/index.html`、`frontend/style.css`、`frontend/app.js` 的 Liquid Glass 风格，页面只做本地展示和轻量交互，不在浏览器中执行训练、爬取或重型数据处理。
- `frontend/` 当前 mock 数据只能用于产品形态验证；接真实数据时先补 FastAPI read-only endpoint 和本地 Parquet 契约，再改前端 fetch。
- `frontend/app.js` 中已有 `escapeHtml()`、`escapeAttr()`、`sanitizeCssPercent()` 和 `csvCell()`；新增 HTML 模板、attribute、style width 或 CSV 导出时优先复用这些 helper，不要把后端/本地字符串直接拼进 HTML。
- 当前已落地的 FastAPI 只读契约子集：`/artifacts`、`/players/{player_name}`、`/ratings/snapshots`、`/predictions/{home}/{away}`、`/predictions/meta`、`/review-queue`、`/watchlist`、`/shortlist`、`/action-values`、`/reports/model-runs`；旧路由别名继续保留给现有页面兼容使用。
- 新增电子战术板优先放在 `frontend/`：使用归一化球场坐标、本地 JSON 工程、对象/图层/帧 schema、关键帧或步骤式时间轴；第一阶段导出 PNG/PDF/WebM，MP4 只能作为检测到本地 ffmpeg 后的可选后端能力。
- 电子战术板工程 schema 至少包含 `board_id`、`title`、`sport`、`pitch_type`、`objects`、`layers`、`frames`、`version`、`created_at`、`updated_at`、`source_attribution`。
- 战术板导出文件优先写入 `data/reports/tactical_exports/`；如果只是浏览器本地下载，不要假装已进入模型/报告产物目录。
- 前端长期视图和后端契约对应关系：
  - 总览：artifact registry、行数、产物更新时间、真实/代理/合成数据标记、license attribution。
  - 球员：player profile API、评分快照、位置内指标、低置信度原因、导出。
  - 身价：value-fairness OOF report、残差分层、手动身价导入边界。
  - 比赛预测：统一 prediction service、模型版本、coverage、log loss/Brier/RPS、比分矩阵。
  - 球探：review queue/watchlist/shortlist Parquet 契约，只读展示优先。
  - 动作价值：P2 action_value 产物稳定前只展示样例，不声称全量能力。
  - 报告：model-run registry、输入 hash、随机种子、参数、指标、误差案例。
  - 战术板：local board projects、board snapshot、animation export、coaching notes、source attribution；写入 API 后置，先支持本地 JSON 导入导出。
- 新增评分特征矩阵模块使用 `src/scoutfootball/features/rating_matrix.py`。
- 新增 coverage 置信度模块使用 `src/scoutfootball/evaluation/coverage_confidence.py`。
- 新增出勤诊断模块使用 `src/scoutfootball/evaluation/availability_diagnostic.py`。
- 新增位置内指标模块使用 `src/scoutfootball/evaluation/position_metrics.py`。
- 新增统一置信度模块使用 `src/scoutfootball/evaluation/confidence.py`。
- 新增真实标签契约模块使用 `src/scoutfootball/evaluation/truth_labels.py`。
- 新增足球专用图表扩展 `src/scoutfootball/viz/pitch.py`，使用 mplsoccer。
- Streamlit 页面只读本地产物，不直接执行重型训练。
- 训练产物写入 `data/models/` 或 `data/gold/feature_store/`，并保存 feature manifest、参数、随机种子和输入 hash。
- 数据合规和引用要求写入 data source license manifest；StatsBomb Open Data 衍生产物公开展示必须注明 StatsBomb。

## 技术默认值

Python, uv, DuckDB + Parquet, pandas, scikit-learn, Streamlit, Plotly, mplsoccer, pytest, Ruff。前端继续以静态 `frontend/` 为产品壳；战术板可评估 Canvas/SVG 或轻量画布库，但新增依赖前必须先证明导出、响应式和可维护性收益。PyTorch 已用于评分优化/GPU 脚本；若把神经网络纳入主项目，必须同步更新 `pyproject.toml`、锁文件、训练入口、模型产物和评估文档。socceraction 是 P2 计划依赖候选；kloppy、floodlight、common-data-format-validator 只有进入 P6 且完成依赖评估后再加入 `pyproject.toml`。

## 验证命令

```bash
uv run ruff check .
uv run pytest
uv run pytest tests/unit/test_rating_optimizer_validation.py
uv run pytest tests/unit/test_rating_optimizer_validation.py tests/unit/test_composite_objective.py tests/unit/test_player_rating_nn.py
PYTHONPATH=src uv run python -m scoutfootball info
PYTHONPATH=src uv run python -m scoutfootball validate
PYTHONPATH=src uv run python -m scoutfootball ingest
PYTHONPATH=src uv run python -m scoutfootball build-features
PYTHONPATH=src uv run python -m scoutfootball train
PYTHONPATH=src uv run python -m scoutfootball train-rating-nn
uv run streamlit run src/scoutfootball/app/streamlit_app.py
node --check frontend/app.js
python3 -m http.server 8600 --directory frontend
```
