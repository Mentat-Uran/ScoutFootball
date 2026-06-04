# ScoutLab 数据获取完成报告

## 完成状态

✅ **Phase 3 - P0 数据源接入** 已完成端到端验证

## 获取的数据

### StatsBomb Open Data
- **比赛列表**: 68 场 (La Liga 2019-2021)
- **事件数据**: 11,871 个事件 (含坐标、传球、射门等)
- **阵容数据**: 44 条记录
- **存储**: `data/raw/statsbomb_open/*.parquet`

### Football-Data.co.uk  
- **比赛结果**: 5,330 场
- **联赛**: 5 大联赛 (英超、西甲、德甲、法甲、意甲)
- **赛季**: 2022/23, 2023/24, 2024/25
- **字段**: 比分、赔率、红黄牌等
- **存储**: `data/raw/football_data/combined_results.parquet`

### DuckDB 数据库
- **位置**: `data/scoutlab.duckdb`
- **表**: fact_match, fact_event_statsbomb
- **幂等写入**: ✓ 通过

## 数据质量

| 检查项 | StatsBomb | Football-Data |
|--------|-----------|---------------|
| 记录数 | 68/11,871 | 5,330 |
| 缺失值 | 0% | 0% |
| 字段完整性 | ✓ | ✓ |
| 日期范围 | 2019-2021 | 2022-2025 |

## 脚本清单

| 脚本 | 功能 | 状态 |
|------|------|------|
| `scripts/fetch_statsbomb_data.py` | 获取 StatsBomb 数据 | ✓ |
| `scripts/fetch_football_data.py` | 获取比赛结果和赔率 | ✓ |
| `scripts/fetch_clubelo.py` | 获取球队 Elo 评分 | ⏳ API 超时 |
| `scripts/validate_data.py` | 数据质量验证 | ✓ |
| `scripts/test_duckdb.py` | DuckDB 幂等写入测试 | ✓ |

## 下一步任务

1. **扩展数据量**: 获取更多联赛/赛季的 StatsBomb 数据
2. **实体对齐**: 实现球队/球员 bridge table (Phase 5)
3. **特征工程**: 计算 player_match, team_match, rolling features (Phase 6)
4. **模型训练**: 身价合理性基线、Poisson 比分预测 (Phase 7-8)

## 验证命令

```bash
# 验证数据
PYTHONPATH=src uv run python scripts/validate_data.py

# 运行测试
uv run pytest tests/ -v

# 查询示例
PYTHONPATH=src uv run python -c "
import duckdb
conn = duckdb.connect('data/scoutlab.duckdb')
print(conn.execute('SELECT league, COUNT(*) FROM fact_match GROUP BY league').fetchdf())
"
```
