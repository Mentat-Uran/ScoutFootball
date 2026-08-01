# ScoutFootball 前后端与核心能力审计及开发建议

**审计日期：** 2026-07-31  
**审计快照：** `codex/integration`，基线提交 `10d0ed8`  
**审计范围：** `frontend/`、FastAPI/API 门面、数据加载与本地存储、球员评级与研究健康链路、静态导出、测试与文档契约  
**文档性质：** 只读审计和开发规划，不代表下述改进已经实现

> 审计期间工作区存在正在进行的 `cohort_sensitivity` 相关未提交修改。本文没有评估这些修改是否完成，也没有把它们当作当前稳定能力。文件规模、路由数和测试数均是审计时点快照，后续应由自动化清单更新。

## 1. 结论

项目当前不是“功能太少”，而是已经具备大量分析、世界杯、球探工作流和研究端点，但核心真值、访问控制、数据来源状态和模块边界没有完全跟上功能宽度。下一阶段不应继续横向增加页面和评分模型，而应先关闭四个最高风险缺口：

1. **评级研究状态没有在主球员界面失效关闭。** 当前运行态研究健康为 `not_ready`，但主球员列表仍可把旧优化评分作为普通排名展示，容易把团队积分代理目标或未审阅模型误读为球员能力。
2. **静态快照可能被界面标成 LIVE。** Vercel/桌面静态优先流程会先展示静态 JSON，只要后台 `/health` 可访问，全局状态就可能变成 `LIVE/API OK`，即使当前可见数据并未被实时响应替换。
3. **本地写接口缺少统一访问门。** API 支持绑定 `0.0.0.0`，但除 scouting workspace 外，多数 POST/PUT/DELETE 路由没有统一的 loopback 或显式授权检查。CORS 不是访问控制。
4. **前后端核心文件过于集中且契约弱。** `frontend/app.js`、`api.py`、`api_server.py` 都承担过多职责；OpenAPI 约 206 个操作几乎没有业务响应 schema，修改只能依赖大量静态源码断言和人工同步。

推荐开发顺序是：

`真值与写入边界` → `统一响应/来源契约` → `评级垂直切片` → `前后端拆分` → `性能与测试分层` → `继续 PRS-4 以后功能`

这不是一次“大重写”。应通过兼容适配层逐步抽出数据访问、领域服务和评级读模型，每一步都保持现有本地工作流可用。

## 2. 当前架构与事实边界

```text
外部/本地数据源
  StatsBomb / Transfermarkt / ClubElo / 手工标签 / 本地工作区
                         │
                         ▼
数据管线与派生物
  Parquet / JSON / 模型运行记录 / 特征清单 / DuckDB（可选）
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
       src/scoutfootball/api.py   静态 JSON 导出
       领域查询与兼容门面          Vercel/离线读取
              │                     │
              ▼                     │
       api_server.py / FastAPI ─────┤
              │                     │
              └──────────┬──────────┘
                         ▼
              frontend/app.js 单页工作台
              桌面壳 / 浏览器 / 静态站点
```

当前架构的优点是本地优先、数据来源覆盖广、已有较多验证和证据字段，并且部分本地工作区存储已经具备 schema 校验、修订号、原子替换和锁。问题主要发生在各层交界处：

- “文件存在”与“可形成可信结论”之间缺少统一门；
- “API 可达”与“当前数据来自 API”被混为一谈；
- 读端、写端、静态端使用相近但不完全统一的契约；
- 前端页面直接理解过多后端领域细节；
- 核心链路与大量外围功能共享超大文件，导致回归半径过大。

### 2.1 审计时点的量化快照

| 项目 | 审计值 | 含义 |
|---|---:|---|
| `frontend/app.js` | 约 28,166 行 | 数据访问、状态、i18n、路由、渲染和工作流集中 |
| `src/scoutfootball/api.py` | 约 13,501 行 | 多个领域查询、缓存、数据读取和兼容逻辑集中 |
| `src/scoutfootball/api_server.py` | 约 2,370 行 | 约 200 个 API 函数导入和路由注册集中 |
| OpenAPI | 196 paths / 206 operations | API 面已经很宽 |
| Python 测试文件 | 175 | 覆盖面较大，但默认测试分层不清晰 |
| 前端 Node 测试文件 | 4 | 与前端体量不匹配 |
| 全量 pytest 收集 | 5,865 项 | 只证明可收集，不等于全量通过 |

## 3. 问题优先级总表

