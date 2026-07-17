# Data Contracts

This document defines the schema contracts for all data artifacts in
ScoutFootball. Changes to these schemas require updating this document,
the downstream consumers, and the validation tests.

---

## 1. StatsBomb Events Schema

**File**: `data/raw/statsbomb_open/events_all.parquet`
**Source**: StatsBomb Open Data (free for research, must attribute)
**Coverage**: Sample only (3 matches, ~12K events). NOT full league coverage.

| Column | Type | Description |
|---|---|---|
| match_id | str | StatsBomb match identifier |
| event_id | int | Unique event identifier within match |
| index | int | Event sequence index |
| period | int | 1=1st half, 2=2nd half, etc. |
| timestamp | str | Time within match (HH:MM:SS.mmm) |
| minute | int | Minute of event |
| second | int | Second within minute |
| possession | int | Possession sequence number |
| duration | float | Duration of event in seconds |
| type_id | int | StatsBomb event type ID |
| event_type | str | Event type name (Pass, Shot, Carry, etc.) |
| possession_team_id | int | Team in possession |
| possession_team_name | str | Team name in possession |
| team_id | int | Team performing action |
| team_name | str | Team name |
| player_id | int | StatsBomb player ID |
| player_name | str | Player name |
| location | list[float] | [x, y] start location (120x80 pitch) |
| pass_end_location | list[float] | [x, y] pass end location |
| carry_end_location | list[float] | [x, y] carry end location |
| shot_end_location | list[float] | [x, y] shot end location |
| shot_statsbomb_xg | float | StatsBomb xG for shot |
| pass_recipient_id | int | Pass recipient player ID |
| pass_recipient_name | str | Pass recipient name |
| pass_length | float | Pass length in yards |
| pass_angle | float | Pass angle in radians |
| pass_outcome_id | int | Pass outcome ID (null=complete) |
| pass_outcome_name | str | Pass outcome name |
| shot_outcome_id | int | Shot outcome ID |
| shot_outcome_name | str | Shot outcome name |
| ... | ... | Additional qualifier columns |

**Coordinate system**: StatsBomb uses 120x80 (x: 0=own goal, 120=opponent goal).

---

## 2. Internal Actions Schema

**Defined in**: `src/scoutfootball/action_value/schema.py`
**Coordinate system**: 0-100 normalized (x: left-to-right, y: bottom-to-top)
**Direction**: Always attack-to-defense (left-to-right after normalization)

| Field | Type | Description |
|---|---|---|
| action_id | int | Unique ID within match |
| provider_action_id | str | Original action ID from source |
| match_id | str | Match identifier |
| team_id | str | Team identifier |
| player_id | str | Player identifier |
| period | int | 1=1st half, 2=2nd half |
| minute | int | Minute of action |
| second | int | Second within minute |
| action_type | ActionType | Standardized type (SPADL-compatible) |
| result | ActionResult | Outcome: success/failure/unknown |
| start_x | float | Start x coordinate (0-100) |
| start_y | float | Start y coordinate (0-100) |
| end_x | float | End x coordinate (0-100) |
| end_y | float | End y coordinate (0-100) |
| body_part | str | Body part used |
| qualifier | dict | Additional metadata |
| source | str | Data provider name |
| source_coverage | str | Coverage flag: full/partial/sample |

**ActionTypes**: pass, dribble, shot, freeze, take_on, clearance,
interception, tackle, block, goalkeeper, receipt, carry, unknown

**ActionResults**: success, failure, unknown

---

## 3. SPADL Mapping

StatsBomb events are converted to InternalAction via
`src/scoutfootball/action_value/spadl_adapter.py`.

| StatsBomb Type | InternalAction Type |
|---|---|
| Pass | pass |
| Carry | carry |
| Shot | shot |
| Dribble | dribble |
| Ball Receipt* | receipt |
| Clearance | clearance |
| Interception | interception |
| Duel | tackle |
| Block | block |
| Goalkeeper | goalkeeper |
| Take On | take_on |
| Ball Recovery | clearance |
| Miscontrol | failure (pass) |
| Foul Committed | freeze |

Coordinate transformation: `x_internal = x_statsbomb / 120 * 100`

---

## 4. player_ratings_optimized.parquet

**File**: `data/gold/feature_store/player_ratings_optimized.parquet`
**Rows**: ~30,000 (all seasons, all leagues)
**Source**: Rating optimizer GPU pipeline

| Column | Type | Description |
|---|---|---|
| player | str | Player name |
| team | str | Club team name |
| league | str | League name (Premier League, La Liga, etc.) |
| season | str | Season code (e.g., "2425") |
| source_position | str | Raw position string from source |
| sub_position | str | Mapped position group (GK/CB/FB/DM/CM/AM/W/ST) |
| pos_idx | int | Position index (0-7) |
| position_source | str | Position mapping source |
| position_confidence | str | Position mapping confidence (low/medium/high) |
| matches | float | Number of matches played |
| starts | float | Number of starts |
| minutes | float | Total minutes played |
| npg_p90 | float | Non-penalty goals per 90 minutes |
| assists_p90 | float | Assists per 90 minutes |
| g_a_volume | float | Total goals + assists |
| tackles_p90 | float | Tackles per 90 |
| interceptions_p90 | float | Interceptions per 90 |
| crosses_p90 | float | Crosses per 90 |
| fouls_drawn_p90 | float | Fouls drawn per 90 |
| fouls_p90 | float | Fouls committed per 90 |
| defense_composite | float | Defense composite score (0-100) |
| possession_composite | float | Possession composite score (0-100) |
| season_rank | int | Rank within season |
| npg_trend | float | Attack trend metric |
| def_trend | float | Defense trend metric |
| pos_trend | float | Possession trend metric |
| experience_factor | float | Experience adjustment factor |
| low_appearance | bool | True if <20 matches (penalized) |
| optimized_score | float | Final optimized rating (0-100) |
| same_position_score | float | Rating within same position group (0-100) |

---

## 5. rating_feature_matrix.parquet

**File**: `data/gold/feature_store/rating_feature_matrix.parquet`
**Purpose**: Input features for the rating optimizer

| Column | Type | Description |
|---|---|---|
| player_id | str | Player identifier |
| season_id | str | Season identifier |
| goals | int | Goals scored |
| assists | int | Assists |
| shots | int | Total shots |
| shots_on_target | int | Shots on target |
| minutes_played | int | Total minutes |
| starts | int | Number of starts |
| npxg | float | Non-penalty expected goals |
| xa | float | Expected assists |
| available_flag | bool | Data availability flag |
| tackles | int | Tackles made |
| passes | int | Passes attempted |
| xT_added | float | Expected threat added |
| player_name | str | Player name |
| team_id | str | Team identifier |
| team_name | str | Team name |
| competition_id | str | Competition identifier |
| position_group | str | Mapped position group |
| defense_missing | bool | Defense data missing flag |
| possession_missing | bool | Possession data missing flag |
| xT_VAEP_missing | bool | xT/VAEP data missing flag |
| goalkeeper_missing | bool | GK data missing flag |
| finishing_raw | float | Raw finishing metric |
| finishing_shrunk | float | Shrunk finishing metric |
| statsbomb_open_source_covered | bool | StatsBomb coverage flag |
| fbref_source_covered | bool | FBref coverage flag |
| understat_source_covered | bool | Understat historical season-proxy coverage flag |
| has_expected_metrics | bool | xG/xA data available |
| has_ball_value_data | bool | Ball value data available |

---

### Historical Understat season proxies

`data/raw/understat/players_10seasons.parquet` may extend `player_match` and
`rating_feature_matrix` for Big Five seasons that are not present in the local
FBref proxy. These rows use `source_name="understat"` and
`data_granularity="season_proxy"`; they are aggregate season statistics, not
match events. The pipeline excludes seasons already covered by FBref and does
not import RFPL rows because this rating route has no aligned team-results
target for that competition.

### Optimizer optional-artifact status

Optimizer run metadata may include `data_coverage.artifact_statuses`, one item
per raw input with `source`, `status`, and `path`; an unreadable optional file
also records `error_type` and a bounded error message. `fbref_misc`,
`fbref_shooting`, and `understat` are optional enrichment inputs: `missing` or
`unreadable` means their dependent fields fall back to explicit missing-data
handling. The FBref standard table and Football-Data results remain required;
a run cannot be interpreted as complete if either cannot be read.

---

## 6. player_truth_labels.parquet

**File**: `data/gold/feature_store/player_truth_labels.parquet`
**Purpose**: Ground truth labels for rating validation

| Column | Type | Description |
|---|---|---|
| player_id | str | Player identifier |
| season | str | Season code |
| label_source | str | Source of truth label (see allowed values below) |
| label_confidence | str | Confidence in label (low/medium/high) |
| label_value | float | Label value |
| as_of_date | str | Date label was assigned (YYYY-MM-DD) |
| position_scope | str | Position scope for label |
| manual_review_flag | bool | Requires manual review |

