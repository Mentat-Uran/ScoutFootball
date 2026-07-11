# Codex Continuous Development State

## Recently Merged

- **Match Prediction Enhancement Suite (2026-07-12):**
  1. **Bootstrap confidence intervals:** `bootstrap_prediction_confidence()` in `match_prediction.py` — resamples fixture-level data with replacement, refits Dixon-Coles per bootstrap sample, collects distributions of home_win/draw/away_win/home_lambda/away_lambda, returns `PredictionConfidenceInterval` with percentile bounds. `_build_bootstrap_fixtures()` helper converts team-match rows to fixture-level for resampling.
  2. **Form-based match weighting:** `compute_form_weights()` computes per-match weights from rolling team form (points per game in preceding N matches). `fit_dixon_coles_with_form()` convenience wrapper applies form weights on top of time-decay. `fit_dixon_coles()` gains `match_weights` parameter for arbitrary per-match weighting.
  3. **Form-weighted prediction API:** `GET /predictions/{home}/{away}?model=form` endpoint via `get_form_weighted_prediction()` — uses form-weighted DC with tuned decay, returns prediction + form_config metadata + confidence intervals. Frontend model selector (Poisson / Dixon-Coles / DC+Form) in matches view.
  4. **Confidence intervals in API + frontend:** DC prediction endpoint now includes `confidence_intervals` field (10-minute TTL cache per team pair, 90% CI, n_bootstrap=50). Frontend renders CI ranges inline with probability bars and as a detailed block in the calibration section (home_win/draw/away_win/home_lambda/away_lambda intervals with n and failed_iterations).
  5. **Team comparison radar enhancement:** Radar chart now uses color-coded area fills (blue vs orange), split area styling, and a dimension difference table below the chart showing per-dimension values, delta with status pills, and edge winner.
  6. **Tests:** 24 new tests (bootstrap CI, form weights, form-weighted DC fit, fixture builder). All pass, ruff + node check clean.
- **Prediction Calibration & Tuning Suite (2026-07-11):**
  1. **Decay grid search:** `tune_dixon_coles_decay()` in `backtests.py` — evaluates 9 decay candidates (0.0 to 0.02) via time-series cross-validation, collects log_loss/brier/rps per candidate, selects best by configurable metric (default: RPS). Returns `DecayTuningResult` with comparison table, per-candidate metrics, and half-life conversions.
  2. **CLI `tune-predictions` command:** `--metric`, `--n-splits`, `--run-backtest` flags. With `--run-backtest`, generates full backtest artifacts (Poisson + DC no-decay + DC best-decay predictions/metrics JSON + isotonic calibration report) using the tuned optimal decay. Shared `_load_team_match_from_raw()` helper extracted to avoid duplication.
  3. **`GET /predictions/tuning` endpoint:** Reads `decay_tuning_results.json`, 5-minute TTL cache, not_available status with instructions when no artifacts. `get_decay_tuning()` in `api.py`.
  4. **Frontend tuning panel:** `_renderDecayTuning()` in backtest view — candidate comparison table with highlighted BEST decay, half-life days, per-metric values, and summary grid (best decay, selection metric, match count). Bilingual i18n.
  5. **Pipeline fix:** `_resolve_dc_decay()` in `pipeline.py` replaces hardcoded `0.005` — reads best decay from tuning results if available, falls back to paper default. Fixes doc-code inconsistency (TASKS.md claimed `half_life_days=180` but code used `decay=0.005`).
  6. **Tests:** 18 new tests (tuning function, API not_available/ok states, pipeline resolver with fallback/invalid/negative cases). All pass, ruff + node check clean.
