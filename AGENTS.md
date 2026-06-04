# AGENTS.md

你是一个务实的 AI 开发助手。回答和开发都要直接、准确、可验证。

## 当前项目状态

Pipeline 端到端可运行：`scoutlab ingest` -> `scoutlab build-features` -> `scoutlab train`。当前文档真源是 `TASKS.md`，用户说明是 `README.md`，算法解释以 `ALGORITHM.md` 和后续 `MODEL_CARD.md` 为准。

本地缓存当前可验证状态：

- FBref：5 赛季标准、射门、misc 表均为 14,356 行。
- Football-Data：10 赛季、20 个 league/division，`combined_results.parquet` 当前为 68,953 个 match-key 行。
- Understat：10 赛季、6 个联赛，`players_10seasons.parquet` 当前为 31,902 个球员赛季行。
- StatsBomb Open Data：126 场比赛，`events_all.parquet` 当前为 11,871 条事件。
- 评分产物：`player_ratings_optimized.parquet` 当前为 27,254 行。

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
- `PROBLEMS.md` 中记录的问题只能算完成第一轮代码级防护；完整结论必须重新跑 GPU 优化和 2526 holdout 误差复盘后再写。

## 后续架构方向

未来更新按七层推进：

1. 数据与合规层：本地缓存、DuckDB、Parquet、手动导入和数据质量日志。
2. 标准事实层：比赛、球队、球员、阵容、事件、赛季统计、身价、联赛强度。
3. 事件动作价值层：StatsBomb events -> SPADL/atomic-SPADL -> xT -> VAEP。
4. 球员评分层：赛季统计 + xG/xA + xT/VAEP + 出勤可靠性 + 联赛强度 + 年龄/趋势 + 置信度。
5. 评估与模型卡层：`EVALUATION.md`、`MODEL_CARD.md`、position-wise metrics、误差分析。
6. 产品可视化层：Streamlit + Plotly；后续引入 mplsoccer 做球场图和足球专用图表。
7. 比分预测层：league average -> Independent Poisson -> Dixon-Coles + time decay。

## 当前优先级

1. P0：评分系统真实影响力标签和训练目标重构。
   - 近期先用新 availability cap 和稳健球队聚合重跑 GPU optimizer，并复盘 Everton/Stuttgart/Rennes/Napoli/Real Madrid/Arsenal/PSG 等误差案例。
   - 随后引入 Transfermarkt 手动导入、奖项、专家分档或人工校准集作为球员真实影响力标签。
2. P1：展示增强和可解释产品层，优先接入 mplsoccer。核心交付：球员雷达/排名页、身价偏离榜、比赛预测页 3 个可截图 Streamlit 页面，README 加 3–5 张截图和 demo 复现说明。
3. P2：StatsBomb 事件动作价值层，先 xT，后 VAEP。
4. P3：评分模型重构，把 action value 作为增强维度接入。
5. P4：模型评估文档和模型卡。补 `EVALUATION.md`（Spearman、时间切分、baseline、误差案例）和 `MODEL_CARD.md`（数据源、标签定义、适用边界、偏差、不可用场景）。
6. P5：Dixon-Coles 比分预测升级。
7. P6：kloppy、floodlight、xG+、tracking data 只作为远期方向。

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
- `goals - xG` 不能直接当射术；必须用样本量 shrinkage 或低置信度标记。
- Top N 位置配额不能替代真实影响力校准。
- availability 只是可靠性/样本量信号，不是球员能力本身；未经真实标签验证，不要把 availability cap 提回 0.25 以上。
- 球队赛季聚合不得回退为 raw minutes weighted mean；如果要改 aggregation，必须同时输出 holdout、联赛分层、误差案例和出勤置换重要性。
- 报告 position weights 时必须使用 capped weights，不要把 raw softmax 权重当作实际模型权重。
- 对 team coverage 低于 0.90 的 league-season，只能输出低置信度诊断，不要写成完整联赛排名或前四预测结论。
- 如果用户要求测试评分优化器，先在当前电脑小规模运行；未经用户明确允许，不要调用 Windows 5070 Ti 服务器。
- Dixon-Coles 是比分预测第二主线，不能抢在评分系统 P0/P1/P2 前面。

## 模块约定

- 现有包根目录是 `src/scoutlab/`。
- 现有命令入口是 `src/scoutlab/__main__.py`。
- 现有 pipeline 入口是 `src/scoutlab/pipeline.py`。
- 新增事件动作价值模块时使用 `src/scoutlab/action_value/`。
- 新增足球专用图表时优先扩展 `src/scoutlab/viz/`，不要把绘图逻辑堆进 Streamlit 页面。
- Streamlit 页面只读本地产物，不直接执行重型训练。
- 训练产物写入 `data/models/` 或 `data/gold/feature_store/`，并保存 feature manifest、参数、随机种子和输入 hash。

## 技术默认值

Python, uv, DuckDB + Parquet, pandas, scikit-learn, PyTorch, Streamlit, Plotly, pytest, Ruff。socceraction 和 mplsoccer 是后续计划依赖，只有进入对应 phase 时再加入 `pyproject.toml`。

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
