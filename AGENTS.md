# AGENTS.md

You are a pragmatic AI development assistant. Answers and development must be direct, accurate, and verifiable.

## Current Project Status

The pipeline end-to-end entry points are `scoutfootball ingest` -> `scoutfootball build-features` -> `scoutfootball train`. The project's authoritative source of truth is `docs/PROJECT_CHARTER.md`, the current task source of truth is the top of `docs/TASKS.md`, the capability source of truth is `docs/CAPABILITIES.md`, the long-term dependency order is `docs/ROADMAP.md`, the industry tooling and technical trade-off basis is `docs/FOOTBALL_TOOLING_LANDSCAPE_2026.md`, the user guide is `README.md`, and algorithm explanations are governed by `docs/ALGORITHM.md` and `docs/MODEL_CARD.md`. Before executing tasks, first read the charter and capability table, and verify with the current code/artifacts — do not infer current status from the historical numbers below.

## Pre-work Checks and Documentation Sources of Truth

- `C:\football` is the workspace root directory, not a Git repository; typically work from `C:\football\scoutlab`. First confirm the actual child repository and the nearest `AGENTS.md`, and do not run Git commands directly in the root directory.
- Before starting, at minimum check `git status --short`, `git branch --show-current`, `git worktree list --porcelain`, and recent logs, then decide whether to use an existing worktree or create a new one.
- When locating conflicts, `docs/PROJECT_CHARTER.md` is authoritative; current facts are based on code, tests, and artifacts that have passed content-level verification; capability scope is governed by `docs/CAPABILITIES.md`; task status is governed by the top of `docs/TASKS.md`; long-term roadmap only refers to dependencies and gates in `docs/ROADMAP.md`.
- `docs/CODEX_CONTINUOUS_STATE.md`, `docs/deep-research-report.md`, the historical section of `docs/TASKS.md`, and the old phase records at the bottom of this file are only historical evidence, not the current task or capability source of truth.
- `docs/ROADMAP.md` does not write weekly, monthly, yearly, or release date targets; it only writes direct dependencies, startup conditions, exit gates, unlock results, and stop conditions. Audit dates, data `as_of`, model time splits, match times, and license retention periods are not roadmap deadlines and can be retained.
- Do not manually copy easily-drifting routing numbers, page counts, line counts, coverage rates, or build status across multiple documents; prefer to generate them from OpenAPI, code, manifests, tests, and run reports.

## Git and Worktree Safety

- Do not overwrite, stage, stash, reset, checkout, or clean user's uncommitted changes. When the workspace is dirty but the changes are unrelated to the task, prefer to bypass; when there is overlap, you must stop and report.
- Remote GitHub access is currently unavailable: the account used for
  `https://github.com/Mentaturan/ScoutFootball_for_World_Cup.git` is suspended
  (observed 2026-07-17: `remote: Your account is suspended`, HTTP 403). All
  remote operations — `git push`, PR creation, release publishing, GitHub
  Actions triggers, `gh` CLI calls — will fail until the account is restored
  via https://support.github.com. Continue committing locally; queue pushes
  and run `git push --set-upstream origin codex/integration` (or the relevant
  branch) once access is restored. Do not retry remote operations in a loop.
- Prefer using existing active worktrees with clear status. When isolation is needed, first check `git worktree list --porcelain`, confirm the target branch is not checked out in another worktree, then create a new worktree with a unique name; do not blindly use a fixed directory or overwrite an existing directory.
- Do not assume `main`, `codex/integration`, or any working tree is in a mergeable state. Before creating branches, squashing, or fast-forwarding, you must verify the baseline, branch pointers, workspace cleanliness, and diff scope.
- Local commits and merges only proceed when the user's current goal explicitly authorizes them; push, remote PR, deployment, formal release, tags, and release assets always require explicit authorization.
- After the merge is completed and verified, delete the temporary worktree created by the agent in this round that has been confirmed clean, to avoid accumulating large snapshots; do not delete existing user worktrees. Before deletion, parse and verify that the absolute path is within the expected `C:\football` subdirectory.
- Do not automatically create Git bundles for each round. `C:\football\backups` is treated as read-only per workspace rules; only create bundles when the user explicitly requests a backup, and first confirm the target path and remaining space.
- `git reset --hard`, history rewriting, and `git checkout --` on unknown changes are prohibited. When branch or worktree conflicts occur, first preserve the scene and choose another safe path.

## Windows and PowerShell Conventions

- This environment defaults to Windows PowerShell. Do not directly copy POSIX syntax such as `PYTHONPATH=src command`, `$(date ...)`, `rm -rf`; use PowerShell syntax, and restore the original value after temporarily modifying environment variables.
- For path operations, prefer absolute paths, `Resolve-Path`, and `-LiteralPath`. Before recursive moves or deletions, you must verify that the resolved target is within the expected worktree; do not hand PowerShell enumeration results to `cmd.exe` or other shells for deletion.
- `uv sync` is only run when the environment is missing, the lock file, or dependencies have changed. If the existing `.venv` has permission or lock conflicts, first check other processes and available worktrees; do not mask the problem by deleting the user environment or repeatedly rebuilding.
- When you need to set the source path, use the existing workable method in the current repository; if you must set `$env:PYTHONPATH`, first save the old value and restore it after the command ends.
- API and frontend joint debugging defaults to the FastAPI same-origin entry `127.0.0.1:8000`. `python -m http.server` only verifies pure static/STATIC fallback, and cannot be used to claim that LIVE API is connected.
- Long-running services or GUIs are only started when verification requires; background processes must be identifiable, stoppable, and must not leave orphan processes occupying ports.