| 编号 | 优先级 | 问题 | 直接后果 | 建议首先改什么 |
|---|---|---|---|---|
| CORE-001 | P0 | `research_health=not_ready` 未约束主评级展示 | 未审阅评分被当作球员能力或可靠排名 | 建立评级读模型并在 API/UI fail closed |
| FE-001 | P0 | 静态数据可能显示为 LIVE | 用户无法判断当前页面证据的新鲜度和来源 | 改为逐资源 provenance 状态 |
| SEC-001 | P0 | 多数写接口无统一 loopback/授权门 | LAN 暴露时可被同网段调用，造成持久化修改或资源消耗 | 所有写路由接入统一依赖 |
| CORE-002 | P0 | 主球员画像仍依赖名字匹配且缺失值回填 0/50 | 同名、多赛季、缺失数据会被错误合并或平均化 | 使用 canonical player key，缺失保持 null |
| API-001 | P1 | OpenAPI 缺少业务 request/response schema | 前端、静态导出和后端容易悄然漂移 | 先给核心垂直切片增加 Pydantic 契约 |
| ARCH-001 | P1 | 前后端超大单体文件 | 小修改回归半径大，难并行开发 | 按领域逐步抽模块，不一次性重写 |
| PERF-001 | P1 | 启动同步预热、首页急切加载、回测串行请求 | 冷启动和首屏慢，局部页面拖累全局 | 健康端点先就绪，按视图懒加载 |
| DATA-001 | P1 | DuckDB/Parquet 来源优先级和健康判断未统一 | 同一运行中不同路径可能看到不同事实 | 建立 active storage resolver |
| TEST-001 | P1 | 默认 pytest 会收集 E2E，与文档说明不一致 | 本地/CI 时间和环境依赖不可预测 | 默认排除 E2E，独立 job 执行 |
| FE-002 | P1 | 战术板 hover 使用未转义标签拼接 `innerHTML` | DOM 内容注入；CSP 只能降低脚本执行风险 | 使用 `textContent`/节点构建 |
| DOC-001 | P1 | 任务状态、能力文档和实现存在语义矛盾 | 后续开发可能从错误前提开始 | 自动生成快照并明确验收门 |
| UX-001 | P2 | 页面状态不进入 URL/history | 刷新丢页面，无法深链和可靠复现 | 增加 hash/router 状态 |
| MAINT-001 | P2 | TestClient 依赖出现弃用告警 | 将来的依赖升级可能集中爆发 | 单独安排兼容升级 |

## 4. 前端问题分析

### 4.1 FE-001：LIVE / STATIC / OFFLINE 状态不可信

`frontend/app.js` 的静态优先读取逻辑会先返回静态 JSON，同时后台尝试 API。后台请求成功时只修改全局 `apiOnline`；它没有把已经展示的数据替换为 API 响应，也没有稳定记录该资源来自静态文件。后续 `/health` 成功又可能把 `usingStaticData` 设为 false。

因此会出现：

```text
页面数据：static_data/*.json
健康请求：/health 成功
界面状态：LIVE / API OK
```

这不是纯视觉问题，而是证据边界问题。评级、数据健康、模型运行和世界杯状态都可能被误判为当前实时结果。

此外，首页同时发起多个请求，而来源状态使用全局布尔值；某个请求的回退或成功会覆盖其他请求的来源判断。一个页面同时展示实时数据和静态数据时，单个全局灯无法准确表达。

**建议契约：**

```json
{
  "data": {},
  "provenance": {
    "source": "live|static|local-cache|unavailable",
    "as_of": "ISO-8601|null",
    "endpoint": "/ratings",
    "snapshot_id": "string|null"
  },
  "error": null
}
```

**验收标准：**

- 每个可见卡片或数据集保留自己的 `source` 和 `as_of`；
- 使用静态响应时绝不能显示 LIVE；
- API 后台刷新只有在新响应真正写入当前视图后，才能把该资源切换为 LIVE；
- 混合来源页面显示 `MIXED`，并能展开看到每个资源的来源；
- 为 API 成功、API 失败、静态成功、静态失败、竞态返回和视图卸载增加测试。

### 4.2 CORE-001：主球员界面绕开研究就绪门

运行态检查结果为：

```text
research_health.verdict = not_ready
lineage_health          = unverified
model_reviewability     = no_reviewable_runs
active_rating_freshness = unverified
research_readiness      = blocked
```

但主球员列表仍主要读取旧的 optimized rating，并按正常评分展示。当前 `detailed health` 前端也没有完整渲染 `research_health`；旧概览对“真实标签可用”的判断更接近“标签文件存在”，不能区分独立人工标签和派生的 `expert_tier`。

这会造成两个误导：

- 代理目标训练出来的评分被用户理解成独立验证过的球员能力；
- “有标签文件”被理解成“已有可用于模型准入的真实标签”。

