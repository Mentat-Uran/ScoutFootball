# AGENTS.md

你是一个务实的 AI 开发助手。回答和开发都要直接、准确、可验证，不铺垫，不夸张，不把未完成内容说成已完成。

## 项目真源

开始任何开发前先阅读：

1. `deep-research-report.md`：架构、数据源、模型路线和合规依据。
2. `TASKS.md`：当前 roadmap 真源。
3. `README.md`：项目定位、默认技术栈和使用说明。

如果三者冲突，优先级为：

1. 合规与数据权利约束。
2. `TASKS.md` 的当前阶段和验收标准。
3. `deep-research-report.md` 的架构分析。
4. `README.md` 的对外说明。

## 当前项目状态

当前仓库已完成 Phase 1 的基础骨架。可以假设已存在最小可运行的 Python 工程、测试目录和数据层目录占位，但不要假设已有真实数据源接入、DuckDB/Parquet 读写、业务特征或模型实现。

除非用户明确要求进入实现阶段，否则不要补完整业务代码，也不要越过 `TASKS.md` 当前阶段批量补齐后续业务模块。

## 技术默认值

- 语言：Python。
- 包管理器：`uv`。
- 本地数据层：DuckDB + Parquet。
- schema 与参数校验：Pydantic。
- 测试：pytest。
- 代码质量：Ruff。
- MVP 可视化：Streamlit + Plotly。
- 后续服务层：FastAPI。
- 后续生产存储：PostgreSQL。

FastAPI、PostgreSQL、权限控制、复杂调度、视频/跟踪数据属于扩展阶段，不要在 MVP 早期强行引入。

## 开发原则

- 按 `TASKS.md` 从前到后推进，不跳阶段。
- 每次实现一个小而稳定的切片。
- 优先实现可测试的纯函数和清晰 I/O，再接外部数据源。
- 外部依赖必须可 mock。
- 数据处理必须可复现、可缓存、可校验、可回溯。
- ETL 必须幂等，重复运行不能重复写入或污染结果。
- 所有模型训练必须记录数据版本、feature 版本、参数、指标和产物路径。
- 不把任何外部源 ID 直接当内部主键；使用 canonical ID + bridge table。
- 不把“球员水平”直接做成不可解释的单一神秘分数；保留表现分、市场分、匹配分和风格向量等分项。

## 数据源与合规边界

允许优先实现：

- StatsBomb Open Data：官方公开 JSON，作为事件流主源。
- Football-Data.co.uk：官方 CSV，作为结果和赔率基线。
- Club Elo：官方 API/CSV，作为球队强度时间序列。

谨慎实现：

- Understat：可作为 xG、xA、xGChain、xGBuildup 补充源，必须缓存、限速、校验字段。
- FBref：只作为低频标准表或赛程补充源，必须限速和缓存；不要把它作为 advanced 主源。

禁止实现：

- Transfermarkt 自动抓取。
- 绕过登录、验证码、Cloudflare、反爬或网站条款的采集逻辑。
- 高频请求受限网站。
- 公开分发受限制的原始缓存。
- 用项目支持赌博营销、规避服务条款或操纵性决策。

Transfermarkt 只能实现本地 CSV/Parquet 手动导入或明确授权数据导入。对应模块不得包含网络请求能力。

## 建议模块边界

后续实现时按以下接口边界组织，不要一次性补完整代码：

- `adapters/*`：数据源采集与手动导入。
- `entities/*`：名称标准化、球队/球员实体对齐、bridge table。
- `storage/*`：DuckDB/Parquet 读写。
- `features/*`：比赛、球员、球队、市场标签特征。
- `models/*`：身价合理性、转会匹配、Poisson/Dixon-Coles、风格 embedding。
- `evaluation/*`：时间序列回测、校准、模型报告。
- `viz/*`：Plotly 图表。
- `app/*`：Streamlit 页面。

## 测试要求

- 单元测试不能访问真实网络。
- adapter 测试使用 fixture 或 mock 响应。
- storage 测试验证幂等写入、主键去重、schema 校验和 metadata 记录。
- entity matching 测试必须覆盖重音、标点、同名球员、生日冲突、国家冲突。
- rolling feature 测试必须证明没有未来信息泄露。
- 模型测试必须包含简单基线，不能只报告复杂模型指标。
- 概率模型必须验证概率和、Brier/log loss/RPS 等指标中的至少一种。

## 文档要求

- 不把计划中的功能写成已经可运行。
- 新增命令前必须确保命令真实存在。
- README 面向使用者，TASKS 面向开发计划，AGENTS 面向后续 agent。
- 数据源风险、限制和合规策略必须在文档里保持一致。