**Allowed `label_source` values**:
- `transfermarkt_value` — Transfermarkt market value tiers
- `award` — individual awards (Ballon d'Or, best XI, etc.)
- `expert_tier` — expert/analyst tier classification
- `manual_calibration` — manual calibration set
- `scouting_review` — labels derived from scouting workspace review decisions
  (approved → 1.0/high, rejected → 0.0/medium). Populated via
  `workspace_to_truth_labels()` + CLI `import-truth-labels --workspace`.

**Supervision source policy (`source-policy-v1`)**: `transfermarkt_value`,
`award`, `manual_calibration`, and `scouting_review` are eligible for the NN
candidate and optimizer truth-anchor. `expert_tier` is excluded because the
current local tier import was derived from `optimized_score`, so using it would
create a circular target. Eligibility is a guardrail, not proof that a manual
or scouting label was collected independently.

The audit also reports `temporal`: for eligible sources, a label is
temporally eligible only when its `as_of_date` is on or before the conservative
May 31 end date of its compact season code. Post-season snapshots and malformed
dates remain visible as audit findings; this date check alone does not prove
that a label was causally collected.

Use `scoutfootball audit-truth-labels` or `GET /reports/truth-labels` to see
the exact row/source counts used by the policy. The current tracked artifact
has no supervision-eligible rows; training and truth anchoring must remain
skipped until independent labels are imported.

**Manual Transfermarkt import**: only a local CSV or Parquet snapshot is
accepted; this project does not scrape Transfermarkt. Use
`scoutfootball import-transfermarkt-truth-labels --snapshot <file> --season <YYZZ> --dry-run`
to validate the source date, show the source-scoped replacement count, preview
name-and-season resolution against the local rating matrix, and inspect the
temporal audit without writing. A real import preserves each source
`snapshot_date` as `as_of_date` by default. `--as-of-date YYYY-MM-DD` is an
explicit provenance override, not a way to make a post-season value appear to
have been known earlier. Re-imports replace only the same
`player_id + season + label_source` key; labels from other sources remain.

Before writing labels, the import resolves each snapshot row against the
selected season of `rating_feature_matrix.parquet`. Only deterministic
name/team/season or unique-name/season matches become labels with canonical
`player_id`s. Team conflicts, ambiguous same-name candidates, and unmatched
rows are excluded from supervision and written to
`transfermarkt_identity_report.json` for review. `GET
/reports/transfermarkt-identities` exposes that local report; it is an audit
of the current matrix, not a cross-provider identity authority.

`scoutfootball transfermarkt-identity-review` records an explicit local
`confirmed`, `rejected`, or `revoked` decision in an append-only JSONL ledger.
Confirmation is accepted only for an ID already present in that report row's
candidate set. On a later import, `--identity-ledger <path>` consumes only
decisions whose snapshot SHA-256, feature-matrix SHA-256, season, and source
row all match the current inputs. A revocation makes a prior manual choice
ineligible for subsequent imports. Each non-empty import also writes a local
append-only `transfermarkt_truth_label_import_ledger.jsonl` beside the output
unless `--label-ledger` selects another path. It records the input hashes,
source row, resolved ID, identity method, label key, and a fingerprint of the
exact row written; it never copies the source snapshot.

`scoutfootball reconcile-transfermarkt-truth-labels --identity-ledger <path>
--label-ledger <path>` is preview-only by default. After a revocation it lists
only labels whose ledger record proves they came from that manual confirmation
and whose current row fingerprint still matches. `--apply` atomically removes
only those proven rows. Historical labels without this new import ledger, rows
replaced by a later import, and labels from another source remain untouched and
are reported for maintainer review rather than silently deleted.

Both the dry-run summary and the persisted identity report include SHA-256 and
byte size for the explicitly supplied snapshot and local feature matrix. These
fingerprints identify the exact input files without uploading or copying them;
they do not turn an unrecorded historical snapshot into an earlier `as_of`.

---

## 7. team_match.parquet

**File**: `data/gold/feature_store/team_match.parquet`
**Rows**: ~10,000
**Source**: Football-Data.co.uk match results

| Column | Type | Description |
|---|---|---|
| match_id | str | Match identifier |
| match_date | str | Match date (YYYY-MM-DD) |
| competition_id | str | Competition identifier |
| season_id | str | Season identifier |
| team_id | str | Team identifier |
| team_name | str | Team name |
| opponent_team_id | str | Opponent identifier |
| opponent_team_name | str | Opponent name |
| is_home | bool | Home team flag |
| goals_for | int | Goals scored |
| goals_against | int | Goals conceded |
| goal_diff | int | Goal difference |
| result_points | int | Points earned (3/1/0) |
| shots | int | Shots taken |
| has_shots_data | bool | Shot data available flag |
| shots_on_target | int | Shots on target |
| has_shots_on_target_data | bool | SOT data available flag |
| xg | float | Expected goals for |
| xg_against | float | Expected goals against |
| has_xg_data | bool | xG data available flag |
| rest_days | int | Days since last match |
| elo_pre | float | ELO rating before match |
| opponent_elo_pre | float | Opponent ELO before match |
| elo_diff | float | ELO difference |

---

## 8. player_value_metrics.parquet

**File**: `data/gold/feature_store/player_value_metrics.parquet`
**Source**: StatsBomb Open Data sample only
**Coverage**: ~10 sample players from 3 matches

| Column | Type | Description |
|---|---|---|
| player_id | str | Player identifier |
| player_name | str | Player name |
| team_id | str | Team identifier |
| estimated_minutes | float | Estimated playing time |
| n_matches | int | Number of matches |
| shots | int | Total shots |
| shots_per_90 | float | Shots per 90 minutes |
| xG_total | float | Total expected goals |
| xG_per_90 | float | xG per 90 minutes |
| goals | int | Actual goals |
| goals_per_90 | float | Goals per 90 |
| finishing_delta | float | Goals minus xG |
| passes_per_90 | float | Passes per 90 |
| pass_completion_rate | float | Pass completion rate |
| forward_pass_rate | float | Forward pass rate |
| total_xt | float | Total xT accumulated |
| xT_per_90 | float | xT per 90 minutes |
| tackles_per_90 | float | Tackles per 90 |
| interceptions_per_90 | float | Interceptions per 90 |
| blocks_per_90 | float | Blocks per 90 |
| duel_win_rate | float | Duel win rate |
| duels_per_90 | float | Duels per 90 |
| touches_per_90 | float | Touches per 90 |
| progressive_carries_per_90 | float | Progressive carries per 90 |
| final_third_touches_per_90 | float | Final third touches per 90 |
| penalty_area_touches_per_90 | float | Penalty area touches per 90 |
| composite_score | float | Composite action value score |
| source | str | Data source |
| source_attribution | str | Attribution text |
| coverage_note | str | Coverage limitation note |

---

## 9. API Endpoint Contracts

### GET /health
Returns server health status.

**Response**: `{ status, data_source, version }`

### GET /ratings
Returns player ratings with optional filters.

**Query params**: `position`, `league`, `team`, `season`, `limit`
**Response**: `{ count, players: [...] }`

### GET /players/{player_name}
Returns detailed player profile with fuzzy search support.

**Query params**:
- `season` (str, optional): Filter by season
- `position_group` (str, optional): Filter by position group
- `limit` (int, default=50): Pagination limit for fuzzy matches
- `offset` (int, default=0): Pagination offset for fuzzy matches
- `format` (str, default="json"): Response format ("json" or "csv")

**Response** (exact match):
```json
{
  "player": "string",
  "found": true,
  "team": "string",
  "league": "string",
  "season": "string",
  "position_group": "string",
  "optimized_score": 85.0,
  "minutes": 2500,
  "matches": 30,
  "low_appearance": false,
  "confidence_level": "HIGH",
  "confidence_reason": "adequate minutes, matches, and peer pool",
  "npg_p90": 0.5,
  "assists_p90": 0.3,
  "defense_composite": 45.0,
  "possession_composite": 60.0,
  "radar": [80.0, 60.0, 45.0, 92.0, 85.0],
  "seasons": [
    { "season": "2425", "team": "...", "league": "...",
      "position_group": "...", "optimized_score": 85.0, "minutes": 2500 }
  ],
  "position_explanation": {
    "attack": { "raw_score", "percentile_rank", "contribution", "confidence" },
    "defense": { "raw_score", "percentile_rank", "contribution", "confidence" },
    "possession": { "raw_score", "percentile_rank", "contribution", "confidence" },
    "availability": { "raw_score", "percentile_rank", "contribution", "confidence" },
    "quality": { "raw_score", "percentile_rank", "contribution", "confidence" },
    "xT": {
      "xT_per_90": 0.5,
      "percentile_rank": 80.0,
      "contribution": 16.7,
      "confidence": "LOW"
    }
  },
  "xt_summary": {
    "available": true,
    "xT_per_90": 0.5,
    "xT_total": 12.5,
    "xT_percentile": 80.0,
    "xT_contribution": 16.7,
    "coverage_note": "StatsBomb Open Data sample only"
  }
}
```

**Response** (fuzzy match, multiple players):
```json
{
  "player": "search_term",
  "found": true,
  "fuzzy_match": true,
  "total": 15,
  "offset": 0,
  "limit": 50,
  "players": [
    { "player", "found", "team", "league", "season",
      "position_group", "optimized_score", "minutes" }
  ]
}
```

### GET /predictions/calibration
Returns calibration metrics for match prediction models.

**Response**:
```json
{
  "dixon_coles": {
    "status": "ok",
    "log_loss_exact": 2.1,
    "brier_1x2": 0.55,
    "rps_1x2": 0.22,
    "n_matches": 1000
  },
  "poisson": { "status", "log_loss_exact", "brier_1x2", "rps_1x2", "n_matches" },
  "low_score_breakdown": [
    { "score_bucket": "0-0", "n_matches": 100,
      "actual_pct": 10.0, "mean_predicted_pct": 8.0, "calibration_error": 2.0 }
  ],
  "calibration_plot": [
    { "bin_center": 0.15, "n_matches": 200,
      "mean_predicted": 0.14, "mean_actual": 0.16 }
  ],
  "league_coverage": [
    { "league": "Premier League", "n_matches": 380,
      "mean_log_loss": 2.1, "mean_brier": 0.55 }
  ]
}
```

### GET /predictions/{home_team}/{away_team}
Match prediction between two teams.

**Query params**: `model` ("poisson", "dixon_coles", "form", or "ensemble")
**Response (poisson/dixon_coles)**: `{ home_team, away_team, model_type, home_lambda, away_lambda, home_win, draw, away_win, over_2_5, btts_yes, score_matrix, calibration, confidence_intervals? }`
**Response (form)**: Same as dixon_coles plus `{ form_config: { lookback, form_factor, decay }, rho, home_advantage }`
**Response (ensemble)**: `{ home_team, away_team, model_type: "ensemble", home_lambda, away_lambda, home_win, draw, away_win, over_2_5, btts_yes, score_matrix, weights: { poisson, dixon_coles, dixon_coles_form }, model_predictions: { <name>: { home_lambda, away_lambda, home_win, draw, away_win } }, confidence_intervals? }`

**`confidence_intervals` field** (when available, dixon_coles/form models only):
```json
{
  "n_bootstrap": 50,
  "confidence_level": 0.90,
  "failed_iterations": 0,
  "home_win": [0.25, 0.55],
  "draw": [0.20, 0.40],
  "away_win": [0.15, 0.45],
  "home_lambda": [0.8, 1.8],
  "away_lambda": [0.9, 2.0]
}
```

> 注：`/prediction/{home}/{away}`（单数）别名端点已删除，`/predictions/{home}/{away}`（复数）为唯一路由。

### GET /predictions/{home_team}/{away_team}/h2h

返回两队历史交锋记录、近期 form 和汇总统计。

**查询参数：**
- `limit` (int, default=10, range=1–100): H2H 交锋记录条数上限；越界返回 HTTP 422
- `form_limit` (int, default=10, range=1–50): 每队近期 form 条数上限；越界返回 HTTP 422

**响应字段：**
- `home_team` (str): 查询的主队名
- `away_team` (str): 查询的客队名
- `head_to_head` (list[dict]): H2H 交锋记录，按日期倒序，每条含 `date`/`season`/`league`/`home_team`/`away_team`/`home_goals`/`away_goals`/`result`/`queried_home_result`；后者始终从查询主队视角返回 `W`/`D`/`L`，避免别名导致前端结果反转
- `home_form` (list[dict]): 主队近期比赛列表，每条含 `date`/`season`/`league`/`opponent`/`venue`/`goals_for`/`goals_against`/`result`
- `home_form_summary` (dict): 主队 form 汇总，含 `wins`/`draws`/`losses`/`goals_for`/`goals_against`/`points`/`streak`
- `away_form` (list[dict]): 客队近期比赛列表
- `away_form_summary` (dict): 客队 form 汇总
- `summary` (dict): H2H 汇总统计，含 `total_meetings`/`home_wins`/`draws`/`away_wins`/`home_goals_avg`/`away_goals_avg`/`last_meeting_date`
- `data_coverage` (dict): 数据覆盖范围，含 `seasons_covered` (list[str])/`total_matches_scanned` (int)/`source` (str)

**数据范围：** Football-Data 10 赛季（1617–2526）、20 联赛。不代表全量历史交锋。

**静态回退：** 纯静态服务器回退到 `frontend/data/h2h_pairs.json`。文件使用 `{schema_version, pairs, team_aliases}` 契约；`pairs` 按 `{home_slug}_{away_slug}` 保存 40 个有向组合，`team_aliases` 将 `Man City`、`Manchester Utd` 等数据源变体映射到同一静态键。

**缓存：** 源比赛表和规范化球队名使用统一 TTL 缓存（默认 300 秒，可由 `SCOUTFOOTBALL_CACHE_TTL_SECONDS` 调整）；`force_refresh=True` 可供离线重导出绕过缓存。

### GET /predictions/{home_team}/{away_team}/momentum

返回比赛中实时胜率时间线。基于赛前 Dixon-Coles 预测的 lambdas 和当前比分/分钟，使用独立 Poisson 计算剩余时间内的进球分布，推导出每分钟的胜/平/负概率。

**查询参数：**
- `home_goals` (int, default=0, range=0–20): 当前主队进球数
- `away_goals` (int, default=0, range=0–20): 当前客队进球数
- `minute` (int, default=0, range=0–120): 当前比赛分钟

**响应字段：**
- `home_team`, `away_team` (str): 球队名
- `home_lambda`, `away_lambda` (float): 赛前预期进球（全场比赛）
- `current_minute` (int): 当前分钟
- `current_home_goals`, `current_away_goals` (int): 当前比分
- `timeline` (list[dict]): 时间线，每 5 分钟一个点，含 `minute`/`home_win`/`draw`/`away_win`/`remaining_home_lambda`/`remaining_away_lambda`

**边缘情况：**
- 第 90 分钟时，结果由当前比分决定（确定性）
- 球队数据不足时返回 `{"error": "..."}`
- 前端提供比分和分钟输入控件，点击"更新"重新获取时间线

### GET /ratings/meta
Model metadata and league metrics.

### GET /artifacts
Artifact counts and data health summary.

### GET /action-values
Player action value summary from StatsBomb sample. xT and VAEP are kept in
separate arrays because they have different granularity (xT is
player-team-season; VAEP is player-team career).

**Query params**: `limit` (default=20), `offset` (default=0); both apply
independently to each model section.

**Response**:
```json
{
  "status": "ok",
  "count": 15062,
  "offset": 0,
  "limit": 500,
  "data_source": "StatsBomb Open Data + xT/VAEP model",
  "attribution_required": "StatsBomb Open Data",
  "model_granularity": { "xt": "player_team_season", "vaep": "player_team_career" },
  "metrics": {
    "total_rows": 15062,
    "xt_rows": 8291,
    "vaep_rows": 6771,
    "mean_xt_per_90": 0.0123,
    "mean_vaep_per_90": 0.0456,
    "players_with_xt": 8291,
    "players_with_vaep": 6771
  },
  "identity_coverage": {
    "schema": "scoutfootball.vaep-identity-coverage",
    "version": "1.1.0",
    "granularity": "player_team_career",
    "total_rows": 6771,
    "mapped_rows": 6698,
    "partial_rows": 0,
    "unmapped_rows": 73,
    "coverage_rate": 0.989,
    "player_name_coverage_rate": 0.989,
    "team_name_coverage_rate": 1.0,
    "season_context_coverage_rate": 0.989,
    "single_season_rows": 5000,
    "multi_season_rows": 1771,
    "source_counts": { "xt_player_team_bridge": 6698, "unmapped": 73 },
    "season_context_semantics": "Context only: VAEP values are aggregated across the player-team career row, not allocated to individual seasons."
  },
  "players": [ /* xt_page rows (alias for xt_players) */ ],
  "xt_players": [
    {
      "player_id": "10", "player_name": "Ada Forward", "team_id": "20",
      "team_name": "City Women", "season": "2023/2024", "competition": "League",
      "xt_total": 1.23, "xt_per_90": 0.045, "estimated_minutes": 1800
    }
  ],
  "vaep_players": [
    {
      "player_id": "10", "player_name": "Ada Forward", "team_id": "20",
      "team_name": "City Women", "vaep_total": 8.0, "vaep_per_90": 0.4,
      "season_context": "2022/2023 | 2023/2024", "season_count": 2,
      "competition_context": "League | Cup", "competition_count": 2,
      "identity_status": "mapped", "identity_mapped": true,
      "player_name_source": "xt_player_team_bridge", "team_name_source": "statsbomb_matches"
    }
  ]
}
```

**Identity fields (VAEP rows only)**:
- `identity_status`: `mapped` (player+team+season all resolved), `partial` (some resolved), `unmapped` (none).
- `identity_mapped`: boolean, true when `identity_status` == "mapped".
- `player_name_source` / `team_name_source`: provenance of display name.
- `season_context` / `competition_context`: pipe-delimited sorted deduplicated list; context only, not season-level allocation.
- Unmapped rows are retained; the frontend falls back to displaying `player_id`.

**Coverage report schema**: `scoutfootball.vaep-identity-coverage` v1.1.0.
Coverage rates are derived from the current VAEP rows; when the VAEP artifact
is empty, all counts/rates are 0 and no exception is raised.

### GET /action-values/evidence

Index of players that have match-level xT evidence in the tracked
`events_sample.parquet` snapshot. The response contains `coverage`,
`player_index`, and `available_player_ids`. The current tracked snapshot covers
exactly 3 matches and 69 players; it is not a full competition extract.

### GET /action-values/evidence/{player_id}

Match/action detail for one player in that tracked sample. The response includes
per-match pass/carry/shot counts and xT totals, action-type, destination-zone and
time-bucket breakdowns, plus the 12 highest-value actions with coordinates. A
player outside the sample returns `status: "not_found"` with empty arrays and
the same coverage metadata.

The evidence xT grid is recomputed from the three tracked matches. Therefore
these match-level xT values are **not directly comparable or additive** to the
full `player_action_value.parquet` aggregate. This limitation is machine-readable
as `coverage.xt_grid_scope: "sample_recomputed"` and
`coverage.aggregate_comparability: "not_directly_comparable"`.

### GET /action-values/players/{player_id}/context

Read-only player research dossier. It returns `models.xt.rows`,
`models.vaep.rows`, and `match_sample.rows` as independent sections, plus a
mandatory `comparability` object with `direct_numeric_comparison: false` and
`additive: false`. xT rows are player-team-season samples; VAEP rows are
player-team career aggregates and their season fields are coverage context
only. Match-level xT comes from the separately recomputed tracked sample.

The endpoint is for side-by-side inspection and JSON export, never for summing
values or building a cross-model ranking. Missing player IDs return
`invalid_player_id`; unknown IDs return `not_found` with explicit unavailable
model sections.

Static deployments use `frontend/data/action_value_evidence.json`, a versioned
`{schema_version, coverage, player_index, players}` snapshot. Both endpoints
retain `StatsBomb Open Data` source attribution and degrade to explicit

### GET /action-values/matches

Versioned player-team-match xT rows generated by
`scoutfootball action-value-matches`. The tracked artifact is
`player_match_action_value_sample.parquet` plus an adjacent manifest with the
input hash, action count, match count, coverage scope and comparability note.
Each row includes match date, competition, season, scoreline context, estimated
minutes, action-type counts, positive/negative xT and xT per 90. The current
release has exactly three StatsBomb Open Data matches; `coverage_scope: sample`
is mandatory and must not be presented as full competition coverage. Before
generation the endpoint returns `status: not_generated` and its build command,
never an empty result that looks like a zero-value conclusion. Static fallback
is `frontend/data/action_value_matches.json`.
`no_data`/`error` states when the tracked sample cannot be loaded.

### GET /review-queue
Low-confidence players for review.

### GET /watchlist, /shortlist
Scouting watchlist and shortlist.

### Local scouting workspace persistence

This opt-in store is disabled unless
`SCOUTFOOTBALL_ENABLE_WORKSPACE_WRITES=1`. By default it accepts access only
from loopback clients; non-loopback access additionally requires the explicit
`SCOUTFOOTBALL_ALLOW_REMOTE_WORKSPACE_WRITES=1` override. It stores workspace
JSON only and never mutates review queues, rating artifacts, or truth labels.

- `GET /scouting-workspaces/capabilities`: always available; reports whether
  persistence is configured and accessible to the current client.
- `GET /scouting-workspaces`: metadata for up to 100 stored workspaces.
- `GET /scouting-workspaces/latest`: latest stored record for explicit frontend
  preview.
- `GET /scouting-workspaces/{workspace_id}`: one record.
- `PUT /scouting-workspaces/{workspace_id}`: create or update a record. Existing
  records require `If-Match: "<server_revision>"`.

Stored records use the envelope below; `server_revision` is separate from the
browser workspace's `audit.revision`:

```json
{
  "schema": "scoutfootball.scouting-workspace-record",
  "version": "1.0",
  "server_revision": 2,
  "stored_at": "2026-07-11T01:00:00Z",
  "workspace": { "schema": "scoutfootball.scouting-workspace", "version": "1.2.0" }
}
```

The payload limit is 1 MB. Workspace IDs are path-safe and must match
`workspace.audit.workspace_id`; dynamic maps, notes, selections, timestamps,
statuses, dossiers, nesting, and forbidden prototype keys are validated. New records get
server revision 1. Updating without `If-Match` returns 428; a stale revision
returns 409 with `current_revision`. Each successful update copies the previous
record to `data/reports/scouting/workspaces/backups/`, then atomically replaces
the live JSON file. No delete endpoint is exposed.

### GET /model-runs
Model run registry with holdout metrics. New optimizer runs include a
`lineage` object with `schema: scoutfootball.model-run-lineage`, a dataset
snapshot `input_hash`, and a fingerprint/version of
`rating_feature_matrix_manifest.json`. Legacy runs return
`lineage.status: not_recorded` rather than implying that provenance was
captured retroactively. A missing manifest yields `status: partial`. Each
directory-backed run also has an `admission` summary from the local read-only
model-admission checks: `status`, `failed_checks`, optional holdout comparison,
and limitations. `reviewable` means evidence exists for human review only;
`not_reviewable` is not a failed model score and neither status activates a
rating artifact.

### GET /reports/model-runs/{run_id}
Full details for a single model run, including the same lineage object for
reproducibility review. New runs may also include `data_coverage` with source
rows, observed-field counts, and optional-artifact statuses. Historic runs
without that field are not retroactively labelled as fully audited.

### Local model-admission report

`scoutfootball model-admission` is a read-only local screen over
`data/models/runs/<run_id>/`. A run is `reviewable` only when its own directory
contains `optimized_params.npy`, recorded input and feature-manifest lineage,
non-empty train/test season split, finite structured baseline and candidate
holdout Spearman values, and an error-case summary from that same holdout.
The report fails closed when a required optimizer input is absent from the run
metadata or explicitly unavailable. It does not set a performance threshold, write a promotion pointer, alter
`player_ratings_optimized.parquet`, or claim that a reviewable run is promoted.
Historic records that predate these fields are `not_reviewable`, never upgraded
from filenames, timestamps, or prose metrics.

New optimizer run metadata preserves nested `baseline_*` and `optimized_*`
metric objects and records the holdout's largest team-level under/over-estimates
with residual definition `prediction_minus_actual`. These are evidence for a
maintainer's comparison, not a substitute for calibration, slice, and scope
review.

The optimizer input hash lists only artifacts the optimizer can read: its raw
FBref/Football-Data/Understat inputs and, when present, local matrix or
truth-label inputs. The currently active
`player_ratings_optimized.parquet` is explicitly excluded because it is an
output, not optimizer input; changing an active score artifact must not change
the lineage of a candidate that did not read it.

Optimizer run metadata records the actual season lists returned by its time
split, rather than configuration such as `--test-seasons 1`. A missing or
numeric count in the metadata is not converted into a claimed holdout season.

### GET /world-cup/groups, /world-cup/schedule, /world-cup/squads/{team}, /world-cup/predictions
World Cup data endpoints.
`/world-cup/squads/{team}` and `/world-cup/outlook/{team}` include a versioned
`squad_balance` object. It reports expected-callup snapshot counts and rating
coverage by listed role (GK/CB/FB/DM/CM/AM/W/ST), unit summaries, and planning
flags relative to internal role-depth targets. It is not a confirmed 26-player
roster, lineup, injury report, or tactical recommendation; missing or thin
roles only describe the local expected-callup list.

### GET /world-cup/squad-balance-comparison/{team_a}/{team_b}
Returns a versioned, side-by-side comparison of the two teams' local
expected-callup snapshots. Each listed role reports both sides' count, planning
target, rated-player count, rating coverage, average rating, and transparent
count/coverage differences. The response deliberately does not assign a role
advantage or recommend a lineup. It is unavailable for unknown teams and is
not a confirmed roster, injury report, or tactical assessment.
The comparison page can download this response as a browser-local JSON export
(`scoutfootball.world-cup-squad-balance-comparison-export` v1.0.0) or a CSV
role table. Both retain the bounded disclaimer; CSV values use the shared
formula-injection guard and neither action writes server state.

### GET /world-cup/match-briefings/{home_team}/{away_team}
Returns a versioned, source-bounded World Cup pre-match briefing. It combines
the simplified strength-ratio Poisson output with each side's local
squad-rating coverage, strength components, and up to five rated players. It
does not represent confirmed lineups, live team news, market odds, or a
tactical recommendation.

**Response**: `{ schema, version, status, fixture, prediction, teams, source_attribution, limitations }`.
`teams.home` and `teams.away` include `squad.rating_coverage`,
`squad.top_rated_players`, `squad.balance`, and bounded strength components.
Static exports may
provide `/data/worldcup/match_briefings.json`; if no matching static briefing
exists, the frontend shows it as unavailable rather than synthesizing one.
`input_snapshot` records the current rating run ID/input hash and feature
manifest hash only when model-run lineage has captured them; otherwise its
status is `not_recorded`. It also names the fixed World Cup strength-model
version and parameters used for the response.
The comparison view can download the briefing as a browser-local JSON export
(`scoutfootball.world-cup-match-briefing-export` v1.0.0) or CSV report. Both
retain source attribution and limitations; CSV cells use the shared formula
injection guard and neither action writes server state.
When a briefing creates a tactical-board project, its decision-pack provenance
also stores the bounded briefing schema, version, and source attribution. The
tactical JSON export preview surfaces those fields so the board can be checked
against a compatible local briefing export.

`GET /world-cup/tournament/knockout/{match_id}/briefing` exposes a populated
local knockout matchup through the same source-bounded match-briefing contract,
with an additional `knockout_context` containing match ID, round, bracket
position, local provisional status, and match status. It returns `not_ready`
for unresolved winner slots and never predicts an opponent. The frontend can
open a populated matchup in the comparison/briefing flow; any export retains
the local bracket context and remains neither an official fixture confirmation
nor a tactical recommendation.

`GET /world-cup/tournament/knockout/{match_id}/review` is a separate
`scoutfootball.world-cup-knockout-result-review` v1.0.0 contract for a
completed **locally recorded** knockout result. When the API records a result,
it first stores a `scoutfootball.world-cup-knockout-prediction-snapshot`
v1.0.0 of the live Bradley-Terry matchup projection. The review returns that
immutable snapshot, the local score/winner, and a limited directional
comparison (`matched_direction`, `recorded_upset`, or `no_directional_call`).
It is not an official-result feed and must not be interpreted as a one-match
accuracy, calibration, or model-quality assessment. Existing/imported results
without a snapshot return `snapshot_not_recorded`; the service never derives a
retrospective prediction from post-result probabilities. Clearing a result,
including a cascaded downstream result, removes its snapshot. The completed
card can render this local-only review and download its JSON. The tournament
state is persisted by the local application API, rather than browser storage;
manual export/import is explicit and does not create automatic sharing or
synchronization.

`GET /world-cup/tournament/knockout/reviews` exposes the compact
`scoutfootball.world-cup-knockout-review-ledger` v1.0.0 for all completed
locally recorded knockout matches. Its `summary` separates completed entries,
captured snapshots, missing snapshots, and directional comparisons. It does
not backfill missing snapshots and is never an official-result feed,
calibration statistic, or model-accuracy report. The World Cup page can render
and locally download this ledger as JSON.

`POST /world-cup/tournament/import/preview` validates an encoded tournament
state without writing local data. Its versioned response summarizes incoming
and current result/snapshot counts plus bounded replacement differences. The
World Cup page enables confirmation only after a successful preview of the
unchanged encoded value. Confirmation still replaces the complete local
application state; it is not a merge, official result feed, or automatic sync.
Malformed but decodable states return `status: error`, `code:
integrity_failed`, and up to 20 `integrity_errors` describing score, fixture,
or knockout inconsistencies. These diagnostics are read-only; they do not
partially import, repair, or persist any state.
Successful previews also expose bounded `result_changes` and `knockout_changes`
ledgers. Each has `items`, `total`, and `truncated`; the result ledger contains
the scheduled fixture plus the current/incoming local result, while the
knockout ledger only describes local record and snapshot-presence changes. It
is an overwrite-impact aid, not an official result feed or an audit history.
They also return `current_state_fingerprint`. The browser sends it as
`expected_current_fingerprint` when confirming; if local state changed after
preview, import returns `stale_preview` and writes nothing. Direct API callers
may omit the optional field for backward compatibility.

The general match-prediction tactical handoff writes a bounded
`scoutfootball.tactical-decision-pack` v1.1.0 into the browser-local board
project. Alongside the loaded model output and provenance, it may preserve the
already loaded head-to-head/recent-form summary and momentum query. These are
explicitly `non_additive_to_prediction`, cannot change the recorded
probabilities, and do not create a lineup, player availability claim, or
tactical recommendation. The pack keeps unavailable context as unavailable and
sanitizes imported metadata to its compact numeric/status schema.

### GET /world-cup/knockout
World Cup knockout bracket simulation.

Returns the projected knockout bracket from Round of 32 through Final, with
per-match win probabilities and Monte Carlo tournament win probabilities.

**Response**:
```json
{
  "status": "ok",
  "round_of_32": [
    {
      "home_group": "J", "home_team": "Argentina", "home_strength": 0.77,
      "away_group": "L", "away_team": "Panama", "away_strength": 0.25,
      "home_win_probability": 0.92, "away_win_probability": 0.08
    }
  ],
  "round_of_16": [ { "home_team", "home_strength", "away_team", "away_strength",
    "home_win_probability", "away_win_probability", "from_match": [1, 2] } ],
  "quarter_finals": [ ... ],
  "semi_finals": [ ... ],
  "final": [ ... ],
  "tournament_win_probability": [
    { "team": "Argentina", "group": "J", "strength": 0.77, "win_probability": 0.15 }
  ],
  "num_simulations": 10000,
  "disclaimer": "Knockout probabilities use a simplified Bradley-Terry strength model..."
}
```

**Static fallback**: `/data/worldcup/knockout.json`

### GET /world-cup/tournament/summary
Tournament-wide summary: completion rate, all 12 group standings, best thirds, and advancing teams.

### GET /world-cup/tournament/qualification-impact?group=A

Read-only local standings interpretation for one group. Returns the current
top two, its third-placed team's cross-group rank against the eight best-third
slots, the current cutline, and recorded/remaining group matches. `provisional`
remains true until the relevant local results are complete; this is neither an
official qualification decision nor a match prediction.
The matching CLI is `scoutfootball tournament qualification --group A [--json]`.
The page can download the exact loaded response in a separate
`scoutfootball.world-cup-qualification-impact-export` v1.0.0 local JSON file;
it creates no server-side audit record or synchronization.

### GET /world-cup/tournament/tiebreak-diagnostics?group=A

Returns tied clusters that remain after points, goal difference, and goals
scored, together with the number of head-to-head fixtures recorded versus
required. It exposes only the availability of the locally calculated rule; it
does not model fair-play or drawing of lots, and never represents a local
display order as an official ranking decision.
The same result is available offline through
`scoutfootball tournament tiebreaks --group A [--json]` and never writes
tournament state.

**Response**:
```json
{
  "status": "ok",
  "schema_version": "1.0.0",
  "tournament_start": "2026-06-11",
  "tournament_end": "2026-07-19",
  "total_matches": 72,
  "completed_matches": 0,
  "completion_rate": 0.0,
  "groups_complete": 0,
  "total_groups": 12,
  "is_complete": false,
  "hosts": ["USA", "Canada", "Mexico"],
  "standings": { "A": [GroupStanding, ...], ... },
  "best_thirds": [ { group, team, played, points, goal_difference, goals_for, goals_against, provisional }, ... ],
  "advancing": {
    "winners": [ { team, group, position, played, won, drawn, lost, goals_for, goals_against, goal_difference, points }, ... ],
    "runners_up": [ { ... }, ... ],
    "best_thirds": [ { ... }, ... ],
    "all_advancing": ["team1", "team2", ...],
    "provisional": true
  }
}
```

### GET /world-cup/tournament/standings?group=A
Standings for a single group (or all groups when `group` is omitted).

**Response** (single group): `{ "status": "ok", "standings": [GroupStanding, ...] }`
**Response** (all groups): `{ "status": "ok", "standings": { "A": [...], "B": [...], ... } }`

`GroupStanding` shape: `{ team, played, won, drawn, lost, goals_for, goals_against, goal_difference, points }`

### GET /world-cup/tournament/matches?group=A&pending=true
List group-stage matches. `group` filters to one group; `pending=true` returns only matches without a recorded result.

**Response**:
```json
{
  "status": "ok",
  "matches": [
    { "match_id", "matchday", "date", "time_et", "home", "away", "venue", "city", "group", "stage", "completed": false }
  ]
}
```

### GET /world-cup/tournament/scenarios/{team}?max_scenarios=30
Qualification scenarios for a team based on its remaining group-stage fixtures.

**Response**:
```json
{
  "status": "ok",
  "team": "Mexico",
  "group": "A",
  "current_standing": { "team", "played", "won", "drawn", "lost", "goals_for", "goals_against", "goal_difference", "points" },
  "remaining_matches": [ { match_id, home, away, matchday, group }, ... ],
  "advance_probability": 0.75,
  "scenarios": [
    { "description", "results": [ {match_id, home_goals, away_goals}, ... ], "final_position": 1, "advances": true, "advance_path": "winner" }
  ],
  "summary": "Mexico advances in 75% of remaining scenarios."
}
```

### POST /world-cup/tournament/result?match_id=...&home_goals=...&away_goals=...
Record a group-stage match result. Persists state to `data/reports/worldcup/tournament_state.json`.

**Response**: `{ "status": "ok", "match_id", "home_goals", "away_goals", "saved_to": "data/reports/worldcup/tournament_state.json" }`

### DELETE /world-cup/tournament/result?match_id=...
Clear a recorded match result.

**Response**: `{ "status": "ok", "match_id", "cleared": true, "saved_to": "..." }`

### POST /world-cup/tournament/reset
Reset all tournament results to a fresh state (keeps the 72-match schedule).

**Response**: `{ "status": "ok", "reset": true, "saved_to": "..." }`

### GET /world-cup/tournament/knockout
Return the knockout bracket overview (generated flag, provisional flag, champion, current_round, completed_matches, total_matches=31, rounds dict keyed by r32/r16/qf/sf/final with label + matches). Returns `{ "generated": false }` when no bracket has been generated yet.

### POST /world-cup/tournament/knockout/generate
Generate the full 31-match knockout bracket from current group standings (12 winners + 12 runners-up + 8 best thirds) and persist to `DEFAULT_STATE_PATH`. Later rounds have home/away=None with seed labels like "Winner R32-01".

**Response**: `{ "status": "ok", "generated": true, "provisional": bool, "total_matches": 31, "saved_to": "..." }`

### POST /world-cup/tournament/knockout/result?match_id=r32-01&home_goals=2&away_goals=1&penalties_winner=...
Record a knockout match result. Draws require `penalties_winner` (must be home or away team). Winner auto-advances to the next round's home (odd position) or away (even position) slot. Sets champion when the final is completed.

**Response**: `{ "status": "ok", "match_id", "winner", "decided_by": "regular"|"penalties", "saved_to": "..." }`

### DELETE /world-cup/tournament/knockout/result?match_id=...
Clear a knockout match result. Cascades: clearing a result recursively clears all downstream matches that depended on that winner (and clears champion if the final is cleared).

**Response**: `{ "status": "ok", "cleared": true, "saved_to": "..." }`

### GET /world-cup/tournament/knockout/probabilities
Return per-match win probabilities and Monte Carlo tournament championship odds for the current knockout bracket. Uses Bradley-Terry strength model with amplification exponent k=2.8 for ready matches; completed matches return 1.0/0.0 for the known winner/loser; TBD matches return null probabilities. Tournament win probabilities are only computed when all 16 R32 matches have both teams filled (10,000 simulations, seeded).

**Response** (when bracket generated and squads available):
```json
{
  "match_probabilities": [
    {
      "match_id": "r32-01",
      "home": "Argentina",
      "away": "Panama",
      "home_win_prob": 0.92,
      "away_win_prob": 0.08,
      "status": "ready"
    },
    {
      "match_id": "r16-01",
      "home": null,
      "away": null,
      "home_win_prob": null,
      "away_win_prob": null,
      "status": "tbd"
    }
  ],
  "tournament_win_probability": [
    { "team": "Argentina", "win_probability": 0.234 },
    { "team": "France", "win_probability": 0.187 }
  ],
  "num_simulations": 10000,
  "disclaimer": "Probabilities are model estimates for illustrative purposes..."
}
```

**Response** (when no bracket generated): `{ "status": "error", "message": "No knockout bracket generated yet..." }`

### GET /world-cup/tournament/knockout/scenarios/{team}
Return per-stage championship probability scenarios for a specific team in the knockout bracket. Shows current baseline championship probability and what-if analysis for each remaining knockout stage (conditional on winning each match). Uses Monte Carlo simulation (5,000 iterations, seeded) with force-winner logic for conditional analysis.

**Response** (when team is in bracket):
```json
{
  "status": "ok",
  "team": "Argentina",
  "current_championship_probability": 0.234,
  "next_match": {
    "match_id": "r32-01",
    "round": "r32",
    "opponent": "Panama",
    "win_probability": 0.92
  },
  "scenarios": [
    {
      "round": "r32",
      "match_id": "r32-01",
      "opponent": "Panama",
      "match_win_probability": 0.92,
      "championship_if_win": 0.255,
      "championship_if_lose": 0.0
    },
    {
      "round": "r16",
      "match_id": null,
      "opponent": null,
      "match_win_probability": null,
      "championship_if_reach": 0.255,
      "note": "Opponent TBD — projected championship probability if team reaches this round."
    }
  ],
  "disclaimer": "Scenario probabilities are Monte Carlo estimates..."
}
```

**Response** (when team eliminated): `{ "status": "ok", "team": "...", "current_championship_probability": 0.0, "next_match": null, "scenarios": [] }`

**Response** (when no bracket): `{ "status": "error", "message": "No knockout bracket generated..." }`

### GET /world-cup/tournament/group-simulation?mode=random&num_simulations=1000
Batch-simulate all remaining group-stage matches and report advancement odds. `mode` is `random` (uniform 1/3 win/draw/loss) or `strength` (Bradley-Terry-weighted with 28% draw baseline).

**Response**:
```json
{
  "status": "ok",
  "mode": "strength",
  "num_simulations": 1000,
  "remaining_matches": 48,
  "advancement_probability": [
    { "team": "Argentina", "group": "A", "advance_prob": 0.95, "win_group_prob": 0.82 },
    { "team": "France", "group": "B", "advance_prob": 0.88, "win_group_prob": 0.65 }
  ],
  "most_likely_group_winners": [
    { "group": "A", "team": "Argentina", "frequency": 820, "probability": 0.82 }
  ],
  "disclaimer": "Group-stage simulation uses simplified outcome models..."
}
```

### GET /world-cup/tournament/export
Export the full tournament state (matches + results + knockout) as a base64-URL-safe encoded JSON string for sharing/importing.

**Response**:
```json
{
  "status": "ok",
  "format": "base64url-json-v1",
  "schema_version": "1.0.0",
  "state_size": 12345,
  "encoded": "eyJzY2hlbWFfdmVyc2lvbiI6...",
  "exported_at": "2026-07-12T12:00:00Z"
}
```

### POST /world-cup/tournament/import
Import a shared tournament state and persist it to disk. Overwrites the current state.

**Request body**:
```json
{ "encoded": "eyJzY2hlbWFfdmVyc2lvbiI6..." }
```

**Response (success)**:
```json
{
  "status": "ok",
  "imported": true,
  "schema_version": "1.0.0",
  "matches": 72,
  "results": 5,
  "has_knockout": true,
  "saved_to": "data/reports/worldcup/tournament_state.json"
}
```

**Response (error)**:
```json
{
  "status": "error",
  "code": "decode_failed",
  "message": "Failed to decode state: ..."
}
```
Error codes: `decode_failed` (invalid base64 or JSON), `invalid_state` (incompatible schema version).

### GET /license
Data source license attribution.

**Response**:
```json
{
  "license_attribution": {
    "statsbomb": { "name", "license", "url", "attribution_required", "note" },
    "fbref": { ... },
    "football_data": { ... },
    "understat": { ... },
    "club_elo": { ... },
    "transfermarkt": { ... }
  },
  "data_source_label": "string",
  "updated_at": 1234567890.0
}
```

### GET /value-summary
Value deviation analysis from OOF predictions.

**Response**: `{ players: [...], summary: { ... } }`

### GET /predictions/meta
Match prediction model metadata.

### GET /teams/strength

Aggregated team-level strength metrics derived from player ratings.

**Query params**: `league` (optional), `season` (optional), `limit` (default 100)

**Response**:
```json
{
  "count": 2,
  "teams": [
    {
      "team": "Team Alpha",
      "league": "Premier League",
      "season": "2526",
      "overall_rating": 62.5,
      "squad_size": 20,
      "total_minutes": 25000,
      "position_groups": {
        "GK": { "rating": 55.0, "player_count": 2, "avg_minutes": 900 },
        "DEF": { "rating": 60.0, "player_count": 6, "avg_minutes": 1500 },
        "MID": { "rating": 65.0, "player_count": 7, "avg_minutes": 1800 },
        "ATT": { "rating": 68.0, "player_count": 5, "avg_minutes": 1600 }
      },
      "top_players": [
        { "name": "Player A", "position": "ST", "broad_pos": "ATT", "rating": 70.0, "minutes": 1800, "confidence": "HIGH" }
      ],
      "confidence_distribution": { "HIGH": 15, "MEDIUM": 3, "LOW": 2 }
    }
  ]
}
```

The overall rating is minutes-weighted: `sum(score * minutes) / sum(minutes)`.
Position groups are mapped from granular positions to GK, DEF, MID, ATT.
Players with comma-joined team names (transferred players) are excluded.

### GET /teams/compare

Side-by-side comparison of two teams with position group radar and diff table.

**Query params**: `a` (team name), `b` (team name)

**Response**:
```json
{
  "team_a": { "name": "Arsenal", "league": "...", "overall_rating": 65.5, "squad_size": 22 },
  "team_b": { "name": "Barcelona", "league": "...", "overall_rating": 68.0, "squad_size": 25 },
  "overall_diff": -2.5,
  "overall_advantage": "b",
  "position_group_comparison": [
    { "group": "GK", "rating_a": 55.0, "rating_b": 60.0, "diff": -5.0, "advantage": "b", "players_a": 2, "players_b": 3 }
  ],
  "top_players_comparison": [
    { "player_a": { "name": "...", "rating": 72.0 }, "player_b": { "name": "...", "rating": 75.0 } }
  ],
  "radar_labels": ["GK", "DEF", "MID", "ATT", "Overall"],
  "radar_a": [55.0, 60.0, 65.0, 70.0, 65.5],
  "radar_b": [60.0, 62.0, 68.0, 72.0, 68.0]
}
```

Team matching is case-insensitive and supports partial name matches.

### GET /teams/style-clusters/similarity

NxN cosine similarity matrix between team-style cluster centroids. Reuses the
clustering from `GET /teams/style-clusters` and computes pairwise cosine
similarity between every pair of cluster centroids. Symmetric with 1.0 on the
diagonal. An upper-triangle `pairs` list (sorted by similarity descending)
carries a heuristic clash label.

**Query params**: `season` (optional), `league` (optional, case-insensitive),
`n_clusters` (default 4, clamped to 2–8), `min_minutes_total` (default 1800.0)

**Response**:
```json
{
  "status": "ok",
  "n_clusters": 4,
  "season": null,
  "league": null,
  "labels": [
    { "cluster_id": 0, "label": "attacking", "n_teams": 2 }
  ],
  "matrix": [[1.0, 0.42], [0.42, 1.0]],
  "pairs": [
    { "a": 0, "b": 1, "label_a": "attacking", "label_b": "defensive",
      "similarity": 0.42, "clash": "complementary" }
  ],
  "disclaimer": "Cluster similarities are cosine similarities between standardised cluster centroids..."
}
```

Non-`ok` statuses: `no_data`, `insufficient_teams` (<4 teams after filtering),
`sklearn_unavailable`. The `clash` label maps: `similar` (≥0.75),
`complementary` (≥0.25), `contrasting` (<0.25). This is a statistical
affinity description, not a tactical relationship or match-outcome prediction.

### GET /teams/style-matchup

Diagnostic of how two teams' tactical styles clash. Computes each team's
minutes-weighted style profile, standardises both against the league
population, and reports per-dimension advantage, overall style distance, a
heuristic game-script classification, and optional cluster context.

**Query params**: `home_team` (required), `away_team` (required), `season`
(optional), `league` (optional, case-insensitive), `n_clusters` (default 4,
clamped to 2–8), `min_minutes_total` (default 1800.0)

**Response**:
```json
{
  "status": "ok",
  "home_team": "Team A",
  "away_team": "Team B",
  "season": null,
  "league": null,
  "home": {
    "team": "Team A", "league": "...", "season": "2526",
    "n_players": 14, "total_minutes": 18000,
    "raw": { "npg_p90": 0.55, "assists_p90": 0.28, "defense_composite": 12.0, "possession_composite": 33.0 },
    "standardized": { "npg_p90": 1.2, "assists_p90": 0.8, "defense_composite": -1.1, "possession_composite": -0.5 }
  },
  "away": { "...": "..." },
  "dimensions": [
    { "feature": "npg_p90", "label": "attack", "home": 0.55, "away": 0.15,
      "delta_std": 1.05, "advantage": "home" }
  ],
  "style_distance": 2.14,
  "game_script": "asymmetric",
  "game_script_label": "asymmetric",
  "home_cluster": { "cluster_id": 0, "label": "attacking" },
  "away_cluster": { "cluster_id": 1, "label": "defensive" },
  "cluster_similarity": 0.42,
  "cluster_clash": "complementary",
  "disclaimer": "Style matchup is a non-additive interpretive overlay..."
}
```

Non-`ok` statuses: `no_data`, `team_not_found` (includes `missing` list). The
`advantage` field uses a 0.15σ threshold: `home` (delta > 0.15), `away`
(delta < -0.15), `even` (|delta| ≤ 0.15). `game_script` ∈ {asymmetric,
open_game, defensive_battle, possession_duel, balanced}. `cluster_clash` ∈
{same_cluster, similar, complementary, contrasting}. This is a strictly
non-additive interpretive overlay — it does NOT modify the match-probability
model; win/draw/loss probabilities remain the sole source of truth.

### GET /teams/{team}/style-neighbors

Finds the nearest tactical-style neighbors for a given team. Standardises all
team style profiles against the league population, then ranks every other team
by cosine similarity (descending) on the standardised 4-dim vector. When
clustering succeeds, each neighbor carries cluster context.

**Query params**: `team` (path, required), `season` (optional), `league`
(optional, case-insensitive), `top_n` (default 10, clamped to 1–50),
`n_clusters` (default 4, clamped to 2–8), `min_minutes_total` (default 1800.0)

**Response**:
```json
{
  "status": "ok",
  "team": "Team A",
  "season": null,
  "league": null,
  "target": {
    "team": "Team A", "league": "...", "season": "2526",
    "n_players": 14, "total_minutes": 18000,
    "raw": { "npg_p90": 0.55, "assists_p90": 0.28, "defense_composite": 12.0, "possession_composite": 33.0 },
    "standardized": { "npg_p90": 1.2, "assists_p90": 0.8, "defense_composite": -1.1, "possession_composite": -0.5 }
  },
  "target_cluster": { "cluster_id": 0, "label": "attacking" },
  "n_population": 8,
  "n_returned": 7,
  "neighbors": [
    { "team": "Team B", "league": "...", "season": "2526",
      "cosine_similarity": 0.97, "style_distance": 0.32,
      "cluster_id": 0, "cluster_label": "attacking", "same_cluster": true }
  ],
  "disclaimer": "Style neighbors are ranked by cosine similarity..."
}
```

Non-`ok` statuses: `no_data`, `team_not_found`. `cosine_similarity` ∈ [-1, 1].
`style_distance` is Euclidean on standardised vectors (≥0). `same_cluster` only
present when clustering succeeds. This is an interpretive overlay — it does not
predict match outcomes or rank teams by quality.

### GET /teams/{team}/style-percentiles

Per-dimension percentile rank of one team within its league population. For
each of the 4 style dimensions, computes the team's percentile (0–100, average
rank for ties) with quartile label and population statistics.

