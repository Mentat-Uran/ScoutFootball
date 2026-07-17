# ScoutFootball 参考索引

> 自动生成：请勿手工编辑。来源为 `data/project_manifest.json`；重新生成命令为 `PYTHONPATH=src uv run python scripts/generate_manifest.py`。

- manifest schema：`1.0.0`
- package version：`1.0.3`
- manifest generated_at：`2026-07-17T14:56:23.413180+00:00`
- content SHA-256：`ae81fcdb3c7a13b52250cc699a20f98c9dd8ebac312b7f647ab75d32bb918994`

本页用于定位本地入口和已登记契约；它不证明 Parquet 内容已解码、样例具有完整覆盖，或线上部署当前可达。请运行相应的 preflight、契约检查和本地工作流后再作此类陈述。

## 支持的本地命令

- `uv sync`
- `uv run pytest`
- `uv run ruff check .`
- `uv run python -m scoutfootball info`
- `uv run python -m scoutfootball capabilities`
- `uv run python -m scoutfootball data-contracts`
- `uv run python -m scoutfootball ingest`
- `uv run python -m scoutfootball build-features`
- `uv run python -m scoutfootball train`
- `uv run python -m scoutfootball train-rating-nn`
- `uv run python -m scoutfootball validate`
- `uv run python -m scoutfootball source-health`
- `uv run python -m scoutfootball inspect-raw-source`
- `uv run python -m scoutfootball contract-quality`
- `uv run python -m scoutfootball model-admission`
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
- `uv run python -m scoutfootball backtest`
- `uv run python -m scoutfootball tune-predictions`
- `uv run python -m scoutfootball optimize-ensemble`
- `uv run python -m scoutfootball serve`
- `uv run python -m scoutfootball tournament`
- `uv run streamlit run src/scoutfootball/app/streamlit_app.py`

## 能力登记

| ID | 领域 | 状态 | API | CLI | 前端视图 |
| --- | --- | --- | --- | --- | --- |
| pipeline.ingest | data_pipeline | delivered | — | ingest | — |
| pipeline.build_features | data_pipeline | delivered | — | build-features | — |
| pipeline.validate | data_pipeline | delivered | /health, /artifacts | validate, preflight, optimizer-preflight, source-health, inspect-raw-source, contract-quality, model-admission, discard-model-run, reject-model-run, promote-model-run, rollback-model-run, validate-decision-package, record-source-snapshot, record-source-policy, record-quality-audit, record-quality-threshold | — |
| ratings.training | player_ratings | delivered | — | train, train-rating-nn | — |
| ratings.export | player_ratings | delivered | /ratings, /ratings/meta, /ratings/snapshots | export-ratings | players, value |
| ratings.truth_labels | player_ratings | delivered | /reports/truth-labels, /reports/transfermarkt-identities | import-truth-labels, import-transfermarkt-truth-labels, transfermarkt-identity-review, reconcile-transfermarkt-truth-labels, audit-truth-labels | — |
| predictions.match | match_predictions | delivered | /predictions/{home}/{away}, /predictions/meta, /predictions/ensemble/weights, /predictions/{home}/{away}/attribution, /predictions/{home}/{away}/diagnostics | backtest, tune-predictions, optimize-ensemble | matches |
| predictions.calibration | match_predictions | delivered | /predictions/calibration, /predictions/backtest, /predictions/tuning, /predictions/drift, /predictions/calibration/reliability, /predictions/calibration/scoreline | backtest, tune-predictions | matches, calibration, backtest |
| predictions.value_bet | match_predictions | delivered | /predictions/{home}/{away}/value | — | matches |
| team.analysis | team_analysis | delivered | /teams/compare, /teams/strength, /teams/style-clusters, /teams/style-atlas, /teams/style-matchup, /teams/{team}/style-neighbors, /teams/{team}/style-drift, /teams/style-evolution | — | teams, league |
| team.action_profile | team_analysis | delivered | /teams/action-profile, /teams/action-atlas, /teams/action-evolution, /teams/{team}/action-percentiles, /teams/{team}/action-similarity, /teams/cross-league-action | — | actions |
| league.season_projection | team_analysis | delivered | /league/season-projection, /league/form-table, /league/fixture-difficulty | — | league |
| player.comparison | player_analysis | delivered | /players/compare, /players/compare-multi, /players/{player}/similar, /players/{player}/career-trajectory | — | compare, players |
| player.style_fit | player_analysis | delivered | /players/{player}/style-fit, /players/{player}/role-fit, /players/{player}/peer-benchmark, /style-neighbors, /style-drift-neighbors | — | players |
| position.analysis | player_analysis | delivered | /positions/depth-profile, /positions/style-evolution, /positions/action-profile, /positions/trend-overlay, /positions/{position}/style-drift, /positions/{position}/cross-league, /positions/{position}/action-similarity | — | players |
| action_value.core | action_value | delivered | /action-values, /action-values/evidence, /action-values/evidence/{player}, /action-values/players/{player}/context, /action-values/players/{player}/rating-links, /action-values/matches | action-value, action-value-matches | actions |
| action_value.position_similarity | action_value | delivered | /positions/{position}/action-similarity, /teams/cross-league-action, /cross-league-action-comparison | — | actions |
| scouting.targets | scouting | delivered | /teams/{team}/scouting-targets, /teams/{team}/scouting-style-match/{position}, /teams/{team}/scouting-dashboard, /teams/{team}/position-gap-report, /teams/style-clusters/recruits | — | scouting |
| scouting.watchlist | scouting | delivered | /scouting/risers-decliners, /watchlist, /shortlist, /review-queue | — | scouting |
| scouting.workspace | scouting | delivered | /scouting-workspaces, /scouting-workspaces/capabilities, /scouting-workspaces/latest, /scouting-workspaces/{id}, /scouting-workspaces/{id} (PUT) | — | scouting |
| worldcup.tournament | world_cup | delivered | /world-cup/groups, /world-cup/schedule, /world-cup/teams, /world-cup/tournament-summary, /world-cup/tournament-standings, /world-cup/tournament-matches, /world-cup/tournament-scenarios | tournament, tournament show, tournament standings, tournament apply, tournament matches, tournament scenarios | wc_schedule, wc_knockout, wc_tournament |
| worldcup.knockout | world_cup | delivered | /world-cup/knockout, /world-cup/knockout-bracket, /world-cup/knockout-probabilities, /world-cup/knockout-scenarios | tournament knockout, tournament knockout generate, tournament knockout show, tournament knockout apply | wc_knockout, wc_tournament |
| worldcup.predictions | world_cup | delivered | /world-cup/predictions, /world-cup/standings-probabilities, /world-cup/qualification-impact, /world-cup/tournament-match-predictions, /world-cup/match-prediction | — | wc_probability, wc_compare |
| worldcup.squads | world_cup | delivered | /world-cup/squads/{team}, /world-cup/squad-balance-comparison/{a}/{b}, /world-cup/squads/{team}/scouting-needs | — | wc_squads, wc_compare |
| api.server | infrastructure | delivered | /health, /license | serve | — |
| frontend.analyst_console | infrastructure | delivered | — | — | overview, players, compare, value, matches, teams, league, scouting, actions, reports, tactical, wc_schedule, wc_squads, wc_compare, wc_probability, wc_knockout, wc_tournament, license, data, calibration, backtest, help |
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