**建议引入评级读模型，不让页面直接组合多个旧端点：**

```json
{
  "rating": 67.2,
  "rating_status": "blocked|candidate|admitted",
  "rank_eligible": false,
  "model_role": "baseline|challenger|active",
  "research_readiness": "blocked",
  "blockers": ["no_reviewable_runs", "independent_labels_missing"],
  "evidence_grain": "player_season",
  "feature_manifest_hash": null,
  "input_hash": null,
  "missing_fields": ["..."]
}
```

**界面规则：**

- `blocked`：允许浏览事实和特征覆盖，不显示强排名结论；
- `candidate`：明确写“研究候选”，不能称为当前评级；
- `admitted`：只有通过既定模型准入、可复核性和新鲜度检查后才能排序并称为当前评级；
- 评级缺失显示 `—` 和原因，不显示 0、50 或“平均”；
- 标签面板分别显示“独立标签数”和“派生标签数”。

### 4.3 CORE-002：主画像仍使用名字和模糊匹配

项目已经有 canonical identity / resolver 方向，但主要球员画像 API 和前端仍以名字为重要查询键，并可能从同名记录中选择最高评分。对于同名球员、同一球员多个赛季、转会前后不同球队，这会造成静默合并。

同时，画像计算中存在以下语义：

- 特征缺失时通过 `row.get(..., 0)` 或 `fillna(0)` 进入雷达图；
- 无有效对比池或数值为空时，百分位可能回到 50；
- xT 等扩展证据仍可能通过名字拼接，而不是 canonical key。

这些默认值让“未知”看起来像“平均”或“表现为零”，属于核心数据语义错误。

**目标：**

- 所有主查询使用 `player_key + season + competition/team context`；
- 只允许显示名用于搜索和展示，不作为最终 join key；
- 无法唯一解析时返回 `ambiguous` 和候选列表，不自动选最高分；
- 数值缺失保持 `null`，同时返回 `missing_reason`；
- 雷达图只画有效维度，并显示覆盖率；
- 排名接口排除 `rank_eligible=false` 的记录。

### 4.4 ARCH-001：`app.js` 同时承担过多职责

当前单文件包含：

- 大段中英文 i18n 字典；
- API/静态读取和全局来源状态；
- 约 24 个视图的切换与渲染；
- 球员、球队、回测、世界杯、战术板、本地工作区等领域逻辑；
- 对话框、导入导出、图表和错误处理。

扫描中还可见大量 `innerHTML`、事件绑定和内联样式。这并不自动等于安全漏洞，但使“字段是否已经 escape”“事件是否重复绑定”“视图切换后异步响应是否仍有效”等问题难以局部证明。当前 4 个 Node 测试文件、40 项测试与前端规模不匹配。

**不要直接重写整个前端。** 按 ADR 所指方向先抽最稳定的缝：

1. `frontend/js/data-client.js`：只负责 API、静态回退、超时、取消和 provenance；
2. `frontend/js/view-router.js`：视图、URL/hash、进入/离开生命周期；
3. `frontend/js/rating-view-model.js`：评级状态、缺失语义和展示门；
4. `frontend/js/safe-dom.js`：统一文本节点、属性和受控模板；
5. 之后再按 `players/`、`research/`、`world-cup/` 等领域迁移。

每抽出一个模块，都保留原有入口的兼容调用，先迁移测试覆盖高、契约清晰的路径。

### 4.5 FE-002：战术板 hover 标签存在 HTML 注入

战术板 renderer 把导入项目中的 `label` 拼到 `innerHTML`。现有 `_safeString` 主要限制类型、长度和控制字符，并不等价于 HTML escape。CSP 可以降低内联脚本执行概率，但不能保证 DOM 结构和显示内容不被注入。

**修复要求：**

- hover 卡片用 DOM API 创建，动态标签只写入 `textContent`；
- 导入值 `<img src=x onerror=...>`、`</div><div>`、双向控制字符都应按纯文本显示或拒绝；
- 保留 CSP，但不把 CSP 当作 escape 的替代品；
- 增加真实 DOM 测试，而不只做源码字符串断言。

### 4.6 PERF-001：首屏和重页面加载策略不合理

初始化阶段会请求大量与当前首屏无关的数据；世界杯初始化也较早开始。回测视图还会依次等待多个可能耗时 30–60 秒的端点。结果是：

- 首屏被后台功能拖慢；
- API 失败时产生大量重复超时；
- 用户离开页面后，旧请求仍可能回写 DOM；
- 回测页面越加功能越慢。

**改进：**