**Query params**: `team` (path, required), `season` (optional), `league`
(optional, case-insensitive), `min_minutes_total` (default 1800.0)

**Response**:
```json
{
  "status": "ok",
  "team": "Team A",
  "season": null,
  "league": null,
  "target": { "team": "Team A", "raw": {...}, "standardized": {...} },
  "n_population": 8,
  "dimensions": [
    { "feature": "npg_p90", "label": "attack", "value": 0.55,
      "percentile": 100.0, "quartile": "top",
      "population_min": 0.15, "population_max": 0.55,
      "population_mean": 0.33, "population_median": 0.30 }
  ],
  "disclaimer": "Percentile ranks describe where a team sits..."
}
```

Non-`ok` statuses: `no_data`, `team_not_found`. `quartile` ∈ {top (≥75),
upper_mid (≥50), lower_mid (≥25), bottom (<25)}. Percentiles are relative, not
absolute — a 90th-percentile attack in a weak league is not equivalent to
90th-percentile in a strong one.

### GET /teams/style-atlas

League-wide distribution of team styles across all dimensions. For each of the
4 style dimensions, computes a histogram (with explicit bin edges), quartiles
(Q1/median/Q3/IQR), and outlier teams (|z| ≥ 2.0).

**Query params**: `season` (optional), `league` (optional, case-insensitive),
`n_bins` (default 8, clamped to 3–20), `min_minutes_total` (default 1800.0)

