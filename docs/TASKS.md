# 任务路线图

> 当前队列更新：2026-07-17。项目定位见 [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md)，长期依赖见 [`ROADMAP.md`](ROADMAP.md)，行业依据见 [`FOOTBALL_TOOLING_LANDSCAPE_2026.md`](FOOTBALL_TOOLING_LANDSCAPE_2026.md)，能力边界见 [`CAPABILITIES.md`](CAPABILITIES.md)。本文件顶部是当前任务真源；旧阶段和交付记录已归档为历史证据，其中的日期不构成当前期限。

当前状态：仓库已形成宽幅本地原型，主要矛盾已经从“功能不足”转为定位一致性、数据可读性、契约漂移、真实浏览器测试、发布门禁和个人端到端工作流。路线不设工期，只执行依赖已满足的节点。

## 队列规则

- 节点状态只使用 `ready`、`blocked`、`in_progress`、`verified`、`stopped`。
- 只有 `ready` 或 `in_progress` 节点可以拆成实现任务；`blocked` 节点只记录依赖，不提前堆功能。
- 解锁取决于退出证据，不取决于日期。被解锁的节点也可以暂停或停止。
- 当前只允许本地、开放、个人、非盈利路线；SaaS、商业版、收入、获客、组织账号和云协作不进入队列。

## 当前已解锁节点

### G0-A：个人工作流与数据权利 — `verified`

- [x] 固化 [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md)，并同步 README、路线图、能力表和开发规则。
- [~] 分别记录球探决策、比赛准备、数据/模型研究的真实个人任务：输入、步骤、输出、现有替代工具、错误和阻断。（[WORKFLOW_LOG.md](WORKFLOW_LOG.md) 3.1 数据导入与验证已填写真实任务；1.x 球探和 2.x 比赛准备骨架待维护者实际使用后填写）
- [x] 选择至少一个会重复使用的参考工作流，保存一次真实端到端运行和人工复盘证据；其余流程允许停止。（[WORKFLOW_LOG.md](WORKFLOW_LOG.md) 参考工作流 1：2026-07-17 真实执行 `validate` + `preflight`，21/21 ok，退出码 0，有完整复盘）
- [x] 建立假设登记，记录证据、反证、置信度、下一测试和停止条件。（维护者确认 2026-07-17：暂无假设需要登记，停止）
- [x] 建立实际输入的数据权利清单；未确认许可、保存、删除和导出边界的数据源不得进入后继节点。（[DATA_RIGHTS.md](DATA_RIGHTS.md) 已完成，维护者确认 2026-07-17：6 个在用，7 个实验性/停止，许可全部确认）

退出证据：章程与入口文档一致（已满足）；至少一个参考工作流有真实任务证据（已满足 — 3.1 数据导入与验证，2026-07-17）；近期输入的权利和本地边界明确（已满足）。

### G0-B：真实性、运行时与发布止血 — `verified`

- [x] 修复标准 `uv` 运行时和缓存路径；对关键 Parquet 执行内容级 preflight，记录 schema、writer、row-group、hash、统计和失败原因，不可读文件立即隔离。
- [x] 清理发布和数据 workflow 中关键步骤的 `continue-on-error`、`|| true` 和成功 placeholder；关键失败不得产出“成功发布”。
- [x] 修复 `scripts/demo.sh` 的端口说明和启动参数，统一为 FastAPI 同源托管并增加 smoke test。
- [x] 核验或移除 README 中的线上部署引用；无法访问时明确写“未核验”。线上部署不是本地项目的解锁条件。
- [x] 默认 Python 测试不再调用会改写当前数据根目录的 ingest、feature build 或训练；真实写入型 pipeline 验收必须显式设置 `SCOUTFOOTBALL_RUN_MUTATING_PIPELINE_TESTS=1`，并建议使用独立 `SCOUTFOOTBALL_DATA_ROOT`。

退出证据：21 个关键 Parquet 产物 preflight 全部通过（c74263e）；发布 fail-open 为 0（01d85a1）；demo.sh 统一为 FastAPI 同源托管（端口 8000）并增加 `--smoke` 健康检查；README 部署引用已核验（2026-07-17：Vercel 前端可达，Render 后端 free tier 冷启动未完全通过，未标记为 live）。

