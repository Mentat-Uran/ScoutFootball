# ScoutFootball 数据获取指南

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
- **位置**: `data/scoutfootball.duckdb`
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

### Transfermarkt（Kaggle 第三方数据集，实验性）

德转官网没有公开 API，且 ToS 禁止机器人/爬虫/页面抓取。本仓库通过 Kaggle 第三方数据集 `davidcariboo/player-scores`（与 `dcaribou/transfermarkt-datasets` 同源）获取结构化 CSV，作为既有 DuckDB 下载路径之外的并列选项。

**前置条件**：
1. 安装/可调用 Kaggle CLI（脚本默认走 `uvx kaggle`，无需写入项目依赖；也可执行 `uv tool install kaggle` 或 `pip install kaggle`）。
2. 首次使用先在终端执行一次（浏览器登录 Kaggle，凭证写到 `~/.kaggle/kaggle.json`）：

```powershell
uvx kaggle auth login
```

**下载并验证**（从 `scoutlab/` 项目根目录运行）：

```powershell
# 仅检查是否已认证
uv run python scripts/download_transfermarkt_kaggle.py --check-only

# 下载并解压 CSV 到 data/raw/transfermarkt_datasets/csv/
uv run python scripts/download_transfermarkt_kaggle.py

# 强制重新下载
uv run python scripts/download_transfermarkt_kaggle.py --force-refresh
```

**布局**（整个 `data/raw/transfermarkt_datasets/` 已被 `.gitignore` 排除，不进入仓库）：

```
data/raw/transfermarkt_datasets/
├─ csv/                                # Kaggle 解压后的原始 CSV
│  ├─ players.csv
│  ├─ clubs.csv
│  ├─ appearances.csv
│  ├─ player_valuations.csv
│  ├─ transfers.csv
│  └─ ...
├─ {table_name}.parquet               # 转换后的 Parquet 快照（与 DuckDB 路径共用）
└─ transfermarkt_kaggle_manifest.json # 溯源清单：上游、下载时间、缺失表
```

**Python 调用**（读取已下载的 CSV 并缓存为 Parquet）：

```python
from scoutfootball.adapters import load_csv_table

result = load_csv_table("player_valuations")
df = result.dataframe          # pandas DataFrame
print(result.metadata.record_count)
```

**许可边界**：
- 个人本地使用 OK；MIT 许可证只覆盖本仓库代码，不会让第三方德转数据自动变成 MIT 数据。
- 公开导出或再分发必须先向德转申请书面许可（`sales@transfermarkt.com` 或 `info@transfermarkt.com`）。
- 完整合规信息见 [DATA_RIGHTS.md §2.1](DATA_RIGHTS.md#21-transfermarkt_datasets)。
- 此数据源仍是实验性状态，未注册到 `architecture.py`，未进入下游特征/训练/真值标签流程。

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
