# 任务路线图

当前状态：Pipeline 端到端可运行，评分系统处于真实影响力标签和训练目标重构前的校准阶段。

本路线图吸收 `advise.md` 的建议，但只采纳适合 ScoutLab 当前数据现实的部分：优先做展示增强、StatsBomb 事件动作价值、评分验证和模型评估，不把后续更新变成更多爬虫。

## 顶层架构

ScoutLab 的长期形态是本地优先的足球数据研究平台，而不是数据抓取集合。后续架构按七层推进：

1. 数据与合规层：继续使用本地缓存、DuckDB 和 Parquet；Transfermarkt 只允许手动或授权导入；FBref 只作为受限低频补充源。
2. 标准事实层：把比赛、球队、球员、阵容、事件、赛季统计、身价和联赛强度统一到 raw/silver/gold/models/reports/logs 分层。
3. 事件动作价值层：以 StatsBomb Open Data 为第一主源，新增 `src/scoutlab/action_value/`，形成 StatsBomb events -> SPADL/atomic-SPADL -> xT -> VAEP 的演进路线。
4. 球员评分层：综合赛季统计、xG/xA、xT/VAEP、出勤可靠性、联赛强度、年龄和趋势；训练目标必须引入真实球员标签，不能只优化球队积分相关性。
5. 评估与模型卡层：建立 `EVALUATION.md`、`MODEL_CARD.md`、位置内指标、跨位置总榜指标、误差分析和数据覆盖说明。
6. 产品可视化层：Streamlit 保持本地只读；Plotly 继续用于交互图；后续引入 mplsoccer 做球场图、雷达图、pizza chart、shot map、pass map 和 xT heatmap。
7. 比分预测层：保持 Independent Poisson 作为基线，后续升级 Dixon-Coles + time decay，并用 log loss、Brier score、RPS 做对照。

## 采纳边界

立即采纳：

- mplsoccer 作为可视化增强库。
- socceraction 思路作为事件动作价值层的主要参考。
- xT 作为 VAEP 前的第一版可落地动作价值模型。
- VAEP 论文作为评分解释和动作价值建模的理论核心。
- Dixon-Coles 作为比分预测第二主线，但优先级低于球员评分。
- xG finishing signal 使用样本量 shrinkage，禁止简单用 `goals - xG` 判定射术。

暂缓采纳：

- kloppy 作为 v1.0 之后的跨供应商数据标准化方案。
- floodlight 只参考数据抽象，不直接引入。
- xG+ / possession-level shot probability 作为远期研究方向。
- Opta、Wyscout、SkillCorner、TRACAB 等商业或 tracking 数据源不进入近期计划。

不采纳：

- 新增绕过反爬或验证码的爬虫。
- 把 StatsBomb 小样本事件能力写成全量球员评分能力。
- 用 Top N 位置配额替代真实影响力校准。

## 已完成

- [x] 五类核心数据源接入：FBref、Football-Data、Understat、StatsBomb Open Data、Club Elo。
- [x] 本地缓存扩展到 10 赛季级别：Football-Data 当前 Parquet 为 68,953 个 match-key 行，Understat 为 31,902 个球员赛季行。
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
- [x] 重新生成 `player_ratings_optimized.parquet`。
- [x] 将 `advise.md` 融入未来架构和实施策略文档。

## P0：评分系统真实影响力校准

目标：先修训练目标，再扩展评分模型。当前球队积分相关性会偏向出勤、CM 和 GK，不能单独作为球员影响力标签。

- [ ] 定义真实标签层级：Transfermarkt 手动导入、权威奖项、国际/俱乐部出场级别、专家分档、位置内人工校准集。
- [ ] 新增标签数据契约和校验脚本，输出 `data/gold/feature_store/player_truth_labels.parquet`。
- [ ] 重写优化目标：组合 Spearman/NDCG、位置内排序、跨联赛校准、年龄/趋势合理性、极端样本惩罚。
- [ ] 保留球队结果相关性作为辅助校验，不再作为主目标。
- [ ] 将位置内榜单和跨位置总榜拆成两个视图。
- [ ] 给 GK、CB、FB、DM、CM、AM、W、ST 建立位置内指标和解释模板。
- [ ] 对 finishing 使用 shrinkage，避免小样本 `goals - xG` 过度放大。
- [ ] 输出评分模型卡，说明数据覆盖、权重、偏差、不可解释区域和低置信度球员。

验收：

- `uv run pytest tests/unit/test_rating_optimizer_validation.py`
- 生成新的评分产物和 holdout 报告。
- README、AGENTS、TASKS、MODEL_CARD 同步更新。

## P1：展示增强和可解释产品层

目标：先让当前评分、xG/xA、趋势和比赛事件变得可读，提升项目展示价值。

- [ ] 引入 mplsoccer 依赖并保持 Plotly 现有交互图不回退。
- [ ] 新增 `src/scoutlab/viz/pitch.py`，封装球场、坐标、shot map、pass map、heatmap 基础图。
- [ ] 做球员雷达图和 pizza chart，优先展示位置内 percentile。
- [ ] 做 Top 100 球员榜、球员详情页、评分趋势、身价散点的 README 截图素材。
- [ ] 在 Streamlit 增加“位置内榜单”和“跨位置总榜”切换。
- [ ] 增加低置信度提示：分钟不足、数据源缺失、位置重判不确定、事件样本不足。

验收：

- `uv run ruff check .`
- `uv run pytest`
- `uv run streamlit run src/scoutlab/app/streamlit_app.py`

## P2：StatsBomb 事件动作价值层

目标：先用公开事件数据完成一条可复现的动作价值链路，不引入商业数据源。

- [ ] 盘点 `events_all.parquet` 字段和坐标覆盖，写入事件数据覆盖说明。
- [ ] 新增 `src/scoutlab/action_value/` 模块：`spadl_adapter.py`、`xt.py`、`vaep.py`、`aggregate.py`。
- [ ] 第一版只做 StatsBomb events -> internal actions -> xT。
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
- [ ] 建立评分回归测试，防止 CM/GK/出勤捷径再次主导 Top 100。
- [ ] 输出 `ALGORITHM.md` 的实现对齐版本。

验收：

- 新旧评分有可解释对比。
- Top 100、位置内 Top 20、弱联赛顶端样本、低分钟球员均有审查报告。
- `MODEL_CARD.md` 更新。

## P4：模型评估文档和报告层

目标：把“能跑”升级为“可评估、可复现、可解释”。

- [ ] 新建 `EVALUATION.md`：数据切分、基线、指标、误差分析、置信度分层。
- [ ] 新建 `MODEL_CARD.md`：评分模型、身价模型、比分预测模型分别说明。
- [ ] 对评分系统增加 position-wise metrics。
- [ ] 对 value_fairness 增加 OOF 残差、联赛偏差、年龄段偏差分析。
- [ ] 对比分预测增加 log loss、Brier score、RPS。
- [ ] 每次训练保存 feature manifest、参数、随机种子、输入文件 hash。

验收：

- `scoutlab train` 产出模型报告或报告输入数据。
- 文档能解释当前模型不能做什么。

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

## P6：远期研究方向

这些方向只记录，不进入近期实施：

- kloppy：多 provider 事件/tracking 标准化。
- floodlight：参考 Game/Team/Player/Event/Frame/Segment 抽象。
- xG+：possession-level shot probability 和 possession threat。
- tracking data：Metrica、SkillCorner、TRACAB 等。

启动条件：

- P2 事件动作价值层稳定。
- P4 评估文档稳定。
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
