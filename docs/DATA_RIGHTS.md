# 数据权利清单

> 初版：2026-07-17。本文记录 ScoutFootball 实际使用或已实现适配器的每个数据源的许可、获取方式、保存、删除和导出边界。未确认许可的数据源不得进入后继节点（G1+）。

本清单由代码实际使用情况推断，而非维护者声明。维护者需在 G0-A 验收前核对并补充真实使用情况。

## 1. 已注册数据源（architecture.py）

以下 6 个数据源已在 [architecture.py](../src/scoutfootball/architecture.py) 的 `planned_components` 中注册。

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

## 2. 已实现但未注册的数据源

以下 7 个适配器已实现并暴露在 `adapters/__init__.py`，但**未在** [architecture.py](../src/scoutfootball/architecture.py) 的 `planned_components` 中注册。这是架构 manifest 的缺口，需在 G1 契约基线中补齐。

### 2.1 transfermarkt_datasets

| 项 | 值 |
|---|---|
| 适配器 | [transfermarkt_datasets.py](../src/scoutfootball/adapters/transfermarkt_datasets.py) |
| 获取方式 | HTTP 下载预构建 DuckDB 文件（~500MB，源自 `dcaribou/transfermarkt-datasets`） |
| 许可 | **未确认**。需核对上游数据集许可和 Transfermarkt ToS |
| 保存 | 本地 DuckDB 文件 |
| 删除 | 可随时删除本地文件 |
| 导出/再分发 | **未确认**。在许可确认前不得用于公开导出 |
| 合规缺口 | 在 [desktop/app.js](../desktop/app.js) 和 [api.py](../src/scoutfootball/api.py) 的许可清单中**完全缺失** |

### 2.2 WhoScored

| 项 | 值 |
|---|---|
| 适配器 | [whoscored.py](../src/scoutfootball/adapters/whoscored.py) |
| 获取方式 | 通过 soccerdata.WhoScored（Selenium + Chrome）抓取 whoscored.com |
| 许可 | **未确认**。WhoScored ToS 可能限制自动化访问和数据再分发 |
| 保存 | 本地缓存 |
| 删除 | 可随时删除本地缓存 |
| 导出/再分发 | **未确认**。在许可确认前不得用于公开导出 |
| 合规缺口 | 在所有现有许可清单中缺失；需 Chrome + Selenium；部分地区需代理 |

### 2.3 SoFIFA

| 项 | 值 |
|---|---|
| 适配器 | [sofifa.py](../src/scoutfootball/adapters/sofifa.py) |
| 获取方式 | 通过 soccerdata.SoFIFA 抓取 sofifa.com |
| 许可 | **未确认**。FIFA 球员属性源自 EA Sports，再分发可能受限 |
| 保存 | 本地缓存 |
| 删除 | 可随时删除本地缓存 |
| 导出/再分发 | **未确认**。在许可确认前不得用于公开导出 |

### 2.4 SofaScore

| 项 | 值 |
|---|---|
| 适配器 | [sofascore.py](../src/scoutfootball/adapters/sofascore.py) |
| 获取方式 | 通过 soccerdata.Sofascore 调用非官方 API `api.sofascore.com/api/v1/` |
| 许可 | **未确认**。使用非官方 API，再分发边界不明 |
| 保存 | 本地缓存 |
| 删除 | 可随时删除本地缓存 |
| 导出/再分发 | **未确认**。在许可确认前不得用于公开导出 |

### 2.5 Capology

| 项 | 值 |
|---|---|
| 适配器 | [capology.py](../src/scoutfootball/adapters/capology.py) |
| 获取方式 | 通过 ScraperFC.Capology 抓取薪水数据 |
| 许可 | **未确认**。薪水数据再分发通常受 ToS 限制 |
| 保存 | 本地缓存 |
| 删除 | 可随时删除本地缓存 |
| 导出/再分发 | **未确认**。在许可确认前不得用于公开导出 |

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

**影响**：架构 manifest 与实际能力不一致，违反"已实现能力必须映射到 manifest"原则。

**建议**：在 G1 契约基线中补齐注册，或确认这些适配器为实验性/停止状态并从 `__init__.py` 移除。

### 3.2 许可清单覆盖缺口

| 位置 | 覆盖数据源数 | 缺失数据源 |
|---|---|---|
| [desktop/app.js](../desktop/app.js) `LICENSE_SOURCES` | 6 | transfermarkt_datasets、whoscored、sofifa、sofascore、capology、api_football |
| [api.py](../src/scoutfootball/api.py) `license_attribution` | 5（缺 clubelo） | clubelo、transfermarkt_datasets、whoscored、sofifa、sofascore、capology、api_football |

**影响**：前端和 API 的许可署名不完整，部分数据源的来源声明对用户不可见。

**建议**：在 G1 中统一许可清单为单一真源（data contract），前端和 API 从中读取。

### 3.3 许可未确认数据源

以下数据源的许可状态标记为**未确认**：
- transfermarkt_datasets
- whoscored
- sofifa
- sofascore
- capology

**影响**：根据 G0-A 退出证据要求，"未确认许可、保存、删除和导出边界的数据源不得进入后继节点"。

**约束**：在维护者确认这些数据源的许可之前，它们不得用于：
- 公开导出或再分发
- G1 及后续节点的契约基线
- 任何对外发布的衍生产物

## 4. 维护者需确认的事项

本清单由代码推断。维护者在 G0-A 验收前需确认：

1. **实际使用的数据源**：哪些适配器在维护者的真实工作流中被使用？哪些是实验性/未使用？
2. **许可确认**：对"未确认"的数据源，是否已阅读并理解其 ToS？是否获得使用授权？
3. **保存/删除边界**：本地缓存的数据是否有保留期限要求？是否有数据应被删除？
4. **导出边界**：哪些数据源的衍生产物可以公开？哪些仅限本地？
5. **transfermarkt_datasets 的 ~500MB DuckDB 文件**：是否仍在使用？其上游许可是否已确认？

## 5. 更新规则

- 数据源新增、适配器变更或许可状态变化时，必须同步更新本清单。
- 许可状态从"未确认"变为"已确认"时，需记录确认证据（ToS 链接、授权凭证或维护者声明）。
- 本清单是 G1 契约基线的输入；G1 的数据契约必须与此清单一致。
