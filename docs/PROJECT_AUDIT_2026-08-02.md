# ScoutFootball 全项目独立审计 2026-08-02

## 执行记录（2026-08-02 开发窗口）

- 基线工作区：`main`，`git status --short` 为空，未发现未提交改动。
- `uv run ruff check src tests`：通过。
- `node --check frontend/app.js`：通过。
- `uv run pytest tests/unit tests/integration -m "not e2e" -q`：命令本身触发 Windows `uv trampoline failed to canonicalize script path`；等价的 `uv run python -m pytest tests/unit tests/integration -m "not e2e" -q` 运行超过 120 秒后超时，未产生失败汇总。
- `uv run python -m scoutfootball research-health`：退出码 0，运行态 verdict=`not_ready`；blocking reasons 为 lineage unverified、no_reviewable_runs、active_rating_freshness unverified、research_readiness blocked。
- 开发后聚焦验证：`/ratings?limit=5` 返回 `canonical_resolution=ok`，每行带 `canonical_player_id` 与 `canonical_match_ambiguous`；当前样本仍为 unresolved，未做未经确认的同名合并。canonical resolver、API/写入防护相关聚焦测试，以及 Ruff 和 Node 语法检查通过。
- 提交前回归：默认收集明确排除 `tests/e2e`；显式 `-m e2e` 收集 48 项。`uv run python -m pytest tests/unit tests/integration -q` 运行 184 秒后超时，未产生失败汇总；等价命令的超时不作为通过证据。
- 分支清理：在确认当前工作树仅使用 `main` 后，按维护者指令删除 18 个无工作树历史本地分支；未删除远端分支、未推送。
- 运行态边界：以上只证明静态检查、CLI 诊断和测试执行边界；不证明完整回归或外部发布验收。
- 追加复核（2026-08-02）：`uv run pytest ...` 在 Windows 仍先触发 `uv trampoline failed to canonicalize script path`，改用等价入口 `uv run python -m pytest tests/unit tests/integration -m "not e2e" -q --durations=20` 后完整运行约 428 秒，全部通过，2 项跳过；最慢测试为 `tests/unit/test_phase10.py::TestAPI::test_get_match_prediction`，约 177 秒。等待窗口本身不是失败根因，缺失/不完整的可选 PyTorch 环境和生成式 manifest 漂移才是此前失败原因。
- 追加环境修复：`uv sync --extra optimizer` 安装并验证 `torch==2.13.0+cpu`；`uv run python scripts/generate_manifest.py --check` 的 project manifest 与 reference index 均通过。
- 追加候选实验：现有优化器 `20260801T224117Z-872e1349`（`--quick --no-viz`）holdout `N=95`，optimized Spearman=`0.6993`、Pearson=`0.7043`、points MAE=`14.75`、RMSE=`17.34`；新增球队积分 MLP 候选 `20260801T225209Z-team-points-mlp` 使用 fit/validation/test 赛季切分，holdout `N=95`，MAE=`9.94`、RMSE=`11.68`、R²=`0.5041`、Spearman=`0.8023`。两者都未激活；MLP 目标是球队赛季积分代理，不是独立球员能力真值。
- 追加研究健康：候选运行后 `research-health` 仍为 `not_ready`，主要阻塞为 active rating 未绑定激活 run、lineage/freshness unverified、独立合格标签 `0`；不能因候选 holdout 指标改善而升级为 ready。
- 追加最终复核：候选 MLP 写入标准 `meta.json` 后，`research-health` 登记 43 个 run，其中 1 个可复核、41 个不可复核、1 个不可用；独立合格标签仍为 0，故 verdict 仍为 `not_ready`。
- 追加测试兼容性记录：完整回归仍出现 Starlette 的 TestClient/httpx 弃用告警，但不影响本次结果；后续单独评估升级到兼容的 httpx/Starlette 组合或固定兼容版本，避免把依赖迁移与评分模型实验混在同一变更中。
- 追加问题清单复核：A1/A2/A3、写入访问门、MP4 安全边界和默认非 E2E 测试入口已落地；A4 身份覆盖、C3/C4 前端双真源与拆分、C5 单一依赖真源、静态 demo 快照清理及滚动文档归档仍为部分完成，不能标记为全部关闭。

