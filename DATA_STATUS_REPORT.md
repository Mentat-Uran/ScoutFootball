# ScoutLab 数据获取完成报告

## 数据规模

### FBref 五大联赛球员数据 ✅

| 指标 | 数值 |
|------|------|
| 总记录数 | 8,595 条 |
| 独特球员数 | 4,321 名 |
| 覆盖赛季 | 3 个 (2022-2025) |
| 覆盖联赛 | 4 个 (英西法意) |

**各联赛分布:**

| 联赛 | 记录数 | 球员数 |
|------|--------|--------|
| 英超 (Premier League) | 1,723 | 939 |
| 西甲 (La Liga) | 1,806 | 1,009 |
| 法甲 (Ligue 1) | 1,699 | 1,032 |
| 意甲 (Serie A) | 1,853 | 1,038 |

**统计列包含:**
- 比赛场次、首发、分钟数
- 进球、助攻、点球
- 黄牌、红牌
- 每90分钟数据

---

### 其他数据源

| 数据源 | 记录数 | 状态 |
|--------|--------|------|
| StatsBomb Open Data | 68 场比赛, 11,871 事件 | ✓ |
| Football-Data.co.uk | 5,330 场比赛 (5大联赛) | ✓ |
| 球员价值指标 | 10 名球员 | ✓ |

---

## 数据文件位置

```
data/
├── raw/
│   ├── fbref/
│   │   └── player_stats_big5_3seasons.parquet    # 8,595 条记录
│   ├── statsbomb_open/
│   │   ├── big5_matches.parquet                  # 58 场比赛
│   │   ├── matches_all.parquet                   # 68 场比赛
│   │   └── events_sample.parquet                 # 11,871 事件
│   └── football_data/
│       └── combined_results.parquet              # 5,330 场比赛
├── gold/feature_store/
│   ├── player_value_metrics.parquet              # 球员价值指标
│   ├── team_features.parquet                     # 球队特征
│   └── match_features.parquet                    # 比赛特征
└── scoutlab.duckdb                               # DuckDB 数据库
```

---

## 数据获取脚本

| 脚本 | 功能 | 状态 |
|------|------|------|
| `scripts/fetch_fbref_full.py` | 获取 FBref 五大联赛数据 | ✓ |
| `scripts/fetch_statsbomb_full.py` | 获取 StatsBomb 数据 | ✓ |
| `scripts/fetch_football_data.py` | 获取比赛结果和赔率 | ✓ |
| `scripts/player_value_system.py` | 球员价值评估 | ✓ |

---

## 下一步

1. **扩展德甲数据**: 当前 FBref 数据缺少德甲，需要单独获取
2. **获取更多统计类型**: 传球、射门、防守等详细统计
3. **球员价值评估**: 对所有 4,321 名球员进行价值评估
4. **特征工程**: 基于完整数据计算高级特征

---

## 运行命令

```bash
# 查看数据概览
PYTHONPATH=src uv run python scripts/data_overview.py

# 球员价值评估
PYTHONPATH=src uv run python scripts/player_value_system.py

# 特征工程
PYTHONPATH=src uv run python scripts/feature_engineering.py
```
