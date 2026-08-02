# 前端顶层视图数据源清单

更新时间：2026-08-02 开发窗口。状态只描述当前仓库代码和本地快照，不表示外部数据授权或实时可达。

| 视图 | 主数据源 | 状态 | `hidden` | 说明 |
|---|---|---|---:|---|
| overview | `/artifacts`、`/health`、`/ratings/meta` | API live，离线无数字 fallback | false | 首页指标从 API 读取，无数据显示 `—`。 |
| workflow | recruitment/opposition 本地 API 与浏览器本地状态 | API live / local-only | false | 无 API 时显示离线/空状态。 |
| versions | 四类 decision artifact 本地 API | API live / local-only | false | 不使用静态匿名记录。 |
| players | `/ratings`、`/players/{name}`、`/health/research` | API live + 静态旧快照；研究门禁 fail-closed | false | `research_health != ready` 时评分列不排序、不作强排名；静态快照不扩展为实时数据。 |
| compare | `/players/compare`、`/players/compare-multi` | API live + 静态比较快照 | false | 缺失字段保持 `—`。 |
| value | `/market-value/summary`、`/market-value/players`；`/value-summary` 仅 OOF 研究 | 市价 API live；公平性研究 partial | false | market value 不再消费 `value_summary.json` synthetic；公平性数据无真实 OOF 时显示 unavailable。 |
| matches | prediction API、`/predictions/meta`、calibration API | API live；默认预测静态 fallback 已移除 | false | API 不可用时不显示默认比分。 |
| teams | `/teams`、`/teams/strength`、`/teams/compare` | API live + 静态快照 | false | 需保留 data source 标记。 |
| league | league/form/projection API | API live | false | 无数据时使用 API 空状态。 |
| scouting | scouting API、ratings API、浏览器本地 shortlist/watchlist | API live / local-only | false | 本地状态不表示跨设备同步。 |
| actions | `/action-values` 与 evidence API | API live + 静态 artifact snapshot | false | artifact status/coverage 由响应决定。 |
| reports | model runs、truth labels、identity reports API | API live + 静态模型快照 | false | report 不把候选 run 说成 admitted。 |
| tactical | Canvas/browser-local；MP4 使用本地 API | local-only + guarded write | false | 写入受 loopback/Bearer 门保护；导出响应不泄露绝对路径。 |
| wc_schedule | World Cup schedule API | API live + 静态快照 | false | 快照需保留来源和生成时间。 |
| wc_squads | World Cup squad API | API live + 静态快照 | false | 名单/预计阵容边界由页面说明。 |
| wc_compare | World Cup comparison API | API live | false | 无数据不回填概率。 |
| wc_probability | World Cup probability API/static export | API live + 静态快照 | false | 静态输出不是实时模拟。 |
| wc_knockout | World Cup knockout API/static export | API live + 静态快照 | false | 赛事状态写入仍受写门保护。 |
| wc_tournament | local tournament store/API | API live / local-only | false | import/reset/result 等写操作受写门保护。 |
| license | `/license`、artifact attribution | API live + artifacts snapshot | false | 只展示归因与许可边界，不改变许可。 |
| data | `/artifacts`、`/health/detailed` | API live + 静态健康快照 | false | 健康状态不是数据正确性证明。 |
| calibration | calibration API/static calibration artifact | API live + 静态快照 | false | 无 artifact 时显式 unavailable。 |
| backtest | backtest/calibration API | API live；无数据显示 no data | true | 当前版本没有可供离线静态 fallback 的可信 backtest 结果，导航保留待后续通过主链路验收后恢复。 |
| help | 仓库文档与静态说明 | static documentation | false | 非数据结论视图。 |

## 暴露门规则

- `API live` 或带明确来源/快照日期的静态 artifact 可以暴露，但必须把 API、静态快照和离线状态区分开。
- `demo synthetic`、硬编码数字、未接入主链路的功能不得作为结果显示。
- `backtest` 本窗口标记 `hidden:true`；后端代码和数据层保留，恢复条件是有真实 artifact、来源/快照字段和一条前端垂直测试。
- 身价公平性研究子区不是市场身价真源；`value_summary.json` 的 synthetic 数据只可作为被隐藏/不可用的研究输入，不能作为展示结果。
