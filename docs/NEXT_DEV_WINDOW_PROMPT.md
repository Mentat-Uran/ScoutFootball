# 下一个开发窗口提示词（整体更新）

> 用法：把本文件路径告诉下一个开发会话，让它完整读取并按本文指令执行。本文自包含，不依赖之前的对话记忆。
> 最终权威：以本仓库当前代码、测试和运行态事实为准；本文与任何旧文档冲突时，本文优先（本文就是"整体更新"的产物）。

---

你是 ScoutFootball 仓库的**整体更新**开发会话。这个项目经历了长期自主开发，现状是：内容陈旧、结构臃肿、功能互相冲突、前端与后端链路多处断裂。本次窗口不是只修几个 bug，而是执行一次有边界的整体更新，让仓库回到"可维护、可信、单一真源"的状态。

## 0. 铁律（先读 AGENTS.md，以下为补充约束）

- **本地-only**：所有开发（提交、构建、测试、导出）只在本地进行。**绝不 `git push`、不开 PR、不发布、不触发任何云端流程**，除非本提示词或用户后续消息明确要求推送。
- **诚实边界**：不得把 demo/synthetic/静态旧快照/模型输出当作真实数据展示；`research_health=not_ready` 时评分相关 UI fail closed。演示数据必须永远显式标注 demo。
- **不提交**：`.env`、凭据、日志、缓存、备份文件（`.bak-*`）、个人数据、下载的二进制。数据产物默认不提交。
- **不引入** SaaS、账号体系、云同步、遥测、订阅。
- 只提交与本次改动相关的文件；提交信息保持小而清晰。

## 1. 第一步：建立基线（约 10 分钟，先做，不要跳过）

1. 读 `docs/PROJECT_AUDIT_2026-08-02.md`（问题清单、根因分析第八节、验收标准）、`docs/FRONTEND_BACKEND_CORE_AUDIT_2026-07-31.md`、`docs/CAPABILITIES.md` 一页结论、`docs/TASKS.md` 顶部队列。
2. 运行基线检查并记录结果：
   - `uv run ruff check src tests`
   - `node --check frontend/app.js`
   - `uv run pytest tests/unit tests/integration -m "not e2e" -q`（若超时则跑 `tests/unit/test_grain.py tests/unit/test_role_system.py` 等定向子集并如实说明）
   - `uv run python -m scoutfootball research-health`
3. 记录 `git status` 与未提交 diff（当前已知：仅版本号类改动未提交）。
4. 把基线结果写回 `docs/PROJECT_AUDIT_2026-08-02.md` 顶部"执行记录"节。

## 2. 本次窗口的核心目标：整体更新，四个阶段按序执行

> 总原则（来自根因分析，见 `docs/PROJECT_AUDIT_2026-08-02.md` 第八节）：
> **a) 主链路优先** —— 任何工具交付必须消费到主链路（主 UI 或主 API），否则不算完成；纯 CLI 工具可以存在，但必须声明"未接入主链路"。
> **b) 暴露门（用户决策）** —— 前端只暴露"已接入真实数据源且过验收"的功能；未完善的功能直接隐藏（导航隐藏 + 占位），等完善后再暴露。隐藏不是删除，后端代码保留，隐藏状态可追踪。

### 阶段 A — 数据链路接通（维护者最高优先级）

**A1 身价前端对接（WP-E3）**
- 事实：真实身价数据已在本地（`data/raw/transfermarkt_manual/`，2026-08-02 更新，69,441 球员 / 33,590 有效 >0，快照截至 2025-09-11）；后端 `GET /market-value/summary`、`/market-value/players`、`/market-value/players/{player_name}` 已返回真实数据（实测 Yamal 2 亿欧 / Haaland / Bellingham / Mbappé 1.8 亿）；但 `frontend/app.js` 对 market-value 零引用。
- 任务：前端接入上述端点，让身价/价值视图显示真实身价（球员名、球队、位置、身价、快照日期、来源与许可边界）。`frontend/data/value_summary.json`（synthetic "Player A/B/C…"）不得再作为身价展示；价值公平性研究视图如保留则必须显式标 demo。
- 验收：打开身价视图可见真实球员身价与快照日期；无后端时显示 honest empty state，绝不显示假数据。

