# Liquid Glass 前端当前状态

> 状态日期：2026-07-17。项目定位见 [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md)，任务完成状态以 [`TASKS.md`](TASKS.md) 顶部为准，长期依赖顺序见 [`ROADMAP.md`](ROADMAP.md)，能力成熟度和本地/样例边界见 [`CAPABILITIES.md`](CAPABILITIES.md)。

## 产品形态

`frontend/` 是无构建步骤的本地优先分析工作台，由 `index.html`、`style.css`、`app.js`、战术板脚本和预计算 JSON 组成。视觉方向保持克制的 Liquid Glass 数据终端：浅/深主题、几何 Unicode 图标、清晰的置信度和来源状态。只有在能证明降低状态、测试、路由和单人维护复杂度时才迁移 React/Vue 等框架。

### 统一分析台视觉基础（2026-07-12）

- 全部视图共用一套场地数据台 token：深绿主色、克制金色辅助色、统一玻璃层级、边框、阴影、圆角和状态色；浅/深主题从同一语义 token 派生，不在业务视图再引入第二套色板。
- 导航、搜索、筛选、分段控件、数据卡、表格、排行榜与状态 pill 使用一致的层级、hover 和 selected 规则；桌面导航的活动入口有清晰导轨，移动导航保留活动视图文字，避免只凭图标判断当前页面。
- 增加键盘跳转链接、明确的焦点环、`aria-current="page"` 导航状态、主题切换 `aria-pressed` 语义，以及 `prefers-reduced-motion` 降级；移动端继续保证 44px 触控目标。
- 纯静态服务、导航语义、主题状态与前端契约均由本地验证覆盖；发布前仍应在目标桌面和移动浏览器完成最终视觉回归。

## 当前视图

`index.html` 当前包含 22 个顶层 `data-view` 目标；以下是实现清单，不代表 22 个流程都已达到相同成熟度：

- 核心分析：总览、球员、球员对比、身价、比赛、球队、联赛、球探、动作价值、报告。
- 工作流：电子战术板。
- 世界杯：赛程、阵容、球队对比、概率、淘汰赛、赛事中心。
- 质量与治理：许可、数据、校准、回测、帮助。

在三个黄金工作流完成真实浏览器 E2E 前，暂停新增顶层导航；优先把新能力放进现有流程的步骤、详情、标签页或报告模板。

## 本轮恢复的功能

### 球探

- 侧栏入口已恢复。
- 修复 `player_name` 被错误读取为 `player` 的契约错配，保留 reason、status、note、date、snapshot ID。
- 支持搜索、状态筛选、优先级/日期/姓名排序、状态流转、显式 watchlist 快照和复核队列 CSV 导出。
- 服务端 watchlist/shortlist 与球员页 localStorage 手动选择合并展示。
- review queue 已分页，每页 50 条，避免一次渲染 9000+ 条记录。
- 支持 `scoutfootball.scouting-workspace` v1.1 JSON 导入/导出；工作区记录 ID、revision、创建/更新时间、最后操作和来源快照 ID。
- 导入前显示本地与文件摘要；同键状态/备注冲突会明确计数，安全合并按较新工作区解决冲突，替换本地必须显式点击。
- 导入字段限制数量、长度和文件大小，禁止原型污染键；写入 localStorage 失败时回滚本次批量更新。
- 可选本地 API 持久化默认关闭；显式启用后显示“保存到本地 API/从本地 API 加载”，加载仍先进入现有冲突预览，更新使用服务器 revision，移动浏览器可选择安全合并或显式替换。
- 边界：API 队列仍然只读；持久化只保存工作区 JSON，不改写队列或模型产物。默认仅回环地址可访问，不是云同步、身份系统或多人协作。

### 动作价值

- 侧栏入口已恢复。
- 修复旧 `xT_per_90/composite_score/finishing_delta` 与现行 `xt_per_90/vaep_per_90` 的字段错配及未定义变量异常。
- 支持 xT/VAEP 切换、搜索、赛事筛选、球队筛选、赛季筛选、最低估算分钟筛选、样本摘要、Top 20 图表和小样本提示。
- VAEP 行通过 xT 的 `player_id`+`team_id` 桥接到显示名、队名和赛季/赛事上下文；未映射球员回退显示 `Player ID {id}` 并带未映射标识。
- 身份覆盖率摘要展示映射/未映射数量与比例；明确标注赛季为上下文，非按赛季分配。
- xT 模式可把带 StatsBomb attribution 的样例热区发送到战术板；VAEP 模式禁用该动作。
- 筛选选项由当前数据动态聚合（`frontend/action-value-explorer.js`）。
- 有比赛证据的球员显示标记；详情可下钻到比赛，并查看 pass/carry/shot、目标区域、时间段和高价值动作坐标。API 与纯静态快照均可用，样本外球员明确显示“无比赛证据”。
- 边界：比赛证据只来自仓库跟踪的 3 场 StatsBomb Open Data 样本；证据 xT 网格由这 3 场比赛重新计算，不能与完整聚合榜的 xT 直接比较或相加，也不是全量联赛能力。

