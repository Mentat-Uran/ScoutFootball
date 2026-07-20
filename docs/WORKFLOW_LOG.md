# 工作流记录

> 初版：2026-07-17。本文记录维护者在 ScoutFootball 中的真实个人任务和参考工作流执行证据。
>
> **状态：部分填写。** 3.1 数据导入与验证工作流已有真实执行证据（2026-07-17）。其余工作流待维护者填写。

## 填写说明

每个工作流记录需包含：

- **是否在用**：是 / 否 / 偶尔
- **输入**：实际使用时输入了什么（数据源、参数、范围）
- **步骤**：实际执行的 CLI 命令或前端操作
- **输出**：得到了什么（文件、视图、决策）
- **现有替代工具**：之前用什么工具完成同样任务
- **错误和阻断**：遇到的真实问题
- **复盘证据**：至少一次真实端到端运行的截图、日志或人工备注

---

## 1. 球探决策工作流

对应前端视图：`scouting`（球探工作台）、`players`（球员列表）、`compare`（球员比较）

对应 CLI：`scoutfootball truth-labels`、`scoutfootball transfermarkt-truth`

### 1.1 候选球员筛选与比较

- **是否在用**：待填写
- **输入**：待填写（位置、联赛、年龄范围、最低评分）
- **步骤**：待填写
- **输出**：待填写（候选名单、比较表、导出文件）
- **现有替代工具**：待填写
- **错误和阻断**：待填写
- **复盘证据**：待填写

### 1.2 真值标签录入与复核

- **是否在用**：待填写
- **输入**：待填写
- **步骤**：待填写（`scoutfootball truth-labels` 流程）
- **输出**：待填写
- **现有替代工具**：待填写
- **错误和阻断**：待填写
- **复盘证据**：待填写

---

## 2. 比赛准备工作流

对应前端视图：`matches`（比赛列表）、`teams`（队伍）、`tactical`（战术板）、`wc_schedule`（世界杯赛程）

对应 CLI：`scoutfootball tournament`、`scoutfootball serve`

### 2.1 赛前简报与对手分析

- **是否在用**：待填写
- **输入**：待填写（比赛、队伍、时间范围）
- **步骤**：待填写
- **输出**：待填写（简报、战术板配置、预测）
- **现有替代工具**：待填写
- **错误和阻断**：待填写
- **复盘证据**：待填写

### 2.2 世界杯赛程模拟与情景假设

- **是否在用**：待填写
- **输入**：待填写
- **步骤**：待填写（`scoutfootball tournament` 子命令流程）
- **输出**：待填写（小组 standings、淘汰赛 bracket、出线概率）
- **现有替代工具**：待填写
- **错误和阻断**：待填写
- **复盘证据**：待填写

---

## 3. 数据与模型研究工作流

对应前端视图：`value`（球员价值）、`actions`（动作价值）、`reports`（报告）

对应 CLI：`scoutfootball ingest`、`scoutfootball build-features`、`scoutfootball train`、`scoutfootball train-rating-nn`、`scoutfootball action-value`、`scoutfootball optimize-ensemble`、`scoutfootball preflight`

### 3.1 数据导入与验证

- **是否在用**：是
- **输入**：本地已存在的 6 个数据源快照（StatsBomb Open、Football-Data、ClubElo、Understat、FBref、Transfermarkt 手动），无需联网抓取
- **步骤**：
  1. `uv run python -m scoutfootball info` — 确认模块和命令状态
  2. `uv run python -m scoutfootball validate` — 运行 6 项数据验证门禁
  3. `uv run python -m scoutfootball preflight --target key --evidence-out data/reports/data_health/preflight-evidence-2026-07-17.json` — 对 21 个关键 Parquet 产物执行内容级 preflight，并保留本地可复核证据报告
- **输出**：
  - validate 结果：`Validation: PASS (6/6 checks passed)`
  - preflight 结果：`21/21 ok, 0 unreadable, 0 footer/content mismatch, 0 flagged`
  - evidence report：`data/reports/data_health/preflight-evidence-2026-07-17.json`；记录 21 个 content-level inspection，9 个已登记 source license；未登记的 snapshot 与 lineage 保持 `not_recorded`
  - 关键产物行数确认（见下方复盘证据）
- **现有替代工具**：无（此前没有统一的数据验证和 preflight 入口；G0-B 新增了 `preflight` 命令）
- **错误和阻断**：无。本次运行全部通过
- **复盘证据**：见下方"参考工作流端到端运行证据"

### 3.2 模型训练与评估

- **是否在用**：偶尔（Dixon-Coles 训练路径已端到端验证；NN 评分训练和 ensemble 优化仍按 3.3 节使用）
- **输入**：本地 `data/gold/feature_store/team_match.parquet`（137906 行，覆盖 Big Five 联赛多赛季）
- **步骤**：
  1. `uv run python -m scoutfootball build-features`（已运行过；team_match.parquet 存在）
  2. `uv run python -m scoutfootball train` 调用 `pipeline.run_weekly_train`，其中 `fit_independent_poisson` + `fit_dixon_coles(decay=0.005)` + DC calibration backtest + isotonic 概率校准
  3. 本轮额外执行的真实数据烟雾测试：直接对 `team_match.parquet` 调用 `fit_dixon_coles`，确认 NaN 过滤生效
