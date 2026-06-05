# P0 GPU 重跑、优化目标重写与误差复盘 Spec

## Why

当前评分优化器只优化球队积分 Spearman/Pearson 相关性，导致出勤捷径（CM/CB/FB/GK 靠高出场分钟拉高球队评分）和强队核心低估（Napoli、Real Madrid、Arsenal）两大核心问题。需要：1) 用新口径（availability cap 0.18-0.20 + 稳健球队聚合 + N/A 过滤）在 GPU 服务器重跑完整优化；2) 重写优化目标为组合目标；3) 复盘误差案例并记录结论。

## What Changes

- 重写 `objective_torch()` 为组合目标：Spearman + NDCG + 位置内排序一致性 + 极端样本惩罚 + 先验正则
- 在 GPU 服务器用完整参数（pop=32, steps=500）重跑优化，生成新的 `optimized_params.npy`、holdout predictions、league metrics、calibration
- 复盘 PROBLEMS.md 中的误差案例，记录新旧排名变化
- 定义神经网络准入门槛，写入 MODEL_CARD.md
- 保存 feature manifest、参数、随机种子、输入 hash 到 `data/models/runs/`
- 更新 PROBLEMS.md、TASKS.md、AGENTS.md、README.md

## Impact

- Affected specs: P0 评分系统真实影响力校准
- Affected code:
  - `scripts/optimize_ratings_gpu.py` — objective_torch 重写 + model run 保存
  - `PROBLEMS.md` — 误差复盘更新
  - `MODEL_CARD.md` — 神经网络准入门槛
  - `data/models/runs/` — 新增模型运行登记
- Affected docs: README.md、TASKS.md、AGENTS.md

## ADDED Requirements

### Requirement: 组合优化目标

系统 SHALL 将 `objective_torch()` 从纯 Spearman/Pearson 相关性改为组合目标：

1. **Spearman rank correlation**（权重 0.50）：保留球队积分排序相关性作为主目标
2. **NDCG@20**（权重 0.20）：对每个联赛赛季的 Top 20 球队评分做 NDCG，奖励头部排序准确性
3. **位置内排序一致性**（权重 0.15）：对每个位置组内评分排序与位置内统计指标排序的一致性惩罚
4. **极端样本惩罚**（权重 0.10）：对评分极端值（超出 3σ）施加 L2 惩罚，防止出勤捷径产生异常高分
5. **先验正则**（权重 0.05）：保持与 v3 explainable prior 的距离

#### Scenario: 组合目标可微分

- **WHEN** 优化器计算 loss
- **THEN** 五个子目标均可通过 PyTorch autograd 反向传播
- **AND** 各子目标权重可通过命令行参数覆盖

#### Scenario: 位置内排序一致性

- **WHEN** 计算位置内排序一致性 loss
- **THEN** 对每个位置组（ST/W/AM/CM/DM/FB/CB/GK），计算球员评分排序与该位置核心统计指标排序的 soft-Spearman
- **AND** 位置核心指标为：ST→npxg_p90, W→g_a_volume, AM→assists_p90, CM→progressive_passes, DM→defense_composite, FB→crosses_p90, CB→defense_composite, GK→gk_save_rate

### Requirement: GPU 服务器完整重跑

系统 SHALL 在 Windows 5070 Ti 服务器上用完整参数重跑优化：

- pop_size=32, n_steps=500, lr=0.05, patience=80
- 使用新 availability cap (0.18-0.20) 和稳健球队聚合
- 使用 N/A 球队过滤后的 Football-Data 积分
- 保存 optimized_params.npy、optimized_params_meta.json、holdout predictions

#### Scenario: 完整优化成功

- **WHEN** 在 GPU 服务器运行 `python optimize_ratings_gpu.py --data_dir ./data`
- **THEN** 生成新的 optimized_params.npy 和 holdout 指标
- **AND** holdout Spearman 不低于 0.55（当前 smoke test 为 0.5729）

### Requirement: 误差案例复盘

系统 SHALL 对 PROBLEMS.md 中的误差案例进行复盘，记录新旧排名变化。

#### Scenario: 复盘完成

- **WHEN** 新优化完成
- **THEN** 对 Everton、Stuttgart、Hoffenheim、Rennes、Napoli、Real Madrid、Arsenal、PSG 记录：新评分、新排名、与实际积分排名的偏差、是否改善
- **AND** 更新 PROBLEMS.md

### Requirement: 神经网络准入门槛

系统 SHALL 在 MODEL_CARD.md 中定义神经网络评分器的准入门槛。

#### Scenario: 准入门槛定义

- **WHEN** MODEL_CARD.md 被读取
- **THEN** 包含神经网络准入门槛章节，明确：
  1. 必须先有球员真实标签（player_truth_labels.parquet 非空）
  2. 必须有时间切分（train/val/test）
  3. 必须有当前优化器作为 baseline
  4. 必须有位置内/跨位置指标
  5. 必须有误差案例复盘
  6. 不允许只用球队积分监督训练默认模型

### Requirement: 模型运行登记

系统 SHALL 每次优化后保存模型运行登记到 `data/models/runs/`。

#### Scenario: 运行登记保存

- **WHEN** 优化完成
- **THEN** 保存到 `data/models/runs/<timestamp>/`：optimized_params.npy、meta.json（含参数、随机种子、输入 hash、指标、位置内指标、误差案例摘要）

## MODIFIED Requirements

### Requirement: objective_torch

`objective_torch()` 从纯 Spearman/Pearson 改为组合目标，保留 `differentiable_rank_loss()` 作为子目标之一。

### Requirement: PROBLEMS.md

PROBLEMS.md 增加"本轮 GPU 重跑复盘"章节，记录新旧指标对比和误差案例变化。