**A2 视图数据源盘点 + 暴露门（WP-E2）**
- 事实：`frontend/data/value_summary.json` 为 synthetic；`predictions_default.json` 默认预测路径存在（app.js 约 3029 行）；index.html 首页 4 个指标硬编码（8,689/10,660/27,254/11,871）；24 个视图中有多个 demo/硬编码/未接入数据源。
- 任务：
  1. 逐一核对 24 个顶层视图的数据来源，输出清单 `docs/VIEW_DATA_SOURCES.md`（视图 → 数据源 → 状态：API live / 静态快照 / demo synthetic / 硬编码 / 空 / 未接入）；
  2. **执行暴露门（用户决策）**：未接入真实数据源、未过验收的视图直接在前端隐藏——移除或禁用导航入口、`setView` 时显示"开发中"占位；后端与数据层代码保留不动，隐藏状态登记在清单中（标注 `hidden:true` + 原因），完善后再恢复暴露；
  3. 消灭默认预测路径与首页硬编码数字（改读 API 或静态快照，无数据时显示 "—" 与原因）。
- 验收：清单入库；demo/硬编码/未接入视图不再可见（隐藏或占位）；已隐藏项在清单中可追踪；同一视图隐藏后其 API 代码不被删除。

**A3 评分来源标注（WP-E1）**
- 事实：当前评分 = 优化器代理目标产物（`scripts/optimizer/`，优化 77 维位置权重，训练目标 = 球队积分 Spearman/NDCG/校准等；当前登记 43 个 run，其中 1 个候选可复核，但 active rating 尚未绑定激活 run；球队积分 MLP 仍是未激活候选，不是已投产的独立监督 NN）。
- 任务：主球员列表/详情显示评分来源行（优化器代理目标产物、最近 run_id、训练目标摘要、feature hash 与当前 manifest 是否一致），与 `research_health` 联动：not_ready 时不得作为强排名结论。
- 验收：not_ready 状态下主页面不排序/不强排名；来源行在后端可达时可见。

**A4 同名球员实体聚合（WP-E4）**
- 事实：legacy 评分表 `player_ratings_optimized.parquet` 30,483 行**无 player_id 列**，主键为 `(player, team, league, season)` 名字组合；6,169 个名字跨多行（Messi 6 行、Cristiano Ronaldo 6 行）；前端评分表按行渲染 `name/team/league/season`（app.js 约 5003 行），同一球员跨赛季在排名中像多个球员；`players_list.json` 按名字字符串去重（10,260 名），真同名被合并、名字变体被分裂（`Kylian_Mbappe-Lottin.json` vs `Kylian_Mbappé.json` 两个 profile）；`player_match.parquet` 的 player_id 双格式混用，同源 85 处同名多 ID，statsbomb 数值 ID 与 understat/fbref 字符串 ID 无法 join。
- 任务：
  1. 复用 PRS-1 已交付的 `canonical_resolver`/`identity_registry`（`load_resolved_player_ratings` 派生视图）给 legacy 评分表挂 `canonical_player_id` 派生列，主链路（评分 API → 前端）改用该 key；
  2. 排名视图默认按实体聚合：同一球员只出现一次（可切换"球员视图 / 赛季视图"）；无 key 的行显示 unresolved 标记，**不得静默合并真同名不同人**；
  3. 合并名字变体静态 profile 文件（保留单真源，另一份 deprecate 或由生成脚本统一 slug）；
  4. 同步前端搜索/详情跳转使用 canonical key 而非裸名字。
- 验收：Messi 在球员列表与排名中只出现一次；真同名不同人（如 Gabriel 系）不被合并；unresolved 行可见标记。

### 阶段 B — 功能冲突消解（整体更新的核心）

**B1 冲突盘点**
- 事实清单（已核实的冲突源）：
  - 双前端真源：`frontend/app.js` 与 `desktop/app.js` 为差一字节的近亲副本（仅版本常量不同）；
  - 三重产品面：Streamlit（15 页）+ 静态前端（24 视图）+ FastAPI；另存在公开 Render 端点引用（`backend-health-check.yml`）与 Vercel/Cloudflare 配置，与"本地优先"章程存在张力；
  - 评分文件多版本并存：`player_ratings.parquet` / `player_ratings_v2.parquet` / `player_ratings_v3.parquet` / `player_ratings_optimized.parquet` + `data/models/runs/` 82 个产物文件；
  - 依赖双真源：`requirements.txt`（含编码乱码注释）+ `pyproject.toml`/`uv.lock` + 被 ignore 的 `package-lock.json`；
  - API 宽而无 schema：约 202 个路由，OpenAPI 无业务 response schema。
- 任务：输出一份冲突/冗余清单（`docs/OVERLAP_AND_DEPRECATION.md`），每项标注：保留 / 合并 / 弃用（deprecate）/ 删除，并给理由与影响面。**本次窗口只做盘点 + 明确决策建议 + 低风险清理**，不做大重写。
- 验收：清单覆盖上述 5 类冲突；每项有明确决策建议；用户确认前不执行高风险的删除/迁移。