- **输出**：`data/models/artifacts/dixon_coles_results.parquet`、`dc_team_strengths.parquet`、`dc_calibration_report.parquet`；本轮修复后所有参数 finite
- **现有替代工具**：无（此前无统一的 DC 训练入口与校准链路）
- **错误和阻断**：本轮发现并修复 `fit_dixon_coles` 对 NaN 进球的静默损坏路径，详见下方"参考工作流 3"
- **复盘证据**：见下方"参考工作流 3：DC 模型 NaN 进球数值稳定性修复"

### 3.3 动作价值与优化器

- **是否在用**：是（评分权重优化器与模型候选治理部分在用；动作价值与 ensemble 优化待填写）
- **输入**：本地 `data/` 目录的 5 个已加载来源（fbref_standard、fbref_misc、fbref_shooting、understat、football_data_results），时间切分 `train=1617..2425 / test=2526`
- **步骤**：
  1. `uv run python scripts/optimize_ratings_gpu.py --data_dir ./data --quick --no-viz` — 在 CPU 上快速生成 reviewable 候选
  2. `uv run python -m scoutfootball model-admission --json` — 检查候选是否 `reviewable`（7 项 evidence 检查）
  3. `uv run python -m scoutfootball promote-model-run <run_id> --decision "..." --confirm --json` — 晋级候选到活跃产物（创建带 sha256 的备份）
  4. `uv run python -m scoutfootball rollback-model-run <backup_id> --decision "..." --confirm --json` — 从备份还原活跃产物
  5. `uv run python -m scoutfootball reject-model-run <run_id> --decision "..." --confirm --json` — 拒绝候选（元数据操作，不删除文件）
- **输出**：
  - 候选 run 目录 `data/models/runs/<timestamp>-<uuid8>/`，含 `meta.json`（lineage、metrics、error_cases、activation 状态）+ `optimized_params.npy` + `player_ratings_candidate.parquet` + `training_history.json`
  - 备份目录 `data/models/backups/<backup_timestamp>-<run_id>-<uuid8>/`，含 `manifest.json` + 三个 baseline 活跃产物副本
  - 晋级时活跃产物 sha256 替换为候选 sha256；回滚时还原为 baseline sha256
- **现有替代工具**：无（此前优化器 run 全部 `not_reviewable`，无晋级/回滚/拒绝的治理路径；C1 新增了 4 个 lifecycle 命令）
- **错误和阻断**：无。本次运行全部通过
- **复盘证据**：见下方"参考工作流 2：模型候选治理与可逆晋级"

---

## 参考工作流端到端运行证据

> G0-A 子任务 3 要求：选择至少一个会重复使用的参考工作流，保存一次真实端到端运行和人工复盘证据。

### 参考工作流 1：数据导入与验证（3.1）

- **选择的工作流**：3.1 数据导入与验证
- **执行日期**：2026-07-17
- **执行环境**：Windows, Python 3.11, uv, 工作目录 `c:\football\scoutlab`
- **真实输入**：本地已存在的 6 个数据源快照，21 个关键 Parquet 产物
- **执行步骤与命令**：
  ```bash
  # 1. 确认模块和命令状态
  PYTHONPATH=src uv run python -m scoutfootball info

  # 2. 运行数据验证门禁
  PYTHONPATH=src uv run python -m scoutfootball validate

  # 3. 对关键 Parquet 产物执行内容级 preflight，并显式保存本地证据报告
  PYTHONPATH=src uv run python -m scoutfootball preflight --target key --evidence-out data/reports/data_health/preflight-evidence-2026-07-17.json
  ```
- **执行结果**：
  - `info`：正常输出 8 个模块和 11 条命令清单
  - `validate`：`Validation: PASS (6/6 checks passed)`，退出码 0
  - `preflight`：`21/21 ok, 0 unreadable, 0 footer/content mismatch, 0 flagged`，退出码 0
  - `preflight --evidence-out`：本地写入 `data/reports/data_health/preflight-evidence-2026-07-17.json`；21 个 artifact inspection 均通过，已登记的 source license 为 9 个，snapshot 和 lineage 均未登记并如实输出为 `not_recorded`
  - 关键产物行数（preflight 确认 footer 与 content 一致）：

    | 产物路径 | 行数 | 列数 | 大小 |
    |---|---|---|---|
    | raw/football_data/combined_results.parquet | 68953 | 190 | 5.9 MB |
    | raw/statsbomb_open/matches_all.parquet | 2187 | 12 | — |
    | raw/statsbomb_open/events_sample.parquet | 11871 | 137 | — |
    | raw/understat/players_10seasons.parquet | 31902 | 20 | — |
    | raw/fbref/player_standard_5seasons.parquet | 14356 | 26 | — |
    | gold/feature_store/player_match.parquet | 27598 | 32 | 1.21 MB |
    | gold/feature_store/team_match.parquet | 137906 | 24 | — |
    | gold/feature_store/player_ratings.parquet | 8595 | 23 | — |
    | gold/feature_store/player_truth_labels.parquet | 29723 | 8 | 0.39 MB |
    | gold/feature_store/player_value_metrics.parquet | 3740 | 30 | — |
    | gold/feature_store/player_action_value.parquet | 9951 | 29 | — |
    | gold/feature_store/rating_feature_matrix.parquet | 26678 | 40 | 1.2 MB |

