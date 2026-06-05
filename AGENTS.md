# AGENTS.md

你是一个务实的 AI 开发助手。回答和开发都要直接、准确、可验证。

## 当前项目状态

Pipeline 端到端可运行：`scoutlab ingest` -> `scoutlab build-features` -> `scoutlab train`。当前文档真源是 `TASKS.md`，用户说明是 `README.md`，算法解释以 `ALGORITHM.md` 和 `MODEL_CARD.md` 为准。

本地缓存当前可验证状态：

- FBref：5 赛季标准、射门、misc 表均为 14,356 行。
- Football-Data：10 赛季、20 个 league/division，原始 CSV 合计 68,953 行；重建脚本 `scripts/rebuild_football_data.py` 可生成完整 10 赛季 `combined_results.parquet`，`rebuild_combined_results()` 函数封装在 `football_data.py` 中。
- Understat：10 赛季、6 个联赛，`players_10seasons.parquet` 当前为 31,902 个球员赛季行。
- StatsBomb Open Data：`big5_matches.parquet` 当前为 126 场比赛，`events_all.parquet` 当前为 11,871 条事件；`matches_all.parquet` 当前为空表，不要把它当 matches 真源。
- 评分产物：`player_ratings_optimized.parquet` 当前为 27,254 行。
- 评分特征矩阵：`rating_feature_matrix.parquet`（8,141 行）+ `rating_feature_matrix_manifest.json`，含缺失字段标记、数据源覆盖标记和位置内中位数 fallback。
- Coverage 置信度规则：HIGH/MEDIUM/LOW 三级，coverage < 0.90 禁止强排序结论。
- 出勤捷径诊断报告：置换重要性、位置 availability 权重、球队聚合权重分布、出勤驱动球员识别。
- 位置内指标：GK/CB/FB/DM/CM/AM/W/ST 各位置核心维度、percentile rank 和中文解释模板。
- Finishing shrinkage：经验贝叶斯收缩，K=50，小样本射门不过度放大。
- mplsoccer 集成：`src/scoutlab/viz/pitch.py` 封装球场、shot map、pass map、heatmap、pizza chart。
- 低置信度提示：分钟不足、数据缺失、位置重判不确定、联赛 coverage 低。
- Streamlit 从 5 页扩展到 8 页（+Player Rankings、Value Deviation、Match Prediction）。
- `frontend/` 静态 Liquid Glass 前端已重构为 7 视图分析工作台：总览、球员、身价、比赛预测、球探、动作价值、报告。当前使用前端 mock 数据演示产品形态，不能写成已接入真实后端。

新增适配器（已实现，部分需特定环境运行）：
- SofaScore、SoFIFA、WhoScored、Capology：需要 Chrome + Selenium，建议在 Windows GPU 服务器运行。
- API-Football：需要 `API_FOOTBALL_KEY` 环境变量，无 Key 时优雅降级。
- Transfermarkt-datasets：需手动下载 DuckDB 文件放到 `data/raw/transfermarkt_datasets/`。
- FBref 扩展联赛 + 7 种新 stat_type：需要 Chrome + Selenium，建议在 Windows GPU 服务器运行。
- StatsBomb 批量下载：无特殊要求，但下载量大，需稳定网络环境。
- 运行 soccerdata 脚本需设置 `SOCCERDATA_DIR=./data/soccerdata`。

评分系统仍处于校准阶段：

- PyTorch GPU 优化器和远程 GPU 计算脚本已存在。
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
- 评分模型卡 `MODEL_CARD.md` 已输出，记录数据源、标签定义、适用边界、已知偏差和不可用场景。
- 神经网络评分器只能作为真实标签层完成后的候选实验；没有球员级标签、特征缺失标记、时间切分和 baseline 对比前，不要把 MLP/深度模型写成默认评分能力。
- `PROBLEMS.md` 中记录的问题只能算完成第一轮代码级防护；完整结论必须重新跑 GPU 优化和 2526 holdout 误差复盘后再写。

## 后续架构方向

未来更新按十层推进。前七层是当前主干，第八到第十层分别扩展到球探工作流、预测校准和空间/视频研究，需在 P0-P4 稳定后逐步推进：

