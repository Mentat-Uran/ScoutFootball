# Codex 指令：修复评分系统位置权重失衡

## 当前问题

`scripts/optimize_ratings_gpu.py` 的 `compute_ratings_torch` 函数在最近一轮优化后，Top 30 球员中 CM 占 28 人，ST 只有 2 人。原因：

1. **CM 的 quality 权重过高**: 优化器给 CM 的 quality 维度权重 0.54，导致全能型中场得分虚高
2. **ST 的 attack 权重过低**: 优化器给 ST 的 attack 维度权重只有 0.086，加上 attack_scale=0.94 的缩放，前锋被双重压低
3. **优化器过拟合**: 77 个自由参数 + 10赛季数据，优化器找到了"让 CM 高 quality 权重"的局部最优解

## 目标

Top 30 球员位置分布:
- ST: 6-10 人
- W: 4-6 人
- CM: 8-12 人
- AM/DM/FB/CB: 2-4 人

联赛分布 (已基本达标):
- Premier League: 10-15 人
- La Liga: 4-7 人
- Bundesliga: 4-7 人
- Ligue 1: 2-4 人
- Serie A: 2-4 人

## 修改要求

修改 `compute_ratings_torch` 函数 (第 840-988 行)，采用以下方案之一:

### 方案 A: 给 quality 维度加位置缩放 (推荐)

在第 924 行 `quality` 计算后，添加位置缩放:
```python
# quality 维度位置缩放: 避免 CM 因全能型数据虚高
quality_scale = torch.ones(N_POS, device=device)
cm_idx = POS_TO_IDX.get("CM", 3)
dm_idx = POS_TO_IDX.get("DM", 4)
quality_scale[st_idx] = 1.05  # ST 的 quality 略微上浮
quality_scale[cm_idx] = 0.92  # CM 的 quality 降低
quality_scale[dm_idx] = 0.95  # DM 的 quality 略降
quality = quality * quality_scale[pos_idx]
```

### 方案 B: 限制 ST 的 attack 最低权重

在参数解包时 (第 849-852 行)，给 ST 的 attack 权重设下限:
```python
aw = torch.softmax(aw_raw, dim=1)
# ST 的 attack 权重下限 0.15 (当前优化后只有 0.086)
aw[st_idx, :] = torch.clamp(aw[st_idx, :], min=0.15)
aw = aw / aw.sum(dim=1, keepdim=True)  # 重新归一化
```

### 方案 C: 在 loss 中加位置多样性惩罚

在 `optimize` 函数的 loss 计算中，添加位置分布惩罚:
```python
# 计算 Top 30 球员的位置分布
top30_positions = pos_idx[top30_indices]
position_counts = torch.bincount(top30_positions, minlength=N_POS).float()
position_entropy = -(position_counts / position_counts.sum() * torch.log(position_counts / position_counts.sum() + 1e-8)).sum()
diversity_penalty = -position_entropy * 0.1  # 鼓励位置多样性
total_loss = loss + reg + diversity_penalty
```

### 方案 D: 分阶段优化

1. 先固定联赛系数，只优化位置权重 (pop=8, steps=200)
2. 再固定位置权重，只优化联赛系数 (pop=8, steps=200)
3. 最后联合微调 (pop=16, steps=300)

## 验证方法

修改后运行:
```bash
cd /Users/mentat/Library/Mobile Documents/com~apple~CloudDocs/football
uv run python -c "
import numpy as np, torch
from pathlib import Path
from scripts.optimize_ratings_gpu import load_data, build_feature_tensors, compute_ratings_torch

df, _ = load_data(Path('data'))
train_df = df[df['season'].isin(['1617','1718','1819','1920','2021','2122','2223','2324','2425'])]
feat = build_feature_tensors(df, rank_reference_df=train_df)
params = torch.tensor(np.load('data/gold/feature_store/optimized_params.npy'))
ratings = compute_ratings_torch(feat, params, torch.device('cpu'))
df['score'] = ratings.detach().numpy()
top30 = df[df['season']=='2526'].nlargest(30, 'score')

print('联赛分布:')
for l, c in top30['league'].value_counts().items():
    print(f'  {l}: {c}')
print('位置分布:')
for p, c in top30['sub_position'].value_counts().items():
    print(f'  {p}: {c}')
"
```

期望输出:
```
联赛分布:
  Premier League: 10-15
  Bundesliga: 4-7
  La Liga: 4-7
  Ligue 1: 2-4
  Serie A: 2-4
位置分布:
  CM: 8-12
  ST: 6-10
  W: 4-6
```

## 注意事项

- 不要修改 N_PARAMS (保持 77)
- 不要修改优化器核心逻辑 (soft-Spearman loss, AdamW)
- 不要修改数据加载和特征构建
- 添加详细的中文注释