## Local Data and Networking Boundaries

- Core capabilities run locally by default, with no requirement for accounts, public cloud, cloud sync, or telemetry. Any networked import must be explicitly triggered by the user, can be turned off, and retain source and license; do not add default uploads or background telemetry.
- Browser localStorage, browser downloads, same-machine files, and loopback API are all different storage scopes; UI, exports, and documentation must clearly distinguish them; browser-local state cannot be described as server-side audit, cross-device sync, or multi-user collaboration.
- Same-machine workspace writes are only allowed to loopback addresses by default; do not enable remote writes by default for testing convenience. Any remote access switch must remain explicit, limited to trusted networks, and clearly state the risks.
- Third-party commercial data may only be imported by the user via legal local files or explicitly authorized APIs. Do not scrape restricted sites, bypass access controls, submit credentials, attach third-party data, resell, or redistribute.
- User local data, internal evaluations, contracts, videos, minor information, and sensitive health data must not be uploaded, committed to Git, written into public samples, or used for public deployment. Debug logs and failure reports must also avoid leaking these contents.
- Public/open code does not mean third-party data is open. Any reports, static snapshots, models, and exports must inherit input licenses, attribution, redistribution, retention, and deletion boundaries.
- Parquet footer, file existence, or metadata row count does not prove content is usable; only after content-level reads, schema, and key statistical verification are completed at a locked runtime can data be written as a currently usable capability.
- STATIC fallback, samples, synthetic data, estimates, projected rosters, and model outputs must be clearly labeled, and cannot be written as real-time, official, complete coverage, or verified online capabilities.

Locally cached historical records (the following numbers come from development records at different times and may conflict with each other or have become invalid; only after content-level reads are completed at a locked runtime can they be called "currently verifiable"):

