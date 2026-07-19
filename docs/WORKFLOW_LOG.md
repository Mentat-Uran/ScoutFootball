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

- **是否在用**：待填写
- **输入**：待填写
- **步骤**：待填写（`build-features` → `train` → `train-rating-nn`）
- **输出**：待填写（模型产物、holdout 指标、特征 manifest）
- **现有替代工具**：待填写
- **错误和阻断**：待填写
- **复盘证据**：待填写

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

  # 2. 验证候选 admission 状态（7 项 evidence 检查）
  uv run python -m scoutfootball model-admission --json
  # → reviewable_run_count: 1（lineage.status=recorded、parameter_artifact、
  #   recorded_lineage、time_split、baseline_holdout、candidate_holdout、
  #   error_cases、required_inputs 全部满足）

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
  - 候选 run `20260719T142124Z-631abaea` 在 `model-admission` 中状态为 `reviewable`，7 项 evidence 检查全部通过
  - 候选 meta.json 关键字段：`lineage.status=recorded`、`lineage.feature_manifest.path=gold/feature_store/rating_feature_matrix_manifest.json`、`activation.status=rolled_back`、`activation.backup_id=20260719T142324Z-20260719T142124Z-631abaea-f1416f39`
  - 候选 metrics（test split）：baseline Spearman=0.6028 → optimized Spearman=0.6993（+0.0965）；baseline points MAE=18.22 → optimized points MAE=14.75（-3.47）
  - 候选 error_cases：over_estimated 5 队（Wolfsburg +1.4 .. Burnley +8.9）、under_estimated 5 队（Parma -35.0 .. Bologna -30.8）
  - promote 创建备份目录，含 `manifest.json` + 三个 baseline 活跃产物副本（带 sha256 校验）
  - rollback 后三个活跃产物 sha256 与 baseline 完全一致，可逆性得到端到端验证
- **人工复盘**：
  - **是否达到预期**：是。这是首次在当前 snapshot 上生成 `reviewable` 候选（此前 40 个历史 run 全部 `not_reviewable`，主因是缺 `rating_feature_matrix_manifest.json`）。promote/rollback 端到端可逆，活跃产物 sha256 在回滚后与 baseline 字节级一致。
  - **有什么问题**：无功能性阻断。运行时有一条 `FutureWarning: DataFrame concatenation with empty or all-NA entries is deprecated`（understat 拼接，data.py:439），不影响结果，未修复。
  - **reject 路径覆盖**：reject 是纯元数据操作（不删除候选目录、不变更活跃产物），由单元测试 `tests/unit/test_model_run_lifecycle.py::test_rejection_is_a_confirmed_metadata_action_that_keeps_candidate` 覆盖（验证 dry-run 保持 `not_activated`、`--confirm` 翻转为 `rejected` 且候选目录保留）。本次未重复跑 quick run 作为 reject 目标，因为该路径不涉及活跃产物可逆性这种需要端到端实测的场景。
  - **下一步改进**：C1 退出门槛第 3 条已端到端验证。剩余 C1 退出门槛包括补齐 6 个来源的 `snapshot_date`、建立身份/来源审计样本、处置 `data/raw/transfermarkt/` 遗留未登记目录。
- **是否可重复使用**：是。维护者每次模型迭代后可重复执行 `optimize_ratings_gpu.py → model-admission → promote-model-run` 流程；如需还原，使用 `rollback-model-run <backup_id>`。候选 meta.json 完整记录了 lineage、metrics、error_cases、args，可在同一 snapshot 上复算。

---

## 更新规则

- 维护者填写真实任务后，将对应"待填写"替换为真实内容。
- 真实端到端运行证据需保存截图、日志或输出文件，并在本文记录路径。
- 工作流变更（新增、废弃、步骤变化）时同步更新本文。
- 本文是 G0-A 子任务 2-3 的退出证据；未填写前 G0-A 不可验证。