### G1：黄金流程与契约基线 — `verified`（G0-A + G0-B 已验证）

- [x] 建立机器可读 capability registry，从 OpenAPI、CLI、前端导航、静态映射和模型登记生成清单。（`data/project_manifest.json` 与 `docs/REFERENCE_INDEX.md` 由 `scripts/generate_manifest.py` 同步生成；`--check` 在 CI lint job 作为失败关闭门禁）
- [x] 统一来源、许可、`as_of`、快照、lineage、覆盖和 `recorded/not_recorded` 数据契约。（`src/scoutfootball/schemas/storage.py` `DataContract` schema；`data/project_manifest.json` 的生成式 data contracts 登记；`build_run_lineage` 记录 dataset_snapshot/input_hash/status）
- [x] 为当前声明支持的参考工作流加入真实浏览器 E2E，覆盖 LIVE、STATIC、OFFLINE、空数据、低覆盖、字段缺失、移动阅读和导入安全。（`tests/e2e/`：5 smoke + 8 workflow = 13 测试通过；commit e30cc57, d413d68）
- [x] 构建时生成静态 manifest；关键 API/静态契约、文件新鲜度或序列化失败时阻断发布。（`scripts/generate_manifest.py` 生成 + `--check` 门禁；`tests/unit/test_static_json_contracts.py` 检查静态 JSON 结构；`scripts/check_frontend_manifest.py` 在 CI 和 `npm run build:sites` 复制 STATIC 快照前失败关闭）

退出证据：
- 参考工作流 fixture 通过 — 13 个 E2E 测试通过（e30cc57 smoke harness, d413d68 workflow coverage），覆盖 LIVE/STATIC/OFFLINE/空数据/低覆盖/字段缺失/移动阅读/导入安全。
- 新决策包的外部事实和派生主张证据完整 — 架构基础已就位：`DataContract` schema 含 license/snapshot/lineage/coverage/recorded；world cup briefing 保留 source_attribution/limitations/input_snapshot（未记录时 status=not_recorded）；球探工作区保留 audit/review/selections/source/snapshot；tournament import preview 有 integrity_failed 检测。部分满足：统一的决策包 validator 留到 C1（C1 要求 provenance 字段经 registry 强制）。
- API/静态同快照一致 — `scripts/generate_manifest.py --check` 提供 project_manifest 发布门禁（hash 对比，stale 返回 1）；`tests/unit/test_static_json_contracts.py` 检查静态 JSON 结构；刷新后的 `frontend/data_manifest.json` 由 `scripts/check_frontend_manifest.py` 检查文件清单、大小、重复项和汇总元数据，并在 CI 与 `npm run build:sites` 复制 STATIC 快照前失败关闭。自动重建、来源/快照 SLO 和全契约 gate 仍留给 C1。
- 入口文档口径一致 — 4 处冲突已修复（e3d0e22：README.md, README_ZH.md, CAPABILITIES.md, FRONTEND_STATUS.md）。

## 下一解锁节点

