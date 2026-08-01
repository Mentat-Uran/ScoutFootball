# v1.0 Phase 1: 数据层补全 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补全所有数据源，评分矩阵特征无 fallback 缺口，球员真实标签填充，世界杯真实数据替换 demo。

**Architecture:** 在现有 pipeline 和 adapter 框架上扩展，不改变核心架构。每个数据源通过 adapter 接入 pipeline，评分矩阵通过 `rating_matrix.py` 扩展字段，真实标签通过 `fill_truth_labels.py` 填充。

**Tech Stack:** Python, pandas, DuckDB, soccerdata (FBref), selenium (FBref), numpy, pathlib

---

## File Structure

| 文件 | 职责 | 操作 |
|---|---|---|
| `src/scoutfootball/adapters/football_data.py` | Football-Data CSV 下载和合并 | 修改 |
| `src/scoutfootball/adapters/transfermarkt_manual.py` | Transfermarkt CSV 导入 | 修改 |
| `src/scoutfootball/adapters/fbref_soccerdata.py` | FBref 扩展表采集 | 修改 |
| `src/scoutfootball/adapters/statsbomb_open.py` | StatsBomb 事件加载 | 修改 |
| `src/scoutfootball/action_value/spadl_adapter.py` | StatsBomb events → SPADL 转换 | 修改 |
| `src/scoutfootball/action_value/xt.py` | xT 全量计算 | 修改 |
| `src/scoutfootball/features/rating_matrix.py` | 评分特征矩阵扩展 | 修改 |
| `src/scoutfootball/evaluation/truth_labels.py` | 真实标签契约 | 修改 |
| `src/scoutfootball/worldcup/data.py` | 世界杯真实数据 | 修改 |
| `src/scoutfootball/pipeline.py` | Pipeline 入口 | 修改 |
| `scripts/fill_truth_labels.py` | 真实标签填充 | 修改 |
| `scripts/consolidate_events.py` | 事件合并 | 修改 |
| `data/raw/football_data/combined_results.parquet` | 10 赛季合并产物 | 重建 |
| `data/gold/feature_store/player_truth_labels.parquet` | 真实标签产物 | 重建 |
| `data/gold/feature_store/rating_feature_matrix.parquet` | 扩展特征矩阵 | 重建 |
| `data/gold/feature_store/player_action_value.parquet` | 全量 xT 产物 | 重建 |

---

### Task 1: Football-Data 10 赛季合并

**Files:**
- Modify: `src/scoutfootball/adapters/football_data.py`
- Test: `tests/unit/test_football_data_rebuild.py`

**现状**：`combined_results.parquet` 仅 4 赛季（2223-2526），但 `data/raw/football_data/` 下已有 1617-2526 共 10 赛季 CSV。`rebuild_combined_results()` 已支持扫描所有子目录。

- [ ] **Step 1: 验证现有 CSV 覆盖**

Run: `ls data/raw/football_data/` 确认 1617-2526 共 10 个赛季目录存在，每个目录有 E0.csv, D1.csv, SP1.csv, I1.csv, F1.csv。

- [ ] **Step 2: 运行 rebuild 扩展到 10 赛季**

Run: `PYTHONPATH=src .venv\Scripts\python.exe -c "from scoutfootball.adapters.football_data import rebuild_combined_results; print(rebuild_combined_results('data/raw/football_data', 'data/raw/football_data/combined_results.parquet'))"`

Expected: total_rows ~17,000+, 10 赛季 5 大联赛

- [ ] **Step 3: 验证行数**

Run: `.venv\Scripts\python.exe -c "import pandas as pd; df = pd.read_parquet('data/raw/football_data/combined_results.parquet'); print(f'rows={len(df)}, seasons={sorted(df[\"season\"].unique())}')"` 

Expected: rows ~17,000+, seasons 包含 1617-2526