**Response**:
```json
{
  "status": "ok",
  "season": null,
  "league": null,
  "n_population": 8,
  "dimensions": [
    {
      "feature": "npg_p90", "label": "attack",
      "min": 0.15, "max": 0.55, "mean": 0.33, "median": 0.30,
      "q1": 0.18, "q3": 0.40, "iqr": 0.22,
      "bins": [
        { "low": 0.15, "high": 0.21, "count": 3 },
        { "low": 0.21, "high": 0.27, "count": 1 }
      ],
      "outliers": [
        { "team": "Team A", "league": "...", "season": "2526",
          "value": 0.55, "z_score": 2.13, "direction": "high" }
      ]
    }
  ],
  "disclaimer": "The style atlas is a descriptive population view..."
}
```

Non-`ok` statuses: `no_data`. Bin counts sum to `n_population`. Outliers are
teams with |z_score| ≥ 2.0 on the standardised dimension; `direction` ∈ {high,
low}. This is a descriptive population view — it does not rank teams by quality
or predict outcomes.

### GET /teams/{team}/style-drift

Single team's style trajectory across multiple seasons. For each of the 4 style
dimensions, computes a least-squares slope, net delta (latest - earliest), R²
consistency, per-season values, and a drift_label.

**Path params**: `team` (team name, case-insensitive)

**Query params**: `league` (optional, case-insensitive), `min_minutes_total`
(default 1800.0)

