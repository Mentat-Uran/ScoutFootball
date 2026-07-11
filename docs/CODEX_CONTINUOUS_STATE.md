# Codex Continuous Development State

## Recently Merged

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

- Model Evaluation & Tournament Outlook Suite complete; merged to `codex/integration`. Preparing next round.

## Known Blockers

- GitHub account suspension persists (HTTP 403 on `gh`/`git push`/REST API). Local development and merges continue normally; remote PR/push blocked.

## Next Round Candidates

1. Add shortlist notes persistence and watchlist diff in the scouting workflow.
2. Generate a versioned full match-action artifact with dates, minutes, competition coverage, and independent evaluation.
3. Add browser integration coverage for scouting, action-value, API/static empty states, and mobile breakpoints.
4. Enrich team outlook with strength_details wiring from team_strength API (currently coverage is None without details).
5. Add per-fold backtest visualization (line charts of log_loss/brier/rps across folds) to the backtest view.
6. Surface model-run registry provenance (dependency versions, error cases) in the frontend report page.