### 前端稳定化（2026-06-23）

- API 状态 pill 区分三种状态：LIVE（API 在线）、STATIC（回退到 `frontend/data/` 快照）、OFFLINE（API 和静态缓存均不可用）。
- 静态 fallback 成功时，pill 明确标识 STATIC，不会误导用户以为是实时数据。
- API 和静态缓存都不可用时，视图显示加载失败提示，而非空白或错误数据。
- NaN/undefined 数值显示已加防护：数值字段遇到 NaN/undefined 时显示为 "N/A" 或空，不会渲染为原始字符串。
- 世界杯页状态 pill 已动态化：根据实际数据来源显示 LIVE/STATIC/OFFLINE，而非硬编码。

### 搜索 typeahead（2026-07-10）

- 球员搜索、球员对比 A/B、球队对比 A/B 共 5 个输入框接入 `SearchTypeahead` 组件（`frontend/app.js`）。
- 最少 2 个字符触发请求，300ms 防抖；请求由 `GET /search?q=&type=&limit=` 提供，前缀优先、子串回退。
- 键盘导航：上/下箭头移动高亮项，Enter 选中，Escape 关闭建议面板；鼠标点击同样选中。
- API 离线时静默降级：不渲染建议面板、不抛错，输入框仍可手动提交。
- 球员对比和球队对比端点额外提供静态 fallback：离线时前端加载 `frontend/data/player_compare_pairs.json` 或 `team_compare_pairs.json`，按归一化名称做客户端 pair 查找；未命中 pair 时提示无静态对比数据。
- 边界：静态 compare pairs 是发布快照子集，不等同于全量 API 覆盖；仅作为离线演示 fallback。

### 比赛交锋记录（2026-07-11）

- 比赛预测页新增"交锋记录"section：H2H 比例条、近期交锋表（最多10场）、两队近期战绩对比（摘要+streak badges+近5场列表）、数据来源标注。查询主队结果由 API 显式返回，球队别名不会反转胜负。没有直接交锋时仍展示两队近期状态；完全空数据与加载失败均不影响概率预测。移动端状态卡改为单列，动态内容使用 `aria-live`。静态回退到带 schema 版本和球队别名索引的 `h2h_pairs.json`，空格球队名与常见数据源变体均可命中。

### 静态模式

- API 在线时优先读取 FastAPI。
- 对有静态映射的端点，纯静态服务器返回 404 时继续回退到 `frontend/data/`。
- `frontend/data/` 是跟踪的发布快照；`frontend/local-data/` 是忽略的本地快照。
- 静态快照导出已修复 BUG-001：dataclass/Pydantic response 不再被 `str(obj)` 写成 repr 字符串，必须经过 JSON-safe serializer。

## 质量基线

- 所有外部字符串进入 `innerHTML` 前使用 `escapeHtml()` / `escapeAttr()`。
- CSV 使用 `csvCell()` 防公式注入。
- StatsBomb 衍生图表和导出必须显示 attribution。
- 动画尊重 `prefers-reduced-motion`；交互元素保留焦点态和移动端触控尺寸。
- 当前验证：Node 语法检查、前端契约测试、API 集成测试、安全回归和本地浏览器交互检查。CI 尚未形成覆盖三个黄金工作流的真实浏览器自动化，因此不能把纯 Node 测试视为完整 UI 验收。
- 当前 `frontend/data_manifest.json` 的记录生成时间仍为 2026-06-23；在构建时自动刷新并校验契约之前，静态快照新鲜度属于已知风险。

## G1 解锁后的前端顺序

1. 为球探决策、比赛准备、数据/模型发布三个黄金流程加入真实浏览器 CI，覆盖 LIVE、STATIC、OFFLINE、空数据、低覆盖、字段缺失、移动阅读和导入安全。
2. 从 OpenAPI、导航、静态映射和 capability registry 生成前端能力/契约清单；构建时刷新 manifest，漂移或陈旧即阻断发布。
3. 按领域拆分 `app.js`，先抽出契约/数据访问、球探、世界杯和动作价值模块，并保持现有安全 helper 与静态降级语义。
4. 把工作流中的“下一步、缺失证据、阻断原因”做成一等状态；不再用增加顶层视图表示进度。
5. 继续加强本地导入、导出、备份和迁移；公开链接、云同步、组织账号及多人实时协作不在当前章程范围内。

## 启动与验收

```bash
# API + 前端同源
uv run python -m scoutfootball serve --host 127.0.0.1 --port 8000

# 纯静态发布快照
python -m http.server 8601 --directory frontend

node --check frontend/app.js
uv run pytest tests/unit/test_frontend_feature_contracts.py -q
uv run pytest tests/unit/test_frontend_security.py -q
uv run pytest tests/integration/test_api_endpoints.py -q
```