- FBref: 5 seasons standard, shooting, misc tables are all 14,356 rows.
- Football-Data: `data/raw/football_data/combined_results.parquet` currently has 10 seasons (1617–2526), 20 leagues, 68,953 rows. 2526 season data has been added. 8 team name alias mismatches have been fixed (accent removal + 12 new aliases).
- Understat: 10 seasons, 6 leagues, `players_10seasons.parquet` currently has 31,902 player-season rows.
- StatsBomb Open Data: historical records state `big5_matches.parquet` has 126 matches, `events_all.parquet` has 7,744,412 events, and `actions_all.parquet` has 7,740,429 rows (SPADL format). During the 2026-07-16 audit, `matches_all.parquet` footer reported 2,187 rows, conflicting with the old "empty table" claim; do not select the source of truth until content-level verification is completed at the standard runtime.
- xT grid: `xt_grid.npy` full xT grid has been generated for action value calculation.
- VAEP model: 6,771 player-season rows, scores AUC=0.65, concedes AUC=0.88.
- World Cup data: 48-team rosters/projected call-up snapshots and rating coverage exist; you must distinguish official rosters, recorded data, projected call-ups, and placeholder content, and do not write them as real-time actual rosters.
- Rating artifacts: `player_ratings_optimized.parquet` currently has 30,483 rows.
- GPU optimization results (2026-06-09, after alias fix): 2526 holdout Spearman=0.740/Pearson=0.744 (baseline 0.618/0.619), 3-fold CV average test Spearman=0.718/Pearson=0.719. Fold 1 (2324) Spearman=0.662, Fold 2 (2425) Spearman=0.792, Fold 3 (2526) Spearman=0.701. Parameter stability 3 seeds std=0.002. Feature importance: assists_p90 > npg_p90 > minutes. Strong teams systematically underestimated (Barcelona -37.7, Real Madrid -33.4), relegated teams overestimated (Burnley +24.9). v1.3.1 rerun completed: holdout Spearman=0.724 (meta)/0.711 (holdout), 3-fold CV average 0.677.
- Rating feature matrix: `rating_feature_matrix.parquet` (8,141 rows) + `rating_feature_matrix_manifest.json`, including missing field flags, data source coverage flags, and in-position median fallback. Added 6 defensive fields (tackles_won, interceptions, fouls_committed, fouls_drawn, crosses, own_goals), missing rate 0.02%. Added 4 xT/VAEP fields (xt_total, xt_per_90, vaep_total, vaep_per_90), missing rate 71.7% (consistent with expected StatsBomb open data coverage).
- Coverage confidence rules: HIGH/MEDIUM/LOW three levels, coverage < 0.90 prohibits strong ranking conclusions.
- Availability shortcut diagnostic report: permutation importance, position availability weights, team aggregation weight distribution, availability-driven player identification.
- In-position metrics: GK/CB/FB/DM/CM/AM/W/ST core dimensions, percentile rank, and Chinese explanation templates for each position.
- Finishing shrinkage: empirical Bayes shrinkage, K=50, prevents small-sample shots from being over-amplified.
- mplsoccer integration: `src/scoutfootball/viz/pitch.py` wraps pitch, shot map, pass map, heatmap, pizza chart.
- Low-confidence prompts: insufficient minutes, missing data, position reclassification uncertainty, low league coverage.
- Streamlit is currently a 15-page workbench: overview, 5 analysis pages, 3 P1 demo pages, 4 World Cup pages, 1 scouting queue page, and 1 action value sample page; the overview page has been connected to artifact/model-run reads, the scouting page has been connected to review queue/watchlist/shortlist reads, and the action value page has been connected to xT + VAEP artifacts.
- `frontend/` static Liquid Glass frontend has been refactored into an analysis workbench: overview, players, value, match prediction, scouting, action value, reports, tactical board, World Cup, and governance views. Scouting and action value entries were restored on 2026-06-23: scouting supports real queue fields, filtering, status transitions, snapshots, and CSV; action value supports xT/VAEP, match/minute filtering, sample summaries, and StatsBomb attribution. When the API is online, it reads from FastAPI; when mapped endpoints return 404 on a pure static server, it falls back to `frontend/data/`. All navigation icons use geometric Unicode symbols, no emoji; API/local JSON strings are uniformly escaped before entering HTML, and CSV exports have formula injection protection. The first round of frontend stabilization has been completed: API status pill distinguishes LIVE/STATIC/OFFLINE, review queue is paginated (50 items per page), NaN/undefined numeric display is guarded, STATIC is clearly identified when static fallback succeeds, loading failure is shown when both API and static cache are unavailable, and World Cup page status pills are now dynamic. Static snapshot export bug BUG-001 fixed: dataclass/Pydantic responses are no longer written as repr strings by `str(obj)`.
- `data_loader.py` has been hardened: DuckDB read exceptions correctly fall back to Parquet; a new `_safe_read_parquet` helper prevents corrupt Parquet files from causing 500 errors; 6 data loading functions now use safe reads.
- `api.py` has been hardened: `_clean_json_value` supports numpy.int64/float64/bool_ and inf; `get_match_prediction` catches all exception types; inline NaN cleanup code has been merged into `_clean_json_value`.
- Electronic tactical board P1.5 has landed: `frontend/` local canvas, normalized coordinates, basic objects, formation presets, local JSON projects, localStorage save, and schema-cleaned import/export. Added: drawing tools (free brush/line/rectangle/ellipse), text annotations, curved arrows, touch gesture support, looping animation, object delete buttons. PNG static export, WebM animation export, PDF export, and version migration are implemented. MP4 export is implemented via backend ffmpeg conversion (`/tactical-board/capabilities` and `/tactical-board/export/mp4` endpoints). GIF export is implemented browser-side via gif.js.
- Desktop application built: `desktop/` directory contains Electron + PyInstaller packaging configuration, macOS arm64 version verified usable (221MB .dmg), Windows build script `scripts/build-desktop-windows.ps1` has been added. Frontend is packaged into app.asar, backend executable is placed in extraResources, and data files are distributed with the app. Auto-update is implemented via electron-updater + GitHub releases.
- Dixon-Coles score prediction model implemented: `fit_dixon_coles()` has been integrated into the pipeline and `data_loader.py`, with 7 unit tests covering parameter fitting and prediction. Calibration integrated with time decay + isotonic calibration, Brier 0.632, RPS 0.220.
- Frontend security hardening: `index.html` adds CSP meta tag, echarts CDN gets SRI integrity, HTTP responses add `X-Content-Type-Options: nosniff`; browser-level XSS/CSV regression tests completed.
- Test warnings cleanup: `conftest.py` adds matplotlib backend fixture to avoid GUI warnings, `pyproject.toml` adds `filterwarnings` configuration.
- Bug fixes: 26 bugs fixed (6 critical, 9 warning, 11 minor), total tests 582 (575 unit + 5 integration + 2 skipped).
- Phase 4 CI/CD and deployment: GitHub Actions CI is configured with Ruff, pytest, Node syntax, and frontend Node tests; the three golden workflows still lack real browser E2E. The `continue-on-error`, `|| true`, and placeholders in the release workflow are risks to be fixed and cannot be called release successes. Cloud configuration or local builds also do not prove that the target URL is currently reachable.
- Value deviation analysis: value-fairness OOF residuals, league/position bias, and age scatter analysis implemented.
- Scouting queue enhancements: review status transitions, watchlist diff, and shortlist notes landed; current browser state is only stored in localStorage and must not be described as formal backend audit or cross-device sync.
- Player comparison percentile table: same-position percentile comparison table implemented.
- WebM animation export: `canvas.captureStream` + `MediaRecorder` implemented, with fallback prompt on failure.
- Set piece templates: corner near post, corner second ball, free kick wall, throw-in, penalty, goal kick build-up templates implemented.
- Player list enhancements: pagination, sorting, and league filtering implemented.

