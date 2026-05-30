# ScoutLab 任务路线图

本文件是后续开发的 roadmap 真源。所有实现都应按小而稳定的切片推进，每个切片完成后再进入下一项。

当前状态：已完成 Phase 1–10 的首批实现。仓库已有 `pyproject.toml`、`src/scoutlab/`、`tests/`、`data/` 目录占位，以及 DuckDB 查询入口、Parquet 幂等写入、ingest metadata sidecar、`source_request_log` 结构、核心表定义草案、共享抓取缓存/限速/重试层、`StatsBomb Open Data`、`Football-Data.co.uk`、`Club Elo`、`Understat`、受限 `FBref`、`Transfermarkt manual importer`、名称标准化与球队/球员 bridge builder、`team_match`、`player_match`、`team_rolling`、`player_rolling` 特征第一刀、带时间序列切分与 OOF 预测的身价合理性 baseline，以及独立 Poisson 比分 baseline、比分概率矩阵和最小回测，以及 Streamlit + Plotly 交互式可视化 MVP（双球员雷达图、位置百分位条形图、趋势图、身价散点图、比分概率矩阵热图），以及 CLI 管线入口（`scoutlab info/ingest/build-features/train/validate/serve`）、数据校验层（Parquet 存在性/行数/日期范围/null key 检查）、概率校准（isotonic regression + Brier score）、日更/周度管线入口、FastAPI 服务层草案；但尚未接入真实数据端到端验证和扩展阶段。

## 全局验收原则

- 数据处理必须可复现、可缓存、可校验、可回溯。
- 外部请求必须可 mock，不能让测试依赖实时网络。
- ETL 必须幂等，重复运行不能重复写入或污染结果。
- 时间序列任务不能泄露未来信息。
- 模型必须有简单合理的基线对照。
- Transfermarkt 不进入自动抓取任务，只允许手动或授权导入。
- FBref 只作为受限补充源，不作为 advanced 主数据源。

## Phase 0 - 文档与项目初始化

优先级：P0

目标：建立后续开发的最低项目边界，避免在未定义约束下直接写业务代码。

交付物：

- `README.md`：项目定位、架构、数据源策略、技术默认值。
- `TASKS.md`：阶段任务、优先级、验收标准。
- `AGENTS.md`：面向 Codex/agent 的开发规则。
- 后续实现时再创建 `pyproject.toml`、`src/`、`tests/` 和数据目录。

验收标准：

- 三个文档都存在于项目根目录。
- 文档对 DuckDB/Parquet、Streamlit、P0 数据源、Transfermarkt 手动导入、FBref 受限使用的描述一致。
- 文档不声称当前已有可运行源码。

## Phase 1 - 项目配置与基础骨架

优先级：P0

目标：建立最小 Python 工程，可安装、可测试、可格式检查，但不接入真实数据源。

交付物：

- `pyproject.toml`，使用 `uv` 管理依赖。
- `src/football_data_platform/` 包结构。
- `tests/` 测试目录。
- Ruff、pytest、基础类型和配置。
- `data/` 目录占位规则，避免提交大型原始数据。

验收标准：

- `uv sync` 成功。
- `uv run pytest` 成功。
- `uv run ruff check .` 成功。
- README 中的命令与实际入口一致。

## Phase 2 - 数据湖与 schema

优先级：P0

目标：先定义数据落地方式和 schema，再接入具体数据源。

交付物：

- `raw/silver/gold` 数据层目录规范。
- DuckDB 连接与 Parquet 读写工具。
- Pydantic schema 或等价字段校验。
- `source_request_log` 和 ingest metadata 结构。
- 核心表定义草案：competition、season、team、player、match、team_match、player_match、event、bridge、market_snapshot。

验收标准：

- 可以把模拟 DataFrame 写入 Parquet 并通过 DuckDB 查询。
- 重复写入同一主键不会产生重复记录。
- 每次写入都有来源、时间、哈希和解析版本记录。

## Phase 3 - P0 数据源接入

优先级：P0

目标：先接入低风险、高价值、结构稳定的数据源。

交付物：

- StatsBomb Open Data adapter：比赛、阵容、事件 JSON 读取。
- Football-Data.co.uk adapter：比赛结果和赔率 CSV 下载/缓存。
- Club Elo adapter：按日期获取球队 Elo。
- 请求缓存、限速、错误重试和结构化异常。
- 外部请求 mock 测试。

验收标准：

- 每个 adapter 都能输出 DataFrame 和 source metadata。
- 网络失败时抛出结构化异常，不吞错。
- 测试不访问真实网络。
- 原始文件可缓存，重复运行优先读缓存。

## Phase 4 - P1/P2 数据源边界

优先级：P1

目标：以受控方式补充 Understat、FBref 和市场标签。

交付物：