- **人工复盘**：
  - **是否达到预期**：是。数据验证和 preflight 全部通过，21 个关键产物的 footer 行数与 content 行数一致，无损坏文件，无需隔离。
  - **有什么问题**：无。本次运行无错误、无阻断。
  - **下一步改进**：C1 的后续切片应补齐 source health、append-only snapshot 和 lineage 的真实记录；本次报告不会根据文件名或时间戳猜测它们。G0-B 已清理 workflow 的 fail-open 模式，`preflight` 可作为发布门禁接入。
- **是否可重复使用**：是。此工作流不依赖网络（数据已在本地），可随时重复执行。维护者每次数据更新后都应运行 `validate` + `preflight --evidence-out <new-path>` 确认完整性，并保留新的本地证据文件。

### 参考工作流 2：模型候选治理与可逆晋级（3.3 评分权重优化器部分）

- **选择的工作流**：3.3 评分权重优化器的模型候选治理子流程（生成 → admission → promote → rollback）
- **执行日期**：2026-07-19
- **执行环境**：Windows, Python 3.12.11, uv, CPU 模式（`torch 2.13.0+cpu`），工作目录 `c:\football\scoutlab`
- **真实输入**：本地 5 个已加载来源（fbref_standard、fbref_misc、fbref_shooting、understat、football_data_results）；`--quick` 模式（steps=80, pop=6, patience=15, warmup=8, 跳过 CV/稳定性/重要性）；时间切分 `train=1617..2425 / test=2526`
- **执行步骤与命令**：
  ```bash
  # 0. 先记录 baseline 活跃产物的 sha256（用于回滚后比对）
  #    ratings=B657F3E4... size=2101840
  #    params=7F0534FC... size=436
  #    meta  =E27BEAC8... size=26776

  # 1. 生成 reviewable 候选（CPU 上约 1 分钟）
  uv run python scripts/optimize_ratings_gpu.py --data_dir ./data --quick --no-viz
  # → 生成 data/models/runs/20260719T142124Z-631abaea/

  # 2. 验证候选 admission 状态（8 项 evidence 检查）
  uv run python -m scoutfootball model-admission --json
  # → reviewable_run_count: 1（parameter_artifact、recorded_lineage、
  #   time_split、baseline_holdout、candidate_holdout、error_cases、
  #   required_inputs、candidate_rating_artifact 全部满足）

  # 3. 晋级候选到活跃产物（创建带 sha256 校验的备份）
  uv run python -m scoutfootball promote-model-run 20260719T142124Z-631abaea \
      --decision "C1 admission gate verification: promote reviewable candidate" \
      --confirm --json
  # → 创建 data/models/backups/20260719T142324Z-20260719T142124Z-631abaea-f1416f39/
  # → 活跃产物 sha256 替换为候选 sha256
  #    ratings=F6034D7F... size=1903108
  #    params=D5678C2E... size=436
  #    meta  =48010E9B... size=13226

  # 4. 从备份还原活跃产物
  uv run python -m scoutfootball rollback-model-run \
      20260719T142324Z-20260719T142124Z-631abaea-f1416f39 \
      --decision "C1 admission gate verification: restore original active artifacts after promote test" \
      --confirm --json
  # → 活跃产物 sha256 还原为 baseline
  #    ratings=B657F3E4... size=2101840  ✓ 与 baseline 完全一致
  #    params=7F0534FC... size=436        ✓ 与 baseline 完全一致
  #    meta  =E27BEAC8... size=26776      ✓ 与 baseline 完全一致
  ```
- **执行结果**：
  - 候选 run `20260719T142124Z-631abaea` 在 `model-admission` 中状态为 `reviewable`，8 项 evidence 检查全部通过（含 candidate_rating_artifact SHA-256 校验）
  - 候选 meta.json 关键字段：`lineage.status=recorded`、`lineage.feature_manifest.path=gold/feature_store/rating_feature_matrix_manifest.json`、`activation.status=rolled_back`、`activation.backup_id=20260719T142324Z-20260719T142124Z-631abaea-f1416f39`
  - 候选 metrics（test split）：baseline Spearman=0.6028 → optimized Spearman=0.6993（+0.0965）；baseline points MAE=18.22 → optimized points MAE=14.75（-3.47）
  - 候选 error_cases：over_estimated 5 队（Wolfsburg +1.4 .. Burnley +8.9）、under_estimated 5 队（Parma -35.0 .. Bologna -30.8）
  - promote 创建备份目录，含 `manifest.json` + 三个 baseline 活跃产物副本（带 sha256 校验）
  - rollback 后三个活跃产物 sha256 与 baseline 完全一致，可逆性得到端到端验证