- 首屏只加载当前视图需要的数据和轻量健康摘要；
- 每个 view 拥有 `AbortController`，离开时取消请求；
- 重型回测数据按面板展开后加载；
- 可并行且独立的请求使用受控并发；
- 后端提供轻量 summary，而不是让前端拼接多个全量诊断；
- 对首屏请求数、JS 解析时间和关键 API 延迟建立可重复基线。

### 4.7 UX-001：缺少可复现的导航状态

`setView` 主要修改内存和 DOM，没有把当前页面、筛选条件和选中对象写入 URL/history。刷新、后退和分享链接不能稳定回到同一研究上下文。

建议先实现：

```text
#/players?player_key=...&season=...&competition=...
#/research/runs/<run_id>
#/backtests?panel=stability
```

只把非敏感、可重建状态放进 URL。本地工作区正文和手工笔记仍保留在本地存储。

## 5. 后端问题分析

### 5.1 SEC-001：写端访问控制不完整

审计时 OpenAPI 中约有 21 个实际变更操作。scouting workspace 路由使用了 `_require_workspace_access`，但世界杯结果/重置/导入、brief/dossier/review 的创建更新恢复、本地 pack 导入、战术板 MP4 导出等写路径没有统一接入同一保护。

当服务只绑定 `127.0.0.1` 时风险有限；一旦用户按现有能力绑定 `0.0.0.0`，同一局域网中的客户端可能调用这些端点。浏览器 CORS 只能限制部分跨源浏览器请求，不能限制 curl、脚本、同源页面或服务端请求。

同时，CORS 允许方法列表只包含 GET/POST/OPTIONS，而 API 实际存在 PUT/DELETE。这会导致允许的跨源前端可以读取和创建，却无法稳定更新或删除。

**统一策略：**

- 所有产生持久化修改、文件输出或高成本任务的路由标记为 `write`；
- 默认只允许 loopback；
- 非 loopback 访问必须由用户显式开启，并使用本地密钥或等价的短期授权；
- CORS 从显式配置生成，并覆盖实际需要的方法；CORS 不承担授权；
- 通过路由元数据测试确保新增写路由不能漏掉 guard；
- 审计日志只记录必要元数据，不写入隐私内容。

### 5.2 战术板 MP4 导出需要单独加固

当前端点先把整个请求体读入内存，再检查约 50 MB 限制，并调用 ffmpeg 处理不可信输入。异常和超时路径的临时文件清理不完整，错误响应可能包含本地绝对路径或 ffmpeg 片段，且部分失败仍返回 HTTP 200。

**建议：**

- 流式读取并在传输过程中实施上限；
- 接入统一 write guard 和并发限额；
- 使用随机临时目录和 `finally` 清理；
- 校验容器、帧率、分辨率、时长和像素总量；
- 输出使用随机 ID，下载端点映射 ID，不暴露绝对路径；
- 失败返回一致的 4xx/5xx error envelope；
- 对超时、畸形输入、并发、清理和路径泄露增加测试。

### 5.3 API-001：OpenAPI 基本没有业务 schema

约 206 个操作中，没有发现稳定使用的业务 `response_model`；200 响应大多在 OpenAPI 中显示为 `{}`。写接口也常直接读取 `request.body()` 后手工解析 JSON。

后果：

- OpenAPI 不能作为前端或工具生成的可靠契约；
- 字段删除、null 语义变化和错误结构变化难以及时发现；
- 静态导出需要再维护一套隐式 schema；
- 单元测试越来越依赖源码文本和样例快照。

不建议一次给 206 个端点补 schema。优先为这三个垂直切片建立范式：

1. `/health/detailed` 与 `research_health`；
2. 评级列表、评级详情和 canonical player profile；
3. 一个带 revision/conflict 的本地工作区写流程。

应统一：

- `data / meta / provenance / error` 响应 envelope；
- `missing`、`no_data`、`blocked`、`ambiguous` 的状态枚举；
- 错误码、HTTP 状态和用户可见消息；
- 时间、版本、hash、来源字段；
- Pydantic request/response model 和 OpenAPI contract snapshot。

### 5.4 ARCH-001：`api.py` 和 `api_server.py` 领域边界不清

`api_server.py` 从 `api.py` 导入大量函数，并在一个 `create_app` 中注册大批路由。`api.py` 同时处理：

- 文件/DuckDB 读取；
- 缓存；
- 领域聚合；
- 兼容字段；
- 健康状态和诊断；
- 大量世界杯、模型与球探功能。

建议目标结构：

