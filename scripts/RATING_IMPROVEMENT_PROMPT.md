# 评分系统改进任务

## 当前问题

`scripts/optimize_ratings_gpu.py` 的评分系统有三个平衡问题：

### 1. 联赛系数不合理

**当前实现 (第 947-980 行):**
```python
# 使用加权平均: 70% ln 比值 + 30% 线性比值
ln_ratio = torch.log(league_coeffs) / eng_log
linear_ratio = league_coeffs / max_coeff
weight_linear = torch.sigmoid(league_log_scale_clamped - 1.0)
league_strength = (1 - weight_linear) * ln_ratio + weight_linear * linear_ratio
```

**问题:**
- 使用 ln 比值时，联赛间差距太小 (0.92-1.0)，导致优化器给 Ligue 1/Serie A 球员过高分数
- 使用线性比值时，差距太大 (0.68-1.0)，导致英超占 27/30 Top 30

**目标排序 (基于 UEFA 官方系数 + Opta Power Rankings):**
- Premier League: 119.52 (最强)
- La Liga: 93.00
- Bundesliga: 92.90
- Ligue 1: 83.50
- Serie A: 81.93

**期望效果:**
- EPL 球员占 Top 30 约 12-15 人 (40-50%)
- La Liga 占 5-7 人
- Bundesliga 占 3-5 人
- Ligue 1 占 2-4 人
- Serie A 占 2-4 人

**建议方案:**
- 使用 `(coeff / max_coeff) ^ 0.6` 作为联赛系数
- 这样 Serie A 的系数 = (81.93/119.52)^0.6 ≈ 0.82
- 差距适中，不会过度惩罚弱联赛

### 2. 前锋分数偏高

**当前实现 (第 987-998 行):**
```python
pos_penalty = torch.ones(N_POS, device=device)
st_idx = POS_TO_IDX.get("ST", 0)
w_idx = POS_TO_IDX.get("W", 1)
pos_penalty[st_idx] = 0.96  # ST 打 96 折
pos_penalty[w_idx] = 0.98   # W 打 98 折
```

**问题:**
- 前锋的进攻权重 (attack_weight) 在优化后通常很高 (0.5-0.8)
- 导致前锋排名偏高，Top 30 中 ST 占 21 人

**期望效果:**
- Top 30 中 ST 占 6-10 人
- Top 30 中 W 占 4-6 人
- Top 30 中 CM/AM 占 8-12 人
- Top 30 中 DM/FB/CB 占 2-4 人

**建议方案:**
- 不要用固定的 position_penalty
- 改为: 对 attack 维度施加位置相关的缩放
  ```python
  # 攻击权重缩放: 前锋的 attack 权重降低 15%
  attack_scale = torch.ones(N_POS, device=device)
  attack_scale[st_idx] = 0.85
  attack_scale[w_idx] = 0.90
  attack_scale[am_idx] = 0.95
  # 在计算 attack 时应用
  attack = (npg_pct * player_aw[:, 0] + ast_pct * player_aw[:, 1] + vol_pct * player_aw[:, 2]) * attack_scale[pos_idx]
  ```

### 3. 出场时间惩罚需要微调

**当前实现 (第 918-947 行):**
```python
min_threshold = 500.0
min_ceiling = 1500.0
min_floor = 0.3

below_threshold = minutes < min_threshold
in_transition = (minutes >= min_threshold) & (minutes < min_ceiling)
above_ceiling = minutes >= min_ceiling

min_rel = torch.full_like(minutes, min_floor)
if in_transition.any():
    transition_progress = (minutes[in_transition] - min_threshold) / (min_ceiling - min_threshold)
    min_rel[in_transition] = min_floor + (1.0 - min_floor) * transition_progress
min_rel[above_ceiling] = 1.0
```

**问题:**
- 500 分钟的球员只有 0.3 底分，可能太重
- 1500 分钟才到满分，可能太慢

**期望效果:**
- < 500 分钟: 0.4-0.5 底分 (惩罚但不致命)
- 500-1200 分钟: 快速上升
- > 1200 分钟: 满分

**建议方案:**
```python
min_threshold = 400.0
min_ceiling = 1200.0
min_floor = 0.4
```

## 修改要求

1. **只修改 `compute_ratings_torch` 函数** (第 838-998 行)
2. **不要修改优化器的核心逻辑** (soft-Spearman loss, AdamW 等)
3. **不要修改数据加载和特征构建**
4. **保持 77 个参数不变** (N_PARAMS = 77)
5. **添加详细的中文注释** 说明每个调整的原因

## 验证方法

修改后运行以下命令验证:
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

**期望输出:**
```
联赛分布:
  Premier League: 12-15
  La Liga: 5-7
  Bundesliga: 3-5
  Ligue 1: 2-4
  Serie A: 2-4

位置分布:
  CM: 8-12
  ST: 6-10
  W: 4-6
  AM: 2-4
  DM: 1-3
  FB: 1-2
```

## 参考信源

- UEFA 官方国家系数: https://kassiesa.net/uefa/data/method5/ccoef2026.html
- Opta Power Rankings: https://theanalyst.com/articles/strongest-leagues-in-the-world-opta-power-rankings-june-2025
- 位置权重参考: FM (Football Manager) 系列的位置权重设计
