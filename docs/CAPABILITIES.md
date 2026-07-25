# ScoutFootball 能力真相表

> 审计快照：2026-07-25，分支 `codex/integration`。本文只描述本地仓库可核验状态，不证明线上部署当前可达，也不把计划、样例或估算写成生产能力。工程与发布缺口表已更新到 2026-07-25，反映 G0-B 修复、G1 子任务3（真实浏览器 E2E）、P1（决策工作流闭环 E2E + 创建/编辑路径）和 P1+（dossier/review 条目级编辑 E2E：supporting_evidence / risks / hypothesis_results 的新增/编辑/移除/客户端校验阻断）落地。

项目属性以 [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md) 为准：本地优先、MIT 开放源代码、个人维护、非盈利。本表中的桌面、容器、API 或可选协作能力不代表 SaaS、商业版、企业支持或营收计划。

## 状态定义

| 状态 | 定义 |
| --- | --- |
| 已交付 | 代码、入口和相应测试/产物存在，能明确说明适用边界 |
| 部分交付 | 主路径存在，但覆盖、契约、测试、发布或完整数据仍缺一项以上 |
| 样例/实验 | 只适合演示、研究或候选比较，不能代表完整赛事/人群/生产能力 |
| 本地状态 | 只保存在浏览器或同机服务，不是云同步、组织审计或跨设备协作 |
| 计划 | 文档或代码入口存在，但尚未满足交付定义 |
| 未核验 | 本次审计无法以当前运行时或网络环境复现，不能据此作当前承诺 |

## 一页结论

- 仓库已经是一个跨数据、模型、API、静态前端、桌面包装和世界杯场景的完整原型，不是空壳。
- 产品宽度显著超过旧文档的"7 个分析视图 + 4 个世界杯视图"：当前 HTML 中可见 24 个顶层 `data-view` 目标（含 P1 新增的 `workflow` 和 `versions`）。
- 关键缺口不再是"有没有更多功能"，而是统一契约、能力登记、真实浏览器 E2E 覆盖面、发布门禁、完整可读数据和三个端到端决策闭环的持续验证。
- 浏览器球探工作区、战术工程和部分世界杯输入仍是本地状态；动作价值下钻仍只有 3 场比赛、94 条球员—比赛证据记录，并非 tracking；预计名单和模拟结果不是官方实时事实。
- 2026-07-25 在当前锁定 `uv` 运行时执行 `scoutfootball preflight --target key`，21 个关键 Parquet 均完成内容级解码、schema 检查和抽样校验。该结果只覆盖本次本地检查的文件，不证明来源权利、快照新鲜度或未来运行时持续可读。

## 仓库规模快照

| 对象 | 本地观察 | 判断 |
| --- | ---: | --- |
| FastAPI 路由装饰器 | 163 | 产品契约面较宽，必须自动盘点和分域 |
| 静态前端顶层视图 | 24 | 旧 README 的 7+4 口径已过时；P1 新增 `workflow` + `versions` |
| Python 测试文件 | 94（93 个 `test_*.py` + `conftest.py`） | 单元/集成基础较强，但不替代真实浏览器测试 |
| 前端 Node 测试文件 | 4 | 有纯 JS 回归基础，覆盖面仍有限 |
| `frontend/app.js` | 26,490 个物理行 / 1.35 MiB | 高变更耦合风险，应按领域拆分 |
| `frontend/index.html` | 2,654 个物理行 / 191 KiB | 导航、模板和内容高度集中 |
| `src/scoutfootball/api.py` | 11,493 个物理行 / 428 KiB | 数据装配单体过大 |
| `src/scoutfootball/api_server.py` | 1,853 个物理行 / 64 KiB | 路由面需要分域和生成式文档 |
| `docs/TASKS.md` | 约 230 KiB | 活跃队列与历史交付日志混合 |
| `docs/CODEX_CONTINUOUS_STATE.md` | 约 318 KiB | 大量滚动状态不适合作为当前真源 |

这些数字是复杂度信号，不是产品成功指标。

## 产品能力清单

