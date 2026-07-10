# Codex Continuous Development State

## Last Updated
2026-07-10

## Recently Merged (3 PRs in this session)
- **PR #38 - Team Strength Analysis**: New `GET /teams/strength` API and frontend "Teams" view with minutes-weighted team ratings, position group breakdowns, top players, and ECharts stacked bar chart. Also fixed scouting queue caching, MP4 upload limit, pipeline dead code, and Path import.
- **PR #39 - Player Comparison + VAEP + Calibration**: New `GET /players/compare` API and frontend "Compare" view with dual-player radar overlay and metric diff tables. Fixed VAEP player_id→name mapping via xT bridge. Replaced permanent lru_cache with 5-minute TTL cache on calibration.
- **PR #40 - Team Comparison**: New `GET /teams/compare` API and frontend team comparison section with dual-team radar overlay, position group diff table, and top player comparison.

## Test Status
- Full test suite: 745+ tests passing
- ruff check: clean
- Frontend syntax: clean

## Next Round Candidates
1. **Action value three-level drill-down**: Transform flat action value leaderboard into player → team → match drill-down with pass/carry/shot breakdowns.
2. **Server-side scouting write-back**: Add POST endpoints for scouting workspace persistence (ROADMAP Phase B).
3. **Duplicate endpoint cleanup**: Remove `/prediction/{home}/{away}`, `/ratings/snapshots` aliases if no longer used by frontend.
4. **Player search autocomplete**: Add typeahead/suggestions to player and team search inputs.
5. **Static data export for compare endpoints**: Generate static fallback data for player/team comparisons.
6. **Cache TTL for other loaders**: Apply TTL cache pattern to `_load_all_player_ratings()`, `load_model_meta()`, `load_league_metrics()`, etc.