New adapters (implemented, some require specific environments to run):
- SofaScore, SoFIFA, WhoScored, Capology: require Chrome + Selenium, recommended to run on Windows GPU server.
- API-Football: requires `API_FOOTBALL_KEY` environment variable, gracefully degrades without a key.
- Transfermarkt-datasets: requires manual download of DuckDB file placed in `data/raw/transfermarkt_datasets/`.
- FBref extended leagues + 7 new stat_types: require Chrome + Selenium, recommended to run on Windows GPU server.
- StatsBomb bulk download: no special requirements, but large download volume requires a stable network environment.
- Running soccerdata scripts requires setting `SOCCERDATA_DIR=./data/soccerdata`.

The rating system is still in the calibration phase:

- PyTorch GPU optimizer and remote GPU compute scripts exist.
- The optimization objective has changed from pure Spearman/Pearson to a composite objective: Spearman(0.42) + soft NDCG@20(0.16) + in-position ranking consistency(0.12) + training set points regression calibration(0.16) + points distribution match(0.10) + title/relegation tail calibration(0.14) + training set league average residual penalty(0.08) + player rating outlier guardrail(0.05) + optional player truth label anchoring (default 0.08, disabled when labels are insufficient) + prior regularization(0.04); each weight can be overridden via command-line parameters. v1.3 GPU rerun historical record: 2526 holdout Spearman=0.737/Pearson=0.742, points spread ratio=0.985, points MAE=11.55; v1.3.1 historical record is holdout Spearman=0.724 (meta)/0.711 (holdout), 3-fold CV average 0.677. v1.3.2-dev has added truth-anchor and supervised MLP candidates; old documents state labels at 41,389 rows, but 2026-07-16 footer reports 29,723 and the current runtime has not completed content decoding. MLP Spearman=0.950 comes from self-circulating labels and cannot be used as evidence of real impact.
- Model run registry implemented: after each optimization, saves to `data/models/runs/<timestamp>/`, including optimized_params.npy + meta.json (parameters, seeds, input hash, metrics, in-position metrics, error case summary).
- Neural network admission gates have been written into `docs/MODEL_CARD.md`: must first have independent player labels, time splits, baseline comparison, in-position metrics, and error cases; pure team points supervised training is prohibited. `src/scoutfootball/models/player_rating_nn.py` is only a supervised sklearn MLP candidate entry; label row count and source must be re-verified at the content level.
- The current rating layer prioritizes role, league, and real impact calibration, and no longer treats Top N quotas as the main objective.
- Coarse position role reclassification, stronger league strength curves, holdout evaluation, Pearson metric fix, and ST/W quality cap have been added.
- All position availability caps have been lowered to 0.18-0.20; CM/DM/FB/CB/GK can no longer use 0.30-0.36 availability weights to dominate ratings.
- Team season rating aggregation has been changed from pure minute-weighted to capped minutes + core rotation robust aggregation, avoiding rating layer and team layer repeatedly rewarding raw availability.
- The evaluation report now outputs team coverage, showing target team count, rating-side team count, matched team count, and coverage rate by league-season; when coverage is insufficient, do not force interpretation of the leaderboard.
- The 2526 top-five league test set has directly patched team name aliases for Football-Data and the rating side; Premier League, La Liga, Bundesliga, Serie A, Ligue 1 holdout coverage has reached 1.00.
- Team points correlation will be biased toward availability, CM, and GK, and cannot be used alone as a player impact label.
- The top of weak leagues has been suppressed, but real value, awards, expert labels, or manual tier calibration are still needed to calibrate cross-league levels.
- FBref coarse positions can only be conservatively reclassified; StatsBomb, formation, or manual position enhancement is still needed.
- `player_value_metrics.parquet` only has StatsBomb event value samples and cannot be treated as full-league action value. 2026-07-16 footer shows truth labels at 29,723 rows and action value at 9,951 rows respectively, but full read failed; the standard runtime must be fixed first and the source distribution and content verified before continuing to use the old 41,389/15,062 figures.
- The evaluation pipeline has added N/A team filtering: `build_matched_results()` and `build_team_target_tensors()` automatically exclude teams with NaN/inf points, and `evaluate_params()` reports the number excluded.
- The rating model card `docs/MODEL_CARD.md` has been output, documenting data sources, label definitions, applicability boundaries, known biases, and unavailable scenarios.
- The neural network rater can only be a candidate experiment after an independent real label layer is completed; even if the label file is readable, it must pass source policy, time split, baseline, slicing, and error case review before replacing the default rating.
- Issues recorded in `docs/PROBLEMS.md` can only be considered as completing the first round of code-level protection; complete conclusions must be written after rerunning GPU optimization and the 2526 holdout error review.
- GPU rerun completed (2026-06-09, after alias fix, RTX 5070 Ti): 2526 holdout Spearman=0.740/Pearson=0.744 (baseline 0.618, improvement +0.122). 3-fold CV average test Spearman=0.718/Pearson=0.719. Fold 1 (2324) Spearman=0.662, Fold 2 (2425) Spearman=0.792, Fold 3 (2526) Spearman=0.701. Parameter stability 3 seeds std=0.002. Feature importance: assists_p90 > npg_p90 > minutes. Strong teams systematically underestimated (Barcelona -37.7, Real Madrid -33.4), relegated teams overestimated (Burnley +24.9). Aliases fixed (12 new aliases + accent removal), Bundesliga coverage fixed from 0.778 to 1.000.