## 后续模型开发与复核（2026-08-02）

- 将球队积分神经候选扩展为可选的普通 MLP 与 Set Transformer。Set Transformer 对每个 `team|league|season` 球员集合执行共享编码、集合自注意力、PMA 池化注意力、位置槽位上限、分钟权重和球队积分回归；旧优化器继续作为 prior、排名基线和回滚依据。
- 在同一 2526 holdout（96 个 Big-5 team-season）上用相同特征、标签、时间切分比较：优化器 Spearman=`0.6954`、points MAE=`14.95`、RMSE=`17.55`；MLP Spearman=`0.6820`、MAE=`11.01`、RMSE=`14.27`、R²=`0.2580`、bias=`-2.56`；默认 Set Transformer Spearman=`0.6559`、MAE=`11.63`、RMSE=`14.35`、R²=`0.2494`、bias=`1.25`。32 维/2 层注意力变体 Spearman=`0.6560`，未超过默认注意力模型。
- 选择 MLP 作为当前最佳神经候选并本地晋级：run=`20260802T-gpu-mlp-selected`，`meta.json`、候选评分 parquet、模型 SHA 和 lineage admission 全部通过；active `player_ratings_optimized.parquet`=`26,663` 行，active `player_rating_model.pt` 与候选模型 SHA 一致，旧 `optimized_params.npy` 与晋级前备份字节一致。Set Transformer run=`20260802T-gpu-set-transformer-selected` 保留为 `reviewable` 研究候选，不替换 MLP。
- 修复 PyTorch 环境：项目 uv source 锁定 `torch 2.13.0+cu130`；实测 `torch.cuda.is_available()=True`、`NVIDIA GeForce RTX 5070 Ti`、矩阵乘法在 `cuda:0` 完成；候选 `metrics.json` 记录 `training_device=cuda`。
- 修复研究健康门禁的语义漏洞：Transfermarkt 身价标签共 `21,037` 行仍允许作为代理监督，但 `independent_rows=0` 时不得把系统升级为 `ready`。当前 `research-health` 已回到 `verdict=not_ready`，原因明确为无独立球员能力标签；这不否定候选模型可复核，只限制真实性结论。
- 聚焦回归：truth-label 与 research-health 测试通过；Ruff 通过。以上晋级为本地、可回滚动作，未推送远端。

> 审计性质：独立只读复核（git 历史、测试配置、依赖管理、仓库卫生、文档契约），与 2026-07-31 的前后端核心审计（`FRONTEND_BACKEND_CORE_AUDIT_2026-07-31.md`）重叠部分重新验证并注明；本文件是新发现 + 确认未修复项的当前清单，是下一个开发窗口的工作输入。
> 审计时点：2026-08-02，分支 `main`（`fc44ac2`），工作区有未提交的版本号类改动（10 文件、18 行，未含任何审计项修复）。
> 已执行：`ruff check src tests` 通过；`test_grain.py`/`test_role_system.py` 定向通过；pytest 收集 5,865 项（含 48 e2e + 34 integration）；`node --check frontend/app.js`、`desktop/app.js` 通过。
> 未执行：全量测试、浏览器 E2E、性能压测、数据重建、任何写接口调用。

## 一、结论

**核心矛盾：功能宽度（24 个前端视图、202 个路由、4 个产品面）远超核心真值能力（独立监督标签 = 0、可复核模型 run = 0）。** 长期自主开发的典型症状全部出现：单体膨胀、测试配置与文档撒谎、文档替代实现、git 历史重写、仓库体积膨胀。项目自省能力强（大部分 P0 已被 2026-07-31 审计识别），但"识别 → 修复"转化率低：截至本审计，P0 项在代码中均无修复痕迹。

