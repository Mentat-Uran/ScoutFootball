# Tasks

- [x] Task 1: 重建 Football-Data 10 赛季合并 Parquet
  - [x] 1.1 新增 `scripts/rebuild_football_data.py`，扫描 `data/raw/football_data/` 下所有赛季目录，读取全部 CSV，合并为统一 DataFrame
  - [x] 1.2 处理 20 个 league/division 代码（E0/E1/SP1/SP2/D1/D2/I1/I2/F1/F2/N1/B1/P1/T1/SC0/SC1/SC2/SC3/B1/G1/等），确保所有 CSV 均被读取
  - [x] 1.3 保留 2526 alias patch 逻辑，重建后五大联赛 holdout coverage 仍为 1.00
  - [x] 1.4 输出重建元数据：raw CSV 总行数、active Parquet 行数、league-season 覆盖列表、输入文件 hash、重建时间
  - [x] 1.5 将合并逻辑封装为 `src/scoutlab/adapters/football_data.py` 中的 `rebuild_combined_results()` 函数，供 pipeline 调用
  - [x] 1.6 编写单元测试验证合并产物行数、league-season 覆盖和 alias patch

- [x] Task 2: 补全 2526 评估覆盖
  - [x] 2.1 在评估函数中增加积分 N/A 球队过滤逻辑
  - [x] 2.2 在 team coverage 报告中标注剔除的球队数量和原因
  - [x] 2.3 编写单元测试验证 N/A 球队被正确剔除

- [x] Task 3: 真实标签数据契约
  - [x] 3.1 新增 `src/scoutlab/evaluation/truth_labels.py`，定义 `player_truth_labels` 的 schema（player_id, season, label_source, label_confidence, label_value, as_of_date, position_scope, manual_review_flag）
  - [x] 3.2 定义 `label_source` 枚举：transfermarkt_value、award、expert_tier、manual_calibration
  - [x] 3.3 定义 `label_confidence` 枚举：high、medium、low
  - [x] 3.4 实现 `validate_truth_labels()` 校验函数：schema 一致性、枚举值、无重复 player_id+season+label_source
  - [x] 3.5 实现 `create_empty_truth_labels()` 函数，生成空表模板
  - [x] 3.6 在 `pipeline.py` 的 `run_build_features` 中集成空表模板输出
  - [x] 3.7 编写单元测试验证 schema 定义、枚举值、校验逻辑和空表生成

- [x] Task 4: 评分模型卡 MODEL_CARD.md
  - [x] 4.1 编写 `MODEL_CARD.md`，包含：数据源、标签定义、适用边界、已知偏差、不可用场景、低置信度球员处理规则、特征维度说明、训练/评估切分方式
  - [x] 4.2 在 AGENTS.md 中添加 MODEL_CARD.md 作为算法解释参考文档之一

- [x] Task 5: 更新 README.md、TASKS.md、AGENTS.md
  - [x] 5.1 更新 README.md：本地数据概览中 Football-Data 行数、新增真实标签契约说明、新增模型卡引用
  - [x] 5.2 更新 TASKS.md：标记已完成的 P0 任务项，更新当前状态描述
  - [x] 5.3 更新 AGENTS.md：新增真实标签模块路径、更新本地缓存状态、更新文档真源列表

# Task Dependencies
- Task 1 (Football-Data 重建) 独立，可先执行
- Task 2 (2526 覆盖) 依赖 Task 1（重建后的 Parquet 是评估输入）
- Task 3 (标签契约) 可与 Task 1 并行
- Task 4 (模型卡) 可与 Task 1-3 并行
- Task 5 (文档更新) 依赖 Task 1-4 全部完成