| 领域 | 当前能力 | 状态 | 证据边界 / 下一门槛 |
| --- | --- | --- | --- |
| 数据流水线 | `ingest`、`build-features`、`train`、验证和多类导出入口 | 已交付 | 当前工作区全部已登记来源已有本地保留/删除政策；上游快照日期、陈旧度与来源主张审计仍须逐项保留证据 |
| 本地数据层 | raw/silver/gold/models/reports/logs，DuckDB + Parquet | 已交付 | 当前锁定 `uv` 运行时的 21 个关键 Parquet 已通过内容级 preflight；每次数据或运行时变更后仍须重新检查，且这不替代来源、快照与许可审计 |
| 球员评分 | 优化器、覆盖/可用性约束、holdout 指标、模型运行登记、候选评分快照与本地准入/拒绝/晋级/回滚 | 部分交付 | 只有维护者带决策文本并确认后才会切换已核验候选；v1.3.1/v1.3.2 后续完整重跑、独立真值与经审计设定的质量阈值仍未完成 |
| NN 评分 | `train-rating-nn` 监督式候选入口 | 样例/实验 | 只有独立合格标签、时间外 holdout 并优于 baseline 后才可晋级 |
| 真值标签 | schema、来源政策、手动 Transfermarkt 快照导入与保守身份复核 | 部分交付 | 标签来源、独立性和当前可读行数口径仍需统一；不得把模型衍生标签当外部真值 |
| 比赛预测 | Independent Poisson、Dixon-Coles 基线、概率矩阵与校准展示 | 已交付的基线 | 不是投注建议；需按联赛/时间/阵容覆盖持续校准 |
| 动作价值 | xT/VAEP 聚合、分页、来源标记、比赛证据下钻 | 部分交付 | 本地 footer 报告聚合 9,951 行；下钻仅有 3 场比赛、94 条球员—比赛证据记录，不能写成 tracking 或全量联赛 |
| 球员画像/对比 | 百分位、趋势、雷达、导出和低置信度原因 | 已交付 | 结论强度必须服从字段覆盖、联赛和样本量 |
| 球探工作区 | review/watch/shortlist、备注、决策档案、版本化导入导出、冲突预览 | 已交付的本地工作流 | 默认浏览器本地；同机 loopback 持久化需显式开启；不是组织云协作 |
| 战术板 | 本地工程、对象/图层/帧、动画、导入清洗、多格式导出、可选 ffmpeg | 已交付的本地工具 | 浏览器下载不等于服务器保存；本地视频叠画/追踪导入有研究门槛，实时云协作不在当前章程范围内 |
| 世界杯赛程/阵容 | 赛程、球队、比较、概率、淘汰赛/赛事分析 | 部分交付 | 数据快照和覆盖必须显示；预计征召不等于官方最终名单 |
| 世界杯赛前简报 | 从赛程打开来源受限简报、JSON/安全 CSV 下载、战术计划联动 | 已交付的本地/静态流程 | `recorded/not_recorded`、输入快照和模型边界必须端到端保留 |
| 世界杯 Core 契约复用 | 7 个 artifact 通过 `worldcup/contracts.py` 复用 Core `DataContract`/`SnapshotInfo`/`LineageEntry`；5 类事实类型（official_roster/expected_callup/injury_report/rating_coverage/model_probability）；`GET /world-cup/contracts` registry 端点；`TournamentState` 1.1.0 嵌入 contract，1.0.0 向后兼容 | 已交付 | 满足 P1 退出门槛第 4 条"世界杯包与招募/比赛包复用 Core，没有复制身份/快照/导出逻辑" |
| 招募决策简报（Recruitment Brief） | `scoutfootball.recruitment-brief` v1.0.0 schema、BriefStore 版本化本地存储（`If-Match` 乐观并发）、备份/恢复/diff、`POST /recruitment/briefs`（create）、`GET /recruitment/briefs/{id}/backups`/`/diff`/`/restore`、前端 `versions` 视图时间线 | 已交付的本地工作流 | 默认浏览器本地 + 同机 loopback 文件持久化；不是组织云协作；API 仅暴露 create（`expected_revision=0`），更新/删除走 store 直连或 CLI |
| 招募决策档案（Decision Dossier） | `scoutfootball.recruitment-decision-dossier` v1.0.0 schema、DossierStore 版本化存储、状态机（draft→decided/rejected/superseded）、证据/反证/比较/风险条目、`POST /recruitment/dossiers`、备份/恢复/diff 端点 | 已交付的本地工作流 | 与 brief 共享 Core 契约；决策只能由维护者带决策文本确认后切换；不是自动评分晋级 |
| 对手赛前简报（Opposition Briefing） | `scoutfootball.opposition-briefing` v1.0.0 schema、BriefingStore 版本化存储、分节事实分级（official/recorded/estimated/unknown）、`POST /opposition/briefs`、备份/恢复/diff 端点 | 已交付的本地工作流 | 从赛程打开来源受限简报；`recorded/not_recorded` 边界必须端到端保留；不是官方实时球队新闻 |
| 对手赛后复盘（Post-Match Review） | `scoutfootball.opposition-post-match-review` v1.0.0 schema、ReviewStore 版本化存储、假设验证/证伪模式/新问题、`POST /opposition/reviews`、备份/恢复/diff 端点 | 已交付的本地工作流 | 与 briefing 共享 Core 契约；复盘结论必须标注事实分级和证据来源；不是自动视频分析 |
| 决策工作流导航 + 版本恢复 | 前端 `workflow` 视图：基于已加载 brief/briefing/dossier/review 状态推断可执行下一步、阻断原因和缺失证据；前端 `versions` 视图：四类记录的备份时间线、字段级 diff、`If-Match` 恢复、可移植离线包导出 | 已交付的本地工作流 | P1 E2E 覆盖 versions 视图冒烟、workflow 视图冒烟、四类 artifact（brief/briefing/dossier/review）的 diff+restore 往返（2026-07-25）；P1+ E2E 覆盖 dossier/review 的条目级编辑（supporting_evidence / risks / hypothesis_results 的新增、编辑、移除、客户端校验阻断：缺失 ID、重复 ID、非法枚举）（2026-07-25） |
| 世界杯可复现 demo 快照 | `scripts/demo_snapshot/export_worldcup_demo_snapshot.py` 导出 6 JSON + manifest + README，`--check` 验证 hash 一致性 | 已交付的本地流程 | 剥离 volatile timestamp keys（`generated_at`/`updated_at`/`created_at`/`recorded_at`/`as_of`）后计算 SHA-256；当前 6/6 文件 hash 一致；维护者数据变更后需重新导出 |
| 静态前端 | 24 个顶层视图、API/静态 fallback、离线状态 | 部分交付 | 静态路径映射不是全路由覆盖；静态 manifest 陈旧度和契约一致性需自动门禁 |
| API | 只读分析接口及有限、显式开启的本地工作区写入 | 已交付/部分交付 | 163 个路由装饰器过宽；需要分域、schema registry、弃用策略和 API/静态一致性 |
| Streamlit | 15 页研究/运维工作台 | 已交付 | 与主静态产品的职责需要收敛，避免双重产品真源 |
| 桌面/容器 | Electron/PyInstaller、Docker/GHCR/发布配置 | 部分交付 | 跨平台构建、签名、回滚和最终资产需在每次发布中独立确认 |
| 云部署 | README 记录 Vercel/Render 路径 | 未核验 | 本次不把文档 URL 当成当前可达证明；发布需要实际健康检查和访问确认 |

