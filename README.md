# ScoutLab

本地优先的足球数据研究平台。整合五大公开数据源，覆盖五大联赛 10 赛季 27,000+ 球员。

## 核心能力

- PyTorch GPU 评分优化器 (77 参数, Holdout Spearman=0.80)
- GPU 远程计算 (Windows RTX 5070 Ti REST API)
- Pipeline: ingest → build-features → train
- Poisson 比分预测, 身价合理性评估
- Streamlit 可视化界面

## 数据源

| 数据源 | 记录数 | 赛季 |
|--------|--------|------|
| FBref | 14,356 条 | 2021-2026 |
| Football-Data | 17,936 场 | 2016-2026 |
| Understat | 27,254 条 | 2016-2026 |
| StatsBomb | 126 场 | - |
| Club Elo | 630 队 | - |

## 快速开始

```bash
# 本地优化
PYTHONPATH=src uv run python scripts/optimize_ratings_gpu.py --data_dir ./data --pop 10 --steps 300

# GPU 远程优化
uv run python scripts/gpu_client.py --server http://192.168.0.189:8420 optimize --pop 32 --steps 500

# Pipeline
PYTHONPATH=src uv run python -m scoutlab ingest
PYTHONPATH=src uv run python -m scoutlab build-features
PYTHONPATH=src uv run python -m scoutlab train

# 可视化
uv run streamlit run src/scoutlab/app/streamlit_app.py
```

## 技术栈

Python 3.14, uv, PyTorch (MPS/CUDA), DuckDB+Parquet, Streamlit+Plotly, pytest+Ruff

## 合规边界

- 不绕过验证码/反爬
- 不自动抓取 Transfermarkt
- 不高频请求 FBref