- Understat adapter：读取球员/球队 xG、xA、xGChain、xGBuildup。
- FBref adapter：只读取低频标准表或赛程补充数据，必须限速和缓存。
- Transfermarkt manual importer：只从本地 CSV/Parquet 快照读取市场价值、合同和转会标签。
- 数据源风险说明写入 README 或单独 docs。

验收标准：

- Transfermarkt 模块没有任何网络请求能力。
- FBref 模块默认限速，且测试验证缓存路径。
- Understat 字段变化时能给出明确错误。

## Phase 5 - 实体对齐与 bridge table

优先级：P0

目标：建立内部 canonical ID，不把任意外部 ID 当作主键。

交付物：

- 球队名称标准化：大小写、重音、标点、后缀、国家别名。
- 球员名称标准化：大小写、重音、标点、空格。
- `bridge_source_team` 和 `bridge_source_player`。
- 确定性匹配规则：球队用 normalized name + country；球员用 normalized name + DOB + nationality。
- 模糊匹配规则：高置信度自动通过，中间区间进入人工复核，低置信度拒绝。

验收标准：

- 生日冲突的球员不会自动合并。
- 国家不一致的相似球队不会自动合并。
- bridge 记录包含 method、score、approved_by、approved_at。
- 抽样复核准确率达到报告中的 MVP 阈值：球队 >=98%，球员 >=95%。

## Phase 6 - 特征工程与 feature store

优先级：P0

目标：生成可复算、无未来泄露的基础特征。

交付物：

- `player_match`、`team_match`、`player_rolling`、`team_rolling` 特征。
- 出勤、进攻、expected metrics、球权价值、传球推进、防守、纪律、年龄曲线、联赛强度、球队状态等特征族。
- 缺失值策略：区分真缺失和源不覆盖，保留布尔指示列。
- 小样本分钟数 shrinkage。

验收标准：

- rolling 特征只使用当前比赛前可见数据。
- 每 90 分钟指标对低分钟样本做收缩或标记。
- Feature table 可按日期、赛季、球员、球队重算。
- 关键标签源缺失时不做虚假填补。

## Phase 7 - 身价合理性基线

优先级：P0

目标：建立第一个核心监督学习任务，先胜过简单基线。

交付物：

- `log1p(market_value)` 回归目标。
- 位置、年龄、联赛中位数基线。
- ElasticNet 或 HistGradientBoostingRegressor 基线模型。
- 时间序列切分与 OOF 预测。
- cheap/fair/expensive 分类标签。

验收标准：

- 训练只使用快照日前可见特征。
- 模型 MAE 优于位置 x 年龄段 x 联赛中位数基线。
- 输出残差、分类标签和模型评估摘要。
- 模型结果能回溯到数据版本和 feature 版本。

## Phase 8 - 比分预测基线

优先级：P1

目标：实现非核心但稳定可解释的比赛概率模型。

交付物：

- 独立 Poisson 模型。
- Dixon-Coles 模型或后续接口占位。
- 比分概率矩阵。
- 1X2、大小球、BTTS 概率汇总。
- 滚动时间窗回测。

验收标准：

- 比分概率矩阵总和为 1。
- 回测使用比赛日前可见数据。
- 输出 log loss、Brier、RPS 或等价概率指标。
- Poisson 基线在测试中稳定可复现。

## Phase 9 - Streamlit MVP

优先级：P1

目标：把研究结果变成可交互的本地分析界面。

交付物：

- 双球员对比页。
- 位置内百分位条形图。
- 球员/球队趋势图。
- 身价 vs 表现散点图。
- 比分概率矩阵展示。
- HTML/Markdown 报告导出原型。

验收标准：

- Streamlit 页面能在本地启动。
- UI 不依赖实时外部请求，只读取本地 Gold/Feature/Model 结果。
- 页面清楚展示数据版本、模型版本和更新时间。
- 报告导出不会缺图、缺表或引用不存在的路径。

## Phase 10 - 调度、回归测试与二阶段扩展

优先级：P2

目标：从单次研究脚本升级为可重复运行的平台。

交付物：

- 日更管线入口。
- 周度训练入口。
- 数据校验失败时阻止训练。
- 回归测试样本。
- PostgreSQL 同步脚本草案。
- FastAPI 服务层草案。
- 转会匹配、风格 embedding、SHAP、概率校准扩展任务。

验收标准：

- 日更任务可断点续跑。
- 周度训练只在数据校验通过后执行。
- 模型版本、数据版本、评估指标和报告可追溯。
- 扩展模块不破坏核心 tabular pipeline。

## MVP 推荐实现顺序

1. 文档与项目配置。
2. 数据目录与 schema。
3. DuckDB/Parquet 读写。
4. StatsBomb Open Data、Football-Data、Club Elo。
5. 球队和球员 bridge table。
6. 基础 feature store。
7. 身价合理性 baseline。
8. Poisson 比分 baseline。
9. Streamlit dashboard。
