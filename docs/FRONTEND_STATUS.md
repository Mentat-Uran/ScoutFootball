# Liquid Glass 前端当前状态

> 状态日期：2026-06-23。任务完成状态以 `docs/TASKS.md` 为准，中长期顺序见 `docs/ROADMAP.md`。

## 产品形态

`frontend/` 是无构建步骤的本地优先分析工作台，由 `index.html`、`style.css`、`app.js`、战术板脚本和预计算 JSON 组成。视觉方向保持克制的 Liquid Glass 数据终端：浅/深主题、几何 Unicode 图标、清晰的置信度和来源状态。短期不引入 React/Vue；框架迁移必须先证明能降低状态、测试和路由复杂度。

## 当前视图

- 分析：总览、球员、身价、比赛预测、球探、动作价值、报告。
- 工作流：电子战术板。
- 世界杯：赛程、名单、对比、出线概率。
- 治理：数据源、数据状态、校准、帮助。

## 本轮恢复的功能

### 球探

- 侧栏入口已恢复。
- 修复 `player_name` 被错误读取为 `player` 的契约错配，保留 reason、status、note、date、snapshot ID。
- 支持搜索、状态筛选、优先级/日期/姓名排序、状态流转、显式 watchlist 快照和复核队列 CSV 导出。
- 服务端 watchlist/shortlist 与球员页 localStorage 手动选择合并展示。
- 边界：API 队列只读；状态和备注仅保存在当前浏览器，尚未形成正式审计产物。

### 动作价值

- 侧栏入口已恢复。
- 修复旧 `xT_per_90/composite_score/finishing_delta` 与现行 `xt_per_90/vaep_per_90` 的字段错配及未定义变量异常。
- 支持 xT/VAEP 切换、搜索、赛事筛选、最低估算分钟筛选、样本摘要、Top 20 图表和小样本提示。
- xT 模式可把带 StatsBomb attribution 的样例热区发送到战术板；VAEP 模式禁用该动作。
- 边界：部分 VAEP 产物只有 `player_id`，当前明确显示 ID；动作价值只代表 StatsBomb Open Data 覆盖样本。

### 静态模式

- API 在线时优先读取 FastAPI。
- 对有静态映射的端点，纯静态服务器返回 404 时继续回退到 `frontend/data/`。
- `frontend/data/` 是跟踪的发布快照；`frontend/local-data/` 是忽略的本地快照。

## 质量基线

- 所有外部字符串进入 `innerHTML` 前使用 `escapeHtml()` / `escapeAttr()`。
- CSV 使用 `csvCell()` 防公式注入。
- StatsBomb 衍生图表和导出必须显示 attribution。
- 动画尊重 `prefers-reduced-motion`；交互元素保留焦点态和移动端触控尺寸。
- 当前验证：Node 语法检查、前端契约测试、API 集成测试、安全回归和本地浏览器交互检查。

## 下一步

1. 把球探/动作价值浏览器流程加入 CI，覆盖 API、静态、空数据和移动断点。
2. review queue 增加分页或虚拟列表。
3. 建立版本化 scouting workspace 导入/导出和审计字段。
4. 完成 VAEP 球员身份映射与覆盖率报告。
5. 增加动作类型、比赛、球队和球员三级下钻；在任何评分融合前完成独立评估。

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