```text
src/scoutfootball/
  api/
    app.py
    envelopes.py
    dependencies.py
    routers/
      health.py
      ratings.py
      players.py
      research.py
      workspaces.py
      world_cup.py
  services/
    rating_read_model.py
    player_profile.py
    research_health.py
  repositories/
    artifact_repository.py
    workspace_repository.py
    storage_resolver.py
```

拆分原则：

- router 只做输入校验、依赖注入和 HTTP 映射；
- service 实现领域规则，不依赖 FastAPI Request；
- repository 统一 DuckDB/Parquet/JSON 的选择和读取；
- 旧 `api.py` 先作为兼容 facade，再逐步缩小；
- 每迁移一组路由，比较旧新 JSON 和 OpenAPI，不同时改业务语义。

### 5.5 DATA-001：DuckDB 与 Parquet 活跃来源不统一

审计环境中的 `scoutlab.duckdb` 存在但没有业务表，部分加载路径会先尝试 DuckDB，记录带 traceback 的 warning 后回退 Parquet；健康检查和其他路径又可能直接检查 Parquet。当前回退能工作，但存在三个问题：

- 正常的“可选存储未初始化”产生高噪声日志；
- 不同端点对“当前活跃数据”的判断可能不同；
- 将来 DuckDB 局部更新后，旧 Parquet 与新表可能同时存在，来源优先级不透明。

建议建立单一 `StorageResolution`：

```json
{
  "backend": "parquet",
  "location": "data/derived/...",
  "version": "...",
  "as_of": "...",
  "fallback_reason": "duckdb_table_missing"
}
```

CLI、健康检查、API 和静态导出都使用同一个 resolver。预期回退记为 info；真正损坏、schema 不匹配或读失败才记 warning/error。

### 5.6 启动阶段同步预热阻塞就绪

FastAPI lifespan 中存在同步缓存预热，相关测试/注释允许冷启动达到几十秒。桌面壳和 E2E 因此需要很长等待。健康检查应表达“服务进程已就绪”和“重型数据已预热”两个不同事实。

建议：

- `/health/live` 只检查进程；
- `/health/ready` 检查核心依赖，但设置明确预算；
- 重型世界杯/模型缓存后台预热；
- 首次使用端点可返回 `warming`，而不是阻塞整个应用启动；
- 记录预热耗时、缓存版本和失败原因。

## 6. 核心数据与评级链路问题

### 6.1 当前最重要的不是再训练一个模型，而是统一“什么可以被称为评级”

当前项目同时保留旧 optimized rating、代理目标、特征矩阵、基线/候选模型、标签台账和研究健康。这些组件分别有价值，但主产品读取链路没有统一回答：

- 当前 active model 是谁；
- 它是否 reviewable；
- 特征、输入和训练代码能否复现；
- 独立标签是否足够；
- 数据是否过期；
- 该评分是否允许排名；
- 该数字属于事实、模型输出还是派生代理。

应建立唯一的 `RatingAdmission` 状态机：

```text
artifact exists
      │
      ▼
lineage verified ──否──> blocked
      │是
      ▼
reviewable run ───否──> blocked
      │是
      ▼
independent evaluation eligible ──否──> candidate/research-only
      │是
      ▼
freshness + stability + error review passed
      │
      ▼
admitted active rating
```

现阶段运行态处于 `blocked/not_ready`，所以 UI 和导出都应 fail closed，而不是仅在健康页放一个告警。

### 6.2 独立标签与派生标签必须分账

当前有大量旧标签记录，但独立、可用于准入评估的标签仍为 0。文件存在或行数大不能证明有独立监督。后续开发应：

- 在 API/UI 同时显示 `independent_count`、`derived_count`、`eligible_count`；
- 盲评 UI 必须真正隐藏模型评分和派生建议，而不只是 schema 中有 `blind` 字段；
- 导入协议记录来源、评价者、时间、量表版本、冲突和撤销；
- 没有独立标签时，不允许把 B3 或类似监督模型标为已验证；
- PRS-4 及以后能力继续受 PRS-2/PRS-3 验收门约束。

当前任务文档中“blind UI 尚未实现”与“blind mode 已满足”的描述存在语义冲突，应以“真实操作过程中评分不可见并有测试证明”为完成标准。

### 6.3 基线 B0 的“全缺失 = 50 分”应改为不可排名

如果核心特征全部缺失，给出 50 分和低置信度仍会让该球员进入排序或被理解为平均水平。更合理的输出是：

```json
{
  "rating": null,
  "status": "insufficient_evidence",
  "rank_eligible": false,
  "coverage": 0.0,
  "missing_reason": "all_core_features_missing"
}
```

低覆盖但仍有证据的记录可以保留分数，同时明确 coverage、置信度和可比较人群；完全无证据不应生成中位数。