## Subsequent Architecture Direction (Historical Ten-Layer Description)

This section is retained as historical background; new dependency nodes, startup conditions, and exit gates are governed only by `docs/ROADMAP.md`, and the roadmap is not bound by year or duration.

Future updates advance in ten layers. The first seven layers are the current main trunk, and layers eight to ten extend to scouting workflow, prediction calibration, and spatial/video research, which should be advanced gradually after P0-P4 stabilizes:

1. Data and compliance layer: local cache, DuckDB, Parquet, manual import, and data quality logs.
2. Standard facts layer: matches, teams, players, lineups, events, season statistics, value, and league strength.
3. Cross-vendor standardization layer: internal event/tracking schema, aligned with SPADL, atomic-SPADL, Common Data Format, kloppy/floodlight concepts; no rush to add dependencies in the short term.
4. Event action value layer: StatsBomb events -> internal actions -> SPADL/atomic-SPADL -> xT -> VAEP/Atomic-VAEP.
5. Player truth and rating layer: real labels + season statistics + xG/xA + xT/VAEP + availability reliability + league strength + age/trend + confidence.
6. Evaluation and model card layer: `docs/EVALUATION.md`, `docs/MODEL_CARD.md`, position-wise metrics, error analysis, model run registry.
7. Product visualization and API layer: Streamlit + Plotly + mplsoccer + FastAPI read-only artifacts + electronic tactical board.
8. Scouting decision layer: watchlist, shortlist, manual label review, low-confidence review queue, tactical notes.
9. Score prediction and probability calibration layer: league average -> Independent Poisson -> Dixon-Coles + time decay -> calibration.
10. Spatial/video/off-ball research layer: StatsBomb 360, Metrica/open tracking, space control, xG+, off-ball value, must rely on compliant sample data.

External research basis:

- socceraction: main reference for SPADL/atomic-SPADL, xT, VAEP, Atomic-VAEP.
- StatsBomb Open Data: first primary source for the event layer; public display of derived products must attribute the data source.
- mplsoccer: football-specific visualization library, currently integrated.
- Electronic tactical board cases: Tactico, DrawTactics, TacticSlate, Coach Tactic Board, Soccer Tactic Board, Metrica Tactical Boards, FC Tactix, TacticalPad, TacticalBoards; common features are formation/player dragging, red/blue dual teams, jersey number/name/role, hover or click player info, free brush/eraser, arrows/regions/trajectories, training equipment, keyframe or path animation, demo playback, PNG/PDF/WebM/MP4/GIF export, sharing, folders/templates, 2D/3D or video telestration workflows.
- kloppy, floodlight, Common Data Format: only as long-term references for cross-vendor event/tracking schemas.
- VAEP, xT vs VAEP, PlayeRank, combined player rating, xG finishing bias, and Dixon-Coles papers: correspond to action value, model comparison, in-role rating, hybrid rating, finishing shrinkage, and score prediction baseline, respectively.

## Historical Priorities (No Longer the Current Queue)

The following P0–P8 are old development phase records. Current tasks are only selected from the top of `docs/TASKS.md`; do not continue old routes due to the numbering in this section.

1. P0: Rating system real impact labels and training objective reconstruction.
   - In the near term, first rebuild the Football-Data 10-season combined Parquet, then rerun the GPU optimizer with the new availability cap and robust team aggregation, and review error cases such as Everton/Stuttgart/Rennes/Napoli/Real Madrid/Arsenal/PSG.
   - Subsequently introduce Transfermarkt manual imports, awards, expert tiers, or manual calibration sets as player real impact labels, and complete the feature matrix, missing field flags, and neural network admission gates.
2. P1: Demonstration enhancement and explainable product layer, prioritize integrating mplsoccer. Core deliverables: player radar/ranking page, value deviation leaderboard, match prediction page — 3 screenshotable Streamlit pages, README adds 3–5 screenshots and demo reproduction instructions.
   - `frontend/` Liquid Glass static workbench Phase 3 completed: all mock data has been replaced with FastAPI contract calls, the World Cup page is connected to real data, and player comparison/prediction card/action value have been enhanced.