1. 数据与合规层：本地缓存、DuckDB、Parquet、手动导入和数据质量日志。
2. 标准事实层：比赛、球队、球员、阵容、事件、赛季统计、身价、联赛强度。
3. 跨供应商标准化层：internal event/tracking schema，对齐 SPADL、atomic-SPADL、Common Data Format、kloppy/floodlight 思路；短期不急加依赖。
4. 事件动作价值层：StatsBomb events -> internal actions -> SPADL/atomic-SPADL -> xT -> VAEP/Atomic-VAEP。
5. 球员真值与评分层：真实标签 + 赛季统计 + xG/xA + xT/VAEP + 出勤可靠性 + 联赛强度 + 年龄/趋势 + 置信度。
6. 评估与模型卡层：`EVALUATION.md`、`MODEL_CARD.md`、position-wise metrics、误差分析、模型运行登记。
7. 产品可视化与 API 层：Streamlit + Plotly + mplsoccer + FastAPI 只读产物。
8. 球探决策层：watchlist、shortlist、人工标签审阅、低置信度复核队列。
9. 比分预测与概率校准层：league average -> Independent Poisson -> Dixon-Coles + time decay -> calibration。
10. 空间/视频/离球研究层：StatsBomb 360、Metrica/open tracking、space control、xG+、off-ball value，必须依赖合规样例数据。

外部调研依据：

- socceraction：SPADL/atomic-SPADL、xT、VAEP、Atomic-VAEP 的主要参考。
- StatsBomb Open Data：事件层第一主源；公开展示衍生产物必须注明数据来源。
- mplsoccer：足球专用可视化库，当前已接入。
- kloppy、floodlight、Common Data Format：只作为跨供应商 event/tracking schema 的远期参考。
- VAEP、xT vs VAEP、PlayeRank、combined player rating、xG finishing bias 和 Dixon-Coles 论文：分别对应动作价值、模型比较、角色内评分、混合评分、终结能力 shrinkage 和比分预测 baseline。

## 当前优先级

1. P0：评分系统真实影响力标签和训练目标重构。
   - 近期先重建 Football-Data 10 赛季合并 Parquet，再用新 availability cap 和稳健球队聚合重跑 GPU optimizer，并复盘 Everton/Stuttgart/Rennes/Napoli/Real Madrid/Arsenal/PSG 等误差案例。
   - 随后引入 Transfermarkt 手动导入、奖项、专家分档或人工校准集作为球员真实影响力标签，并补齐特征矩阵、缺失字段标记和神经网络准入门槛。
2. P1：展示增强和可解释产品层，优先接入 mplsoccer。核心交付：球员雷达/排名页、身价偏离榜、比赛预测页 3 个可截图 Streamlit 页面，README 加 3–5 张截图和 demo 复现说明。
   - 同步维护 `frontend/` Liquid Glass 静态工作台；保持其 UI 风格，但后续必须用 FastAPI/Parquet 契约替换 mock 数据。
3. P2：StatsBomb 事件动作价值层，先 xT，后 VAEP。
4. P3：评分模型重构，把 action value 作为增强维度接入；真实标签层稳定后，神经网络只能先作为候选模型与当前优化器同口径对比。
5. P4：模型评估文档和模型卡。补 `EVALUATION.md`（Spearman、时间切分、baseline、误差案例）和 `MODEL_CARD.md`（数据源、标签定义、适用边界、偏差、不可用场景）。
6. P5：Dixon-Coles 比分预测升级。
7. P6：跨供应商标准化和开放格式层，先做 schema、license manifest 和转换实验，不改变当前 pipeline。
8. P7：球探决策与人工校准层，把真实标签、低置信度样本和误差案例纳入 review queue、watchlist、shortlist。
9. P8：空间/视频/离球研究层，StatsBomb 360、Metrica/open tracking、xG+、off-ball value、强化学习只作为远期方向。

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

## 模块约定

