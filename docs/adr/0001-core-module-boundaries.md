# ADR-0001：核心交付层的模块边界与渐进拆分

- 状态：已接受
- 日期：2026-07-17
- 范围：G1 后置维护；不表示 C1 已启动，也不承诺全面重构。

## 背景

`frontend/app.js`、`src/scoutfootball/api.py` 和
`src/scoutfootball/api_server.py` 已同时承担多个参考工作流的交付职责：数据
读取、静态回退、领域装配、HTTP 路由、页面渲染和浏览器事件接线。它们是本地
产品的兼容性边界，而不是可以一次性替换的内部实现细节。

现有测试和用户入口直接依赖这些边界：Python 测试会从 `scoutfootball.api` 和
`scoutfootball.api_server` 导入函数，浏览器测试依赖 `create_app()`、同源 API、
STATIC 回退、OFFLINE 状态和既有 DOM 入口。直接按文件大小拆分会提高回归风险，
也容易把来源、覆盖或本地状态语义拆散。

## 决定

保留三个现有文件作为稳定兼容性 facade。未来每次只抽取一个低耦合领域 seam；
在该 seam 的契约、静态策略、失败状态和真实浏览器覆盖没有通过前，不继续抽取
下一块。

| 现有 facade | 未来内部领域边界 | 必须保持不变 |
| --- | --- | --- |
| `api.py` | `api_domains/` 下的 data、model、scouting、match、worldcup、governance 纯读取/装配模块 | 现有公共函数导入路径、返回字段、来源/覆盖/`recorded` 语义、无数据错误形态 |
| `api_server.py` | `api_routes/` 下按相同领域注册路由；`create_app()` 继续统一生命周期、静态托管和本地写入访问控制 | 路径、请求校验、HTTP 状态、同源部署、loopback 写入限制和 OpenAPI 可发现性 |
| `frontend/app.js` | `frontend/modules/` 下的 data-access、scouting、match、worldcup、governance 和 view 初始化模块 | `fetchJson` 的 LIVE/STATIC/OFFLINE 语义、静态映射、`escapeHtml`/`escapeAttr`/`sanitizeCssPercent`/`csvCell`、已有选择器和本地状态边界 |

共享代码只在以下条件下下沉：它不改变领域数据契约、不隐含网络或持久化行为、且可
由现有单元测试覆盖。不得为了“模块化”复制 sanitizer、静态回退或来源标记逻辑。

## 首个允许的 seam

首个候选仅限前端的只读 data-access 层：把 `fetchJson`、明确的静态映射、超时和
错误归类抽到一个 ES module，`app.js` 继续调用它。此候选不新增页面、路由或网络
目标，也不改变浏览器 localStorage 的数据范围。

在开始前必须先记录：

1. 当前 API 与静态映射清单及 4xx/5xx/网络失败的差异；
2. 受影响黄金流程的 LIVE、STATIC、OFFLINE、空数据和低覆盖断言；
3. 静态 JSON 契约与 `data_manifest.json` 门禁结果。

## 每个 seam 的退出门槛

- 公共导入路径、HTTP 路径、OpenAPI、静态文件名和前端选择器不变，或先提供经测试
  的兼容层；
- 受影响的 Python 单元/集成测试、静态 JSON 契约测试、前端 Node 测试和对应浏览器
  E2E 通过；
- 使用真实本地产物复核来源、许可、快照、coverage、`recorded/not_recorded`、样例和
  本地状态标签没有丢失或被强化；
- `scoutfootball validate`、静态 manifest 检查与相关本地打包路径通过；
- diff 只覆盖一个领域 seam，不包含顺带重命名、批量格式化或新功能。

## 后果

拆分会暂时保留 facade 和兼容测试，因此短期不会显著减少代码行数；换取的是每次
变更都可以回滚、验证并保持个人维护者可理解的边界。C1 的 provenance 强制、质量
SLO、身份工作台和模型晋级/回滚仍需维护者选择真实工作流后单独启动。
