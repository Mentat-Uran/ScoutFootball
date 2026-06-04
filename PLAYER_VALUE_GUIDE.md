# ScoutLab 球员价值评估系统指南

## 一、数据源获取

### 已实现的数据源

| 数据源 | 优先级 | 状态 | 用途 |
|--------|--------|------|------|
| StatsBomb Open Data | P0 | ✅ | 事件流主源 |
| Football-Data.co.uk | P0 | ✅ | 比赛结果和赔率 |
| Club Elo | P0 | ⏳ API 超时 | 球队强度 |

### 建议扩展的数据源

| 数据源 | 优先级 | 用途 | 获取方式 |
|--------|--------|------|----------|
| Understat | P1 | xG, xA, xGChain | Python 库 |
| FBref | P1 | 补充统计 | 限速爬取 |
| Transfermarkt | P2 | 市场价值 | 手动导入 |

---

## 二、高阶指标计算方法

### 1. Expected Threat (xT)

**原理**: 将球场划分为 16x12 网格，每个格子有一个威胁值

**计算公式**:
```
xT(action) = xT(end_location) - xT(start_location)
```

**应用场景**:
- 评估传球的进攻价值
- 评估带球推进的价值
- 识别创造机会的球员

### 2. Expected Goals (xG)

**原理**: 基于射门位置、角度、防守压力等计算进球概率

**数据源**: StatsBomb 提供 xG 值

**应用**:
- 评估射门质量
- 识别高产射手
- 预测未来进球

### 3. 预期助攻 (xA)

**原理**: 评估传球转化为进球的概率

**计算**:
```
xA(pass) = Σ(xG of resulting shot)
```

### 4. 进球超额 (G - xG)

**原理**: 实际进球减去预期进球

**解读**:
- 正值: 射手能力强于平均水平
- 负值: 射手能力低于平均水平

---

## 三、综合球员价值评估

### 评估维度

```
球员价值 = 进攻贡献 + 防守贡献 + 控球贡献 + 比赛背景调整
```

### 进攻指标权重 (按位置)

| 位置 | 核心指标 | 权重 |
|------|----------|------|
| 前锋 | goals_per_90, xG, finishing_delta | 40% |
| 中场 | xT, passes, forward_pass_rate | 50% |
| 后卫 | tackles, interceptions, duel_win_rate | 30% |

### 综合评分公式

```python
composite_score = Σ(normalized_metric × weight) × 100
```

---

## 四、运行示例

### 1. 获取数据

```bash
# StatsBomb 数据
PYTHONPATH=src uv run python scripts/fetch_statsbomb_data.py

# Football-Data
PYTHONPATH=src uv run python scripts/fetch_football_data.py

# 数据验证
PYTHONPATH=src uv run python scripts/validate_data.py
```

### 2. 计算指标

```bash
# 特征工程
PYTHONPATH=src uv run python scripts/feature_engineering.py

# 球员价值评估
PYTHONPATH=src uv run python scripts/player_value_system.py
```

### 3. 查看结果

```python
import pandas as pd
from scoutlab.config import PlatformSettings

settings = PlatformSettings.from_root()

# 加载球员指标
metrics = pd.read_parquet(settings.gold_root / "feature_store" / "player_value_metrics.parquet")

# 查看 Top 10
top_players = metrics.nlargest(10, "composite_score")
print(top_players[["player_name", "composite_score", "xG_total", "xT_total"]])
```

---

## 五、指标解读

### xT (Expected Threat)

| xT 值 | 解读 |
|--------|------|
| > 0.05 | 高价值传球/带球 |
| 0.01 - 0.05 | 中等价值 |
| < 0.01 | 低价值或负价值 |

### 综合评分

| 评分 | 解读 |
|------|------|
| 80+ | 世界级表现 |
| 70-79 | 优秀表现 |
| 60-69 | 良好表现 |
| 50-59 | 平均表现 |
| < 50 | 低于平均 |

---

## 六、下一步改进

1. **获取更多数据**: 扩展到更多联赛和赛季
2. **百分位归一化**: 用真实数据分布计算百分位
3. **比赛背景调整**: 考虑对手强度、比赛重要性
4. **时间序列分析**: 跟踪球员状态变化
5. **机器学习模型**: 训练更精确的价值预测模型
