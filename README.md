# ScoutLab

本地优先的足球数据研究平台，用公开合规的数据源完成球员评分、比分预测和可视化分析。

## 当前状态

| 数据源 | 记录数 | 赛季 | 状态 |
|--------|--------|------|------|
| FBref 球员统计 | 14,356 条 | 2021-2026 (5赛季) | ✓ |
| Football-Data.co.uk | 17,936 场 | 2016-2026 (10赛季) | ✓ |
| Understat | 27,254 条 | 2016-2026 (10赛季) | ✓ |
| StatsBomb Open Data | 126 场, 11,871 事件 | - | ✓ |
| Club Elo | 630 支球队 | - | ✓ |

**核心能力:**
- 评分优化器: PyTorch GPU, 77 参数, Holdout Spearman=0.8382
- GPU 远程计算: Windows RTX 5070 Ti REST 服务器
- Pipeline: ingest → build-features → train 全接通
- 比分预测: Poisson 基线模型

**快速开始:**
```bash
# 本地优化
PYTHONPATH=src uv run python scripts/optimize_ratings_gpu.py --data_dir ./data --pop 10 --steps 300

# GPU 远程优化 (需要 Windows 服务器)
python scripts/gpu_client.py --server http://192.168.0.189:8420 optimize --pop 32 --steps 500

# 球员评分 Top 100
PYTHONPATH=src uv run python scripts/player_rating_v3.py

# Pipeline 命令
PYTHONPATH=src uv run python -m scoutlab ingest
PYTHONPATH=src uv run python -m scoutlab build-features
PYTHONPATH=src uv run python -m scoutlab train

# 可视化
uv run streamlit run src/scoutlab/app/streamlit_app.py
```

## 项目定位

- 目标赛事: Big 5 联赛
- 时间范围: 最近 10 个赛季
- 使用场景: 本地研究型内部工具
- 存储: DuckDB + Parquet
- 可视化: Streamlit + Plotly

核心输出:
- 球员表现分 (按位置权重、联赛系数、出场时间校准)
- 身价合理性评估
- 比分预测 (Poisson 基线)
- 风格 embedding (规划中)

## 数据源策略

| 数据源 | 优先级 | 用途 | 策略 |
|--------|--------|------|------|
| StatsBomb | P0 | 事件流 | 官方公开 JSON |
| Football-Data | P0 | 比赛结果 | 官方 CSV |
| Club Elo | P0 | 球队强度 | 官方 API |
| Understat | P1 | xG/xA | 公开端点，需缓存限速 |
| FBref | P1 | 标准表 | 仅低频补充，不作主源 |
| Transfermarkt | P2 | 市值 | 禁止自动抓取 |

## 技术栈

- Python 3.14, uv 包管理
- PyTorch (Mac MPS / Windows CUDA)
- DuckDB + Parquet
- Streamlit + Plotly
- pytest + Ruff

## 常用命令

```bash
# 环境
uv sync
uv run pytest
uv run ruff check .

# Pipeline
PYTHONPATH=src uv run python -m scoutlab ingest
PYTHONPATH=src uv run python -m scoutlab build-features
PYTHONPATH=src uv run python -m scoutlab train
PYTHONPATH=src uv run python -m scoutlab validate

# 数据抓取
PYTHONPATH=src uv run python scripts/fetch_fbref_5seasons.py
PYTHONPATH=src uv run python scripts/fetch_understat_extended.py
PYTHONPATH=src uv run python scripts/fetch_football_data_extended.py

# GPU 远程计算
python scripts/gpu_client.py --server http://192.168.0.189:8420 health
python scripts/gpu_client.py --server http://192.168.0.189:8420 optimize --pop 32 --steps 500
python scripts/gpu_client.py --server http://192.168.0.189:8420 score "Haaland"
python scripts/gpu_client.py --server http://192.168.0.189:8420 top --n 20 --position ST

# 可视化
uv run streamlit run src/scoutlab/app/streamlit_app.py
```

## 合规边界

- 不绕过验证码/反爬机制
- 不自动抓取 Transfermarkt
- 不高频请求 FBref
- 不公开分发受限制的缓存