## 一.b 维护者报告问题的核实结论（2026-08-02）

### E1 当前评分由优化器训练产出（属实）

- 证据：41 个模型 run 全部来自 `scripts/optimizer/`（产物 `optimized_params.npy` = 77 维位置权重，meta.json 含 pop_size/n_steps/lr/seed），评分 = 权重对特征的线性组合（`scoring.py`），训练目标是球队积分 Spearman/NDCG/校准等组合（代理目标）。`player_ratings_optimized.parquet`（30,483 行）即主球员界面展示的评分文件。NN（`train-rating-nn` / `models/player_rating_nn.py`）仍为样例/实验路径，无任何投产 run。
- 含义：当前"球员评分"是**优化器拟合球队积分代理目标**的产物，不是独立监督验证的球员能力，这与 research_health=not_ready 一致。

### E2 前端部分界面使用默认/演示数值（属实）

- 证据：`frontend/data/value_summary.json` 为 `status=demo / data_mode=synthetic` 的匿名占位数据（"Player A/B/C…"）；`predictions_default.json` 存在（app.js:3029 默认预测文件）；index.html:166-178 首页指标为硬编码数字（8,689 / 10,660 / 27,254 / 11,871）；静态 fallback 映射 `/value-summary → /data/value_summary.json`。
- 含义：后端可达时部分数据会刷新，但 value/预测等视图仍展示 demo 或静态旧快照；来源标签不可逐资源信任（与 FE-001 同一根因）。

### E3 身价数据已在本地但前端未接入（属实，且后端数据是好的）

- 证据：本地 `data/raw/transfermarkt_manual/`（2026-08-02 更新）`player_latest_market_value.csv` 69,441 行，与历史表按 player 取最大日期 100% 一致，有效（value>0）33,590 行，快照截至 2025-09-11；`get_market_value_summary()` 返回真实 top10（Lamine Yamal 2 亿欧 / Haaland / Bellingham 各 1.8 亿 / Mbappé 1.8 亿）。但 `frontend/app.js` 对 `market-value|marketValue|market_value` **零引用**，`/market-value/*` 三个端点无任何前端消费；身价/价值偏差视图（`data-view="value"`）读的是 synthetic `value_summary.json`。
- 含义：CAPABILITIES"前端尚未接入身价视图"属实，且用户看到的"身价"是演示假数据；后端 → 前端链路从未接通。

### E4 同名球员跨赛季被当作不同球员（属实，实体层无 canonical key）

- 证据（实测）：
  - legacy 评分表 `player_ratings_optimized.parquet` 30,483 行**没有 player_id 列**，主键为 `(player, team, league, season)` 名字组合；6,169 个球员名跨多行（Messi 6 行含巴萨+PSG、Cristiano Ronaldo 6 行含皇马/尤文/曼联、Gabriel Jesus 6 行含曼城/阿森纳）。
  - 前端评分表格按行渲染 `name/team/league/season/optimized_score`（app.js 约 5003 行），同一球员跨赛季在排名中占多行，视觉上像多个球员。
  - `players_list.json` 按**名字字符串**去重（10,260 名）——名字去重 ≠ 实体去重：真同名不同人会被合并，名字变体会被分裂（静态 profile 同时存在 `Kylian_Mbappe-Lottin.json` 与 `Kylian_Mbappé.json`）。
  - `player_match.parquet` 的 player_id 双格式混用（`understat|10381` vs `malinovskyi|1993|ukr`）；同源 85 处 (name, source) 映射到多个 player_id（fbref 16 + understat 69）；statsbomb 数值 ID 与 understat/fbref 字符串 ID 无法 join。
