# ⚽️ ScoutLab

> **A local-first football data research platform.**
> 
> **本地优先的足球数据研究平台。**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
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
* **Player Ratings:** PyTorch-based weight optimizer with composite objective (Spearman + NDCG@20 + position consistency + extreme penalty + prior regularization), holdout evaluation, Pearson fixes, availability caps, quality caps, robust team pooling, coverage reports, and model run registry.
* **Truth Label Contracts:** Schema and validation for `player_truth_labels.parquet`, supporting transfermarkt value, awards, expert tiers, and manual calibration.
* **Model Evaluation & Cards:** Maintain data sources, label definitions, bounds, and known biases in `MODEL_CARD.md`.
* **Product & Visuals:** 8-page Streamlit analysis console, a new `frontend/` Liquid Glass static analyst console, and a FastAPI draft backend featuring Player Rankings, Value Deviation, and Match Prediction (Independent Poisson baseline).
* **Advanced Metrics:** Support for Position Metrics, Finishing Shrinkage (Empirical Bayes), and Action Value prototypes. Visualization powered by `mplsoccer`.

### Frontend Product Direction

The current UI should stay a quiet analyst workstation rather than becoming a marketing page. A static Liquid Glass prototype now lives in `frontend/index.html`; long term, the same visual style needs to support:

* Global data/source status, artifact freshness, and confidence badges.
* Player search, ranking, comparison, position-relative profiles, and exportable tables.
* Value deviation analysis with OOF residuals, league/age/position bias checks, and manual market-value import boundaries.
* Match prediction with model comparison, calibration diagnostics, and score probability drill-down.
* Scouting workflow views: review queue, watchlist, shortlist, rating diffs, and low-confidence follow-up.
* Event/action-value visualizations once xT/VAEP artifacts exist.

Backend work should therefore focus on typed read-only service contracts: artifact registry, player profile API, rating snapshot API, value model reports, prediction service/model registry, review queue Parquet contracts, source attribution manifest, and lightweight export/report endpoints. Streamlit should keep reading local artifacts and must not run heavy ingest/training jobs inside page code.

### 📂 Local Data Overview
* **FBref:** 14,356 rows per table across 5 seasons.
* **Football-Data:** 68,953 raw CSV rows across 10 seasons / 20 divisions; the currently active `combined_results.parquet` checked on 2026-06-05 has 5,330 rows and should be rebuilt before claiming full 10-season active coverage.
* **Understat:** 31,902 player-season records.
* **StatsBomb Open Data:** 126 big-5 matches, 11,871 events cached locally.
* **Frontend Artifacts:** `player_match.parquet` 8,689 rows (94 real match rows + 8,595 season proxy rows), `team_match.parquet` 10,660 rows, value-fairness OOF 6,513 rows, and optimized ratings 27,254 rows.

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

# Static Liquid Glass UI
python3 -m http.server 8600 --directory frontend
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
- **球员评分:** PyTorch 权重优化器，组合优化目标（Spearman + NDCG@20 + 位置内一致性 + 极端惩罚 + 先验正则），holdout 评估、availability cap、ST/W quality cap、稳健球队聚合、覆盖率过滤和模型运行登记。
- **真实标签契约:** `player_truth_labels.parquet` schema 与校验（`truth_labels.py`），支持四种标签源：历史身价、奖项、专家分档、人工校准。
- **评分模型卡:** `MODEL_CARD.md` 记录数据源、标签定义、适用边界、已知偏差和不可用场景。
- **比分预测与身价:** 包含 Independent Poisson baseline 预测，以及 OOF 的实际预测身价偏离榜。
- **产品与可视化:** 8 页 Streamlit 分析工作台、`frontend/` 静态 Liquid Glass 工作台与 FastAPI 草案入口。集成 mplsoccer/ECharts 绘制球员雷达、身价散点、比分矩阵、动作价值热区等，同时针对低覆盖、season proxy 和样本不足包含醒目提示。

### 前端长期方向

当前前端的风格应保持安静、密集、分析工具化，不做营销落地页。新的静态原型位于 `frontend/index.html`，保留原 `frontend/` 液态玻璃风格，已覆盖总览、球员、身价、比赛预测、球探、动作价值和报告视图。长远需要在同一套 UI 风格下支撑这些能力：

- 全局数据状态、产物更新时间、真实/代理/合成数据标记和低置信度提示。
- 球员检索、排名、对比、位置内画像、跨位置总榜、详情钻取和表格导出。
- 身价偏离分析：OOF 残差、联赛/年龄/位置偏差、手动导入身价边界和误差案例。
- 比赛预测：模型族对比、概率校准、比分矩阵、Top score drill-down、低覆盖 league-season 提示。
- 球探工作流：review queue、watchlist、shortlist、评分版本 diff、人工校准闭环。
- 事件动作价值：在 xT/VAEP 产物稳定后展示传球、带球、射门和区域价值图。
- 报告和导出：按模型运行、球员、球队、联赛生成只读报告快照。

对应后端优先补齐：本地产物 registry、球员画像 API、评分快照 API、预测服务/model registry、value-fairness 报告、review queue/watchlist Parquet 契约、data source attribution manifest、轻量导出端点。Streamlit 页面继续只读本地产物，不在页面里执行重型 ingest、训练或爬取。

### 📂 本地数据概览

| 数据源 | 当前缓存 | 覆盖 |
| --- | --- | --- |
| **FBref** | 每表 14,356 行 | 5 赛季标准、射门与 Misc 数据 |
| **Football-Data** | 原始 CSV 68,953 行；当前活动 `combined_results.parquet` 5,330 行 | 10 赛季原始缓存，活动 Parquet 待重建完整覆盖 |
| **Understat** | 31,902 行 | 10 赛季球员统计 |
| **StatsBomb Open Data** | 126 场 / 11,871 事件 | 公开比赛与事件样本库 |
| **内部特征层** | 27,254 评分 / 8,141 特征 | 落表为优化后评分与特征缺失兜底矩阵 |
| **前端当前读取** | player_match 8,689 行；team_match 10,660 行；OOF 6,513 行 | `player_match` 当前只有 94 条真实 match-level 行，其余 8,595 行为 season proxy |

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

### 📸 截图计划

截图目录当前尚未落盘。P1 后续需要补 3-5 张可复现截图：球员雷达/排名、身价偏离榜、比赛预测、Top 榜单和球员详情页。截图前必须确认页面顶部数据状态，不把 season proxy 或 demo fallback 误写成完整真实数据。

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

# 5. 静态 Liquid Glass 前端
python3 -m http.server 8600 --directory frontend
```

### 🔰 技术栈与合规边界

*   **Stack:** Python, uv, DuckDB + Parquet, pandas, scikit-learn, Streamlit, Plotly, mplsoccer, FastAPI, PyTorch.
*   **合规准则:**
    *   绝不绕过验证码或进行恶意高频反爬。
    *   外部商用数据源（如 Transfermarkt）仅支持手动或受权导入。
    *   利用公开事件样本数据衍生的任何公开展现，必须显著标明数据源出处 (如 StatsBomb Open Data)。

---
*Developed with ❤️ and data by ScoutLab.*
