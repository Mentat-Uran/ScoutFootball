# 扩展爬虫覆盖范围 Spec

## Why
当前数据集仅覆盖五大联赛（EPL、La Liga、Bundesliga、Serie A、Ligue 1），且 FBref 仅 3-5 赛季、StatsBomb 仅 3 场事件数据。数据量和维度不足限制了评分模型的泛化能力。需要从三个方向扩展：**更多联赛**（葡超/荷甲/土超等二级联赛 + 英冠/西乙等次级联赛）、**更多维度**（FBref passing/defense/possession、SofaScore 评分、SoFIFA 属性、API-Football 伤停/转会）、**更多赛季**（统一 10 赛季 2016-2026）。

## What Changes
- **FBref**: 扩展联赛映射（+5 个二级联赛）；扩展 stat_type（+passing/defense/possession/gca/playing_time/keeper）；扩展赛季到 10 赛季
- **Football-Data.co.uk**: 增加 13 个联赛代码（含次级联赛）；扩展赛季到 10 赛季
- **Understat**: 增加 RFPL 联赛支持；确认 10 赛季覆盖
- **StatsBomb**: 批量获取所有可用赛季的 events + lineups（当前仅 3 场）
- **新增 SofaScore 适配器**: 球员单场评分 + 非五大联赛覆盖（通过 soccerdata）
- **新增 SoFIFA 适配器**: FIFA 球员属性数据（通过 soccerdata）
- **新增 API-Football 适配器**: 伤停/转会/教练数据（REST API，免费 100/天或 Pro $19/月）
- **新增 transfermarkt-datasets 导入器**: 从 dcaribou/transfermarkt-datasets 项目的预构建 DuckDB 文件导入 player_valuations（50万+条历史身价）、game_lineups（280万+条）、game_events（110万+条）、transfers（8.7万条）等 12 张表
- **新增 WhoScored 适配器**: 比赛评分（1-10分）+ 事件流数据（通过 soccerdata），作为评分模型 ground truth
- **新增 Capology 适配器**: 球员薪资数据（通过 ScraperFC），新增薪资特征维度
- **Pipeline 配置驱动**: 硬编码联赛/赛季列表提取到集中配置
- **数据质量**: 跨源球员 ID 对齐、球队名规范化、去重逻辑

## Impact
- Affected specs: 数据采集层、特征工程层、实体规范化层
- Affected code:
  - `src/scoutlab/adapters/fbref.py` — LEAGUE_MAPPINGS 扩展
  - `src/scoutlab/adapters/fbref_soccerdata.py` — 支持更多 stat_type 和联赛
  - `src/scoutlab/adapters/football_data.py` — 无需改动（league_code 已支持任意字符串）
  - `src/scoutlab/adapters/understat.py` — 无需改动
  - `src/scoutlab/adapters/statsbomb_open.py` — 无需改动
  - `src/scoutlab/adapters/sofascore.py` — 新增
  - `src/scoutlab/adapters/sofifa.py` — 新增
  - `src/scoutlab/adapters/api_football.py` — 新增
  - `src/scoutlab/adapters/transfermarkt_datasets.py` — 新增
  - `src/scoutlab/adapters/whoscored.py` — 新增
  - `src/scoutlab/adapters/capology.py` — 新增
  - `src/scoutlab/adapters/__init__.py` — 注册新适配器
  - `src/scoutlab/config.py` — 新增 IngestConfig
  - `src/scoutlab/pipeline.py` — 配置驱动重构
  - `src/scoutlab/entities/normalize.py` — 球队名跨源映射
  - `scripts/fetch_*.py` — 更新联赛/赛季参数 + 新增脚本

## ADDED Requirements

### Requirement: FBref 联赛扩展
系统 SHALL 支持从 FBref 抓取以下额外联赛的球员标准统计：
- 葡超 (Primeira Liga, comp_id=32)
- 荷甲 (Eredivisie, comp_id=23)
- 土超 (Süper Lig, comp_id=26)
- 苏超 (Scottish Premiership, comp_id=24)
- 比甲 (First Division A, comp_id=22)

#### Scenario: 抓取新联赛数据
- **WHEN** 调用 `fetch_player_standard(leagues=["POR-Primeira Liga"], seasons=[2024])`
- **THEN** 成功返回葡超 2024-25 赛季球员数据