3. P1.5: Electronic tactical board, tactical demonstration, and animation export. Canvas/JSON/drawing tools/text annotations/curved arrows/touch support/looping animation/delete button landed; GIF export implemented via gif.js. This is a historical description; local video telestration, tracking, and 2D/3D research must comply with current dependency gates, and real-time cloud collaboration has been excluded by the project charter.
4. P2: StatsBomb event action value layer, xT and VAEP implemented. VAEP 6,771 player-season rows, scores AUC=0.65, concedes AUC=0.88; xT/VAEP features integrated into the rating matrix (missing rate 71.7%).
5. P3: Rating model reconstruction, integrating action value as an enhancement dimension; after the real label layer stabilizes, the neural network can only first be a candidate model compared with the current optimizer under the same conditions.
6. P4: Model evaluation documentation and model card. Add `docs/EVALUATION.md` (Spearman, time split, baseline, error cases) and `docs/MODEL_CARD.md` (data sources, label definitions, applicability boundaries, biases, unavailable scenarios).
7. P5: Dixon-Coles score prediction upgrade (`fit_dixon_coles` implements time decay + isotonic calibration, Brier 0.632, RPS 0.220).
8. P6: Cross-vendor standardization and open format layer, first do schema, license manifest, and conversion experiments, without changing the current pipeline.
9. P7: Scouting decision and manual calibration layer, incorporating real labels, low-confidence samples, error cases, and tactical notes into review queue, watchlist, shortlist.
10. P8: Spatial/video/off-ball research layer, StatsBomb 360, Metrica/open tracking, xG+, off-ball value, reinforcement learning only as long-term directions.

Apart from the tactical board, the current plan must continue to retain these gaps: v1.3.1 rerun completed but error review still needs deepening, scouting manual annotation re-injection not implemented, cross-vendor schema and tracking/video research still remain in subsequent phases.

## Development Principles

- Project positioning is governed by `docs/PROJECT_CHARTER.md` as the highest priority: local-first, MIT open source, individually maintained, non-profit. Unless the user explicitly modifies the charter, do not plan SaaS, paid tiers, enterprise editions, sales/customer acquisition, revenue KPIs, default cloud sync, or default telemetry.
- The roadmap only expresses dependencies, sequence, startup conditions, and exit gates, and is not bound by week, month, year, or release date; calendar deadlines cannot compress licensing, testing, security, recoverability, or honesty requirements.
- The primary audience is the maintainer and similar individual analysis/research users. External organizations may reuse open results, but this does not create SLA, custom delivery, centralized hosting, or customer-driven scheduling obligations.
- After v1.0.0, new features must be merged via PR; direct commits to the main branch are prohibited.
- Data processing must be reproducible, cacheable, and verifiable.
- ETL must be idempotent and cannot depend on uncontrollable real-time web page state.
- Models must have baseline, time split, metrics, and error analysis.
- Before adding a new model, write evaluation metrics first; before adding a new long-term data source, write compliance boundaries first.
- Do not write planned modules as implemented capabilities.
- Do not write StatsBomb small-sample event capabilities as full-league capabilities.
- New features must map to at least one golden workflow of scouting decisions, match preparation, or data/model release; before real browser E2E, contracts, and failure states are complete, do not add top-level navigation or wide routes.
- Page count, route count, data row count, and model parameter count are not success metrics; prioritize improving decision workflow completion rate, evidence completeness rate, and key process reproducible pass rate.
- All capabilities are first classified as delivered, partially delivered, sample/experiment, local state, planned, or unverified; "implemented" cannot be used to mask data coverage, release, or governance gaps.
- Transfermarkt only allows manual or authorized imports.
- FBref is only a restricted low-frequency supplementary source, and does not bypass CAPTCHAs or anti-scraping.
- When publicly displaying StatsBomb data products, the data source must be attributed.
- Before adding new public charts, reports, or export products, you must confirm data source attribution and public display boundaries.
- Before adding new electronic tactical board exports, you must clarify whether the export contains real data, StatsBomb Open Data, or model-derived products; when included, source attribution must be retained.
- The first phase of the electronic tactical board only allows browser-local canvas, JSON projects, and lightweight exports; do not perform training, scraping, batch video transcoding, or heavy model inference in the browser.
- Whenever the frontend writes API, Parquet-derived JSON, local JSON, demo strings, or user-imported fields into `innerHTML`, it must first use existing escaping/sanitizer helpers; CSV exports must go through `csvCell()`; tactical board import/save/read must go through `TACTICAL_BOARD.sanitizeProject()`.
- It is not allowed to silently `str()` non-JSON-serializable objects into static snapshots; `scripts/export_static_frontend_data.py` must use a JSON-safe serializer and error out on non-serializable objects.
- Static fallback must be explicitly labeled STATIC; when both API and static cache are unavailable, loading failure must be displayed, not blank or incorrect data.
- browser-local state (watchlist/shortlist/review notes) must not be described as backend audit or cross-device sync; the UI must label "local state".
- `goals - xG` cannot be directly used as finishing ability; sample-size shrinkage or low-confidence labeling must be used.
- Top N position quotas cannot replace real impact calibration.
- Availability is only a reliability/sample-size signal, not the player's ability itself; without real label verification, do not raise the availability cap back above 0.25.
- Team season aggregation must not fall back to raw minutes weighted mean; if changing aggregation, you must output holdout, league stratification, error cases, and availability permutation importance at the same time.
- When reporting position weights, you must use capped weights; do not treat raw softmax weights as actual model weights.
- Missing defensive, possession, xT/VAEP, and advanced goalkeeper fields must be expressed with missing flags and low-confidence fallback; missing values of 0 cannot be treated as real low ability.
- Before adding neural networks or other complex models, first define labels, evaluation metrics, and baseline; models trained only on team points correlation cannot be used as real player ability models.
- If implementing a neural network candidate model, you must retain the current rating optimizer as baseline, saving feature manifest, parameters, random seeds, input hash, holdout metrics, in-position metrics, and error case comparison.
- Reinforcement learning, GCN, Transformer, off-ball value, xG+, or tracking/video models cannot enter default capabilities without compliant sample data, labels, baseline, and model card.
- kloppy, floodlight, Common Data Format are currently only schema and conversion references; do not add them directly to `pyproject.toml` before entering the corresponding phase.
- For league-seasons with team coverage below 0.90, only output low-confidence diagnostics; do not write them as complete league rankings or top-four prediction conclusions.
- If the user requests testing the rating optimizer, first run a small-scale test on the current computer; do not call the Windows 5070 Ti server without explicit user permission.
- Dixon-Coles is the second main line of score prediction and cannot jump ahead of the rating system P0/P1/P2.
- Tactical board MP4 export, local ffmpeg, video telestration, tracking data import, and 3D/behind-goal views must only enter implementation after the current canvas model, animation schema, export fallback, report attribution, and roadmap research gates are stable; real-time cloud collaboration will not be implemented unless the user first explicitly modifies the project charter.

