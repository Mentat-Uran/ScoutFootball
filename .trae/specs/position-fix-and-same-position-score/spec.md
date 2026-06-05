# 位置识别修复与同位置评分 Spec

## Why

当前评分产物 Top 20 里 CB 占 15 个、Top 100 里 CB 占 61 个，大量高分"CB"实为边后卫/翼卫（Cancelo、Trent、Hakimi、Theo、David Raum）。根本原因：1) `map_position()` 把所有 `DF` 默认映射为 `CB`，Understat 的 `D S`/`D M S`/`F M S` 等多位置字符串无法正确解析；2) 最终 `optimized_score` 是全局绝对分，没有同位置百分位，导致后卫池与前锋池直接竞争总榜。需要修位置映射、增加同位置评分、加位置分布回归测试，再重跑 GPU optimizer。

## What Changes

- 重写 `map_position()` 支持 Understat 多位置字符串（`D S`→CB/ST 双标记、`D M S`→FB/DM 等），输出 `sub_position` + `position_source` + `position_confidence`
- `refine_role_positions()` 增强：利用 `position_source`/`position_confidence` 做更精细的 CB/FB/W/AM 重判
- 主输出增加 `same_position_score`：按 `season + sub_position` 计算最终分的同位置百分位，样本不足时退回 `sub_position` 全局百分位
- 保留 `optimized_score`（绝对代理分）和 `same_position_score`（同位置水平），不合并为单一分数
- 球队聚合增加位置槽位上限：GK/CB/FB/中场/前场各有贡献上限，避免单位置堆人主导球队评分
- 增加 Top 100 位置分布回归测试和位置误判诊断输出
- 不使用 Top N 配额硬压后卫数量

## Impact

- Affected specs: P0 评分系统真实影响力校准
- Affected code:
  - `scripts/optimize_ratings_gpu.py` — map_position 重写、refine_role_positions 增强、same_position_score 计算、球队聚合位置槽位、诊断输出
  - `src/scoutlab/entities/normalize.py` — POSITION_ALIASES 扩展
- Affected docs: MODEL_CARD.md（位置识别方法说明）、AGENTS.md（产物字段更新）

## ADDED Requirements

### Requirement: 多位置字符串解析

系统 SHALL 将 `map_position()` 从简单字符串匹配改为支持多位置字符串解析：

1. Understat 位置字符串格式：`D`、`M`、`F`、`S`、`D S`、`D M`、`D M S`、`F M`、`F M S`、`GK`
2. 解析规则：
   - `GK` → GK
   - `D` → CB（无其他线索时默认 CB）
   - `D M` 或 `M D` → FB（有防守+中场线索优先判为翼卫/边后卫）
   - `D S` → CB（防守+射门线索，默认 CB 但标记低置信度）
   - `D M S` → FB（三位置线索，翼卫/边后卫）
   - `F M` 或 `M F` → AM（前场+中场线索）
   - `F M S` → W（三位置线索，边锋）
   - `F` 或 `S` → ST
   - `M` → CM
3. 输出三个字段：
   - `sub_position`：最终位置（与现有 POSITIONS 列表一致）
   - `position_source`：原始位置字符串
   - `position_confidence`：`high`/`medium`/`low`，多位置字符串为 `medium`，单字母为 `low`，FBref 多位置组合为 `high`

#### Scenario: Understat D M S 解析

- **WHEN** Understat 球员位置为 `D M S`
- **THEN** `sub_position` = `FB`，`position_confidence` = `medium`

#### Scenario: FBref DF,MF 解析

- **WHEN** FBref 球员位置为 `DF,MF`
- **THEN** `sub_position` = `FB`，`position_confidence` = `high`

#### Scenario: 单字母 D 解析

- **WHEN** Understat 球员位置为 `D`
- **THEN** `sub_position` = `CB`，`position_confidence` = `low`

### Requirement: 同位置评分输出

系统 SHALL 在评分产物中增加 `same_position_score` 字段：

1. 计算方式：按 `season + sub_position` 分组，对 `optimized_score` 计算百分位排名
2. 样本不足退回：当某 `season + sub_position` 组合少于 5 人时，退回 `sub_position` 全局百分位
3. 全局退回：当 `sub_position` 全局也少于 5 人时，`same_position_score` = NaN 并标记低置信度
4. 两个分数并存：`optimized_score` 保留为绝对代理分，`same_position_score` 为同位置百分位（0-100）
5. 榜单展示优先使用 `same_position_score`

#### Scenario: 正常赛季位置组

- **WHEN** 某赛季 CB 组有 30 人
- **THEN** 该组内 `same_position_score` 为该球员在 30 人中的百分位排名

#### Scenario: 小样本退回

- **WHEN** 某赛季 GK 组只有 2 人
- **THEN** 退回 GK 全局百分位

### Requirement: 球队聚合位置槽位上限

系统 SHALL 在球队赛季聚合中增加位置槽位贡献上限：

1. 位置分组：GK、CB、FB、MF（CM+DM）、ATT（AM+W+ST）
2. 每组贡献上限：GK=1.0, CB=2.5, FB=1.5, MF=2.5, ATT=2.5（总计≈10，约一个首发阵容）
3. 组内权重分配：组内仍用 capped minutes + core rotation 权重
4. 超出上限的球员权重按比例缩减

#### Scenario: 后卫堆人被限制

- **WHEN** 某球队赛季有 6 个 CB 且出场时间都较高
- **THEN** CB 组总贡献不超过 2.5，超出部分按比例缩减

### Requirement: 位置分布回归测试

系统 SHALL 增加 Top N 位置分布回归测试：

1. 测试内容：Top 20/50/100 的位置分布统计
2. 报警阈值：Top 100 中任意单位置占比超过 40% 时报警
3. 位置误判诊断：输出 `position_confidence=low` 且评分 Top 100 的球员名单
4. 不使用硬性配额约束（如"后卫最多 N 个"），仅做诊断和报警

#### Scenario: 位置分布异常报警

- **WHEN** Top 100 中 CB 占比超过 40%
- **THEN** 输出报警信息，但不阻止优化流程

### Requirement: 诊断输出增强

系统 SHALL 在优化完成后输出以下诊断：

1. Top 20/50/100 位置分布表
2. `position_confidence=low` 球员在 Top 100 中的名单
3. 同位置评分 Top 5（按 `sub_position` 分组，按 `same_position_score` 排序）
4. 位置映射统计：各 `position_source` → `sub_position` 的映射计数

## MODIFIED Requirements

### Requirement: map_position

`map_position()` 从简单字符串匹配改为多位置字符串解析，输出 `sub_position` + `position_source` + `position_confidence`。FBref 和 Understat 的位置字符串分别处理。

### Requirement: refine_role_positions

`refine_role_positions()` 增加 `position_confidence` 利用：对 `position_confidence=low` 的球员放宽重判阈值，对 `position_confidence=high` 的球员保守重判。

### Requirement: 评分产物 schema

`player_ratings_optimized.parquet` 新增列：`same_position_score`（float）、`position_source`（str）、`position_confidence`（str）。

## REMOVED Requirements

无。
