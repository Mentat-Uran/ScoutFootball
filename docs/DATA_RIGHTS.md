# 数据权利清单

> 初版：2026-07-17，维护者确认 2026-07-17。本文记录 ScoutFootball 实际使用或已实现适配器的每个数据源的许可、获取方式、保存、删除和导出边界。未确认许可的数据源不得进入后继节点（G1+）。

## 维护者确认（2026-07-17）

1. **实际使用**：6 个分析输入源（StatsBomb、Football-Data、ClubElo、Understat、FBref、Transfermarkt 手动）在维护者真实工作流中使用；Reep 是另行登记的本地身份映射快照，不进入分析、标签或对外数据流。后 7 个已实现但未注册的适配器**写了代码但未在使用**，标记为实验性/停止状态。
2. **许可**：项目仅维护者本人本地使用，5 个此前"未确认"的数据源（transfermarkt_datasets、whoscored、sofifa、sofascore、capology）维护者确认个人本地使用没有问题。但**再分发和公开导出**仍需各自遵守上游 ToS。
3. **适用范围**：世界杯是第一个参考包，后续会扩展到更多联赛、其他国家队比赛和俱乐部比赛场景。数据权利边界以"个人本地使用"为基线。

## 1. 已注册数据源（architecture.py）

以下 7 个数据源已在 [architecture.py](../src/scoutfootball/architecture.py) 的 `planned_components` 中注册。

### 1.1 StatsBomb Open Data

| 项 | 值 |
|---|---|
| 适配器 | [statsbomb_open.py](../src/scoutfootball/adapters/statsbomb_open.py) |
| 获取方式 | HTTP 拉 GitHub raw 开放数据 JSON |
| 许可 | StatsBomb Open Data: User Protocol。免费用于研究，必须署名。商业使用需单独向 StatsBomb 申请许可 |
| 保存 | 本地 `data/raw/statsbomb_open/` 不可变快照 |
| 删除 | 可随时删除本地快照；不影响上游 |
| 导出/再分发 | 公开衍生产物必须显示 StatsBomb 署名标记。原始数据再分发需遵守 StatsBomb Open Data 许可 |
| 当前覆盖 | 样本（3 场比赛，~12K 事件）。**非**完整联赛覆盖 |

### 1.2 Football-Data.co.uk

| 项 | 值 |
|---|---|
| 适配器 | [football_data.py](../src/scoutfootball/adapters/football_data.py) |
| 获取方式 | HTTP 下载 CSV |
| 许可 | Football-Data.co.uk 标注 "Free for non-commercial use"。建议署名 |
| 保存 | 本地 `data/raw/football_data/` CSV 基线 |
| 删除 | 可随时删除本地 CSV |
| 导出/再分发 | 非商业使用；再分发需遵守上游许可 |
| 当前覆盖 | 大量历史赛季比赛结果和赔率 |

### 1.3 ClubElo

| 项 | 值 |
|---|---|
| 适配器 | [clubelo.py](../src/scoutfootball/adapters/clubelo.py) |
| 获取方式 | HTTP 拉 CSV（`api.clubelo.com/{date}`） |
| 许可 | ClubElo 公开数据。建议署名 |
| 保存 | 本地 `data/raw/clubelo/` 队伍 Elo 快照 |
| 删除 | 可随时删除本地快照 |
| 导出/再分发 | 遵守上游许可 |
| 当前覆盖 | 历史 Elo 评分 |
| 合规缺口 | [api.py](../src/scoutfootball/api.py) 的 `license_attribution` 字典中**缺失** clubelo |

### 1.4 Understat

| 项 | 值 |
|---|---|
| 适配器 | [understat.py](../src/scoutfootball/adapters/understat.py) |
| 获取方式 | HTTP scrape（自定义 User-Agent） |
| 许可 | Understat 公开数据，建议署名 |
| 保存 | 本地 `data/raw/understat/` 缓存 |
| 删除 | 可随时删除本地缓存 |
| 导出/再分发 | 遵守上游许可；scrape 行为需遵守 robots.txt 和 ToS |
| 当前覆盖 | 10 赛季球员攻击统计聚合 |

### 1.5 FBref

| 项 | 值 |
|---|---|
| 适配器 | [fbref.py](../src/scoutfootball/adapters/fbref.py)、[fbref_soccerdata.py](../src/scoutfootball/adapters/fbref_soccerdata.py) |
| 获取方式 | HTTP scrape（伪装浏览器 UA，6.5 秒速率限制）；或通过 soccerdata 库 |
| 许可 | FBref 数据用于个人研究。**禁止再分发**。禁止绕过验证码或反爬措施（AGENTS.md） |
| 保存 | 本地 `data/raw/fbref/` 低频缓存标准表提取 |
| 删除 | 可随时删除本地缓存 |
| 导出/再分发 | **禁止再分发**原始数据。衍生产物需确认上游许可 |
| 当前覆盖 | 五大联赛标准表，低频补充 |