## Module Conventions

- The existing package root is `src/scoutfootball/`.
- The existing command entry is `src/scoutfootball/__main__.py`.
- The existing pipeline entry is `src/scoutfootball/pipeline.py`.
- When adding new event action value modules, use `src/scoutfootball/action_value/`.
- New internal actions schemas should preferably be written into `src/scoutfootball/action_value/schema.py` or `src/scoutfootball/schemas/`, and synced with `docs/DATA_CONTRACTS.md`.
- When adding a new neural network rating candidate model, prefer `src/scoutfootball/models/player_rating_nn.py` or a sibling module; training scripts should only be thin entry points, not pile core logic into `scripts/`.
- New model run registries should preferably be written into `data/reports/model_runs/` or `data/models/runs/`, and must save dataset snapshot, input hash, parameters, random seeds, dependency versions, and metrics.
- New scouting manual calibration data should preferably be written into `data/gold/feature_store/player_truth_labels.parquet`, `data/reports/review_queue/`, or equivalent local artifacts; do not write manual labels and model predictions into the same field.
- When adding new football-specific charts, prefer extending `src/scoutfootball/viz/`, do not pile plotting logic into Streamlit pages.
- `frontend/` is the static product shell: retain the Liquid Glass style of `frontend/index.html`, `frontend/style.css`, `frontend/app.js`; pages only do local display and lightweight interaction, and do not perform training, scraping, or heavy data processing in the browser.
- Documentation responsibilities are fixed: `docs/PROJECT_CHARTER.md` governs project positioning and has the highest priority, the top of `docs/TASKS.md` is the source of truth for current task status, `docs/CAPABILITIES.md` governs capability maturity and fact boundaries, `docs/ROADMAP.md` governs long-term dependency order and phase gates, `docs/FOOTBALL_TOOLING_LANDSCAPE_2026.md` governs industry tooling basis and technical trade-offs, `docs/FRONTEND_STATUS.md` records frontend implementation, `docs/FRONTEND_SYNC.md` governs API/static snapshot sync; do not maintain conflicting numbers separately across multiple files. Easily-drifting inventories should preferably be generated from code, OpenAPI, manifests, and run reports.
- `desktop/` is the desktop application packaging directory: `main.js` (Electron main process), `preload.js` (IPC bridge), `backend/server.py` (PyInstaller entry), `scoutfootball-server.spec` (PyInstaller configuration), `package.json` (electron-builder configuration, without `publish` block — publishing is handled by `softprops/action-gh-release` in GitHub Actions). Build artifacts (`dist/`, `backend-dist/`, `backend-build/`, `frontend/`, `node_modules/`) are not committed to git and are excluded via `.gitignore`. Build command: `bash scripts/build-desktop.sh --mac`.
- `frontend/` Phase 3 has completed mock->real replacement; pages read FastAPI local artifacts or contract-aligned tracked static snapshots, and no longer depend on hardcoded mock data blocks.
- `frontend/app.js` already has `escapeHtml()`, `escapeAttr()`, `sanitizeCssPercent()`, and `csvCell()`; when adding new HTML templates, attributes, style widths, or CSV exports, prefer reusing these helpers, and do not directly concatenate backend/local strings into HTML.
- Frontend payload field changes must sync API, `scripts/export_static_frontend_data.py`, static JSON, empty states, `docs/DATA_CONTRACTS.md`, and contract tests; action value main fields use `xt_per_90`/`vaep_per_90`, scouting name main field uses `player_name`.
- API paths with static mappings are allowed to fall back on network failure, 5xx, or pure static server 404; 4xx without static mappings must preserve error semantics.
- The currently landed FastAPI read-only contract subset includes `/artifacts`, `/players/{player_name}`, `/ratings/snapshots`, `/predictions/{home}/{away}`, `/predictions/meta`, `/predictions/calibration`, `/review-queue`, `/watchlist`, `/shortlist`, `/action-values`, `/worldcup/teams`, `/reports/model-runs`, `/tactical-board/capabilities`, `/tactical-board/export/mp4`, etc.; exact routes, schemas, and deprecation status must be generated from the current OpenAPI/code, and row counts or "real roster" scope are not maintained in this file.
- New electronic tactical boards should preferably be placed in `frontend/`: use normalized pitch coordinates, local JSON projects, object/layer/frame schemas, keyframe or step-style timelines; first phase exports PNG/PDF/WebM, MP4 only as an optional backend capability after local ffmpeg is detected.
- The electronic tactical board project schema must include at least `board_id`, `title`, `sport`, `pitch_type`, `objects`, `layers`, `frames`, `version`, `created_at`, `updated_at`, `source_attribution`.
- Tactical board export files should preferably be written to `data/reports/tactical_exports/`; if it is only a browser-local download, do not pretend it has entered the model/report artifacts directory.
- Correspondence between frontend long-term views and backend contracts:
  - Overview: artifact registry, row count, artifact update time, real/proxy/synthetic data labels, license attribution.
  - Players: player profile API (including in-position percentiles + low-confidence reasons + 3-season trend), rating snapshots, radar chart overlay comparison, percentile comparison table, export.
  - Value: value-fairness OOF report, residual stratification, manual value import boundaries.
  - Match prediction: unified prediction service, model version, coverage, log loss/Brier/RPS, score matrix heatmap, calibration metrics, win/draw/loss probability bar chart.
  - Scouting: review queue/watchlist/shortlist Parquet contract; server-side read-only, browser localStorage state must be explicitly labeled as local state.
  - Action value: xT + VAEP aggregation, pagination, minute threshold, and source attribution; specific row counts are only generated from current artifacts that have passed content-level verification. "Full" even when used only refers to that artifact's row set, and does not represent full-league coverage.
  - Reports: model-run registry, input hash, random seeds, parameters, metrics, error cases.
  - Tactical board: local board projects, board snapshot, animation export, coaching notes, source attribution; write API is deferred, first support local JSON import/export.
