# Data Contracts

ScoutFootball 内部数据产物的 schema 契约。

## 比赛预测产物

### poisson_baseline_results.parquet
训练好的 Independent Poisson 模型元数据。

| 字段 | 类型 | 说明 |
|------|------|------|
| model_type | string | `"independent_poisson"` |
| train_rows | int | 训练用比赛行数 |
| league_home_rate | float | 联赛主场进球率 |
| league_away_rate | float | 联赛客场进球率 |
| num_teams | int | 球队数 |
| smoothing | float | 平滑系数 |

### dixon_coles_results.parquet
训练好的 Dixon-Coles 模型元数据。

| 字段 | 类型 | 说明 |
|------|------|------|
| model_type | string | `"dixon_coles"` |
| num_matches | int | 训练用比赛数 |
| rho | float | 低比分相关系数 (通常 -0.3 ~ 0) |
| home_advantage | float | 主场优势参数 |
| league_mean_goals | float | 联赛场均进球 |
| num_teams | int | 球队数 |
| half_life_days | float or null | 时间衰减半衰期 (null = 无衰减) |

### team_strengths.parquet
Poisson 模型的球队攻防强度参数。

| 字段 | 类型 | 说明 |
|------|------|------|
| team_id | string | 球队标识 |
| home_attack_strength | float | 主场进攻强度 (1.0 = 联赛平均) |
| away_attack_strength | float | 客场进攻强度 |
| home_defense_strength | float | 主场防守强度 |
| away_defense_strength | float | 客场防守强度 |

### dc_team_strengths.parquet
Dixon-Coles 模型的球队攻防参数。

| 字段 | 类型 | 说明 |
|------|------|------|
| team_id | string | 球队标识 |
| attack | float | 进攻参数 (0 = 联赛平均) |
| defense | float | 防守参数 (0 = 联赛平均) |

## 球员评分产物

### player_ratings_optimized.parquet
GPU 优化器产出的球员评分。

| 字段 | 类型 | 说明 |
|------|------|------|
| player_id | string | 球员标识 |
| player_name | string | 球员姓名 |
| team_name | string | 球队名 |
| position_group | string | 位置组 (GK/CB/FB/DM/CM/AM/W/ST) |
| rating | float | 综合评分 (0-100) |
| season | string | 赛季 |
| league | string | 联赛 |
| minutes_played | int | 出场分钟数 |
| confidence | string | 置信度 (HIGH/MEDIUM/LOW) |

### rating_feature_matrix.parquet
评分特征矩阵，含缺失字段标记和覆盖率。

| 字段 | 类型 | 说明 |
|------|------|------|
| player_id | string | 球员标识 |
| player_name | string | 球员姓名 |
| position_group | string | 位置组 |
| season | string | 赛季 |
| league | string | 联赛 |
| minutes_played | int | 出场分钟数 |
| goals | int | 进球数 |
| assists | int | 助攻数 |
| npg_p90 | float or null | 每90分钟非点球进球 |
| assists_p90 | float or null | 每90分钟助攻 |
| has_defense | bool | 是否有防守数据 |
| has_possession | bool | 是否有控球数据 |
| coverage | float | 数据覆盖率 (0-1) |

## 球探队列产物

### review_queue.parquet
低置信度球员复核队列。

| 字段 | 类型 | 说明 |
|------|------|------|
| player_id | string | 球员标识 |
| player_name | string | 球员姓名 |
| reason | string | 低置信度原因 |
| priority | string | 优先级 (high/medium/low) |
| created_at | datetime | 创建时间 |

### watchlist.parquet / shortlist.parquet
球探关注列表和候选名单。Schema 同 review_queue。

## API 响应契约

### GET /predictions/{home}/{away}?model=poisson|dixon_coles
比赛预测 API。返回精确比分矩阵、期望进球和市场概率。

### GET /predictions/meta
返回 Poisson 和 Dixon-Coles 模型状态及可用模型列表。

```json
{
  "poisson": { "model_type": "...", "league_home_rate": 1.5, ... },
  "dixon_coles": { "status": "ok" | "not_available", ... },
  "available_models": ["poisson", "dixon_coles"]
}
```
