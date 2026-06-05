# Tasks

- [x] Task 1: 重写 objective_torch 为组合目标
  - [x] 1.1 新增 `ndcg_loss()` 函数：对每个联赛赛季 Top 20 球队做可微分 NDCG
  - [x] 1.2 新增 `position_consistency_loss()` 函数：对每个位置组计算评分排序与核心统计指标排序的 soft-Spearman
  - [x] 1.3 新增 `extreme_penalty()` 函数：对评分超出 3σ 的球员施加 L2 惩罚
  - [x] 1.4 重写 `objective_torch()` 为五项组合目标，权重通过命令行参数覆盖
  - [x] 1.5 更新 `optimize()` 函数签名，增加组合目标权重参数
  - [x] 1.6 更新 `argparse` 命令行参数，增加 `--spearman-weight`、`--ndcg-weight`、`--position-consistency-weight`、`--extreme-penalty-weight`、`--prior-weight`
  - [x] 1.7 编写单元测试验证各子目标函数的梯度可传播性

- [x] Task 2: 模型运行登记
  - [x] 2.1 新增 `save_model_run()` 函数：保存 optimized_params.npy + meta.json 到 `data/models/runs/<timestamp>/`
  - [x] 2.2 meta.json 包含：参数、随机种子、输入文件 hash、holdout 指标、位置内指标、误差案例摘要、组合目标权重
  - [x] 2.3 在 `optimize()` 完成后调用 `save_model_run()`
  - [x] 2.4 编写单元测试验证模型运行登记的保存和读取

- [x] Task 3: 神经网络准入门槛
  - [x] 3.1 在 MODEL_CARD.md 增加"神经网络准入门槛"章节
  - [x] 3.2 明确六项准入条件：真实标签非空、时间切分、baseline 对比、位置内指标、误差案例复盘、禁止纯球队积分监督

- [ ] Task 4: GPU 服务器完整重跑
  - [ ] 4.1 将代码和数据同步到 Windows GPU 服务器
  - [ ] 4.2 运行完整优化：`python optimize_ratings_gpu.py --data_dir ./data --pop 32 --steps 500 --patience 80`
  - [ ] 4.3 记录 holdout 指标：Spearman、Pearson、NDCG@20、overfit gap
  - [ ] 4.4 生成新的 `player_ratings_optimized.parquet`

- [ ] Task 5: 误差案例复盘
  - [ ] 5.1 对 Everton、Stuttgart、Hoffenheim、Rennes 记录新评分、新排名、与实际积分偏差
  - [ ] 5.2 对 Napoli、Real Madrid、Arsenal、PSG 记录新评分、新排名、与实际积分偏差
  - [ ] 5.3 更新 PROBLEMS.md，增加"GPU 重跑复盘"章节

- [x] Task 6: 更新 README.md、TASKS.md、AGENTS.md
  - [x] 6.1 更新 README.md：组合优化目标说明、模型运行登记说明
  - [x] 6.2 更新 TASKS.md：标记已完成的 P0 任务项，更新当前状态
  - [x] 6.3 更新 AGENTS.md：新增模型运行登记路径、更新评分系统状态

# Task Dependencies
- Task 1 (重写目标) ✅ 独立，已完成
- Task 2 (模型运行登记) ✅ 已完成
- Task 3 (准入门槛) ✅ 已完成
- Task 4 (GPU 重跑) 依赖 Task 1-2（新目标函数和运行登记）— 待 GPU 服务器执行
- Task 5 (误差复盘) 依赖 Task 4（需要新评分产物）— 待 GPU 服务器执行
- Task 6 (文档更新) ✅ 已完成
