# ScoutFootball 参考索引

> 自动生成：请勿手工编辑。来源为 `data/project_manifest.json`；重新生成命令为 `PYTHONPATH=src uv run python scripts/generate_manifest.py`。

- manifest schema：`1.0.0`
- package version：`1.0.3`
- manifest generated_at：`2026-07-30T18:40:19.423545+00:00`
- content SHA-256：`d48a3c6dae0642c1909e0d54923a82341c576c0d74a7f1008718184ae946a7b9`

本页用于定位本地入口和已登记契约；它不证明 Parquet 内容已解码、样例具有完整覆盖，或线上部署当前可达。请运行相应的 preflight、契约检查和本地工作流后再作此类陈述。

## 支持的本地命令

- `uv sync`
- `uv run pytest`
- `uv run ruff check .`
- `uv run python -m scoutfootball info`
- `uv run python -m scoutfootball capabilities`
- `uv run python -m scoutfootball data-contracts`
- `uv run python -m scoutfootball list-adapters [--source S] [--capability C] [--json]`
- `uv run python -m scoutfootball adapter-compatibility [--source S] [--json]`
- `uv run python -m scoutfootball ingest`
- `uv run python -m scoutfootball build-features`
- `uv run python -m scoutfootball train`
- `uv run python -m scoutfootball train-rating-nn`
- `uv run python -m scoutfootball validate`
- `uv run python -m scoutfootball source-health`
- `uv run python -m scoutfootball inspect-raw-source`
- `uv run python -m scoutfootball reep-identity-lookup`
- `uv run python -m scoutfootball contract-quality`
- `uv run python -m scoutfootball model-admission`
- `uv run python -m scoutfootball research-health`
- `uv run python -m scoutfootball discard-model-run <run_id>`
- `uv run python -m scoutfootball reject-model-run <run_id> --decision <text>`
- `uv run python -m scoutfootball promote-model-run <run_id> --decision <text>`
- `uv run python -m scoutfootball rollback-model-run <backup_id> --decision <text>`
- `uv run python -m scoutfootball validate-decision-package <path>`
- `uv run python -m scoutfootball record-source-snapshot`
- `uv run python -m scoutfootball record-source-policy`
- `uv run python -m scoutfootball record-quality-audit`
- `uv run python -m scoutfootball record-quality-threshold`
- `uv run python -m scoutfootball preflight`
- `uv run python -m scoutfootball preflight --evidence-out <path>`
- `uv run python -m scoutfootball optimizer-preflight`
- `uv run python -m scoutfootball action-value`
- `uv run python -m scoutfootball action-value-matches`
- `uv run python -m scoutfootball export-ratings`
- `uv run python -m scoutfootball import-truth-labels`
- `uv run python -m scoutfootball import-transfermarkt-truth-labels`
- `uv run python -m scoutfootball transfermarkt-identity-review`
- `uv run python -m scoutfootball reconcile-transfermarkt-truth-labels`
- `uv run python -m scoutfootball audit-truth-labels`
- `uv run python -m scoutfootball audit-identity`
- `uv run python -m scoutfootball identity-registry-lookup --source S --source-id X`
- `uv run python -m scoutfootball identity-registry-append --source S --source-id X --canonical-id C --evidence E`
- `uv run python -m scoutfootball identity-registry-revoke --source S --source-id X --evidence E`
- `uv run python -m scoutfootball identity-registry-list [--source S]`
- `uv run python -m scoutfootball identity-registry-stats`
- `uv run python -m scoutfootball resolve-canonical-ids [--sample N]`
- `uv run python -m scoutfootball suggest-identity-mappings [--json]`
- `uv run python -m scoutfootball role-system-report [--json]`
- `uv run python -m scoutfootball cohort-preview [filters] [--json]`
- `uv run python -m scoutfootball backtest`
- `uv run python -m scoutfootball tune-predictions`
- `uv run python -m scoutfootball optimize-ensemble`
- `uv run python -m scoutfootball serve`
- `uv run python -m scoutfootball tournament`
- `uv run python -m scoutfootball create-brief`
- `uv run python -m scoutfootball list-briefs`
- `uv run python -m scoutfootball show-brief <brief_id>`
- `uv run python -m scoutfootball validate-brief <path>`
- `uv run python -m scoutfootball create-briefing`
- `uv run python -m scoutfootball list-briefings`
- `uv run python -m scoutfootball show-briefing <briefing_id>`
- `uv run python -m scoutfootball validate-briefing <path>`
- `uv run python -m scoutfootball create-dossier`
- `uv run python -m scoutfootball list-dossiers`
- `uv run python -m scoutfootball show-dossier <dossier_id>`
- `uv run python -m scoutfootball validate-dossier <path>`
- `uv run python -m scoutfootball create-review`
- `uv run python -m scoutfootball list-reviews`
- `uv run python -m scoutfootball show-review <review_id>`
- `uv run python -m scoutfootball validate-review <path>`
- `uv run python -m scoutfootball export-local-pack [--output <path>]`
- `uv run python -m scoutfootball import-local-pack [--from <path>] [--confirm]`
- `uv run streamlit run src/scoutfootball/app/streamlit_app.py`

