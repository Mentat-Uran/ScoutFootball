# ScoutFootball for World Cup

> **Your local-first football analytics toolkit for the 2026 FIFA World Cup.**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![uv](https://img.shields.io/badge/uv-Fast-magenta)](https://github.com/astral-sh/uv)
[![DuckDB](https://img.shields.io/badge/DuckDB-Fast%20Analytics-yellow)](https://duckdb.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-Optimized-ee4c2c)](https://pytorch.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B)](https://streamlit.io/)

**English** | **[中文](docs/README_ZH.md)**

---

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
- **Product & Visuals:** 15-page Streamlit console with artifact overview, scouting queue, and action-value sample pages. Liquid Glass static frontend with 7 analysis views (Overview, Players, Value, Matches, Scouting, Action Values, Reports), 4 World Cup views (Schedule, Squads, Compare, Probability), and a first-slice local tactical board. FastAPI read-only backend serves artifacts, player profiles, rating snapshots, predictions, review queue, watchlist, shortlist, action-value samples, and model runs. `mplsoccer` powers pitch plots, pizza charts, and shot maps. Frontend rendering now escapes API/local JSON strings, CSV exports guard against spreadsheet formula injection, and tactical-board JSON imports pass through a schema sanitizer.

### Liquid Glass Frontend

The `frontend/` directory contains a static analysis workbench with a consistent geometric icon system (no emojis). All navigation icons use minimal Unicode symbols (◎ ◇ € △ □ ⌁ ▣ ⬡ ⊕ ⟷ ⊞) for visual consistency. API, local Parquet-derived JSON, demo strings, and imported tactical-board project fields are escaped or sanitized before entering HTML.

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
| Electronic tactical board | First local canvas/JSON slice available; animation timeline, PNG/PDF/WebM export, report embedding, and version migration remain P1.5 work |
| Dixon-Coles with time decay | Planned (P5) |

### Known Limitations (v1.0.0)

**Rating System:**
- Player truth labels are empty; supervised training paths (NN candidate) skip by default
- Rating system is in calibration phase; strong teams (Barcelona, Real Madrid) may be systematically undervalued
- League intercept bias exists (Serie A -16.6, Ligue 1 -11.3)

**Data Coverage:**
- Action value metrics are StatsBomb sample only (3 matches, ~12K events), not full league coverage
- FBref data limited to 5 seasons; coarse position mapping needs StatsBomb/formation data
- World Cup views contain demo/sample data pending official squad rosters

**Frontend:**
- Frontend falls back to built-in demo data when API is unavailable (marked with DEMO badge)
- Tactical board MP4 export requires ffmpeg installed on the system
- GIF export not yet implemented

**Not Included in v1.0:**
- VAEP (planned for future after xT stabilization)
- Spatial/video analysis (StatsBomb 360, tracking data)
- Real-time collaboration on tactical board
- Mobile-optimized tactical board editing

### Electronic Tactical Board

The first tactical-board slice is available as a local-first coaching and analysis workspace inside `frontend/`, aligned with products such as [Tactico](https://tactico.pro/), [DrawTactics](https://drawtactics.com/animated-tactics-board), [TacticSlate](https://tacticslate.com/football-tactic-board), [JLA Tactics Board](https://jlatacticsboard.com/), [Metrica Tactical Boards](https://www.metrica-sports.com/help-center/tactical-boards), and [TacticalBoards](https://tacticalboards.com/). The current slice covers static local canvas work, normalized coordinates, basic objects, formation presets, local JSON projects, localStorage persistence, and schema-sanitized import/export.

Remaining P1.5 scope stays lightweight but broader than simple animation: red/blue teams, editable jersey numbers, player hover cards, whiteboard-style freehand drawing, eraser and line tools, training equipment, set-piece and drill templates, richer team/player project schema, animation timeline, browser playback, PNG/PDF still export, WebM animation export via the browser, report embedding, version migration, and read-only fallback for incompatible projects. MP4 export is available via backend ffmpeg conversion (`/tactical-board/capabilities` and `/tactical-board/export/mp4` endpoints). GIF export, video telestration, tracking-data import, 2D/3D synced views, live collaboration, and behind-goal views are later extensions.

### Desktop App (macOS)

A standalone desktop application is available for macOS (Apple Silicon / arm64). It bundles the Python backend, frontend, and pre-computed data into a single native app with auto-update support.

| Feature | Status |
|---|---|
| macOS arm64 (.dmg) | Built and verified |
| Auto-update via GitHub releases | Implemented (electron-updater) |
| System tray | Implemented |
| Bundled data | Player ratings, match results, models |
| Windows build | Not yet (requires Windows machine) |

Build from source:

```bash
cd desktop && npm install
bash scripts/build-desktop.sh --mac
```

Output: `desktop/dist/ScoutFootball-1.0.0-arm64.dmg`

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

**Prerequisites:** Python 3.11+ and [uv](https://docs.astral.sh/uv/) (fast Python package manager).

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/Mentaturan/ScoutFootball_for_World_Cup.git
cd ScoutFootball_for_World_Cup
uv sync

# One-command demo (validates data, runs pipeline, starts servers)
bash scripts/demo.sh

# Or step by step:
PYTHONPATH=src uv run python -m scoutfootball info      # Project info
PYTHONPATH=src uv run python -m scoutfootball validate   # Validate data
PYTHONPATH=src uv run python -m scoutfootball ingest     # Ingest data
PYTHONPATH=src uv run python -m scoutfootball build-features
PYTHONPATH=src uv run python -m scoutfootball train      # Train ratings

# Start web UI (two terminals)
PYTHONPATH=src uv run python -m scoutfootball serve      # API on :8600
python3 -m http.server 8601 --directory frontend         # Frontend on :8601
```

Open http://localhost:8601 for the Liquid Glass frontend, or run Streamlit:

```bash
uv run streamlit run src/scoutfootball/app/streamlit_app.py
```

**First run note:** The pipeline will download and cache public data on first run. This requires an internet connection. Subsequent runs use local cache.

### Tech Stack & Compliance

- **Stack:** Python, uv, DuckDB + Parquet, pandas, scikit-learn, Streamlit, Plotly, mplsoccer, FastAPI, PyTorch.
- **Compliance:**
  - No CAPTCHA bypass or aggressive scraping.
  - Commercial sources (Transfermarkt etc.) only via manual or authorized import.
  - Public StatsBomb Open Data derivatives must attribute the source.

---
*ScoutFootball for World Cup — built for the beautiful game's biggest stage.*
