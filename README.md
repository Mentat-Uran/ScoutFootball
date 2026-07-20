# ScoutFootball for World Cup

## Optional demo reference

https://scoutfootball.vercel.app/ — this URL is an optional historical deployment target, not the primary product mode and not a guarantee that the current commit or backend is reachable. Core use is local and does not depend on this URL. Verify the version, access policy, `/health`, and a real data request before calling any online demo live.

> **Verified 2026-07-17:** Vercel frontend is reachable; Render backend is on free tier (cold start 60–90s), `/health` did not fully pass within the timeout. Not marked as live.

> **A local-first, open-source, personally maintained, non-profit football analytics toolkit.**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![uv](https://img.shields.io/badge/uv-Fast-magenta)](https://github.com/astral-sh/uv)
[![DuckDB](https://img.shields.io/badge/DuckDB-Fast%20Analytics-yellow)](https://duckdb.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-Optimized-ee4c2c)](https://pytorch.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B)](https://streamlit.io/)

**English** | **[Chinese](docs/README_ZH.md)**

---

### The 2026 World Cup Is Coming

The 2026 FIFA World Cup kicks off June 11 across the US, Canada, and Mexico — 48 teams, 104 matches, one trophy. ScoutFootball for World Cup is built to help you make sense of it all: who's overperforming, who's flying under the radar, and what the numbers say about every squad.

### What It Does

ScoutFootball is a local-first, open-source, personally maintained, non-profit football analytics and research project. It turns public data, lawful manual imports, interpretable player ratings, and match predictions into reproducible workflows that run primarily on the user's own machine.

It is not being developed as a SaaS, paid product, enterprise platform, or data marketplace. The code and documentation are available under the repository's MIT License; third-party data and video remain subject to their own licenses. The canonical positioning and decision rules are in [`docs/PROJECT_CHARTER.md`](docs/PROJECT_CHARTER.md).

The World Cup is the first reference pack, not the permanent boundary of the core platform; the same evidence and workflow contracts are intended to support recruitment and match preparation beyond one tournament.

The focus now is to turn the broad prototype into three trustworthy, repeatable workflows: scouting decisions, match preparation, and data/model releases. Source licenses, snapshots, identity review, contracts, browser E2E, and fail-closed releases take priority over adding more top-level pages or model complexity.

### Strategy and verified scope

- [`docs/PROJECT_CHARTER.md`](docs/PROJECT_CHARTER.md) defines the local, open, personal, non-profit project identity and takes precedence over other planning documents.
- [`docs/CAPABILITIES.md`](docs/CAPABILITIES.md) separates shipped, partial, sample, browser/local-only, planned, and unverified capabilities.
- [`docs/FOOTBALL_TOOLING_LANDSCAPE_2026.md`](docs/FOOTBALL_TOOLING_LANDSCAPE_2026.md) maps the 2026 commercial and open tooling landscape as technical context, not as a monetization or market-entry plan.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) defines a dependency-gated long-term development order without calendar deadlines; [`docs/TASKS.md`](docs/TASKS.md) contains the current executable queue.

### Core Capabilities

- **Pipeline:** End-to-end `ingest` -> `build-features` -> `train`.
- **Data Validation:** `scoutfootball validate` checks data integrity before training.
- **Local Data Layer:** DuckDB + Parquet, organized into raw/silver/gold/models/reports/logs.
- **Historical Rating Coverage:** Local Understat aggregate snapshots extend Big Five season-proxy features to historical seasons where FBref is absent. FBref remains authoritative in overlapping seasons; the UI labels both as season-level proxies rather than match events.
- **Player Ratings:** PyTorch optimizer with composite objective (Spearman + soft NDCG@20 + position consistency + train-fitted points/league calibration + distribution/tail/league-bias losses + player-score guardrails + optional player truth-label anchor), holdout evaluation, availability caps, quality caps, robust team pooling, coverage reports, and model run registry.
- **Optimizer Preflight:** `scoutfootball optimizer-preflight --data-dir data` checks required/optional Parquet readability, pandas/PyArrow, and PyTorch without writing model artifacts. Install its optional runtime with `uv sync --extra optimizer`.
- **Truth Label Contracts:** Schema, validation, and a source-policy supervision audit for `player_truth_labels.parquet`. `expert_tier` labels derived from the current optimizer are excluded from NN training and optimizer anchors; source eligibility is still not proof of independent collection. Dated, locally supplied Transfermarkt CSV/Parquet snapshots are resolved against the current rating matrix before import; ambiguous identities stay in a local review report. No Transfermarkt scraping is implemented.
- **Neural Rating Candidate:** `scoutfootball train-rating-nn` trains a supervised sklearn MLP candidate only from supervision-eligible labels in `rating_feature_matrix.parquet` + `player_truth_labels.parquet`, writing provenance and its source-policy audit to `data/models/player_rating_nn/`; it does not replace `player_ratings_optimized.parquet` unless it beats the current optimizer on the same eligible holdout and baseline checks.
- **Model Evaluation & Cards:** Data sources, label definitions, bounds, and known biases documented in `docs/MODEL_CARD.md`.
- **Match Prediction:** Independent Poisson baseline with score probability matrices, plus Football-Data head-to-head history and recent-form comparison with form-trend momentum ratings and offline snapshots.
- **Product & Visuals:** 15-page Streamlit console and a Liquid Glass static workbench with 22 current top-level view targets across core analysis, World Cup, tactical, quality, and governance areas. This breadth is not itself a maturity claim; the exact inventory and boundaries are in `docs/CAPABILITIES.md`. FastAPI serves the corresponding local artifacts and source-bounded World Cup briefings. Scouting projects, decision packs, tactical projects, and several briefing handoffs are browser-local by default, not cloud or multi-user sync. Estimated rosters and tournament outputs are explicitly separate from official live team news.

### Liquid Glass Frontend

The `frontend/` directory contains a static analysis workbench with a consistent geometric icon system (no emojis). All navigation icons use minimal Unicode symbols (◎ ◇ € △ □ ⌁ ▣ ⬡ ⊕ ⟷ ⊞) for visual consistency. API, local Parquet-derived JSON, demo strings, and imported tactical-board project fields are escaped or sanitized before entering HTML.

**Core analysis workflow views (selected; not the full navigation inventory):**

| View | Description | Data Source |
| --- | --- | --- |
| **Overview** (◎) | Artifact registry, data health, coverage metrics | `/artifacts` API |
| **Players** (◇) | Player pool, radar charts, position percentiles, multi-section scouting report export (CSV/JSON) | `/ratings`, `/players/{name}` API |
| **Value** (€) | Value deviation scatter, over/under-valued rankings | `/value-summary` API |
| **Matches** (△) | Match prediction, score probability matrix, head-to-head history, recent form, and form-trend momentum cards | `/predictions/{home}/{away}`, `/predictions/{home}/{away}/h2h` API |
| **Scouting** (□) | Review queue filters, local status/notes, shortlist decision dossiers, versioned workspace import/export, optional conflict-safe local API persistence | `/review-queue`, `/watchlist`, `/shortlist`, `/scouting-workspaces/*` |
| **Actions** (⌁) | xT/VAEP ranking, sample filters, 3-match player→match action evidence, tactical heatmap handoff | `/action-values`, `/action-values/evidence/{player_id}` API |
| **Reports** (▣) | Model runs, backend contracts, metrics | `/reports/model-runs` API |

**World Cup entry views (selected; the current product also includes knockout and tournament views):**

| View | Description |
| --- | --- |
| **Schedule** (⬡) | Group stage fixtures, team groups, venues |
| **Squads** (⊕) | Team rosters with club, league, rating, confidence |
| **Compare** (⟷) | Head-to-head team comparison with radar overlay |
| **Probability** (⊞) | Group advancement probabilities, 48-team strength ranking |

### Deployment target

**https://scoutfootball.vercel.app/** (frontend) · `https://scoutfootball-for-world-cup.onrender.com` (backend, Render free tier)

The project is configured for a Vercel frontend and Render backend. Treat it as live only after checking the deployed version, access policy, `/health`, and a representative API request; local build success is not deployment confirmation.

**Verified 2026-07-17:** Vercel frontend is reachable and returns the full UI; Vercel `/health` returns 404 (expected — the backend is on Render, not Vercel). The Render backend is deployed but on free tier, cold start takes 60–90s, and `/health` did not fully pass within the timeout. Online deployment is not an unlock condition for the local project — the primary use mode is local.

### LAN / Campus Network Deployment

For access from other devices on the same campus network, run the backend on your computer and let it serve both the frontend and API:

```bash
uv sync
uv run python -m scoutfootball serve --host 0.0.0.0 --port 8000
```

Then open `http://YOUR-PC-IP:8000` from another device on the same network.

Windows users can use:

```bat
scripts\start-lan.bat
```

Notes:

- `frontend/` is mounted by FastAPI at `/`, so one port is enough.
- Local/LAN deployments now default to same-origin API mode.
- A plain static server falls back to the tracked JSON snapshot under `frontend/data/` when mapped API routes return 404.
- Allow TCP `8000` through Windows Firewall, or choose another port if needed.

### Optional local scouting workspace persistence

Scouting decisions stay in browser storage by default. To explicitly enable
audited save/load through a backend running on the same machine:

```powershell
$env:SCOUTFOOTBALL_ENABLE_WORKSPACE_WRITES="1"
uv run python -m scoutfootball serve --host 127.0.0.1 --port 8000
```

The API validates the v1.x workspace contract, requires `If-Match` server
revisions for updates, writes atomically, and keeps the previous record as an
immutable backup under `data/reports/scouting/workspaces/backups/`. Non-loopback
access remains denied unless `SCOUTFOOTBALL_ALLOW_REMOTE_WORKSPACE_WRITES=1` is
also set deliberately. This is local persistence, not cloud or multi-user sync.

### Docker Deployment

Build and run the API plus static frontend in one container:

```bash
docker build -t scoutfootball:local .
docker run --rm -p 8000:8000 scoutfootball:local
```

Open `http://localhost:8000` and verify the backend with:

```bash
curl http://localhost:8000/health
```

For local development with your full `data/` directory mounted into the
container:

```bash
docker compose up --build
```

If Docker Hub or apt mirrors are blocked on your local network, override the
build image and skip optional system packages for a smoke test:

```powershell
$env:SCOUTFOOTBALL_PYTHON_IMAGE="mcr.microsoft.com/devcontainers/python:1-3.11-bookworm"
$env:SCOUTFOOTBALL_INSTALL_SYSTEM_PACKAGES="0"
docker compose up --build
```

The container reads `SCOUTFOOTBALL_DATA_ROOT` and defaults it to `/app/data`.
Mounting `./data:/app/data` lets Docker use local Parquet/model artifacts and
write tactical-board exports under `data/reports/tactical_exports/`.

Release builds publish a GHCR image and upload a Docker archive:

```bash
docker pull ghcr.io/mentaturan/scoutfootball_for_world_cup:latest
docker run --rm -p 8000:8000 ghcr.io/mentaturan/scoutfootball_for_world_cup:latest
```

### Static Snapshot Layout

- `frontend/data/` is the tracked release snapshot used by the static demo and refreshed by GitHub Actions.
- `frontend/local-data/` is the ignored local snapshot for ad-hoc exports on your machine.

Local export:

```bash
uv run python scripts/export_static_frontend_data.py
uv run python scripts/compute_worldcup_predictions.py
```

Release export:

```bash
uv run python scripts/export_static_frontend_data.py --profile release
uv run python scripts/compute_worldcup_predictions.py --profile release
```

### Demo Data

The frontend falls back to built-in demo data when the FastAPI backend is unavailable or when specific artifacts are missing. Views using demo data display a **DEMO** badge.

To see real data:

```bash
# FastAPI serves the frontend and local Parquet/DuckDB artifacts on one origin
PYTHONPATH=src uv run python -m scoutfootball serve --host 127.0.0.1 --port 8000

# Open http://127.0.0.1:8000
```

`frontend/config.js` uses same-origin API requests. A separate plain static server is useful for testing STATIC fallback, but it will not call an API on another port unless the configuration is deliberately changed.

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
| Electronic tactical board | Local canvas, animation, PNG/PDF/WebM/GIF export, optional MP4, report snapshots, and schema migration available |
| Dixon-Coles with time decay | Implemented baseline with calibration metrics |

### Current Known Limitations

**Rating System:**
- The 2026-07-16 audit could read the truth-label footer/schema but not the content or `label_source` distribution. Treat the source mix and supervision eligibility as unverified until the locked project runtime completes a content-level source-policy audit; no player-level validation claim should rely on the footer row count.
- Rating system is in calibration phase; strong teams (Barcelona, Real Madrid) may be systematically undervalued
- League intercept bias exists (Serie A -16.6, Ligue 1 -11.3)

**Data Coverage:**
- The action-value aggregate file footer reported 9,951 rows in the 2026-07-16 audit, but the current audit runtime could not fully decode it; treat it as unavailable until the locked project runtime passes content-level validation. The separate match-evidence slice contains only 94 player-match evidence records across 3 matches, not tracking data or full-league coverage.
- FBref data limited to 5 seasons; coarse position mapping needs StatsBomb/formation data
- World Cup squads are populated, but rating coverage remains incomplete outside the major leagues

**Frontend:**
- Frontend falls back to a tracked static snapshot when mapped API routes are unavailable; it is cached data, not live data
- API status pill shows LIVE (API online), STATIC (fallback from snapshot), or OFFLINE (neither available)
- Review queue is paginated at 50 items per page to avoid rendering thousands of cards at once
- Scouting review states, notes, and shortlist dossiers remain browser-local, but they can be moved or backed up with the versioned workspace JSON. Audit metadata records local revisions and timestamps; it is not a server-side identity or cross-device audit service.
- Some VAEP rows only have `player_id`; identity mapping remains incomplete
- Tactical board MP4 export requires ffmpeg installed on the system

**Scope boundaries:**
- Spatial/video analysis (StatsBomb 360, tracking data) remains dependency-gated local research, not a current capability
- Public links, cloud sync, organization accounts, and real-time tactical-board collaboration are outside the current project charter
- Mobile tactical-board editing is optional and must first prove value without increasing single-maintainer complexity

### Electronic Tactical Board

The tactical board is available as a local-first coaching and analysis workspace inside `frontend/`, aligned with products such as [Tactico](https://tactico.pro/), [DrawTactics](https://drawtactics.com/animated-tactics-board), [TacticSlate](https://tacticslate.com/football-tactic-board), [JLA Tactics Board](https://jlatacticsboard.com/), and [Metrica Tactical Boards](https://www.metrica-sports.com/help-center/tactical-boards). It includes normalized pitch coordinates, formations and set pieces, drawing tools, frame/path animation, local JSON projects, schema migration, report snapshots, and PNG/PDF/WebM/GIF export. A pre-match plan saves a versioned decision pack containing the exact loaded prediction, coverage, score matrix, and available local-artifact provenance; when a prediction is unavailable it records `not_loaded` rather than placeholder probabilities. Projects and JSON exports remain browser-local. MP4 remains an optional local-backend capability requiring ffmpeg. Public links, cloud sync, organization accounts, and real-time collaboration are out of scope under the current charter; local video telestration and tracking import remain gated research.

Long-term sequencing and engineering gates are documented in [`docs/ROADMAP.md`](docs/ROADMAP.md). Current work comes only from the top of [`docs/TASKS.md`](docs/TASKS.md); the old P1.5 numbering is historical.

### Desktop App

The repository contains Electron/PyInstaller packaging and a historical macOS arm64 build record. This audit did not reproduce the `.dmg`, signature, installation, auto-update, or release asset, so desktop delivery remains partially verified rather than a current availability promise.

| Feature | Status |
|---|---|
| macOS arm64 (.dmg) | Historical build record; current artifact/signature/install unverified |
| Auto-update via GitHub releases | Code path exists; end-to-end update unverified in this audit |
| System tray | Code path exists |
| Bundled data | Packaging configuration exists; exact current bundle requires release inspection |
| Windows build | Script exists; current artifact/install unverified |

Build from source:

```bash
cd desktop && npm install
bash scripts/build-desktop.sh --mac
```

Expected local output path: `desktop/dist/`; exact versioned asset depends on the build configuration.

### Local Data Overview

README does not maintain volatile cache counts. Use generated data-health reports and [`docs/CAPABILITIES.md`](docs/CAPABILITIES.md). In the 2026-07-16 audit, several Parquet footers were readable but full decoding failed in the available runtime; footer counts are not proof of usable data. The StatsBomb match index, the 3-match event sample, and player-match evidence are different files and grains and must not be combined into one coverage figure.

### Architecture

The target structure is ScoutFootball Core (source/license, snapshot/lineage, identity, contracts, model governance, evidence packages, workspaces, adapters) plus World Cup, Recruitment, Opposition & Match, and later Academy packs. The gated phases and non-goals are maintained only in [`docs/ROADMAP.md`](docs/ROADMAP.md).

### Quick Start

**Prerequisites:** Python 3.11+ and [uv](https://docs.astral.sh/uv/) (fast Python package manager).

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/Mentaturan/ScoutFootball_for_World_Cup.git
cd ScoutFootball_for_World_Cup
uv sync

# Validate and build step by step:
PYTHONPATH=src uv run python -m scoutfootball info      # Project info
PYTHONPATH=src uv run python -m scoutfootball validate   # Validate data
PYTHONPATH=src uv run python -m scoutfootball preflight --target key --evidence-out data/reports/data_health/preflight-evidence.json
PYTHONPATH=src uv run python -m scoutfootball ingest     # Ingest data
PYTHONPATH=src uv run python -m scoutfootball build-features
PYTHONPATH=src uv run python -m scoutfootball train      # Train ratings (fail-closed; --force to bypass validation)

# Start the same-origin web UI and API
PYTHONPATH=src uv run python -m scoutfootball serve --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 for the Liquid Glass frontend, or run Streamlit:

```bash
uv run streamlit run src/scoutfootball/app/streamlit_app.py
```

**First run note:** Some ingestion paths download and cache public data and require an internet connection; others require manual/authorized local inputs. `scripts/demo.sh` is aligned with the same-origin FastAPI setup (port 8000) and includes a `--smoke` health check; it is the canonical local launcher for the demo pipeline.

`preflight --evidence-out` is an explicit local write: it saves the content-level
inspection together with only the source-license, snapshot, and lineage metadata
recorded in the contract registry. It does not upload data, infer missing
provenance, or overwrite an existing evidence file unless
`--overwrite-evidence` is supplied.

For a registered local CSV source that is intentionally outside the Parquet
pipeline, use `inspect-raw-source` before recording a source snapshot. The
inspection is local-only and records structural hashes rather than CSV values:

```powershell
uv run python -m scoutfootball inspect-raw-source --source reep --path raw/reep/people.csv --evidence-out data/reports/data_health/reep-people-inspection.json
uv run python -m scoutfootball record-source-snapshot --source reep --snapshot-date YYYY-MM-DD --evidence data/reports/data_health/reep-people-inspection.json
```

This establishes neither an upstream date nor rights by itself; the date is an
explicit maintainer declaration and source use remains bounded by its contract.

The retained Reep snapshot can also help a maintainer cross-check one exact
Transfermarkt, FBref, or Wikidata identifier before a separate manual identity
review. It reads only the local CSV and never imports Transfermarkt files or
writes a player rating, roster, market value, or truth label:

```powershell
uv run python -m scoutfootball reep-identity-lookup --provider transfermarkt --id <provider-id> --json
```

The result may contain multiple Reep rows. Even one exact match is only an
identity-review aid; it is not a confirmed canonical ScoutFootball player ID.

### Verification safety

`uv run pytest` does not run mutation-capable pipeline integration checks by
default. Feature building and training can write local feature or model
artifacts, so run them only after deliberately choosing the data root:

```powershell
$env:SCOUTFOOTBALL_RUN_MUTATING_PIPELINE_TESTS = "1"
uv run pytest tests/integration/test_pipeline_e2e.py
```

Use a disposable `SCOUTFOOTBALL_DATA_ROOT` for this check when the maintained
local data directory must not be changed.

### Local quality-audit records

`contract-quality` reports identity-resolution and external-source claim error
rates only from an explicitly supplied local audit ledger. It never treats
unreviewed rows, ambiguous identities, or contract presence as correct. Record
one manually reviewed sample in preview mode first:

```powershell
uv run python -m scoutfootball record-quality-audit --audit-kind identity_resolution --source transfermarkt_manual --sample-id "local-review-001" --outcome confirmed_correct --reviewer "maintainer" --evidence-reference "local-review:001" --decision "Reviewed against the permitted local snapshot."
```

Add `--confirm` only after the review. A quality gate can apply only after the
maintainer also records its own error-rate and sample-count threshold:

```powershell
uv run python -m scoutfootball record-quality-threshold --audit-kind identity_resolution --maximum-error-rate 0.05 --minimum-sample-count 40 --decision "Local review threshold for this source scope."
```

Use `--confirm` only after selecting that threshold, then inspect both local ledgers:

```powershell
uv run python -m scoutfootball contract-quality --audit-ledger data/reports/data_health/quality_audit_ledger.jsonl --threshold-ledger data/reports/data_health/quality_threshold_ledger.jsonl
```

The report never derives a threshold: insufficient samples remain
`baseline_required`, and an exceeded recorded threshold fails the relevant check.

### Tech Stack & Compliance

- **Stack:** Python, uv, DuckDB + Parquet, pandas, scikit-learn, Streamlit, Plotly, mplsoccer, FastAPI, PyTorch.
- **Compliance:**
  - No CAPTCHA bypass or aggressive scraping.
  - Commercial sources (Transfermarkt etc.) only via manual or authorized import.
  - Public StatsBomb Open Data derivatives must attribute the source.

---
*ScoutFootball for World Cup — built for the beautiful game's biggest stage.*
