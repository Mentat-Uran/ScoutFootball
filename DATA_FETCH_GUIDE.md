# ScoutLab 数据获取指南

## 已获取数据

### 1. StatsBomb Open Data
- **比赛数据**: 68 场比赛 (La Liga 2019-2021)
- **事件数据**: 11,871 个事件 (3 场比赛样本)
- **阵容数据**: 44 条记录
- **文件位置**: `data/raw/statsbomb_open/`

### 2. Football-Data.co.uk
- **比赛结果**: 5,330 场比赛
- **覆盖联赛**: Premier League, La Liga, Bundesliga, Ligue 1, Serie A
- **覆盖赛季**: 2022/23, 2023/24, 2024/25
- **文件位置**: `data/raw/football_data/combined_results.parquet`

### 3. DuckDB 数据库
- **位置**: `data/scoutlab.duckdb`
- **表**: fact_match (5,330 行), fact_event_statsbomb (11,871 行)

## 获取更多数据

### StatsBomb (扩展数据量)
```bash
PYTHONPATH=src uv run python scripts/fetch_statsbomb_data.py
```
修改脚本中的 `COMPETITIONS` 和 `SEASONS` 变量可获取更多联赛/赛季。

### Football-Data.co.uk
```bash
PYTHONPATH=src uv run python scripts/fetch_football_data.py
```

### Club Elo
```bash
PYTHONPATH=src uv run python scripts/fetch_clubelo.py
```
注意: Club Elo API 可能较慢，建议分批获取。

## 数据验证

```bash
PYTHONPATH=src uv run python scripts/validate_data.py
```

## 数据质量指标

| 数据源 | 记录数 | 缺失值 | 日期范围 |
|--------|--------|--------|----------|
| StatsBomb 比赛 | 68 | 0% | 2019-09 ~ 2021-05 |
| StatsBomb 事件 | 11,871 | 0% | - |
| Football-Data | 5,330 | 0% | 2022-2025 |

## 下一步

1. 获取更多联赛/赛季数据
2. 实现实体对齐 (球队/球员 bridge table)
3. 计算特征 (player_match, team_match, rolling features)
4. 训练基线模型 (身价合理性, Poisson 比分预测)