- **Scouting Intelligence & Player Similarity Suite (2026-07-11):**
  1. **Player similarity search (full stack):** `find_similar_players()` in `api.py` builds a 6-dimensional z-scored feature vector (npg_p90/Attack, assists_p90/Creation, defense_composite/Defense, possession_composite/Possession, optimized_score/Overall, minutes/Availability) and ranks pool players by cosine similarity (clamped to [0,1]). `GET /players/{player_name}/similar` endpoint with `limit`/`season`/`same_position_only` params. Frontend `_fetchAndRenderSimilarPlayers()` panel at the bottom of player profile with color-coded similarity cards, CSV export (formula-injection-safe via `csvCell()`), and click-to-switch-player navigation.
  2. **Truth label feedback loop:** `LabelSource.SCOUTING_REVIEW` enum value added. `workspace_to_truth_labels()` converts a scouting workspace's `review.statuses` (approved→1.0/high, rejected→0.0/medium; pending/reviewing skipped) into a truth-labels DataFrame, auto-detecting season from `source.rating_snapshot_ids` and falling back to `selections.shortlist` keys. CLI `import-truth-labels --workspace <path>` command merges workspace-derived labels into `player_truth_labels.parquet`, removing same-player prior `scouting_review` rows to avoid duplicates.
  3. **Team comparison radar 6-dim enhancement:** `get_team_comparison()` radar expanded from 5 dimensions (GK/DEF/MID/ATT/Overall) to 6 by adding a Depth dimension quantifying squad rating depth (avg of non-top-11 players). Frontend and tests updated to 6-dim contract.
  4. **Bug fix — player comparison position_percentiles contract:** `get_player_comparison()` was incorrectly treating `position_percentiles` as a `{"dimensions": [...]}` list shape; the actual contract is a dict `{dim_key: {label, percentile}}`. This caused `position_percentile_comparison` to always be empty. Fixed to iterate dict keys and extract `label`/`percentile` from each entry.
  5. **Tests:** 13 new similarity tests (`test_player_similarity.py`), 9 new workspace-to-truth-labels tests, updated player/team comparison tests for 6-dim radar and `label` field. All ~1000+ tests pass, ruff + node check clean.
- **Player Profile Deep Dive & Team Outlook Fix (2026-07-11):**
  1. **Player detail panel enhancement:** `renderPlayerProfile()` now renders 5 new blocks — per-90 metrics (npg_p90, assists_p90, defense_composite, possession_composite), position dimension percentiles (all dimensions from `position_percentiles` with color-coded percentile badges and `overall_score` highlight), rating dimension breakdown table (attack/defense/possession/availability/quality/xT with percentile, contribution, confidence from `position_explanation`), 3-season trend with delta (score/goals/assists/minutes changes from `trend_3seasons`), and low confidence reasons warning list (from `low_confidence_reasons`).
  2. **Season history table:** Replaced compact "season: score" dots string with a full 6-column table (season/team/league/position_group/minutes/optimized_score) from the `seasons` array.
  3. **Team outlook strength_breakdown bug fix:** `compute_team_strength_details()` now returns `rated_players` and `total_players` fields (previously missing — caused `strength_breakdown.rated_players`/`total_players` to be always None in the outlook API).
  4. **Extended strength_breakdown forwarding + frontend display:** `compute_team_outlook()` now forwards all 17 fields from strength details (added depth_avg_rating, reserve_avg_rating, squad_quality_rating, observed_avg_rating, proxy_avg_rating, rating_score, coverage_score, big5_score, big5_ratio). Frontend `renderWcOutlook()` now displays rated/total players, all rating tiers (core/depth/reserve/squad quality/observed/proxy), and a "Strength Components" section showing all 6 component scores as percentages.
  5. **Tests:** 5 new tests — `test_strength_breakdown_forwards_all_fields` (outlook forwarding), `test_rated_and_total_players_present`, `test_coverage_matches_rated_total`, `test_all_component_fields_present`, `test_empty_squad` (compute_team_strength_details).
- **Model Trust & Data Attribution Suite (2026-07-11):**
  1. **Report detail endpoint integration:** `fetchModelRunDetail()` async loads `/reports/model-runs/{run_id}` on first expand; `_renderRunDetailExtra()` renders feature_importance (parquet-level, top 10), params_summary (shape/mean/std/min/max), and data_attribution (primary_source, license_note, StatsBomb attribution callout).
  2. **Data attribution compliance panel:** `_renderDataAttributionPanel()` renders `/license` endpoint's `license_attribution` dict — data source label, update timestamp, per-source license notes with links, StatsBomb attribution highlight.
  3. **Model run comparison view:** `_populateRunComparisonSelects()` + `renderRunComparison()` — select two runs, compare holdout metrics across optimized/baseline × test/train splits with delta coloring and overfit gap comparison.
  4. **Backtest per-fold visualization:** `_renderBacktestFoldChart()` ECharts line chart showing per-fold log_loss/brier/rps trends across all models.
  5. **Tests:** 7 new tests for `get_model_run_detail` API (data_attribution, params_summary, feature_importance, holdout_summary, reproduce_command, nonexistent run, fallback to latest).