- **人工复盘**：
  - **是否达到预期**：是。这是首次在当前 snapshot 上生成 `reviewable` 候选（此前 40 个历史 run 全部 `not_reviewable`，主因是缺 `rating_feature_matrix_manifest.json`）。promote/rollback 端到端可逆，活跃产物 sha256 在回滚后与 baseline 字节级一致。
  - **有什么问题**：无功能性阻断。运行时有一条 `FutureWarning: DataFrame concatenation with empty or all-NA entries is deprecated`（understat 拼接，data.py:439），不影响结果，未修复。
  - **reject 路径覆盖**：reject 是纯元数据操作（不删除候选目录、不变更活跃产物），由单元测试 `tests/unit/test_model_run_lifecycle.py::test_rejection_is_a_confirmed_metadata_action_that_keeps_candidate` 覆盖（验证 dry-run 保持 `not_activated`、`--confirm` 翻转为 `rejected` 且候选目录保留）。本次未重复跑 quick run 作为 reject 目标，因为该路径不涉及活跃产物可逆性这种需要端到端实测的场景。
  - **下一步改进**：C1 退出门槛第 3 条已端到端验证。`data/raw/transfermarkt/` 遗留未登记目录已于 2026-07-19 对齐（3 个 CSV 移动到已登记的 `data/raw/transfermarkt_manual/`，`pipeline.py` 和 `fill_truth_labels.py` 路径同步更新，`contract-quality` 的 `unregistered_raw_directories` 检查从 `fail` 转为 `pass`）。2026-07-19 后续补：`model-admission` 新增第 8 项 `candidate_rating_artifact` 检查，确保 `player_ratings_candidate.parquet` 存在且 SHA-256 与 meta.json 一致，`reviewable` 状态不再具有误导性；同时补齐该 run 目录下未被 git 跟踪的 `player_ratings_candidate.parquet` 和 `training_history.json`，与 DATA_CONTRACTS.md 声明的候选产物清单一致。剩余 C1 退出门槛包括补齐 6 个来源的 `snapshot_date`、建立身份/来源审计样本和阈值。
- **是否可重复使用**：是。维护者每次模型迭代后可重复执行 `optimize_ratings_gpu.py → model-admission → promote-model-run` 流程；如需还原，使用 `rollback-model-run <backup_id>`。候选 meta.json 完整记录了 lineage、metrics、error_cases、args，可在同一 snapshot 上复算。

### 参考工作流 3：DC 模型 NaN 进球数值稳定性修复（3.2 模型训练子流程）

- **选择的工作流**：3.2 模型训练的 Dixon-Coles 子流程（数据真实性 bug 修复）
- **执行日期**：2026-07-20
- **执行环境**：Windows, Python 3.12.11, uv, 工作目录 `c:\football\scoutlab`
- **真实输入**：本地 `data/gold/feature_store/team_match.parquet`，137906 行；其中 2 行 `goals_for` 为 NaN、2 行 `goals_against` 为 NaN，对应 1 个不完整 home-away pair（`fd-match-64766`）
- **bug 现象**：
  - 运行 `uv run pytest tests/unit/test_phase10.py::TestAPI::test_get_match_prediction` 时，`scipy.stats.poisson.logpmf` 与 `scipy.optimize._numdiff` 抛出 `RuntimeWarning: invalid value encountered in cast` 和 `invalid value encountered in subtract`
  - 根因：`match_prediction.py:294` 处 `hg.astype(int)` 对 NaN 产生平台依赖无效值，scipy 数值微分在 NaN 上产生 NaN，L-BFGS-B 在不抛错的情况下可能收敛到不可靠参数
- **修复**：
  - 在 `fit_dixon_coles` 内、`matches_merged` 构建后立即添加 NaN 进球过滤逻辑（`src/scoutfootball/models/match_prediction.py` 第 232-248 行）
  - 记录 `logger.warning` 含 match_id 列表（前 10 个）
  - 若全部 match 为 NaN 进球，抛出 `ValueError("No complete home-away match pairs with non-NaN goals found")`，不静默返回空模型
- **回归测试**（`tests/unit/test_match_prediction.py`）：
  1. `TestFitIndependentPoisson.test_nan_goals_skipped_in_aggregations` — 验证 IP 模型在 NaN 进球上不产生 NaN 强度，使用 `warnings.simplefilter("error", RuntimeWarning)` 在未来若 NaN 路径被破坏会立即失败
  2. `TestFitDixonColes.test_nan_goals_dropped_with_warning` — 验证 DC 模型在 NaN 进球上丢弃对应 match，参数全部 finite
  3. `TestFitDixonColes.test_all_nan_goals_raises` — 验证全部 NaN 进球时显式抛 `ValueError`
- **执行步骤与命令**：
  ```bash
  # 1. lint
  uv run ruff check src/scoutfootball/models/match_prediction.py tests/unit/test_match_prediction.py

  # 2. 单元测试（43/43 通过）
  uv run pytest tests/unit/test_match_prediction.py -v

  # 3. 原来会触发 RuntimeWarning 的测试（现在通过且无 warning）
  uv run pytest tests/unit/test_phase10.py::TestAPI::test_get_match_prediction -v

  # 4. 全量回归（unit + integration）
  uv run pytest tests/unit/ tests/integration/

  # 5. 真实数据烟雾测试
  uv run python -c "
  import pandas as pd
  from scoutfootball.models.match_prediction import fit_dixon_coles
  df = pd.read_parquet('data/gold/feature_store/team_match.parquet')
  print(f'input rows: {len(df)}')
  print(f'NaN goals_for rows: {df[\"goals_for\"].isna().sum()}')
  m = fit_dixon_coles(df, decay=0.005)
  print(f'model.num_matches: {m.num_matches}')
  print(f'home_adv: {m.home_advantage:.4f} / rho: {m.rho} / league_mean: {m.league_mean_goals:.4f}')
  print(f'teams: {len(m.team_attack)} / finite attacks: {all(__import__(\"numpy\").isfinite(v) for v in m.team_attack.values())}')
  "
  ```