**Response**:
```json
{
  "status": "ok",
  "team": "Arsenal",
  "league": "Premier League",
  "seasons": ["2324", "2425", "2526"],
  "n_seasons": 3,
  "dimensions": [
    {
      "feature": "npg_p90", "label": "attack",
      "slope": 0.05, "delta": 0.1, "r_squared": 0.95,
      "mean": 0.45, "drift_label": "rising",
      "per_season": [
        { "season": "2324", "value": 0.35 },
        { "season": "2425", "value": 0.45 },
        { "season": "2526", "value": 0.55 }
      ]
    }
  ],
  "disclaimer": "Style drift is a descriptive trajectory..."
}
```

Non-`ok` statuses: `no_data`, `team_not_found`, `insufficient_seasons` (when
the team has fewer than 2 seasons of profiles). `drift_label` ∈ {rising,
falling, stable} using a 5% relative threshold. This is a descriptive overlay
— it does not predict future style or rank teams by quality.

### GET /teams/style-evolution

League-wide style evolution across seasons. Groups team-season profiles by
season, computes median and mean per dimension per season, and fits slopes.

**Query params**: `league` (optional, case-insensitive), `min_minutes_total`
(default 1800.0)

**Response**:
```json
{
  "status": "ok",
  "league": null,
  "seasons": ["2324", "2425", "2526"],
  "n_seasons": 3,
  "per_season": [
    {
      "season": "2324", "n_teams": 20,
      "npg_p90": { "median": 0.3, "mean": 0.32, "std": 0.1, "min": 0.1, "max": 0.6 },
      "assists_p90": { "median": 0.2, "mean": 0.21, "std": 0.05, "min": 0.1, "max": 0.35 },
      "defense_composite": { "median": 50.0, "mean": 48.0, "std": 15.0, "min": 10.0, "max": 80.0 },
      "possession_composite": { "median": 50.0, "mean": 51.0, "std": 12.0, "min": 30.0, "max": 80.0 }
    }
  ],
  "dimensions": [
    {
      "feature": "npg_p90", "label": "attack",
      "median_slope": 0.02, "median_delta": 0.04, "median_r_squared": 0.9,
      "mean_slope": 0.025, "mean_delta": 0.05, "mean_r_squared": 0.88,
      "evolution_label": "rising"
    }
  ],
  "disclaimer": "League style evolution is a descriptive population view..."
}
```

Non-`ok` statuses: `no_data`, `insufficient_seasons` (when fewer than 2
seasons available). `evolution_label` ∈ {rising, falling, stable} using a 5%
relative threshold on the median delta. This is a descriptive population view
— it does not predict future league style or rank seasons by quality.

### GET /teams/{team}/style-drift-neighbors

Teams with similar style-drift patterns. Computes a 4-dimensional drift vector
(least-squares slope per dimension) for each team with ≥ `min_seasons` profiles,
then ranks others by cosine similarity to the target team's drift vector.

**Path params**: `team` (team name, case-insensitive)

**Query params**: `league` (optional, case-insensitive), `top_n` (default 10,
clamped to 1–50), `min_seasons` (default 2, clamped to ≥ 2), `min_minutes_total`
(default 1800.0)

**Response**:
```json
{
  "status": "ok",
  "team": "Arsenal",
  "league": "Premier League",
  "seasons": ["2324", "2425", "2526"],
  "n_seasons": 3,
  "target_drift_vector": [0.05, 0.01, -2.0, 1.5],
  "target_drift_vector_labels": ["npg_p90", "assists_p90", "defense_composite", "possession_composite"],
  "n_candidates": 15,
  "neighbors": [
    {
      "team": "Liverpool", "league": "Premier League",
      "n_seasons": 3, "seasons": ["2324", "2425", "2526"],
      "cosine_similarity": 0.92, "euclidean_distance": 0.05,
      "drift_vector": [0.04, 0.02, -1.8, 1.3]
    }
  ],
  "disclaimer": "Style drift neighbors are a descriptive overlay..."
}
```

Non-`ok` statuses: `no_data`, `team_not_found` (when the target team has fewer
than `min_seasons` profiles). `cosine_similarity` ∈ [-1, 1]. This is a
descriptive overlay — similar drift does not imply similar quality or future
trajectory.

### GET /positions/style-evolution

Per-position-group style evolution across seasons. For each standard position
group (GK/CB/FB/DM/CM/AM/W/ST) with ≥2 seasons of minutes-weighted aggregates
(filtering players below `min_player_minutes`), fits a least-squares slope
across seasons for each of the 4 style dimensions.

**Query params**: `league` (optional, case-insensitive), `min_player_minutes`
(default 500.0)

**Response**:
```json
{
  "status": "ok",
  "league": null,
  "seasons": ["2324", "2425", "2526"],
  "n_seasons": 3,
  "position_groups": [
    {
      "position_group": "ST",
      "seasons": ["2324", "2425", "2526"],
      "n_seasons": 3,
      "dimensions": [
        {
          "feature": "npg_p90", "label": "attack",
          "slope": 0.05, "delta": 0.1, "r_squared": 0.85,
          "mean": 0.45, "evolution_label": "rising",
          "per_season": [
            { "season": "2324", "value": 0.4, "n_players": 12 },
            { "season": "2425", "value": 0.45, "n_players": 14 },
            { "season": "2526", "value": 0.5, "n_players": 13 }
          ]
        }
      ]
    }
  ],
  "skipped_positions": [
    { "position_group": "FB", "reason": "insufficient_seasons", "n_seasons": 1 }
  ],
  "disclaimer": "Per-position-group style evolution is a descriptive overlay..."
}
```

Non-`ok` statuses: `no_data`, `insufficient_seasons` (when no position group
has ≥2 seasons). `evolution_label` ∈ {rising, falling, stable} using a 5%
relative threshold on the delta. This is a descriptive population view — it
does not predict future position-group style or rank positions by quality.

### GET /positions/{position_group}/style-drift

Single position group's style trajectory across seasons. Validates position
against the 8 canonical groups (GK/CB/FB/DM/CM/AM/W/ST).

**Path params**: `position_group` (case-insensitive, one of GK/CB/FB/DM/CM/AM/W/ST)

**Query params**: `league` (optional, case-insensitive), `min_player_minutes`
(default 500.0)

**Response**:
```json
{
  "status": "ok",
  "position_group": "ST",
  "league": "Premier League",
  "seasons": ["2324", "2425", "2526"],
  "n_seasons": 3,
  "dimensions": [
    {
      "feature": "npg_p90", "label": "attack",
      "slope": 0.05, "delta": 0.1, "r_squared": 0.85,
      "mean": 0.45, "drift_label": "rising",
      "per_season": [
        { "season": "2324", "value": 0.4, "n_players": 12 },
        { "season": "2425", "value": 0.45, "n_players": 14 },
        { "season": "2526", "value": 0.5, "n_players": 13 }
      ]
    }
  ],
  "disclaimer": "Per-position-group style drift is a descriptive overlay..."
}
```

Non-`ok` statuses: `no_data`, `invalid_position` (when position_group is not
one of the 8 canonical groups), `position_not_found` (when the target position
group is absent from the data after filtering), `insufficient_seasons` (when
the position group has <2 seasons of profiles). `drift_label` ∈ {rising,
falling, stable} using a 5% relative threshold. This is a descriptive overlay
— it does not predict future position-group style or rank positions by quality.

### GET /positions/{position_group}/style-drift-neighbors

Position groups with similar style-drift patterns. Computes a 4-dimensional
drift vector (least-squares slope per dimension) for each position group with
≥2 seasons of profiles, then ranks others by cosine similarity to the target
position group's drift vector.

**Path params**: `position_group` (case-insensitive, one of GK/CB/FB/DM/CM/AM/W/ST)

**Query params**: `league` (optional, case-insensitive), `min_player_minutes`
(default 500.0)

**Response**:
```json
{
  "status": "ok",
  "position_group": "ST",
  "league": "Premier League",
  "seasons": ["2324", "2425", "2526"],
  "n_seasons": 3,
  "target_drift_vector": [0.05, 0.01, -2.0, 1.5],
  "target_drift_vector_labels": ["npg_p90", "assists_p90", "defense_composite", "possession_composite"],
  "n_candidates": 5,
  "neighbors": [
    {
      "position_group": "GK",
      "n_seasons": 3, "seasons": ["2324", "2425", "2526"],
      "cosine_similarity": 0.88, "euclidean_distance": 0.15,
      "drift_vector": [0.04, 0.02, -1.8, 1.3]
    }
  ],
  "disclaimer": "Per-position-group style drift neighbors are a descriptive overlay..."
}
```

Non-`ok` statuses: `no_data`, `invalid_position`, `position_not_found` (when
the target position group has <2 seasons of profiles and cannot form a drift
vector). `cosine_similarity` ∈ [-1, 1]. This is a descriptive overlay —
similar drift does not imply similar quality or future trajectory.

### GET /positions/depth-profile

Per-position-group squad depth profile. For each standard position group
(GK/CB/FB/DM/CM/AM/W/ST) after filtering players below `min_player_minutes`,
computes player count, total minutes, score distribution (min/median/max/
mean/std/p25/p75), minutes distribution, minutes-weighted style means, and
a depth_label (shallow <2 / adequate 2-3 / deep ≥4). Position groups with
zero qualifying players are listed in `missing_positions`.

**Query params**: `league` (optional, case-insensitive), `season` (optional),
`min_player_minutes` (default 500.0)

**Response**:
```json
{
  "status": "ok",
  "league": "Premier League",
  "season": "2526",
  "n_positions": 4,
  "position_groups": [
    {
      "position_group": "ST",
      "n_players": 8,
      "total_minutes": 11200,
      "score_min": 55.0, "score_median": 70.0, "score_max": 85.0,
      "score_mean": 70.0, "score_std": 10.0,
      "score_p25": 62.5, "score_p75": 77.5,
      "minutes_median": 1450, "minutes_mean": 1400,
      "attack": 0.25, "creation": 0.12,
      "defense": 30.5, "possession": 40.3,
      "depth_label": "deep"
    }
  ],
  "missing_positions": ["GK", "DM", "AM", "W"],
  "disclaimer": "Position depth profile is a descriptive snapshot..."
}
```

Non-`ok` statuses: `no_data` (empty input, no position_group column, or no
players above the minutes threshold). `depth_label` ∈ {shallow, adequate,
deep}. This is a descriptive overlay — depth labels do not account for
injuries, tactical flexibility, or upcoming transfers.

### GET /positions/{position_group}/cross-league

Cross-league quality comparison for one position group. Groups players by
league, computes per-league depth stats, sorts by mean score descending,
and assigns a quality_tier (top/middle/bottom).

**Path params**: `position_group` (case-insensitive, one of GK/CB/FB/DM/CM/AM/W/ST)

**Query params**: `season` (optional), `min_player_minutes` (default 500.0)

**Response**:
```json
{
  "status": "ok",
  "position_group": "ST",
  "season": "2526",
  "n_leagues": 2,
  "leagues": [
    {
      "league": "Premier League",
      "n_players": 8, "score_mean": 70.0, "score_median": 70.0,
      "attack": 0.25, "defense": 30.5,
      "depth_label": "deep", "quality_tier": "top"
    },
    {
      "league": "La Liga",
      "n_players": 5, "score_mean": 70.0, "score_median": 70.0,
      "attack": 0.22, "defense": 28.0,
      "depth_label": "adequate", "quality_tier": "bottom"
    }
  ],
  "best_league": "Premier League",
  "worst_league": "La Liga",
  "score_spread": 0.0,
  "disclaimer": "Cross-league position comparison is a descriptive overlay..."
}
```

Non-`ok` statuses: `no_data` (empty input or no position_group column),
`invalid_position` (when position_group is not one of the 8 canonical groups),
`position_not_found` (when the target position group is absent from the data
after filtering). `quality_tier` ∈ {top, middle, bottom}; when ≤2 leagues,
only top/bottom are assigned. This is a descriptive overlay — quality tiers
are relative rankings within the available leagues and do not account for
differences in league difficulty or sample size.

### GET /teams/{team}/position-gap-report

Position-group gap and strength report for one team. Computes per-position-
group depth stats for the target team and compares against league-wide p40/p60
percentiles to identify gaps (shallow/low_quality/missing) and strengths
(deep + high quality).

**Path params**: `team` (case-insensitive team name)

**Query params**: `season` (optional), `min_player_minutes` (default 500.0)

**Response**:
```json
{
  "status": "ok",
  "team": "Gap Team",
  "league": "Premier League",
  "season": "2526",
  "n_positions": 4,
  "position_groups": [
    {
      "position_group": "CM",
      "n_players": 5, "score_mean": 78.4,
      "depth_label": "deep",
      "league_p40": 65.0, "league_p60": 76.2, "league_n_players": 12
    }
  ],
  "missing_positions": ["GK", "DM", "AM", "W"],
  "gaps": [
    {
      "position_group": "ST", "gap_type": "shallow",
      "n_players": 1, "mean_score": 70.0,
      "reason": "Only 1 qualifying player(s) — depth below shallow threshold (2)."
    },
    {
      "position_group": "CB", "gap_type": "low_quality",
      "n_players": 3, "mean_score": 52.0, "league_p40": 54.6,
      "reason": "Mean score 52.0 below league 40th percentile (54.6)."
    },
    {
      "position_group": "GK", "gap_type": "missing",
      "n_players": 0, "reason": "No players in this position group."
    }
  ],
  "n_gaps": 7,
  "strengths": [
    {
      "position_group": "CM", "n_players": 5, "mean_score": 78.4,
      "league_p60": 76.2,
      "reason": "Deep roster (5 players) with mean score 78.4 >= league 60th percentile (76.2)."
    }
  ],
  "n_strengths": 1,
  "disclaimer": "Position gap report is a descriptive overlay..."
}
```

Non-`ok` statuses: `no_data` (empty input or no position_group column),
`team_not_found` (when the target team is absent from the data after filtering).
`gap_type` ∈ {shallow, low_quality, missing}. This is a descriptive overlay —
gap types and strength labels are heuristic thresholds, not transfer
recommendations or tactical advice.

### GET /positions/action-profile

Granular per-90 action profile for each standard position group. Decomposes
the 4 composite style features (npg_p90/assists_p90/defense_composite/
possession_composite) into 7 granular per-90 actions
(tackles_p90/interceptions_p90/crosses_p90/fouls_drawn_p90/fouls_p90/
g_a_volume/npg_p90) with minutes-weighted means. Position groups with zero
qualifying players are listed in `missing_positions`.

**Query params**: `league` (optional, case-insensitive), `season` (optional),
`min_player_minutes` (default 500.0)

**Response**:
```json
{
  "status": "ok",
  "league": "Premier League",
  "season": "2526",
  "n_positions": 4,
  "position_groups": [
    {
      "position_group": "ST",
      "n_players": 8,
      "total_minutes": 11200,
      "tackles_p90": 0.35, "interceptions_p90": 0.22,
      "crosses_p90": 0.10, "fouls_drawn_p90": 0.55,
      "fouls_p90": 0.42, "g_a_volume": 7.8, "npg_p90": 0.52
    }
  ],
  "missing_positions": ["GK", "DM", "AM", "W"],
  "action_features": ["tackles_p90", "interceptions_p90", "crosses_p90",
    "fouls_drawn_p90", "fouls_p90", "g_a_volume", "npg_p90"],
  "disclaimer": "Position action profile decomposes composite style scores..."
}
```

Non-`ok` statuses: `no_data` (empty input, no position_group column, missing
action columns, or no players above the minutes threshold). This is a
descriptive overlay — it does not predict future performance or rank positions
by quality.

### GET /positions/{position_group}/action-similarity