### Requirement: FBref 多维度统计
系统 SHALL 支持从 FBref 抓取以下额外 stat_type 的球员数据（通过 soccerdata）：
- passing（传球：关键传球、传球成功率、渐进传球等）
- defense（防守：抢断、拦截、解围等）
- possession（控球：触球、过人、被抢断等）
- gca（进球创造：射门创造动作、传球创造动作等）
- playing_time（出场时间：首发、替补、未上场等）
- keeper（门将：扑救、失球、PSxG 等）
- keeper_adv（高级门将：扫荡、交叉扑救等）

#### Scenario: 抓取传球数据
- **WHEN** 调用 soccerdata FBref 适配器获取 `stat_type="passing"` 数据
- **THEN** 返回包含关键传球、渐进传球、传球成功率等列的 DataFrame

### Requirement: Football-Data 联赛扩展
系统 SHALL 支持从 Football-Data.co.uk 下载以下额外联赛的 CSV：
- E1 (Championship)、E2 (League One)、E3 (League Two)
- SP2 (Segunda División)、D2 (2. Bundesliga)
- F2 (Ligue 2)、I2 (Serie B)
- N1 (Eredivisie)、P1 (Primeira Liga)
- T1 (Süper Lig)、B1 (First Division A)
- SC0 (Scottish Premiership)、SC1 (Scottish Championship)
- SC2 (Scottish League One)、SC3 (Scottish League Two)

#### Scenario: 下载 Championship 数据
- **WHEN** 调用 `download_csv(league_code="E1", season="2425")`
- **THEN** 成功返回 Championship 2024-25 赛季比赛数据

### Requirement: StatsBomb 事件数据批量获取
系统 SHALL 能批量获取 StatsBomb Open Data 中所有五大联赛可用赛季的比赛事件和阵容数据，而非仅手动指定 3 场。

#### Scenario: 批量获取事件数据
- **WHEN** 运行 StatsBomb 事件数据获取脚本
- **THEN** 自动从 competitions.json 发现所有可用赛季，下载所有比赛的事件和阵容数据，保存为 `events_all.parquet` 和 `lineups_all.parquet`

### Requirement: SofaScore 适配器
系统 SHALL 提供 SofaScore 适配器，通过 soccerdata 库获取球员单场评分和球队比赛统计。SofaScore 评分是业界最广泛使用的单场评分系统，可作为评分模型的验证基准。

#### Scenario: 获取球员单场评分
- **WHEN** 调用 SofaScore 适配器获取指定联赛/赛季的球员比赛统计
- **THEN** 返回包含球员名、球队、比赛日期、SofaScore 评分的 DataFrame

#### Scenario: 获取非五大联赛数据
- **WHEN** 调用 SofaScore 适配器获取葡超/荷甲等联赛数据
- **THEN** 成功返回该联赛的球员评分数据

### Requirement: SoFIFA 适配器
系统 SHALL 提供 SoFIFA 适配器，通过 soccerdata 库从 soFIFA.com 抓取球员 FIFA 属性数据（OVR、PAC、SHO、PAS、DRI、DEF、PHY 等综合评分），作为球员特征的补充维度。

#### Scenario: 抓取球员属性
- **WHEN** 调用 SoFIFA 适配器获取指定联赛的球员属性
- **THEN** 返回包含球员名、球队、位置、综合评分及六维属性的 DataFrame

### Requirement: API-Football 适配器
系统 SHALL 提供 API-Football 适配器，从 api-football.com REST API 获取以下数据：
- 伤停信息（injuries）：球员受伤类型、预计恢复日期
- 转会记录（transfers）：转入/转出俱乐部、转会费
- 教练信息（coaches）：教练姓名、国籍、球队

适配器 SHALL 支持 API Key 配置，并在无 Key 时优雅降级（跳过该数据源）。

#### Scenario: 获取伤停数据
- **WHEN** 调用 API-Football 适配器获取指定联赛的伤停信息
- **THEN** 返回包含球员名、球队、受伤类型、恢复日期的 DataFrame

#### Scenario: 无 API Key 降级
- **WHEN** 未配置 API-Football API Key
- **THEN** ingest 流程跳过 API-Football 数据源，记录 warning 日志，不中断其他数据源

### Requirement: transfermarkt-datasets 导入器
系统 SHALL 提供从 dcaribou/transfermarkt-datasets 预构建 DuckDB 文件批量导入数据的能力，替代手动 CSV 导入。该数据集每周自动更新，CC0 协议，包含 12 张表。