**B2 陈旧内容清理（低风险项直接做）**
- 从 git 移除 6 个 `.bak-20260605044151` 备份文件（`git rm`，6.2MB parquet + 5 CSV）；
- 删除/归档 13 个未合并残留分支的建议写进清单（`codex/*` ×10、`solo/*` ×3）——分支删除需用户确认，不要自行执行；
- 清理 `frontend/data/` 中已无消费者或已 synthetic 的静态文件（先确认引用，再删）；
- 修复 `requirements.txt` 的编码乱码注释；
- 统一评分文件真源：在清单中明确哪个文件是当前唯一事实源，其余标记 deprecate（不删数据，只改读取链）。

### 阶段 C — 工程治理（沿用审计工作包）

- **C1 写路由统一访问门（SEC-001）**：建立 `require_local_write_access` 依赖；api_server.py 全部 POST/PUT/DELETE 与文件生成任务接入；默认仅 loopback；路由清单测试保证新增写路由漏 guard 时失败；CORS 从显式配置生成并与授权分离。验收：非 loopback 写请求默认 403；不泄露绝对路径。
- **C2 测试分层与默认命令（TEST-001）**：`pyproject.toml` addopts 加 `-m "not e2e"`；`ci.yml` test job 同步；AGENTS.md/README 检查命令说明与实现一致；处理或记录 TestClient 弃用告警计划。验收：`uv run pytest -q` 不再收集 e2e（48 项）。
- **C3 战术板安全（FE-002 + MP4 导出）**：hover 标签改 `textContent`；MP4 导出流式上限、`finally` 清理、错误 envelope、响应不含绝对路径、失败返回 4xx/5xx。验收：注入测试 + 临时文件清理测试。
- **C4 依赖与文档治理**：依赖单一声明真源；`TASKS.md`/`CODEX_CONTINUOUS_STATE.md` 等滚动文档向脚本生成或归档方向收敛（至少在本窗口结束时让 `docs/PROJECT_AUDIT_2026-08-02.md` 与 `CAPABILITIES.md` 与实现一致）。

### 阶段 D — 回归与收尾

1. 全量检查：`uv run ruff check src tests`；`node --check frontend/app.js`（及 desktop/app.js）；`uv run pytest tests/unit tests/integration -m "not e2e" -q`；`uv run pytest --collect-only -o addopts=""` 确认 e2e 默认排除。
2. 同步文档：`docs/CAPABILITIES.md`、`docs/TASKS.md`、`docs/PROJECT_AUDIT_2026-08-02.md`（勾选完成项、标注未完成与原因）、新增 `docs/VIEW_DATA_SOURCES.md` 与 `docs/OVERLAP_AND_DEPRECATION.md`。
3. 提交：按逻辑分多个小提交（如 A1/A2/A3/A4、B1 清单、B2 清理、C1、C2、C3、C4、docs），**不 push**。

## 3. 禁止事项（违反即返工）

- 不一次性重写 `app.js` / `api.py` / `index.html`（只做模块抽取或局部修改）；
- 不新增功能、页面、路由、模型、评分方案（本次是收敛不是扩张）；
- 不把缺失值填 0/50；不用 CORS 代替授权；不把 demo 当真实数据；
- 不修改 `data/` 下产物（只读诊断可以）；不提交任何数据/日志/备份文件；
- 不删除未确认的既有功能（删除前必须列入 B1 清单并给理由）；
- 不 push、不开 PR、不发布。

## 4. 完成定义（每项改动都要）

实现 + 定向测试通过 + 真实数据/运行态证据；检查命令与结果记录在案；`TASKS.md`/`CAPABILITIES.md`/审计文档同步同一语义；汇报区分"静态检查通过"与"运行态验证通过"。**新增规则：工具交付必须满足"主链路接入"（主 UI 或主 API 消费 + 集成/垂直测试证明）才可标 verified；未接入主链路的交付必须在文档中显式声明。**

## 5. 汇报格式（结束时返回）

1. 四个阶段的逐项状态（done / partial / blocked + 一句话原因）；
2. 关键证据：基线检查输出、`research-health` 输出、身价视图截图或等价运行证据、冲突清单摘要；
3. **暴露门执行结果：隐藏了哪些视图、原因、对应 `docs/VIEW_DATA_SOURCES.md` 登记项**；
4. 未完成项与阻塞原因、需要用户决策的问题列表（尤其 B1 清单中的保留/删除决策）；
5. 提交列表（commit message 一行摘要）。