Rank position groups by similarity to the target position group's 7-dimensional
per-90 action vector (tackles/interceptions/crosses/fouls_drawn/fouls/
g_a_volume/npg_p90). Cosine similarity is the primary ranking key (descending);
Euclidean distance on the raw vectors is provided for reference.

**Path params**: `position_group` (case-insensitive, one of GK/CB/FB/DM/CM/AM/W/ST)

**Query params**: `league` (optional, case-insensitive), `season` (optional),
`min_player_minutes` (default 500.0)

**Response**:
```json
{
  "status": "ok",
  "position_group": "ST",
  "league": "Premier League",
  "season": "2526",
  "n_candidates": 3,
  "target_action_vector": [0.35, 0.22, 0.10, 0.55, 0.42, 7.8, 0.52],
  "target_action_vector_labels": ["tackles_p90", "interceptions_p90", "crosses_p90",
    "fouls_drawn_p90", "fouls_p90", "g_a_volume", "npg_p90"],
  "neighbors": [
    {
      "position_group": "AM",
      "cosine_similarity": 0.842,
      "euclidean_distance": 1.235
    }
  ],
  "disclaimer": "Action-based position similarity is a descriptive overlay..."
}
```

Non-`ok` statuses: `no_data` (empty input or missing action columns),
`invalid_position` (when position_group is not one of the 8 canonical groups),
`position_not_found` (when the target position group is absent from the data
or has no players above the minutes threshold). `cosine_similarity` ∈ [-1, 1].
This is a descriptive overlay — similar action signatures do not imply similar
tactical roles, quality, or future trajectories.

### GET /positions/trend-overlay

Cross-season improvement/decline trends for each position group. For each
standard position group, computes minutes-weighted means of npg_trend /
def_trend / pos_trend (the cross-season improvement metrics from the rating
pipeline) and assigns a trend_label (improving >0.05 / declining <-0.05 /
stable |val|<0.05) per dimension.

**Query params**: `league` (optional, case-insensitive), `season` (optional),
`min_player_minutes` (default 500.0)

**Response**:
```json
{
  "status": "ok",
  "league": "Premier League",
  "season": "2526",
  "n_positions": 4,
  "position_groups": [
    {
      "position_group": "ST",
      "n_players": 8,
      "total_minutes": 11200,
      "dimensions": [
        { "feature": "npg_trend", "value": 0.103, "trend_label": "improving" },
        { "feature": "def_trend", "value": 0.022, "trend_label": "stable" },
        { "feature": "pos_trend", "value": -0.098, "trend_label": "declining" }
      ]
    }
  ],
  "missing_positions": ["GK", "DM", "AM", "W"],
  "trend_features": ["npg_trend", "def_trend", "pos_trend"],
  "disclaimer": "Position trend overlay aggregates per-player cross-season..."
}
```

Non-`ok` statuses: `no_data` (empty input, no position_group column, missing
trend columns, or no players above the minutes threshold). `trend_label` ∈
{improving, declining, stable}. This is a descriptive overlay — it does not
predict future trends or rank positions by quality.

### GET /teams/action-profile

Granular per-90 action profile for each team. Decomposes the 4 composite
style features (npg_p90/assists_p90/defense_composite/possession_composite)
into 7 granular per-90 actions (tackles_p90/interceptions_p90/crosses_p90/
fouls_drawn_p90/fouls_p90/g_a_volume/npg_p90) with minutes-weighted means
per team. Teams are sorted by `total_minutes` descending for stable display.

**Query params**: `league` (optional, case-insensitive), `season` (optional),
`min_player_minutes` (default 500.0)

**Response**:
```json
{
  "status": "ok",
  "league": "Premier League",
  "season": "2526",
  "n_teams": 8,
  "teams": [
    {
      "team": "Arsenal",
      "n_players": 18,
      "total_minutes": 28800,
      "tackles_p90": 4.2, "interceptions_p90": 3.1,
      "crosses_p90": 1.8, "fouls_drawn_p90": 2.5,
      "fouls_p90": 1.9, "g_a_volume": 12.3, "npg_p90": 0.42
    }
  ],
  "action_features": ["tackles_p90", "interceptions_p90", "crosses_p90",
    "fouls_drawn_p90", "fouls_p90", "g_a_volume", "npg_p90"],
  "disclaimer": "Team action profile decomposes composite style scores..."
}
```

Non-`ok` statuses: `no_data` (empty input, missing action columns, or no
team had players above the minutes threshold). This is a descriptive overlay
— it does not predict future performance or rank teams by quality.

### GET /teams/{team}/action-percentiles

Per-action percentile rank of one team within its league population. For
each of the 7 action features (tackles/interceptions/crosses/fouls_drawn/
fouls/g_a_volume/npg_p90), computes the team's percentile (0–100, tie-handled
average ranks) with quartile label and population statistics.

**Path params**: `team` (case-insensitive team name)

**Query params**: `league` (optional, case-insensitive), `season` (optional),
`min_player_minutes` (default 500.0)

**Response**:
```json
{
  "status": "ok",
  "team": "Arsenal",
  "season": "2526",
  "league": "Premier League",
  "target": {
    "team": "Arsenal",
    "n_players": 18,
    "total_minutes": 28800,
    "action_values": {
      "tackles_p90": 4.2, "interceptions_p90": 3.1,
      "crosses_p90": 1.8, "fouls_drawn_p90": 2.5,
      "fouls_p90": 1.9, "g_a_volume": 12.3, "npg_p90": 0.42
    },
    "population_means": { "tackles_p90": 3.8, "..." : "..." },
    "population_stds": { "tackles_p90": 0.6, "..." : "..." }
  },
  "n_population": 8,
  "dimensions": [
    { "feature": "tackles_p90", "label": "tackles", "value": 4.2,
      "percentile": 87.5, "quartile": "top",
      "population_min": 2.1, "population_max": 4.5,
      "population_mean": 3.8, "population_median": 3.9 }
  ],
  "disclaimer": "Action percentiles describe where a team sits..."
}
```

Non-`ok` statuses: `no_data` (empty input or no team profiles above the
minutes threshold), `team_not_found` (when the target team is absent from
the filtered data). `quartile` ∈ {top (≥75), upper_mid (≥50), lower_mid
(≥25), bottom (<25)}. Percentile rank uses tie-handled average ranks
(`rank = count_below + 0.5 * count_equal`, `pct = 100 * rank / n_pop`).
Percentiles are relative, not absolute — a 90th-percentile cross volume in
a low-cross league is not equivalent to 90th-percentile in a high-cross one.

### GET /teams/{team}/action-similarity

Rank teams by similarity to the target team's 7-dimensional per-90 action
vector (tackles/interceptions/crosses/fouls_drawn/fouls/g_a_volume/npg_p90).
Cosine similarity is the primary ranking key (descending); Euclidean
distance on the raw vectors is provided for reference. Each neighbor
includes `n_players` and `total_minutes` for context.

**Path params**: `team` (case-insensitive team name)

**Query params**: `league` (optional, case-insensitive), `season` (optional),
`top_n` (default 10, clamped to `max(1, min(int(top_n), n_candidates))`),
`min_player_minutes` (default 500.0)

**Response**:
```json
{
  "status": "ok",
  "team": "Arsenal",
  "league": "Premier League",
  "season": "2526",
  "n_candidates": 7,
  "target_action_vector": [4.2, 3.1, 1.8, 2.5, 1.9, 12.3, 0.42],
  "target_action_vector_labels": ["tackles_p90", "interceptions_p90",
    "crosses_p90", "fouls_drawn_p90", "fouls_p90", "g_a_volume", "npg_p90"],
  "neighbors": [
    {
      "team": "Liverpool",
      "cosine_similarity": 0.952,
      "euclidean_distance": 1.234,
      "n_players": 17,
      "total_minutes": 27600
    }
  ],
  "disclaimer": "Team action similarity is a descriptive overlay..."
}
```

Non-`ok` statuses: `no_data` (empty input or no team profiles above the
minutes threshold), `team_not_found` (when the target team is absent from
the filtered data). `cosine_similarity` ∈ [-1, 1]; zero-norm vectors fall
back to a similarity of 0.0. This is a descriptive overlay — similar action
signatures do not imply similar quality, tactical systems, or match
outcomes.

### GET /teams/action-atlas

League-wide distribution atlas of team-level action signatures. For each
of the 7 action features (tackles/interceptions/crosses/fouls_drawn/fouls/
g_a_volume/npg_p90), computes a histogram (default 8 bins over min–max range)
with per-bin team counts and a summary header (min/Q1/median/Q3/max/IQR).
Outlier teams (z-score magnitude ≥ 2.0 on the standardized dimension) are
listed with their raw values. Teams are filtered by per-team
`min_player_minutes` aggregated from player minutes.

**Query params**: `season` (optional), `league` (optional, case-insensitive),
`n_bins` (default 8, clamped to `max(3, min(int(n_bins), 20))`),
`min_player_minutes` (default 500.0)

**Response**:
```json
{
  "status": "ok",
  "season": "2526",
  "league": "Premier League",
  "n_bins": 8,
  "min_player_minutes": 500.0,
  "n_teams": 8,
  "dimensions": [
    {
      "feature": "tackles_p90",
      "label": "tackles",
      "bin_edges": [2.1, 2.5, 2.9, 3.3, 3.7, 4.1, 4.5, 4.9, 5.3],
      "bin_counts": [1, 0, 2, 1, 2, 1, 0, 1],
      "summary": {
        "min": 2.1, "q1": 2.9, "median": 3.6, "q3": 4.3,
        "max": 5.3, "iqr": 1.4, "mean": 3.6, "std": 0.9
      },
      "outliers": [
        { "team": "Leeds United", "value": 5.3, "z_score": 2.1 }
      ]
    }
  ],
  "action_features": ["tackles_p90", "interceptions_p90", "crosses_p90",
    "fouls_drawn_p90", "fouls_p90", "g_a_volume", "npg_p90"],
  "disclaimer": "The action atlas is a descriptive overlay..."
}
```

Non-`ok` statuses: `no_data` (empty input or no team profiles above the
minutes threshold). `bin_edges` has length `n_bins + 1`; `bin_counts` has
length `n_bins`. When fewer than 2 distinct values exist, bins collapse to
a single bucket. `outliers` may be empty. The atlas does not modify the
prediction model — it is an interpretive layer over team action signatures.

### GET /teams/action-evolution

Multi-season drift trajectory of league-wide action signatures. For each
action feature, fits a least-squares slope against season index and reports
the slope, R² consistency, total Δ (last − first season median), and a drift
label (`rising` / `falling` / `stable`, 5% relative threshold). A per-season
median matrix is included for each dimension.

**Query params**: `league` (optional, case-insensitive),
`min_player_minutes` (default 500.0)

**Response**:
```json
{
  "status": "ok",
  "league": "Premier League",
  "min_player_minutes": 500.0,
  "seasons": ["2324", "2425", "2526"],
  "n_seasons": 3,
  "dimensions": [
    {
      "feature": "tackles_p90",
      "label": "tackles",
      "slope": 0.18,
      "r2": 0.87,
      "delta": 0.36,
      "drift_label": "rising",
      "per_season_median": { "2324": 3.2, "2425": 3.5, "2526": 3.6 }
    }
  ],
  "action_features": ["tackles_p90", "interceptions_p90", "crosses_p90",
    "fouls_drawn_p90", "fouls_p90", "g_a_volume", "npg_p90"],
  "disclaimer": "Action evolution is a descriptive overlay..."
}
```

Non-`ok` statuses: `no_data` (empty input), `insufficient_seasons`
(fewer than 2 distinct seasons available after filtering). `slope` is the
fitted linear coefficient on the season index (0-based). `r2` ∈ [0, 1] —
returns 0.0 when variance is zero or n < 2. `drift_label` uses a 5%
relative threshold on `delta / abs(first_season_median)`; `stable` is
returned when the relative change is below the threshold or the first-season
median is zero. The overlay does not modify the prediction model.

### GET /teams/cross-league-action

Cross-league comparison of action signatures for a given season. For each
action feature, ranks leagues by mean team value (descending) and assigns a
quality tier (`top` / `middle` / `bottom`, or `top` / `bottom` when ≤ 2
leagues). Each league entry includes mean, median, team count, and member
teams.

**Query params**: `season` (optional),
`min_player_minutes` (default 500.0)

**Response**:
```json
{
  "status": "ok",
  "season": "2526",
  "min_player_minutes": 500.0,
  "n_leagues": 3,
  "leagues": ["Premier League", "La Liga", "Bundesliga"],
  "dimensions": [
    {
      "feature": "tackles_p90",
      "label": "tackles",
      "rankings": [
        {
          "rank": 1,
          "league": "La Liga",
          "mean": 4.1,
          "median": 4.0,
          "n_teams": 8,
          "teams": ["Real Madrid", "Barcelona", "..."],
          "tier": "top"
        },
        {
          "rank": 2,
          "league": "Premier League",
          "mean": 3.7,
          "median": 3.6,
          "n_teams": 8,
          "teams": ["Arsenal", "Liverpool", "..."],
          "tier": "middle"
        }
      ]
    }
  ],
  "action_features": ["tackles_p90", "interceptions_p90", "crosses_p90",
    "fouls_drawn_p90", "fouls_p90", "g_a_volume", "npg_p90"],
  "disclaimer": "Cross-league comparison is a descriptive overlay..."
}
```

Non-`ok` statuses: `no_data` (empty input or no leagues with profiles
above the minutes threshold). Rankings are sorted descending by `mean`.
When only one league is present, a single `top`-tier entry is returned.
The comparison does not modify the prediction model — it is an interpretive
layer over aggregated team action signatures.

### GET /teams/cross-league-depth

Per-position-group depth comparison between two teams in a given season.
For each of the 8 standard position groups (GK/CB/FB/DM/CM/AM/W/ST),
returns n_players, total_minutes, score stats (min/median/max/mean/std),
and a depth_label (`shallow` <2 players / `adequate` 2-3 / `deep` ≥4).
Each position carries an `advantage` flag (`team_a` / `team_b` / `even`)
using a 0.5-point mean-score threshold, and `complementary_positions`
lists positions where the weaker side still has adequate depth (≥2
players). All stats are non-additive interpretive overlays and do not
modify the prediction model or imply transfer recommendations.

**Query params**: `team_a` (required, min_length=1), `team_b` (required,
min_length=1), `season` (optional), `min_player_minutes` (default 500.0,
ge=0.0)

**Response**:
```json
{
  "status": "ok",
  "team_a": "Arsenal",
  "team_b": "Barcelona",
  "season": "2425",
  "min_player_minutes": 500.0,
  "position_comparison": [
    {
      "position_group": "CB",
      "team_a": {"n_players": 4, "total_minutes": 8500, "mean": 78.2,
        "median": 79.0, "min": 71.5, "max": 83.1, "std": 4.8,
        "depth_label": "deep"},
      "team_b": {"n_players": 2, "total_minutes": 5200, "mean": 75.4,
        "median": 75.8, "min": 70.2, "max": 80.1, "std": 5.6,
        "depth_label": "adequate"},
      "advantage": "team_a"
    }
  ],
  "complementary_positions": ["FB", "CM"],
  "disclaimer": "Cross-league depth comparison is a descriptive overlay..."
}
```

Non-`ok` statuses: `team_a_not_found`, `team_b_not_found` (returned
instead of `no_data` when a requested team is absent from the filtered
frame), `no_data` (empty input or no `position_group` column).

### GET /teams/{team}/scouting-targets