### 6.4 数据粒度必须进入所有比较与导出

球员评分、xT/VAEP、比赛行为、赛季代理和世界杯名单数据的粒度不同。前端目前已经有部分 `evidence_grain` 字段，但还没有成为统一的比较门。

任何排序、对比和导出都应至少携带：

- `player_key`；
- `season`；
- `competition`；
- `team context`；
- `evidence_grain`；
- `minutes/sample_size`；
- `source`；
- `as_of`；
- `model_run_id` 或 `artifact_hash`。

粒度不同的指标可以并列展示，但不能自动合并成同一能力结论。

## 7. 测试、CI 与文档治理

### 7.1 已有测试很多，但分层和前端运行时覆盖不足

本次验证：

- `node --test frontend/tests/*.test.js`：40/40 通过；
- 前端安全、前端功能契约、静态 JSON 契约和 API 端点定向 pytest：914 项通过；
- 全量 pytest：成功收集 5,865 项，未执行全量测试；
- 存在 Starlette TestClient/httpx 兼容弃用告警。

这些结果证明当前定向契约没有被本次只读审计破坏，但不证明所有运行时交互、浏览器安全和全量回归都通过。

### 7.2 TEST-001：默认测试实际上包含 E2E

E2E 文档/注释倾向于表达“默认 pytest 不运行 E2E”，但当前配置没有默认排除 `e2e` marker；全量收集包含 48 项浏览器 E2E。CI 使用 `uv run pytest` 时，也会受到浏览器、服务启动和长等待影响。

建议分成：

```text
pytest -m "not e2e"                 # 默认、本地、PR 必跑
pytest tests/integration -m "not e2e"
pytest -m e2e                       # 独立 job，明确浏览器与服务依赖
node --test frontend/tests/*.test.js
```

验收标准：

- 默认命令的选择规则与文档一致；
- CI 分别显示 unit/integration/e2e/frontend；
- E2E 失败不被误报成纯单元测试失败；
- 每个 job 有独立超时和产物；
- 收集数量由脚本生成，不手工写死在能力文档。

### 7.3 前端测试下一批重点

优先增加：

1. provenance 状态机和多请求竞态；
2. `research_health=not_ready` 时主评级不排序；
3. canonical identity 的同名、多赛季和 ambiguous 情形；
4. 缺失值不被转换为 0/50；
5. 战术 hover 标签按文本渲染；
6. 视图卸载取消请求；
7. URL 深链和前进/后退；
8. API/静态 schema 兼容；
9. 一条真实浏览器评级垂直流程，而不是只做源码扫描。

### 7.4 DOC-001：文档需要从手工状态表转向可验证快照

当前 `TASKS.md`、`CAPABILITIES.md`、`FRONTEND_STATUS.md`、评级计划和实际代码在数量及完成语义上会漂移。建议：

- 路由数、测试数、静态文件数、模型运行数自动生成；
- 能力表把 `implemented`、`verified`、`runtime accepted` 分开；
- 每项 PRS 任务带命令、产物、hash 和停止条件；
- 文档中“已支持 blind mode”必须对应 UI 行为测试；
- 静态 manifest、API schema 和前端消费契约在 CI 同步检查。

## 8. 推荐目标架构

目标不是引入 SaaS、账号系统或云同步，仍保持本地个人研究工具定位。

```text
┌──────────────────────── Frontend ────────────────────────┐
│ View modules → View models → Data client                 │
│                            │                              │
│             ResourceResult<T> + provenance               │
└────────────────────────────┼──────────────────────────────┘
                             ▼
┌────────────────────────── FastAPI ────────────────────────┐
│ Domain routers → Pydantic contracts → shared dependencies│
│                                   write guard / errors    │
└────────────────────────────┼──────────────────────────────┘
                             ▼
┌──────────────────────── Services ─────────────────────────┐
│ RatingReadModel | PlayerProfile | ResearchHealth          │
│ WorldCup | Workspace                                      │
└────────────────────────────┼──────────────────────────────┘
                             ▼
┌────────────────────── Repositories ───────────────────────┐
│ StorageResolver → DuckDB / Parquet / JSON / local stores  │
│ artifact lineage + canonical identity + revision          │
└───────────────────────────────────────────────────────────┘
```

跨层不变量：

- 未知值保持未知；
- 来源和时间随数据一起传递；
- `not_ready` 在主路径 fail closed；
- 写操作默认仅本机；
- 同一实体使用 canonical key；
- 静态导出与 API 使用同一 schema；
- 任何“通过”都区分静态检查、测试通过和运行态准入。

## 9. 可直接进入开发的工作包

### WP-01：统一本地写入保护