## 当前 24 个静态前端视图

| 组 | 视图 |
| --- | --- |
| 决策工作流 | 工作流导航、版本与备份 |
| 核心分析 | 总览、球员、对比、身价、比赛、球队、联赛、球探、动作价值、报告、战术板 |
| 世界杯 | 赛程、阵容、球队对比、概率、淘汰赛、赛事中心 |
| 质量与治理 | 许可、数据、校准、回测、帮助 |

导航数量不再继续扩张，除非新视图无法作为现有黄金工作流的步骤、详情或标签页表达，并同时给出契约、静态策略、空状态、移动端和 E2E。

## 本地产物观察

本次用当前系统 Python/PyArrow 读取 footer 得到以下元数据：

| 文件 | footer 行数 | 解释 |
| --- | ---: | --- |
| `data/raw/statsbomb_open/matches_all.parquet` | 2,187 | 与部分旧文档“空文件”说法冲突 |
| `data/gold/feature_store/player_action_value.parquet` | 9,951 | 与旧文档的 15,062 行说法冲突 |
| `data/gold/feature_store/player_truth_labels.parquet` | 29,723 | 包含 `label_source`，但来源分布未在本次成功解码 |
| `data/gold/feature_store/player_match_action_value_sample.parquet` | 94 | 仅比赛证据样例，不是完整联赛 |

