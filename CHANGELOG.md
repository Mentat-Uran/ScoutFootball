# Changelog

All notable changes to ScoutFootball will be documented in this file.

## [1.0.0] - 2026-06-11

### Highlights

First stable release of ScoutFootball — a local-first football analytics platform for the 2026 FIFA World Cup.

### Core Pipeline

- End-to-end data pipeline: `ingest` → `build-features` → `train`
- Five data sources: FBref, Football-Data, Understat, StatsBomb Open Data, Club Elo
- Data validation: `scoutfootball validate` checks integrity before training
- DuckDB + Parquet storage with raw/silver/gold/models/reports/logs layering

### Player Ratings

- PyTorch GPU optimizer with composite objective (Spearman + soft NDCG@20 + position consistency + train-fitted points/league calibration + distribution/tail/league-bias losses + player-score guardrails + optional player truth-label anchor)
- Holdout evaluation with 3-fold CV (Spearman=0.706 on 2526 holdout)
- Position-specific weights for 8 positions (GK/CB/FB/DM/CM/AM/W/ST)
- Availability caps (0.18-0.20) preventing attendance-driven gaming
- Robust team aggregation (capped minutes + core rotation)
- Coverage confidence gates (HIGH/MEDIUM/LOW)
- Finishing shrinkage (empirical Bayes, K=50)
- Truth label schema and validation (`player_truth_labels.parquet`)
- Rating feature matrix with missing-field flags and position-median fallback
- Neural network candidate entry (`scoutfootball train-rating-nn`)

### Match Prediction

- Independent Poisson baseline with attack-defense parameters
- Dixon-Coles (1997) bivariate Poisson with low-score tau correction
- Time decay weighting (configurable half-life)
- Rolling backtest framework with time-series cross-validation
- Calibration metrics: log loss, Brier score, RPS, low-score analysis

### Frontend (Liquid Glass)

- 14-view static analysis workbench with geometric Unicode icon system
- 7 analysis views: Overview, Players, Value, Matches, Scouting, Action Values, Reports
- 4 World Cup views: Schedule, Squads, Compare, Probability
- Electronic tactical board with 15 object types, 12 formations, 6 pitch types
- Animation system: step-based, Bezier paths, ghost silhouettes, trails
- Export: PNG, PDF (print), WebM animation, MP4 (via backend ffmpeg)
- Set-piece templates, training drills, coaching points, teaching mode
- Security: HTML escaping, CSV formula injection guard, CSP meta tag, SRI, schema sanitizer

### Streamlit Console

- 15-page workbench with artifact overview, player rankings, value deviation, match prediction, scouting queue, action value samples, and World Cup pages
- Dixon-Coles vs Poisson model comparison
- Calibration visualization with Brier decomposition

### API

- FastAPI read-only backend with 20+ endpoints
- Player profiles, rating snapshots, match predictions, review queue, watchlist, shortlist
- Action value samples, model run registry, World Cup data
- License attribution and data source manifest
- CORS configurable via environment variable

### Action Value (StatsBomb)

- StatsBomb events → InternalAction (SPADL-compatible) → xT pipeline
- 12 standardized action types with 0-100 normalized coordinates
- Player xT rankings, team xT heatmaps
- StatsBomb Open Data attribution in all exports

### Scouting Workflow

- Review queue with auto-detection of low-confidence, low-appearance, role-remap, weak-coverage players
- Watchlist and shortlist with review status flow
- Watchlist diff between rating snapshots
- CSV export from all scouting views

### Documentation

- README with English/Chinese bilingual sections
- MODEL_CARD.md: data sources, label definitions, known biases, unavailable scenarios
- ALGORITHM.md: rating formula, position weights, league coefficients, Dixon-Coles
- DATA_CONTRACTS.md: all Parquet schemas, API contracts, cross-provider schema reference, socceraction evaluation
- EVALUATION.md: baselines, metrics, error analysis

### Testing

- 570 unit tests across 37 test files
- Coverage: action value schema, calibration, match prediction, backtests, scouting queue, cross-provider schema, frontend security, rating regression, position metrics, and more

### Known Limitations

See `docs/MODEL_CARD.md` and the "Known Limitations" section in README for details.

- Player truth labels are empty; supervised training paths skip by default
- Action value metrics are StatsBomb sample only (not full league coverage)
- World Cup views contain demo/sample data pending official squad rosters
- Rating system is still in calibration phase; strong teams may be systematically undervalued
- FBref data limited to 5 seasons; coarse position mapping needs StatsBomb/formation data to improve