- New rating feature matrix modules use `src/scoutfootball/features/rating_matrix.py`.
- New coverage confidence modules use `src/scoutfootball/evaluation/coverage_confidence.py`.
- New availability diagnostic modules use `src/scoutfootball/evaluation/availability_diagnostic.py`.
- New in-position metrics modules use `src/scoutfootball/evaluation/position_metrics.py`.
- New unified confidence modules use `src/scoutfootball/evaluation/confidence.py`.
- New truth label contract modules use `src/scoutfootball/evaluation/truth_labels.py`.
- New football-specific chart extensions use `src/scoutfootball/viz/pitch.py`, using mplsoccer.
- Streamlit pages only read local artifacts, do not directly perform heavy training.
- Training artifacts are written to `data/models/` or `data/gold/feature_store/`, and save feature manifest, parameters, random seeds, and input hash.
- Data compliance and attribution requirements are written into the data source license manifest; StatsBomb Open Data derived products publicly displayed must attribute StatsBomb.

## Technology Defaults

Python, uv, DuckDB + Parquet, pandas, scikit-learn, Streamlit, Plotly, mplsoccer, pytest, Ruff. The frontend continues to use the static `frontend/` as the product shell; the tactical board can evaluate Canvas/SVG or lightweight canvas libraries, but before adding dependencies, you must first prove export, responsiveness, and maintainability benefits. PyTorch is already used for rating optimization/GPU scripts; if neural networks are brought into the main project, you must sync update `pyproject.toml`, lock file, training entry, model artifacts, and evaluation documentation. socceraction is a P2 planned dependency candidate; kloppy, floodlight, common-data-format-validator are only added to `pyproject.toml` after entering P6 and completing dependency evaluation.

## Verification Commands

```bash
uv run ruff check .
uv run pytest
uv run pytest tests/unit/test_rating_optimizer_validation.py
uv run pytest tests/unit/test_rating_optimizer_validation.py tests/unit/test_composite_objective.py tests/unit/test_player_rating_nn.py
uv run pytest tests/integration/ -q
PYTHONPATH=src uv run python -m scoutfootball info
PYTHONPATH=src uv run python -m scoutfootball validate
PYTHONPATH=src uv run python -m scoutfootball ingest
PYTHONPATH=src uv run python -m scoutfootball build-features
PYTHONPATH=src uv run python -m scoutfootball train
PYTHONPATH=src uv run python -m scoutfootball train-rating-nn
uv run streamlit run src/scoutfootball/app/streamlit_app.py
node --check frontend/app.js
# Only verifies STATIC fallback; real API/frontend uses `scoutfootball serve --port 8000` same-origin hosting
python3 -m http.server 8600 --directory frontend
```