此前审计环境曾报 `OSError: Repetition level histogram size mismatch`，但 2026-07-17
在当前锁定 `uv` 运行时对 `preflight --target key` 的 21 个关键产物完成了内容级
解码、schema 与抽样校验，未发现不可读文件。该检查只说明本次本地输入可读，不把
footer、mtime 或这一次运行写成来源新鲜度、许可完整性或永久数据健康结论。数据、
依赖或运行时变更后必须重新运行 preflight；若再次失败，先记录 writer、schema、
row-group、hash 和最小复现，只有完成备份及行数、schema、统计和来源不变校验后，
才可考虑重写文件。

## 真实性分类

### 可直接陈述

- 仓库存在本地流水线、API、静态工作台、Streamlit、桌面和容器构建路径。
- 球探工作区支持版本化本地导入导出与冲突预览。
- 世界杯赛程可以进入赛前简报，并将有来源的输入交给战术计划。
- 模型与导出已有部分来源、覆盖、快照和 lineage 字段。
- 招募 brief/dossier 和对手 briefing/review 四类决策记录有版本化本地存储、备份/恢复/diff 端点，且四类 artifact 的 diff+restore 往返均已通过真实浏览器 E2E（2026-07-25）。工作流视图的 OFFLINE blocker 推断、LIVE 状态契约（四类 artifact 的 create-*/*-missing 推断与 API 计数双向一致）与字段级 evidence gap 推断（complete/incomplete brief、classified/unclassified briefing 的 brief-gap-*/briefing-tier-* 推断与记录内容一致）均已通过真实浏览器 E2E（2026-07-25）。versions 视图支持从工具栏起草全部四类决策档案（brief / briefing / dossier / review，draft 状态），其中 dossier / review 支持从工作流视图跳转时携带 pre-fill 自动打开对话框与预选关联字段（2026-07-25）。versions 视图支持编辑已存在的 decision dossier / post-match review 的顶层字段（title / notes / human_opinion / recommendation / status / decision / decision_note）与状态推进（draft → decided / finalized），客户端校验 decision/status 一致性，409 revision conflict 时保持对话框打开让维护者刷新后重试（2026-07-25）。versions 视图支持条目级编辑 dossier 的 supporting_evidence / counter_evidence / comparisons / risks 和 review 的 hypothesis_results / falsified_patterns / new_questions / supporting_evidence / counter_evidence：新增/编辑/移除条目、全列表替换语义、客户端校验缺失 ID / 重复 ID / 非法枚举（fact_tier / severity / outcome），且 9 条条目级编辑往返 E2E 均已通过真实浏览器验证（2026-07-25）。

### 必须带限定词

- “全量”只能指某个已验证产物的完整行集，不能指全球、完整联赛或完整赛季覆盖。
- “阵容”要区分官方名单、记录到的数据、预计征召和占位内容。
- “持久化”要区分浏览器 localStorage、同机文件、服务端数据库和云同步。
- “模型改进”必须说明相同输入、相同时间切分、baseline、误差和是否已晋级。
- “部署成功”必须有目标 URL、版本、访问策略和实际健康检查。

### 当前不能陈述

- 不能称动作价值比赛证据为全量联赛能力。
- 不能称 NN 候选为默认评分模型。
- 不能称预计世界杯名单为官方实时球队新闻。
- 不能称浏览器工作区为跨设备或多人审计系统。
- 不能因 workflow 生成 placeholder 或允许失败继续，就称发布资产已通过验证。

## 工程与发布缺口