- 现有包根目录是 `src/scoutlab/`。
- 现有命令入口是 `src/scoutlab/__main__.py`。
- 现有 pipeline 入口是 `src/scoutlab/pipeline.py`。
- 新增事件动作价值模块时使用 `src/scoutlab/action_value/`。
- 新增 internal actions schema 优先写入 `src/scoutlab/action_value/schema.py` 或 `src/scoutlab/schemas/`，并同步 `docs/DATA_CONTRACTS.md`。
- 新增神经网络评分候选模型时优先使用 `src/scoutlab/models/player_rating_nn.py` 或同级模块；训练脚本只做薄入口，不把核心逻辑堆在 `scripts/`。
- 新增模型运行登记优先写入 `data/reports/model_runs/` 或 `data/models/runs/`，必须保存 dataset snapshot、输入 hash、参数、随机种子、依赖版本和指标。
- 新增球探人工校准数据优先写入 `data/gold/feature_store/player_truth_labels.parquet`、`data/reports/review_queue/` 或等价本地产物；不要把人工标签和模型预测写进同一字段。
- 新增足球专用图表时优先扩展 `src/scoutlab/viz/`，不要把绘图逻辑堆进 Streamlit 页面。
- `frontend/` 是静态产品壳：保留 `frontend/index.html`、`frontend/style.css`、`frontend/app.js` 的 Liquid Glass 风格，页面只做本地展示和轻量交互，不在浏览器中执行训练、爬取或重型数据处理。
- `frontend/` 当前 mock 数据只能用于产品形态验证；接真实数据时先补 FastAPI read-only endpoint 和本地 Parquet 契约，再改前端 fetch。
- 前端长期视图和后端契约对应关系：
  - 总览：artifact registry、行数、产物更新时间、真实/代理/合成数据标记、license attribution。
  - 球员：player profile API、评分快照、位置内指标、低置信度原因、导出。
  - 身价：value-fairness OOF report、残差分层、手动身价导入边界。
  - 比赛预测：统一 prediction service、模型版本、coverage、log loss/Brier/RPS、比分矩阵。
  - 球探：review queue/watchlist/shortlist Parquet 契约，只读展示优先。
  - 动作价值：P2 action_value 产物稳定前只展示样例，不声称全量能力。
  - 报告：model-run registry、输入 hash、随机种子、参数、指标、误差案例。
- 新增评分特征矩阵模块使用 `src/scoutlab/features/rating_matrix.py`。
- 新增 coverage 置信度模块使用 `src/scoutlab/evaluation/coverage_confidence.py`。
- 新增出勤诊断模块使用 `src/scoutlab/evaluation/availability_diagnostic.py`。
- 新增位置内指标模块使用 `src/scoutlab/evaluation/position_metrics.py`。
- 新增统一置信度模块使用 `src/scoutlab/evaluation/confidence.py`。
- 新增真实标签契约模块使用 `src/scoutlab/evaluation/truth_labels.py`。
- 新增足球专用图表扩展 `src/scoutlab/viz/pitch.py`，使用 mplsoccer。
- Streamlit 页面只读本地产物，不直接执行重型训练。
- 训练产物写入 `data/models/` 或 `data/gold/feature_store/`，并保存 feature manifest、参数、随机种子和输入 hash。
- 数据合规和引用要求写入 data source license manifest；StatsBomb Open Data 衍生产物公开展示必须注明 StatsBomb。

## 技术默认值

Python, uv, DuckDB + Parquet, pandas, scikit-learn, Streamlit, Plotly, mplsoccer, pytest, Ruff。PyTorch 已用于评分优化/GPU 脚本；若把神经网络纳入主项目，必须同步更新 `pyproject.toml`、锁文件、训练入口、模型产物和评估文档。socceraction 是 P2 计划依赖候选；kloppy、floodlight、common-data-format-validator 只有进入 P6 且完成依赖评估后再加入 `pyproject.toml`。

## 验证命令

```bash
uv run ruff check .
uv run pytest
uv run pytest tests/unit/test_rating_optimizer_validation.py
PYTHONPATH=src uv run python -m scoutlab info
PYTHONPATH=src uv run python -m scoutlab validate
PYTHONPATH=src uv run python -m scoutlab ingest
PYTHONPATH=src uv run python -m scoutlab build-features
PYTHONPATH=src uv run python -m scoutlab train
uv run streamlit run src/scoutlab/app/streamlit_app.py
```