### 1.6 Transfermarkt（手动导入）

| 项 | 值 |
|---|---|
| 适配器 | [transfermarkt_manual.py](../src/scoutfootball/adapters/transfermarkt_manual.py) |
| 获取方式 | 纯本地手动导入（CSV/Parquet）。**无自动化抓取** |
| 许可 | 仅允许手动或授权导入（AGENTS.md）。Transfermarkt 数据再分发受其 ToS 限制 |
| 保存 | 本地 `data/raw/transfermarkt_manual/` 手动快照 |
| 删除 | 可随时删除本地快照 |
| 导出/再分发 | 本地产物继承 Transfermarkt ToS 边界；能导出不等于能公开发布 |
| 当前覆盖 | 带日期的本地手动快照，经身份复核后导入 |

### 1.7 Reep identity register

| Item | Value |
|---|---|
| Acquisition | Explicit maintainer-triggered download of repository-published `people.csv`; no login, scraping, or credentials |
| License | Repository declares CC0 1.0 Universal; this record does not independently interpret that declaration |
| Local boundary | `data/raw/reep/` is ignored by Git and retained only for local identifier-mapping review |
| Permitted use | Cross-provider identifier lookup/review only; not a market-value, performance, roster, or truth-label source |
| Snapshot | Reep metadata declares data version `2026.25`, generated `2026-06-21T08:36:25Z`; local inspection and snapshot-ledger records identify the exact retained CSV |
| Retention and deletion | Explicitly recorded in the local source-policy ledger; deletion invalidates any future dependent identity bridge for regeneration |

## 2. 已实现但未注册的数据源（实验性/停止状态）

> **维护者确认 2026-07-17：以下 7 个适配器写了代码但未在维护者真实工作流中使用，标记为实验性/停止状态。** 它们不进入 G1 契约基线；若未来启用，需先确认许可和注册。

以下 7 个适配器已实现并暴露在 `adapters/__init__.py`，但**未在** [architecture.py](../src/scoutfootball/architecture.py) 的 `planned_components` 中注册，且维护者确认未在使用。

### 2.1 transfermarkt_datasets

| 项 | 值 |
|---|---|
| 适配器 | [transfermarkt_datasets.py](../src/scoutfootball/adapters/transfermarkt_datasets.py) |
| 获取方式 | HTTP 下载预构建 DuckDB 文件（~500MB，源自 `dcaribou/transfermarkt-datasets`） |
| 许可 | 维护者确认个人本地使用 OK（2026-07-17）。再分发需核对上游数据集许可和 Transfermarkt ToS |
| 保存 | 本地 DuckDB 文件 |
| 删除 | 可随时删除本地文件 |
| 导出/再分发 | 个人本地使用 OK；公开导出需核对上游数据集许可 |
| 合规缺口 | 在 [desktop/app.js](../desktop/app.js) 和 [api.py](../src/scoutfootball/api.py) 的许可清单中**完全缺失** |

### 2.2 WhoScored

| 项 | 值 |
|---|---|
| 适配器 | [whoscored.py](../src/scoutfootball/adapters/whoscored.py) |
| 获取方式 | 通过 soccerdata.WhoScored（Selenium + Chrome）抓取 whoscored.com |
| 许可 | 维护者确认个人本地使用 OK（2026-07-17）。WhoScored ToS 可能限制自动化访问和数据再分发 |
| 保存 | 本地缓存 |
| 删除 | 可随时删除本地缓存 |
| 导出/再分发 | 个人本地使用 OK；公开导出需核对 WhoScored ToS |
| 合规缺口 | 在所有现有许可清单中缺失；需 Chrome + Selenium；部分地区需代理 |

### 2.3 SoFIFA

| 项 | 值 |
|---|---|
| 适配器 | [sofifa.py](../src/scoutfootball/adapters/sofifa.py) |
| 获取方式 | 通过 soccerdata.SoFIFA 抓取 sofifa.com |
| 许可 | 维护者确认个人本地使用 OK（2026-07-17）。FIFA 球员属性源自 EA Sports，再分发可能受限 |
| 保存 | 本地缓存 |
| 删除 | 可随时删除本地缓存 |
| 导出/再分发 | 个人本地使用 OK；公开导出需核对 EA Sports / SoFIFA 许可 |

### 2.4 SofaScore

| 项 | 值 |
|---|---|
| 适配器 | [sofascore.py](../src/scoutfootball/adapters/sofascore.py) |
| 获取方式 | 通过 soccerdata.Sofascore 调用非官方 API `api.sofascore.com/api/v1/` |
| 许可 | 维护者确认个人本地使用 OK（2026-07-17）。使用非官方 API，再分发边界不明 |
| 保存 | 本地缓存 |
| 删除 | 可随时删除本地缓存 |
| 导出/再分发 | 个人本地使用 OK；公开导出需核对 SofaScore ToS |