- **执行结果**：
  - ruff check 通过
  - `test_match_prediction.py`：43/43 通过
  - `test_phase10.py::TestAPI::test_get_match_prediction`：通过且无 RuntimeWarning
  - 全量 unit + integration：通过（仅 2 skipped，与本次修改无关）
  - 真实数据烟雾测试输出：
    ```
    WARNING scoutfootball.models.match_prediction: Dropping 1 match(es) with NaN goals from Dixon-Coles fit: ['fd-match-64766']
    input rows: 137906 / NaN goals_for rows: 2 / model.num_matches: 68952
    home_adv: 0.2399 / rho: 0.0 / league_mean: 1.3373
    teams: 522 / finite attacks: True
    ```
- **人工复盘**：
  - **是否达到预期**：是。bug 根因（NaN cast 到 int 的平台依赖行为）已被显式过滤取代；维护者现在能看到 `logger.warning` 知道哪些 match 被丢弃，而不是看到 scipy 的 RuntimeWarning 后被迫猜测原因
  - **有什么问题**：无。修复未改变正常数据路径的行为；`team_match.parquet` 中只有 1 个 match 被丢弃，参数与修复前的"看似收敛"结果在数量级上一致（home_adv ~0.24，rho ~0.0），但现在可以证明参数是 finite 的
  - **数据治理启示**：`team_match.parquet` 中存在 NaN 进球本身是数据质量问题，应在 `build-features` 阶段或 `validate` 阶段增加 NaN 进球检查；但这超出本轮 bug 修复范围，留作后续任务
  - **下一步改进**：C1 的 `validate` 或 `preflight` 可以新增"team_match 中 NaN 进球比例"检查；当前不阻塞 DC 训练，但应让维护者每次 build-features 后看到统计
- **是否可重复使用**：是。修复是 `fit_dixon_coles` 的内部防御性逻辑，对所有调用方（`pipeline.run_weekly_train`、`api.get_ensemble_prediction`、`fit_dixon_coles_with_form`）透明生效。维护者每次训练时若数据再次出现 NaN 进球，会看到 warning 而非 silent corruption。

### 参考工作流 4：football_data 未来比赛占位行源头过滤（3.1 数据导入子流程）

- **选择的工作流**：3.1 数据导入的 football_data → team_match 构建子流程（数据真实性源头修复）
- **执行日期**：2026-07-20
- **执行环境**：Windows, Python 3.12.11, uv, 工作目录 `c:\football\scoutlab`
- **真实输入**：本地 `data/raw/football_data/combined_results.parquet`，68953 行；其中 1 行（Bastia vs Red Star 2025-12-05，法乙 F2）的 FTHG/FTAG/FTR 全部为 NaN，是 football-data.co.uk 对未来未踢比赛的占位行
- **根因**：football-data.co.uk 的 results CSV 在赛季进行中会包含未来赛程的占位行，进球字段为空；`rebuild_combined_results` 原样保留这些行进入 `combined_results.parquet`，`_build_team_match_from_football_data` 没有过滤它们，导致 NaN 进球进入 `team_match.parquet` 并触发下游 `fit_dixon_coles` 的数值稳定性 bug（见参考工作流 3）
- **修复**：
  - 在 `_build_team_match_from_football_data` 中、`pd.to_numeric(FTHG/FTAG)` 之前添加 NaN 过滤（`src/scoutfootball/pipeline.py` 第 609-630 行）
  - 记录 `logger.info` 含被过滤行数和前 5 行样例（match_date、Div、HomeTeam、AwayTeam）
  - 若全部行都是 NaN 占位符，抛 `ValueError` 指向 raw 文件路径，说明数据可能仅有未来赛程
  - 过滤在 `match_id` 分配之前发生，因此过滤后 match_id 重新连续编号，不会留下空缺
- **回归测试**（`tests/unit/test_phase10.py::TestPipeline`）：
  1. `test_build_team_match_filters_nan_goals_placeholder_rows` — 构造 2 个合法 match + 1 个 NaN 占位符，验证输出 4 行（2 match × 2 team）、0 NaN、占位符队伍不出现
  2. `test_build_team_match_all_nan_raises` — 构造全 NaN 行，验证抛 `ValueError` with "future-match placeholders"
- **执行步骤与命令**：
  ```bash
  # 1. lint
  uv run ruff check src/scoutfootball/pipeline.py tests/unit/test_phase10.py

  # 2. 单元测试（TestPipeline 5/5 通过，含新增 2 个）
  uv run pytest tests/unit/test_phase10.py::TestPipeline -v

  # 3. 全量回归
  uv run pytest tests/unit/ tests/integration/ -q

  # 4. 真实数据烟雾测试（只读 raw，不写 gold）
  uv run python -c "
  from scoutfootball.config import PlatformSettings
  from scoutfootball.pipeline import _build_team_match_from_football_data
  import logging; logging.basicConfig(level=logging.INFO)
  settings = PlatformSettings.from_root()
  tm = _build_team_match_from_football_data(settings)
  print(f'rows: {len(tm)} / NaN goals_for: {tm[\"goals_for\"].isna().sum()} / NaN goals_against: {tm[\"goals_against\"].isna().sum()}')
  "
  ```
- **执行结果**：
  - ruff check 通过
  - TestPipeline：5/5 通过（原 3 个 + 新增 2 个）
  - 全量 unit + integration：通过（仅 2 skipped，与本次修改无关）
  - 真实数据烟雾测试输出：
    ```
    INFO scoutfootball.pipeline: Filtering 1 future-match placeholder row(s) from Football-Data (FTHG/FTAG NaN): [{'match_date': Timestamp('2025-12-05 00:00:00'), 'Div': 'F2', 'HomeTeam': 'Bastia', 'AwayTeam': 'Red Star'}]
    rows: 137904 / NaN goals_for: 0 / NaN goals_against: 0
    ```
  - 与 pre-fix baseline 对比：rows 137906 → 137904（-2，即 1 个 match pair 被过滤），NaN goals 从 2/2 降为 0/0