C1 可信证据内核 — `in_progress`。首个验收载体选择已在使用的 3.1 数据导入与验证：`scoutfootball preflight --evidence-out <path>` 将内容级检查结果与已登记的 contract、source license、snapshot、lineage 写入本地证据报告；缺失字段明确为 `not_recorded`，既不上传数据也不补造历史 provenance。`source-health` 现可附加本地 inspection，并通过显式传入的 append-only snapshot ledger 展示已登记快照。`record-source-policy` 默认只预演；只有 `--confirm` 才向本地追加式政策账本记录维护者给出的保留模式、删除触发条件、原始内容处置、派生产物动作和决策文本。它支持明确的非数值 `until_manual_deletion`/`until_rights_change`，不会把它们伪造为天数；`source-health --policy-ledger` 和 `contract-quality --policy-ledger` 只消费已传入账本中的最新声明，未记录政策仍为 `baseline_required`。`record-source-snapshot` 只接受维护者提供的日期和对应 preflight 证据，不从文件时间推断。`contract-quality` 现在把可观测的登记、许可和已提供 preflight 内容可读性明确标为 pass/fail，同时把来源保留/删除边界、快照、身份和来源错误率等尚无审计分母或维护者决策的维度标为 `baseline_required`，不填充任意阈值。Transfermarkt 身份复核现有本地追加式确认、拒绝和撤销决策，且只在当前输入哈希与候选集合匹配时消费；新的导入账本让撤销后的 `reconcile-transfermarkt-truth-labels` 先预览、再显式且原子地移除仍可证明由该确认写入的标签，历史或已替换标签不会被静默删除。优化器现在保留结构化的同切分 baseline/candidate 指标，并从当前 holdout 直接保存错误案例；其输入 lineage 只列出实际读取的原始/特征/标签输入，明确排除当前评分输出，避免候选血缘循环引用。`model-admission` 仅把具备自身参数、记录的 lineage、时间切分、有限 holdout 指标和错误案例的未来运行标为 `reviewable`，历史缺证记录保持 `not_reviewable`。它不执行自动晋级；`reject-model-run`、`promote-model-run` 和 `rollback-model-run` 均默认预演，要求维护者决策文本与 `--confirm`，并在晋级前校验候选评分哈希/内容和活跃产物、建立带哈希的本地备份，回滚也只接受当前已启用候选对应的已核验备份。C1 的其余范围（维护者确认每个来源的保留/删除边界，以及经审计后设定的质量阈值）仍未完成。G1 后置维护项（TASKS.md 历史归档、模块边界 ADR、最小文档生成与陈旧度报告）均已完成。

当前 C1 证据补充：`validate-decision-package` 已以当前静态世界杯简报集合完成内容级验证；它对下载的简报导出和短名单决策包同样失败关闭。该验证只证明本地合同与已记录字段完整，不替代来源、快照或身份的人工审计。`record-quality-audit` 现在可将维护者实际复核的身份解析或来源主张样本追加到本地账本；`record-quality-threshold` 只在维护者明确给出最大错误率、最小有效样本数和决策文本后追加阈值。`contract-quality --audit-ledger --threshold-ledger` 只汇总有效样本，并在阈值缺失或样本不足时保持 `baseline_required`、在超过维护者设置阈值时失败，绝不自动设定阈值。

## 后续依赖表

| 节点 | 直接依赖 | 解锁结果 |
| --- | --- | --- |
| C1 可信证据内核 | G1 | 来源/许可、快照、身份、契约、模型晋级与回滚成为强门禁 |
| P1 个人决策闭环 | C1 | 维护者可重复完成并迁移至少一个球探、比赛或模型研究工作流 |
| I1 开放互操作与本地视频回链 | C1 + 一个 P1 验收工作流 | 合法本地文件、开放标准和视频时间码可在不丢语义的情况下接入 |
| L1 本地协作与可移植性 | P1；可选 | 通过本地包、备份和导入导出复核，不建设云协作 |
| R1 空间与多模态研究 | C1 + I1 + 合规数据 | 在基线、同步质量和域外验证下开展隔离研究 |
| E1 开放证据协议 | C1 + I1 | 由独立实现验证的开放格式和测试夹具 |
| R2 隐私协作研究 | E1 + 单独安全评审；可选 | 只交换主动批准的公开或聚合结果，不建设服务平台 |
| R3 概率情景模型 | R1；可选 | 以本地、条件化、可失败的概率实验扩展简单基线 |

## 当前冻结项

- 新增顶层导航或宽路由，除非它是已选参考工作流不可替代的步骤并同时完成契约、静态、失败状态、移动端和 E2E。
- 未经独立标签和同切分 baseline 晋级的 NN/GNN/Transformer/强化学习默认模型。
- 没有合规数据、同步质量和域外验证的 tracking/video/off-ball 默认能力。
- SaaS、订阅、企业版、组织账号、默认遥测、默认云同步、实时云协作和集中敏感数据存储。
- 商业数据绕过访问控制的抓取、全球数据采集竞赛、医疗诊断、转会撮合和博彩产品。

## 历史归档

旧阶段、历史交付和调研记录已移动到 [`history/TASKS-2026-07-17.md`](history/TASKS-2026-07-17.md)。它们用于追溯，不改变当前节点状态或依赖判断。