Recommends players from other leagues to fill the target team's position
gaps. Reuses `compute_position_gap_report` to identify gaps
(`shallow` <2 players / `low_quality` mean < p40 / `missing` no players),
then for each gap position scans candidates from other leagues who:
(a) play the gap position_group, (b) meet `min_player_minutes`, (c) score
≥ the gap threshold (p60 of the candidate's own league at that position
for shallow/missing gaps, team mean for low_quality gaps), (d) sit in the
top quartile (p75) of their own league at that position. Candidates are
sorted by score descending and capped at `top_n`. All recommendations are
non-additive interpretive overlays and do not constitute transfer
directives or scouting verdicts.

**Query params**: `season` (optional), `min_player_minutes` (default
500.0, ge=0.0), `top_n` (int, default 10, clamped to 1–50),
`exclude_same_league` (bool, default true)

**Response**:
```json
{
  "status": "ok",
  "team": "Arsenal",
  "season": "2425",
  "min_player_minutes": 500.0,
  "top_n": 10,
  "exclude_same_league": true,
  "target_league": "Premier League",
  "gaps": [
    {
      "position_group": "ST",
      "gap_type": "shallow",
      "team_score": 72.3,
      "threshold": 74.0,
      "candidates": [
        {
          "player": "Erling Haaland",
          "team": "Manchester City",
          "league": "Premier League",
          "position_group": "ST",
          "score": 88.6,
          "minutes": 3100,
          "npg_p90": 0.92,
          "assists_p90": 0.18,
          "defense_composite": 0.08,
          "possession_composite": 0.42
        }
      ]
    }
  ],
  "disclaimer": "Scouting target recommendation is a descriptive overlay..."
}
```

Non-`ok` statuses: `team_not_found` (target team absent from filtered
frame), `no_data` (empty input or no `position_group` column). When
`exclude_same_league` is true, candidates from the target team's league
are filtered out. When no candidates meet the threshold for a gap, the
`candidates` list is empty (the gap is still reported).

### GET /teams/{team}/scouting-style-match/{position_group}

Finds players from other leagues whose 4-dim style vector (npg_p90 /
assists_p90 / defense_composite / possession_composite) is most similar
to the target team's aggregate style at the given position group, using
cosine similarity. Returns the team's `target_player` (top player at that
position by minutes), the team's `target_style_vector`, and a ranked
`candidates` list with per-player `similarity` (0–1), `style_vector`, and
`minutes`. Validates `position_group` against the 8 canonical groups
(GK/CB/FB/DM/CM/AM/W/ST). All matches are non-additive interpretive
overlays and do not constitute transfer directives.

**Path params**: `team` (player name), `position_group` (one of
GK/CB/FB/DM/CM/AM/W/ST)

**Query params**: `season` (optional), `min_player_minutes` (default
500.0, ge=0.0), `top_n` (int, default 10, clamped to 1–50),
`exclude_same_league` (bool, default true)

**Response**:
```json
{
  "status": "ok",
  "team": "Arsenal",
  "position_group": "ST",
  "season": "2425",
  "min_player_minutes": 500.0,
  "top_n": 10,
  "exclude_same_league": true,
  "target_player": {
    "player": "Bukayo Saka",
    "team": "Arsenal",
    "league": "Premier League",
    "position_group": "ST",
    "minutes": 2950,
    "score": 82.4
  },
  "target_style_vector": {"npg_p90": 0.45, "assists_p90": 0.38,
    "defense_composite": 0.18, "possession_composite": 0.62},
  "candidates": [
    {
      "player": "Ousmane Dembélé",
      "team": "Paris Saint-Germain",
      "league": "Ligue 1",
      "position_group": "W",
      "minutes": 2400,
      "score": 80.1,
      "similarity": 0.94,
      "style_vector": {"npg_p90": 0.42, "assists_p90": 0.41,
        "defense_composite": 0.15, "possession_composite": 0.65}
    }
  ],
  "disclaimer": "Style-match scouting is a descriptive overlay..."
}
```

Non-`ok` statuses: `invalid_position` (position_group not in the 8
canonical groups), `team_not_found` (target team absent), `no_data`
(empty input), `team_position_not_found` (target team has no players at
the given position meeting the minutes threshold). Candidates are sorted
by `similarity` descending. When `exclude_same_league` is true, players
from the target team's league are filtered out.

### GET /league/form-table

Last-N recent-form table for every team in a league-season. For each team
returns W/D/L counts, points, PPG, 0–100 form rating, chronological form
string (e.g. `"WWDLW"`), trend label (rising/declining/stable), home/away
PPG split, and goals for/against. Teams are sorted by PPG descending.

**Query params**: `league` (optional), `season` (required),
`last_n` (int, default 6, clamped to 1–30)

**Response**:
```json
{
  "status": "ok",
  "league": "Premier League",
  "season": "2425",
  "last_n": 6,
  "teams": [
    {
      "team": "Arsenal",
      "played": 6,
      "wins": 5,
      "draws": 1,
      "losses": 0,
      "points": 16,
      "ppg": 2.67,
      "form_rating": 88.9,
      "form_string": "WWWDW",
      "trend_label": "rising",
      "recent_ppg": 3.0,
      "older_ppg": 2.0,
      "home_ppg": 3.0,
      "away_ppg": 2.5,
      "goals_for": 14,
      "goals_against": 3
    }
  ],
  "disclaimer": "Descriptive season overlay based on in-season results only; does not use the Dixon-Coles prediction model..."
}
```

Non-`ok` statuses: `no_data` (empty input, missing required columns, or
no matches in the requested league-season). The form string is a string
(not a list) of W/D/L characters in chronological order (oldest → newest
within the last-N window). The function is a non-additive interpretive
overlay — it does not modify the prediction model or predict future form.

### GET /league/fixture-difficulty

Retrospective fixture difficulty rating for each team's most recent N
matches in a league-season, using a Bradley-Terry expected-points model
derived from in-season points-per-game. When `team` is omitted, returns
difficulty ratings for every team in the league-season.

**Query params**: `league` (optional), `season` (required),
`team` (optional, case-insensitive), `upcoming_n` (int, default 10,
clamped to 1–30)

**Response**:
```json
{
  "status": "ok",
  "league": "Premier League",
  "season": "2425",
  "team": "Arsenal",
  "upcoming_n": 10,
  "fixtures": [
    {
      "date": "2025-04-12T00:00:00",
      "opponent": "Liverpool",
      "venue": "H",
      "goals_for": 2,
      "goals_against": 1,
      "result": "W",
      "expected_points": 1.42,
      "actual_points": 3,
      "difficulty_label": "very_hard"
    }
  ],
  "summary": {
    "n_matches": 10,
    "avg_expected_points": 1.61,
    "avg_actual_points": 2.10,
    "avg_difficulty": 0.55,
    "difficulty_label": "hard"
  },
  "disclaimer": "Descriptive season overlay based on in-season results only..."
}
```

Non-`ok` statuses: `no_data` (empty input or no matches in the requested
league-season), `team_not_found` (the requested `team` is absent from the
filtered frame — distinct from `no_data`). `difficulty_label` per fixture
is one of `very_hard` / `hard` / `moderate` / `easy` / `very_easy`.
Bradley-Terry strength uses `log1p(ppg)` plus a 0.25 home-advantage
logit; draw intensity is `exp(-|delta|) * 0.28`. The function is a
non-additive interpretive overlay — it does not modify the prediction
model or predict future difficulty.

### GET /league/season-projection

Monte Carlo simulation of the remaining league season, producing
per-team final-position distributions and title / top-N / relegation
probabilities. Assumes a standard double round-robin fixture list
(each pair meets twice, home and away); remaining fixtures are inferred
as the complement of already-played pairs. Reproducible via `random_seed`
(uses `np.random.default_rng`).

**Query params**: `league` (optional), `season` (required),
`num_simulations` (int, default 1000, clamped to 100–10000),
`random_seed` (int, default 42, range 0–2,000,000,000),
`top_n` (int, default 4, clamped to 1–20),
`relegation_slots` (int, default 3, clamped to 0–10)

**Response**:
```json
{
  "status": "ok",
  "league": "Premier League",
  "season": "2425",
  "num_simulations": 1000,
  "random_seed": 42,
  "top_n": 4,
  "relegation_slots": 3,
  "teams": [
    {
      "team": "Arsenal",
      "current_points": 78,
      "games_played": 32,
      "avg_final_points": 86.4,
      "avg_position": 1.2,
      "position_distribution": { "1": 760, "2": 210, "3": 30 },
      "title_probability": 0.76,
      "top_n_probability": 1.0,
      "relegation_probability": 0.0
    }
  ],
  "disclaimer": "Descriptive season overlay based on in-season results only..."
}
```

Non-`ok` statuses: `no_data` (empty input or no matches in the requested
league-season). Teams are sorted by `(avg_position, avg_final_points,
team)` ascending. `position_distribution` only includes positions that
actually occurred in the simulation (may be fewer than the total number
of teams). Per-team probabilities sum to 1.0 across all teams for each
of title / top-N / relegation. The function is a non-additive
interpretive overlay — it does not use the Dixon-Coles prediction model,
rating matrix, or any external odds feed. Projections assume a standard
double round-robin fixture list and a Bradley-Terry strength estimate.

### GET /players/compare

Side-by-side comparison of two players with radar overlay and metric diffs.

**Query params**: `a` (player name), `b` (player name)

**Response**:
```json
{
  "player_a": { "name": "...", "team": "...", "position_group": "ST", "optimized_score": 72.0 },
  "player_b": { "name": "...", "team": "...", "position_group": "CM", "optimized_score": 68.0 },
  "radar_labels": ["Attack", "Possession", "Defense", "Reliability", "Impact"],
  "radar_a": [85.0, 40.0, 20.0, 100.0, 75.0],
  "radar_b": [30.0, 80.0, 70.0, 100.0, 60.0],
  "radar_comparison": [
    { "dimension": "Attack", "player_a": 85.0, "player_b": 30.0, "diff": 55.0, "advantage": "a" }
  ],
  "position_percentile_comparison": [...],
  "stats_comparison": [
    { "metric": "optimized_score", "player_a": 72.0, "player_b": 68.0, "diff": 4.0 }
  ],
  "same_position": false
}
```

Radar values are position-pool percentiles (0-100). Position percentile comparison
uses position-specific dimensions from `POSITION_DIMENSIONS`. Players in different
position groups will have different dimension sets.

### GET /players/{player_name}/similar

Returns the most similar players to the target player based on a 6-dimensional
z-scored feature vector (Attack, Creation, Defense, Possession, Overall,
Availability) compared via cosine similarity. Features are position-weighted
before similarity is computed, so dimensions more relevant to the target's
position carry more signal. The target player is excluded from results.

**Query params**:
- `limit` (int, default=10): Maximum number of similar players to return.
- `season` (str, optional): Filter the comparison pool by season. When omitted,
  the player's own season is used.
- `same_position_only` (bool, default=true): When true, restrict the pool to
  players sharing the target's position group and z-score within that pool.
  When false, build a cross-position pool where each player is z-scored
  against their own position group first, so profiles stay comparable across
  positions.