**优先级：** P0  
**主要文件：** `api_server.py`、新的 API dependencies、相关写路由测试  
**依赖：** 无

任务：

- 建立 `require_local_write_access`；
- 给所有 POST/PUT/DELETE 和文件生成任务分类；
- preview/纯计算 POST 可显式标为 read-like，不能靠方法名猜测；
- 增加路由清单测试，新增写路由漏 guard 时 CI 失败；
- 修正 CORS 配置，使其与授权策略分离。

验收：

- 默认配置下，非 loopback 的所有写请求返回 403；
- loopback 保持现有工作流；
- 显式 LAN 写入开关有测试和警告；
- 不泄露绝对路径和内部异常。

停止条件：

- 如果某路由是否持久化无法判断，先标记为 write 并阻断，不默认放行。

### WP-02：逐资源数据来源契约

**优先级：** P0  
**主要文件：** `frontend/app.js`、新 `data-client.js`、静态 manifest/API envelope  
**依赖：** 可与 WP-01 并行

任务：

- 定义 `ResourceResult<T>`；
- API、静态回退和本地缓存都返回 provenance；
- 取消全局 `apiOnline/usingStaticData` 作为数据真值；
- 当前卡片显示自己的来源和 `as_of`；
- 修复静态优先后台刷新逻辑。

验收：

- 静态数据永不显示 LIVE；
- 混合来源可见且可解释；
- 并发请求顺序不影响最终来源标签；
- API 刷新只有发布新数据后才切换状态。

### WP-03：评级 fail-closed 垂直切片

**优先级：** P0  
**主要文件：** research health、rating service、rating routes、球员列表/详情  
**依赖：** WP-02 的最小 envelope

任务：

- 建立 `RatingReadModel`；
- 合并 admission、reviewability、freshness、lineage 和标签资格；
- 主球员 API 返回 `rank_eligible` 和 blockers；
- 主 UI 遵循 blocked/candidate/admitted 状态；
- 健康页完整展示 `research_health`。

验收：

- 当前 `not_ready` 环境中，主页面不产生强排名结论；
- 独立标签与派生标签分开；
- blocked 原因从 CLI、API 到 UI 一致；
- 静态导出也保留相同门，不因离线而放宽。

停止条件：

- 未获得独立评估或可复核运行时，不把候选模型提升为 active。

### WP-04：canonical player profile 与缺失语义

**优先级：** P0/P1  
**主要文件：** identity resolver、player profile service/API、球员 UI  
**依赖：** WP-03 的评级读模型

任务：

- 新增 canonical key 路由；
- 名字查询只返回 resolver 结果；
- 同名、多赛季、多球队返回明确上下文；
- 所有缺失保留 null 和原因；
- 雷达/排名尊重 coverage 与 `rank_eligible`。

验收：

- 同名球员不静默合并；
- 全核心特征缺失不返回 50；
- API、CSV 和 UI 的缺失语义一致；
- xT/VAEP 关联不再以裸姓名为最终 join。

### WP-05：核心 API 契约与路由拆分

**优先级：** P1  
**主要文件：** 新 `api/routers`、`api/envelopes.py`、Pydantic models  
**依赖：** WP-01、WP-03 已确定范式

任务：

- 先迁移 health/ratings/players；
- 为 request、response、errors 定义 schema；
- 旧函数保留 facade；
- 对旧新响应做 golden/contract comparison；
- 生成并检查 OpenAPI snapshot。

验收：

- 目标路由在 OpenAPI 有非空业务 schema；
- null、enum、时间和错误状态可机器验证；
- 兼容期内旧前端不破坏；
- router 中不再包含数据读取和业务聚合。

### WP-06：前端数据层与视图生命周期拆分

**优先级：** P1  
**主要文件：** `frontend/js/data-client.js`、`view-router.js`、第一批 view modules  
**依赖：** WP-02，最好在 WP-05 核心契约稳定后扩展

任务：

- 抽数据客户端；
- 增加 view enter/leave 和请求取消；
- 先迁移评级/研究健康页面；
- 增加 URL/hash；
- 逐步外移 i18n 和领域渲染。

验收：

- `app.js` 不再是新功能的默认落点；
- 首个迁移视图不读取全局来源布尔值；
- 离开视图后响应不回写；
- 深链、刷新和后退可恢复页面。

### WP-07：战术板输入与媒体导出加固

**优先级：** P1  
**主要文件：** tactical renderer、MP4 route、媒体处理测试  
**依赖：** WP-01

任务：

- 动态标签使用 text node；
- 上传改为流式上限；
- 临时目录统一清理；
- 输出 ID 化；
- 规范错误状态和并发限制。