- **人工复盘**：
  - **是否达到预期**：是。源头过滤生效，team_match.parquet 重建后不再含 NaN 进球；DC 训练链路的 NaN 防御（参考工作流 3）现在变成真正的"defense in depth"而不是第一道防线
  - **有什么问题**：无。过滤逻辑在 `match_id` 分配之前，因此 match_id 重新编号不会留下空缺；Bastia 和 Red Star 因有其他合法比赛（如 2025-02-21 的 1-0）仍出现在 team_match 中，这是预期行为
  - **数据治理启示**：football-data.co.uk 的未来比赛占位行是上游数据源行为，不在项目控制范围；但项目应在导入阶段就过滤它们，而不是依赖下游模型训练的防御性逻辑。`rebuild_combined_results`（raw CSV → combined_results.parquet）目前不过滤，因为它的职责是原样保留 raw 数据；过滤放在 `_build_team_match_from_football_data`（raw → gold）更合适
  - **下一步改进**：原计划在 `validate` 命令中增加"team_match NaN 进球比例"检查作为发布门禁，当时判断"源头过滤已经消除了这个问题，validate 检查是冗余的 defense in depth"。**该判断已被参考工作流 5 推翻**：validation 检查实际捕获了"源头过滤修复未持久化到磁盘产物"的真实 Layer 1 失效。已实现，见参考工作流 5。
- **是否可重复使用**：是。修复是 `_build_team_match_from_football_data` 的内部防御性逻辑，对 `run_build_features` 调用方透明生效。维护者每次 build-features 后若 raw 数据新增未来比赛占位行，会看到 INFO 日志知道过滤了多少行。

---

### 参考工作流 5：validation goals 完整性检查捕获磁盘产物未重建（3.1 数据导入 + 发布门禁子流程）

- **选择的工作流**：3.1 数据导入的 validation 发布门禁子流程（pre-training gate 扩展）
- **执行日期**：2026-07-20
- **执行环境**：Windows, Python 3.12.11, uv, 工作目录 `c:\football\scoutlab`
- **真实输入**：本地 `data/gold/feature_store/team_match.parquet`，磁盘版本仍为 137906 行（含 2 行 NaN goals_for + 2 行 NaN goals_against，对应 fd-match-64766 Bastia vs Red Star 2025-12-05 占位行）
- **根因**：参考工作流 3-4 修复了 `_build_team_match_from_football_data` 的源头过滤和 `fit_dixon_coles`/`compute_form_weights` 的模型层防御，但**没有重新运行 `build-features` 将修复持久化到磁盘产物**。team_match.parquet 磁盘版本仍是污染的 137906 行。参考工作流 4 的"下一步改进"曾判断"validate 检查是冗余的 defense in depth"，该判断是错误的。
- **修复**：
  - 新增 `validate_no_null_values(relative_path, value_columns, settings)` 函数（`src/scoutfootball/evaluation/validation.py`），与 `validate_no_null_keys` 区分语义：key 列标识行不能为空，value 列承载度量值，仅在 NaN 表示数据损坏时检查（如 goals_for/goals_against）
  - 在 `run_pre_training_validation` 中为 `team_match.parquet` 增加 `goals_for`/`goals_against` NaN 检查（第 7 项检查）
  - 在 `evaluation/__init__.py` 导出新函数
- **回归测试**（`tests/unit/test_phase10.py`）：
  1. `TestValidateNoNullValues.test_missing_file` — 文件不存在时返回 fail
  2. `TestValidateNoNullValues.test_with_null_values` — 含 NaN 值时返回 fail，消息包含各列 null 计数
  3. `TestValidateNoNullValues.test_without_null_values` — 无 NaN 时返回 pass
  4. `TestValidateNoNullValues.test_missing_columns` — 列不存在时返回 fail
  5. `TestRunPreTrainingValidation.test_includes_team_match_goals_completeness_check` — 验证 `run_pre_training_validation` 包含 goals 检查
  6. `TestRunPreTrainingValidation.test_fails_when_team_match_has_nan_goals` — 验证 NaN goals 触发 fail（gate 训练）