- **Model Evaluation & Tournament Outlook Suite (2026-07-11):**
  1. **World Cup team outlook (frontend wiring):** `renderWcOutlook()` frontend with group finish probability bars, knockout projection path, championship probability, and strength breakdown; `fetchWcTeamOutlook()` with per-team caching; `initWorldCup()` select population and event binding. Fixed field name mismatches (`projected_opponent`→`opponent`, `advance_probability`→`win_probability`, `quarter_final`→`quarter_finals`, `group_teams` dict-list handling).
  2. **Prediction backtest comparison:** `get_backtest_comparison()` API reading CLI backtest artifacts (`poisson_backtest_metrics.json`, `dixon_coles_backtest_metrics.json`, `dixon_coles_decay_backtest_metrics.json`), building metric comparison table (log_loss_exact/brier_1x2/rps_1x2 with winner selection), folds breakdown, and isotonic calibration report; `GET /predictions/backtest` endpoint; frontend backtest view with metric comparison table, per-fold details, and calibration effect panel. 5-minute TTL cache.
  3. **Model-run provenance tests:** Extended `TestSaveModelRun` with dependency versions (python/numpy/pandas), train/test seasons from args, position_metrics persistence, and error_cases computation when holdout parquet exists.
  4. **Frontend fixes:** Removed dead model-comparison code in matches view; fixed `wc_knockout` view wiring.
  5. **Tests:** 9 outlook tests + 5 model-run provenance tests + 7 backtest/model_comparison tests (21 new tests, 975+ total passing).
- **World Cup Knockout Bracket Predictor (2026-07-11):**
  1. **Backend:** `simulate_knockout()` in `worldcup/data.py` — Bradley-Terry strength model with Monte Carlo tournament win probability (10,000 simulations, seeded for reproducibility). Projects Round of 32 → Round of 16 → Quarter-Finals → Semi-Finals → Final with per-match win probabilities.
  2. **API:** `GET /world-cup/knockout` endpoint returning full bracket structure and top-16 tournament win probability.
  3. **Frontend:** New "Knockout" (淘汰赛) view with 5-column bracket display, winner highlighting, probability bars, and tournament win probability table. Mobile-responsive single-column layout. Chinese/English bilingual support.
  4. **Static export:** `knockout.json` added to `export_static_frontend_data.py` for offline fallback.
  5. **Tests:** 24 unit tests covering match probability model, group finish prediction, seeding, bracket structure, Monte Carlo reproducibility, and edge cases.
- **v1.0.3 (2026-07-11):**
  1. **Server-side scouting workspace persistence:** `ScoutingWorkspaceStore` with REST endpoints, If-Match optimistic concurrency, atomic writes, immutable backups, loopback access control.
  2. **H2H form trend momentum and rating:** `compute_form_trend()` computing momentum, form_rating (0-100), trend_label, goals trends, clean sheets, and cumulative points sparkline; frontend form trend card with SVG sparkline.
  3. **Multi-section player scouting report export (CSV/JSON):** replaced single-row CSV with 8-section scouting report; fixed `position_percentiles` field name bug and radar label mismatch (Volume/Overall → Reliability/Impact).
  4. **Player comparison CSV export:** comparison result panel now exports multi-section CSV covering profiles, radar, stats, and percentiles.
- **Search autocomplete and offline compare fallback (#42):** prefix-first player/team suggestions, keyboard navigation, TTL-backed data loaders, and static player/team comparison pairs.
- **H2H history and recent form (#43):** Football-Data matchup history, alias-safe results, recent-form comparison, 40 static fallback pairs, responsive frontend states, validated query limits, and cached match normalization.
- **Match-level action-value evidence (#44):** player→match→action xT drill-down, pass/carry/shot and zone/time splits, API/static fallback, mobile overflow repair, and explicit three-match sample boundaries.

## Current Development

- Match Prediction Enhancement Suite complete on branch `codex/match-prediction-enhancement`. All code, tests (24 new), ruff, and node checks pass. Merging to `codex/integration` next.

## Known Blockers

- GitHub account suspension persists (HTTP 403 on `gh`/`git push`/REST API). Local development and merges continue normally; remote PR/push blocked.

## Next Round Candidates

1. Generate a versioned full match-action artifact with dates, minutes, competition coverage, and independent evaluation.
2. Add browser integration coverage for scouting, action-value, API/static empty states, and mobile breakpoints.
3. Add cross-provider schema validation fixtures and empty-data behavior tests.
4. Player shortlist notes persistence (per-player notes attached to scouting workspace shortlist entries).
5. Similar-player search enhancement: position-weighted feature vector and per-position similarity pools.
6. Model-run registry enhancement: tag runs with dataset snapshot hash and feature manifest version.
7. Prediction calibration drift monitoring: track RPS/Brier over time windows and alert on degradation.
8. Ensemble prediction: blend Poisson, DC, and form-weighted DC predictions with optimal weighting.
9. Match momentum prediction: in-play win probability update model based on elapsed time and scoreline.
