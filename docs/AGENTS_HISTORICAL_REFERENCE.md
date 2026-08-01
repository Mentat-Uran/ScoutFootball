# AGENTS 历史与参考记录

> 本文件由 `scoutlab/AGENTS.md` 拆分而来，承载容易过时的历史数字、旧阶段记录与外部调研基础。**它不是当前任务或能力的真源**——当前任务以 [`TASKS.md`](TASKS.md) 顶部为准，能力边界以 [`CAPABILITIES.md`](CAPABILITIES.md) 为准，路线依赖以 [`ROADMAP.md`](ROADMAP.md) 为准，项目定位以 [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md) 为准。
>
> 以下数字来自不同时间点的开发记录，可能彼此冲突或已失效；只有当锁定运行时完成内容级读取、schema 校验和关键统计核验后，才能将其称为“当前可核验”。

## 1. 本地缓存历史记录

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

## 2. 适配器实现状态

新适配器（已实现，部分需要特定环境才能运行）：

- SofaScore, SoFIFA, WhoScored, Capology: require Chrome + Selenium, recommended to run on Windows GPU server.
- API-Football: requires `API_FOOTBALL_KEY` environment variable, gracefully degrades without a key.
- Transfermarkt-datasets: requires manual download of DuckDB file placed in `data/raw/transfermarkt_datasets/`.
- FBref extended leagues + 7 new stat_types: require Chrome + Selenium, recommended to run on Windows GPU server.
- StatsBomb bulk download: no special requirements, but large download volume requires a stable network environment.
- Running soccerdata scripts requires setting `SOCCERDATA_DIR=./data/soccerdata`.

## 3. 评级系统校准阶段历史

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

## 4. 后续架构方向（历史十层描述）

本节作为历史背景保留；新的依赖节点、启动条件和退出门禁仅以 [`ROADMAP.md`](ROADMAP.md) 为准，路线图不绑定年份或期限。

未来更新按十层推进。前七层是当前主干，八到十层延伸到 scouting 工作流、预测校准和空间/视频研究，应在 P0–P4 稳定后逐步推进：

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

## 5. 外部研究基础

- socceraction: main reference for SPADL/atomic-SPADL, xT, VAEP, Atomic-VAEP.
- StatsBomb Open Data: first primary source for the event layer; public display of derived products must attribute the data source.
- mplsoccer: football-specific visualization library, currently integrated.
- Electronic tactical board cases: Tactico, DrawTactics, TacticSlate, Coach Tactic Board, Soccer Tactic Board, Metrica Tactical Boards, FC Tactix, TacticalPad, TacticalBoards; common features are formation/player dragging, red/blue dual teams, jersey number/name/role, hover or click player info, free brush/eraser, arrows/regions/trajectories, training equipment, keyframe or path animation, demo playback, PNG/PDF/WebM/MP4/GIF export, sharing, folders/templates, 2D/3D or video telestration workflows.
- kloppy, floodlight, Common Data Format: only as long-term references for cross-vendor event/tracking schemas.
- VAEP, xT vs VAEP, PlayeRank, combined player rating, xG finishing bias, and Dixon-Coles papers: correspond to action value, model comparison, in-role rating, hybrid rating, finishing shrinkage, and score prediction baseline, respectively.

更系统的行业工具与研究方向见 [`FOOTBALL_TOOLING_LANDSCAPE_2026.md`](FOOTBALL_TOOLING_LANDSCAPE_2026.md)。

## 6. 历史优先级（不再是当前队列）

以下 P0–P8 是旧开发阶段记录。当前任务只从 [`TASKS.md`](TASKS.md) 顶部选取；不要因本节编号继续旧路线。

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