- **执行步骤与命令**：
  ```bash
  # 1. lint
  uv run ruff check src/scoutfootball/evaluation/validation.py src/scoutfootball/evaluation/__init__.py tests/unit/test_phase10.py

  # 2. 单元测试（TestValidateNoNullValues 4/4 + TestRunPreTrainingValidation 2/2 + 原有 9/9 = 15/15）
  uv run pytest tests/unit/test_phase10.py::TestValidateNoNullValues tests/unit/test_phase10.py::TestRunPreTrainingValidation tests/unit/test_phase10.py::TestValidateNoNullKeys tests/unit/test_phase10.py::TestValidateParquetExists tests/unit/test_phase10.py::TestValidateRowCount tests/unit/test_phase10.py::TestValidationReport -v

  # 3. 全量 unit 回归
  uv run pytest tests/unit/ -q

  # 4. 真实数据烟雾测试（关键步骤：在当前磁盘产物上运行 validation）
  uv run python -c "from scoutfootball.evaluation.validation import run_pre_training_validation; r = run_pre_training_validation(); print(r.summary())"

  # 5. 重建 team_match + team_rolling（最小重建，不动 player_match 链路）
  uv run python -c "
  from scoutfootball.config import PlatformSettings
  from scoutfootball.pipeline import _build_team_match_from_football_data
  from scoutfootball.features.team_rolling import build_team_rolling_features
  settings = PlatformSettings.from_root()
  tm = _build_team_match_from_football_data(settings)
  tm.to_parquet(settings.gold_root / 'feature_store' / 'team_match.parquet', index=False)
  tr = build_team_rolling_features(tm, windows=(3, 5))
  tr.to_parquet(settings.gold_root / 'feature_store' / 'team_rolling.parquet', index=False)
  print(f'team_match: {len(tm)} rows, NaN goals_for: {tm[\"goals_for\"].isna().sum()}, NaN goals_against: {tm[\"goals_against\"].isna().sum()}')
  print(f'team_rolling: {len(tr)} rows')
  "

  # 6. 重建后重新运行 validation 确认通过
  uv run python -c "from scoutfootball.evaluation.validation import run_pre_training_validation; r = run_pre_training_validation(); print(r.summary())"
  ```
- **执行结果**：
  - ruff check 通过
  - 单元测试：15/15 通过
  - 全量 unit：通过（无 failures）
  - **真实数据烟雾测试（步骤 4，重建前）**：
    ```
    Validation: FAIL (6/7 checks passed)
      FAIL [no_null_values:gold/feature_store/team_match.parquet]: Null values: {'goals_for': 2, 'goals_against': 2}
    ```
    validation **成功捕获** team_match.parquet 磁盘版本仍含 NaN goals（fd-match-64766 Bastia vs Red Star 2025-12-05）。这正是 Layer 0 validation 的价值：在训练前就发现 Layer 1 源头过滤修复未持久化到磁盘产物。
  - **重建（步骤 5）**：
    ```
    team_match: 137904 rows, NaN goals_for: 0, NaN goals_against: 0
    team_rolling: 137904 rows
    ```
  - **重建后 validation（步骤 6）**：
    ```
    Validation: PASS (7/7 checks passed)
    ```
- **人工复盘**：
  - **是否达到预期**：是，且超出预期。原本只是增加 defense-in-depth 检查，实际捕获了真实的 Layer 1 失效——上一轮修复了源头过滤代码但没有重建磁盘产物。这验证了"validation 不是冗余的 defense in depth，而是必要的 Layer 0 早期预警"。
  - **有什么问题**：无。重建只影响 team_match 和 team_rolling（直接依赖源头过滤的产物），未动 player_match/player_rolling/rating_feature_matrix（与 football_data 无依赖关系）。
  - **数据治理启示**：代码修复 ≠ 磁盘产物修复。修复 raw → gold 转换逻辑后，必须重新运行 `build-features` 将修复持久化到磁盘产物。validation 检查是捕获这种"代码-产物不一致"的关键机制。参考工作流 4 的"冗余 defense in depth"判断是错误的——任何"defense in depth"都可能在某个时刻成为唯一防线。
  - **下一步改进**：可考虑在 `scoutfootball validate` CLI 输出中显式提示"若 no_null_values 失败，请运行 build-features 重建产物"。但当前 fail 消息已包含 null 计数，维护者可自行判断。
- **是否可重复使用**：是。`validate_no_null_values` 是通用值列完整性检查，未来可扩展到其他数据契约（如 player_match 的 minutes_played、rating_feature_matrix 的 rating 等值列）。`run_pre_training_validation` 的第 7 项检查对 `run_weekly_train` 透明生效：若 goals 含 NaN，`skip_if_validation_fails=True` 会跳过训练并返回 fail 原因。

### 参考工作流 6：Understat 转会球员 team_title 逗号分隔修复（3.1 数据导入子流程）

- **是否在用**：是（数据治理巡检中发现）
- **输入**：`data/raw/understat/players_10seasons.parquet`（31902 行），Understat 公开数据快照
- **步骤**：
  1. 巡检队名匹配率时发现 `rating_feature_matrix.parquet` 的 `team_name` 列包含 "Monaco,Nice" 等逗号连接的双队名
  2. 溯源到 `player_match.parquet` 的 understat season_proxy 行（485 行）
  3. 溯源到 `build_understat_season_proxy` 直接使用 `team_title` 字段，未处理逗号分隔的多队名
  4. 确认原始数据：`players_10seasons.parquet` 中 980/31902 行的 `team_title` 含逗号，979 行是 2 队，1 行是 3 队
  5. 修复：取第一个队名作为主归属，增加 `multi_team_season` 布尔标志
  6. 重建：`run_build_features()` 全量重建 player_match / player_rolling / rating_feature_matrix
  7. 验证：player_match 和 rating_matrix 的逗号 team_name 从 485 行降到 0；队名匹配率 96.3%（球队级别）/ 97.4%（队-赛季级别）
- **输出**：
  - 修复 `src/scoutfootball/features/understat_history.py`：`build_understat_season_proxy` 增加逗号 team_title 处理
  - 新增 `multi_team_season` 列标记转会球员
  - 3 个回归测试（双队、三队、无逗号）
  - 重建后磁盘产物：player_match 27598 行（0 逗号）、rating_matrix 26678 行（0 逗号）
