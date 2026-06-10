# ScoutFootball for World Cup

> **Your local-first football analytics toolkit for the 2026 FIFA World Cup.**
>
> **面向 2026 美加墨世界杯的本地优先足球分析工具箱。**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![uv](https://img.shields.io/badge/uv-Fast-magenta)](https://github.com/astral-sh/uv)
[![DuckDB](https://img.shields.io/badge/DuckDB-Fast%20Analytics-yellow)](https://duckdb.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-Optimized-ee4c2c)](https://pytorch.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B)](https://streamlit.io/)

**[English](#english)** | **[中文](#简体中文)**

---

<a id="english"></a>
## English

### The 2026 World Cup Is Coming

The 2026 FIFA World Cup kicks off June 11 across the US, Canada, and Mexico — 48 teams, 104 matches, one trophy. ScoutFootball for World Cup is built to help you make sense of it all: who's overperforming, who's flying under the radar, and what the numbers say about every squad.

### What It Does

ScoutFootball is a local-first football analytics platform that turns public data, manual imports, interpretable player ratings, and match predictions into a reproducible research pipeline.

The focus right now: upgrading the rating system into an interpretable, evaluable scouting tool — fixing true impact labels and training targets first, then integrating event action values, football-specific visualizations, and model cards.

### Core Capabilities

- **Pipeline:** End-to-end `ingest` -> `build-features` -> `train`.
- **Data Validation:** `scoutfootball validate` checks data integrity before training.
- **Local Data Layer:** DuckDB + Parquet, organized into raw/silver/gold/models/reports/logs.
- **Player Ratings:** PyTorch optimizer with composite objective (Spearman + soft NDCG@20 + position consistency + train-fitted points/league calibration + distribution/tail/league-bias losses + player-score guardrails + optional player truth-label anchor), holdout evaluation, availability caps, quality caps, robust team pooling, coverage reports, and model run registry.
- **Truth Label Contracts:** Schema and validation for `player_truth_labels.parquet` — transfermarkt value, awards, expert tiers, manual calibration. The current local truth-label table is still empty, so supervised player-level training paths skip by design.
- **Neural Rating Candidate:** `scoutfootball train-rating-nn` trains a supervised sklearn MLP candidate from `rating_feature_matrix.parquet` + `player_truth_labels.parquet` and writes artifacts to `data/models/player_rating_nn/`; it does not replace `player_ratings_optimized.parquet` unless it beats the current optimizer on the same holdout and baseline checks.
- **Model Evaluation & Cards:** Data sources, label definitions, bounds, and known biases documented in `docs/MODEL_CARD.md`.
- **Match Prediction:** Independent Poisson baseline with score probability matrices.
- **Product & Visuals:** 15-page Streamlit console with artifact overview, scouting queue, and action-value sample pages. Liquid Glass static frontend with 7 analysis views (Overview, Players, Value, Matches, Scouting, Action Values, Reports) and 4 World Cup views (Schedule, Squads, Compare, Probability). FastAPI read-only backend for artifacts, player profiles, rating snapshots, predictions, review queue, watchlist, shortlist, action-value samples, and model runs. `mplsoccer` powers pitch plots, pizza charts, and shot maps. A browser-based electronic tactical board is planned, not implemented yet.

### Liquid Glass Frontend

The `frontend/` directory contains a static analysis workbench with a consistent geometric icon system (no emojis). All navigation icons use minimal Unicode symbols (◎ ◇ € △ □ ⌁ ▣ ⬡ ⊕ ⟷ ⊞) for visual consistency.

**7 Analysis Views:**

| View | Description | Data Source |
| --- | --- | --- |
| **Overview** (◎) | Artifact registry, data health, coverage metrics | `/artifacts` API |
| **Players** (◇) | Player pool, radar charts, position percentiles | `/ratings`, `/players/{name}` API |
| **Value** (€) | Value deviation scatter, over/under-valued rankings | `/value-summary` API |
| **Matches** (△) | Match prediction, score probability matrix | `/predictions/{home}/{away}` API |
| **Scouting** (□) | Review queue, watchlist, shortlist | `/review-queue`, `/watchlist`, `/shortlist` API |
| **Actions** (⌁) | StatsBomb action value heatmaps | `/action-values` API |
| **Reports** (▣) | Model runs, backend contracts, metrics | `/reports/model-runs` API |

**4 World Cup Views:**

| View | Description |
| --- | --- |
| **Schedule** (⬡) | Group stage fixtures, team groups, venues |
| **Squads** (⊕) | Team rosters with club, league, rating, confidence |
| **Compare** (⟷) | Head-to-head team comparison with radar overlay |
| **Probability** (⊞) | Group advancement probabilities, 48-team strength ranking |

### Demo Data

The frontend falls back to built-in demo data when the FastAPI backend is unavailable or when specific artifacts are missing. Views using demo data display a **DEMO** badge.

To see real data:

```bash
# 1. Start the FastAPI backend (serves local Parquet/DuckDB artifacts)
PYTHONPATH=src uv run python -m scoutfootball serve

# 2. In another terminal, start the frontend
python3 -m http.server 8600 --directory frontend

# 3. Open http://localhost:8600 in your browser
```

To generate the rating artifacts the frontend reads:

```bash
uv sync
PYTHONPATH=src uv run python -m scoutfootball ingest
PYTHONPATH=src uv run python -m scoutfootball build-features
PYTHONPATH=src uv run python -m scoutfootball train

# Optional supervised NN candidate; skips until player_truth_labels has enough rows
PYTHONPATH=src uv run python -m scoutfootball train-rating-nn
```

### World Cup Readiness

| Feature | Status |
| --- | --- |
| 48-team squad rating coverage | In progress — current data covers Big 5 leagues; World Cup squads need additional league data |
| Match prediction (Independent Poisson) | Working baseline |
| Player radar / pizza chart | Available via mplsoccer |
| Position-relative rankings | Available with confidence badges |
| Score probability matrix | Available in Streamlit |
| Electronic tactical board | Planned (P1.5) — local board, animation timeline, PNG/PDF/WebM export first |
| Dixon-Coles with time decay | Planned (P5) |

### Planned Electronic Tactical Board

The tactical board is planned as a local-first coaching and analysis workspace inside `frontend/`, aligned with products such as [Tactico](https://tactico.pro/), [DrawTactics](https://drawtactics.com/animated-tactics-board), [TacticSlate](https://tacticslate.com/football-tactic-board), [JLA Tactics Board](https://jlatacticsboard.com/), [Metrica Tactical Boards](https://www.metrica-sports.com/help-center/tactical-boards), and [TacticalBoards](https://tacticalboards.com/). It should support static diagrams, formation presets, draggable players and ball, arrows, zones, labels, movement trails, keyframe or step-based animation, presentation playback, and export.

Initial scope stays lightweight: local JSON projects, normalized pitch coordinates, browser playback, PNG/PDF still export, WebM animation export via the browser, and report embedding. MP4 export through local ffmpeg, video telestration, tracking-data import, and 3D/behind-goal views are later extensions after the canvas model, data contract, and attribution rules are stable.

### Local Data Overview

| Source | Cache | Coverage |
| --- | --- | --- |
| **FBref** | 14,356 rows per table | 5 seasons, standard/shooting/misc |
| **Football-Data** | 68,953 raw CSV rows | 10 seasons, 20 divisions |
| **Understat** | 31,902 player-season rows | 10 seasons, 6 leagues |
| **StatsBomb Open Data** | 126 matches / 11,871 events | Public match & event sample |
| **Ratings** | 30,483 rows | Optimized player ratings |
| **Feature Matrix** | 8,141 rows | With missing-field flags and position-median fallback |

### Architecture

10-layer roadmap. Layers 1-7 are the current trunk; 8-10 expand into scouting workflows, prediction calibration, and spatial/video research:

1. **Data & Compliance** — caching, cleaning, merging
2. **Standard Facts** — unified entities (matches, players, events)
3. **Cross-Provider Standardization** — SPADL, kloppy/floodlight compatibility
4. **Event Action Value** — xT -> VAEP
5. **Player Truth & Rating** — model cards, truth labels, season stats
6. **Evaluation & Reporting** — baselines, error analysis
7. **Product & API** — FastAPI, Streamlit, mplsoccer, electronic tactical board
8. **Scout Decision** — watchlist, expert review queue, tactical notes
9. **Score Prediction & Calibration** — Dixon-Coles + time decay
10. **Spatial/Video/Off-Ball** — StatsBomb 360, tracking, xG+

### Quick Start

```bash
uv sync

# Project info
PYTHONPATH=src uv run python -m scoutfootball info

# Run pipeline
PYTHONPATH=src uv run python -m scoutfootball ingest
PYTHONPATH=src uv run python -m scoutfootball build-features
PYTHONPATH=src uv run python -m scoutfootball train

# Validate data
PYTHONPATH=src uv run python -m scoutfootball validate

# Streamlit dashboard
uv run streamlit run src/scoutfootball/app/streamlit_app.py

# FastAPI read-only backend
PYTHONPATH=src uv run python -m scoutfootball serve

# Liquid Glass frontend
python3 -m http.server 8600 --directory frontend
```

### Tech Stack & Compliance

- **Stack:** Python, uv, DuckDB + Parquet, pandas, scikit-learn, Streamlit, Plotly, mplsoccer, FastAPI, PyTorch.
- **Compliance:**
  - No CAPTCHA bypass or aggressive scraping.
  - Commercial sources (Transfermarkt etc.) only via manual or authorized import.
  - Public StatsBomb Open Data derivatives must attribute the source.

---

<a id="简体中文"></a>
## 简体中文

### 2026 世界杯来了

2026 美加墨世界杯 6 月 11 日开赛，48 支球队、104 场比赛、一座奖杯。ScoutFootball for World Cup 帮你看懂数据：谁在超常发挥、谁被低估、每支球队的数字画像。

### 它做什么

ScoutFootball 是本地优先的足球分析平台，把公开数据、手动导入、可解释球员评分和比赛预测组织成可复现的研究流水线。

当前重点：把评分系统升级为可解释、可评估的球探工具——先修真实影响力标签和训练目标，再接入事件动作价值、足球专用可视化和模型卡。

### 核心能力

- **研发流水线:** `ingest` -> `build-features` -> `train`。
- **数据验证:** `scoutfootball validate` 检查训练前数据一致性。
- **本地数据层:** DuckDB + Parquet，按 raw/silver/gold/models/reports/logs 分层。
- **球员评分:** PyTorch 权重优化器，组合目标（Spearman + soft NDCG@20 + 位置内一致性 + 训练集积分/联赛校准 + 分布/尾部/联赛偏差损失 + 球员评分 guardrail + 可选球员真值标签锚定），holdout 评估、availability cap、quality cap、稳健球队聚合、覆盖率过滤和模型运行登记。
- **真实标签契约:** `player_truth_labels.parquet` schema 与校验，支持历史身价、奖项、专家分档、人工校准。当前本地真值标签表仍为空，因此监督式球员层训练路径会按设计跳过。
- **神经网络候选模型:** `scoutfootball train-rating-nn` 使用 `rating_feature_matrix.parquet` + `player_truth_labels.parquet` 训练监督式 sklearn MLP 候选模型，并写入 `data/models/player_rating_nn/`；除非同切分下优于当前优化器和 baseline，否则不替换 `player_ratings_optimized.parquet`。
- **评分模型卡:** `MODEL_CARD.md` 记录数据源、标签定义、适用边界和已知偏差。
- **比分预测:** Independent Poisson baseline，含比分概率矩阵。
- **产品与可视化:** 15 页 Streamlit 工作台（含产物总览页、球探队列页和动作价值样本页）。Liquid Glass 静态前端含 7 个分析视图（总览、球员、身价、预测、球探、动作价值、报告）和 4 个世界杯视图（赛程、名单、对比、出线）。面向 artifact、球员画像、评分快照、预测、复核队列、watchlist、shortlist、动作价值样本和模型运行的 FastAPI 只读入口。集成 mplsoccer 绘制球员雷达、pizza chart、shot map。低覆盖和样本不足有醒目提示。电子战术板已纳入规划，尚未实现。

### Liquid Glass 前端

`frontend/` 目录包含静态分析工作台，采用统一的几何图标系统（无 emoji）。所有导航图标使用最小化 Unicode 符号（◎ ◇ € △ □ ⌁ ▣ ⬡ ⊕ ⟷ ⊞），保持视觉一致性。

**7 个分析视图：**

| 视图 | 说明 | 数据来源 |
| --- | --- | --- |
| **总览** (◎) | 产物注册表、数据健康、覆盖指标 | `/artifacts` API |
| **球员** (◇) | 球员池、雷达图、位置内百分位 | `/ratings`、`/players/{name}` API |
| **身价** (€) | 身价偏离散点图、高估/低估排名 | `/value-summary` API |
| **预测** (△) | 比赛预测、比分概率矩阵 | `/predictions/{home}/{away}` API |
| **球探** (□) | 复核队列、watchlist、shortlist | `/review-queue`、`/watchlist`、`/shortlist` API |
| **动作价值** (⌁) | StatsBomb 动作价值热区 | `/action-values` API |
| **报告** (▣) | 模型运行记录、后端契约、指标 | `/reports/model-runs` API |

**4 个世界杯视图：**

| 视图 | 说明 |
| --- | --- |
| **赛程** (⬡) | 小组赛赛程、分组、场馆 |
| **名单** (⊕) | 球队阵容含俱乐部、联赛、评分、置信度 |
| **对比** (⟷) | 两队实力对比含雷达叠加 |
| **出线** (⊞) | 小组出线概率、48 队实力排名 |

### Demo 数据

当 FastAPI 后端不可用或特定产物缺失时，前端会回退到内置 demo 数据。使用 demo 数据的视图会显示 **DEMO** 标记。

查看真实数据：

```bash
# 1. 启动 FastAPI 后端（提供本地 Parquet/DuckDB 产物）
PYTHONPATH=src uv run python -m scoutfootball serve

# 2. 在另一个终端启动前端
python3 -m http.server 8600 --directory frontend

# 3. 浏览器打开 http://localhost:8600
```

生成前端读取的评分产物：

```bash
uv sync
PYTHONPATH=src uv run python -m scoutfootball ingest
PYTHONPATH=src uv run python -m scoutfootball build-features
PYTHONPATH=src uv run python -m scoutfootball train

# 可选监督式 NN 候选；player_truth_labels 行数不足时会跳过
PYTHONPATH=src uv run python -m scoutfootball train-rating-nn
```

### 世界杯准备度

| 功能 | 状态 |
| --- | --- |
| 48 队阵容评分覆盖 | 进行中 — 当前覆盖五大联赛，世界杯阵容需补充更多联赛数据 |
| 比赛预测 (Independent Poisson) | 基线可用 |
| 球员雷达 / Pizza chart | 已集成 mplsoccer |
| 位置内排名 | 可用，带置信度标记 |
| 比分概率矩阵 | Streamlit 可用 |
| 电子战术板 | 计划中 (P1.5) — 先做本地战术板、动画时间轴、PNG/PDF/WebM 导出 |
| Dixon-Coles + 时间衰减 | 计划中 (P5) |

### 规划中的电子战术板

电子战术板计划作为 `frontend/` 内的本地优先教练和分析工作台建设，参考 [Tactico](https://tactico.pro/)、[DrawTactics](https://drawtactics.com/animated-tactics-board)、[TacticSlate](https://tacticslate.com/football-tactic-board)、[JLA Tactics Board](https://jlatacticsboard.com/)、[Metrica Tactical Boards](https://www.metrica-sports.com/help-center/tactical-boards) 和 [TacticalBoards](https://tacticalboards.com/) 等案例。核心能力包括静态战术图、阵型预设、球员和足球拖拽、箭头、区域、标签、跑动轨迹、关键帧或步骤式动画、演示播放和导出。

第一阶段保持轻量：本地 JSON 工程、标准化球场坐标、浏览器播放、PNG/PDF 静态导出、浏览器 WebM 动画导出，以及嵌入报告。MP4 导出、本地 ffmpeg、视频叠画、tracking 数据导入、3D 和门后视角放到后续阶段，等画布模型、数据契约和引用边界稳定后再做。

### 本地数据概览

| 数据源 | 当前缓存 | 覆盖 |
| --- | --- | --- |
| **FBref** | 每表 14,356 行 | 5 赛季标准、射门与 Misc 数据 |
| **Football-Data** | 原始 CSV 68,953 行 | 10 赛季，20 个联赛/级别 |
| **Understat** | 31,902 行 | 10 赛季球员统计 |
| **StatsBomb Open Data** | 126 场 / 11,871 事件 | 公开比赛与事件样本 |
| **评分** | 30,483 行 | 优化后球员评分 |
| **特征矩阵** | 8,141 行 | 含缺失字段标记与位置中位数兜底 |

### 顶层架构

10 层路线图，前 7 层是当前主干，第 8-10 层在核心层稳定后建设：

1. **数据与合规层** — 缓存、清洗、合并
2. **标准事实层** — 统一实体（比赛、球员、事件）
3. **跨供应商标准化层** — 兼容 SPADL、kloppy/floodlight
4. **事件动作价值层** — xT -> VAEP
5. **球员真值与评分层** — 模型卡、真实标签、赛季统计
6. **评估与报告层** — baseline 与误差分析
7. **产品可视化与 API 层** — FastAPI、Streamlit、mplsoccer、电子战术板
8. **球探决策层** — Watchlist、专家队列审阅、战术备注
9. **比分预测与概率校准层** — Dixon-Coles + 时间衰减
10. **空间/视频/离球研究层** — StatsBomb 360、Tracking 解析

### 快速开始

```bash
uv sync

# 项目信息
PYTHONPATH=src uv run python -m scoutfootball info

# 运行流水线
PYTHONPATH=src uv run python -m scoutfootball ingest
PYTHONPATH=src uv run python -m scoutfootball build-features
PYTHONPATH=src uv run python -m scoutfootball train

# 数据验证
PYTHONPATH=src uv run python -m scoutfootball validate

# Streamlit 看板
uv run streamlit run src/scoutfootball/app/streamlit_app.py

# FastAPI 只读后端
PYTHONPATH=src uv run python -m scoutfootball serve

# Liquid Glass 前端
python3 -m http.server 8600 --directory frontend
```

### 技术栈与合规

- **技术栈:** Python, uv, DuckDB + Parquet, pandas, scikit-learn, Streamlit, Plotly, mplsoccer, FastAPI, PyTorch.
- **合规准则:**
  - 不绕验证码，不恶意高频爬取。
  - 商用数据源（如 Transfermarkt）仅支持手动或授权导入。
  - 公开 StatsBomb Open Data 衍生产物必须标明数据来源。

---
*ScoutFootball for World Cup — built for the beautiful game's biggest stage.*