## 能力登记

| ID | 领域 | 状态 | API | CLI | 前端视图 |
| --- | --- | --- | --- | --- | --- |
| pipeline.adapters | data_pipeline | delivered | /adapters, /adapters/compatibility | list-adapters, adapter-compatibility | — |
| pipeline.ingest | data_pipeline | delivered | — | ingest | — |
| pipeline.build_features | data_pipeline | delivered | — | build-features | — |
| pipeline.validate | data_pipeline | delivered | /health, /artifacts | validate, preflight, optimizer-preflight, source-health, inspect-raw-source, reep-identity-lookup, contract-quality, model-admission, research-health, discard-model-run, reject-model-run, promote-model-run, rollback-model-run, validate-decision-package, record-source-snapshot, record-source-policy, record-quality-audit, record-quality-threshold | — |
| ratings.training | player_ratings | delivered | — | train, train-rating-nn | — |
| ratings.export | player_ratings | delivered | /ratings, /ratings/meta, /ratings/snapshots | export-ratings | players, value |
| ratings.truth_labels | player_ratings | delivered | /reports/truth-labels, /reports/transfermarkt-identities | import-truth-labels, import-transfermarkt-truth-labels, transfermarkt-identity-review, reconcile-transfermarkt-truth-labels, audit-truth-labels | — |
| ratings.identity_audit | player_ratings | delivered | — | audit-identity | — |
| ratings.identity_registry | player_ratings | delivered | — | identity-registry-lookup, identity-registry-append, identity-registry-revoke, identity-registry-list, identity-registry-stats | — |
| ratings.canonical_resolver | player_ratings | delivered | — | resolve-canonical-ids | — |
| ratings.identity_suggester | player_ratings | delivered | — | suggest-identity-mappings | — |
| ratings.role_system | player_ratings | delivered | — | role-system-report | — |
| ratings.cohort | player_ratings | delivered | — | cohort-preview | — |
| predictions.match | match_predictions | delivered | /predictions/{home_team}/{away_team}, /predictions/meta, /predictions/ensemble/weights, /predictions/models/comparison, /predictions/staleness, /predictions/team-accuracy/{team_id}, /predictions/{home_team}/{away_team}/attribution, /predictions/{home_team}/{away_team}/attribution/ci, /predictions/{home_team}/{away_team}/ensemble-attribution, /predictions/{home_team}/{away_team}/ensemble-attribution/ci, /predictions/{home_team}/{away_team}/diagnostics, /predictions/{home_team}/{away_team}/h2h, /predictions/{home_team}/{away_team}/h2h-bias-correction, /predictions/{home_team}/{away_team}/momentum | backtest, tune-predictions, optimize-ensemble | matches |
| predictions.calibration | match_predictions | delivered | /predictions/calibration, /predictions/backtest, /predictions/tuning, /predictions/drift, /predictions/drift/timeline, /predictions/calibration/reliability, /predictions/calibration/scoreline, /predictions/calibration/comparison, /predictions/calibration/confidence-distribution, /predictions/calibration/error-analysis, /predictions/calibration/outcome-distribution, /predictions/calibration/temporal-validation, /predictions/calibration/probability-heatmap, /predictions/calibration/ci-plot, /predictions/calibration/ci-coverage, /predictions/calibration/ci-width, /predictions/calibration/fold-comparison, /predictions/calibration/league-errors, /predictions/calibration/feature-importance, /predictions/calibration/drift-heatmap, /predictions/calibration/error-clustering, /predictions/calibration/data-drift, /predictions/calibration/stress-test, /predictions/calibration/team-drift, /predictions/calibration/team-profile, /predictions/calibration/uncertainty, /predictions/calibration/profit-loss, /predictions/calibration/trajectory, /predictions/calibration/difficulty, /predictions/calibration/streaks, /predictions/calibration/report-card, /predictions/calibration/anomalies | backtest, tune-predictions | matches, calibration, backtest |
| predictions.value_bet | match_predictions | delivered | /predictions/{home_team}/{away_team}/value | — | matches |
| team.analysis | team_analysis | delivered | /teams, /teams/compare, /teams/strength, /teams/style-clusters, /teams/style-clusters/similarity, /teams/style-atlas, /teams/style-matchup, /teams/style-evolution, /teams/{team}/style-neighbors, /teams/{team}/style-percentiles, /teams/{team}/style-drift, /teams/{team}/style-drift-neighbors, /teams/cross-league-depth | — | teams, league |
| team.action_profile | team_analysis | delivered | /teams/action-profile, /teams/action-atlas, /teams/action-evolution, /teams/{team}/action-percentiles, /teams/{team}/action-similarity, /teams/cross-league-action | — | actions |
| league.season_projection | team_analysis | delivered | /league/season-projection, /league/form-table, /league/fixture-difficulty | — | league |
| player.comparison | player_analysis | delivered | /players, /players/compare, /players/compare-multi, /players/{player_name}, /players/{player_name}/similar, /players/{player_name}/career-trajectory, /player/{player_name}/profile | — | compare, players |
| player.style_fit | player_analysis | delivered | /players/{player_name}/style-fit, /players/{player_name}/role-fit, /players/{player_name}/peer-benchmark | — | players |
| position.analysis | player_analysis | delivered | /positions/depth-profile, /positions/style-evolution, /positions/action-profile, /positions/trend-overlay, /positions/{position_group}/style-drift, /positions/{position_group}/style-drift-neighbors, /positions/{position_group}/cross-league, /positions/{position_group}/action-similarity | — | players |
| action_value.core | action_value | delivered | /action-values, /action-values/evidence, /action-values/evidence/{player_id}, /action-values/players/{player_id}/context, /action-values/players/{player_id}/rating-links, /action-values/matches, /value-summary | action-value, action-value-matches | actions |
| action_value.position_similarity | action_value | delivered | /positions/{position_group}/action-similarity, /teams/cross-league-action | — | actions |
| scouting.targets | scouting | delivered | /teams/{team}/scouting-targets, /teams/{team}/scouting-style-match/{position_group}, /teams/{team}/scouting-dashboard, /teams/{team}/position-gap-report, /teams/style-clusters/recruits | — | scouting |
| scouting.watchlist | scouting | delivered | /scouting/risers-decliners, /watchlist, /shortlist, /review-queue | — | scouting |
| scouting.workspace | scouting | delivered | /scouting-workspaces, /scouting-workspaces/capabilities, /scouting-workspaces/latest, /scouting-workspaces/{workspace_id}, /scouting-workspaces/{workspace_id} (PUT) | — | scouting |
| recruitment.briefs | recruitment | delivered | /recruitment/briefs, /recruitment/briefs (POST), /recruitment/briefs/{brief_id}, /recruitment/briefs/{brief_id}/backups, /recruitment/briefs/{brief_id}/backups/{backup_filename}, /recruitment/briefs/{brief_id}/diff, /recruitment/briefs/{brief_id}/restore (POST), /recruitment/contracts | create-brief, list-briefs, show-brief, validate-brief | — |
| recruitment.dossiers | recruitment | delivered | /recruitment/dossiers, /recruitment/dossiers (POST), /recruitment/dossiers/{dossier_id}, /recruitment/dossiers/{dossier_id} (PUT), /recruitment/dossiers/{dossier_id}/backups, /recruitment/dossiers/{dossier_id}/backups/{backup_filename}, /recruitment/dossiers/{dossier_id}/diff, /recruitment/dossiers/{dossier_id}/restore (POST) | create-dossier, list-dossiers, show-dossier, validate-dossier | — |
| opposition.briefings | opposition | delivered | /opposition/briefs, /opposition/briefs (POST), /opposition/briefs/{briefing_id}, /opposition/briefs/{briefing_id} (PUT), /opposition/briefs/{briefing_id}/backups, /opposition/briefs/{briefing_id}/backups/{backup_filename}, /opposition/briefs/{briefing_id}/diff, /opposition/briefs/{briefing_id}/restore (POST), /opposition/contracts | create-briefing, list-briefings, show-briefing, validate-briefing | — |
| opposition.post_match_reviews | opposition | delivered | /opposition/reviews, /opposition/reviews (POST), /opposition/reviews/{review_id}, /opposition/reviews/{review_id} (PUT), /opposition/reviews/{review_id}/backups, /opposition/reviews/{review_id}/backups/{backup_filename}, /opposition/reviews/{review_id}/diff, /opposition/reviews/{review_id}/restore (POST) | create-review, list-reviews, show-review, validate-review | — |
| worldcup.tournament | world_cup | delivered | /world-cup/groups, /world-cup/schedule, /worldcup/teams, /world-cup/contracts, /world-cup/tournament/summary, /world-cup/tournament/standings, /world-cup/tournament/standings-probabilities, /world-cup/tournament/overall-leaderboard, /world-cup/tournament/qualification-impact, /world-cup/tournament/tiebreak-diagnostics, /world-cup/tournament/matches, /world-cup/tournament/match-predictions, /world-cup/tournament/match-impact, /world-cup/tournament/top-matches, /world-cup/tournament/scenarios/{team}, /world-cup/tournament/group-simulation, /world-cup/tournament/export, /world-cup/tournament/import (POST), /world-cup/tournament/import/preview (POST), /world-cup/tournament/result (POST/DELETE), /world-cup/tournament/reset (POST), /world-cup/match-briefings/{home}/{away}/spotlight, /world-cup/teams/{team}/form-trend | tournament, tournament show, tournament standings, tournament apply, tournament clear, tournament reset, tournament matches, tournament scenarios, tournament qualification, tournament tiebreaks | wc_schedule, wc_knockout, wc_tournament |
| worldcup.knockout | world_cup | delivered | /world-cup/knockout, /world-cup/tournament/knockout, /world-cup/tournament/knockout/{match_id}/briefing, /world-cup/tournament/knockout/{match_id}/review, /world-cup/tournament/knockout/reviews, /world-cup/tournament/knockout/probabilities, /world-cup/tournament/knockout/scenarios/{team}, /world-cup/tournament/knockout/match-impact, /world-cup/tournament/knockout/generate (POST), /world-cup/tournament/knockout/result (POST/DELETE) | tournament knockout, tournament knockout generate, tournament knockout show, tournament knockout apply, tournament knockout clear | wc_knockout, wc_tournament |
| worldcup.predictions | world_cup | delivered | /world-cup/predictions, /world-cup/predictions/{home_team}/{away_team}, /world-cup/match-briefings/{home_team}/{away_team}, /world-cup/outlook/{team} | — | wc_probability, wc_compare |
| worldcup.squads | world_cup | delivered | /world-cup/squads/{team}, /world-cup/squads/{team}/scouting-needs, /world-cup/squad-balance-comparison/{team_a}/{team_b} | — | wc_squads, wc_compare |
| api.server | infrastructure | delivered | /health, /health/detailed, /health/research, /license, /search, /local-pack/export, /local-pack/import (POST), /tactical-board/capabilities, /tactical-board/export/mp4 (POST) | serve | — |
| local.portable_pack | infrastructure | delivered | /local-pack/export, /local-pack/import (POST) | export-local-pack, import-local-pack | — |
| frontend.analyst_console | infrastructure | delivered | — | — | overview, players, compare, value, matches, teams, league, scouting, actions, reports, tactical, wc_schedule, wc_squads, wc_compare, wc_probability, wc_knockout, wc_tournament, license, data, calibration, backtest, help, workflow, versions |
| data.artifacts | infrastructure | delivered | /artifacts, /model-runs, /reports/model-runs, /reports/model-runs/{run_id} | info, capabilities, data-contracts | data |

