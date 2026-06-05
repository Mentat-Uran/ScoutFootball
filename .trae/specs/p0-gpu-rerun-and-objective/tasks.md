# Tasks

- [x] Task 1: 重写 objective_torch 为组合目标
  - [x] 1.1 新增 `ndcg_loss()` 函数
  - [x] 1.2 新增 `position_consistency_loss()` 函数
  - [x] 1.3 新增 `extreme_penalty()` 函数
  - [x] 1.4 重写 `objective_torch()` 为五项组合目标
  - [x] 1.5 更新 `optimize()` 函数签名
  - [x] 1.6 更新 `argparse` 命令行参数
  - [x] 1.7 编写单元测试

- [x] Task 2: 模型运行登记
  - [x] 2.1 新增 `save_model_run()` 函数
  - [x] 2.2 meta.json 包含完整元数据
  - [x] 2.3 在 `optimize()` 完成后调用
  - [x] 2.4 编写单元测试

- [x] Task 3: 神经网络准入门槛
  - [x] 3.1 在 MODEL_CARD.md 增加章节
  - [x] 3.2 明确六项准入条件

- [x] Task 4: GPU 服务器完整重跑
  - [x] 4.1 同步代码和数据到 Windows GPU 服务器
  - [x] 4.2 运行完整优化（pop=32, steps=500, lr=0.05）
  - [x] 4.3 记录 holdout 指标：Spearman=0.6346, Pearson=0.6251, overfit gap=0.0537
  - [x] 4.4 保存参数到本地

- [x] Task 5: 误差案例复盘
  - [x] 5.1 分析各联赛 coverage 和 Spearman
  - [x] 5.2 识别 PL/La Liga coverage 不足问题
  - [x] 5.3 更新 PROBLEMS.md，增加"GPU 重跑复盘"章节

- [x] Task 6: 更新 README.md、TASKS.md、AGENTS.md
  - [x] 6.1 更新 README.md
  - [x] 6.2 更新 TASKS.md
  - [x] 6.3 更新 AGENTS.md
