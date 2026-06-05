# ⚽️ ScoutLab

> **A local-first football data research platform.**
> 
> **本地优先的足球数据研究平台。**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![uv](https://img.shields.io/badge/uv-Fast-magenta)](https://github.com/astral-sh/uv)
[![DuckDB](https://img.shields.io/badge/DuckDB-Fast%20Analytics-yellow)](https://duckdb.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-Optimized-ee4c2c)](https://pytorch.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B)](https://streamlit.io/)

🌐 **[English Version](#-english)** | 🇨🇳 **[中文版本](#-简体中文)**

---

<br>

<a id="-english"></a>
## 🇺🇸 English

### 🌟 Overview

ScoutLab is a local-first football data research platform. Its goal is to organize public data, manually imported data, interpretable player ratings, match predictions, and visual reports into a reproducible research pipeline. 

The current focus is not on accumulating more web scrapers, but on upgrading the rating system into an interpretable and evaluable scouting tool: fixing true impact labels and training targets first, followed by integrating event action values, football-specific visualizations, and model cards.

### 🚀 Core Capabilities
* **Pipeline:** End-to-end `ingest` -> `build-features` -> `train`.
* **Data Validation:** Run `scoutlab validate` to ensure data integrity.
* **Local Data Layer:** Powered by DuckDB + Parquet, structured into raw/silver/gold/models/reports/logs layers.
* **Player Ratings:** PyTorch-based weight optimizer with holdout evaluation, Pearson fixes, availability caps, quality caps, robust team pooling, and coverage reports.
* **Truth Label Contracts:** Schema and validation for `player_truth_labels.parquet`, supporting transfermarkt value, awards, expert tiers, and manual calibration.
* **Model Evaluation & Cards:** Maintain data sources, label definitions, bounds, and known biases in `MODEL_CARD.md`.
* **Product & Visuals:** 8-page Streamlit MVP and FastAPI draft backend featuring Player Rankings, Value Deviation, and Match Prediction (Independent Poisson baseline).
* **Advanced Metrics:** Support for Position Metrics, Finishing Shrinkage (Empirical Bayes), and Action Value prototypes. Visualization powered by `mplsoccer`.

### 📂 Local Data Overview
* **FBref:** 14,356 rows per table across 5 seasons.
* **Football-Data:** 68,953 matches across 10 seasons / 20 divisions. 
* **Understat:** 31,902 player-season records.
* **StatsBomb Open Data:** 126 big-5 matches, 11,871 events cached locally.

### 🏗 Architecture
The long-term roadmap spans 10 layers, starting with Data & Compliance, Standard Facts, and Action Value, all the way to Scout Decision workflows and Spatial/Video Research.

### 🏃 Quick Start

```bash
uv sync

# Project Info
PYTHONPATH=src uv run python -m scoutlab info

# Run Pipeline
PYTHONPATH=src uv run python -m scoutlab ingest
PYTHONPATH=src uv run python -m scoutlab build-features
PYTHONPATH=src uv run python -m scoutlab train

# Local UI
uv run streamlit run src/scoutlab/app/streamlit_app.py
```

<br>

---

<br>

<a id="-简体中文"></a>
## 🇨🇳 简体中文

### 🌟 概览

ScoutLab 是本地优先的足球数据研究平台，目标是把公开数据、手动导入数据、可解释球员评分、比赛预测和可视化报告组织成一条可复现的研究流水线。

当前重点不是继续堆爬虫，而是把评分系统升级为可解释、可评估的球探工具：先修真实影响力标签和训练目标，再接入事件动作价值、足球专用可视化和模型卡。

### 🚀 核心能力

- **研发流水线 (Pipeline):** `ingest` -> `build-features` -> `train`。
- **数据验证:** 执行 `scoutlab validate` 确保数据一致性。
- **本地数据层:** 采用 DuckDB + Parquet，按 raw/silver/gold/models/reports/logs 分层。
- **球员评分:** PyTorch 权重优化器，已加入 holdout 评估、Pearson 修复、availability cap、ST/W quality cap、稳健球队聚合与覆盖率过滤。
- **真实标签契约:** `player_truth_labels.parquet` schema 与校验（`truth_labels.py`），支持四种标签源：历史身价、奖项、专家分档、人工校准。
- **评分模型卡:** `MODEL_CARD.md` 记录数据源、标签定义、适用边界、已知偏差和不可用场景。
- **比分预测与身价:** 包含 Independent Poisson baseline 预测，以及 OOF 的实际预测身价偏离榜。
- **产品与可视化:** Streamlit 多页 MVP 与 FastAPI 入口。集成 mplsoccer 绘制球员雷达 (Pizza chart)、热力图等，同时针对低覆盖与样本不足包含醒目提示。

### 📂 本地数据概览

| 数据源 | 当前缓存 | 覆盖 |
| --- | --- | --- |
| **FBref** | 每表 14,356 行 | 5 赛季标准、射门与 Misc 数据 |
| **Football-Data** | 68,953 行 | 10 赛季，20 个联赛/级别 |
| **Understat** | 31,902 行 | 10 赛季球员统计 |
| **StatsBomb Open Data** | 126 场 / 11,871 事件 | 公开比赛与事件样本库 |
| **内部特征层** | 27,254 评分 / 8,141 特征 | 落表为优化后评分与特征缺失兜底矩阵 |

> **提示：** `FBref`, `WhoScored`, `SofaScore`, `Capology` 的抓取脚本需在带 Chrome + Selenium 的环境中运行。`API-Football` 需配置环境变量 `API_FOOTBALL_KEY`。

### 🏗 顶层架构

ScoutLab 的长期路线扩展为 **10 层**。前 7 层是当前主干，第 8-10 层将在核心层稳定后建设：
1. **数据与合规层:** 缓存、清洗、合并源。
2. **标准事实层:** 统一实体 (比赛、球员、事件)。
3. **跨供应商标准化层:** 兼容 SPADL、kloppy/floodlight。
4. **事件动作价值层:** xT -> VAEP。
5. **球员真值与评分层:** 融入模型卡、真实标签与赛季统计。
6. **评估与报告层:** baseline 与误差分析体系。
7. **产品可视化与 API 层:** FastAPI, Streamlit, mplsoccer。
8. **球探决策层:** Watchlist、专家队列审阅。
9. **比分预测与概率校准层:** Dixon-Coles + Time decay。
10. **空间/视频/离球研究层:** StatsBomb 360 与 Tracking 解析。

### 📸 截图展示

| 球员雷达/排名 | 身价偏离榜 | 比赛预测 |
| :---: | :---: | :---: |
| ![球员雷达](screenshots/player_radar.png) | ![身价偏离](screenshots/value_deviation.png) | ![比赛预测](screenshots/match_prediction.png) |

| Top 100 榜单 | 球员详情页 |
| :---: | :---: |
| ![Top 100](screenshots/top100.png) | ![球员详情](screenshots/player_detail.png) |

### 🛠 如何复现 Demo 

以下步骤在 macOS/Linux 环境下适用：

```bash
# 1. 克隆与依赖
git clone <repo-url> && cd scoutlab
uv sync

# 2. 环境变量 (按需配置)
export API_FOOTBALL_KEY=your_key_here
export SOCCERDATA_DIR=./data/soccerdata

# 3. 运行执行流
PYTHONPATH=src uv run python -m scoutlab ingest
PYTHONPATH=src uv run python -m scoutlab build-features
PYTHONPATH=src uv run python -m scoutlab train

# 4. 数据检查与看板启动
PYTHONPATH=src uv run python -m scoutlab validate
uv run streamlit run src/scoutlab/app/streamlit_app.py
```

### 🔰 技术栈与合规边界

*   **Stack:** Python, uv, DuckDB + Parquet, pandas, scikit-learn, Streamlit, Plotly, mplsoccer, FastAPI, PyTorch.
*   **合规准则:**
    *   绝不绕过验证码或进行恶意高频反爬。
    *   外部商用数据源（如 Transfermarkt）仅支持手动或受权导入。
    *   利用公开事件样本数据衍生的任何公开展现，必须显著标明数据源出处 (如 StatsBomb Open Data)。

---
*Developed with ❤️ and data by ScoutLab.*