| 缺口 | 当前观察 | 目标状态 |
| --- | --- | --- |
| 真实浏览器 E2E | 2026-07-25 起 `tests/e2e/` 提供 Playwright + 系统 Chrome 的 smoke + workflow + decision-workflow 覆盖（LIVE/STATIC/OFFLINE/空数据/低覆盖/字段缺失/移动阅读/导入安全/versions 冒烟/workflow 冒烟/workflow OFFLINE blocker/workflow LIVE 状态契约/workflow 字段级 evidence gap 推断（complete/incomplete brief、classified/unclassified briefing）/recruitment brief diff+restore 往返/opposition briefing diff+restore 往返/recruitment dossier diff+restore 往返/opposition review diff+restore 往返/versions 视图创建按钮可见性/versions 视图起草 dossier round-trip/versions 视图起草 review round-trip/versions 视图起草 brief round-trip/versions 视图起草 briefing round-trip/workflow → versions 创建跳转 pre-fill/versions 视图编辑按钮可见性/versions 视图编辑 dossier round-trip/versions 视图编辑 dossier 状态推进到 decided/versions 视图编辑 dossier 客户端校验阻断/versions 视图编辑 dossier 冲突恢复/versions 视图编辑 review round-trip/versions 视图编辑 review 状态推进到 finalized/versions 视图编辑 dossier 新增 supporting_evidence 条目往返/versions 视图编辑 dossier 移除 supporting_evidence 条目往返/versions 视图编辑 dossier 编辑已存在 supporting_evidence 条目往返/versions 视图编辑 dossier 缺失 evidence_id 客户端校验阻断/versions 视图编辑 dossier 重复 evidence_id 客户端校验阻断/versions 视图编辑 dossier 非法 fact_tier 客户端校验阻断/versions 视图编辑 dossier 新增 risk 条目往返/versions 视图编辑 review 新增 hypothesis_result 条目往返/versions 视图编辑 review 移除 hypothesis_result 条目往返），通过 `-m e2e` 显式运行 | 三个黄金工作流完整导航路径在静态和低覆盖路径运行 |
| 发布 fail-open | 2026-07-17 G0-B 已清理关键发布/数据 workflow 的 `continue-on-error`、`|| true` 和成功 placeholder | 关键验证失败即停止；仅非关键上传可明确容错 |
| 签名与跨平台 | 签名发现被禁用，平台状态在文档间有漂移 | 每个平台独立构建、签名/未签名声明、安装与回滚证据 |
| 静态新鲜度 | 已以本地 release 导出刷新 `frontend/data_manifest.json`；检查器同时核对文件清单、大小、去重和汇总元数据。`npm run build:sites` 与 CI 在复制 STATIC 快照前均会失败关闭 | 自动重新生成、来源/快照 SLO 与跨产物一致性仍留给 C1；门禁不会把旧快照写成新数据 |
| 契约维护 | `project_manifest.json` 与 [`REFERENCE_INDEX.md`](REFERENCE_INDEX.md) 由同一生成器产出；`--check` 同时校验机器清单和人读索引，并在 CI lint job 失败关闭 | schema registry + compatibility tests + C1 的来源/快照 SLO 强制 |
| 模块边界 | API/前端核心文件仍高度集中；[`ADR-0001`](adr/0001-core-module-boundaries.md) 已固定 facade、领域边界、首个低耦合 seam 和每次拆分的验证门槛 | 仅在已选参考工作流的契约/E2E 通过后，一次拆分一个领域 seam |
| 任务真源 | `TASKS.md` 顶部仅保留当前队列；历史交付记录归档在 [`history/TASKS-2026-07-17.md`](history/TASKS-2026-07-17.md)，且有链接/真源边界检查 | 新历史记录按版本归档，不能覆盖当前节点状态 |

## 当前验收优先级

1. 章程、个人参考工作流和实际输入的数据权利边界一致。
2. 标准运行时中所有关键 Parquet 可读、schema 可验证、统计可重算；发布关键步骤 fail-closed。
3. 来源、许可、快照、身份、契约和模型运行的统一能力登记。
4. 已声明支持的参考工作流完成真实浏览器 E2E、低覆盖/失败状态和静态/API 同契约验证。
5. 只有前置门槛通过后才开始新的顶层功能或空间/视频实验；多人云协作不在当前章程范围内。

长期顺序见 [`ROADMAP.md`](ROADMAP.md)，市场与产品判断见 [`FOOTBALL_TOOLING_LANDSCAPE_2026.md`](FOOTBALL_TOOLING_LANDSCAPE_2026.md)。