- 开发窗口进展：`/ratings` 已消费 `load_resolved_player_ratings` 派生视图，前端支持默认实体视图/赛季视图，并对 unresolved/ambiguous 行显示标记且不合并；当前 registry 仍只有 7 行 resolved，故 Messi 等未确认实体不会被伪造为已聚合。
- 工作项见 WP-E4。

## 二、P0 — 数据真实性（先修）

### A1 评分真实性门禁与主 UI 脱节（CORE-001 未修复）

- 证据：`research_health` 运行态 `not_ready`（lineage unverified / 0 个 reviewable run / 29,723 条标签全为派生 `expert_tier`）；主球员列表仍展示旧 optimized 评分作为普通排名。
- 验收：`not_ready` 时主页面不产生强排名结论；`blocked/candidate/admitted` 三态从 CLI、API 到 UI 一致；静态导出不因离线放宽。

### A2 身份与缺失语义（CORE-002 未修复）

- 证据：27,598 行 player_match 仅 10 个确认映射，legacy 评分表 1,640 行 ambiguous；主画像仍以名字为查询键；缺失值可能回填 0/50。
- 验收：同名不静默合并（返回 ambiguous + 候选）；全核心特征缺失返回 `null` + `missing_reason`，不返回 50；xT/VAEP 关联不以裸姓名 join。

### A3 特征/评分漂移已证实

- 证据：特征矩阵 manifest hash `951d5f39d6fd4b20` vs 最近候选训练 hash `bba38aa0f9c1b233`；历史评估存在 coverage 0.60–0.65 联赛（PL/La Liga）。
- 验收：漂移在 UI 上可见（freshness 标记），不允许作为当前评级排序。

## 三、P0 — 安全边界（2026-07-31 提出，未修复）

### B1 写路由无统一访问门（SEC-001）

- 证据：api_server.py 约 21 个写操作，仅 scouting workspace 有 `_require_workspace_access`；世界杯重置/导入、brief/dossier/review 创建、MP4 导出无统一 loopback 门；服务可绑定 0.0.0.0；CORS 不是授权。
- 验收：默认配置下非 loopback 写请求全部 403；loopback 工作流不破坏；新增写路由漏 guard 时测试失败；不泄露绝对路径和内部异常。

### B2 战术板 MP4 导出（未加固）

- 证据：请求体整读入内存、ffmpeg 处理不可信输入、异常/超时临时文件清理不完整、错误响应可能含本地绝对路径、部分失败返回 200。
- 验收：流式上限；`finally` 清理；响应不含绝对路径；失败返回一致 4xx/5xx envelope。

### B3 战术板 hover 标签 innerHTML 注入（FE-002 未修复）

- 验收：动态标签只写 `textContent`；`<img onerror>` 等按纯文本显示；真实 DOM 测试而非源码字符串断言。

## 四、P1 — 测试 / CI / 架构（我实测确认）

### C1 默认测试包含 E2E（TEST-001 未修复）

- 证据：`pyproject.toml` addopts 仅 `-q`；`uv run pytest -q`（AGENTS.md 标准命令）收集 5,865 项，含 48 e2e + 34 integration；`ci.yml` test job 全量直跑。
- 验收：默认命令与文档一致（`-m "not e2e"`）；CI 分 unit/integration/e2e/frontend 独立 job。

### C2 TestClient 弃用告警

- 证据：每次测试输出 `StarletteDeprecationWarning: httpx + starlette.testclient is deprecated`。
- 验收：消除告警或显式锁定兼容版本并记录升级计划。

### C3 前端测试与体量不匹配

- 证据：`frontend/app.js` ~30K 行 / 1.6MB，Node 测试仅 4 文件 40 项；`desktop/app.js` 与 `frontend/app.js` 为差一个字节的近亲副本（仅 `APP_VERSION` 常量不同），靠 FRONTEND_SYNC.md 人工同步。
- 验收：先抽 `data-client`/`view-router`/`safe-dom` 模块并迁移测试；消除前端双真源（desktop 与 frontend 由构建/脚本同步，或明确单真源）。