验收：

- 恶意 HTML 作为文本显示；
- 超限请求不会先占用完整内存；
- 成功、失败、超时后均无残留临时文件；
- 响应不包含本机绝对路径。

### WP-08：测试分层、性能预算和文档自动化

**优先级：** P1  
**主要文件：** `pyproject.toml`、CI、测试文档、能力快照脚本  
**依赖：** 可以早做，但最终预算需结合 WP-05/06

任务：

- 默认排除 e2e；
- 拆 CI job；
- 建立 `/health/live`、`/health/ready`；
- 首屏按视图懒加载；
- 自动生成路由、测试、静态 manifest 数量；
- 处理 TestClient 依赖弃用。

验收：

- 默认测试与文档一致；
- E2E 有独立环境和超时；
- `/health/live` 不等待重型缓存；
- 首页不请求当前视图无关的大型端点；
- 能力文档中的数量由脚本生成。

## 10. 建议迭代顺序

### 迭代 0：冻结真值边界

- 完成 WP-01、WP-02 的最小版本；
- 主 UI 明确 STATIC/LIVE；
- 所有写路由有统一分类；
- 不增加新评分或新页面。

### 迭代 1：完成可信评级垂直切片

- WP-03、WP-04；
- 从 canonical identity 到 rating admission 再到 UI 一条链打通；
- 把当前 `not_ready` 如实展示并约束排序。

### 迭代 2：建立可持续模块边界

- WP-05、WP-06；
- 先 health/ratings/players，再迁移世界杯和工作区；
- 不做全量重写。

### 迭代 3：性能、安全细化与回归体系

- WP-07、WP-08；
- 建立冷启动、首屏、重型端点和浏览器交互基线；
- 把文档计数改为自动生成。

### 迭代 4：恢复 PRS 后续能力

只有当 PRS-2、PRS-3 的独立标签、真实 blind UI、评级语义和 GK/分位置基础满足验收后，才继续 PRS-4 及后续模型能力。否则继续增加模型只会扩大“有输出、无准入”的面积。

## 11. 暂时不要做的事情

- 不要一次性重写 `app.js` 或 `api.py`；
- 不要把缺失值继续填成 0 或 50；
- 不要用“文件存在”替代“可用于独立评估”；
- 不要在 `not_ready` 时用颜色、排序或文案暗示评级可靠；
- 不要用 CORS 代替写接口授权；
- 不要为了模块化引入 SaaS、账号、订阅或云同步；
- 不要在没有真实独立标签前训练并宣传更复杂的监督评分模型；
- 不要把静态检查、测试收集、定向测试通过写成运行态准入完成。

## 12. 跨工作包完成定义

一个核心改进只有同时满足以下条件才应标为完成：

1. **语义：** 状态、缺失、来源、粒度和时间字段有明确含义；
2. **契约：** API 和静态导出可机器验证；
3. **安全：** 写入、文件和高成本任务有统一边界；
4. **实现：** 不依赖名字模糊 join 或全局来源布尔值；
5. **测试：** 单元、契约、集成和至少一条真实浏览器流程覆盖；
6. **证据：** 有命令、测试结果、运行态 health 和产物 hash；
7. **回退：** 兼容 facade 或迁移方案可恢复旧路径；
8. **文档：** `TASKS.md`、`CAPABILITIES.md` 和相关状态文档使用相同完成语义。

## 13. 本次审计验证记录

执行并得到的结果：

```text
node --test frontend/tests/*.test.js
  40 passed, 0 failed

uv run pytest \
  tests/unit/test_frontend_security.py \
  tests/unit/test_frontend_feature_contracts.py \
  tests/unit/test_static_json_contracts.py \
  tests/integration/test_api_endpoints.py -q
  914 collected and passed

uv run pytest --collect-only -q -o addopts=''
  5865 tests collected
```

还进行了：

- 当前 OpenAPI 路由与 schema 快照检查；
- 前端数据来源、视图初始化、评级和战术 hover 路径的源码审查；
- API 写路由、CORS、请求体解析和本地 workspace guard 的对照；
- 当前数据健康和研究健康的只读运行态检查；
- DuckDB/Parquet 活跃来源与回退行为检查；
- 项目任务、能力、前端状态、ADR 和评级计划的交叉核对。

未进行：

- 全量 5,865 项测试执行；
- 所有浏览器 E2E 的实际运行；
- 性能压测和并发攻击测试；
- 任何数据重建、模型训练、写接口调用或功能实现。

因此本文中的代码问题是审计发现，测试结果只覆盖上述定向范围；建议中的目标性能与安全验收仍需在对应工作包中实际验证。