## 数据契约登记

| Artifact | 层 | 状态 | recorded | 来源 / 许可 | 主键 |
| --- | --- | --- | --- | --- | --- |
| raw/statsbomb_open | raw | delivered | True | statsbomb_open / StatsBomb Open Data User Protocol | — |
| raw/football_data | raw | delivered | True | football_data / Football-Data.co.uk non-commercial | — |
| raw/clubelo | raw | delivered | True | clubelo / ClubElo public data | — |
| raw/understat | raw | delivered | True | understat / Understat public data | — |
| raw/fbref | raw | delivered | True | fbref / FBref personal research only | — |
| raw/transfermarkt_manual | raw | delivered | True | transfermarkt_manual / Transfermarkt manual import only | — |
| raw/reep | raw | delivered | True | reep / CC0 1.0 Universal | — |
| competition | silver | delivered | True |  | competition_id |
| season | silver | delivered | True |  | season_id |
| team | silver | delivered | True |  | team_id |
| player | silver | delivered | True |  | player_id |
| match | silver | delivered | True |  | match_id |
| team_match | silver | delivered | True |  | match_id, team_id |
| player_match | silver | delivered | True |  | match_id, player_id |
| event | silver | delivered | True |  | match_id, event_id |
| bridge_source_team | silver | delivered | True |  | source_name, source_team_id |
| bridge_source_player | silver | delivered | True |  | source_name, source_player_id |
| market_snapshot | silver | delivered | True |  | player_id, snapshot_date |
| gold/marts | gold | delivered | True |  | — |
| gold/feature_store | gold | delivered | True |  | — |
| models/training_sets | models | delivered | True |  | — |
| models/artifacts | models | delivered | True |  | — |
| models/oof_predictions | models | delivered | True |  | — |
| reports/html | reports | delivered | True |  | — |
| reports/pdf | reports | delivered | True |  | — |
| logs/ingestion | logs | delivered | True |  | — |
| logs/validation | logs | delivered | True |  | — |