- [ ] **Step 4: 运行现有测试确认无回归**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_football_data_rebuild.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add data/raw/football_data/combined_results.parquet
git commit -m "data: expand Football-Data to 10 seasons (1617-2526)"
```

---

### Task 2: Transfermarkt 身价导入接入 Pipeline

**Files:**
- Modify: `src/scoutfootball/pipeline.py`
- Modify: `src/scoutfootball/adapters/transfermarkt_manual.py`
- Test: `tests/unit/test_adapters_phase3.py`

**现状**：`data/raw/transfermarkt/player_market_value.csv` 和 `player_profiles.csv` 已存在，`transfermarkt_manual.py` 有 `load_snapshot()` 函数，但 pipeline 未自动调用。pipeline 中 `_build_market_enriched_features` 先尝试 Transfermarkt CSV，失败则生成合成身价。

- [ ] **Step 1: 验证 Transfermarkt CSV 数据**

Run: `.venv\Scripts\python.exe -c "import pandas as pd; df = pd.read_csv('data/raw/transfermarkt/player_market_value.csv', nrows=5); print(df.columns.tolist()); print(len(pd.read_csv('data/raw/transfermarkt/player_market_value.csv')))"`

Expected: 列包含 player_name/team_name/market_value 等，行数 ≥30,000

- [ ] **Step 2: 测试 load_snapshot 能否读取**

Run: `.venv\Scripts\python.exe -c "from scoutfootball.adapters.transfermarkt_manual import load_snapshot; r = load_snapshot('data/raw/transfermarkt/player_market_value.csv'); print(f'rows={len(r.dataframe)}, cols={r.dataframe.columns.tolist()}')"`

Expected: 成功加载，行数 ≥30,000

- [ ] **Step 3: 确认 pipeline 中 Transfermarkt 路径已正确配置**

读取 `pipeline.py` 中 `_build_market_enriched_features` 函数，确认 Transfermarkt CSV 路径指向 `data/raw/transfermarkt/`。如果路径不正确，修改为正确路径。

- [ ] **Step 4: 运行 pipeline build-features 验证身价数据**

Run: `PYTHONPATH=src .venv\Scripts\python.exe -m scoutfootball build-features`

Expected: 无报错，`player_match.parquet` 包含 market_value 列且非全 NaN

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: integrate Transfermarkt market values into pipeline"
```

---

### Task 3: FBref 扩展表采集

**Files:**
- Modify: `src/scoutfootball/adapters/fbref_soccerdata.py`
- Modify: `src/scoutfootball/pipeline.py`

**现状**：`fbref_soccerdata.py` 已有 `read_player_season_stats_with_bundesliga_fallback()` 和 `read_player_season_stats_extended()`，支持 7 种 stat_type（standard, shooting, passing, possession, misc, keeper, keeper_adv）。但从未实际运行，且 pipeline 中 FBref 只用了 `player_standard_5seasons.parquet`。

- [ ] **Step 1: 安装 soccerdata 依赖**

Run: `uv add soccerdata`

Expected: 安装成功

- [ ] **Step 2: 测试单个 stat_type 采集**

Run: `.venv\Scripts\python.exe -c "from scoutfootball.adapters.fbref_soccerdata import read_player_season_stats_with_bundesliga_fallback; df = read_player_season_stats_with_bundesliga_fallback(2025, stat_type='misc'); print(f'rows={len(df)}, cols={df.columns.tolist()[:10]}')"`

Expected: rows ≥2,000, 包含 tackles, interceptions, fouls 等字段

- [ ] **Step 3: 批量采集 5 赛季 7 种 stat_type**

编写脚本遍历 5 赛季（2122-2526）× 7 种 stat_type，保存到 `data/raw/fbref/` 下对应 parquet 文件。每个文件命名如 `player_misc_5seasons.parquet`。

- [ ] **Step 4: 验证采集结果**

检查每种 stat_type 的 parquet 文件行数，确保 ≥10,000。

- [ ] **Step 5: Commit**