### C4 单体与产品面过宽

- 证据：`api.py` 14K 行 / 581KB、`api_server.py` 2.6K 行、`frontend/index.html` 2.8K 行；Streamlit（15 页）+ 静态前端 + FastAPI + Electron + Cloudflare + Render（`backend-health-check.yml` 引用 onrender.com）+ Vercel。
- 验收：新功能不再默认落 `app.js`/`api.py`；Streamlit 与主产品收敛或明确废弃；公共部署与本地优先章程的冲突显式决策。

### C5 依赖管理双真源

- 证据：`requirements.txt`（含编码乱码 `�?excludes`）+ `pyproject.toml`/`uv.lock` + 被 ignore 的 `package-lock.json`。
- 验收：单一声明真源，其余为生成的派生物；修复乱码注释。

## 五、P2 — 仓库卫生 / 文档 / git

- D1 **git 体积膨胀**：tracked 共 158MB data/（432 文件），含 6 个 `.bak-20260605044151` 备份（6.2MB parquet + 5 CSV）、82 个模型运行产物、216 个 `frontend/data/` 静态快照；违反 AGENTS.md"永不提交本地运行输出"。验收：`.bak` 出库；静态快照走发布流程而非常态提交。
- D2 **git 历史重写过两次**（`merge: integrate local ScoutFootball history` / `merge: preserve remote public history`），13 个未合并分支（codex/* ×10、solo/* ×3）残留。验收：删除或归档陈旧分支；发布走 tag。
- D3 **文档体量失控**：TASKS.md 293KB、CODEX_CONTINUOUS_STATE.md 325KB、DATA_CONTRACTS.md 149KB。验收：状态数字改由脚本生成（`generate_manifest.py` 方向），滚动状态归档。
- D4 **工作区残留**：10 个文件仅版本号改动未提交。验收：发布收尾提交完整。

## 六、修复顺序（不重写、不停机）

1. **迭代 0 — 诚实显示**：A1 + B1 最小版 + C1（fail-closed 展示、写路由统一门、测试分层）。不新增评分/页面。
2. **迭代 0+ — 数据链路接通（维护者优先级）**：
   - WP-E3 **身价前端对接**：`frontend/app.js` 接入 `/market-value/summary`、`/market-value/players`（新增或改造 `data-view="value"` 视图），显示真实身价（含快照日期 2025-09-11、source/license 归因、0 值占位过滤说明）；synthetic `value_summary.json` 不得作为身价展示，降级为仅在"价值偏差/公平性"研究视图保留并显式标注 demo。
   - WP-E2 **视图数据源盘点**：逐一核对 24 个视图，输出每视图数据源清单（API live / 静态快照 / demo synthetic / 硬编码），demo 与硬编码项必须显示来源状态（落到 WP-02 的 provenance 契约）；至少消灭 `predictions_default.json` 与首页硬编码数字两类。
   - WP-E1 **评分来源标注**：主球员界面显示"当前评分 = 优化器代理目标产物（非独立验证）"来源行 + 优化器 run_id/args 摘要，与 research_health 门禁联动。
   - WP-E4 **同名球员实体聚合**：评分排名按 canonical 实体展示——复用 PRS-1 已交付的 `canonical_resolver`/`identity_registry`（`load_resolved_player_ratings`），让 legacy 评分表挂上 `canonical_player_id` 派生列；排名视图同一球员只出现一次（默认显示最新赛季或可切换"球员视图/赛季视图"）；名字变体 profile 文件合并（`Kylian_Mbappe-Lottin.json` vs `Kylian_Mbappé.json`）；无 canonical key 的行显示 unresolved 标记，不得静默合并真同名不同人。验收：Messi 在球员列表与排名中只出现一次；同名不同人（如 Gabriel）不合并。
3. **迭代 1 — 可信评级垂直切片**：A2 + A3（canonical 身份 → rating admission → UI 一条链）。
4. **迭代 2 — 安全细化**：B2 + B3 + 前端模块抽取（C3）。
5. **迭代 3 — 卫生与治理**：C2/C4/C5 + D1–D4。

## 七、任何工作项的完成定义（沿用 7-31 审计第 12 节）

语义明确、契约可机器验证、写边界统一、不依赖名字模糊 join、单元+契约+至少一条真实浏览器流程、有命令与产物 hash 证据、兼容回退、TASKS/CAPABILITIES 同步更新。**静态检查通过、测试收集通过、定向测试通过 ≠ 运行态准入完成。**

## 八、根因分析：为什么交付了很多工具，主链路却不使用（2026-08-02）

### 现象（全部经实测证实）

- canonical 身份工具链已交付（PRS-1 verified：`canonical_resolver`/`identity_registry`/`cohort`/`role_system`），但主评分链路未消费：30,483 行评分仅 7 行 resolved、1,640 行 ambiguous，前端仍按名字+赛季展示。
- `/market-value/*` 三个端点交付且数据真实，前端 0 引用，身价视图展示 synthetic demo。
- 41 个模型 run 中 0 个可复核、research_health=not_ready，主球员界面仍把优化器评分当普通排名展示。
- 前端 24 个视图中有 demo/硬编码/静态旧快照数据源，视觉上"看起来有数据"。

### 根因（按贡献度排序）

1. **验收定义偏"组件自洽"，缺"主链路接入"项。** 每个 PRS 切片的验收 = 模块 + CLI + 单元测试 + 文档/能力表登记，从未有一条验收要求"主评分链路或主 UI 消费本模块"。工具在侧链上完成即被标 verified。
2. **文档驱动形成"完成假象"。** TASKS.md / CAPABILITIES.md / CODEX 滚动状态把"工具存在 + 单测通过 + 文档已写"呈现为"已交付"，文档替代了产品流程验证，后续窗口从文档出发信任旧结论，不再复核主链路。
3. **开发节奏奖励新切片、惩罚整合。** 每窗口产出新 `feat(PRS-x slice N)` 提交容易得分；把旧模块接入主链路没有新提交名目、回归风险大、验收模糊，因此永远不被排期。审计建议"停止横向扩张"也与这种节奏相反。
4. **静态 fallback 掩盖了前后端断裂。** 前端读 `frontend/data/*.json` 即可自洽运行，后端端点可独立交付；两个平行世界没有汇合点，断裂（前端不调 API、静态快照过期）在视觉上不可见，也未被测试捕获（e2e 默认不跑、前端 Node 测试仅 40 项、无"UI→数据文件"垂直链路测试）。
5. **没有"产品主流程"的单一 owner。** 没有任何环节回答"首页/球员页的数据从哪来、显示什么、何时可称完成"；各轮次 agent 各自交付组件后即离开。
6. **功能暴露无门。** UI 始终展示全部 24 个视图（哪怕数据源是 demo），未完成状态从不被隐藏，用户（和 agent）无法区分"已接入"与"占位"。

### 对策（已纳入开发窗口提示词）

- **暴露门（feature gating）**：未接入真实数据源、未过验收的视图一律前端隐藏（导航入口移除/禁用），后端与数据层代码保留不动；完善后再暴露。隐藏状态登记在视图清单（`docs/VIEW_DATA_SOURCES.md`）中，避免丢失待办。
- **验收追加"主链路接入"**：任何工具交付必须满足"主 UI 或主 API 链路消费 + 集成/垂直测试证明"才可标 verified；纯 CLI 工具仍可交付，但必须写明"未接入主链路"。
- **视图盘点（WP-E2）即暴露门的执行依据**：live/静态快照（fresh）→ 显示；demo/硬编码/未接入 → 隐藏或显示"开发中"占位。
