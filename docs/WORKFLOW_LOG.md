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
  - **下一步改进**：可考虑在 `validate` 命令中增加"team_match NaN 进球比例"检查作为发布门禁；但当前源头过滤已经消除了这个问题，validate 检查是冗余的 defense in depth
- **是否可重复使用**：是。修复是 `_build_team_match_from_football_data` 的内部防御性逻辑，对 `run_build_features` 调用方透明生效。维护者每次 build-features 后若 raw 数据新增未来比赛占位行，会看到 INFO 日志知道过滤了多少行。

---

## 更新规则

- 维护者填写真实任务后，将对应"待填写"替换为真实内容。
- 真实端到端运行证据需保存截图、日志或输出文件，并在本文记录路径。
- 工作流变更（新增、废弃、步骤变化）时同步更新本文。
- 本文是 G0-A 子任务 2-3 的退出证据；未填写前 G0-A 不可验证。