```bash
git add data/raw/fbref/ src/scoutfootball/adapters/fbref_soccerdata.py
git commit -m "data: collect FBref extended stats (7 types, 5 seasons)"
```

---

### Task 4: 防守/控球特征入评分矩阵

**Files:**
- Modify: `src/scoutfootball/features/rating_matrix.py`
- Modify: `src/scoutfootball/pipeline.py`
- Test: `tests/unit/test_rating_feature_matrix.py`

**现状**：`rating_matrix.py` 的 `FIELD_GROUPS` 定义了 defense/possession/xT_VAEP/goalkeeper 四组字段，但实际数据全部为 NaN，被 `mark_missing_fields()` 标记为 missing，然后 `fill_missing_with_position_median()` 用位置中位数填充。

- [ ] **Step 1: 在 rating_matrix.py 中新增 FBref 扩展特征字段**

在 `FIELD_GROUPS` 的 defense 组添加：tackles, tackles_won, interceptions, blocks, clearances, fouls_committed, fouls_drawn, aerials_won, aerials_lost, own_goals。在 possession 组添加：touches, passes_completed, passes_attempted, pass_pct, progressive_passes, progressive_carries, successful_dribbles, attempted_dribbles, dribble_pct。

- [ ] **Step 2: 在 build_rating_feature_matrix 中合并 FBref 扩展数据**

在 `build_rating_feature_matrix()` 中，读取 FBref 扩展 parquet 文件（misc, passing, possession），按 player_name + season 合并到主矩阵。

- [ ] **Step 3: 更新 missing flag 逻辑**

确保 `mark_missing_fields()` 对新字段的缺失标记正确：有数据时 missing=False，无数据时 missing=True。

