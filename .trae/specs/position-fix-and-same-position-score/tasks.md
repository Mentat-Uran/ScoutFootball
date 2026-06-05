# Tasks

- [ ] Task 1: 重写 map_position() 支持多位置字符串解析
  - [ ] 1.1: 实现新的 `map_position_detailed(pos_str)` 函数，返回 `(sub_position, position_source, position_confidence)` 三元组
  - [ ] 1.2: 支持 Understat 位置字符串：`D`/`M`/`F`/`S`/`D S`/`D M`/`D M S`/`F M`/`F M S`/`GK`
  - [ ] 1.3: 支持 FBref 位置字符串：`DF`/`MF`/`FW`/`DF,MF`/`MF,FW`/`FW,MF`/`GK` 等
  - [ ] 1.4: 在 FBref 数据加载处替换 `map_position` 为 `map_position_detailed`
  - [ ] 1.5: 在 Understat 数据加载处替换 `map_position` 为 `map_position_detailed`
  - [ ] 1.6: 确保 `position_source` 和 `position_confidence` 列写入 DataFrame

- [ ] Task 2: 增强 refine_role_positions() 利用 position_confidence
  - [ ] 2.1: 对 `position_confidence=low` 的球员放宽重判阈值（更容易被特征重判）
  - [ ] 2.2: 对 `position_confidence=high` 的球员保守重判（需要更强的特征证据）
  - [ ] 2.3: 重判后更新 `position_confidence`（从 low 变为 medium 或保持不变）

- [ ] Task 3: 实现 same_position_score 计算
  - [ ] 3.1: 在评分输出阶段，按 `season + sub_position` 分组计算 `optimized_score` 百分位
  - [ ] 3.2: 样本不足（<5人）时退回 `sub_position` 全局百分位
  - [ ] 3.3: 全局也不足时设为 NaN
  - [ ] 3.4: 将 `same_position_score` 写入 `player_ratings_optimized.parquet`

- [ ] Task 4: 实现球队聚合位置槽位上限
  - [ ] 4.1: 定义位置分组：GK/CB/FB/MF(CM+DM)/ATT(AM+W+ST)
  - [ ] 4.2: 定义各组贡献上限：GK=1.0, CB=2.5, FB=1.5, MF=2.5, ATT=2.5
  - [ ] 4.3: 修改 `_build_team_aggregation_weights()` 实现位置槽位上限
  - [ ] 4.4: 组内仍用 capped minutes + core rotation 权重

- [ ] Task 5: 增加诊断输出
  - [ ] 5.1: Top 20/50/100 位置分布表
  - [ ] 5.2: `position_confidence=low` 球员在 Top 100 中的名单
  - [ ] 5.3: 同位置评分 Top 5（按 sub_position 分组）
  - [ ] 5.4: 位置映射统计：各 position_source → sub_position 映射计数

- [ ] Task 6: 增加 Top N 位置分布回归测试
  - [ ] 6.1: 测试 Top 20/50/100 位置分布
  - [ ] 6.2: 任意单位置占比超过 40% 时报警（不阻止优化）
  - [ ] 6.3: 验证 same_position_score 计算正确性

- [ ] Task 7: 同步 normalize.py 的 POSITION_ALIASES
  - [ ] 7.1: 扩展 POSITION_ALIASES 支持 Understat 位置字符串映射
  - [ ] 7.2: 确保 normalize_position_group 与 map_position_detailed 一致

# Task Dependencies

- [Task 2] depends on [Task 1]（refine_role_positions 需要 position_confidence 字段）
- [Task 3] depends on [Task 1]（same_position_score 需要 sub_position 正确）
- [Task 4] depends on [Task 1]（位置槽位需要正确的 sub_position）
- [Task 5] depends on [Task 3]（诊断输出需要 same_position_score）
- [Task 6] depends on [Task 3, Task 5]（回归测试需要新产物）
- [Task 7] 可与 Task 1 并行