- `league` (str, optional): Restrict the candidate pool to a single league
  (case-insensitive). The target player is still resolved from the full
  dataset, enabling cross-league scouting use cases (e.g. "find La Liga
  players similar to this Premier League player"). When the target is not in
  the filtered league, its z-score is computed using the filtered pool's
  statistics.
- `min_minutes` (float, optional): Exclude candidates with fewer than this
  many minutes played, to filter out low-reliability comparisons.

**Response**:
```json
{
  "count": 8,
  "target": {
    "name": "string",
    "team": "string",
    "league": "string",
    "season": "2526",
    "position_group": "ST",
    "optimized_score": 80.0
  },
  "features": ["Attack", "Creation", "Defense", "Possession", "Overall", "Availability"],
  "feature_weights": { "Attack": 3.0, "Creation": 1.5, "Defense": 0.5, "Possession": 1.0, "Overall": 1.5, "Availability": 1.0 },
  "filters": {
    "same_position_only": true,
    "league": null,
    "min_minutes": null,
    "season": null
  },
  "similar": [
    {
      "name": "string",
      "team": "string",
      "league": "string",
      "season": "2526",
      "position_group": "ST",
      "optimized_score": 78.0,
      "similarity": 92.0,
      "shared_strengths": ["Attack", "Overall"],
      "shared_weaknesses": ["Defense"],
      "minutes": 2500
    }
  ]
}
```

**Per-position feature weights**: The `feature_weights` field exposes the
active weights used for the target's position group. Weights for the eight
position groups (GK/CB/FB/DM/CM/AM/W/ST) are predefined; unknown positions
fall back to uniform weights (all 1.0). For example, ST weights Attack (npg_p90)
at 3.0 and Defense at 0.5, while CB weights Defense at 3.0 and Attack at 0.5.

**Edge cases**:
- Unknown player returns `{"count": 0, "target": null, "similar": [], "error": "not_found"}`.
- A pool with fewer than 2 rated players returns `{"count": 0, "target": {...}, "similar": [], "error": "pool_too_small"}`.
- A target whose weighted z-vector is zero (e.g. all features identical to pool mean) returns `{"count": 0, "target": {...}, "similar": [], "error": "zero_vector"}`.
- Similarity values are clamped to [0, 1] (negative cosine similarities are treated as zero similarity).
- The target player is always excluded from results, including same-player rows from other seasons.

### GET /search

Returns typeahead suggestions for player and team search inputs. Matching is
prefix-first with substring fallback: prefix matches are returned before
substring matches so that common short queries surface relevant entries first.

**Query params**:
- `q` (str, required): Search term. Results are returned only when `q` has at
  least 2 characters; shorter queries return empty lists.
- `type` (str, default="all"): Filter scope. One of `players`, `teams`, or
  `all`. `players` returns only the `players` array; `teams` returns only the
  `teams` array; `all` returns both.
- `limit` (int, default=10, max=25): Maximum number of results per category
  (players and teams are capped independently).

**Response**:
```json
{
  "players": [
    { "player_name": "string", "team": "string", "position": "string", "rating": 85.0, "league": "string" }
  ],
  "teams": [
    { "team_name": "string", "league": "string" }
  ]
}
```

**Edge cases**:
- Empty or sub-2-char `q` returns `{"players": [], "teams": []}`.
- Empty underlying data returns `{"players": [], "teams": []}` rather than an error.
- `limit` values above 25 are clamped to 25; non-positive values fall back to the default of 10.

### GET /predictions/tuning

Returns Dixon-Coles time-decay parameter tuning results from
`data/reports/calibration_backtest/decay_tuning_results.json` (produced by
`scoutfootball tune-predictions`).

**Response** (when artifacts exist):
```json
{
  "status": "ok",
  "best_decay": 0.005,
  "selection_metric": "rps_1x2",
  "n_folds": 3,
  "n_matches": 45000,
  "candidates": [
    {
      "decay": 0.0,
      "half_life_days": "inf",
      "log_loss_exact": 2.45,
      "brier_1x2": 0.631,
      "rps_1x2": 0.215
    },
    {
      "decay": 0.005,
      "half_life_days": 138.6,
      "log_loss_exact": 2.41,
      "brier_1x2": 0.625,
      "rps_1x2": 0.212
    }
  ]
}
```

**Edge cases**:
- No tuning file: returns `{"status": "not_available", "instructions": "..."}`
- Results are cached for 5 minutes.

### GET /predictions/drift

Returns calibration drift report tracking RPS/Brier/LogLoss across time
windows. Reads `poisson_backtest_predictions.parquet` from the calibration
backtest directory and computes per-window metrics to detect calibration
degradation over time.

**Response** (when artifacts exist):
```json
{
  "status": "ok",
  "drift_detected": false,
  "drift_metric": "rps_1x2",
  "drift_threshold": 0.05,
  "overall_metrics": { "rps_1x2": 0.21, "brier_1x2": 0.58, "log_loss_exact": 2.4 },
  "n_windows": 3,
  "windows": [
    { "start_date": "2024-01-01", "end_date": "2024-03-31", "n_matches": 30, "rps_1x2": 0.20, "brier_1x2": 0.57, "log_loss_exact": 2.38 }
  ],
  "latest_window": { "start_date": "...", "end_date": "...", "n_matches": 30, "rps_1x2": 0.22, "brier_1x2": 0.59, "log_loss_exact": 2.42 }
}
```

**Edge cases**:
- No backtest artifact: returns `{"status": "not_available", "instructions": "..."}`
- Empty predictions: returns `{"status": "no_data"}`
- Missing `match_date` column: returns `{"status": "no_date_column"}`
- Drift is detected when the latest window's `drift_metric` exceeds the
  historical average by more than `drift_threshold` (relative change).
- Results are cached for 5 minutes (shared backtest cache).

### Cache Configuration

The following data loaders and helpers use TTL caches (replacing the previous
permanent `lru_cache`) so that model retrains and data refreshes are visible to
the API without a process restart:

- `_load_all_player_ratings()`
- `load_model_meta()`
- `load_league_metrics()`
- `load_player_value_metrics()`
- `load_player_rolling()` (migrated in H2H round)
- `load_team_rolling()` (migrated in H2H round)
- `_wc_cache` (world-cup helpers in `src/scoutfootball/api.py`)
- `get_prediction_calibration()` (5-minute TTL; migrated in an earlier round)

**Environment variable**: `SCOUTFOOTBALL_CACHE_TTL_SECONDS` (int, default=300)
controls the TTL in seconds for the data loader caches. Each cached function
accepts a `force_refresh=False` parameter; when `True`, the cache entry is
bypassed and repopulated on the next call.

---

## 9.5 Static Snapshot Contracts

`frontend/data/` contains tracked release snapshots consumed by the static demo and Vercel deployment. Each file must be valid JSON (dict or list); Python repr strings are not allowed.

### health.json

**File**: `frontend/data/health.json`
**Source**: `GET /health` response

```json
{
  "status": "ok",
  "data_source": "local",
  "version": "1.0.3"
}
```

### players_list.json

**File**: `frontend/data/players_list.json`
**Source**: `GET /ratings` response

```json
{
  "count": 1234,
  "players": [
    { "player": "string", "team": "string", "league": "string",
      "season": "string", "position_group": "string",
      "optimized_score": 85.0, "minutes": 2500 }
  ]
}
```

### player_compare_pairs.json

**File**: `frontend/data/player_compare_pairs.json`
**Source**: `GET /players/compare` responses for a curated set of player pairs.
Exported by the `compare` section of `scripts/export_static_frontend_data.py`.

Used as the offline fallback for the player comparison view when the API is
unavailable. The frontend loads the pairs JSON once and does a client-side
lookup by normalized player names.

```json
{
  "pairs": [
    {
      "a": "Player One",
      "b": "Player Two",
      "comparison": {
        "player_a": { "name": "...", "team": "...", "position_group": "ST", "optimized_score": 72.0 },
        "player_b": { "name": "...", "team": "...", "position_group": "CM", "optimized_score": 68.0 },
        "radar_labels": ["Attack", "Possession", "Defense", "Reliability", "Impact"],
        "radar_a": [85.0, 40.0, 20.0, 100.0, 75.0],
        "radar_b": [30.0, 80.0, 70.0, 100.0, 60.0],
        "radar_comparison": [
          { "dimension": "Attack", "player_a": 85.0, "player_b": 30.0, "diff": 55.0, "advantage": "a" }
        ],
        "position_percentile_comparison": [],
        "stats_comparison": [
          { "metric": "optimized_score", "player_a": 72.0, "player_b": 68.0, "diff": 4.0 }
        ],
        "same_position": false
      }
    }
  ]
}
```

### team_compare_pairs.json

**File**: `frontend/data/team_compare_pairs.json`
**Source**: `GET /teams/compare` responses for a curated set of team pairs.
Exported by the `compare` section of `scripts/export_static_frontend_data.py`.

Used as the offline fallback for the team comparison view. Same lookup
strategy as `player_compare_pairs.json`.

```json
{
  "pairs": [
    {
      "a": "Team Alpha",
      "b": "Team Beta",
      "comparison": {
        "team_a": { "name": "...", "league": "...", "overall_rating": 65.5, "squad_size": 22 },
        "team_b": { "name": "...", "league": "...", "overall_rating": 68.0, "squad_size": 25 },
        "overall_diff": -2.5,
        "overall_advantage": "b",
        "position_group_comparison": [
          { "group": "GK", "rating_a": 55.0, "rating_b": 60.0, "diff": -5.0, "advantage": "b", "players_a": 2, "players_b": 3 }
        ],
        "top_players_comparison": [],
        "radar_labels": ["GK", "DEF", "MID", "ATT", "Overall"],
        "radar_a": [55.0, 60.0, 65.0, 70.0, 65.5],
        "radar_b": [60.0, 62.0, 68.0, 72.0, 68.0]
      }
    }
  ]
}
```

### Static Snapshot Serialization Rules

1. All values must be JSON-serializable types: `str`, `int`, `float`, `bool`, `None`, `list`, `dict`.
2. dataclass and Pydantic response objects must be serialized via `dataclasses.asdict()` or `model.model_dump()`, not `str(obj)`.
3. `numpy.int64`, `numpy.float64`, `numpy.bool_`, `float('inf')`, and `float('nan')` must be converted to native Python types before serialization.
4. The export script must fail loudly on non-serializable objects rather than falling back to `str()`.

---

## 9.6 Browser-local Scouting Workspace

**Schema**: `scoutfootball.scouting-workspace`

**Current version**: `1.2.0`

**Implementation**: `frontend/scouting-workspace.js`

The workspace is an explicit backup and transfer format for browser-local scouting decisions. It does not change the read-only API boundary and is not a server audit log.

```json
{
  "schema": "scoutfootball.scouting-workspace",
  "version": "1.2.0",
  "exported_at": "2026-07-10T12:00:00.000Z",
  "audit": {
    "workspace_id": "uuid-or-local-id",
    "created_at": "ISO-8601",
    "updated_at": "ISO-8601",
    "revision": 3,
    "device_scope": "browser-local",
    "last_action": "local-edit|manual-export|import-merge|import-replace",
    "app_version": "1.0.3",
    "imported_from": "optional-workspace-id"
  },
  "source": {
    "rating_snapshot_ids": ["snapshot-id"],
    "attribution": "ScoutFootball local scouting decisions; server queues remain read-only"
  },
  "review": {
    "statuses": { "player-key": "pending|reviewing|approved|rejected" },
    "shortlist_notes": { "player-key": "note" },
    "watchlist_notes": { "player-key": "note" },
    "shortlist_dossiers": {
      "stable-player-key": {
        "priority": "urgent|standard|monitor",
        "recommendation": "target|monitor|decline",
        "target_role": "optional role, max 120 characters",
        "rationale": "local decision context and risks, max 2,000 characters"
      }
    }
  },
  "selections": { "watchlist": [], "shortlist": [] },
  "watchlist_snapshot": { "player_keys": [], "saved_at": "ISO-8601|null" }
}
```

Imports are limited to 1 MB, 1,000 status/note/dossier entries and 500 selected players. Unknown statuses, forbidden object keys, oversized strings, invalid dossier enums and unsupported major versions are rejected or sanitized. Safe merge unions selections and uses the workspace with the newer audit timestamp for conflicting status/note/dossier keys; explicit replacement is the only overwrite path. A dossier is browser-local decision context, not a server-side recommendation or a claim that a transfer is in progress.

The scouting view can also export the current shortlist as a browser-local
`scoutfootball.shortlist-decision-pack` v1.0.0 JSON or CSV artifact. It keeps
the loaded shortlist rows together with locally stored priority,
recommendation, target-role, and rationale/risk fields. It is not server-side
audit data, a transfer instruction, or cross-device synchronization; CSV uses
the shared formula-injection guard.

The player comparison view can export the loaded comparison as
`scoutfootball.player-comparison-export` v1.0.0 JSON and can add either
displayed player to the browser-local shortlist. Adding a player does not
persist a server-side recommendation or synchronize the shortlist.

The scouting view can create a browser-local tactical-board project from the
current shortlist. Player markers carry local dossier context only and the
project explicitly states that it is not a confirmed lineup or transfer
recommendation.

The match-prediction view can export the currently loaded prediction as
`scoutfootball.match-prediction-export` v1.1.0 JSON or CSV. It records the
selected fixture, model output, confidence intervals when loaded, and coverage
context, and is browser-local only. When independently loaded, it also records
a compact head-to-head/recent-form context and the current in-play momentum
query. Those sections are explicitly non-additive to the pre-match prediction,
never alter its probabilities, and remain unavailable rather than inferred when
their fetch fails or has not completed. The report is not a betting instruction,
guarantee, or live match intelligence.

Action-value dossier exports may include a separate browser-local shortlist
dossier context. It is explicitly marked non-additive to all action-value
sections and remains a local decision annotation, not a model feature or
server-side recommendation.

`GET /action-values/players/{player_id}/rating-links` returns the separate
`scoutfootball.action-value-rating-links` v1.0.0 contract. StatsBomb action
identifiers and rating artifacts have no shared stable player identifier, so it
only yields candidates when normalized player name, team, and season all agree.
Candidates are not confirmed identities, model features, shortlist entries, or
merged action-value/rating scores; the UI requires human verification and does
not infer a name-only link. Action-value dossier exports may preserve these
strict candidates as a separate, non-additive rating reference.

---

## 10. Cross-Provider Schema Reference

### 10.1 SPADL / atomic-SPADL Compatibility

ScoutFootball's `InternalAction` schema is designed to be compatible with
[socceraction](https://socceraction.readthedocs.io/)'s SPADL representation:

| SPADL Field | InternalAction Field | Notes |
|---|---|---|
| game_id | match_id | |
| period_id | period | |
| seconds | minute * 60 + second | SPADL uses absolute seconds |
| team_id | team_id | |
| player_id | player_id | |
| start_x, start_y | start_x, start_y | Both use 0-100 normalized |
| end_x, end_y | end_x, end_y | Both use 0-100 normalized |
| action_type | action_type | SPADL has 19 types; InternalAction has 13 |
| result_id | result | SPADL uses int (0/1/-1); InternalAction uses string |

**Key differences from SPADL**:
- SPADL uses integer result codes; InternalAction uses string enums.
- SPADL has separate "goalkick" and "freekick" action types; InternalAction
  maps these to existing types via the `qualifier` dict.
- SPADL coordinates are 0-105 x 0-68 (meters); InternalAction uses 0-100 x 100.

### 10.2 kloppy Compatibility

[kloppy](https://kloppy.pysport.org/) provides dataset loading and coordinate
system transformation for tracking data. Current status:

- **Evaluation**: kloppy supports StatsBomb, Opta, Wyscout, TRACAB, SkillCorner,
  Metrica, and FIFA tracking formats with configurable coordinate systems.
- **Risk**: kloppy adds a dependency chain (lxml, requests) and its own coordinate
  normalization may conflict with InternalAction's 0-100 system.
- **Decision**: Use kloppy as reference for coordinate transformation patterns,
  but do not add as direct dependency until P6 cross-provider schema is stable.
  If tracking data enters the pipeline, kloppy's `DatasetTransformer` patterns
  should be adapted rather than imported.

### 10.3 floodlight Compatibility

[floodlight](https://floodlight.readthedocs.io/) provides Game/Team/Player/Event/Frame/Segment
abstractions. Current status:

- **Evaluation**: floodlight's modular design (separate objects for positions,
  events, segments) is a good reference for future tracking data integration.
- **Decision**: Reference only. Not a direct dependency candidate until
  tracking/freeze-frame data enters the pipeline (P8+).

### 10.4 Common Data Format (CDF)

[CDF](https://www.cdf.football/) defines standardized schemas for football data exchange.

- **Evaluation**: CDF's event schema covers similar ground to InternalAction
  but focuses on interoperability between commercial providers.
- **Decision**: Use as validation reference for field completeness; do not
  adopt CDF as the primary internal schema since InternalAction is already
  tailored to the StatsBomb -> xT/VAEP pipeline.

---

## 11. Socceraction Dependency Evaluation

### Current Assessment

[socceraction](https://socceraction.readthedocs.io/en/stable/) provides:
- SPADL and atomic-SPADL action representations
- Expected Threat (xT) model training and evaluation
- VAEP model training and evaluation
- StatsBomb/Wyscout/Opta event conversion

### Dependency Risk

| Factor | Assessment |
|---|---|
| Maintenance | Active (last release 2024, regular commits) |
| Dependencies | numpy, pandas, scipy, scikit-learn (already in project) |
| License | MIT |
| Size | Lightweight (~15 modules) |
| Breaking changes | Low risk; stable API since v1.0 |
| Testing | Well-tested with StatsBomb Open Data |

### Recommendation

**Short-term (P2)**: Use socceraction's SPADL conversion and xT implementation
as reference for validating our `spadl_adapter.py` and `xt.py`. Do NOT add as
direct dependency yet — our internal adapter is already functional and adding
socceraction would require reconciling coordinate systems and action type enums.

**Medium-term (P3-P4)**: Evaluate adding socceraction as an optional dependency
for VAEP training. The key value would be reusing socceraction's VAEP pipeline
rather than reimplementing gradient-boosted feature engineering. Add as
`socceraction[statsbomb]` optional extra in `pyproject.toml` only after:
1. InternalAction schema is stable
2. xT results are validated against socceraction's reference implementation
3. VAEP is the next priority (after truth labels and rating calibration)

**Not recommended**: Using socceraction as the primary action schema.
InternalAction's string-based enums and 0-100 normalized coordinates are
better suited to our multi-source pipeline and frontend visualization needs.

---

## 12. Local Parquet preflight evidence report

`scoutfootball preflight --evidence-out <path>` writes a local JSON evidence
report for the artifacts inspected in that command invocation. It is an
observation record, not a claim that every historical provenance field is
complete.

- `inspection` preserves the content-level decode result, footer comparison,
  schema/content fingerprints, file size, and reader used.
- `provenance.contract` and `provenance.source_license` are copied only when a
  matching directory contract is registered.
- `provenance.snapshot` and `provenance.lineage` are `not_recorded` when the
  registry has no such metadata; filesystem timestamps and filenames are never
  substituted as evidence.
- Reports are local files. The command refuses to replace an existing report
  unless the user explicitly adds `--overwrite-evidence`.

Report type: `scoutfootball.parquet_preflight_evidence`; current report version:
`1.0`.

`scoutfootball source-health` is a separate read-only local observation. It
lists registered raw sources, their recorded license, observed file counts, and
unregistered raw directories. Local file modification times are never treated
as an upstream snapshot timestamp. Its optional `--evidence <preflight JSON>`
attaches only matching raw-artifact inspection fingerprints; malformed reports
and path-escape attempts are rejected, and this attachment never fills in
missing source snapshot provenance.

`scoutfootball record-source-snapshot --source <registered source> --snapshot-date
YYYY-MM-DD --evidence <preflight JSON>` appends one JSONL record to the local
snapshot ledger (default: `data/reports/data_health/source_snapshot_ledger.jsonl`).
It accepts only a registered raw source and evidence containing at least one
matching inspected artifact. The supplied date remains an explicit maintainer
declaration, never a timestamp inferred from the filesystem. Existing records
are never rewritten; duplicate immutable snapshot IDs are refused. Pass the
same ledger to `source-health --snapshot-ledger <path>` to display only its
latest explicitly recorded entry for each source.