- [ ] **Step 4: 运行测试**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_rating_feature_matrix.py -v`

Expected: PASS

- [ ] **Step 5: 重建评分矩阵**

Run: `PYTHONPATH=src .venv\Scripts\python.exe -m scoutfootball build-features`

Expected: `rating_feature_matrix.parquet` 新增 15+ 字段，5 大联赛主力球员 missing rate < 0.30

- [ ] **Step 6: Commit**

```bash
git add src/scoutfootball/features/rating_matrix.py src/scoutfootball/pipeline.py tests/unit/test_rating_feature_matrix.py data/gold/feature_store/rating_feature_matrix.parquet data/gold/feature_store/rating_feature_matrix_manifest.json
git commit -m "feat: add FBref defensive/possession features to rating matrix"
```

---

### Task 5: StatsBomb events → SPADL 转换

**Files:**
- Modify: `src/scoutfootball/action_value/spadl_adapter.py`
- Modify: `src/scoutfootball/action_value/schema.py`
- Test: `tests/unit/test_action_value_schema.py`

**现状**：`spadl_adapter.py` 有 `convert_all_events()` 函数，但使用 iterrows 逐行转换，性能差。`schema.py` 和 `spadl_adapter.py` 的 `STATSBOMB_ACTION_MAP` 不一致。carry 事件 end_location 缺失。

- [ ] **Step 1: 统一 STATSBOMB_ACTION_MAP**

将 `schema.py` 和 `spadl_adapter.py` 的 `STATSBOMB_ACTION_MAP` 合并为一个权威定义（放在 `schema.py` 中，`spadl_adapter.py` 从 schema import）。确保覆盖所有 StatsBomb 事件类型：Pass, Shot, Dribble, Carry, Pressure, Duel, Foul Committed, Foul Won, Goal Keeper, Interception, Clearance, Block, Tactical Shift, Ball Recovery, Miscontrol, Shield, Half End, Half Start, Starting XI, Substitution。

- [ ] **Step 2: 优化 convert_all_events 性能**

将 iterrows 改为向量化操作：先筛选有效事件类型，再用 pd.DataFrame.apply 或列表推导批量转换。

- [ ] **Step 3: 修复 carry 事件 end_location**

carry 事件使用 `carry_end_location` 字段（在 `events_all.parquet` 中为 `carry_end_location_x/y` 列）。如果缺失，fallback 到 start_location。

- [ ] **Step 4: 运行全量转换**

Run: `PYTHONPATH=src .venv\Scripts\python.exe -c "from scoutfootball.action_value.spadl_adapter import convert_all_events; actions = convert_all_events('data/raw/statsbomb_open/events_all.parquet'); print(f'actions={len(actions)}')"`

Expected: actions 约为事件数的 60-70%（~5M）

- [ ] **Step 5: 保存 SPADL 产物**

将转换结果保存为 `data/gold/feature_store/actions_all.parquet`。

- [ ] **Step 6: 运行测试**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_action_value_schema.py -v`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/scoutfootball/action_value/spadl_adapter.py src/scoutfootball/action_value/schema.py tests/unit/test_action_value_schema.py data/gold/feature_store/actions_all.parquet
git commit -m "feat: implement StatsBomb events to SPADL conversion with vectorized performance"
```

---

### Task 6: 球员真实标签填充

**Files:**
- Modify: `scripts/fill_truth_labels.py`
- Test: `tests/unit/test_rating_optimizer_validation.py`

**现状**：`fill_truth_labels.py` 已有三种标签来源（expert_tier, award, transfermarkt），但 expert_tier 是循环标签（用模型输出百分位当真值），Transfermarkt 路径依赖手动文件。`player_truth_labels.parquet` 当前为空。

- [ ] **Step 1: 修复 Transfermarkt 标签路径**

修改 `build_transfermarkt_labels()` 中的路径，指向 `data/raw/transfermarkt/player_market_value.csv`（已存在的文件），而非 `data/raw/transfermarkt_datasets/`。

- [ ] **Step 2: 运行标签填充脚本**

Run: `PYTHONPATH=src .venv\Scripts\python.exe scripts/fill_truth_labels.py`

Expected: `player_truth_labels.parquet` 行数 ≥500

- [ ] **Step 3: 验证标签质量**

Run: `.venv\Scripts\python.exe -c "import pandas as pd; df = pd.read_parquet('data/gold/feature_store/player_truth_labels.parquet'); print(f'rows={len(df)}, sources={df[\"label_source\"].value_counts().to_dict()}, confidence={df[\"label_confidence\"].value_counts().to_dict()}')"`

Expected: 至少有 transfermarkt_value 和 award 两种来源，high+medium 置信度

- [ ] **Step 4: 运行测试确认 pipeline 不回归**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_rating_optimizer_validation.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/fill_truth_labels.py data/gold/feature_store/player_truth_labels.parquet
git commit -m "feat: populate player truth labels from Transfermarkt and awards"
```

---

### Task 7: 世界杯真实数据

**Files:**
- Modify: `src/scoutfootball/worldcup/data.py`

**现状**：`SQUADS` 为占位数据，含大量错误归属（Benzema 归入 Algeria, Messi 归入 Spain）。部分球队阵容为空。

- [ ] **Step 1: 更新 48 队阵容为真实球员**

根据 2026 世界杯各队最新公布的大名单或预期阵容，更新 `SQUADS` 字典。每队 23-26 人，包含 name/position/club/club_league 字段。

- [ ] **Step 2: 修复空阵容球队**

确保所有 48 队至少有 11 名球员（首发阵容）。

- [ ] **Step 3: 更新小组赛日期**

将占位日期替换为 FIFA 官方公布的 2026 世界杯小组赛日期。

- [ ] **Step 4: 验证 enrich_squads_with_ratings 能匹配真实球员**

Run: `PYTHONPATH=src .venv\Scripts\python.exe -c "from scoutfootball.worldcup.data import enrich_squads_with_ratings; import pandas as pd; ratings = pd.read_parquet('data/gold/feature_store/player_ratings_optimized.parquet'); result = enrich_squads_with_ratings(ratings); matched = sum(1 for squad in result.values() if any(p.get('rating') for p in squad)); print(f'matched_teams={matched}/48')"`