优先导入的表：
- `player_valuations`（50万+条历史身价记录）— 评分模型的关键验证标准
- `game_lineups`（280万+条）— 远超当前 StatsBomb 的阵容覆盖
- `game_events`（110万+条）— 远超当前 StatsBomb 的事件覆盖
- `transfers`（8.7万条）— 球队阵容变动特征
- `appearances`（球员出场记录）— 补充 FBref 出场数据
- `players`（球员基础信息）— 跨源 ID 对齐的基础

#### Scenario: 下载并导入 DuckDB
- **WHEN** 运行 transfermarkt-datasets 导入脚本
- **THEN** 自动下载 DuckDB 文件到 `data/raw/transfermarkt_datasets/`，将指定表导出为 parquet

#### Scenario: 身价数据可用于评分验证
- **WHEN** player_valuations 数据已导入
- **THEN** 特征工程层可使用真实市场价值替代合成数据，评分模型有了客观验证标准

### Requirement: WhoScored 适配器
系统 SHALL 提供 WhoScored 适配器，通过 soccerdata 库获取球员单场评分（1-10分）和比赛事件流数据。WhoScored 评分基于 Opta 事件数据，是业界最权威的球员单场评分之一，可作为评分模型的 ground truth 对照。

#### Scenario: 获取球员单场评分
- **WHEN** 调用 WhoScored 适配器获取指定联赛/赛季的球员评分
- **THEN** 返回包含球员名、球队、比赛日期、WhoScored 评分的 DataFrame

#### Scenario: 获取比赛事件流
- **WHEN** 调用 WhoScored 适配器获取比赛事件
- **THEN** 返回包含事件类型、坐标、球员信息的 DataFrame，可用于 xT/VAEP 等高级指标计算

### Requirement: Capology 适配器
系统 SHALL 提供 Capology 适配器，通过 ScraperFC 库获取球员薪资数据（周薪/年薪），作为球员特征的补充维度。

#### Scenario: 获取薪资数据
- **WHEN** 调用 Capology 适配器获取指定联赛的球员薪资
- **THEN** 返回包含球员名、球队、周薪、年薪的 DataFrame

#### Scenario: ScraperFC 未安装降级
- **WHEN** ScraperFC 库未安装
- **THEN** 适配器抛出 ImportError，pipeline 跳过该数据源

### Requirement: Pipeline 配置驱动
系统 SHALL 将 pipeline.py 中硬编码的联赛列表、赛季范围提取到 `IngestConfig` 集中配置，所有 ingest 方法从配置读取联赛/赛季参数。

#### Scenario: 配置变更生效
- **WHEN** 在 IngestConfig 中新增一个联赛
- **THEN** `run_daily_ingest` 自动包含该联赛的数据获取，无需修改代码

### Requirement: 跨源球员 ID 对齐
系统 SHALL 在特征工程层提供跨数据源的球员身份对齐机制，基于规范化球员名 + 出生日期 + 国籍的组合键匹配同一球员在不同数据源中的记录。

#### Scenario: FBref 与 Understat 球员匹配
- **WHEN** FBref 和 Understat 数据中存在同一球员的不同记录
- **THEN** 通过规范化球员名 + 出生年份 + 国籍的组合键正确匹配

### Requirement: 球队名跨源规范化
系统 SHALL 维护球队名映射表，将不同数据源对同一球队的不同命名（如 "Man City" / "Manchester City" / "曼彻斯特城"）统一为规范名称。

#### Scenario: 球队名规范化
- **WHEN** Football-Data 使用 "Man City"，FBref 使用 "Manchester City"
- **THEN** 两者在特征工程层被统一为同一球队 ID

## MODIFIED Requirements

### Requirement: FBref 赛季范围
FBref 适配器 SHALL 默认支持 2016-2026 共 10 赛季的数据获取（当前仅 3-5 赛季）。soccerdata 路径的 `fetch_fbref_10seasons.py` 已实现此功能，但 HTML 解析路径（`fbref.py`）的脚本尚未更新。

### Requirement: Football-Data 赛季范围
Football-Data 适配器 SHALL 默认支持 2016-2026 共 10 赛季的数据获取。`fetch_football_data_extended.py` 已实现，但 pipeline 中的 `_ingest_football_data` 仍硬编码 5 个联赛代码。

### Requirement: Understat 联赛覆盖
Understat ingest SHALL 包含 RFPL（俄超）联赛。当前 `_ingest_understat` 仅硬编码 EPL/La_Liga/Serie_A 三个联赛，遗漏了 Bundesliga、Ligue_1 和 RFPL。

## REMOVED Requirements
无移除项。