- **现有替代工具**：无——之前未意识到 Understat 用逗号连接转会球员的多队名
- **错误和阻断**：
  - **BUG-006：Understat 转会球员 team_name 被逗号污染**：Understat 的赛季汇总数据中，赛季中转会的球员 `team_title` 是 "TeamA,TeamB" 格式（用逗号连接所有效力过的球队）。`build_understat_season_proxy` 直接使用该字段，导致 485 行 player_match 和 rating_matrix 的 `team_name` 是双队名字符串，破坏了所有基于 team_name 的聚合、匹配和评分。
- **人工复盘**：
  - **是否达到预期**：是。逗号污染完全消除，队名匹配率从无法评估提升到 96%+。
  - **有什么问题**：Understat 没有按队分解的 stats，只能取第一队作为主归属。转会球员的 stats 全部归于第一队，这是一种近似，不精确但远好于逗号污染。`multi_team_season` 标志保留了追溯能力。
  - **数据治理启示**：raw 数据字段的格式假设需要验证。Understat 的 `team_title` 看似单队名，实际在转会球员上是多队名逗号连接。这类"看似正常但边缘情况异常"的字段是数据污染的常见来源，需要在 raw → gold 转换时增加格式校验（如 team_name 不应包含逗号）。
  - **下一步改进**：可考虑在 `run_pre_training_validation` 中增加 team_name 格式检查（不含逗号、不为空），作为数据完整性门禁。也可考虑对转会球员做更精细的处理（如按出场数比例分配到各队），但需要 Understat 按队分解的数据或额外数据源交叉验证。
- **是否可重复使用**：是。`multi_team_season` 标志可用于下游过滤（如评分优化器排除转会球员），也可作为数据质量审计的依据。修复模式（检测异常格式 + 保守降级 + 保留标志）适用于其他 raw 字段的边缘情况处理。

---

### 参考工作流 7：pre-training validation 第二轮扩展（3.1 数据导入 + 发布门禁子流程）

- **是否在用**：是（发布门禁 defense-in-depth 补强）
- **输入**：现有 `run_pre_training_validation`（7 项检查），真实数据 gold/feature_store 产物
- **步骤**：
  1. 完成 DC NaN 防御、team_name 逗号污染等数据真实性修复后，评估 pre-training validation 的覆盖缺口
  2. 发现当前 validation 只检查 team_match 的 goals 非空，player_match 的核心指标（goals/assists/minutes）没有非空、非负检查
  3. 发现 rating_feature_matrix 没有主键唯一性检查，重复行会导致训练样本重复计数
  4. 新增 `validate_no_negative_values` 函数：检查核心计数指标不能为负，负值意味符号翻转或导入损坏
  5. 新增 `validate_unique_keys` 函数：检查聚合表主键唯一性
  6. 在 `run_pre_training_validation` 中新增 4 项检查：
     - player_match: goals/assists/minutes_played 非空
     - player_match: goals/assists/minutes_played 非负
     - team_match: goals_for/goals_against 非负
     - rating_feature_matrix: player_id+season_id 唯一
  7. 新增 14 个回归测试（两个新函数各 5 个场景 + run_pre_training_validation 4 个集成场景）
  8. 真实数据烟雾测试：validation 从 7/7 PASS 扩展到 11/11 PASS
- **输出**：
  - 新增 `validate_no_negative_values` 和 `validate_unique_keys` 两个基础检查函数
  - `run_pre_training_validation` 从 7 项扩展到 11 项
  - 14 个回归测试
  - 真实数据 11/11 PASS
- **现有替代工具**：无——之前只有 goals 非空检查，没有非负和唯一性检查
- **错误和阻断**：
  - **BUG-007（潜在）：player_match 核心指标可能含负值或重复行**：尚未在真实数据中发现，但 pipeline 中存在多处算术操作（如 diff、rolling），符号翻转或重复聚合可能引入负值或重复行。当前没有检查机制，问题会静默传播到评分训练。
- **人工复盘**：
  - **是否达到预期**：是。pre-training validation 从 7 项增加到 11 项，覆盖了非空、非负、唯一性三个维度的核心数据质量检查。
  - **有什么问题**：检查范围仍然有限——只检查了最核心的 3-4 个指标，更多衍生指标（如 per-90、composite scores）没有检查。这些衍生指标由核心指标计算而来，如果核心指标没问题，衍生指标通常也没问题。
  - **数据治理启示**：defense-in-depth 不是越多越好。每增加一项检查都有维护成本，且可能误报（比如某些列的 null 是合法的）。检查应该聚焦于"如果出错会导致不可恢复损坏"的核心指标。goals/assists/minutes 是所有评分和预测的基础，它们的非空、非负、唯一性是最低保障。
  - **下一步改进**：可考虑增加 date_range 检查（比赛日期是否在合理范围内）、row_count 合理性检查（行数不应异常下降），但这些需要更复杂的基线设置，优先级较低。
- **是否可重复使用**：是。两个新函数是通用的，可用于任何 parquet 文件的数据质量检查。检查模式（存在性 → 行数 → 键非空 → 值非空 → 值非负 → 键唯一）是一个渐进式的数据质量验证框架，可扩展到其他数据管道。

---

## 更新规则

- 维护者填写真实任务后，将对应"待填写"替换为真实内容。
- 真实端到端运行证据需保存截图、日志或输出文件，并在本文记录路径。
- 工作流变更（新增、废弃、步骤变化）时同步更新本文。
- 本文是 G0-A 子任务 2-3 的退出证据；未填写前 G0-A 不可验证。