Expected: matched_teams ≥30

- [ ] **Step 5: Commit**

```bash
git add src/scoutfootball/worldcup/data.py
git commit -m "data: update World Cup squads with real players and fixtures"
```

---

### Task 8: 全量 xT 计算

**Files:**
- Modify: `src/scoutfootball/action_value/xt.py`
- Modify: `src/scoutfootball/action_value/aggregate.py`
- Modify: `src/scoutfootball/pipeline.py`

**现状**：`xt.py` 有完整 xT 实现，但只用 3 场样本数据计算。`aggregate.py` 有 `aggregate_player_action_values()` 函数。pipeline 中 action-value 步骤已接入但只处理样本。

- [ ] **Step 1: 基于 SPADL 产物计算全量 xT**

在 `xt.py` 中添加 `compute_xt_from_actions(actions_path, output_path)` 函数，读取 `actions_all.parquet`，计算 xT grid，然后为每个动作计算 xT 增量。

- [ ] **Step 2: 聚合到球员赛季粒度**

使用 `aggregate.py` 的 `aggregate_player_action_values()` 将动作级 xT 聚合为球员赛季级，输出 `player_action_value.parquet`。

- [ ] **Step 3: 运行全量计算**

Run: `PYTHONPATH=src .venv\Scripts\python.exe -m scoutfootball action-value`

Expected: `player_action_value.parquet` 行数 ≥30,000

- [ ] **Step 4: 验证 xT 值合理性**

Run: `.venv\Scripts\python.exe -c "import pandas as pd; df = pd.read_parquet('data/gold/feature_store/player_action_value.parquet'); print(f'rows={len(df)}, xt_mean={df[\"xt_total\"].mean():.3f}, xt_top5={df.nlargest(5, \"xt_total\")[[\"player_name\", \"xt_total\"]].to_string()}')"`

Expected: Top 5 球员符合直觉（创造性中场/边锋/前锋）

- [ ] **Step 5: Commit**

```bash
git add src/scoutfootball/action_value/xt.py src/scoutfootball/action_value/aggregate.py src/scoutfootball/pipeline.py data/gold/feature_store/player_action_value.parquet
git commit -m "feat: compute full xT action values from all StatsBomb events"
```

---

### Task 9: 文档同步

**Files:**
- Modify: `docs/DATA_STATUS_REPORT.md`
- Modify: `AGENTS.md`

**现状**：DATA_STATUS_REPORT 数据行数与实际严重不符，AGENTS.md 中 events_all.parquet 记录为 11,871 行，实际为 7,744,412 行。

- [ ] **Step 1: 更新 AGENTS.md 数据行数**

将 StatsBomb events_all.parquet 行数从 11,871 更新为实际值，更新 combined_results.parquet 行数，更新 player_truth_labels.parquet 行数。

- [ ] **Step 2: 更新 DATA_STATUS_REPORT.md**

同步所有数据文件的实际行数和覆盖状态。

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md docs/DATA_STATUS_REPORT.md
git commit -m "docs: sync data status with actual file sizes"
```

---

## Task Dependencies

```
Task 1 (Football-Data 10赛季) ──→ 无依赖
Task 2 (Transfermarkt 导入) ──→ 无依赖
Task 3 (FBref 扩展表) ──→ 无依赖
Task 4 (防守/控球特征) ──→ Task 3
Task 5 (SPADL 转换) ──→ 无依赖
Task 6 (真实标签) ──→ Task 2
Task 7 (世界杯数据) ──→ 无依赖
Task 8 (全量 xT) ──→ Task 5
Task 9 (文档同步) ──→ Task 1-8 全部完成
```

可并行组：
- **组 A**：Task 1, 2, 3, 5, 7（无依赖，可同时进行）
- **组 B**：Task 4（依赖 3）, Task 6（依赖 2）, Task 8（依赖 5）
- **组 C**：Task 9（依赖全部）