### 2.5 Capology

| 项 | 值 |
|---|---|
| 适配器 | [capology.py](../src/scoutfootball/adapters/capology.py) |
| 获取方式 | 通过 ScraperFC.Capology 抓取薪水数据 |
| 许可 | 维护者确认个人本地使用 OK（2026-07-17）。薪水数据再分发通常受 ToS 限制 |
| 保存 | 本地缓存 |
| 删除 | 可随时删除本地缓存 |
| 导出/再分发 | 个人本地使用 OK；公开导出需核对 Capology ToS |

### 2.6 API-Football

| 项 | 值 |
|---|---|
| 适配器 | [api_football.py](../src/scoutfootball/adapters/api_football.py) |
| 获取方式 | 官方 API（`v3.football.api-sports.io`），需 API key |
| 许可 | API-Football (api-sports.io) 官方许可。免费层每日 100 请求 |
| 保存 | 本地缓存；无 key 时优雅降级跳过 |
| 删除 | 可随时删除本地缓存 |
| 导出/再分发 | 遵守 API-Football 官方许可 |
| 合规缺口 | 在所有现有许可清单中缺失 |

## 3. 合规缺口汇总

### 3.1 architecture.py 注册缺口

以下 7 个适配器已实现但未注册：
- fbref_soccerdata（继承 fbref）
- transfermarkt_datasets
- whoscored
- sofifa
- sofascore
- capology
- api_football

**维护者确认 2026-07-17**：这 7 个适配器**未在维护者真实工作流中使用**，标记为实验性/停止状态。

**影响**：架构 manifest 与实际能力不一致（有代码但不在 manifest 也不在使用）。

**建议**：在 G1 契约基线中确认这些适配器的处置——若未来启用则补齐注册和许可声明；若确认不再使用则从 `__init__.py` 移除以减少维护成本。当前不阻塞 G0-A 验收。

### 3.2 许可清单覆盖缺口

| 位置 | 覆盖数据源数 | 缺失数据源 |
|---|---|---|
| [desktop/app.js](../desktop/app.js) `LICENSE_SOURCES` | 6 | transfermarkt_datasets、whoscored、sofifa、sofascore、capology、api_football |
| [api.py](../src/scoutfootball/api.py) `license_attribution` | 6（clubelo 已于 2026-07-17 补齐） | transfermarkt_datasets、whoscored、sofifa、sofascore、capology、api_football |

**影响**：前端和 API 的许可署名覆盖 6 个实际使用的分析数据源，已完整。Reep 只作为本地身份映射快照，当前不进入前端或 API 输出；7 个未使用的实验性适配器不在许可清单中，符合"未使用则不暴露"原则。

**建议**：G1 中统一许可清单为单一真源（data contract），前端和 API 从中读取。若未来启用实验性适配器，需同步补齐许可声明。

### 3.3 许可状态

**维护者确认 2026-07-17**：所有 13 个适配器的许可状态已确认：

- **6 个实际使用的分析数据源**：许可已在 [api.py](../src/scoutfootball/api.py) 和 [desktop/app.js](../desktop/app.js) 的许可清单中声明，覆盖完整。Reep 的本地身份映射快照仅在数据契约和本清单中登记，尚未进入这些输出面。
- **7 个实验性/停止状态的数据源**：维护者确认个人本地使用 OK。公开导出或再分发仍需各自遵守上游 ToS。这些适配器未在使用，不进入 G1 契约基线。

**G0-A 退出证据满足**：近期输入的权利和本地边界明确。无"未确认"许可的数据源阻塞后继节点。

## 4. 维护者确认记录

| 日期 | 确认事项 | 结论 |
|---|---|---|
| 2026-07-17 | 实际使用的数据源 | 前 6 个已注册数据源在用；后 7 个实验性/停止 |
| 2026-07-17 | Reep identity register | 维护者授权下载并保留 CC0 声明的本地 `people.csv` 身份映射快照；仅用于后续人工身份映射复核，不进入市场价值、表现、名单或真值标签流程 |
| 2026-07-17 | 许可状态 | 5 个此前"未确认"的数据源，维护者确认个人本地使用 OK；公开导出需遵守上游 ToS |
| 2026-07-17 | 适用范围 | 世界杯是第一个参考包，后续扩展到更多联赛、国家队和俱乐部比赛；权利边界以"个人本地使用"为基线 |

## 5. 更新规则

- 数据源新增、适配器变更或许可状态变化时，必须同步更新本清单和第 4 节确认记录。
- 许可状态变化时，需记录确认证据（ToS 链接、授权凭证或维护者声明）。
- 实验性适配器启用进入实际工作流前，必须先补齐 architecture.py 注册和许可声明。
- 本清单是 G1 契约基线的输入；G1 的数据契约必须与此清单一致。
