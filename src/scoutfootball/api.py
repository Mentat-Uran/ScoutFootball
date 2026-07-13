"""FastAPI read-only service layer for ScoutFootball."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from scoutfootball.action_value.evidence import (
    get_action_value_evidence as _get_action_value_evidence,
)
from scoutfootball.action_value.evidence import (
    get_action_value_evidence_index as _get_action_value_evidence_index,
)
from scoutfootball.app.data_loader import (
    _MISSING,
    _TTLCache,
    data_source_label,
    load_league_metrics,
    load_model_meta,
    load_oof_predictions,
    load_player_match,
    load_player_ratings,
    load_player_value_metrics,
    load_score_prediction,
    load_score_prediction_dc,
    load_team_match,
)
from scoutfootball.evaluation.scouting_queue import build_scouting_queues
from scoutfootball.head_to_head import get_head_to_head as _compute_head_to_head
from scoutfootball.worldcup.data import (
    BIG5_LEAGUES,
    GROUPS,
    HOSTS,
    compute_group_predictions,
    compute_squad_balance,
    compute_team_strength_details,
    enrich_squads_with_ratings,
    generate_group_stage_matches,
    get_squad,
    get_team_group,
)
from scoutfootball.worldcup.data import (
    compute_team_outlook as _compute_team_outlook,
)
from scoutfootball.worldcup.data import (
    simulate_knockout as _simulate_knockout,
)

_STATSBOMB_ATTRIBUTION = (
    "StatsBomb Open Data must be attributed in any public display. "
    "License: CC-BY-SA 4.0. See https://github.com/statsbomb/open-data"
)


def _read_parquet(path: Path):
    """Read a Parquet file via DuckDB (avoids pyarrow dependency)."""
    import duckdb

    con = duckdb.connect()
    try:
        return con.execute("SELECT * FROM read_parquet(?)", [str(path)]).fetchdf()
    finally:
        con.close()


# ── World Cup data cache ──────────────────────────────────────────
_wc_cache = _TTLCache()
_WC_ENRICHED_KEY = "wc_enriched"
_WC_SCOUTING_KEY = "wc_scouting_queues"


def _get_wc_enriched_squads(force_refresh: bool = False):
    """Return enriched WC squads, computing once and caching with TTL.

    Pass ``force_refresh=True`` to bypass the cache (e.g. after model retraining).
    """
    cached = _wc_cache.get(_WC_ENRICHED_KEY)
    if cached is _MISSING or force_refresh:
        ratings_df = load_player_ratings(force_refresh=force_refresh)
        enriched_squads = enrich_squads_with_ratings(ratings_df)
        strength_details = compute_team_strength_details(
            enriched_squads=enriched_squads
        )
        strengths = {
            team: values["strength"]
            for team, values in strength_details.items()
        }
        cached = {
            "enriched_squads": enriched_squads,
            "strengths": strengths,
            "strength_details": strength_details,
        }
        _wc_cache.set(_WC_ENRICHED_KEY, cached)
    return cached["enriched_squads"], cached["strengths"]


def _get_wc_strength_details(force_refresh: bool = False) -> dict:
    """Return WC team strength details (cached alongside enriched squads)."""
    _get_wc_enriched_squads(force_refresh=force_refresh)
    cached = _wc_cache.get(_WC_ENRICHED_KEY)
    if cached is _MISSING:
        return {}
    return cached.get("strength_details", {})


@dataclass(frozen=True)
class HealthResponse:
    status: str
    data_source: str
    version: str


@dataclass(frozen=True)
class PlayerListResponse:
    player_count: int
    players: list[str]


def _settings():
    from scoutfootball.config import PlatformSettings

    return PlatformSettings.from_root()


def _clean_json_value(value: Any) -> Any:
    import numpy as np

    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    # Handle pandas NA/NaT
    try:
        import pandas as pd
        if value is pd.NA or value is pd.NaT:
            return None
    except (ImportError, AttributeError):
        pass
    if isinstance(value, dict):
        return {key: _clean_json_value(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_clean_json_value(item) for item in value]
    return value


def _read_json(path: Path) -> dict[str, Any]:
    with path.open() as handle:
        return json.load(handle)


def _artifact_file_info(
    path: Path,
    label: str,
    *,
    rows: int | None = None,
    display_root: Path | None = None,
) -> dict[str, Any]:
    display_path = path
    if display_root is not None:
        try:
            display_path = path.resolve().relative_to(display_root.resolve())
        except ValueError:
            display_path = path
    return {
        "label": label,
        "path": str(display_path).replace("\\", "/"),
        "exists": path.exists(),
        "rows": rows,
        "updated_at": path.stat().st_mtime if path.exists() else None,
    }


def _latest_run_id() -> str:
    runs = get_model_runs()
    run_list = runs.get("runs", [])
    if run_list:
        return str(run_list[0].get("run_id", "latest-local"))
    return "latest-local"


def _queue_payload(frame, *, limit: int) -> dict[str, Any]:
    limited = frame.head(limit).copy()
    records = _clean_json_value(limited.to_dict(orient="records"))
    return {"count": len(frame), "players": records}


def health_check() -> HealthResponse:
    from scoutfootball import __version__

    return HealthResponse(
        status="ok",
        data_source=data_source_label(),
        version=__version__,
    )


def list_players() -> PlayerListResponse:
    """Return all unique player names from the ratings dataset."""
    df = load_player_ratings()
    col = (
        "player" if "player" in df.columns
        else ("player_name" if "player_name" in df.columns else None)
    )
    if col is None:
        return PlayerListResponse(player_count=0, players=[])
    names = sorted(df[col].dropna().unique().tolist())
    return PlayerListResponse(player_count=len(names), players=names)


def list_teams() -> list[str]:
    """Return teams supported by the active match-prediction artifacts.

    Player-rating rows can contain comma-joined club histories for transferred
    players. Those values are useful in the rating dataset, but they are not
    valid team identifiers for the prediction model. Prefer the exact team ids
    saved with Dixon-Coles/Poisson and only fall back to ratings data when no
    prediction artifact is available.
    """
    artifact_dir = _settings().model_root / "artifacts"
    for filename in ("dc_team_strengths.parquet", "team_strengths.parquet"):
        path = artifact_dir / filename
        if not path.exists():
            continue
        try:
            frame = _read_parquet(path)
        except Exception:
            continue
        if "team_id" not in frame.columns:
            continue
        teams = {
            str(team).strip()
            for team in frame["team_id"].dropna().tolist()
            if str(team).strip()
        }
        if teams:
            return sorted(teams)

    df = load_player_ratings()
    if "team" in df.columns:
        teams = {
            str(team).strip()
            for team in df["team"].dropna().tolist()
            if str(team).strip() and "," not in str(team)
        }
        return sorted(teams)
    # Fallback to team_match
    tm = load_team_match()
    if "team_name" in tm.columns:
        return sorted(tm["team_name"].dropna().unique().tolist())[:200]
    return []


def search_players_and_teams(
    q: str,
    search_type: str = "all",
    limit: int = 10,
) -> dict[str, Any]:
    """Return matching player and team name suggestions for autocomplete.

    Matches are ranked prefix-first (alphabetical), then substring matches
    (alphabetical). Returns ``{"players": [...], "teams": [...]}``.

    Player entries include ``player_name``, ``team``, ``position``, ``rating``
    (optimized_score) and ``league``. Team entries include ``team_name`` and
    ``league``. Comma-joined club histories (transferred players) are excluded
    from team suggestions.
    """
    empty_result: dict[str, Any] = {"players": [], "teams": []}

    # Input validation — require at least 2 characters
    if not q or len(q.strip()) < 2:
        return empty_result
    q = q.strip()

    # Limit clamping (1..25, default 10)
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 10
    limit = max(1, min(limit, 25))

    # Type validation — invalid values default to "all"
    if search_type not in ("players", "teams", "all"):
        search_type = "all"

    # Load ratings via TTL cache (no forced refresh)
    df = load_player_ratings(force_refresh=False)
    if df is None or df.empty:
        return _clean_json_value(empty_result)

    # Resolve column names (normalize_ratings_frame ensures aliases exist)
    name_col = (
        "player" if "player" in df.columns
        else ("player_name" if "player_name" in df.columns else None)
    )
    team_col = (
        "team" if "team" in df.columns
        else ("team_name" if "team_name" in df.columns else None)
    )
    league_col = "league" if "league" in df.columns else None
    pos_col = (
        "position_group" if "position_group" in df.columns
        else ("sub_position" if "sub_position" in df.columns else None)
    )
    score_col = (
        "optimized_score" if "optimized_score" in df.columns
        else ("rating" if "rating" in df.columns else None)
    )

    players_out: list[dict[str, Any]] = []
    teams_out: list[dict[str, Any]] = []

    # ── Player search ──────────────────────────────────────────────
    if search_type in ("players", "all") and name_col is not None:
        q_lower = q.lower()

        # Deduplicate by player name, keeping the best row (highest score)
        if score_col is not None and score_col in df.columns:
            dedup = df.sort_values(score_col, ascending=False).drop_duplicates(
                subset=[name_col], keep="first",
            )
        else:
            dedup = df.drop_duplicates(subset=[name_col], keep="first")
        dedup = dedup[dedup[name_col].notna()]
        dedup = dedup[dedup[name_col].astype(str).str.strip() != ""]

        dedup_names = dedup[name_col].astype(str).str.lower()
        prefix_mask = dedup_names.str.startswith(q_lower, na=False)
        substring_mask = (
            ~prefix_mask
            & dedup_names.str.contains(q_lower, na=False, regex=False)
        )

        prefix_df = dedup[prefix_mask].sort_values(name_col)
        substring_df = dedup[substring_mask].sort_values(name_col)
        combined = pd.concat([prefix_df, substring_df]).head(limit)

        for _, row in combined.iterrows():
            score_val = row.get(score_col) if score_col else None
            rating = (
                round(float(score_val), 1)
                if score_col and pd.notna(score_val)
                else None
            )
            players_out.append({
                "player_name": str(row.get(name_col, "")),
                "team": str(row.get(team_col, "")) if team_col else "",
                "position": str(row.get(pos_col, "")) if pos_col else "",
                "rating": rating,
                "league": str(row.get(league_col, "")) if league_col else "",
            })

    # ── Team search ────────────────────────────────────────────────
    if search_type in ("teams", "all") and team_col is not None:
        q_lower = q.lower()
        team_df = df[df[team_col].notna()].copy()
        # Exclude comma-joined club histories (transferred players)
        team_df = team_df[~team_df[team_col].astype(str).str.contains(",", na=False)]
        team_df = team_df[team_df[team_col].astype(str).str.strip() != ""]

        if not team_df.empty:
            # Unique teams with league info (first occurrence)
            teams_unique = team_df.drop_duplicates(subset=[team_col], keep="first")
            team_names_lower = teams_unique[team_col].astype(str).str.lower()

            prefix_mask = team_names_lower.str.startswith(q_lower, na=False)
            substring_mask = (
                ~prefix_mask
                & team_names_lower.str.contains(q_lower, na=False, regex=False)
            )

            prefix_teams = teams_unique[prefix_mask].sort_values(team_col)
            substring_teams = teams_unique[substring_mask].sort_values(team_col)
            combined_teams = pd.concat([prefix_teams, substring_teams]).head(limit)

            for _, row in combined_teams.iterrows():
                teams_out.append({
                    "team_name": str(row.get(team_col, "")),
                    "league": str(row.get(league_col, "")) if league_col else "",
                })

    return _clean_json_value({"players": players_out, "teams": teams_out})


def _score_matrix_to_list(prediction) -> list[list[float]]:
    """Convert a score_matrix DataFrame to a 2-D list (0-5 goals)."""
    sm = prediction.score_matrix
    max_goals = 5
    rows = min(max_goals + 1, sm.shape[0])
    cols = min(max_goals + 1, sm.shape[1])
    matrix = []
    for i in range(rows):
        row = []
        for j in range(cols):
            val = float(sm.iloc[i, j]) if i < sm.shape[0] and j < sm.shape[1] else 0.0
            row.append(round(val, 4))
        # Pad if score_matrix is smaller than 6x6
        while len(row) < max_goals + 1:
            row.append(0.0)
        matrix.append(row)
    while len(matrix) < max_goals + 1:
        matrix.append([0.0] * (max_goals + 1))
    return matrix


def _prediction_calibration() -> dict[str, Any]:
    """Load Brier/RPS from prediction artifacts."""
    settings = _settings()
    artifact_dir = settings.data_root / "models" / "artifacts"
    calibration: dict[str, Any] = {}

    # Poisson calibration
    poisson_path = artifact_dir / "poisson_baseline_results.parquet"
    if poisson_path.exists():
        try:
            pf = _read_parquet(poisson_path)
            if not pf.empty:
                row = pf.iloc[0].to_dict()
                calibration["brier"] = _clean_json_value(row.get("brier_1x2"))
                calibration["rps"] = _clean_json_value(row.get("rps_1x2"))
                calibration["log_loss"] = _clean_json_value(row.get("log_loss_exact"))
        except Exception:
            pass

    # DC calibration (overrides if available)
    dc_path = artifact_dir / "dixon_coles_results.parquet"
    if dc_path.exists():
        try:
            dc_df = _read_parquet(dc_path)
            if not dc_df.empty:
                dc_row = dc_df.iloc[0].to_dict()
                calibration["brier"] = _clean_json_value(
                    dc_row.get("brier_1x2", calibration.get("brier"))
                )
                calibration["rps"] = _clean_json_value(
                    dc_row.get("rps_1x2", calibration.get("rps"))
                )
        except Exception:
            pass

    # Full calibration detail is produced by the training backtest. Prefer
    # those evaluated metrics when available; the model-summary parquet only
    # stores fitted parameters and therefore cannot populate Brier/RPS.
    try:
        detail = get_prediction_calibration()
        detail_metrics = detail.get("dixon_coles", {})
        if detail_metrics.get("status") != "ok":
            detail_metrics = detail.get("poisson", {})
        if detail_metrics.get("status") == "ok":
            calibration["brier"] = detail_metrics.get("brier_1x2")
            calibration["rps"] = detail_metrics.get("rps_1x2")
            calibration["log_loss"] = detail_metrics.get("log_loss_exact")
    except Exception:
        pass

    return calibration


def _world_cup_score_matrix(
    home_lambda: float, away_lambda: float, *, max_goals: int = 5
) -> list[list[float]]:
    from scipy.stats import poisson

    goals = np.arange(max_goals + 1)
    home_probs = poisson.pmf(goals, home_lambda)
    away_probs = poisson.pmf(goals, away_lambda)
    matrix = np.outer(home_probs, away_probs)
    matrix = matrix / matrix.sum()
    return [
        [round(float(matrix[i, j]), 4) for j in range(max_goals + 1)]
        for i in range(max_goals + 1)
    ]


def _world_cup_market_summary(score_matrix: list[list[float]]) -> dict[str, float]:
    home_win = 0.0
    draw = 0.0
    away_win = 0.0
    over_2_5 = 0.0
    btts_yes = 0.0
    for home_goals, row in enumerate(score_matrix):
        for away_goals, prob in enumerate(row):
            if home_goals > away_goals:
                home_win += prob
            elif home_goals == away_goals:
                draw += prob
            else:
                away_win += prob
            if home_goals + away_goals >= 3:
                over_2_5 += prob
            if home_goals > 0 and away_goals > 0:
                btts_yes += prob
    return {
        "home_win": round(home_win, 4),
        "draw": round(draw, 4),
        "away_win": round(away_win, 4),
        "over_2_5": round(over_2_5, 4),
        "under_2_5": round(1 - over_2_5, 4),
        "btts_yes": round(btts_yes, 4),
        "btts_no": round(1 - btts_yes, 4),
    }


def get_world_cup_match_prediction(home_team: str, away_team: str) -> dict[str, Any]:
    enriched_squads, strengths = _get_wc_enriched_squads()
    valid_teams = set(enriched_squads)
    if home_team not in valid_teams:
        return {"error": f"World Cup home team '{home_team}' not found"}
    if away_team not in valid_teams:
        return {"error": f"World Cup away team '{away_team}' not found"}
    if home_team == away_team:
        return {"error": "Home and away World Cup teams must be different"}

    home_strength = float(strengths.get(home_team, 0.2))
    away_strength = float(strengths.get(away_team, 0.2))

    strength_gap = math.log((home_strength + 0.05) / (away_strength + 0.05))
    host_bonus = 0.12 if home_team in HOSTS else 0.0
    if away_team in HOSTS:
        host_bonus -= 0.12

    total_goals = 2.35 + 0.55 * ((home_strength + away_strength) - 1.0)
    total_goals = min(max(total_goals, 2.05), 3.35)

    home_share = 1 / (1 + math.exp(-(0.62 * strength_gap + host_bonus)))
    home_share = min(max(home_share, 0.22), 0.78)

    home_lambda = min(max(total_goals * home_share, 0.25), 3.2)
    away_lambda = min(max(total_goals - home_lambda, 0.2), 3.0)

    score_matrix = _world_cup_score_matrix(home_lambda, away_lambda)
    summary = _world_cup_market_summary(score_matrix)

    result = {
        "home_team": home_team,
        "away_team": away_team,
        "model_type": "world_cup_strength_poisson",
        "model_version": "wc-1.0",
        "home_lambda": round(home_lambda, 4),
        "away_lambda": round(away_lambda, 4),
        "home_strength": round(home_strength, 4),
        "away_strength": round(away_strength, 4),
        "host_bonus": round(host_bonus, 4),
        "strength_gap": round(strength_gap, 4),
        "score_matrix": score_matrix,
        **summary,
    }
    return _clean_json_value(result)


def _world_cup_briefing_team_snapshot(
    team: str,
    squad: list[Any],
    strength_detail: dict[str, Any],
) -> dict[str, Any]:
    rated = [player for player in squad if player.has_rating and player.rating is not None]
    top_players = sorted(rated, key=lambda player: float(player.rating), reverse=True)[:5]
    return {
        "team": team,
        "group": get_team_group(team),
        "is_host": team in HOSTS,
        "squad": {
            "total_players": len(squad),
            "rated_players": len(rated),
            "rating_coverage": strength_detail.get("coverage", 0.0),
            "core_avg_rating": strength_detail.get("core_avg_rating"),
            "depth_avg_rating": strength_detail.get("depth_avg_rating"),
            "balance": compute_squad_balance(squad),
            "top_rated_players": [
                {
                    "name": player.name,
                    "position": player.position,
                    "club": player.club,
                    "rating": round(float(player.rating), 2),
                    "rating_confidence": player.rating_confidence,
                }
                for player in top_players
            ],
        },
        "strength": {
            "score": strength_detail.get("strength", 0.0),
            "league_component": strength_detail.get("league_score", 0.0),
            "coverage_component": strength_detail.get("coverage_score", 0.0),
            "big5_component": strength_detail.get("big5_score", 0.0),
        },
    }


def _world_cup_briefing_input_snapshot() -> dict[str, Any]:
    """Expose recorded rating-run lineage without inventing missing hashes."""
    latest_run = (get_model_runs().get("runs") or [{}])[0]
    lineage = latest_run.get("lineage") if isinstance(latest_run, dict) else {}
    if not isinstance(lineage, dict):
        lineage = {}
    dataset_value = lineage.get("dataset_snapshot")
    manifest_value = lineage.get("feature_manifest")
    dataset = dataset_value if isinstance(dataset_value, dict) else {}
    manifest = manifest_value if isinstance(manifest_value, dict) else {}
    input_hash = dataset.get("input_hash") or manifest.get("input_hash") or ""
    return {
        "status": "recorded" if input_hash else "not_recorded",
        "rating_model_run_id": latest_run.get("run_id", "") if isinstance(latest_run, dict) else "",
        "rating_input_hash": input_hash,
        "feature_manifest_hash": manifest.get("sha256", ""),
        "strength_model": {
            "type": "world_cup_strength_ratio_poisson",
            "version": "wc-1.0",
            "score_matrix_max_goals": 5,
            "host_bonus": 0.12,
        },
    }


def get_world_cup_match_briefing(home_team: str, away_team: str) -> dict[str, Any]:
    """Return a source-bounded pre-match briefing for a World Cup pairing.

    This combines the simplified tournament prediction with roster-rating
    coverage, but deliberately does not turn placeholder squads or strength
    proxies into live team news or tactical advice.
    """
    prediction = get_world_cup_match_prediction(home_team, away_team)
    if prediction.get("error"):
        return prediction
    enriched_squads, _ = _get_wc_enriched_squads()
    strength_details = _get_wc_strength_details()
    return _clean_json_value({
        "schema": "scoutfootball.world-cup-match-briefing",
        "version": "1.0.0",
        "status": "ok",
        "fixture": {"home_team": home_team, "away_team": away_team},
        "prediction": prediction,
        "input_snapshot": _world_cup_briefing_input_snapshot(),
        "teams": {
            "home": _world_cup_briefing_team_snapshot(
                home_team,
                enriched_squads.get(home_team, []),
                strength_details.get(home_team, {}),
            ),
            "away": _world_cup_briefing_team_snapshot(
                away_team,
                enriched_squads.get(away_team, []),
                strength_details.get(away_team, {}),
            ),
        },
        "source_attribution": (
            "World Cup squad ratings are derived from ScoutFootball local "
            "FBref/Understat artifacts; the tournament strength model also "
            "uses public Opta priors."
        ),
        "limitations": [
            "Squad lists are placeholders and are not confirmed matchday rosters.",
            "Probabilities come from a simplified strength-ratio Poisson model, "
            "not live team news or market odds.",
            "Lower rating coverage and non-Big5 league proxies can reduce comparability.",
        ],
    })


def _match_model_comparison(home_team: str, away_team: str) -> dict[str, Any] | None:
    """Return 1x2 probabilities from both Poisson and Dixon-Coles for a match.

    Used to populate the ``model_comparison`` field in per-match prediction
    responses so the frontend can render a side-by-side comparison without
    making two separate API calls.
    """
    comparison: dict[str, Any] = {}
    try:
        prediction = load_score_prediction(home_team, away_team)
        if not isinstance(prediction, dict):
            comparison["poisson"] = {
                "home": round(float(prediction.summary.home_win), 4),
                "draw": round(float(prediction.summary.draw), 4),
                "away": round(float(prediction.summary.away_win), 4),
            }
    except Exception:
        pass
    try:
        prediction = load_score_prediction_dc(home_team, away_team)
        if not isinstance(prediction, dict):
            comparison["dixon_coles"] = {
                "home": round(float(prediction.summary.home_win), 4),
                "draw": round(float(prediction.summary.draw), 4),
                "away": round(float(prediction.summary.away_win), 4),
            }
    except Exception:
        pass
    return comparison if len(comparison) >= 2 else None


def get_match_prediction(home_team: str, away_team: str) -> dict:
    try:
        prediction = load_score_prediction(home_team, away_team)
    except Exception as exc:
        return {"error": str(exc)}
    if isinstance(prediction, dict):
        return prediction
    result = {
        "home_team": home_team,
        "away_team": away_team,
        "model_type": "poisson",
        "model_version": "1.0",
        "home_lambda": prediction.home_lambda,
        "away_lambda": prediction.away_lambda,
        "home_win": prediction.summary.home_win,
        "draw": prediction.summary.draw,
        "away_win": prediction.summary.away_win,
        "over_2_5": prediction.summary.over_2_5,
        "btts_yes": prediction.summary.btts_yes,
        "score_matrix": _score_matrix_to_list(prediction),
        "calibration": _prediction_calibration(),
    }
    model_cmp = _match_model_comparison(home_team, away_team)
    if model_cmp:
        result["model_comparison"] = model_cmp
    return _clean_json_value(result)


def get_match_prediction_dc(home_team: str, away_team: str) -> dict:
    """Predict a match using the Dixon-Coles model.

    Returns the same structure as get_match_prediction but with model_type='dixon_coles'
    and includes rho / home_advantage when available.
    Falls back gracefully when DC artifacts are missing.
    """
    try:
        prediction = load_score_prediction_dc(home_team, away_team)
    except Exception as exc:
        return {"error": str(exc)}
    if isinstance(prediction, dict):
        prediction["model_type"] = prediction.get("model_type", "dixon_coles")
        return prediction
    result = {
        "home_team": home_team,
        "away_team": away_team,
        "model_type": "dixon_coles",
        "model_version": "1.0",
        "home_lambda": prediction.home_lambda,
        "away_lambda": prediction.away_lambda,
        "home_win": prediction.summary.home_win,
        "draw": prediction.summary.draw,
        "away_win": prediction.summary.away_win,
        "over_2_5": prediction.summary.over_2_5,
        "btts_yes": prediction.summary.btts_yes,
        "score_matrix": _score_matrix_to_list(prediction),
        "calibration": _prediction_calibration(),
    }
    # Try to enrich with DC-specific parameters (rho, home_advantage)
    try:
        dc_path = (
            _settings().data_root / "models" / "artifacts" / "dixon_coles_results.parquet"
        )
        if dc_path.exists():


            dc_df = _read_parquet(dc_path)
            if not dc_df.empty:
                dc_row = dc_df.iloc[0].to_dict()
                if "rho" in dc_row:
                    result["rho"] = _clean_json_value(dc_row["rho"])
                if "home_advantage" in dc_row:
                    result["home_advantage"] = _clean_json_value(dc_row["home_advantage"])
    except Exception:
        pass  # enrichment is optional
    model_cmp = _match_model_comparison(home_team, away_team)
    if model_cmp:
        result["model_comparison"] = model_cmp
    # Add bootstrap confidence intervals (cached, best-effort)
    ci = _get_prediction_confidence(home_team, away_team)
    if ci:
        result["confidence_intervals"] = ci
    return _clean_json_value(result)


# --- Prediction confidence interval cache ---
_PREDICTION_CI_CACHE: dict[str, Any] = {}
_PREDICTION_CI_TTL_SECONDS = 600  # 10 minutes


def _resolve_tuned_decay() -> float | None:
    """Read the tuned DC decay from calibration backtest results, if available."""
    try:
        tuning_path = (
            _settings().report_root
            / "calibration_backtest"
            / "decay_tuning_results.json"
        )
        if tuning_path.exists():
            data = _read_json(tuning_path)
            best = data.get("best_decay")
            if isinstance(best, (int, float)) and best >= 0:
                return float(best)
    except Exception:
        pass
    return None


def _get_prediction_confidence(
    home_team: str, away_team: str, *, force_refresh: bool = False,
    model_type: str = "dixon_coles",
) -> dict[str, Any] | None:
    """Return cached bootstrap confidence intervals for a match prediction.

    Uses n_bootstrap=50 for API-friendly latency. Returns None on failure.
    The cache is keyed by ``(home, away, model_type)`` so that ensemble
    predictions do not silently reuse DC-only CIs (and vice versa).
    """
    import time as _time

    cache_key = f"{home_team}__{away_team}__{model_type}"
    now = _time.time()
    cached = _PREDICTION_CI_CACHE.get(cache_key)
    if (
        not force_refresh
        and cached is not None
        and now - cached.get("timestamp", 0) < _PREDICTION_CI_TTL_SECONDS
    ):
        cached_data = cached.get("data")
        if isinstance(cached_data, dict):
            # Mark as cache hit for transparency
            cached_data["cached"] = True
            cached_data["cache_age_seconds"] = int(now - cached.get("timestamp", 0))
        return cached_data

    try:
        from scoutfootball.models import bootstrap_prediction_confidence

        team_match = load_team_match()
        if team_match is None or len(team_match) < 50:
            return None

        decay = _resolve_tuned_decay()
        ci = bootstrap_prediction_confidence(
            team_match,
            str(home_team),
            str(away_team),
            n_bootstrap=50,
            confidence_level=0.90,
            decay=decay,
        )
        result = _clean_json_value({
            "n_bootstrap": ci.n_bootstrap,
            "confidence_level": 0.90,
            "failed_iterations": ci.failed_iterations,
            "model_type": model_type,
            "cached": False,
            "home_win": [ci.home_win_low, ci.home_win_high],
            "draw": [ci.draw_low, ci.draw_high],
            "away_win": [ci.away_win_low, ci.away_win_high],
            "home_lambda": [ci.home_lambda_low, ci.home_lambda_high],
            "away_lambda": [ci.away_lambda_low, ci.away_lambda_high],
        })
        _PREDICTION_CI_CACHE[cache_key] = {"data": result, "timestamp": now}
        return result
    except Exception:
        return None


def get_form_weighted_prediction(home_team: str, away_team: str) -> dict:
    """Predict a match using form-weighted Dixon-Coles.

    Uses :func:`fit_dixon_coles_with_form` to apply form-based match weights
    on top of the tuned time-decay parameter. Returns the same structure as
    :func:`get_match_prediction_dc` plus form-specific metadata.
    """
    try:
        from scoutfootball.models import (
            fit_dixon_coles_with_form,
            predict_match_dc,
        )

        team_match = load_team_match()
        if team_match is None or len(team_match) < 50:
            return {"error": "Insufficient team_match data for form-weighted prediction"}

        decay = _resolve_tuned_decay()
        model = fit_dixon_coles_with_form(
            team_match,
            decay=decay,
            form_lookback=5,
            form_factor=0.3,
        )
        pred = predict_match_dc(model, str(home_team), str(away_team))

        result = {
            "home_team": home_team,
            "away_team": away_team,
            "model_type": "dixon_coles_form",
            "model_version": "1.0",
            "home_lambda": pred.home_lambda,
            "away_lambda": pred.away_lambda,
            "home_win": pred.summary.home_win,
            "draw": pred.summary.draw,
            "away_win": pred.summary.away_win,
            "over_2_5": pred.summary.over_2_5,
            "btts_yes": pred.summary.btts_yes,
            "score_matrix": _score_matrix_to_list(pred),
            "form_config": {
                "lookback": 5,
                "form_factor": 0.3,
                "decay": decay,
            },
            "rho": model.rho,
            "home_advantage": model.home_advantage,
        }
        # Add confidence intervals (cached, best-effort)
        ci = _get_prediction_confidence(home_team, away_team, model_type="dixon_coles_form")
        if ci:
            result["confidence_intervals"] = ci
        return _clean_json_value(result)
    except Exception as exc:
        return {"error": str(exc)}


def get_ensemble_prediction(home_team: str, away_team: str, *, recalibrate: bool = False) -> dict:
    """Predict a match using an ensemble of Poisson, DC, and form-weighted DC.

    Blends the three model predictions using cached optimal weights when
    available (falling back to equal weights). When ``recalibrate`` is True,
    applies isotonic recalibration to the blended 1x2 probabilities if a
    fitted calibrator is available from the backtest artifacts.
    """
    try:
        from scoutfootball.models import (
            ensemble_prediction,
            fit_dixon_coles,
            fit_dixon_coles_with_form,
            fit_independent_poisson,
            load_ensemble_weights,
            predict_match,
            predict_match_dc,
        )

        team_match = load_team_match()
        if team_match is None or len(team_match) < 50:
            return {"error": "Insufficient team_match data for ensemble prediction"}

        decay = _resolve_tuned_decay()

        # Fit all three models
        poisson_model = fit_independent_poisson(team_match)
        dc_model = fit_dixon_coles(team_match, decay=decay)
        form_model = fit_dixon_coles_with_form(
            team_match, decay=decay, form_lookback=5, form_factor=0.3,
        )

        # Predict with each model
        poisson_pred = predict_match(poisson_model, str(home_team), str(away_team))
        dc_pred = predict_match_dc(dc_model, str(home_team), str(away_team))
        form_pred = predict_match_dc(form_model, str(home_team), str(away_team))

        # Use cached optimal weights if available, otherwise equal weights
        weights_path = (
            _settings().report_root
            / "calibration_backtest"
            / "ensemble_optimal_weights.json"
        )
        cached_weights = load_ensemble_weights(weights_path)
        weights_source = "equal"
        if cached_weights:
            weights = cached_weights
            weights_source = "optimized"
        else:
            weights = None
            weights_source = "equal"

        ens = ensemble_prediction({
            "poisson": poisson_pred,
            "dixon_coles": dc_pred,
            "dixon_coles_form": form_pred,
        }, weights=weights)

        result = {
            "home_team": home_team,
            "away_team": away_team,
            "model_type": "ensemble",
            "model_version": "1.0",
            "home_lambda": ens.home_lambda,
            "away_lambda": ens.away_lambda,
            "home_win": ens.home_win,
            "draw": ens.draw,
            "away_win": ens.away_win,
            "over_2_5": ens.over_2_5,
            "btts_yes": ens.btts_yes,
            "score_matrix": _clean_json_value(ens.score_matrix.to_numpy().tolist()),
            "weights": ens.weights,
            "weights_source": weights_source,
            "model_predictions": ens.model_predictions,
        }

        # Apply isotonic recalibration if requested and calibrator available
        if recalibrate:
            calibrator = _get_isotonic_calibrator()
            if calibrator is not None:
                from scoutfootball.models import apply_recalibration

                hw, dr, aw = apply_recalibration(
                    calibrator,
                    float(ens.home_win),
                    float(ens.draw),
                    float(ens.away_win),
                )
                result["raw_home_win"] = ens.home_win
                result["raw_draw"] = ens.draw
                result["raw_away_win"] = ens.away_win
                result["home_win"] = hw
                result["draw"] = dr
                result["away_win"] = aw
                result["recalibrated"] = True
                result["calibration_n_samples"] = calibrator.n_samples
            else:
                result["recalibrated"] = False
                result["recalibration_note"] = "No calibration artifacts available"

        # Add confidence intervals (cached, best-effort)
        ci = _get_prediction_confidence(home_team, away_team, model_type="ensemble")
        if ci:
            result["confidence_intervals"] = ci
        return _clean_json_value(result)
    except Exception as exc:
        return {"error": str(exc)}


def get_match_momentum(
    home_team: str,
    away_team: str,
    *,
    home_goals: int = 0,
    away_goals: int = 0,
    minute: int = 0,
) -> dict:
    """Return in-play win probability timeline for a match.

    Computes momentum based on pre-match Dixon-Coles prediction lambdas and
    the current scoreline/minute. Returns a timeline of win/draw/loss
    probabilities at 5-minute intervals from the current minute to 90'.
    """
    try:
        from scoutfootball.models import compute_momentum

        # Get pre-match prediction to extract lambdas
        dc_pred = get_match_prediction_dc(home_team, away_team)
        if "error" in dc_pred:
            return dc_pred

        home_lambda = float(dc_pred.get("home_lambda", 1.3))
        away_lambda = float(dc_pred.get("away_lambda", 1.1))

        momentum = compute_momentum(
            home_team,
            away_team,
            home_lambda,
            away_lambda,
            current_home_goals=home_goals,
            current_away_goals=away_goals,
            current_minute=minute,
        )

        return _clean_json_value({
            "home_team": home_team,
            "away_team": away_team,
            "home_lambda": home_lambda,
            "away_lambda": away_lambda,
            "current_minute": minute,
            "current_home_goals": home_goals,
            "current_away_goals": away_goals,
            "timeline": [
                {
                    "minute": p.minute,
                    "home_win": p.home_win,
                    "draw": p.draw,
                    "away_win": p.away_win,
                    "remaining_home_lambda": p.remaining_home_lambda,
                    "remaining_away_lambda": p.remaining_away_lambda,
                }
                for p in momentum.timeline
            ],
        })
    except Exception as exc:
        return {"error": str(exc)}


def get_calibration_drift() -> dict:
    """Return calibration drift report for the latest backtest predictions.

    Reads the Poisson backtest predictions artifact and computes per-window
    RPS/Brier/LogLoss to detect calibration degradation over time.
    """
    import time

    cache_key = "drift_data"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get("drift_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_calibration_drift

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "poisson_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                # Ensure actual_outcome column exists
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )

                if "match_date" not in preds_df.columns:
                    result = {"status": "no_date_column"}
                else:
                    report = compute_calibration_drift(preds_df)
                    result = _clean_json_value({
                        "status": "ok",
                        "drift_detected": report.drift_detected,
                        "drift_metric": report.drift_metric,
                        "drift_threshold": report.drift_threshold,
                        "overall_metrics": report.overall_metrics,
                        "n_windows": len(report.windows),
                        "windows": report.windows,
                        "latest_window": report.latest_window,
                    })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE["drift_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_calibration_drift_timeline() -> dict:
    """Return a chart-ready calibration drift timeline.

    Wraps :func:`get_calibration_drift` and projects the per-window metrics
    into a flat ``points`` array suitable for a line chart (date + rps/brier/
    log_loss + n_matches). Includes the drift metric name, threshold, and
    detected flag so the frontend can draw a threshold reference line.
    """
    try:
        report = get_calibration_drift()
        if report.get("status") != "ok":
            return report

        windows = report.get("windows", [])
        points: list[dict[str, Any]] = []
        for w in windows:
            points.append({
                "date": w.get("end_date") or w.get("start_date") or "",
                "start_date": w.get("start_date", ""),
                "end_date": w.get("end_date", ""),
                "n_matches": w.get("n_matches", 0),
                "rps_1x2": w.get("rps_1x2"),
                "brier_1x2": w.get("brier_1x2"),
                "log_loss_exact": w.get("log_loss_exact"),
            })

        return _clean_json_value({
            "status": "ok",
            "metric": report.get("drift_metric", "rps_1x2"),
            "threshold": report.get("drift_threshold", 0.05),
            "drift_detected": report.get("drift_detected", False),
            "n_points": len(points),
            "points": points,
            "overall_metrics": report.get("overall_metrics", {}),
        })
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


# --- Isotonic calibrator cache ---
_CALIBRATOR_CACHE: dict[str, Any] = {"calibrator": None, "timestamp": 0.0}
_CALIBRATOR_TTL_SECONDS = 600  # 10 minutes


def _get_isotonic_calibrator(*, force_refresh: bool = False) -> object | None:
    """Return a cached IsotonicCalibrator fitted from backtest predictions.

    Reads the DC decay backtest predictions parquet (which has the best
    calibration) and fits isotonic regression. Returns None if artifacts
    are missing.
    """
    import time as _time

    now = _time.time()
    cached = _CALIBRATOR_CACHE.get("calibrator")
    if (
        not force_refresh
        and cached is not None
        and now - _CALIBRATOR_CACHE.get("timestamp", 0) < _CALIBRATOR_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.models import fit_isotonic_calibrator

        settings = _settings()
        # Prefer DC-with-decay predictions (best calibrated model)
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            # Fall back to Poisson predictions
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            return None

        preds_df = _read_parquet(pred_path)
        if preds_df.empty:
            return None

        # Ensure actual_outcome column exists
        if "actual_outcome" not in preds_df.columns:
            if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                import numpy as np

                preds_df["actual_outcome"] = np.where(
                    preds_df["home_goals"] > preds_df["away_goals"],
                    "home_win",
                    np.where(
                        preds_df["home_goals"] == preds_df["away_goals"],
                        "draw",
                        "away_win",
                    ),
                )
            else:
                return None

        calibrator = fit_isotonic_calibrator(preds_df)
        _CALIBRATOR_CACHE["calibrator"] = calibrator
        _CALIBRATOR_CACHE["timestamp"] = now
        return calibrator
    except Exception:
        return None


def get_ensemble_weights() -> dict:
    """Return the cached ensemble optimal weights and their provenance.

    If no optimization has been run yet, returns ``not_available`` with
    instructions on how to generate the weights.
    """
    import json

    try:
        weights_path = (
            _settings().report_root
            / "calibration_backtest"
            / "ensemble_optimal_weights.json"
        )
        if not weights_path.exists():
            return {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball optimize-ensemble' to compute "
                    "and cache optimal ensemble weights"
                ),
                "default_weights": {
                    "poisson": 0.33,
                    "dixon_coles": 0.34,
                    "dixon_coles_form": 0.33,
                },
            }

        with open(weights_path, encoding="utf-8") as f:
            data = json.load(f)
        return _clean_json_value({
            "status": "ok",
            "weights": data.get("weights"),
            "rps": data.get("rps"),
            "n_matches": data.get("n_matches"),
            "saved_at": data.get("saved_at"),
            "format": data.get("format"),
            "path": str(weights_path),
        })
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_calibration_comparison() -> dict:
    """Return a per-score-line comparison of raw vs recalibrated predictions.

    Fits an isotonic calibrator from the backtest predictions and compares
    raw vs recalibrated Brier/RPS overall and per score line.
    """
    import time

    cache_key = "calibration_comparison"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get("calibration_comparison_timestamp", 0)
        < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_calibration_comparison

        calibrator = _get_isotonic_calibrator()
        if calibrator is None:
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts first"
                ),
            }
        else:
            settings = _settings()
            # Use the same predictions the calibrator was fitted on
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "dixon_coles_decay_backtest_predictions.parquet"
            )
            if not pred_path.exists():
                pred_path = (
                    settings.report_root
                    / "calibration_backtest"
                    / "poisson_backtest_predictions.parquet"
                )
            if not pred_path.exists():
                result = {
                    "status": "not_available",
                    "instructions": "No backtest predictions found",
                }
            else:
                preds_df = _read_parquet(pred_path)
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )

                comparison = compute_calibration_comparison(preds_df, calibrator)
                result = _clean_json_value({
                    "status": "ok",
                    "overall": comparison.overall,
                    "improvement": comparison.improvement,
                    "by_score_line": comparison.by_score_line,
                    "by_league": list(comparison.by_league) if comparison.by_league else [],
                    "n_matches": comparison.n_matches,
                    "calibrator_metrics": {
                        "brier_before": calibrator.brier_before,
                        "brier_after": calibrator.brier_after,
                        "rps_before": calibrator.rps_before,
                        "rps_after": calibrator.rps_after,
                        "n_samples": calibrator.n_samples,
                    },
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE["calibration_comparison_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_prediction_attribution(home_team: str, away_team: str) -> dict:
    """Return permutation-based feature attribution for a match prediction.

    Fits a Dixon-Coles model on the current team-match data and quantifies
    how each factor (home attack, home defense, away attack, away defense,
    home advantage, league mean goals, rho correction) contributes to the
    home-win probability by neutralizing one factor at a time.
    """
    try:
        from scoutfootball.models import (
            compute_prediction_attribution,
            fit_dixon_coles,
        )

        team_match = load_team_match()
        if team_match is None or len(team_match) < 50:
            return {
                "status": "not_available",
                "instructions": "Insufficient team_match data for attribution",
            }

        decay = _resolve_tuned_decay()
        model = fit_dixon_coles(team_match, decay=decay)
        attribution = compute_prediction_attribution(
            model, str(home_team), str(away_team)
        )
        return _clean_json_value({
            "status": "ok",
            "home_team": attribution.home_team,
            "away_team": attribution.away_team,
            "baseline_home_win": attribution.baseline_home_win,
            "baseline_draw": attribution.baseline_draw,
            "baseline_away_win": attribution.baseline_away_win,
            "factors": attribution.factors,
            "model_type": "dixon_coles",
            "method": "permutation-neutralize",
            "n_factors": len(attribution.factors),
        })
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_prediction_attribution_ci(
    home_team: str, away_team: str, *, n_bootstrap: int = 30,
) -> dict:
    """Return bootstrap confidence intervals for prediction attribution deltas.

    Fits Dixon-Coles on the current team-match data, then bootstraps the
    attribution to produce 90% CIs on each factor's delta.
    """
    try:
        from scoutfootball.models import (
            bootstrap_attribution_confidence,
        )

        team_match = load_team_match()
        if team_match is None or len(team_match) < 50:
            return {
                "status": "not_available",
                "instructions": "Insufficient team_match data for bootstrap CI",
            }

        decay = _resolve_tuned_decay()
        ci = bootstrap_attribution_confidence(
            team_match,
            str(home_team),
            str(away_team),
            n_bootstrap=n_bootstrap,
            confidence_level=0.90,
            decay=decay,
            seed=42,
        )
        return _clean_json_value({
            "status": "ok",
            "home_team": ci.home_team,
            "away_team": ci.away_team,
            "n_bootstrap": ci.n_bootstrap,
            "failed_iterations": ci.failed_iterations,
            "confidence_level": 0.90,
            "factor_cis": ci.factor_cis,
        })
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_ensemble_attribution(home_team: str, away_team: str) -> dict:
    """Return per-model and blended prediction attribution for the ensemble.

    Fits Dixon-Coles and form-weighted Dixon-Coles, computes attribution
    for each, and blends with equal weights (or cached optimal weights
    if available).
    """
    try:
        from scoutfootball.models import (
            compute_ensemble_attribution,
            fit_dixon_coles,
            fit_dixon_coles_with_form,
            load_ensemble_weights,
        )

        team_match = load_team_match()
        if team_match is None or len(team_match) < 50:
            return {
                "status": "not_available",
                "instructions": "Insufficient team_match data for ensemble attribution",
            }

        decay = _resolve_tuned_decay()
        dc_model = fit_dixon_coles(team_match, decay=decay)
        form_model = fit_dixon_coles_with_form(team_match, decay=decay)

        models = {"dixon_coles": dc_model, "dixon_coles_form": form_model}

        # Try to load cached optimal weights
        weights = None
        try:
            cached = load_ensemble_weights()
            if cached and "weights" in cached:
                w = cached["weights"]
                weights = {
                    "dixon_coles": w.get("dixon_coles", 0.5),
                    "dixon_coles_form": w.get("dixon_coles_form", 0.5),
                }
        except Exception:
            pass

        ensemble_attr = compute_ensemble_attribution(
            models, str(home_team), str(away_team), weights=weights,
        )

        return _clean_json_value({
            "status": "ok",
            "home_team": ensemble_attr.home_team,
            "away_team": ensemble_attr.away_team,
            "weights": ensemble_attr.weights,
            "weights_source": "optimized" if weights else "equal",
            "blended": {
                "baseline_home_win": ensemble_attr.blended.baseline_home_win,
                "baseline_draw": ensemble_attr.blended.baseline_draw,
                "baseline_away_win": ensemble_attr.blended.baseline_away_win,
                "factors": ensemble_attr.blended.factors,
            },
            "per_model": {
                name: {
                    "baseline_home_win": attr.baseline_home_win,
                    "baseline_draw": attr.baseline_draw,
                    "baseline_away_win": attr.baseline_away_win,
                    "factors": attr.factors,
                }
                for name, attr in ensemble_attr.per_model.items()
            },
        })
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_ensemble_attribution_ci(
    home_team: str, away_team: str, *, n_bootstrap: int = 30,
) -> dict:
    """Return bootstrap CIs for ensemble attribution blended factor deltas.

    Fits both Dixon-Coles and form-weighted Dixon-Coles, bootstraps the
    ensemble attribution to produce 90% CIs on each factor's blended delta.
    """
    try:
        from scoutfootball.models import (
            bootstrap_ensemble_attribution_confidence,
        )

        team_match = load_team_match()
        if team_match is None or len(team_match) < 50:
            return {
                "status": "not_available",
                "instructions": "Insufficient team_match data for ensemble CI",
            }

        decay = _resolve_tuned_decay()

        # Load cached optimal weights if available
        weights = None
        try:
            from scoutfootball.models import load_ensemble_weights

            cached = load_ensemble_weights()
            if cached and "weights" in cached:
                w = cached["weights"]
                weights = {
                    "dixon_coles": w.get("dixon_coles", 0.5),
                    "dixon_coles_form": w.get("dixon_coles_form", 0.5),
                }
        except Exception:
            pass

        ci = bootstrap_ensemble_attribution_confidence(
            team_match,
            str(home_team),
            str(away_team),
            n_bootstrap=n_bootstrap,
            confidence_level=0.90,
            decay=decay,
            weights=weights,
            seed=42,
        )
        return _clean_json_value({
            "status": "ok",
            "home_team": ci.home_team,
            "away_team": ci.away_team,
            "n_bootstrap": ci.n_bootstrap,
            "failed_iterations": ci.failed_iterations,
            "confidence_level": 0.90,
            "weights_source": "optimized" if weights else "equal",
            "factor_cis": ci.factor_cis,
        })
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_value_bet_analysis(
    home_team: str,
    away_team: str,
    *,
    home_odds: float,
    draw_odds: float,
    away_odds: float,
) -> dict:
    """Compute value betting analysis for a match given market odds.

    Fetches the Dixon-Coles prediction for the fixture, then computes
    per-outcome expected value, edge, Kelly fraction, and recommendation.
    """
    try:
        if home_odds < 1.0 or draw_odds < 1.0 or away_odds < 1.0:
            return {"status": "error", "message": "All odds must be >= 1.0"}

        prediction = get_match_prediction_dc(home_team, away_team)
        if "error" in prediction:
            return {"status": "error", "message": prediction["error"]}

        model_probs = {
            "home_win": float(prediction.get("home_win", 0.0)),
            "draw": float(prediction.get("draw", 0.0)),
            "away_win": float(prediction.get("away_win", 0.0)),
        }
        odds = {
            "home_win": float(home_odds),
            "draw": float(draw_odds),
            "away_win": float(away_odds),
        }

        from scoutfootball.evaluation.backtests import compute_value_bets

        analysis = compute_value_bets(model_probs, odds)
        return _clean_json_value({
            "status": "ok",
            "home_team": home_team,
            "away_team": away_team,
            "model_type": prediction.get("model_type", "dixon_coles"),
            "outcomes": [
                {
                    "outcome": o.outcome,
                    "model_probability": o.model_probability,
                    "decimal_odds": o.decimal_odds,
                    "implied_probability": o.implied_probability,
                    "expected_value": o.expected_value,
                    "edge": o.edge,
                    "kelly_fraction": o.kelly_fraction,
                    "recommendation": o.recommendation,
                }
                for o in analysis.outcomes
            ],
            "best_bet": (
                {
                    "outcome": analysis.best_bet.outcome,
                    "model_probability": analysis.best_bet.model_probability,
                    "decimal_odds": analysis.best_bet.decimal_odds,
                    "expected_value": analysis.best_bet.expected_value,
                    "edge": analysis.best_bet.edge,
                    "kelly_fraction": analysis.best_bet.kelly_fraction,
                }
                if analysis.best_bet
                else None
            ),
            "overround": analysis.overround,
            "total_implied": analysis.total_implied,
            "disclaimer": (
                "Analysis uses model probabilities, not live market data. "
                "For research purposes only."
            ),
        })
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_reliability_diagram(*, n_bins: int = 10) -> dict:
    """Return a reliability diagram for 1X2 prediction calibration.

    Reads the backtest predictions artifact and bins predicted probabilities
    against observed frequencies for chart-ready visualization.
    """
    import time

    cache_key = f"reliability_{n_bins}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_reliability_diagram

        settings = _settings()
        # Prefer DC decay predictions, fall back to Poisson
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                diagram = compute_reliability_diagram(preds_df, n_bins=n_bins)
                result = _clean_json_value({
                    "status": "ok",
                    "n_bins": diagram.n_bins,
                    "n_predictions": diagram.n_predictions,
                    "overall": diagram.overall,
                    "per_outcome": {
                        outcome: [
                            {
                                "bin_lower": b.bin_lower,
                                "bin_upper": b.bin_upper,
                                "bin_center": b.bin_center,
                                "mean_predicted": b.mean_predicted,
                                "observed_frequency": b.observed_frequency,
                                "n_samples": b.n_samples,
                            }
                            for b in bins
                        ]
                        for outcome, bins in diagram.per_outcome.items()
                    },
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_team_accuracy(team_id: str, *, min_predictions: int = 3) -> dict:
    """Return per-team prediction accuracy from backtest predictions.

    Computes historical hit rate, average confidence, and calibration gap
    for the specified team (as home or away).
    """
    import time

    cache_key = f"team_accuracy_{team_id}_{min_predictions}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_team_accuracy

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_team_accuracy(preds_df, min_predictions=min_predictions)
                # Filter to the requested team
                team_entry = next(
                    (e for e in report.entries if e.team_id == team_id),
                    None,
                )
                if team_entry is None:
                    result = {
                        "status": "not_found",
                        "team_id": team_id,
                        "message": (
                            f"Team '{team_id}' not found in backtest predictions "
                            f"or has fewer than {min_predictions} predictions"
                        ),
                    }
                else:
                    result = _clean_json_value({
                        "status": "ok",
                        "team_id": team_entry.team_id,
                        "n_predictions": team_entry.n_predictions,
                        "n_correct": team_entry.n_correct,
                        "hit_rate": team_entry.hit_rate,
                        "avg_confidence": team_entry.avg_confidence,
                        "calibration_gap": team_entry.calibration_gap,
                        "last_match_date": team_entry.last_match_date,
                        "overall_hit_rate": report.overall_hit_rate,
                        "total_predictions": report.total_predictions,
                    })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_model_comparison() -> dict:
    """Return a unified comparison of all available backtest models.

    Loads all backtest prediction parquet files (Poisson, Dixon-Coles,
    Dixon-Coles-decay) and computes aligned metrics (log_loss, brier, rps,
    accuracy, avg_confidence, calibration_gap) on the intersection of
    matches. Determines the winning model per metric. Cached for 5 minutes.
    """
    import time

    cache_key = "model_comparison"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_model_comparison

        settings = _settings()
        bt_dir = settings.report_root / "calibration_backtest"

        model_files = [
            ("poisson", "poisson_backtest_predictions.parquet"),
            ("dixon_coles", "dixon_coles_backtest_predictions.parquet"),
            ("dixon_coles_decay", "dixon_coles_decay_backtest_predictions.parquet"),
        ]

        model_predictions: dict[str, Any] = {}
        for model_key, filename in model_files:
            path = bt_dir / filename
            if not path.exists():
                continue
            df = _read_parquet(path)
            if df.empty:
                continue
            if "actual_outcome" not in df.columns:
                if "home_goals" in df.columns and "away_goals" in df.columns:
                    import numpy as np

                    df["actual_outcome"] = np.where(
                        df["home_goals"] > df["away_goals"],
                        "home_win",
                        np.where(
                            df["home_goals"] == df["away_goals"],
                            "draw",
                            "away_win",
                        ),
                    )
            model_predictions[model_key] = df

        if not model_predictions:
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball backtest' to generate prediction artifacts"
                ),
            }
        else:
            comparison = compute_model_comparison(model_predictions)
            result = _clean_json_value({
                "status": "ok",
                "n_aligned": comparison.n_aligned,
                "n_models": comparison.n_models,
                "models": [
                    {
                        "model": e.model,
                        "label": e.label,
                        "n_predictions": e.n_predictions,
                        "log_loss": e.log_loss,
                        "brier": e.brier,
                        "rps": e.rps,
                        "accuracy": e.accuracy,
                        "avg_confidence": e.avg_confidence,
                        "calibration_gap": e.calibration_gap,
                    }
                    for e in comparison.models
                ],
                "metric_winners": comparison.metric_winners,
            })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_scoreline_calibration(*, max_scoreline: int = 5, min_samples: int = 3) -> dict:
    """Return score-line calibration from backtest predictions.

    Groups predictions by actual score-line and compares predicted vs
    actual 1x2 outcome rates per score-line bucket. Prefers Dixon-Coles
    decay predictions, falls back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = f"scoreline_cal_{max_scoreline}_{min_samples}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_scoreline_calibration

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_scoreline_calibration(
                    preds_df,
                    max_scoreline=max_scoreline,
                    min_samples=min_samples,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_matches": report.n_matches,
                    "n_scorelines": report.n_scorelines,
                    "entries": [
                        {
                            "scoreline": e.scoreline,
                            "outcome": e.outcome,
                            "n_matches": e.n_matches,
                            "avg_home_win_prob": e.avg_home_win_prob,
                            "avg_draw_prob": e.avg_draw_prob,
                            "avg_away_win_prob": e.avg_away_win_prob,
                            "actual_home_win_rate": e.actual_home_win_rate,
                            "actual_draw_rate": e.actual_draw_rate,
                            "actual_away_win_rate": e.actual_away_win_rate,
                        }
                        for e in report.entries
                    ],
                    "outcome_summary": report.outcome_summary,
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_confidence_distribution(*, n_bins: int = 10, min_samples_per_bucket: int = 5) -> dict:
    """Return prediction confidence distribution from backtest predictions.

    Buckets predictions by max probability (confidence) and computes
    accuracy per bucket. Prefers Dixon-Coles decay predictions, falls back
    to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = f"confidence_dist_{n_bins}_{min_samples_per_bucket}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_confidence_distribution

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_confidence_distribution(
                    preds_df,
                    n_bins=n_bins,
                    min_samples_per_bucket=min_samples_per_bucket,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_predictions": report.n_predictions,
                    "n_buckets": report.n_buckets,
                    "overall_accuracy": report.overall_accuracy,
                    "overall_confidence": report.overall_confidence,
                    "buckets": [
                        {
                            "bucket_label": b.bucket_label,
                            "bucket_lower": b.bucket_lower,
                            "bucket_upper": b.bucket_upper,
                            "n_predictions": b.n_predictions,
                            "accuracy": b.accuracy,
                            "avg_confidence": b.avg_confidence,
                            "calibration_gap": b.calibration_gap,
                        }
                        for b in report.buckets
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_h2h_bias_correction(
    home_team: str,
    away_team: str,
    *,
    max_correction: float = 0.10,
    min_meetings: int = 3,
    blend_weight: float = 0.25,
) -> dict:
    """Return H2H bias-corrected 1x2 probabilities for a fixture.

    Fetches the baseline DC prediction for the fixture, retrieves the
    historical H2H summary, and nudges the baseline probabilities toward
    the historical outcome rates by ``blend_weight`` (clipped to
    ``±max_correction``).
    """
    try:
        from scoutfootball.evaluation.backtests import compute_h2h_bias_correction

        baseline = get_match_prediction_dc(home_team, away_team)
        if baseline.get("status") not in (None, "ok"):
            return {
                "status": "not_available",
                "reason": "baseline_prediction_unavailable",
                "home_team": home_team,
                "away_team": away_team,
            }

        summary_block = baseline.get("summary", {}) or {}
        baseline_probs = {
            "home_win": float(summary_block.get("home_win_probability", 0.0)),
            "draw": float(summary_block.get("draw_probability", 0.0)),
            "away_win": float(summary_block.get("away_win_probability", 0.0)),
        }

        h2h = get_head_to_head(home_team, away_team)
        h2h_summary = h2h.get("summary", {}) or {}

        report = compute_h2h_bias_correction(
            home_team,
            away_team,
            baseline_probs,
            h2h_summary,
            max_correction=max_correction,
            min_meetings=min_meetings,
            blend_weight=blend_weight,
        )

        return _clean_json_value({
            "status": "ok",
            "home_team": report.home_team,
            "away_team": report.away_team,
            "baseline_probabilities": report.baseline_probabilities,
            "corrected_probabilities": report.corrected_probabilities,
            "h2h_rates": report.h2h_rates,
            "adjustments": report.adjustments,
            "n_meetings": report.n_meetings,
            "correction_applied": report.correction_applied,
            "disclaimer": report.disclaimer,
        })
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_error_analysis(
    *,
    n_bins: int = 5,
    min_samples_per_bucket: int = 5,
    top_n: int = 5,
) -> dict:
    """Return prediction error analysis from backtest predictions.

    Buckets predictions by confidence, computes per-bucket accuracy/Brier/
    log-loss, and surfaces the worst matches (highest Brier) per bucket
    and overall. Prefers Dixon-Coles decay predictions, falls back to
    Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = f"error_analysis_{n_bins}_{min_samples_per_bucket}_{top_n}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_error_analysis

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_error_analysis(
                    preds_df,
                    n_bins=n_bins,
                    min_samples_per_bucket=min_samples_per_bucket,
                    top_n=top_n,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_predictions": report.n_predictions,
                    "n_buckets": report.n_buckets,
                    "overall_accuracy": report.overall_accuracy,
                    "overall_avg_brier": report.overall_avg_brier,
                    "overall_avg_log_loss": report.overall_avg_log_loss,
                    "buckets": [
                        {
                            "bucket_label": b.bucket_label,
                            "bucket_lower": b.bucket_lower,
                            "bucket_upper": b.bucket_upper,
                            "n_predictions": b.n_predictions,
                            "avg_confidence": b.avg_confidence,
                            "accuracy": b.accuracy,
                            "avg_brier": b.avg_brier,
                            "avg_log_loss": b.avg_log_loss,
                            "worst_matches": [
                                {
                                    "match_id": m.match_id,
                                    "home_goals": m.home_goals,
                                    "away_goals": m.away_goals,
                                    "actual_outcome": m.actual_outcome,
                                    "predicted_home_win": m.predicted_home_win,
                                    "predicted_draw": m.predicted_draw,
                                    "predicted_away_win": m.predicted_away_win,
                                    "predicted_outcome": m.predicted_outcome,
                                    "confidence": m.confidence,
                                    "brier": m.brier,
                                    "log_loss": m.log_loss,
                                    "correct": m.correct,
                                }
                                for m in b.worst_matches
                            ],
                        }
                        for b in report.buckets
                    ],
                    "worst_matches_overall": [
                        {
                            "match_id": m.match_id,
                            "home_goals": m.home_goals,
                            "away_goals": m.away_goals,
                            "actual_outcome": m.actual_outcome,
                            "predicted_home_win": m.predicted_home_win,
                            "predicted_draw": m.predicted_draw,
                            "predicted_away_win": m.predicted_away_win,
                            "predicted_outcome": m.predicted_outcome,
                            "confidence": m.confidence,
                            "brier": m.brier,
                            "log_loss": m.log_loss,
                            "correct": m.correct,
                        }
                        for m in report.worst_matches_overall
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_outcome_distribution() -> dict:
    """Return predicted vs actual 1x2 outcome distribution from backtest.

    Reveals whether the model systematically over- or under-predicts a
    particular outcome class (e.g. too many home wins). Prefers Dixon-Coles
    decay predictions, falls back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = "outcome_distribution"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_outcome_distribution

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_outcome_distribution(preds_df)
                result = _clean_json_value({
                    "status": "ok",
                    "n_predictions": report.n_predictions,
                    "predicted_most_likely": report.predicted_most_likely,
                    "actual_counts": report.actual_counts,
                    "dominant_bias": report.dominant_bias,
                    "disclaimer": report.disclaimer,
                    "entries": [
                        {
                            "outcome": e.outcome,
                            "predicted_count": e.predicted_count,
                            "predicted_share": e.predicted_share,
                            "actual_count": e.actual_count,
                            "actual_share": e.actual_share,
                            "distribution_gap": e.distribution_gap,
                        }
                        for e in report.entries
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_temporal_validation(
    *, n_windows: int = 6, min_samples_per_window: int = 10,
) -> dict:
    """Return per-window metric trends from backtest predictions.

    Groups predictions into time windows and computes accuracy, Brier, RPS,
    LogLoss, and avg_confidence per window. Prefers Dixon-Coles decay
    predictions, falls back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = f"temporal_validation_{n_windows}_{min_samples_per_window}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_temporal_validation

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_temporal_validation(
                    preds_df,
                    n_windows=n_windows,
                    min_samples_per_window=min_samples_per_window,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_total_matches": report.n_total_matches,
                    "n_windows": report.n_windows,
                    "overall_accuracy": report.overall_accuracy,
                    "overall_brier": report.overall_brier,
                    "overall_rps": report.overall_rps,
                    "overall_log_loss": report.overall_log_loss,
                    "trend": report.trend,
                    "disclaimer": report.disclaimer,
                    "windows": [
                        {
                            "window_label": w.window_label,
                            "window_start": w.window_start,
                            "window_end": w.window_end,
                            "n_matches": w.n_matches,
                            "accuracy": w.accuracy,
                            "brier": w.brier,
                            "rps": w.rps,
                            "log_loss": w.log_loss,
                            "avg_confidence": w.avg_confidence,
                        }
                        for w in report.windows
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_probability_heatmap(
    *, n_bins: int = 5, min_samples_per_cell: int = 3,
) -> dict:
    """Return 2D probability heatmap from backtest predictions.

    Buckets predictions into an n_bins × n_bins grid of home_win vs
    away_win probability. Prefers Dixon-Coles decay predictions, falls
    back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = f"probability_heatmap_{n_bins}_{min_samples_per_cell}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_probability_heatmap

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_probability_heatmap(
                    preds_df,
                    n_bins=n_bins,
                    min_samples_per_cell=min_samples_per_cell,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_predictions": report.n_predictions,
                    "n_bins": report.n_bins,
                    "total_density": report.total_density,
                    "disclaimer": report.disclaimer,
                    "cells": [
                        {
                            "home_bin": c.home_bin,
                            "away_bin": c.away_bin,
                            "home_lo": c.home_lo,
                            "home_hi": c.home_hi,
                            "away_lo": c.away_lo,
                            "away_hi": c.away_hi,
                            "count": c.count,
                            "density": c.density,
                            "accuracy": c.accuracy,
                            "avg_confidence": c.avg_confidence,
                        }
                        for c in report.cells
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_prediction_staleness() -> dict:
    """Return model staleness indicator from backtest data coverage.

    Reports the backtest data date range, days since last match, and
    staleness level (fresh/aging/stale). Prefers Dixon-Coles decay
    predictions, falls back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = "prediction_staleness"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_prediction_staleness

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        model_type = "dixon_coles_decay"
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
            model_type = "poisson"
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                report = compute_prediction_staleness(
                    preds_df, model_type=model_type,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "has_backtest": report.has_backtest,
                    "backtest_start": report.backtest_start,
                    "backtest_end": report.backtest_end,
                    "n_backtest_matches": report.n_backtest_matches,
                    "model_type": report.model_type,
                    "days_since_backtest_end": report.days_since_backtest_end,
                    "staleness_level": report.staleness_level,
                    "disclaimer": report.disclaimer,
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_confidence_interval_plot(
    *, max_points: int = 500,
    ci_lower_col: str = "home_win_ci_lower",
    ci_upper_col: str = "home_win_ci_upper",
) -> dict:
    """Return CI width vs match confidence scatter plot data.

    Each prediction becomes a scatter point with confidence, CI bounds,
    CI width, and correctness flag. Prefers Dixon-Coles decay predictions,
    falls back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = f"ci_plot_{max_points}_{ci_lower_col}_{ci_upper_col}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_confidence_interval_plot,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            elif (
                ci_lower_col not in preds_df.columns
                or ci_upper_col not in preds_df.columns
            ):
                result = {
                    "status": "not_available",
                    "instructions": (
                        f"Backtest predictions do not include CI columns "
                        f"({ci_lower_col}, {ci_upper_col}). Re-run "
                        f"backtest with bootstrap CI generation enabled."
                    ),
                }
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_confidence_interval_plot(
                    preds_df,
                    ci_lower_col=ci_lower_col,
                    ci_upper_col=ci_upper_col,
                    max_points=max_points,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_predictions": report.n_predictions,
                    "avg_confidence": report.avg_confidence,
                    "avg_ci_width": report.avg_ci_width,
                    "correlation": report.correlation,
                    "disclaimer": report.disclaimer,
                    "points": [
                        {
                            "match_id": p.match_id,
                            "home_team": p.home_team,
                            "away_team": p.away_team,
                            "confidence": p.confidence,
                            "ci_lower": p.ci_lower,
                            "ci_upper": p.ci_upper,
                            "ci_width": p.ci_width,
                            "actual_outcome": p.actual_outcome,
                            "correct": p.correct,
                        }
                        for p in report.points
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_fold_comparison(*, min_samples_per_fold: int = 5) -> dict:
    """Return per-fold metrics comparison from backtest predictions.

    Groups backtest predictions by the ``fold`` column and computes
    accuracy, Brier, RPS, LogLoss, and avg_confidence per fold, plus a
    stability indicator. Prefers Dixon-Coles decay predictions, falls
    back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = f"fold_comparison_{min_samples_per_fold}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_fold_comparison

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            elif "fold" not in preds_df.columns:
                result = {
                    "status": "not_available",
                    "instructions": (
                        "Backtest predictions do not include a 'fold' column. "
                        "Re-run backtest with cross-validation fold assignment."
                    ),
                }
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_fold_comparison(
                    preds_df, min_samples_per_fold=min_samples_per_fold,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_folds": report.n_folds,
                    "n_total_matches": report.n_total_matches,
                    "overall_accuracy": report.overall_accuracy,
                    "overall_brier": report.overall_brier,
                    "overall_rps": report.overall_rps,
                    "overall_log_loss": report.overall_log_loss,
                    "accuracy_std": report.accuracy_std,
                    "brier_std": report.brier_std,
                    "rps_std": report.rps_std,
                    "stability": report.stability,
                    "disclaimer": report.disclaimer,
                    "folds": [
                        {
                            "fold": f.fold,
                            "n_matches": f.n_matches,
                            "accuracy": f.accuracy,
                            "brier": f.brier,
                            "rps": f.rps,
                            "log_loss": f.log_loss,
                            "avg_confidence": f.avg_confidence,
                        }
                        for f in report.folds
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_league_error_analysis(
    *, min_matches_per_league: int = 10, top_n: int = 3,
) -> dict:
    """Return per-league error analysis from backtest predictions.

    Groups backtest predictions by the ``league`` column and computes
    accuracy, Brier, RPS, LogLoss, and avg_confidence per league, plus
    the top-N worst predictions per league. Prefers Dixon-Coles decay
    predictions, falls back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = f"league_error_{min_matches_per_league}_{top_n}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_league_error_analysis,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            elif "league" not in preds_df.columns:
                result = {
                    "status": "not_available",
                    "instructions": (
                        "Backtest predictions do not include a 'league' "
                        "column. Re-run backtest with league metadata."
                    ),
                }
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_league_error_analysis(
                    preds_df,
                    min_matches_per_league=min_matches_per_league,
                    top_n=top_n,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_leagues": report.n_leagues,
                    "n_total_matches": report.n_total_matches,
                    "overall_accuracy": report.overall_accuracy,
                    "overall_brier": report.overall_brier,
                    "disclaimer": report.disclaimer,
                    "leagues": [
                        {
                            "league": lg.league,
                            "n_matches": lg.n_matches,
                            "accuracy": lg.accuracy,
                            "brier": lg.brier,
                            "rps": lg.rps,
                            "log_loss": lg.log_loss,
                            "avg_confidence": lg.avg_confidence,
                            "worst_matches": [
                                {
                                    "match_id": m.match_id,
                                    "home_goals": m.home_goals,
                                    "away_goals": m.away_goals,
                                    "actual_outcome": m.actual_outcome,
                                    "predicted_home_win": m.predicted_home_win,
                                    "predicted_draw": m.predicted_draw,
                                    "predicted_away_win": m.predicted_away_win,
                                    "predicted_outcome": m.predicted_outcome,
                                    "confidence": m.confidence,
                                    "brier": m.brier,
                                    "log_loss": m.log_loss,
                                    "correct": m.correct,
                                }
                                for m in lg.worst_matches
                            ],
                        }
                        for lg in report.leagues
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_feature_importance(
    *, n_bins: int = 5, min_samples_per_bin: int = 10,
) -> dict:
    """Return feature importance ranking from backtest predictions.

    Ranks input feature columns by how strongly they separate prediction
    error (bin-wise Brier standard deviation). Prefers Dixon-Coles decay
    predictions, falls back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = f"feature_importance_{n_bins}_{min_samples_per_bin}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_feature_importance,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_feature_importance(
                    preds_df,
                    n_bins=n_bins,
                    min_samples_per_bin=min_samples_per_bin,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_features": report.n_features,
                    "n_total_matches": report.n_total_matches,
                    "overall_brier": report.overall_brier,
                    "disclaimer": report.disclaimer,
                    "features": [
                        {
                            "feature": fe.feature,
                            "importance": fe.importance,
                            "mean_value": fe.mean_value,
                            "std_value": fe.std_value,
                            "n_matches": fe.n_matches,
                            "bins": [
                                {
                                    "bin_label": b.bin_label,
                                    "bin_lower": b.bin_lower,
                                    "bin_upper": b.bin_upper,
                                    "n_matches": b.n_matches,
                                    "accuracy": b.accuracy,
                                    "brier": b.brier,
                                    "avg_confidence": b.avg_confidence,
                                }
                                for b in fe.bins
                            ],
                        }
                        for fe in report.features
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_ci_coverage(
    *,
    ci_lower_col: str = "home_win_ci_lower",
    ci_upper_col: str = "home_win_ci_upper",
    nominal_level: float | None = None,
    n_bins: int = 5,
    min_samples_per_bucket: int = 10,
) -> dict:
    """Return confidence band coverage analysis from backtest predictions.

    Validates whether bootstrap confidence intervals achieve their nominal
    coverage. Prefers Dixon-Coles decay predictions, falls back to Poisson.
    Cached for 5 minutes.
    """
    import time

    cache_key = (
        f"ci_coverage_{ci_lower_col}_{ci_upper_col}_{nominal_level}_"
        f"{n_bins}_{min_samples_per_bucket}"
    )
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_ci_coverage

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            elif ci_lower_col not in preds_df.columns or ci_upper_col not in preds_df.columns:
                result = {
                    "status": "not_available",
                    "instructions": (
                        f"Backtest predictions do not include CI columns "
                        f"'{ci_lower_col}'/'{ci_upper_col}'. Re-run backtest "
                        f"with bootstrap CI generation enabled."
                    ),
                }
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_ci_coverage(
                    preds_df,
                    ci_lower_col=ci_lower_col,
                    ci_upper_col=ci_upper_col,
                    nominal_level=nominal_level,
                    n_bins=n_bins,
                    min_samples_per_bucket=min_samples_per_bucket,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "overall_coverage": report.overall_coverage,
                    "avg_ci_width": report.avg_ci_width,
                    "n_matches": report.n_matches,
                    "nominal_level": report.nominal_level,
                    "coverage_assessment": report.coverage_assessment,
                    "disclaimer": report.disclaimer,
                    "buckets": [
                        {
                            "bucket_label": b.bucket_label,
                            "confidence_lower": b.confidence_lower,
                            "confidence_upper": b.confidence_upper,
                            "n_matches": b.n_matches,
                            "empirical_coverage": b.empirical_coverage,
                            "avg_ci_width": b.avg_ci_width,
                            "nominal_coverage": b.nominal_coverage,
                        }
                        for b in report.buckets
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_calibration_drift_heatmap(
    *,
    window_size: str = "90D",
    n_confidence_bins: int = 4,
    min_samples_per_cell: int = 5,
) -> dict:
    """Return calibration drift heatmap from backtest predictions.

    Computes a 2D grid of accuracy/Brier/RPS/LogLoss over time windows ×
    confidence buckets. Prefers Dixon-Coles decay predictions, falls back
    to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = (
        f"drift_heatmap_{window_size}_{n_confidence_bins}_{min_samples_per_cell}"
    )
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_calibration_drift_heatmap,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            elif "match_date" not in preds_df.columns:
                result = {
                    "status": "not_available",
                    "instructions": (
                        "Backtest predictions do not include a 'match_date' "
                        "column. Re-run backtest with match date metadata."
                    ),
                }
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_calibration_drift_heatmap(
                    preds_df,
                    window_size=window_size,
                    n_confidence_bins=n_confidence_bins,
                    min_samples_per_cell=min_samples_per_cell,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_windows": report.n_windows,
                    "n_confidence_buckets": report.n_confidence_buckets,
                    "n_total_matches": report.n_total_matches,
                    "window_labels": report.window_labels,
                    "confidence_bucket_labels": report.confidence_bucket_labels,
                    "drift_detected": report.drift_detected,
                    "disclaimer": report.disclaimer,
                    "cells": [
                        {
                            "window_label": c.window_label,
                            "window_start": c.window_start,
                            "window_end": c.window_end,
                            "confidence_bucket": c.confidence_bucket,
                            "confidence_lower": c.confidence_lower,
                            "confidence_upper": c.confidence_upper,
                            "n_matches": c.n_matches,
                            "accuracy": c.accuracy,
                            "brier": c.brier,
                            "rps": c.rps,
                            "log_loss": c.log_loss,
                        }
                        for c in report.cells
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_error_clustering(
    *, n_clusters: int = 3, error_percentile: float = 0.1,
    min_samples_per_cluster: int = 5,
) -> dict:
    """Return prediction error clustering from backtest predictions.

    Clusters the worst predictions by feature signature using k-means.
    Prefers Dixon-Coles decay predictions, falls back to Poisson.
    Cached for 5 minutes.
    """
    import time

    cache_key = (
        f"error_clustering_{n_clusters}_{error_percentile}_"
        f"{min_samples_per_cluster}"
    )
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_error_clustering,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_error_clustering(
                    preds_df,
                    n_clusters=n_clusters,
                    error_percentile=error_percentile,
                    min_samples_per_cluster=min_samples_per_cluster,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_clusters": report.n_clusters,
                    "n_total_matches": report.n_total_matches,
                    "n_features_used": report.n_features_used,
                    "error_percentile": report.error_percentile,
                    "n_worst_matches": report.n_worst_matches,
                    "overall_avg_brier": report.overall_avg_brier,
                    "disclaimer": report.disclaimer,
                    "clusters": [
                        {
                            "cluster_id": c.cluster_id,
                            "n_matches": c.n_matches,
                            "avg_brier": c.avg_brier,
                            "avg_confidence": c.avg_confidence,
                            "accuracy": c.accuracy,
                            "dominant_actual_outcome": c.dominant_actual_outcome,
                            "dominant_predicted_outcome": c.dominant_predicted_outcome,
                            "top_centroid_features": [
                                {
                                    "feature": f.feature,
                                    "centroid_value": f.centroid_value,
                                    "abs_centroid": f.abs_centroid,
                                }
                                for f in c.top_centroid_features
                            ],
                        }
                        for c in report.clusters
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_data_drift(
    *,
    split_ratio: float = 0.7,
    split_date: str | None = None,
    p_value_threshold: float = 0.05,
    min_samples: int = 20,
) -> dict:
    """Return data drift detection from backtest predictions.

    Detects feature distribution drift between train and holdout windows
    via two-sample Kolmogorov-Smirnov test. Prefers Dixon-Coles decay
    predictions, falls back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = (
        f"data_drift_{split_ratio}_{split_date}_"
        f"{p_value_threshold}_{min_samples}"
    )
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import compute_data_drift

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            elif "match_date" not in preds_df.columns:
                result = {
                    "status": "not_available",
                    "instructions": (
                        "Backtest predictions do not include a 'match_date' "
                        "column. Re-run backtest with match date metadata."
                    ),
                }
            else:
                report = compute_data_drift(
                    preds_df,
                    split_ratio=split_ratio,
                    split_date=split_date,
                    p_value_threshold=p_value_threshold,
                    min_samples=min_samples,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_features": report.n_features,
                    "n_drifted": report.n_drifted,
                    "drift_ratio": report.drift_ratio,
                    "n_train": report.n_train,
                    "n_holdout": report.n_holdout,
                    "split_date": report.split_date,
                    "p_value_threshold": report.p_value_threshold,
                    "disclaimer": report.disclaimer,
                    "features": [
                        {
                            "feature": e.feature,
                            "ks_statistic": e.ks_statistic,
                            "p_value": e.p_value,
                            "drifted": e.drifted,
                            "train_mean": e.train_mean,
                            "holdout_mean": e.holdout_mean,
                            "mean_delta": e.mean_delta,
                            "train_std": e.train_std,
                            "holdout_std": e.holdout_std,
                        }
                        for e in report.features
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_ci_width_analysis(
    *,
    ci_lower_col: str = "home_win_ci_lower",
    ci_upper_col: str = "home_win_ci_upper",
    n_bins: int = 5,
    min_samples_per_bucket: int = 10,
) -> dict:
    """Return CI width analysis from backtest predictions.

    Analyzes CI width distribution across confidence levels. Prefers
    Dixon-Coles decay predictions, falls back to Poisson. Cached for
    5 minutes.
    """
    import time

    cache_key = (
        f"ci_width_{ci_lower_col}_{ci_upper_col}_"
        f"{n_bins}_{min_samples_per_bucket}"
    )
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_ci_width_analysis,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            elif ci_lower_col not in preds_df.columns or ci_upper_col not in preds_df.columns:
                result = {
                    "status": "not_available",
                    "instructions": (
                        f"Backtest predictions do not include CI columns "
                        f"'{ci_lower_col}'/'{ci_upper_col}'. Re-run backtest "
                        f"with bootstrap CI generation enabled."
                    ),
                }
            else:
                report = compute_ci_width_analysis(
                    preds_df,
                    ci_lower_col=ci_lower_col,
                    ci_upper_col=ci_upper_col,
                    n_bins=n_bins,
                    min_samples_per_bucket=min_samples_per_bucket,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_matches": report.n_matches,
                    "overall_avg_ci_width": report.overall_avg_ci_width,
                    "overall_avg_confidence": report.overall_avg_confidence,
                    "width_confidence_correlation": report.width_confidence_correlation,
                    "widest_bucket": report.widest_bucket,
                    "narrowest_bucket": report.narrowest_bucket,
                    "assessment": report.assessment,
                    "disclaimer": report.disclaimer,
                    "buckets": [
                        {
                            "bucket_label": b.bucket_label,
                            "confidence_lower": b.confidence_lower,
                            "confidence_upper": b.confidence_upper,
                            "n_matches": b.n_matches,
                            "avg_ci_width": b.avg_ci_width,
                            "avg_ci_lower": b.avg_ci_lower,
                            "avg_ci_upper": b.avg_ci_upper,
                            "width_std": b.width_std,
                            "relative_width": b.relative_width,
                        }
                        for b in report.buckets
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_scenario_stress_test(
    *,
    shift_type: str = "outcome_swap",
    shift_ratio: float = 0.2,
    random_state: int = 42,
) -> dict:
    """Return scenario stress test from backtest predictions.

    Simulates distribution shifts and measures model degradation.
    Prefers Dixon-Coles decay predictions, falls back to Poisson.
    Cached for 5 minutes.
    """
    import time

    cache_key = f"stress_test_{shift_type}_{shift_ratio}_{random_state}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_scenario_stress_test,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                # Ensure actual_outcome column exists
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_scenario_stress_test(
                    preds_df,
                    shift_type=shift_type,
                    shift_ratio=shift_ratio,
                    random_state=random_state,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "shift_type": report.shift_type,
                    "shift_ratio": report.shift_ratio,
                    "baseline": {
                        "n_matches": report.baseline.n_matches,
                        "accuracy": report.baseline.accuracy,
                        "brier": report.baseline.brier,
                        "rps": report.baseline.rps,
                        "log_loss": report.baseline.log_loss,
                        "avg_confidence": report.baseline.avg_confidence,
                    },
                    "stressed": {
                        "n_matches": report.stressed.n_matches,
                        "accuracy": report.stressed.accuracy,
                        "brier": report.stressed.brier,
                        "rps": report.stressed.rps,
                        "log_loss": report.stressed.log_loss,
                        "avg_confidence": report.stressed.avg_confidence,
                    },
                    "accuracy_delta": report.accuracy_delta,
                    "brier_delta": report.brier_delta,
                    "rps_delta": report.rps_delta,
                    "log_loss_delta": report.log_loss_delta,
                    "confidence_delta": report.confidence_delta,
                    "degradation_score": report.degradation_score,
                    "assessment": report.assessment,
                    "n_shifted": report.n_shifted,
                    "disclaimer": report.disclaimer,
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_team_calibration_drift(
    *,
    team_col: str = "home_team",
    team_name: str,
    window_size: str = "180D",
    min_samples_per_window: int = 5,
    n_windows: int | None = None,
) -> dict:
    """Return per-team calibration drift from backtest predictions.

    Filters predictions to a single team and computes per-window
    calibration drift. Prefers Dixon-Coles decay predictions, falls
    back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = (
        f"team_drift_{team_col}_{team_name}_{window_size}_"
        f"{min_samples_per_window}_{n_windows}"
    )
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_team_calibration_drift,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            elif team_col not in preds_df.columns:
                result = {
                    "status": "not_available",
                    "instructions": (
                        f"Backtest predictions do not include team column "
                        f"'{team_col}'."
                    ),
                }
            elif "match_date" not in preds_df.columns:
                result = {
                    "status": "not_available",
                    "instructions": (
                        "Backtest predictions do not include 'match_date'."
                    ),
                }
            else:
                # Ensure actual_outcome column exists
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_team_calibration_drift(
                    preds_df,
                    team_col=team_col,
                    team_name=team_name,
                    window_size=window_size,
                    min_samples_per_window=min_samples_per_window,
                    n_windows=n_windows,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "team_col": report.team_col,
                    "team_name": report.team_name,
                    "n_total_matches": report.n_total_matches,
                    "n_windows": report.n_windows,
                    "drift_detected": report.drift_detected,
                    "latest_brier": report.latest_brier,
                    "historical_avg_brier": report.historical_avg_brier,
                    "relative_change": report.relative_change,
                    "trend": report.trend,
                    "disclaimer": report.disclaimer,
                    "points": [
                        {
                            "window_label": p.window_label,
                            "n_matches": p.n_matches,
                            "accuracy": p.accuracy,
                            "brier": p.brier,
                            "avg_confidence": p.avg_confidence,
                        }
                        for p in report.points
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_prediction_uncertainty(
    *,
    max_points: int = 500,
) -> dict:
    """Return prediction uncertainty analysis from backtest predictions.

    Computes per-match Shannon entropy, margin, and dispersion.
    Prefers Dixon-Coles decay predictions, falls back to Poisson.
    Cached for 5 minutes.
    """
    import time

    cache_key = f"uncertainty_{max_points}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_prediction_uncertainty,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                # Ensure actual_outcome column exists
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_prediction_uncertainty(
                    preds_df,
                    max_points=max_points,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_matches": report.n_matches,
                    "avg_entropy": report.avg_entropy,
                    "avg_margin": report.avg_margin,
                    "avg_dispersion": report.avg_dispersion,
                    "high_uncertainty_count": report.high_uncertainty_count,
                    "high_uncertainty_accuracy": report.high_uncertainty_accuracy,
                    "low_uncertainty_accuracy": report.low_uncertainty_accuracy,
                    "entropy_accuracy_correlation": report.entropy_accuracy_correlation,
                    "disclaimer": report.disclaimer,
                    "points": [
                        {
                            "match_id": p.match_id,
                            "home_team": p.home_team,
                            "away_team": p.away_team,
                            "confidence": p.confidence,
                            "entropy": p.entropy,
                            "margin": p.margin,
                            "dispersion": p.dispersion,
                            "predicted_outcome": p.predicted_outcome,
                            "actual_outcome": p.actual_outcome,
                            "correct": p.correct,
                            "uncertainty_label": p.uncertainty_label,
                        }
                        for p in report.points
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_profit_loss_simulation(
    *,
    max_points: int = 500,
) -> dict:
    """Return profit/loss simulation from backtest predictions.

    Simulates flat-stake and Kelly betting on the model's predicted
    outcome using implied odds from model probabilities. Prefers
    Dixon-Coles decay predictions, falls back to Poisson. Cached for
    5 minutes.
    """
    import time

    cache_key = f"profit_loss_{max_points}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_profit_loss_simulation,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_profit_loss_simulation(
                    preds_df,
                    max_points=max_points,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_matches": report.n_matches,
                    "n_correct": report.n_correct,
                    "win_rate": report.win_rate,
                    "total_flat_stake": report.total_flat_stake,
                    "total_flat_profit": report.total_flat_profit,
                    "flat_roi": report.flat_roi,
                    "max_flat_drawdown": report.max_flat_drawdown,
                    "total_kelly_stake": report.total_kelly_stake,
                    "total_kelly_profit": report.total_kelly_profit,
                    "kelly_roi": report.kelly_roi,
                    "max_kelly_drawdown": report.max_kelly_drawdown,
                    "avg_confidence": report.avg_confidence,
                    "assessment": report.assessment,
                    "disclaimer": report.disclaimer,
                    "points": [
                        {
                            "match_index": p.match_index,
                            "predicted_outcome": p.predicted_outcome,
                            "actual_outcome": p.actual_outcome,
                            "correct": p.correct,
                            "model_probability": p.model_probability,
                            "implied_odds": p.implied_odds,
                            "flat_stake": p.flat_stake,
                            "flat_profit": p.flat_profit,
                            "cumulative_flat_profit": p.cumulative_flat_profit,
                            "kelly_fraction": p.kelly_fraction,
                            "kelly_stake": p.kelly_stake,
                            "kelly_profit": p.kelly_profit,
                            "cumulative_kelly_profit": p.cumulative_kelly_profit,
                        }
                        for p in report.points
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_cumulative_trajectory(
    *,
    rolling_window: int = 50,
    max_points: int = 500,
    change_threshold: float = 0.05,
) -> dict:
    """Return cumulative performance trajectory from backtest predictions.

    Tracks running accuracy, Brier, and profit over the backtest timeline.
    Prefers Dixon-Coles decay predictions, falls back to Poisson.
    Cached for 5 minutes.
    """
    import time

    cache_key = f"trajectory_{rolling_window}_{max_points}_{change_threshold}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_cumulative_trajectory,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_cumulative_trajectory(
                    preds_df,
                    rolling_window=rolling_window,
                    max_points=max_points,
                    change_threshold=change_threshold,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_matches": report.n_matches,
                    "final_accuracy": report.final_accuracy,
                    "final_brier": report.final_brier,
                    "final_profit": report.final_profit,
                    "trend": report.trend,
                    "best_window_accuracy": report.best_window_accuracy,
                    "worst_window_accuracy": report.worst_window_accuracy,
                    "n_change_points": report.n_change_points,
                    "disclaimer": report.disclaimer,
                    "points": [
                        {
                            "match_index": p.match_index,
                            "cumulative_accuracy": p.cumulative_accuracy,
                            "cumulative_brier": p.cumulative_brier,
                            "cumulative_profit": p.cumulative_profit,
                            "rolling_accuracy": p.rolling_accuracy,
                            "rolling_brier": p.rolling_brier,
                            "match_date": p.match_date,
                        }
                        for p in report.points
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_difficulty_stratification(
    *,
    easy_threshold: float = 0.6,
    hard_threshold: float = 0.4,
    n_bins: int = 5,
) -> dict:
    """Return match difficulty stratification from backtest predictions.

    Buckets predictions by difficulty (max predicted probability) and
    computes per-tier metrics. Prefers Dixon-Coles decay predictions,
    falls back to Poisson. Cached for 5 minutes.
    """
    import time

    cache_key = f"difficulty_{easy_threshold}_{hard_threshold}_{n_bins}"
    now = time.time()
    cached = _BACKTEST_CACHE.get(cache_key)
    if (
        cached is not None
        and now - _BACKTEST_CACHE.get(f"{cache_key}_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return cached

    try:
        from scoutfootball.evaluation.backtests import (
            compute_difficulty_stratification,
        )

        settings = _settings()
        pred_path = (
            settings.report_root
            / "calibration_backtest"
            / "dixon_coles_decay_backtest_predictions.parquet"
        )
        if not pred_path.exists():
            pred_path = (
                settings.report_root
                / "calibration_backtest"
                / "poisson_backtest_predictions.parquet"
            )
        if not pred_path.exists():
            result = {
                "status": "not_available",
                "instructions": (
                    "Run 'scoutfootball tune-predictions --run-backtest' "
                    "to generate backtest artifacts"
                ),
            }
        else:
            preds_df = _read_parquet(pred_path)
            if preds_df.empty:
                result = {"status": "no_data"}
            else:
                if "actual_outcome" not in preds_df.columns:
                    if "home_goals" in preds_df.columns and "away_goals" in preds_df.columns:
                        import numpy as np

                        preds_df["actual_outcome"] = np.where(
                            preds_df["home_goals"] > preds_df["away_goals"],
                            "home_win",
                            np.where(
                                preds_df["home_goals"] == preds_df["away_goals"],
                                "draw",
                                "away_win",
                            ),
                        )
                report = compute_difficulty_stratification(
                    preds_df,
                    easy_threshold=easy_threshold,
                    hard_threshold=hard_threshold,
                    n_bins=n_bins,
                )
                result = _clean_json_value({
                    "status": "ok",
                    "n_matches": report.n_matches,
                    "overall_accuracy": report.overall_accuracy,
                    "overall_brier": report.overall_brier,
                    "best_tier": report.best_tier,
                    "worst_tier": report.worst_tier,
                    "disclaimer": report.disclaimer,
                    "tiers": [
                        {
                            "tier": t.tier,
                            "n_matches": t.n_matches,
                            "accuracy": t.accuracy,
                            "brier": t.brier,
                            "rps": t.rps,
                            "log_loss": t.log_loss,
                            "avg_confidence": t.avg_confidence,
                            "calibration_gap": t.calibration_gap,
                            "assessment": t.assessment,
                        }
                        for t in report.tiers
                    ],
                })

        _BACKTEST_CACHE[cache_key] = result
        _BACKTEST_CACHE[f"{cache_key}_timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_prediction_diagnostics(home_team: str, away_team: str) -> dict:
    """Return an aggregated prediction diagnostics summary for a fixture.

    Combines calibration comparison highlights, drift status, and the top
    attribution factors into one response for quick model-trust assessment.
    """
    try:
        # Calibration comparison summary
        cal = get_calibration_comparison()
        cal_summary: dict[str, Any] = {"status": cal.get("status", "unknown")}
        if cal.get("status") == "ok":
            overall = cal.get("overall", {})
            improvement = cal.get("improvement", {})
            cal_summary = {
                "status": "ok",
                "n_matches": cal.get("n_matches", 0),
                "brier_raw": overall.get("brier_raw"),
                "brier_recalibrated": overall.get("brier_recalibrated"),
                "brier_improvement_pct": improvement.get("brier_improvement_pct"),
                "rps_raw": overall.get("rps_raw"),
                "rps_recalibrated": overall.get("rps_recalibrated"),
                "rps_improvement_pct": improvement.get("rps_improvement_pct"),
                "n_leagues": len(cal.get("by_league", [])),
            }

        # Drift status
        drift = get_calibration_drift()
        drift_summary: dict[str, Any] = {"status": drift.get("status", "unknown")}
        if drift.get("status") == "ok":
            drift_summary = {
                "status": "ok",
                "drift_detected": drift.get("drift_detected", False),
                "drift_metric": drift.get("drift_metric"),
                "threshold": drift.get("threshold"),
                "n_windows": drift.get("n_windows", 0),
                "latest_window": drift.get("latest_window"),
            }

        # Attribution top factors
        attr = get_prediction_attribution(home_team, away_team)
        attr_summary: dict[str, Any] = {"status": attr.get("status", "unknown")}
        if attr.get("status") == "ok":
            factors = attr.get("factors", [])
            attr_summary = {
                "status": "ok",
                "baseline_home_win": attr.get("baseline_home_win"),
                "top_factors": factors[:3] if factors else [],
                "n_factors": len(factors),
                "model_type": attr.get("model_type", "dixon_coles"),
            }

        # CI cache status
        ci_status: dict[str, Any] = {"available": False}
        try:
            ci_cache_key = f"{home_team}__{away_team}__dixon_coles"
            cached = _PREDICTION_CI_CACHE.get(ci_cache_key)
            if cached:
                ci_status = {
                    "available": True,
                    "age_seconds": int(__import__("time").time() - cached.get("timestamp", 0)),
                }
        except Exception:
            pass

        return _clean_json_value({
            "status": "ok",
            "home_team": home_team,
            "away_team": away_team,
            "calibration": cal_summary,
            "drift": drift_summary,
            "attribution": attr_summary,
            "ci_cache": ci_status,
        })
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_head_to_head(
    home_team: str, away_team: str, limit: int = 10, form_limit: int = 10
) -> dict:
    """Return head-to-head history, team form, and matchup summary.

    Wraps :func:`scoutfootball.head_to_head.get_head_to_head` with JSON-safe
    serialization and graceful error handling so the API never crashes.
    """
    empty_form_summary = {
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "goals_for": 0,
        "goals_against": 0,
        "points": 0,
        "streak": [],
    }
    empty_summary = {
        "total_meetings": 0,
        "home_wins": 0,
        "draws": 0,
        "away_wins": 0,
        "home_goals_avg": 0.0,
        "away_goals_avg": 0.0,
        "last_meeting_date": None,
    }
    fallback = {
        "home_team": home_team,
        "away_team": away_team,
        "head_to_head": [],
        "home_form": [],
        "home_form_summary": empty_form_summary,
        "away_form": [],
        "away_form_summary": {**empty_form_summary},
        "summary": empty_summary,
        "data_coverage": {
            "seasons_covered": [],
            "total_matches_scanned": 0,
            "source": "Football-Data",
        },
    }
    try:
        result = _compute_head_to_head(
            home_team, away_team, limit=limit, form_limit=form_limit
        )
        return _clean_json_value(result)
    except Exception:
        return _clean_json_value(fallback)


def get_value_summary() -> dict:
    oof = load_oof_predictions()
    if oof.empty:
        return {"status": "no_data", "players": [], "metrics": {}}
    is_synthetic = (
        "is_synthetic" in oof.columns
        and bool(oof["is_synthetic"].fillna(False).all())
    )

    # Filter out records with suspiciously low market values (Transfermarkt placeholder)
    # Values <= 200k are almost certainly data errors, not real valuations
    if "actual_market_value" in oof.columns:
        oof = oof[oof["actual_market_value"] > 200000].copy()

    # Build player-level value data
    player_data = []
    for _, row in oof.iterrows():
        record = {
            "player": row.get("player_name", ""),
            "team": row.get("team_name", ""),
            "actual_value": row.get("actual_market_value"),
            "predicted_value": row.get("predicted_market_value"),
            "residual_log": row.get("residual_log"),
            "fairness_label": row.get("fairness_label", ""),
        }
        for key, value in record.items():
            if isinstance(value, float) and math.isnan(value):
                record[key] = None
        player_data.append(_clean_json_value(record))

    metrics: dict[str, Any] = {}
    results_path = _settings().data_root / "models" / "artifacts" / "value_fairness_results.parquet"
    if results_path.exists():
        try:


            results_df = _read_parquet(results_path)
            if not results_df.empty:
                metrics = _clean_json_value(results_df.iloc[0].to_dict())
        except Exception:
            pass

    mean_residual = None
    if "residual_log" in oof.columns:
        try:
            raw = oof["residual_log"].mean()
            mean_residual = float(raw) if raw == raw else None
        except Exception:
            mean_residual = None

    return _clean_json_value({
        "status": "demo" if is_synthetic else "ok",
        "data_mode": "synthetic" if is_synthetic else "artifact",
        "sample_count": len(oof),
        "fairness_distribution": oof["fairness_label"].value_counts().to_dict()
        if "fairness_label" in oof.columns
        else {},
        "mean_residual_log": mean_residual,
        "metrics": metrics,
        "players": player_data,
    })


def get_player_ratings(
    position: str | None = None,
    league: str | None = None,
    team: str | None = None,
    season: str | None = None,
    limit: int = 20000,
) -> dict:
    """Return player ratings from DuckDB, sorted by optimized_score DESC."""
    df = load_player_ratings(position=position, league=league, team=team, season=season)
    if df.empty:
        return {"count": 0, "players": []}

    # Normalize confidence_level to uppercase for frontend
    if "confidence_level" in df.columns:
        df["confidence_level"] = df["confidence_level"].str.upper()

    # Alias sub_position → position_group for frontend compatibility
    if "sub_position" in df.columns and "position_group" not in df.columns:
        df["position_group"] = df["sub_position"]

    # Limit results
    df = df.head(limit)

    players = df.to_dict(orient="records")
    # Convert NaN to None for JSON serialization
    return _clean_json_value({"count": len(players), "players": players})


def get_ratings_meta() -> dict:
    """Return model metadata and league metrics."""
    meta_df = load_model_meta()
    league_df = load_league_metrics()

    meta = {}
    if not meta_df.empty:
        meta = meta_df.iloc[0].to_dict()

    leagues = league_df.to_dict(orient="records") if not league_df.empty else []

    return _clean_json_value({"model_meta": meta, "league_metrics": leagues})


# ── Position group mapping for team strength aggregation ──────────
_POS_GROUP_MAP: dict[str, str] = {
    "GK": "GK",
    "CB": "DEF", "FB": "DEF", "LB": "DEF", "RB": "DEF", "RWB": "DEF", "LWB": "DEF",
    "DM": "MID", "CM": "MID", "AM": "MID", "CDM": "MID", "CAM": "MID", "LM": "MID", "RM": "MID",
    "W": "ATT", "ST": "ATT", "CF": "ATT", "RW": "ATT", "LW": "ATT", "WF": "ATT",
}


def _broad_position(pos: str | None) -> str:
    """Map a granular position to GK/DEF/MID/ATT."""
    if not pos:
        return "UNK"
    key = str(pos).strip().upper()
    return _POS_GROUP_MAP.get(key, "UNK")


def get_team_strength(
    league: str | None = None,
    season: str | None = None,
    limit: int = 100,
) -> dict:
    """Aggregate player ratings to team-level strength metrics.

    Returns overall team rating, position-group breakdowns, top players,
    squad depth and average confidence for each team.
    """
    df = load_player_ratings(league=league, season=season)
    if df.empty:
        return {"count": 0, "teams": []}

    # Resolve column aliases
    team_col = "team" if "team" in df.columns else (
        "team_name" if "team_name" in df.columns else None
    )
    score_col = "optimized_score" if "optimized_score" in df.columns else (
        "rating" if "rating" in df.columns else None
    )
    pos_col = "position_group" if "position_group" in df.columns else (
        "sub_position" if "sub_position" in df.columns else None
    )
    minutes_col = "minutes" if "minutes" in df.columns else None
    name_col = "player_name" if "player_name" in df.columns else (
        "player" if "player" in df.columns else None
    )
    league_col = "league" if "league" in df.columns else None
    season_col = "season" if "season" in df.columns else None
    conf_col = "confidence_level" if "confidence_level" in df.columns else None

    if team_col is None or score_col is None:
        return {"count": 0, "teams": []}

    # Filter out rows with no team or score
    df = df[df[team_col].notna() & df[score_col].notna()].copy()
    # Exclude comma-joined club histories (transferred players)
    df = df[~df[team_col].astype(str).str.contains(",", na=False)]
    # Normalize team name
    df[team_col] = df[team_col].astype(str).str.strip()
    df = df[df[team_col] != ""]

    if df.empty:
        return {"count": 0, "teams": []}

    # Add broad position group
    if pos_col:
        df["broad_pos"] = df[pos_col].map(_broad_position)
    else:
        df["broad_pos"] = "UNK"

    # Ensure numeric score
    df[score_col] = pd.to_numeric(df[score_col], errors="coerce").fillna(0.0)
    if minutes_col:
        df[minutes_col] = pd.to_numeric(df[minutes_col], errors="coerce").fillna(0.0)
    else:
        df["minutes"] = 0.0
        minutes_col = "minutes"

    teams: list[dict[str, Any]] = []

    for team_name, group in df.groupby(team_col):
        # Minutes-weighted overall rating
        total_minutes = group[minutes_col].sum()
        if total_minutes > 0:
            overall = float((group[score_col] * group[minutes_col]).sum() / total_minutes)
        else:
            overall = float(group[score_col].mean())

        # Position group breakdown
        pos_breakdown: dict[str, dict[str, Any]] = {}
        for bpos, pg in group.groupby("broad_pos"):
            pg_minutes = pg[minutes_col].sum()
            if pg_minutes > 0:
                pg_rating = float((pg[score_col] * pg[minutes_col]).sum() / pg_minutes)
            else:
                pg_rating = float(pg[score_col].mean())
            pos_breakdown[bpos] = {
                "rating": round(pg_rating, 2),
                "player_count": int(len(pg)),
                "avg_minutes": round(float(pg[minutes_col].mean()), 0) if len(pg) > 0 else 0,
            }

        # Top players by score (with minutes weighting)
        top_players_df = group.nlargest(5, score_col)
        top_players = []
        for _, row in top_players_df.iterrows():
            top_players.append({
                "name": str(row.get(name_col, "")) if name_col else "",
                "position": str(row.get(pos_col, "")) if pos_col else "",
                "broad_pos": str(row.get("broad_pos", "")),
                "rating": round(float(row[score_col]), 1),
                "minutes": int(row.get(minutes_col, 0)) if minutes_col else 0,
                "confidence": str(row.get(conf_col, "LOW")).upper() if conf_col else "LOW",
            })

        # Average confidence
        if conf_col and conf_col in group.columns:
            conf_counts = group[conf_col].astype(str).str.upper().value_counts().to_dict()
        else:
            conf_counts = {}

        team_entry = {
            "team": team_name,
            "league": str(group[league_col].iloc[0])
            if league_col and league_col in group.columns else "",
            "season": str(group[season_col].iloc[0])
            if season_col and season_col in group.columns else "",
            "overall_rating": round(overall, 2),
            "squad_size": int(len(group)),
            "total_minutes": int(total_minutes),
            "position_groups": pos_breakdown,
            "top_players": top_players,
            "confidence_distribution": conf_counts,
        }
        teams.append(team_entry)

    # Sort by overall rating descending
    teams.sort(key=lambda t: t["overall_rating"], reverse=True)

    # Apply limit
    teams = teams[:limit]

    return _clean_json_value({"count": len(teams), "teams": teams})


def get_team_comparison(team_a: str, team_b: str) -> dict:
    """Compare two teams side-by-side using team strength data.

    Returns position group diffs, top player comparison and squad metrics.
    """
    # Normalize team names for matching
    strength = get_team_strength(limit=500)
    all_teams = strength.get("teams", [])

    # Find teams by name (case-insensitive partial match)
    def _find(name):
        name_lower = name.lower().strip()
        for t in all_teams:
            if t["team"].lower() == name_lower:
                return t
        for t in all_teams:
            if name_lower in t["team"].lower():
                return t
        return None

    a = _find(team_a)
    b = _find(team_b)

    if not a:
        return {"error": f"Team '{team_a}' not found"}
    if not b:
        return {"error": f"Team '{team_b}' not found"}

    # Position group comparison
    pos_groups = ["GK", "DEF", "MID", "ATT"]
    pos_comparison = []
    for pg in pos_groups:
        pg_a = (a.get("position_groups") or {}).get(pg)
        pg_b = (b.get("position_groups") or {}).get(pg)
        rating_a = pg_a["rating"] if pg_a else None
        rating_b = pg_b["rating"] if pg_b else None
        diff = None
        advantage = "tie"
        if rating_a is not None and rating_b is not None:
            diff = round(rating_a - rating_b, 2)
            advantage = "a" if rating_a > rating_b else ("b" if rating_b > rating_a else "tie")
        pos_comparison.append({
            "group": pg,
            "rating_a": rating_a,
            "rating_b": rating_b,
            "diff": diff,
            "advantage": advantage,
            "players_a": pg_a["player_count"] if pg_a else 0,
            "players_b": pg_b["player_count"] if pg_b else 0,
        })

    # Top players side-by-side (top 5 each)
    top_a = a.get("top_players", [])
    top_b = b.get("top_players", [])
    max_top = max(len(top_a), len(top_b))
    top_comparison = []
    for i in range(max_top):
        pa = top_a[i] if i < len(top_a) else None
        pb = top_b[i] if i < len(top_b) else None
        top_comparison.append({
            "player_a": pa,
            "player_b": pb,
        })

    # Overall metrics comparison
    overall_a = a.get("overall_rating", 0)
    overall_b = b.get("overall_rating", 0)
    overall_diff = round(overall_a - overall_b, 2)

    # Depth dimension: normalize squad_size to 0-100 scale relative to both teams
    squad_a = a.get("squad_size", 0)
    squad_b = b.get("squad_size", 0)
    max_squad = max(squad_a, squad_b, 1)
    depth_a = round(float(squad_a) / max_squad * 100, 1)
    depth_b = round(float(squad_b) / max_squad * 100, 1)

    return _clean_json_value({
        "team_a": {
            "name": a["team"],
            "league": a.get("league", ""),
            "overall_rating": overall_a,
            "squad_size": a.get("squad_size", 0),
            "total_minutes": a.get("total_minutes", 0),
            "confidence_distribution": a.get("confidence_distribution", {}),
        },
        "team_b": {
            "name": b["team"],
            "league": b.get("league", ""),
            "overall_rating": overall_b,
            "squad_size": b.get("squad_size", 0),
            "total_minutes": b.get("total_minutes", 0),
            "confidence_distribution": b.get("confidence_distribution", {}),
        },
        "overall_diff": overall_diff,
        "overall_advantage": "a" if overall_diff > 0 else ("b" if overall_diff < 0 else "tie"),
        "position_group_comparison": pos_comparison,
        "top_players_comparison": top_comparison,
        "radar_labels": ["GK", "DEF", "MID", "ATT", "Overall", "Depth"],
        "radar_a": [
            (a.get("position_groups") or {}).get("GK", {}).get("rating", 0),
            (a.get("position_groups") or {}).get("DEF", {}).get("rating", 0),
            (a.get("position_groups") or {}).get("MID", {}).get("rating", 0),
            (a.get("position_groups") or {}).get("ATT", {}).get("rating", 0),
            overall_a,
            depth_a,
        ],
        "radar_b": [
            (b.get("position_groups") or {}).get("GK", {}).get("rating", 0),
            (b.get("position_groups") or {}).get("DEF", {}).get("rating", 0),
            (b.get("position_groups") or {}).get("MID", {}).get("rating", 0),
            (b.get("position_groups") or {}).get("ATT", {}).get("rating", 0),
            overall_b,
            depth_b,
        ],
    })


def get_prediction_summary() -> dict[str, Any]:
    """Return baseline prediction artifact metadata."""
    artifact_path = (
        _settings().data_root
        / "models"
        / "artifacts"
        / "poisson_baseline_results.parquet"
    )
    poisson_info: dict[str, Any] = {"status": "no_data"}
    if artifact_path.exists():


        try:
            frame = _read_parquet(artifact_path)
            if not frame.empty:
                poisson_info = frame.iloc[0].to_dict()
                poisson_info["status"] = "ok"
        except Exception:
            pass

    # Dixon-Coles artifact info
    dc_path = (
        _settings().data_root
        / "models"
        / "artifacts"
        / "dixon_coles_results.parquet"
    )
    dc_info: dict[str, Any] = {"status": "not_available"}
    if dc_path.exists():


        try:
            dc_frame = _read_parquet(dc_path)
            if not dc_frame.empty:
                dc_info = dc_frame.iloc[0].to_dict()
                dc_info["status"] = "ok"
        except Exception:
            dc_info["status"] = "error"

    poisson_ready = poisson_info.get("status") == "ok"
    dc_ready = dc_info.get("status") == "ok"
    preferred = dc_info if dc_ready else poisson_info

    return _clean_json_value({
        "status": "ok" if (poisson_ready or dc_ready) else "no_data",
        "model_type": preferred.get("model_type", "independent_poisson"),
        "num_teams": preferred.get("num_teams"),
        "train_rows": poisson_info.get("train_rows"),
        "coverage": poisson_info.get("coverage"),
        "poisson": poisson_info,
        "dixon_coles": dc_info,
        "available_models": (
            (["poisson"] if poisson_ready else [])
            + (["dixon_coles"] if dc_ready else [])
        ),
    })


_calibration_cache: dict[str, Any] = {"data": None, "timestamp": 0.0}
_CALIBRATION_TTL_SECONDS = 300  # 5 minutes


def get_prediction_calibration(force_refresh: bool = False) -> dict[str, Any]:
    """Return calibration metrics for match prediction models.

    Compares Poisson vs Dixon-Coles side by side.
    Includes low-score breakdown (0-0, 1-0, 0-1, 1-1) and league coverage.

    Results are cached for 5 minutes to avoid repeated parquet reads.
    Pass force_refresh=True to bypass the cache (e.g. after model retraining).
    """
    import time

    now = time.time()
    if (
        not force_refresh
        and _calibration_cache["data"] is not None
        and now - _calibration_cache["timestamp"] < _CALIBRATION_TTL_SECONDS
    ):
        return _calibration_cache["data"]
    settings = _settings()
    model_root = settings.data_root / "models"
    artifact_dir = model_root / "artifacts"

    # --- DC calibration detail ---
    dc_detail_path = artifact_dir / "dc_calibration_detail.parquet"
    dc_metrics: dict[str, Any] = {"status": "not_available"}
    dc_low_score: list[dict[str, Any]] = []
    dc_calibration_plot: list[dict[str, Any]] = []
    dc_league_coverage: list[dict[str, Any]] = []

    if dc_detail_path.exists():
        import numpy as np


        try:
            dc_df = _read_parquet(dc_detail_path)
            if not dc_df.empty:
                # Compute metrics from detail
                clipped = dc_df["exact_score_probability"].clip(lower=1e-12)
                log_loss = float(-(np.log(clipped)).mean())

                probs_1x2 = dc_df.loc[
                    :,
                    ["home_win_probability", "draw_probability", "away_win_probability"],
                ].to_numpy()
                actual_map = {
                    "home_win": [1.0, 0.0, 0.0],
                    "draw": [0.0, 1.0, 0.0],
                    "away_win": [0.0, 0.0, 1.0],
                }
                actual = np.vstack(dc_df["actual_outcome"].map(actual_map))
                brier = float(np.mean(np.sum((probs_1x2 - actual) ** 2, axis=1)))

                # RPS
                probs_rps = dc_df.loc[
                    :,
                    ["away_win_probability", "draw_probability", "home_win_probability"],
                ].to_numpy()
                actual_rps = np.vstack(
                    dc_df["actual_outcome"].map(
                        {
                            "away_win": [1.0, 0.0, 0.0],
                            "draw": [0.0, 1.0, 0.0],
                            "home_win": [0.0, 0.0, 1.0],
                        },
                    ),
                )
                cum_probs = np.cumsum(probs_rps, axis=1)
                cum_actual = np.cumsum(actual_rps, axis=1)
                rps = float(np.mean(np.sum((cum_probs - cum_actual) ** 2, axis=1) / 2.0))

                dc_metrics = {
                    "status": "ok",
                    "log_loss_exact": round(log_loss, 4),
                    "brier_1x2": round(brier, 4),
                    "rps_1x2": round(rps, 4),
                    "n_matches": len(dc_df),
                }

                # Low-score breakdown
                for bucket in ["0-0", "1-0", "0-1", "1-1"]:
                    group = dc_df[dc_df["score_bucket"] == bucket]
                    n = len(group)
                    actual_pct = n / len(dc_df) * 100.0 if len(dc_df) > 0 else 0.0
                    mean_pred = (
                        float(group["exact_score_probability"].mean()) * 100.0
                        if n > 0 else 0.0
                    )
                    dc_low_score.append({
                        "score_bucket": bucket,
                        "n_matches": n,
                        "actual_pct": round(actual_pct, 2),
                        "mean_predicted_pct": round(mean_pred, 2),
                        "calibration_error": round(abs(actual_pct - mean_pred), 2),
                    })

                # Calibration plot data (decile bins of predicted home-win)
                bin_edges = np.linspace(0, 1, 11)
                hw_probs = dc_df["home_win_probability"].to_numpy()
                hw_actual = (dc_df["actual_outcome"] == "home_win").to_numpy().astype(float)
                bin_idx = np.clip(np.digitize(hw_probs, bin_edges) - 1, 0, 9)
                for b in range(10):
                    mask = bin_idx == b
                    if mask.sum() == 0:
                        continue
                    dc_calibration_plot.append({
                        "bin_center": round(float((bin_edges[b] + bin_edges[b + 1]) / 2), 2),
                        "n_matches": int(mask.sum()),
                        "mean_predicted": round(float(hw_probs[mask].mean()), 4),
                        "mean_actual": round(float(hw_actual[mask].mean()), 4),
                    })

                # League coverage
                if "league" in dc_df.columns:
                    for league, lg in dc_df.groupby("league", sort=True):
                        n_lg = len(lg)
                        if n_lg == 0:
                            continue
                        ll_lg = float(
                            -(np.log(
                                lg["exact_score_probability"].clip(lower=1e-12)
                            )).mean()
                        )
                        probs_lg = lg.loc[
                            :, ["home_win_probability", "draw_probability", "away_win_probability"]
                        ].to_numpy()
                        actual_lg = np.vstack(lg["actual_outcome"].map(actual_map))
                        brier_lg = float(np.mean(np.sum((probs_lg - actual_lg) ** 2, axis=1)))
                        dc_league_coverage.append({
                            "league": str(league),
                            "n_matches": n_lg,
                            "mean_log_loss": round(ll_lg, 4),
                            "mean_brier": round(brier_lg, 4),
                        })

        except Exception:
            dc_metrics = {"status": "error"}

    # --- Poisson calibration (from existing results parquet) ---
    poisson_metrics: dict[str, Any] = {"status": "not_available"}
    poisson_results_path = artifact_dir / "poisson_baseline_results.parquet"
    if poisson_results_path.exists():


        try:
            pf = _read_parquet(poisson_results_path)
            if not pf.empty:
                row = pf.iloc[0].to_dict()
                poisson_metrics = {
                    "status": "ok",
                    "log_loss_exact": _clean_json_value(row.get("log_loss_exact")),
                    "brier_1x2": _clean_json_value(row.get("brier_1x2")),
                    "rps_1x2": _clean_json_value(row.get("rps_1x2")),
                    "n_matches": _clean_json_value(row.get("n_matches")),
                }
        except Exception:
            poisson_metrics = {"status": "error"}

    result = _clean_json_value({
        "dixon_coles": dc_metrics,
        "poisson": poisson_metrics,
        "low_score_breakdown": dc_low_score,
        "calibration_plot": dc_calibration_plot,
        "league_coverage": dc_league_coverage,
    })
    _calibration_cache["data"] = result
    _calibration_cache["timestamp"] = time.time()
    return result


_BACKTEST_CACHE: dict[str, Any] = {"data": None, "timestamp": 0.0}
_BACKTEST_TTL_SECONDS = 300


def get_backtest_comparison(force_refresh: bool = False) -> dict[str, Any]:
    """Return a side-by-side comparison of Poisson vs Dixon-Coles backtests.

    Reads the metrics JSON files produced by ``scoutfootball backtest`` from
    ``data/reports/calibration_backtest/``. Returns a structured comparison
    including overall metrics (log_loss_exact, brier_1x2, rps_1x2), per-fold
    metrics, and a winner per metric. If no backtest artifacts exist, returns
    a status of ``not_available`` with instructions on how to generate them.

    Results are cached for 5 minutes.
    """
    import time

    now = time.time()
    if (
        not force_refresh
        and _BACKTEST_CACHE["data"] is not None
        and now - _BACKTEST_CACHE["timestamp"] < _BACKTEST_TTL_SECONDS
    ):
        return _BACKTEST_CACHE["data"]

    settings = _settings()
    bt_dir = settings.report_root / "calibration_backtest"

    models: list[dict[str, Any]] = []
    metric_files = [
        ("independent_poisson", "poisson_backtest_metrics.json"),
        ("dixon_coles", "dixon_coles_backtest_metrics.json"),
        ("dixon_coles_decay", "dixon_coles_decay_backtest_metrics.json"),
    ]

    available = False
    for model_key, filename in metric_files:
        path = bt_dir / filename
        if not path.exists():
            continue
        try:
            data = _read_json(path)
        except Exception:
            continue
        available = True
        overall = data.get("overall", {}) or {}
        folds = data.get("folds", []) or []
        models.append({
            "model": model_key,
            "label": data.get("model", model_key),
            "decay": data.get("decay"),
            "n_splits": data.get("n_splits"),
            "total_predictions": data.get("total_predictions"),
            "overall": {
                "log_loss_exact": overall.get("log_loss_exact"),
                "brier_1x2": overall.get("brier_1x2"),
                "rps_1x2": overall.get("rps_1x2"),
            },
            "folds": [
                {
                    "fold": f.get("fold"),
                    "train_start": str(f.get("train_start", "")),
                    "train_end": str(f.get("train_end", "")),
                    "test_start": str(f.get("test_start", "")),
                    "test_end": str(f.get("test_end", "")),
                    "train_matches": f.get("train_matches"),
                    "test_matches": f.get("test_matches"),
                    "log_loss_exact": f.get("log_loss_exact"),
                    "brier_1x2": f.get("brier_1x2"),
                    "rps_1x2": f.get("rps_1x2"),
                }
                for f in folds
            ],
        })

    # Calibration report (isotonic) if present
    cal_path = bt_dir / "dc_calibration_report.json"
    calibration: dict[str, Any] = {"status": "not_available"}
    if cal_path.exists():
        try:
            cal_data = _read_json(cal_path)
            calibration = {
                "status": "ok",
                "method": cal_data.get("method"),
                "decay": cal_data.get("decay"),
                "brier_before": cal_data.get("brier_before"),
                "brier_after": cal_data.get("brier_after"),
                "rps_before": cal_data.get("rps_before"),
                "rps_after": cal_data.get("rps_after"),
                "n_matches": cal_data.get("n_matches"),
            }
        except Exception:
            pass

    if not available:
        result = {
            "status": "not_available",
            "backtest_dir": str(bt_dir).replace("\\", "/"),
            "models": [],
            "metric_comparison": [],
            "folds": [],
            "calibration": calibration,
            "instructions": (
                "Run `PYTHONPATH=src uv run python -m scoutfootball backtest` "
                "to generate backtest artifacts."
            ),
        }
    else:
        # Build metric comparison table — pick winner (lower is better)
        metric_keys = ["log_loss_exact", "brier_1x2", "rps_1x2"]
        metric_comparison: list[dict[str, Any]] = []
        for mk in metric_keys:
            row: dict[str, Any] = {"metric": mk}
            values: list[tuple[str, float]] = []
            for m in models:
                v = m["overall"].get(mk)
                row[m["model"]] = v
                if v is not None:
                    values.append((m["model"], float(v)))
            if values:
                winner = min(values, key=lambda x: x[1])[0]
                row["winner"] = winner
            else:
                row["winner"] = None
            metric_comparison.append(row)

        # Collect all fold timelines (union of folds across models)
        max_folds = max((len(m["folds"]) for m in models), default=0)
        folds_table: list[dict[str, Any]] = []
        for i in range(max_folds):
            row: dict[str, Any] = {"fold": i + 1}
            for m in models:
                prefix = m["model"]
                if i < len(m["folds"]):
                    f = m["folds"][i]
                    row[f"{prefix}_test_matches"] = f.get("test_matches")
                    row[f"{prefix}_log_loss"] = f.get("log_loss_exact")
                    row[f"{prefix}_brier"] = f.get("brier_1x2")
                    row[f"{prefix}_rps"] = f.get("rps_1x2")
                else:
                    row[f"{prefix}_test_matches"] = None
                    row[f"{prefix}_log_loss"] = None
                    row[f"{prefix}_brier"] = None
                    row[f"{prefix}_rps"] = None
            folds_table.append(row)

        result = _clean_json_value({
            "status": "ok",
            "backtest_dir": str(bt_dir).replace("\\", "/"),
            "models": models,
            "metric_comparison": metric_comparison,
            "folds": folds_table,
            "calibration": calibration,
        })

    _BACKTEST_CACHE["data"] = result
    _BACKTEST_CACHE["timestamp"] = time.time()
    return result


def get_decay_tuning(force_refresh: bool = False) -> dict[str, Any]:
    """Return Dixon-Coles decay tuning results.

    Reads ``data/reports/calibration_backtest/decay_tuning_results.json``
    produced by ``scoutfootball tune-predictions``. Returns the best decay,
    selection metric, and per-candidate comparison table. If no tuning
    artifacts exist, returns a ``not_available`` status with instructions.

    Results are cached for 5 minutes.
    """
    import time

    now = time.time()
    if (
        not force_refresh
        and _BACKTEST_CACHE.get("tuning_data") is not None
        and now - _BACKTEST_CACHE.get("tuning_timestamp", 0) < _BACKTEST_TTL_SECONDS
    ):
        return _BACKTEST_CACHE["tuning_data"]

    settings = _settings()
    tuning_path = settings.report_root / "calibration_backtest" / "decay_tuning_results.json"

    if not tuning_path.exists():
        result = {
            "status": "not_available",
            "tuning_path": str(tuning_path).replace("\\", "/"),
            "instructions": (
                "Run `PYTHONPATH=src uv run python -m scoutfootball tune-predictions` "
                "to generate decay tuning results."
            ),
        }
    else:
        try:
            data = _read_json(tuning_path)
            result = _clean_json_value({
                "status": "ok",
                "tuning_path": str(tuning_path).replace("\\", "/"),
                "best_decay": data.get("best_decay"),
                "selection_metric": data.get("selection_metric"),
                "n_folds": data.get("n_folds"),
                "n_matches": data.get("n_matches"),
                "candidates": data.get("candidates", []),
            })
        except Exception as exc:
            result = {
                "status": "error",
                "error": str(exc),
                "tuning_path": str(tuning_path).replace("\\", "/"),
            }

    _BACKTEST_CACHE["tuning_data"] = result
    _BACKTEST_CACHE["tuning_timestamp"] = time.time()
    return result


def get_action_value_summary(
    limit: int = 20,
    offset: int = 0,
    full: bool = False,
) -> dict[str, Any]:
    """Return independently paged xT and VAEP action-value rows.

    xT is a player-team-season artifact.  VAEP is currently a player-team
    career aggregate and receives display identity plus season *context* from
    the xT artifact.  The two models are kept in separate arrays because
    joining them on a display name would blur those different granularities.

    ``full`` is retained for backwards compatibility with the static exporter;
    ``limit`` and ``offset`` apply independently to each model section.
    """
    import pandas as pd

    from scoutfootball.action_value.identity import (
        attach_team_names,
        build_identity_coverage_report,
        enrich_vaep_identities,
    )

    del full  # Compatibility flag; callers still control row count with limit.
    limit = max(0, min(int(limit), 20_000))
    offset = max(0, int(offset))
    settings = _settings()
    xt_path = settings.data_root / "gold" / "feature_store" / "player_action_value.parquet"
    vaep_path = settings.data_root / "gold" / "feature_store" / "player_vaep.parquet"
    matches_path = settings.raw_root / "statsbomb_open" / "matches_all.parquet"

    # Load xT data
    xt_df = pd.DataFrame()
    if xt_path.exists():
        try:
            xt_df = _read_parquet(xt_path)
        except Exception:
            pass

    # Load VAEP data
    vaep_df = pd.DataFrame()
    if vaep_path.exists():
        try:
            vaep_df = _read_parquet(vaep_path)
        except Exception:
            pass

    matches_df = pd.DataFrame()
    if matches_path.exists():
        try:
            matches_df = _read_parquet(matches_path)
        except Exception:
            pass

    if xt_df.empty and vaep_df.empty:
        # Fallback to legacy player_value_metrics
        frame = load_player_value_metrics()
        if frame.empty:
            return _clean_json_value({
            "status": "no_data", "count": 0, "players": [],
            "attribution_required": _STATSBOMB_ATTRIBUTION,
        })

        working = frame.copy()
        if "composite_score" in working.columns:
            working = working.sort_values("composite_score", ascending=False)

        return _clean_json_value({
            "status": "ok",
            "count": len(working),
            "data_source": "StatsBomb Open Data + xT/VAEP model",
            "attribution_required": _STATSBOMB_ATTRIBUTION,
            "metrics": {
                "players_with_xt": (
                    int(working["xT_per_90"].notna().sum())
                    if "xT_per_90" in working.columns
                    else 0
                ),
                "players_with_finishing": int(working["finishing_delta"].notna().sum())
                if "finishing_delta" in working.columns
                else 0,
                "mean_xt_per_90": (
                    float(working["xT_per_90"].dropna().mean())
                    if "xT_per_90" in working.columns
                    else None
                ),
                "mean_composite_score": float(working["composite_score"].dropna().mean())
                if "composite_score" in working.columns
                else None,
            },
            "players": working.head(limit).to_dict(orient="records"),
        })

    xt_part = attach_team_names(xt_df, matches_df)
    vaep_part = enrich_vaep_identities(vaep_df, xt_df, matches_df)
    if "xt_per_90" in xt_part.columns:
        xt_part = xt_part.sort_values("xt_per_90", ascending=False)
    if "vaep_per_90" in vaep_part.columns:
        vaep_part = vaep_part.sort_values("vaep_per_90", ascending=False)

    total_count = len(xt_part) + len(vaep_part)
    xt_page = xt_part.iloc[offset : offset + limit]
    vaep_page = vaep_part.iloc[offset : offset + limit]
    metrics: dict[str, Any] = {
        "total_rows": total_count,
        "xt_rows": len(xt_part),
        "vaep_rows": len(vaep_part),
    }
    if "xt_per_90" in xt_part.columns and xt_part["xt_per_90"].notna().any():
        metrics["mean_xt_per_90"] = round(float(xt_part["xt_per_90"].dropna().mean()), 4)
        metrics["players_with_xt"] = int(xt_part["xt_per_90"].notna().sum())
    if "vaep_per_90" in vaep_part.columns and vaep_part["vaep_per_90"].notna().any():
        metrics["mean_vaep_per_90"] = round(
            float(vaep_part["vaep_per_90"].dropna().mean()), 4
        )
        metrics["players_with_vaep"] = int(vaep_part["vaep_per_90"].notna().sum())

    return _clean_json_value({
        "status": "ok",
        "count": total_count,
        "offset": offset,
        "limit": limit,
        "data_source": "StatsBomb Open Data + xT/VAEP model",
        "attribution_required": _STATSBOMB_ATTRIBUTION,
        "model_granularity": {
            "xt": "player_team_season",
            "vaep": "player_team_career",
        },
        "metrics": metrics,
        "identity_coverage": build_identity_coverage_report(vaep_part),
        "players": xt_page.to_dict(orient="records"),
        "xt_players": xt_page.to_dict(orient="records"),
        "vaep_players": vaep_page.to_dict(orient="records"),
    })


def get_action_value_evidence_index() -> dict[str, Any]:
    """Return the players and coverage available in the match evidence sample."""
    return _clean_json_value(_get_action_value_evidence_index())


def get_action_value_evidence(player_id: str) -> dict[str, Any]:
    """Return match, action-type, zone and time evidence for one player."""
    return _clean_json_value(_get_action_value_evidence(player_id))


def get_action_value_player_context(player_id: str) -> dict[str, Any]:
    """Return a non-additive xT/VAEP/match-evidence dossier for one player."""
    import pandas as pd

    from scoutfootball.action_value.context import build_player_action_value_context
    from scoutfootball.action_value.identity import attach_team_names, enrich_vaep_identities

    settings = _settings()
    feature_root = settings.data_root / "gold" / "feature_store"

    def read(name: str) -> pd.DataFrame:
        path = feature_root / name
        if not path.exists():
            return pd.DataFrame()
        try:
            return _read_parquet(path)
        except Exception:
            return pd.DataFrame()

    xt = read("player_action_value.parquet")
    vaep = read("player_vaep.parquet")
    sample = read("player_match_action_value_sample.parquet")
    matches_path = settings.raw_root / "statsbomb_open" / "matches_all.parquet"
    try:
        matches = _read_parquet(matches_path) if matches_path.exists() else pd.DataFrame()
    except Exception:
        matches = pd.DataFrame()
    return _clean_json_value(
        build_player_action_value_context(
            player_id,
            attach_team_names(xt, matches),
            enrich_vaep_identities(vaep, xt, matches),
            sample,
        )
    )


def get_action_value_rating_links(player_id: str) -> dict[str, Any]:
    """Return conservative, human-verifiable rating candidates for an action player."""
    import pandas as pd

    from scoutfootball.action_value.identity import attach_team_names
    from scoutfootball.action_value.rating_links import build_action_value_rating_links

    settings = _settings()
    xt_path = settings.data_root / "gold" / "feature_store" / "player_action_value.parquet"
    matches_path = settings.raw_root / "statsbomb_open" / "matches_all.parquet"
    try:
        xt = pd.read_parquet(xt_path) if xt_path.exists() else pd.DataFrame()
    except Exception:
        xt = pd.DataFrame()
    try:
        matches = pd.read_parquet(matches_path) if matches_path.exists() else pd.DataFrame()
    except Exception:
        matches = pd.DataFrame()
    try:
        ratings = load_player_ratings()
    except Exception:
        ratings = pd.DataFrame()
    return _clean_json_value(
        build_action_value_rating_links(player_id, attach_team_names(xt, matches), ratings)
    )


def get_player_match_action_values(limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read the generated, sample-bounded player-match xT artifact."""
    import json

    limit, offset = max(0, min(int(limit), 2_000)), max(0, int(offset))
    path = (
        _settings().data_root
        / "gold"
        / "feature_store"
        / "player_match_action_value_sample.parquet"
    )
    manifest_path = path.with_suffix(".manifest.json")
    if not path.exists() or not manifest_path.exists():
        return _clean_json_value(
            {
                "status": "not_generated",
                "rows": [],
                "count": 0,
                "build_command": "scoutfootball action-value-matches",
                "coverage_scope": "sample",
                "attribution_required": _STATSBOMB_ATTRIBUTION,
            }
        )
    try:
        frame = _read_parquet(path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _clean_json_value(
            {"status": "error", "rows": [], "count": 0, "error": str(exc)}
        )
    if frame.empty:
        return _clean_json_value(
            {"status": "no_data", "rows": [], "count": 0, "manifest": manifest}
        )
    frame = frame.sort_values("xt_total", ascending=False)
    return _clean_json_value(
        {
            "status": "ok",
            "count": len(frame),
            "offset": offset,
            "limit": limit,
            "rows": frame.iloc[offset : offset + limit].to_dict(orient="records"),
            "manifest": manifest,
            "attribution_required": _STATSBOMB_ATTRIBUTION,
        }
    )


def get_artifacts_summary() -> dict:
    """Return artifact counts and data health for the overview page."""
    ratings = load_player_ratings()
    player_match = load_player_match()
    team_match = load_team_match()
    oof = load_oof_predictions()

    settings = _settings()

    # Count events from StatsBomb
    events_count = 0
    events_path = settings.raw_root / "statsbomb_open" / "events_all.parquet"
    if events_path.exists():
        try:

            events_count = len(_read_parquet(events_path))
        except Exception:
            events_count = 0

    # Data health flags. Demo fallback rows keep the UI usable, but must never
    # be presented as a real trained artifact.
    oof_path = settings.data_root / "models" / "oof_predictions" / "value_fairness_oof.parquet"
    oof_is_synthetic = (
        "is_synthetic" in oof.columns
        and bool(oof["is_synthetic"].fillna(False).all())
    )
    has_oof = oof_path.exists() and not oof.empty and not oof_is_synthetic
    oof_rows = len(oof) if has_oof else 0
    has_truth = False
    truth_rows = 0
    truth_path = settings.data_root / "gold" / "feature_store" / "player_truth_labels.parquet"
    if truth_path.exists():
        try:

            truth_df = _read_parquet(truth_path)
            has_truth = len(truth_df) > 0
            truth_rows = len(truth_df)
        except Exception:
            pass

    # Player match coverage
    pm_coverage = ""
    if not player_match.empty and "data_granularity" in player_match.columns:
        match_count = (player_match["data_granularity"] == "match").sum()
        proxy_count = (player_match["data_granularity"] == "season_proxy").sum()
        pm_coverage = f"{match_count} real + {proxy_count} season proxy"

    artifact_registry = [
        _artifact_file_info(
            settings.data_root / "gold" / "feature_store" / "player_match.parquet",
            "player_match",
            rows=len(player_match),
            display_root=settings.project_root,
        ),
        _artifact_file_info(
            settings.data_root / "gold" / "feature_store" / "team_match.parquet",
            "team_match",
            rows=len(team_match),
            display_root=settings.project_root,
        ),
        _artifact_file_info(
            settings.data_root / "gold" / "feature_store" / "player_ratings_optimized.parquet",
            "player_ratings_optimized",
            rows=len(ratings),
            display_root=settings.project_root,
        ),
        _artifact_file_info(
            events_path,
            "events_all",
            rows=events_count,
            display_root=settings.project_root,
        ),
        _artifact_file_info(
            oof_path,
            "value_fairness_oof",
            rows=oof_rows,
            display_root=settings.project_root,
        ),
        _artifact_file_info(
            truth_path,
            "player_truth_labels",
            rows=truth_rows,
            display_root=settings.project_root,
        ),
    ]

    return _clean_json_value({
        "player_match_rows": len(player_match),
        "team_match_rows": len(team_match),
        "rating_rows": len(ratings),
        "event_samples": events_count,
        "data_source_label": data_source_label(),
        "artifacts": artifact_registry,
        "data_health": {
            "oof_available": has_oof,
            "truth_labels_available": has_truth,
            "player_match_coverage": pm_coverage,
            "confidence_gate": "coverage < 0.90 → low confidence only",
        },
        "license_attribution": {
            "statsbomb": "StatsBomb Open Data — free for research, must attribute source",
            "fbref": "FBref via soccerdata — personal research use only",
            "football_data": "Football-Data.co.uk — free for non-commercial use",
            "understat": "Understat — public data, attribution appreciated",
            "transfermarkt": "Transfermarkt — manual import only, no automated scraping",
        },
    })


def _get_scouting_queues(force_refresh: bool = False):
    """Build and cache scouting queues to avoid redundant computation.

    Each of get_review_queue / get_watchlist / get_shortlist previously
    called build_scouting_queues independently on the full ratings
    DataFrame.  This helper computes the queues once per process and
    reuses the result for all three endpoints.

    Pass ``force_refresh=True`` to bypass the cache (e.g. after model retraining).
    """
    cached = _wc_cache.get(_WC_SCOUTING_KEY)
    if cached is _MISSING or force_refresh:
        df = load_player_ratings(force_refresh=force_refresh)
        if df.empty:
            from scoutfootball.evaluation.scouting_queue import ScoutingQueues
            queues = ScoutingQueues(
                review_queue=df, watchlist=df, shortlist=df,
            )
        else:
            queues = build_scouting_queues(
                df,
                run_id=_latest_run_id(),
                reports_root=_settings().data_root / "reports",
            )
        _wc_cache.set(_WC_SCOUTING_KEY, queues)
    return _wc_cache.get(_WC_SCOUTING_KEY)


def get_review_queue(limit: int = 200) -> dict:
    """Return low-confidence players from ratings data as a review queue."""
    df = load_player_ratings()
    if df.empty:
        return {"count": 0, "players": []}

    queues = _get_scouting_queues()
    return _queue_payload(queues.review_queue, limit=limit)


def get_watchlist(limit: int = 100) -> dict:
    df = load_player_ratings()
    if df.empty:
        return {"count": 0, "players": []}
    queues = _get_scouting_queues()
    return _queue_payload(queues.watchlist, limit=limit)


def get_shortlist(limit: int = 100) -> dict:
    df = load_player_ratings()
    if df.empty:
        return {"count": 0, "players": []}
    queues = _get_scouting_queues()
    return _queue_payload(queues.shortlist, limit=limit)


def _enrich_holdout_summary(meta: dict[str, Any]) -> None:
    """Extract a flat holdout summary from metrics for easy frontend display."""
    metrics = meta.get("metrics", {})
    holdout = meta.get("holdout", {})

    # Source: prefer holdout dict, fallback to metrics dict
    src = holdout if holdout else metrics

    # Find the optimized test metrics (most relevant for reporting)
    # Metrics may be stored as JSON strings in meta.json
    def _parse(m: Any) -> dict:
        if isinstance(m, str):
            try:
                return json.loads(m)
            except (json.JSONDecodeError, TypeError):
                return {}
        return m if isinstance(m, dict) else {}

    opt_test = _parse(src.get("optimized_test", {}))
    base_test = _parse(src.get("baseline_test", {}))
    opt_train = _parse(src.get("optimized_train", {}))
    base_train = _parse(src.get("baseline_train", {}))

    def _pick(m: dict) -> dict:
        return {k: v for k, v in m.items() if k in (
            "spearman", "pearson", "rank_loss", "z_mse", "calibration_mae",
            "points_mae", "points_rmse", "points_bias",
            "points_spread_ratio", "raw_spread_ratio",
            "n_players", "n_team_seasons", "team_coverage",
            "split",
        )}

    summary: dict[str, Any] = {}
    if opt_test:
        summary["optimized_test"] = _pick(opt_test)
    elif "optimized_test" in metrics:
        summary["optimized_test"] = _pick(_parse(metrics["optimized_test"]))
    if base_test:
        summary["baseline_test"] = _pick(base_test)
    if opt_train:
        summary["optimized_train"] = _pick(opt_train)
    if base_train:
        summary["baseline_train"] = _pick(base_train)

    # Flat top-level aliases for simple frontend display
    best = opt_test or _parse(metrics.get("optimized_test", {})) or metrics
    for key in ("spearman", "pearson", "rank_loss", "calibration_mae",
                "n_players", "n_team_seasons", "team_coverage"):
        if key in best and key not in meta:
            meta[key] = best[key]

    # Overfit gap
    if "overfit_rank_loss_gap" in src:
        summary["overfit_rank_loss_gap"] = src["overfit_rank_loss_gap"]
    elif "overfit_rank_loss_gap" in metrics:
        summary["overfit_rank_loss_gap"] = metrics["overfit_rank_loss_gap"]

    meta["holdout_summary"] = summary


def _build_reproduce_command(run_id: str, args: dict[str, Any]) -> str:
    """Build a reproduce command string from stored run args."""
    parts = ["PYTHONPATH=src", "uv run python scripts/optimize_ratings_gpu.py"]
    if args.get("seed") is not None:
        parts.append(f"--seed {args['seed']}")
    if args.get("pop_size") is not None:
        parts.append(f"--pop {args['pop_size']}")
    if args.get("n_steps") is not None:
        parts.append(f"--steps {args['n_steps']}")
    if args.get("lr") is not None:
        parts.append(f"--lr {args['lr']}")
    if args.get("patience") is not None:
        parts.append(f"--patience {args['patience']}")
    if args.get("spearman_weight") is not None:
        parts.append(f"--spearman-weight {args['spearman_weight']}")
    if args.get("ndcg_weight") is not None:
        parts.append(f"--ndcg-weight {args['ndcg_weight']}")
    if args.get("position_consistency_weight") is not None:
        parts.append(f"--position-consistency-weight {args['position_consistency_weight']}")
    if args.get("points_regression_weight") is not None:
        parts.append(f"--points-regression-weight {args['points_regression_weight']}")
    if args.get("warmup_steps") is not None:
        parts.append(f"--warmup-steps {args['warmup_steps']}")
    if args.get("grad_clip") is not None:
        parts.append(f"--grad-clip {args['grad_clip']}")
    if args.get("dc_likelihood_weight") is not None and args["dc_likelihood_weight"] > 0:
        parts.append(f"--dc-likelihood-weight {args['dc_likelihood_weight']}")
    if args.get("dc_rho") is not None:
        parts.append(f"--dc-rho {args['dc_rho']}")
    return " ".join(parts)


def _model_run_lineage(meta: dict[str, Any]) -> dict[str, Any]:
    """Return explicit lineage status for current and legacy model-run metadata."""
    lineage = meta.get("lineage")
    if isinstance(lineage, dict):
        return lineage
    return {
        "schema": "scoutfootball.model-run-lineage",
        "version": "1.0.0",
        "status": "not_recorded",
        "dataset_snapshot": {"input_hash": meta.get("input_hash")},
        "feature_manifest": {"hash": None, "schema_version": None},
        "note": "This legacy run predates feature-manifest lineage capture.",
    }


def get_model_runs() -> dict:
    """Return model run registry from local artifacts."""
    settings = _settings()
    runs = []
    ds_label = data_source_label()

    # Check data/models/runs/ directory
    runs_dir = settings.data_root / "models" / "runs"
    if runs_dir.exists():
        for run_dir in sorted(runs_dir.iterdir(), reverse=True):
            meta_path = run_dir / "meta.json"
            if meta_path.exists():
                meta = _read_json(meta_path)
                meta["run_id"] = run_dir.name
                meta["updated_at"] = meta_path.stat().st_mtime
                meta["data_source"] = ds_label
                meta["lineage"] = _model_run_lineage(meta)
                # Build reproduce command from stored args
                run_args = meta.get("args", {})
                meta["reproduce_command"] = _build_reproduce_command(
                    run_dir.name, run_args,
                )
                # Extract holdout metrics summary for easy frontend access
                _enrich_holdout_summary(meta)
                runs.append(meta)

    # Fallback: read optimized_params_meta.json
    if not runs:
        meta_path = settings.data_root / "gold" / "feature_store" / "optimized_params_meta.json"
        if meta_path.exists():
            meta = _read_json(meta_path)
            meta["run_id"] = "latest"
            meta["updated_at"] = meta_path.stat().st_mtime
            meta["data_source"] = ds_label
            meta["lineage"] = _model_run_lineage(meta)
            run_args = meta.get("args", {})
            meta["reproduce_command"] = _build_reproduce_command("latest", run_args)
            _enrich_holdout_summary(meta)
            runs.append(meta)

    return _clean_json_value({"runs": runs, "count": len(runs)})


def _get_run_ids() -> list[str]:
    """Return list of available run IDs."""
    settings = _settings()
    runs_dir = settings.data_root / "models" / "runs"
    if runs_dir.exists():
        return sorted([d.name for d in runs_dir.iterdir() if d.is_dir()], reverse=True)
    return []


def get_model_run_detail(run_id: str) -> dict[str, Any]:
    """Return full details for a single model run.

    Includes run_id, timestamp, input_hash, params, metrics,
    train/test split, feature importance, and data source attribution.
    """
    settings = _settings()
    ds_label = data_source_label()
    runs_dir = settings.data_root / "models" / "runs"

    # Check the runs directory for the specific run
    if runs_dir.exists():
        run_dir = runs_dir / run_id
        meta_path = run_dir / "meta.json"
        if meta_path.exists():
            meta = _read_json(meta_path)
            meta["run_id"] = run_id
            meta["updated_at"] = meta_path.stat().st_mtime
            meta["data_source"] = ds_label
            meta["lineage"] = _model_run_lineage(meta)

            # Build reproduce command from stored args
            run_args = meta.get("args", {})
            meta["reproduce_command"] = _build_reproduce_command(run_id, run_args)

            # Extract holdout metrics summary
            _enrich_holdout_summary(meta)

            # Load feature importance if available
            importance_path = run_dir / "feature_importance.parquet"
            if importance_path.exists():
    
                try:
                    fi_df = _read_parquet(importance_path)
                    meta["feature_importance"] = _clean_json_value(
                        fi_df.to_dict(orient="records"),
                    )
                except Exception:
                    meta["feature_importance"] = []

            # Load optimized params info
            params_path = run_dir / "optimized_params.npy"
            if params_path.exists():
                import numpy as np
                try:
                    params = np.load(params_path)
                    meta["params_summary"] = {
                        "shape": list(params.shape),
                        "mean": round(float(params.mean()), 6),
                        "std": round(float(params.std()), 6),
                        "min": round(float(params.min()), 6),
                        "max": round(float(params.max()), 6),
                    }
                except Exception:
                    pass

            # Data source attribution
            meta["data_attribution"] = {
                "primary_source": ds_label,
                "license_note": (
                    "Player ratings derived from FBref/Understat data. "
                    "Match results from Football-Data.co.uk. "
                    "Event data from StatsBomb Open Data."
                ),
                "statsbomb_attribution_required": _STATSBOMB_ATTRIBUTION,
            }

            return _clean_json_value(meta)

    # Fallback: check optimized_params_meta.json
    meta_path = settings.data_root / "gold" / "feature_store" / "optimized_params_meta.json"
    if meta_path.exists() and run_id in ("latest", "latest-local"):
        meta = _read_json(meta_path)
        meta["run_id"] = "latest"
        meta["updated_at"] = meta_path.stat().st_mtime
        meta["data_source"] = ds_label
        meta["lineage"] = _model_run_lineage(meta)
        run_args = meta.get("args", {})
        meta["reproduce_command"] = _build_reproduce_command("latest", run_args)
        _enrich_holdout_summary(meta)
        meta["data_attribution"] = {
            "primary_source": ds_label,
            "license_note": (
                "Player ratings derived from FBref/Understat data. "
                "Match results from Football-Data.co.uk. "
                "Event data from StatsBomb Open Data."
            ),
            "statsbomb_attribution_required": _STATSBOMB_ATTRIBUTION,
        }
        return _clean_json_value(meta)

    return {"error": f"Run '{run_id}' not found", "available_runs": _get_run_ids()}


def _player_list_to_csv(player_list: list[dict]) -> str:
    """Convert a list of player dicts to CSV text."""
    import csv
    import io

    if not player_list:
        return ""
    buf = io.StringIO()
    fieldnames = list(player_list[0].keys())
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for row in player_list:
        writer.writerow(row)
    return buf.getvalue()


def _confidence_reason(minutes: float, matches_count: int, pool_size: int) -> str:
    """Return a human-readable explanation for the confidence level."""
    reasons = []
    if minutes < 450:
        reasons.append("very few minutes (<450)")
    elif minutes < 900:
        reasons.append("limited minutes (<900)")
    if matches_count < 10:
        reasons.append("few matches (<10)")
    elif matches_count < 20:
        reasons.append("below 20 matches")
    if pool_size < 10:
        reasons.append("small position pool (<10)")
    if not reasons:
        return "adequate minutes, matches, and peer pool"
    return "; ".join(reasons)


def _build_position_explanation(
    row: Any,
    pos_pool: Any,
    attack_score: float,
    defense: float,
    possession: float,
    minutes: float,
    score: float,
) -> dict[str, Any]:
    """Build position-wise explanation for each rating dimension."""
    import pandas as _pd

    def _pct_rank(value: float, pool: Any, col: str) -> float:
        clean = _pd.to_numeric(pool[col], errors="coerce").dropna()
        if clean.empty or value != value:
            return 50.0
        return float((clean < value).sum() / len(clean) * 100)

    def _confidence_label(minutes_val: float, pool_size: int) -> str:
        if minutes_val >= 2700 and pool_size >= 20:
            return "HIGH"
        if minutes_val >= 900 and pool_size >= 10:
            return "MEDIUM"
        return "LOW"

    dims: dict[str, Any] = {}
    pool_size = len(pos_pool)
    conf = _confidence_label(minutes, pool_size)

    # Attack
    attack_col = "npg_p90" if "npg_p90" in pos_pool.columns else "optimized_score"
    attack_pct = _pct_rank(attack_score, pos_pool, attack_col)
    # Adjust: add assists percentile
    if "assists_p90" in pos_pool.columns:
        assists_vals = _pd.to_numeric(
            pos_pool["assists_p90"], errors="coerce",
        ).fillna(0)
        player_assists = float(row.get("assists_p90", 0) or 0)
        assists_pct = float(
            (assists_vals < player_assists).sum()
            / max(len(assists_vals), 1) * 100
        )
        attack_pct = (attack_pct + assists_pct) / 2
    dims["attack"] = {
        "raw_score": round(attack_score, 3),
        "percentile_rank": round(attack_pct, 1),
        "contribution": round(attack_pct * 0.30, 1),
        "confidence": conf,
    }

    # Defense
    if "defense_composite" in pos_pool.columns:
        defense_pct = _pct_rank(
            defense, pos_pool, "defense_composite",
        )
    else:
        defense_pct = 50.0
    dims["defense"] = {
        "raw_score": round(defense, 2) if defense == defense else None,
        "percentile_rank": round(defense_pct, 1),
        "contribution": round(defense_pct * 0.20, 1),
        "confidence": conf,
    }

    # Possession
    if "possession_composite" in pos_pool.columns:
        poss_pct = _pct_rank(
            possession, pos_pool, "possession_composite",
        )
    else:
        poss_pct = 50.0
    dims["possession"] = {
        "raw_score": round(possession, 2) if possession == possession else None,
        "percentile_rank": round(poss_pct, 1),
        "contribution": round(poss_pct * 0.20, 1),
        "confidence": conf,
    }

    # Availability
    avail_pct = min(100.0, minutes / 2700 * 100)
    dims["availability"] = {
        "raw_score": round(minutes),
        "percentile_rank": round(min(100.0, avail_pct), 1),
        "contribution": round(avail_pct * 0.10, 1),
        "confidence": conf,
    }

    # Quality (overall score percentile)
    if "optimized_score" in pos_pool.columns:
        quality_pct = _pct_rank(
            score, pos_pool, "optimized_score",
        )
    else:
        quality_pct = 50.0
    dims["quality"] = {
        "raw_score": round(score, 1),
        "percentile_rank": round(quality_pct, 1),
        "contribution": round(quality_pct * 0.20, 1),
        "confidence": conf,
    }

    return dims


def _compute_position_percentiles(row: Any, pos_pool: Any) -> dict[str, Any]:
    """Compute within-position percentile ranks for key metrics."""
    import pandas as pd

    from scoutfootball.evaluation.position_metrics import (
        POSITION_DIMENSIONS,
        POSITION_GROUP_MAP,
        compute_dimension_percentile,
    )

    raw_position = str(row.get("position_group", ""))
    resolved = POSITION_GROUP_MAP.get(raw_position, raw_position)
    dim_defs = POSITION_DIMENSIONS.get(resolved, {})

    result: dict[str, Any] = {}
    for dim_key, dim_cfg in dim_defs.items():
        label = dim_cfg.get("label", dim_key)
        pct = compute_dimension_percentile(pos_pool, dim_cfg, row)
        result[dim_key] = {"label": label, "percentile": round(pct, 1)}

    # Add overall optimized_score percentile within position
    if "optimized_score" in pos_pool.columns:
        clean = pd.to_numeric(pos_pool["optimized_score"], errors="coerce").dropna()
        score_val = pd.to_numeric(row.get("optimized_score"), errors="coerce")
        if not clean.empty and pd.notna(score_val):
            overall_pct = float((clean < score_val).mean() * 100)
        else:
            overall_pct = None
    else:
        overall_pct = None
    result["overall_score"] = {
        "label": "综合评分",
        "percentile": round(overall_pct, 1) if overall_pct is not None else None,
    }

    return result


def _compute_low_confidence_reasons(row: Any) -> list[str]:
    """Compute low-confidence reasons using the confidence module."""
    from scoutfootball.evaluation.confidence import assess_player_confidence

    assessment = assess_player_confidence(row)
    return list(assessment.reasons)


def _compute_3season_trend(player_rows: Any) -> list[dict[str, Any]]:
    """Compute 3-season trend data for a player from their season rows."""

    if player_rows.empty:
        return []

    # Sort by season descending, take up to 3
    sorted_rows = player_rows.sort_values("season", ascending=False).head(3)

    trends = []
    for _, r in sorted_rows.iterrows():
        entry: dict[str, Any] = {
            "season": str(r.get("season", "")),
            "optimized_score": round(float(r.get("optimized_score", 0) or 0), 1),
            "goals": round(float(r.get("npg_p90", 0) or 0), 3),
            "assists": round(float(r.get("assists_p90", 0) or 0), 3),
            "minutes": round(float(r.get("minutes", 0) or 0)),
        }
        trends.append(entry)

    # Compute deltas (newest vs oldest)
    if len(trends) >= 2:
        newest = trends[0]
        oldest = trends[-1]
        delta = {
            "season_from": oldest["season"],
            "season_to": newest["season"],
            "score_change": round(newest["optimized_score"] - oldest["optimized_score"], 1),
            "goals_change": round(newest["goals"] - oldest["goals"], 3),
            "assists_change": round(newest["assists"] - oldest["assists"], 3),
            "minutes_change": round(newest["minutes"] - oldest["minutes"]),
        }
        return {"seasons": trends, "delta": delta}
    return {"seasons": trends, "delta": None}


def get_player_profile(
    player_name: str,
    season: str | None = None,
    position_group: str | None = None,
    limit: int = 50,
    offset: int = 0,
    fmt: str = "json",
) -> dict:
    """Return detailed player profile with radar dimensions.

    Supports fuzzy name matching, pagination, position/season filters,
    rating snapshot history, xT integration, confidence explanation,
    and CSV export.
    """
    import pandas as pd

    df = load_player_ratings()

    # Alias sub_position → position_group for frontend compatibility
    if "sub_position" in df.columns and "position_group" not in df.columns:
        df["position_group"] = df["sub_position"]

    # Fuzzy search: exact match first, then partial case-insensitive
    exact_mask = df["player"] == player_name
    if exact_mask.any():
        mask = exact_mask
    else:
        mask = df["player"].str.contains(player_name, case=False, na=False)
    if position_group:
        mask = mask & (df["position_group"] == position_group)
    if season:
        mask = mask & (df["season"] == season)
    rows = df[mask]
    total = int(rows.shape[0])

    # If multiple players matched (fuzzy), return list with pagination
    if not exact_mask.any() and total > 1:
        unique_names = rows["player"].unique()
        page_names = unique_names[offset : offset + limit]
        page_rows = rows[rows["player"].isin(page_names)]
        player_list = []
        for pname in page_names:
            pr = page_rows[page_rows["player"] == pname]
            best = pr.loc[pr["optimized_score"].idxmax()] if not pr.empty else pr.iloc[0]
            player_list.append(_clean_json_value({
                "player": pname,
                "found": True,
                "team": best.get("team", ""),
                "league": best.get("league", ""),
                "season": best.get("season", ""),
                "position_group": best.get("position_group", ""),
                "optimized_score": round(float(best.get("optimized_score", 0) or 0), 1),
                "minutes": round(float(best.get("minutes", 0) or 0)),
            }))
        # CSV export
        if fmt == "csv" and player_list:
            return _player_list_to_csv(player_list)
        return _clean_json_value({
            "player": player_name,
            "found": True,
            "fuzzy_match": True,
            "total": total,
            "offset": offset,
            "limit": limit,
            "players": player_list,
        })

    if rows.empty:
        return {"player": player_name, "found": False}

    # Pick the best season (highest score) if multiple
    try:
        row = rows.loc[rows["optimized_score"].idxmax()]
    except (ValueError, TypeError):
        row = rows.iloc[0]

    # Build radar dimensions from available data
    # Attack: npg_p90 + assists_p90 percentile within position
    # Possession: possession_composite
    # Defense: defense_composite
    # Reliability: minutes-based (900+ = high, 450+ = medium)
    # Impact: optimized_score percentile within position

    position = row.get("position_group", "")
    pos_pool = df[df["position_group"] == position]

    def _pct(value: float, pool: pd.Series) -> float:
        clean = pd.to_numeric(pool, errors="coerce").dropna()
        if clean.empty or value != value:
            return 50.0
        return float((clean < value).sum() / len(clean) * 100)

    npg = float(row.get("npg_p90", 0) or 0)
    assists = float(row.get("assists_p90", 0) or 0)
    attack_score = npg + assists
    defense = float(row.get("defense_composite", 0) or 0)
    possession = float(row.get("possession_composite", 0) or 0)
    minutes = float(row.get("minutes", 0) or 0)
    score = float(row.get("optimized_score", 0) or 0)

    radar = [
        round(_pct(attack_score, pos_pool["npg_p90"].fillna(0) + pos_pool["assists_p90"].fillna(0)), 1),  # noqa: E501
        round(_pct(possession, pos_pool["possession_composite"]), 1),
        round(_pct(defense, pos_pool["defense_composite"]), 1),
        round(min(100, minutes / 2700 * 100), 1),  # 2700 min = 30 full matches
        round(_pct(score, pos_pool["optimized_score"]), 1),
    ]

    # All seasons for this player
    seasons = []
    for _, r in rows.sort_values("season").iterrows():
        seasons.append({
            "season": r.get("season", ""),
            "team": r.get("team", ""),
            "league": r.get("league", ""),
            "position_group": r.get("position_group", ""),
            "optimized_score": round(float(r.get("optimized_score", 0) or 0), 1),
            "minutes": round(float(r.get("minutes", 0) or 0)),
        })

    low_appearance = bool(row.get("low_appearance", False))
    matches_count = int(row.get("matches", 0) or 0)

    # xT integration from player_value_metrics
    xt_summary: dict[str, Any] = {"available": False}
    try:
        vm = load_player_value_metrics()
        if not vm.empty and "player_name" in vm.columns:
            player_xt = vm[vm["player_name"].str.lower() == player_name.lower()]
            if not player_xt.empty:
                xt_row = player_xt.iloc[0]
                xt_per_90 = xt_row.get("xT_per_90")
                xt_total = xt_row.get("total_xt")
                # Compute xT percentile within position
                xt_pct = None
                if "xT_per_90" in vm.columns and position:
                    pos_names = df[df["position_group"] == position]["player"].unique()
                    pos_xt = vm[vm["player_name"].isin(pos_names)]["xT_per_90"].dropna()
                    if not pos_xt.empty and pd.notna(xt_per_90):
                        xt_pct = round(float((pos_xt < xt_per_90).sum() / len(pos_xt) * 100), 1)
                # xT contribution estimate
                xt_contribution = None
                if pd.notna(xt_per_90) and score > 0:
                    xt_contribution = round(float(xt_per_90 / 0.3 * 10), 1)
                xt_summary = {
                    "available": True,
                    "xT_per_90": round(float(xt_per_90), 4) if pd.notna(xt_per_90) else None,
                    "xT_total": round(float(xt_total), 4) if pd.notna(xt_total) else None,
                    "xT_percentile": xt_pct,
                    "xT_contribution": xt_contribution,
                    "coverage_note": "StatsBomb Open Data sample only",
                }
    except Exception:
        xt_summary = {"available": False, "reason": "xT data not available for this player"}

    # Confidence reason explanation
    pool_size = len(pos_pool)
    conf_reason = _confidence_reason(minutes, matches_count, pool_size)

    # Build position explanation with xT
    position_explanation = _build_position_explanation(
        row, pos_pool, attack_score, defense, possession, minutes, score,
    )
    if xt_summary.get("available"):
        _cov = xt_summary.get("coverage_note") or ""
        _xt_conf = "LOW" if "StatsBomb" in _cov else "MEDIUM"
        position_explanation["xT"] = {
            "xT_per_90": xt_summary.get("xT_per_90"),
            "percentile_rank": xt_summary.get("xT_percentile"),
            "contribution": xt_summary.get("xT_contribution"),
            "confidence": _xt_conf,
        }
    else:
        position_explanation["xT"] = {
            "xT_per_90": None,
            "percentile_rank": None,
            "contribution": None,
            "confidence": "N/A",
            "note": "xT data not available for this player",
        }

    result = _clean_json_value({
        "player": player_name,
        "found": True,
        "team": row.get("team", ""),
        "league": row.get("league", ""),
        "season": row.get("season", ""),
        "position_group": position,
        "optimized_score": round(score, 1),
        "minutes": round(minutes),
        "matches": matches_count,
        "low_appearance": low_appearance,
        "confidence_level": str(row.get("confidence_level", "LOW")).upper(),
        "confidence_reason": conf_reason,
        "npg_p90": round(npg, 3),
        "assists_p90": round(assists, 3),
        "defense_composite": round(defense, 2) if defense == defense else None,
        "possession_composite": round(possession, 2) if possession == possession else None,
        "radar": radar,
        "seasons": seasons,
        "position_explanation": position_explanation,
        "xt_summary": xt_summary,
        "position_percentiles": _compute_position_percentiles(row, pos_pool),
        "low_confidence_reasons": _compute_low_confidence_reasons(row),
        "trend_3seasons": _compute_3season_trend(rows),
    })
    # CSV export
    if fmt == "csv":
        return _player_list_to_csv([result])
    return result


# ── Player comparison ────────────────────────────────────────────────────

_RADAR_LABELS = ["Attack", "Possession", "Defense", "Reliability", "Impact"]


def get_player_comparison(player_a: str, player_b: str) -> dict:
    """Compare two players side-by-side with radar overlay and metric diffs.

    Calls get_player_profile for both players, then builds a unified
    comparison structure with per-dimension deltas.
    """
    profile_a = get_player_profile(player_a)
    profile_b = get_player_profile(player_b)

    if not profile_a.get("found"):
        return {"error": f"Player '{player_a}' not found", "found_a": False}
    if not profile_b.get("found"):
        return {"error": f"Player '{player_b}' not found", "found_b": False}

    # Build radar comparison
    radar_a = profile_a.get("radar", [0, 0, 0, 0, 0])
    radar_b = profile_b.get("radar", [0, 0, 0, 0, 0])
    # Pad to 5 elements if needed
    while len(radar_a) < 5:
        radar_a.append(0)
    while len(radar_b) < 5:
        radar_b.append(0)

    radar_comparison = []
    for i, label in enumerate(_RADAR_LABELS):
        val_a = float(radar_a[i]) if i < len(radar_a) else 0.0
        val_b = float(radar_b[i]) if i < len(radar_b) else 0.0
        radar_comparison.append({
            "dimension": label,
            "player_a": round(val_a, 1),
            "player_b": round(val_b, 1),
            "diff": round(val_a - val_b, 1),
            "advantage": "a" if val_a > val_b else ("b" if val_b > val_a else "tie"),
        })

    # Position percentiles comparison
    # position_percentiles is a dict: {dim_key: {label, percentile}}
    pp_a = profile_a.get("position_percentiles", {})
    pp_b = profile_b.get("position_percentiles", {})

    # Merge dimension keys from both (dict keys, preserving order)
    all_dims = list(dict.fromkeys(
        list(pp_a.keys()) + list(pp_b.keys())
    ))

    pct_comparison = []
    for dim in all_dims:
        entry_a = pp_a.get(dim, {})
        entry_b = pp_b.get(dim, {})
        val_a = entry_a.get("percentile") if isinstance(entry_a, dict) else None
        val_b = entry_b.get("percentile") if isinstance(entry_b, dict) else None
        label = entry_a.get("label") or entry_b.get("label") or dim
        diff = None
        advantage = "tie"
        if val_a is not None and val_b is not None:
            diff = round(float(val_a) - float(val_b), 1)
            advantage = "a" if val_a > val_b else ("b" if val_b > val_a else "tie")
        pct_comparison.append({
            "dimension": dim,
            "label": label,
            "player_a": val_a,
            "player_b": val_b,
            "diff": diff,
            "advantage": advantage,
        })

    # Key stats comparison
    stats_fields = [
        "optimized_score", "minutes", "matches", "npg_p90",
        "assists_p90", "defense_composite", "possession_composite",
    ]
    stats_comparison = []
    for field in stats_fields:
        val_a = profile_a.get(field)
        val_b = profile_b.get(field)
        diff = None
        if val_a is not None and val_b is not None:
            try:
                diff = round(float(val_a) - float(val_b), 2)
            except (ValueError, TypeError):
                pass
        stats_comparison.append({
            "metric": field,
            "player_a": val_a,
            "player_b": val_b,
            "diff": diff,
        })

    return _clean_json_value({
        "player_a": {
            "name": profile_a.get("player", player_a),
            "team": profile_a.get("team", ""),
            "league": profile_a.get("league", ""),
            "season": profile_a.get("season", ""),
            "position_group": profile_a.get("position_group", ""),
            "optimized_score": profile_a.get("optimized_score"),
            "confidence_level": profile_a.get("confidence_level", "LOW"),
        },
        "player_b": {
            "name": profile_b.get("player", player_b),
            "team": profile_b.get("team", ""),
            "league": profile_b.get("league", ""),
            "season": profile_b.get("season", ""),
            "position_group": profile_b.get("position_group", ""),
            "optimized_score": profile_b.get("optimized_score"),
            "confidence_level": profile_b.get("confidence_level", "LOW"),
        },
        "radar_labels": _RADAR_LABELS,
        "radar_a": [r["player_a"] for r in radar_comparison],
        "radar_b": [r["player_b"] for r in radar_comparison],
        "radar_comparison": radar_comparison,
        "position_percentile_comparison": pct_comparison,
        "stats_comparison": stats_comparison,
        "same_position": (
            profile_a.get("position_group", "") == profile_b.get("position_group", "")
        ),
    })


# ── Player similarity search ─────────────────────────────────────────────

_SIMILARITY_FEATURES = [
    ("npg_p90", "Attack"),
    ("assists_p90", "Creation"),
    ("defense_composite", "Defense"),
    ("possession_composite", "Possession"),
    ("optimized_score", "Overall"),
    ("minutes", "Availability"),
]

# Per-position feature weights. Each weight scales the corresponding z-scored
# feature before cosine similarity is computed, so that dimensions more
# relevant to a position carry more signal. Weights are normalised inside
# ``find_similar_players`` so absolute magnitude does not matter, only ratios.
_POSITION_FEATURE_WEIGHTS: dict[str, dict[str, float]] = {
    "GK": {"npg_p90": 0.0, "assists_p90": 0.0, "defense_composite": 3.0,
           "possession_composite": 1.0, "optimized_score": 2.0, "minutes": 1.0},
    "CB": {"npg_p90": 0.5, "assists_p90": 0.5, "defense_composite": 3.0,
           "possession_composite": 1.5, "optimized_score": 1.5, "minutes": 1.0},
    "FB": {"npg_p90": 0.5, "assists_p90": 1.0, "defense_composite": 2.0,
           "possession_composite": 2.0, "optimized_score": 1.5, "minutes": 1.0},
    "DM": {"npg_p90": 0.5, "assists_p90": 1.0, "defense_composite": 2.5,
           "possession_composite": 2.5, "optimized_score": 1.5, "minutes": 1.0},
    "CM": {"npg_p90": 1.0, "assists_p90": 1.5, "defense_composite": 1.5,
           "possession_composite": 3.0, "optimized_score": 1.5, "minutes": 1.0},
    "AM": {"npg_p90": 2.0, "assists_p90": 2.5, "defense_composite": 0.5,
           "possession_composite": 2.5, "optimized_score": 1.5, "minutes": 1.0},
    "W":  {"npg_p90": 2.5, "assists_p90": 2.5, "defense_composite": 0.5,
           "possession_composite": 1.5, "optimized_score": 1.5, "minutes": 1.0},
    "ST": {"npg_p90": 3.0, "assists_p90": 1.5, "defense_composite": 0.5,
           "possession_composite": 1.0, "optimized_score": 1.5, "minutes": 1.0},
}
_DEFAULT_FEATURE_WEIGHTS = {fc[0]: 1.0 for fc in _SIMILARITY_FEATURES}


def _position_weights(position_group: str) -> dict[str, float]:
    """Return feature weights for a position group, falling back to uniform."""
    pos = (position_group or "").strip().upper()
    return _POSITION_FEATURE_WEIGHTS.get(pos, _DEFAULT_FEATURE_WEIGHTS)


def find_similar_players(
    player_name: str,
    season: str | None = None,
    limit: int = 10,
    *,
    same_position_only: bool = True,
    league: str | None = None,
    min_minutes: float | None = None,
) -> dict:
    """Find players with similar profiles.

    Uses z-scored feature vectors (attack/creation/defense/possession/
    overall/availability), position-weighted before cosine similarity is
    computed. Returns top-N comparable players with similarity score, shared
    strengths and weaknesses.

    Parameters
    ----------
    same_position_only:
        When ``True`` (default), only compare within the target player's
        position group, z-scoring against that pool. When ``False``, build a
        cross-position pool where each player is z-scored against their own
        position group first, so profiles stay comparable across positions.
    league:
        Optional league filter applied to the candidate pool. The target
        player is still resolved from the full dataset (ignoring this filter
        if necessary) so a known player is never hidden by a league filter.
    min_minutes:
        Optional minimum minutes threshold applied to the candidate pool.
        Players below this threshold are excluded as low-reliability.
    """
    df = load_player_ratings(season=season)
    if df.empty:
        return {"count": 0, "target": None, "similar": [], "error": "no_data"}

    # Resolve position_group column
    if "position_group" not in df.columns:
        if "sub_position" in df.columns:
            df["position_group"] = df["sub_position"]
        else:
            return {"count": 0, "target": None, "similar": [], "error": "no_position"}

    name_col = "player_name" if "player_name" in df.columns else "player"
    if name_col not in df.columns:
        name_col = "player"

    # Fuzzy match target player
    exact_mask = df["player"] == player_name
    if exact_mask.any():
        mask = exact_mask
    else:
        mask = df["player"].str.contains(player_name, case=False, na=False)
    if season:
        mask = mask & (df["season"] == season)
    target_rows = df[mask]
    if target_rows.empty:
        return {"count": 0, "target": None, "similar": [], "error": "not_found"}

    # Pick best season for target
    try:
        target_row = target_rows.loc[target_rows["optimized_score"].idxmax()]
    except (ValueError, TypeError):
        target_row = target_rows.iloc[0]

    target_pos = str(target_row.get("position_group", ""))
    target_player = str(target_row.get("player", player_name))
    target_season = str(target_row.get("season", ""))

    feature_cols = [fc[0] for fc in _SIMILARITY_FEATURES]
    # Coerce feature columns to numeric across the full frame once.
    for col in feature_cols:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Build candidate pool with optional filters.
    pool = df.copy()
    if min_minutes is not None and min_minutes > 0:
        pool = pool[pool["minutes"].fillna(0.0) >= float(min_minutes)]
    if league:
        pool = pool[pool["league"].astype(str).str.lower() == str(league).lower()]

    # Resolve target feature vector (raw, before z-scoring).
    target_features = np.array(
        [float(target_row.get(col, 0.0) or 0.0) for col in feature_cols],
        dtype=float,
    )

    if same_position_only:
        pool = pool[pool["position_group"] == target_pos]
        if len(pool) < 2:
            return {
                "count": 0,
                "target": _target_payload(target_row, target_player, target_season, target_pos),
                "similar": [],
                "error": "pool_too_small",
            }
        # Z-score within the single-position pool. The target's z-score is
        # computed using the same pool statistics even when filters excluded
        # the target row from the pool (cross-league scouting use case).
        means = pool[feature_cols].mean()
        stds = pool[feature_cols].std(ddof=0).replace(0, 1.0)
        z_matrix = (pool[feature_cols] - means) / stds
        weights = _position_weights(target_pos)
        weight_vec = np.array([weights.get(col, 1.0) for col in feature_cols], dtype=float)
        z_values = z_matrix.values * weight_vec
        pool_indices = list(pool.index)
        # Compute target z-score against pool statistics (target may be absent
        # from pool when league/min_minutes filters exclude it).
        target_z = (target_features - means.values) / stds.values
        target_vec = target_z * weight_vec
        # Percentile ranks for the pool (used for strengths/weaknesses).
        pct_ranks = pool[feature_cols].rank(pct=True) * 100
        # Target percentile ranks: rank target against the pool by counting
        # how many pool members fall below the target's raw value.
        target_pcts_series = pd.Series(index=feature_cols, dtype=float)
        for col in feature_cols:
            col_vals = pool[col]
            target_val = float(target_row.get(col, 0.0) or 0.0)
            target_pcts_series[col] = (
                (col_vals < target_val).sum() / max(len(col_vals), 1) * 100
            )
    else:
        # Cross-position pool: z-score each player against their own position
        # group first, so profiles stay comparable across positions.
        if len(pool) < 2:
            return {
                "count": 0,
                "target": _target_payload(target_row, target_player, target_season, target_pos),
                "similar": [],
                "error": "pool_too_small",
            }
        # Compute per-position means/stds from the full df (not the filtered
        # pool) so z-scores are stable regardless of league/minute filters.
        z_full = pd.DataFrame(index=df.index, columns=feature_cols, dtype=float)
        pct_full = pd.DataFrame(index=df.index, columns=feature_cols, dtype=float)
        per_pos_stats: dict[str, tuple[pd.Series, pd.Series]] = {}
        for pos, pos_frame in df.groupby("position_group"):
            means = pos_frame[feature_cols].mean()
            stds = pos_frame[feature_cols].std(ddof=0).replace(0, 1.0)
            per_pos_stats[pos] = (means, stds)
            z_full.loc[pos_frame.index] = (
                (pos_frame[feature_cols] - means) / stds
            ).values
            pct_full.loc[pos_frame.index] = (
                pos_frame[feature_cols].rank(pct=True) * 100
            ).values
        # Apply target player's position weights (consistent comparison axis).
        weights = _position_weights(target_pos)
        weight_vec = np.array([weights.get(col, 1.0) for col in feature_cols], dtype=float)
        z_full_weighted = z_full.values * weight_vec
        # Restrict to filtered pool (preserving pool row order).
        pool_indices = list(pool.index)
        pool_pos_in_df = [list(df.index).index(i) for i in pool_indices]
        z_values = z_full_weighted[pool_pos_in_df]
        # Re-resolve pool from df for downstream metadata access.
        pool = df.loc[pool_indices].copy()
        # Compute target z-score against target's own position group stats.
        target_pos_stats = per_pos_stats.get(target_pos)
        if target_pos_stats is None:
            # Position group had only the target row (no groupby entry with
            # others); fall back to pool statistics.
            t_means = pool[feature_cols].mean()
            t_stds = pool[feature_cols].std(ddof=0).replace(0, 1.0)
        else:
            t_means, t_stds = target_pos_stats
        target_z = (target_features - t_means.values) / t_stds.values
        target_vec = target_z * weight_vec
        pct_ranks = pct_full.loc[pool_indices]
        target_pcts_series = pd.Series(index=feature_cols, dtype=float)
        for col in feature_cols:
            target_pcts_series[col] = float(pct_full.loc[target_row.name, col]) \
                if target_row.name in pct_full.index else 50.0

    # Cosine similarity
    target_norm = float(np.linalg.norm(target_vec))
    if target_norm == 0:
        return {
            "count": 0,
            "target": _target_payload(target_row, target_player, target_season, target_pos),
            "similar": [],
            "error": "zero_vector",
        }

    norms = np.linalg.norm(z_values, axis=1)
    safe_norms = np.where(norms == 0, 1.0, norms)
    similarities = (z_values @ target_vec) / (safe_norms * target_norm)
    # Clamp to [0, 1] — negative cosine similarity means "opposite" profile,
    # which is not meaningful as a similarity score for users
    similarities = np.clip(similarities, 0, 1)

    # Exclude target from results. Target may or may not be in the pool
    # (filtered out by league/min_minutes). When present, skip that row.
    candidates = []
    for i, idx in enumerate(pool_indices):
        row = pool.loc[idx]
        pname = str(row.get("player", ""))
        if pname == target_player:
            continue  # exclude target and same-player other-season rows
        candidates.append((i, idx, pname, row, similarities[i]))

    # Sort by similarity descending
    candidates.sort(key=lambda c: c[4], reverse=True)
    candidates = candidates[:limit]

    similar_list = []
    for _i, idx, pname, row, sim in candidates:
        cand_pcts = pct_ranks.loc[idx]
        # Shared strengths: both > 70th percentile
        shared_strengths = []
        shared_weaknesses = []
        for col, label in _SIMILARITY_FEATURES:
            t_pct = float(target_pcts_series.get(col, 50))
            c_pct = float(cand_pcts.get(col, 50))
            if t_pct > 70 and c_pct > 70:
                shared_strengths.append(label)
            elif t_pct < 30 and c_pct < 30:
                shared_weaknesses.append(label)

        similar_list.append(_clean_json_value({
            "name": pname,
            "team": str(row.get("team", "")),
            "league": str(row.get("league", "")),
            "season": str(row.get("season", "")),
            "position_group": str(row.get("position_group", "")),
            "optimized_score": round(float(row.get("optimized_score", 0) or 0), 1),
            "similarity": round(float(sim) * 100, 1),
            "shared_strengths": shared_strengths,
            "shared_weaknesses": shared_weaknesses,
            "minutes": round(float(row.get("minutes", 0) or 0)),
        }))

    # Surface the active weights + filters in the response so callers can
    # explain why a given candidate ranked where it did.
    weights_out = {label: round(float(weights.get(col, 1.0)), 3)
                   for col, label in _SIMILARITY_FEATURES}

    return _clean_json_value({
        "count": len(similar_list),
        "target": _target_payload(target_row, target_player, target_season, target_pos),
        "features": [fc[1] for fc in _SIMILARITY_FEATURES],
        "feature_weights": weights_out,
        "filters": {
            "same_position_only": bool(same_position_only),
            "league": league,
            "min_minutes": min_minutes,
            "season": season,
        },
        "similar": similar_list,
    })


def _target_payload(target_row, target_player: str, target_season: str, target_pos: str) -> dict:
    return _clean_json_value({
        "name": target_player,
        "team": str(target_row.get("team", "")),
        "league": str(target_row.get("league", "")),
        "season": target_season,
        "position_group": target_pos,
        "optimized_score": round(float(target_row.get("optimized_score", 0) or 0), 1),
    })


# ── World Cup endpoints ──────────────────────────────────────────────────


def get_wc_groups() -> dict:
    """Return World Cup group data with team strength ratings."""
    enriched, strengths = _get_wc_enriched_squads()

    groups_data = []
    for letter, teams in GROUPS.items():
        group_teams = []
        for team in teams:
            squad = enriched.get(team, [])
            rated = [p for p in squad if p.has_rating]
            big5_count = sum(1 for p in squad if p.club_league in BIG5_LEAGUES)
            avg_rating = (
                round(sum(p.rating for p in rated) / len(rated), 2)
                if rated else None
            )
            group_teams.append({
                "team": team,
                "is_host": team in HOSTS,
                "strength": round(strengths.get(team, 0), 3),
                "rated_players": len(rated),
                "total_players": len(squad),
                "big5_players": big5_count,
                "avg_rating": avg_rating,
            })
        groups_data.append({
            "group": letter,
            "teams": group_teams,
        })

    return _clean_json_value({
        "status": "ok",
        "source_attribution": (
            "Ratings derived from FBref/Understat data "
            "via ScoutFootball optimizer"
        ),
        "disclaimer": (
            "Squad ratings are from domestic league performance, "
            "not national team matches. Non-Big5 league players "
            "may lack rating data."
        ),
        "groups": groups_data,
    })


def get_wc_schedule(
    group: str | None = None,
    matchday: int | None = None,
) -> dict:
    """Return World Cup group stage schedule."""
    matches = generate_group_stage_matches()

    match_dicts = []
    for m in matches:
        if group and m.group != group:
            continue
        if matchday and m.matchday != matchday:
            continue
        match_dicts.append({
            "matchday": m.matchday,
            "date": m.date,
            "time_et": m.time_et,
            "home": m.home,
            "away": m.away,
            "venue": m.venue,
            "city": m.city,
            "group": m.group,
            "stage": m.stage,
        })

    return _clean_json_value({
        "status": "ok",
        "count": len(match_dicts),
        "source_attribution": (
            "Schedule generated from official FIFA fixture pattern; "
            "dates/venues are approximate"
        ),
        "matches": match_dicts,
    })


def get_wc_squad(team: str) -> dict:
    """Return a specific team's World Cup squad with player ratings."""
    enriched, _ = _get_wc_enriched_squads()
    squad = enriched.get(team, get_squad(team))

    group = get_team_group(team)
    rated = [p for p in squad if p.has_rating]
    big5_count = sum(1 for p in squad if p.club_league in BIG5_LEAGUES)
    avg_rating = (
        round(sum(p.rating for p in rated) / len(rated), 2)
        if rated else None
    )

    players = []
    for p in squad:
        players.append({
            "name": p.name,
            "position": p.position,
            "club": p.club,
            "club_league": p.club_league,
            "has_rating": p.has_rating,
            "rating": round(p.rating, 2) if p.rating is not None else None,
            "rating_confidence": p.rating_confidence,
        })

    # Sort: rated players first, then by rating desc
    players.sort(key=lambda p: (not p["has_rating"], -(p["rating"] or 0)))

    return _clean_json_value({
        "status": "ok",
        "team": team,
        "group": group,
        "is_host": team in HOSTS,
        "total_players": len(squad),
        "rated_players": len(rated),
        "big5_players": big5_count,
        "avg_rating": avg_rating,
        "squad_balance": compute_squad_balance(squad),
        "source_attribution": (
            "Ratings derived from FBref/Understat data "
            "via ScoutFootball optimizer"
        ),
        "disclaimer": (
            "Squad rosters are placeholder lists; official 26-man "
            "squads not yet announced. Ratings from domestic league "
            "performance only."
        ),
        "players": players,
    })


def get_wc_squad_balance_comparison(team_a: str, team_b: str) -> dict:
    """Compare two expected-callup snapshots without inferring a lineup."""
    enriched_squads, _ = _get_wc_enriched_squads()
    missing = [team for team in (team_a, team_b) if team not in enriched_squads]
    if missing:
        return {
            "status": "error",
            "error": f"Team(s) not found in World Cup data: {', '.join(missing)}",
        }

    team_a_balance = compute_squad_balance(enriched_squads[team_a])
    team_b_balance = compute_squad_balance(enriched_squads[team_b])
    role_rows = []
    for role, team_a_role in team_a_balance["roles"].items():
        team_b_role = team_b_balance["roles"][role]
        role_rows.append({
            "role": role,
            "team_a": team_a_role,
            "team_b": team_b_role,
            "count_difference": team_a_role["count"] - team_b_role["count"],
            "rated_player_difference": (
                team_a_role["rated_players"] - team_b_role["rated_players"]
            ),
            "rating_coverage_difference": round(
                team_a_role["rating_coverage"] - team_b_role["rating_coverage"], 4
            ),
        })

    return _clean_json_value({
        "schema": "scoutfootball.world-cup-squad-balance-comparison",
        "version": "1.0.0",
        "status": "ok",
        "scope": "expected_callup_snapshot",
        "teams": {
            "team_a": {"team": team_a, "balance": team_a_balance},
            "team_b": {"team": team_b, "balance": team_b_balance},
        },
        "roles": role_rows,
        "disclaimer": (
            "This compares local expected-callup snapshots only. It is not a "
            "confirmed roster, lineup, injury report, tactical recommendation, "
            "or claim that one team is stronger in a role."
        ),
    })


def get_wc_predictions() -> dict:
    """Return World Cup group stage predictions based on team strengths."""
    enriched, strengths = _get_wc_enriched_squads()
    strength_details = _get_wc_strength_details()
    group_preds = compute_group_predictions(strengths)

    # Build 48-team ranking
    ranked = sorted(strengths.items(), key=lambda x: x[1], reverse=True)
    ranking = []
    for rank, (team, strength) in enumerate(ranked, 1):
        group = get_team_group(team)
        squad = enriched.get(team, [])
        rated = [p for p in squad if p.has_rating]
        ranking.append({
            "rank": rank,
            "team": team,
            "group": group,
            "strength": round(strength, 3),
            "rated_players": len(rated),
            "coverage": strength_details.get(team, {}).get("coverage"),
            "core_avg_rating": strength_details.get(team, {}).get("core_avg_rating"),
            "shrunk_avg_rating": strength_details.get(team, {}).get("shrunk_avg_rating"),
        })

    # Best 3rd-place predictions
    third_place = []
    for gp in group_preds:
        teams = gp["teams"]
        if len(teams) >= 3:
            third = teams[2]
            third["group"] = gp["group"]
            third_place.append(third)
    third_place.sort(key=lambda x: x["strength"], reverse=True)

    return _clean_json_value({
        "status": "ok",
        "source_attribution": (
            "Predictions based on squad ratings from "
            "FBref/Understat data and Opta public priors"
        ),
        "disclaimer": (
            "Probabilities are rough estimates from a simplified "
            "strength-ratio model. Non-Big5 league team strengths "
            "may be underestimated. Not a real match prediction."
        ),
        "groups": group_preds,
        "ranking": ranking,
        "best_third_place": third_place[:8],
    })


def get_wc_knockout() -> dict:
    """Return World Cup knockout bracket simulation with round-by-round probabilities.

    Simulates the Round of 32 through the Final using a Bradley-Terry
    strength model and Monte Carlo tournament win probabilities.
    Requires the World Cup enriched squad data to be available.
    """
    enriched_squads, strengths = _get_wc_enriched_squads()
    if not enriched_squads:
        return {"status": "error", "error": "World Cup squad data not available"}

    group_preds = compute_group_predictions(strengths)
    bracket = _simulate_knockout(strengths, group_preds, num_simulations=10000)
    return _clean_json_value(bracket)


def get_wc_team_outlook(team: str) -> dict:
    """Return a comprehensive tournament outlook for a single World Cup team.

    Aggregates group finish probabilities, projected knockout path,
    championship probability, and squad strength breakdown.
    """
    enriched_squads, strengths = _get_wc_enriched_squads()
    if not enriched_squads:
        return {"status": "error", "error": "World Cup squad data not available"}
    if team not in strengths:
        return {"status": "error", "error": f"Team '{team}' not found in World Cup data"}

    strength_details = _get_wc_strength_details()
    group_preds = compute_group_predictions(strengths)
    bracket = _simulate_knockout(strengths, group_preds, num_simulations=10000)
    outlook = _compute_team_outlook(
        team, strengths, group_preds, bracket, strength_details,
    )
    outlook["squad_balance"] = compute_squad_balance(enriched_squads.get(team, []))
    return _clean_json_value(outlook)


def get_wc_teams() -> dict:
    """Return all 48 World Cup teams with strength ratings and group info."""
    enriched, strengths = _get_wc_enriched_squads()
    strength_details = _get_wc_strength_details()

    teams_data = []
    for letter, team_names in GROUPS.items():
        for team in team_names:
            squad = enriched.get(team, [])
            rated = [p for p in squad if p.has_rating]
            big5_count = sum(1 for p in squad if p.club_league in BIG5_LEAGUES)
            avg_rating = (
                round(sum(p.rating for p in rated) / len(rated), 2)
                if rated else None
            )
            details = strength_details.get(team, {})
            teams_data.append({
                "team": team,
                "group": letter,
                "is_host": team in HOSTS,
                "strength": round(strengths.get(team, 0), 3),
                "rated_players": len(rated),
                "total_players": len(squad),
                "big5_players": big5_count,
                "avg_rating": avg_rating,
                "coverage": details.get("coverage"),
                "observed_avg_rating": details.get("observed_avg_rating"),
                "proxy_avg_rating": details.get("proxy_avg_rating"),
                "shrunk_avg_rating": details.get("shrunk_avg_rating"),
                "core_avg_rating": details.get("core_avg_rating"),
                "depth_avg_rating": details.get("depth_avg_rating"),
                "reserve_avg_rating": details.get("reserve_avg_rating"),
                "squad_quality_rating": details.get("squad_quality_rating"),
                "rating_score": details.get("rating_score"),
                "opta_score": details.get("opta_score"),
                "league_score": details.get("league_score"),
                "coverage_score": details.get("coverage_score"),
                "big5_score": details.get("big5_score"),
            })

    return _clean_json_value({
        "status": "ok",
        "count": len(teams_data),
        "source_attribution": (
            "Ratings derived from FBref/Understat data "
            "via ScoutFootball optimizer"
        ),
        "disclaimer": (
            "Squad ratings are from domestic league performance, "
            "not national team matches. Non-Big5 league players "
            "may lack rating data."
        ),
        "teams": teams_data,
    })


# ── Tournament state endpoints ───────────────────────────────────────────


def _wc_tournament_state():
    """Load the current tournament state (lazy-init if no file exists)."""
    from scoutfootball.worldcup.tournament import load_state

    # load_state() returns a fresh init_state() if the default file is missing
    return load_state()


def get_wc_tournament_summary() -> dict:
    """Return a comprehensive summary of the current tournament state."""
    from scoutfootball.worldcup.tournament import tournament_summary

    state = _wc_tournament_state()
    summary = tournament_summary(state)
    summary["status"] = "ok"
    return _clean_json_value(summary)


def get_wc_tournament_standings(group: str | None = None) -> dict:
    """Return standings for one or all groups."""
    from dataclasses import asdict

    from scoutfootball.worldcup.tournament import (
        compute_all_standings,
        compute_group_standings,
    )

    state = _wc_tournament_state()
    if group:
        letter = group.upper()
        if letter not in GROUPS:
            return _clean_json_value({
                "status": "error",
                "code": "unknown_group",
                "message": f"Unknown group '{group}'. Valid: A-L",
            })
        standings = {letter: [asdict(s) for s in compute_group_standings(state, letter)]}
    else:
        all_standings = compute_all_standings(state)
        standings = {
            letter: [asdict(s) for s in rows]
            for letter, rows in all_standings.items()
        }

    return _clean_json_value({
        "status": "ok",
        "standings": standings,
    })


def get_wc_tournament_matches(
    group: str | None = None,
    pending: bool = False,
) -> dict:
    """Return matches with optional group filter and pending-only flag."""
    from scoutfootball.worldcup.tournament import _match_completed

    state = _wc_tournament_state()
    matches_out = []
    for m in state.matches:
        if group and m.get("group") != group.upper():
            continue
        result = state.results.get(m["match_id"])
        is_done = _match_completed(result)
        if pending and is_done:
            continue
        entry = {"match_id": m["match_id"], **m}
        if is_done:
            entry["result"] = result
            entry["completed"] = True
        else:
            entry["completed"] = False
        matches_out.append(entry)

    return _clean_json_value({
        "status": "ok",
        "count": len(matches_out),
        "matches": matches_out,
    })


def get_wc_tournament_scenarios(team: str, max_scenarios: int = 30) -> dict:
    """Return qualification scenarios for a single team."""
    from dataclasses import asdict

    from scoutfootball.worldcup.tournament import compute_team_scenarios

    state = _wc_tournament_state()
    try:
        result = compute_team_scenarios(state, team, max_scenarios=max_scenarios)
    except ValueError as exc:
        return _clean_json_value({
            "status": "error",
            "code": "invalid_team",
            "message": str(exc),
        })

    return _clean_json_value({
        "status": "ok",
        "team": result.team,
        "group": result.group,
        "current_standing": result.current_standing,
        "remaining_matches": result.remaining_matches,
        "advance_probability": result.advance_probability,
        "scenarios": [asdict(s) for s in result.scenarios],
        "summary": result.summary,
    })


def apply_wc_tournament_result(
    match_id: str,
    home_goals: int,
    away_goals: int,
) -> dict:
    """Record a match result and persist state. Returns updated group standings."""
    from dataclasses import asdict

    from scoutfootball.worldcup.tournament import (
        DEFAULT_STATE_PATH,
        apply_result,
        compute_group_standings,
        save_state,
    )

    state = _wc_tournament_state()
    match = state.match_by_id(match_id)
    if not match:
        return _clean_json_value({
            "status": "error",
            "code": "match_not_found",
            "message": f"Match id '{match_id}' not found",
        })

    ok = apply_result(state, match_id, home_goals, away_goals)
    if not ok:
        return _clean_json_value({
            "status": "error",
            "code": "invalid_result",
            "message": (
                f"Failed to apply {home_goals}-{away_goals} to {match_id} "
                "(goals must be 0-30)"
            ),
        })

    save_state(state, DEFAULT_STATE_PATH)

    group = match.get("group")
    standings = (
        [asdict(s) for s in compute_group_standings(state, group)]
        if group else []
    )

    return _clean_json_value({
        "status": "ok",
        "match_id": match_id,
        "home": match["home"],
        "away": match["away"],
        "home_goals": home_goals,
        "away_goals": away_goals,
        "group": group,
        "standings": standings,
    })


def clear_wc_tournament_result(match_id: str) -> dict:
    """Clear a recorded match result and persist state."""
    from scoutfootball.worldcup.tournament import (
        DEFAULT_STATE_PATH,
        clear_result,
        save_state,
    )

    state = _wc_tournament_state()
    if not clear_result(state, match_id):
        return _clean_json_value({
            "status": "error",
            "code": "no_result",
            "message": f"No result recorded for {match_id}",
        })
    save_state(state, DEFAULT_STATE_PATH)
    return _clean_json_value({
        "status": "ok",
        "match_id": match_id,
        "cleared": True,
    })


def reset_wc_tournament() -> dict:
    """Reset tournament state to fresh (no results)."""
    from scoutfootball.worldcup.tournament import (
        DEFAULT_STATE_PATH,
        init_state,
        save_state,
        tournament_summary,
    )

    state = init_state()
    save_state(state, DEFAULT_STATE_PATH)
    return _clean_json_value({
        "status": "ok",
        "reset": True,
        "summary": tournament_summary(state),
    })


def get_wc_knockout_bracket() -> dict:
    """Return the current knockout bracket state."""
    from scoutfootball.worldcup.tournament import get_knockout_overview

    state = _wc_tournament_state()
    overview = get_knockout_overview(state)
    overview["status"] = "ok"
    return _clean_json_value(overview)


def get_wc_knockout_match_briefing(match_id: str) -> dict[str, Any]:
    """Return a source-bounded briefing for a populated knockout matchup.

    The bracket state determines whether a fixture is known.  Placeholder
    winner slots stay explicitly unavailable instead of receiving a synthetic
    briefing or a predicted opponent.
    """
    state = _wc_tournament_state()
    if not state.knockout or not state.knockout.get("matches"):
        return _clean_json_value({
            "schema": "scoutfootball.world-cup-knockout-match-briefing",
            "version": "1.0.0",
            "status": "not_generated",
            "match_id": match_id,
            "limitations": ["No local knockout bracket has been generated."],
        })
    match = state.knockout_match_by_id(match_id)
    if not match:
        return _clean_json_value({
            "schema": "scoutfootball.world-cup-knockout-match-briefing",
            "version": "1.0.0",
            "status": "not_found",
            "match_id": match_id,
            "limitations": ["The requested match ID is not in the local knockout bracket."],
        })
    context = {
        "match_id": match.get("match_id"),
        "round": match.get("round"),
        "round_label": match.get("round_label"),
        "position": match.get("position"),
        "bracket_provisional": bool(state.knockout.get("provisional", True)),
        "match_status": match.get("status"),
    }
    if not match.get("home") or not match.get("away"):
        return _clean_json_value({
            "schema": "scoutfootball.world-cup-knockout-match-briefing",
            "version": "1.0.0",
            "status": "not_ready",
            "knockout_context": context,
            "fixture": {"home_team": match.get("home"), "away_team": match.get("away")},
            "limitations": [
                "This knockout slot has an unresolved participant; no opponent or "
                "briefing is inferred.",
            ],
        })
    briefing = get_world_cup_match_briefing(match["home"], match["away"])
    if briefing.get("error"):
        return _clean_json_value({
            "schema": "scoutfootball.world-cup-knockout-match-briefing",
            "version": "1.0.0",
            "status": "briefing_unavailable",
            "knockout_context": context,
            "fixture": {"home_team": match["home"], "away_team": match["away"]},
            "limitations": [
                "The local match briefing was unavailable for this populated bracket fixture.",
            ],
        })
    briefing["knockout_context"] = context
    briefing["knockout_context"]["source"] = "local application tournament state"
    briefing["limitations"] = [
        *briefing.get("limitations", []),
        "Knockout placement reflects the local bracket state and is not an official "
        "fixture confirmation.",
    ]
    return _clean_json_value(briefing)


def _capture_wc_knockout_prediction_snapshot(state: Any, match_id: str) -> dict[str, Any] | None:
    """Capture the live matchup projection before a local result is recorded.

    This deliberately uses the knockout Bradley-Terry projection, not the
    post-result projection that marks a completed fixture as probability 1.0.
    The snapshot is optional: unavailable squad-strength artifacts must not
    prevent a user from recording a local bracket result.
    """
    from scoutfootball.worldcup.data import project_knockout_probabilities
    from scoutfootball.worldcup.tournament import get_knockout_overview

    try:
        overview = get_knockout_overview(state)
        _squads, strengths = _get_wc_enriched_squads()
        if not overview.get("generated") or not strengths:
            return None
        projection = project_knockout_probabilities(
            overview, strengths, num_simulations=0
        )
        match_probability = next(
            (
                item
                for item in projection.get("match_probabilities", [])
                if item.get("match_id") == match_id
            ),
            None,
        )
        if not match_probability:
            return None
        home = match_probability.get("home")
        away = match_probability.get("away")
        home_probability = match_probability.get("home_win_probability")
        away_probability = match_probability.get("away_win_probability")
        if not home or not away or home_probability is None or away_probability is None:
            return None
        return {
            "schema": "scoutfootball.world-cup-knockout-prediction-snapshot",
            "version": "1.0.0",
            "captured_at": datetime.now(UTC).isoformat(),
            "fixture": {"home_team": home, "away_team": away},
            "prediction": {
                "home_win_probability": home_probability,
                "away_win_probability": away_probability,
                "model_type": "bradley_terry_strength",
                "model_version": "wc-knockout-1.0",
                "home_strength": strengths.get(home, 0.2),
                "away_strength": strengths.get(away, 0.2),
            },
            "source": "pre-recording local knockout bracket projection",
            "limitations": [
                "This is a locally captured pre-recording model snapshot, not an "
                "official fixture or result feed.",
                "The simplified strength model does not include live availability, "
                "tactics, form, or market odds.",
            ],
        }
    except Exception:
        return None


def _build_wc_knockout_match_review(state: Any, match_id: str) -> dict[str, Any]:
    """Compare a locally recorded result with its captured pre-result snapshot.

    It is intentionally a one-fixture comparison, not a claim about model
    calibration or predictive quality. Older and non-API bracket entries can
    have a completed result without a snapshot and remain explicitly unknown.
    """
    base = {
        "schema": "scoutfootball.world-cup-knockout-result-review",
        "version": "1.0.0",
        "match_id": match_id,
        "recording_scope": "local application tournament state",
    }
    if not state.knockout or not state.knockout.get("matches"):
        return _clean_json_value({
            **base,
            "status": "not_generated",
            "limitations": ["No local knockout bracket has been generated."],
        })
    match = state.knockout_match_by_id(match_id)
    if not match:
        return _clean_json_value({
            **base,
            "status": "not_found",
            "limitations": ["The requested match ID is not in the local knockout bracket."],
        })
    fixture = {"home_team": match.get("home"), "away_team": match.get("away")}
    outcome = {
        "home_goals": match.get("home_goals"),
        "away_goals": match.get("away_goals"),
        "recorded_winner": match.get("winner"),
        "decided_by": match.get("decided_by"),
    }
    if not match.get("winner"):
        return _clean_json_value({
            **base,
            "status": "not_completed",
            "fixture": fixture,
            "recorded_outcome": outcome,
            "limitations": ["A local result must be recorded before a review is available."],
        })
    snapshot = match.get("prediction_snapshot")
    if not isinstance(snapshot, dict):
        return _clean_json_value({
            **base,
            "status": "snapshot_not_recorded",
            "fixture": fixture,
            "recorded_outcome": outcome,
            "limitations": [
                "This local result has no pre-recording prediction snapshot, so no "
                "retrospective model comparison is inferred.",
            ],
        })
    prediction = snapshot.get("prediction")
    if not isinstance(prediction, dict):
        return _clean_json_value({
            **base,
            "status": "snapshot_unusable",
            "fixture": fixture,
            "recorded_outcome": outcome,
            "limitations": [
                "The stored pre-recording snapshot has no usable matchup probabilities."
            ],
        })
    home_probability = prediction.get("home_win_probability")
    away_probability = prediction.get("away_win_probability")
    home = fixture["home_team"]
    away = fixture["away_team"]
    if not isinstance(home_probability, (int, float)) or not isinstance(
        away_probability, (int, float)
    ):
        return _clean_json_value({
            **base,
            "status": "snapshot_unusable",
            "fixture": fixture,
            "recorded_outcome": outcome,
            "limitations": [
                "The stored pre-recording snapshot has invalid matchup probabilities."
            ],
        })
    if home_probability > away_probability:
        predicted_winner = home
    elif away_probability > home_probability:
        predicted_winner = away
    else:
        predicted_winner = None
    recorded_winner = outcome["recorded_winner"]
    result_label = (
        "no_directional_call" if predicted_winner is None
        else "matched_direction" if predicted_winner == recorded_winner
        else "recorded_upset"
    )
    recorded_probability = home_probability if recorded_winner == home else away_probability
    return _clean_json_value({
        **base,
        "status": "ok",
        "fixture": fixture,
        "recorded_outcome": outcome,
        "prediction_snapshot": snapshot,
        "comparison": {
            "predicted_winner": predicted_winner,
            "recorded_winner": recorded_winner,
            "recorded_winner_probability": recorded_probability,
            "directional_result": result_label,
        },
        "limitations": [
            "This compares one locally recorded result with a captured pre-recording "
            "snapshot; it is not a calibration, accuracy, or official-result assessment.",
            "Clearing the local result also removes this snapshot to avoid retaining "
            "a stale matchup comparison.",
        ],
    })


def get_wc_knockout_match_review(match_id: str) -> dict[str, Any]:
    """Return one local knockout result review."""
    return _build_wc_knockout_match_review(_wc_tournament_state(), match_id)


def get_wc_knockout_review_ledger() -> dict[str, Any]:
    """Return a compact, local-only summary of recorded knockout reviews.

    This aggregates only completed locally recorded bracket entries. It does
    not fill missing snapshots, and the directional counts are explicitly not
    calibration or accuracy metrics.
    """
    state = _wc_tournament_state()
    base = {
        "schema": "scoutfootball.world-cup-knockout-review-ledger",
        "version": "1.0.0",
        "recording_scope": "local application tournament state",
    }
    if not state.knockout or not state.knockout.get("matches"):
        return _clean_json_value({
            **base,
            "status": "not_generated",
            "reviews": [],
            "summary": {"completed_matches": 0, "reviews_with_snapshot": 0},
            "limitations": ["No local knockout bracket has been generated."],
        })
    completed = [
        match for match in state.knockout["matches"] if match.get("winner")
    ]
    reviews = [
        _build_wc_knockout_match_review(state, match["match_id"])
        for match in completed
    ]
    direction_counts = {
        label: sum(
            review.get("comparison", {}).get("directional_result") == label
            for review in reviews
        )
        for label in ("matched_direction", "recorded_upset", "no_directional_call")
    }
    return _clean_json_value({
        **base,
        "status": "ok",
        "reviews": reviews,
        "summary": {
            "completed_matches": len(completed),
            "reviews_with_snapshot": sum(review.get("status") == "ok" for review in reviews),
            "snapshots_missing": sum(
                review.get("status") == "snapshot_not_recorded" for review in reviews
            ),
            **direction_counts,
        },
        "limitations": [
            "This is a local-result audit summary, not an official tournament feed "
            "or a model calibration report.",
            "Completed entries without a captured pre-recording snapshot remain "
            "missing rather than being inferred after the result.",
        ],
    })


def generate_wc_knockout_bracket() -> dict:
    """Generate the knockout bracket from current group standings and persist."""
    from scoutfootball.worldcup.tournament import (
        DEFAULT_STATE_PATH,
        generate_knockout_bracket,
        save_state,
    )

    state = _wc_tournament_state()
    try:
        ko = generate_knockout_bracket(state)
    except ValueError as exc:
        return _clean_json_value({"status": "error", "message": str(exc)})
    state.knockout = ko
    save_state(state, DEFAULT_STATE_PATH)
    return _clean_json_value({
        "status": "ok",
        "generated": True,
        "provisional": ko["provisional"],
        "total_matches": len(ko["matches"]),
        "saved_to": DEFAULT_STATE_PATH,
    })


def apply_wc_knockout_result(
    match_id: str,
    home_goals: int,
    away_goals: int,
    penalties_winner: str | None = None,
) -> dict:
    """Record a knockout match result and auto-advance the winner."""
    from scoutfootball.worldcup.tournament import (
        DEFAULT_STATE_PATH,
        apply_knockout_result,
        save_state,
    )

    state = _wc_tournament_state()
    prediction_snapshot = _capture_wc_knockout_prediction_snapshot(state, match_id)
    try:
        apply_knockout_result(
            state,
            match_id,
            home_goals,
            away_goals,
            penalties_winner=penalties_winner,
        )
    except ValueError as exc:
        return _clean_json_value({"status": "error", "message": str(exc)})

    match = state.knockout_match_by_id(match_id)
    if prediction_snapshot is not None:
        match["prediction_snapshot"] = prediction_snapshot
    save_state(state, DEFAULT_STATE_PATH)
    return _clean_json_value({
        "status": "ok",
        "match_id": match_id,
        "home": match["home"],
        "away": match["away"],
        "home_goals": home_goals,
        "away_goals": away_goals,
        "winner": match["winner"],
        "decided_by": match.get("decided_by"),
        "prediction_snapshot_recorded": prediction_snapshot is not None,
        "saved_to": DEFAULT_STATE_PATH,
    })


def clear_wc_knockout_result(match_id: str) -> dict:
    """Clear a knockout match result (cascades to downstream matches)."""
    from scoutfootball.worldcup.tournament import (
        DEFAULT_STATE_PATH,
        clear_knockout_result,
        save_state,
    )

    state = _wc_tournament_state()
    try:
        clear_knockout_result(state, match_id)
    except ValueError as exc:
        return _clean_json_value({"status": "error", "message": str(exc)})
    save_state(state, DEFAULT_STATE_PATH)
    return _clean_json_value({
        "status": "ok",
        "match_id": match_id,
        "cleared": True,
        "saved_to": DEFAULT_STATE_PATH,
    })


def get_wc_knockout_probabilities() -> dict:
    """Project per-matchup win probabilities for the live knockout bracket.

    Uses the Bradley-Terry strength model to compute home/away win
    probabilities for each match with both teams filled. When all R32
    matches have teams, also runs Monte Carlo tournament win odds
    respecting already-completed matches.
    """
    from scoutfootball.worldcup.data import project_knockout_probabilities
    from scoutfootball.worldcup.tournament import get_knockout_overview

    state = _wc_tournament_state()
    overview = get_knockout_overview(state)
    if not overview.get("generated"):
        return _clean_json_value({
            "status": "error",
            "message": (
                "No knockout bracket generated. "
                "Call /world-cup/tournament/knockout/generate first."
            ),
        })

    enriched_squads, strengths = _get_wc_enriched_squads()
    if not enriched_squads:
        return _clean_json_value({
            "status": "error",
            "message": "World Cup squad data not available for strength model.",
        })

    result = project_knockout_probabilities(overview, strengths)
    return _clean_json_value(result)


def get_wc_qualification_impact(group: str) -> dict:
    """Return the local standings impact for a selected World Cup group."""
    from scoutfootball.worldcup.tournament import qualification_impact

    return _clean_json_value(qualification_impact(_wc_tournament_state(), group))


def get_wc_knockout_scenarios(team: str, num_simulations: int = 5000) -> dict:
    """Return knockout advancement scenarios for a specific team.

    Shows the team's current championship probability and what-if analysis
    for each remaining knockout stage (win/lose championship impact).
    """
    from scoutfootball.worldcup.data import compute_knockout_scenarios
    from scoutfootball.worldcup.tournament import get_knockout_overview

    state = _wc_tournament_state()
    overview = get_knockout_overview(state)
    if not overview.get("generated"):
        return _clean_json_value({
            "status": "error",
            "message": (
                "No knockout bracket generated. "
                "Call /world-cup/tournament/knockout/generate first."
            ),
        })

    enriched_squads, strengths = _get_wc_enriched_squads()
    if not enriched_squads:
        return _clean_json_value({
            "status": "error",
            "message": "World Cup squad data not available for strength model.",
        })

    result = compute_knockout_scenarios(
        overview, strengths, team, num_simulations=num_simulations
    )
    return _clean_json_value(result)


def get_wc_group_stage_simulation(
    mode: str = "random", num_simulations: int = 1000
) -> dict:
    """Simulate remaining group-stage matches and report advancement odds.

    *mode* is ``"random"`` (uniform) or ``"strength"`` (Bradley-Terry-biased).
    """
    from scoutfootball.worldcup.data import simulate_group_stage

    state = _wc_tournament_state()

    strengths: dict[str, float] | None = None
    if mode == "strength":
        enriched_squads, strengths = _get_wc_enriched_squads()
        if not enriched_squads:
            return _clean_json_value({
                "status": "error",
                "message": "World Cup squad data not available for strength model.",
            })

    result = simulate_group_stage(
        state,
        team_strengths=strengths,
        num_simulations=num_simulations,
        mode=mode,
    )
    return _clean_json_value(result)


def export_wc_tournament_state() -> dict:
    """Export the full tournament state as a shareable JSON string.

    Returns the complete state (matches + results + knockout) encoded as
    a base64-URL-safe string that can be shared via URL or saved to a file.
    The importing side uses ``import_wc_tournament_state`` to reconstruct.
    """
    import base64
    import json

    from scoutfootball.worldcup.tournament import state_to_dict

    state = _wc_tournament_state()
    state_dict = state_to_dict(state)
    json_bytes = json.dumps(state_dict, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(json_bytes).decode("ascii")
    return _clean_json_value({
        "status": "ok",
        "format": "base64url-json-v1",
        "schema_version": state_dict.get("schema_version", "1.0.0"),
        "state_size": len(json_bytes),
        "encoded": encoded,
        "exported_at": state_dict.get("updated_at", ""),
    })


def _decode_wc_tournament_import(encoded: str) -> tuple[Any | None, dict | None]:
    """Decode an imported tournament state without writing local state."""
    import base64
    import json

    from scoutfootball.worldcup.tournament import (
        state_from_dict,
        validate_tournament_state_integrity,
    )

    try:
        # Add padding if missing
        padded = encoded + "=" * (4 - len(encoded) % 4) if len(encoded) % 4 else encoded
        json_bytes = base64.urlsafe_b64decode(padded)
        state_dict = json.loads(json_bytes.decode("utf-8"))
    except Exception as exc:
        return None, _clean_json_value({
            "status": "error",
            "code": "decode_failed",
            "message": f"Failed to decode state: {exc}",
        })

    try:
        state = state_from_dict(state_dict, validate_integrity=False)
    except ValueError as exc:
        return None, _clean_json_value({
            "status": "error",
            "code": "invalid_state",
            "message": str(exc),
        })

    integrity_errors = validate_tournament_state_integrity(state)
    if integrity_errors:
        return None, _clean_json_value({
            "status": "error",
            "code": "integrity_failed",
            "message": "Tournament state failed integrity validation.",
            "integrity_errors": integrity_errors,
            "recording_scope": "local application tournament state",
        })

    return state, None


def _wc_import_state_counts(state: Any) -> dict[str, int]:
    """Return bounded counts used by import preview and confirmation UI."""
    knockout_matches = (state.knockout or {}).get("matches", [])
    return {
        "group_results": len(state.results),
        "knockout_matches_completed": sum(
            bool(match.get("winner")) for match in knockout_matches
        ),
        "knockout_prediction_snapshots": sum(
            isinstance(match.get("prediction_snapshot"), dict)
            for match in knockout_matches
        ),
    }


def _wc_tournament_state_fingerprint(state: Any) -> str:
    """Return a stable local-state version token for import confirmation."""
    import hashlib
    import json

    from scoutfootball.worldcup.tournament import state_to_dict

    payload = json.dumps(
        state_to_dict(state), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _wc_import_result_change_ledger(current: Any, incoming: Any, *, limit: int = 20) -> dict:
    """Describe bounded group-result replacement effects in schedule order."""
    changes: list[dict] = []
    for match in current.matches:
        match_id = match["match_id"]
        before = current.results.get(match_id)
        after = incoming.results.get(match_id)
        if before == after:
            continue
        if before is None:
            change_type = "added"
        elif after is None:
            change_type = "removed"
        else:
            change_type = "changed"
        changes.append({
            "match_id": match_id,
            "group": match.get("group"),
            "home": match.get("home"),
            "away": match.get("away"),
            "change_type": change_type,
            "current_result": before,
            "incoming_result": after,
        })
    return {
        "items": changes[:limit],
        "total": len(changes),
        "truncated": len(changes) > limit,
    }


def _wc_import_knockout_change_ledger(current: Any, incoming: Any, *, limit: int = 20) -> dict:
    """Describe bounded knockout record effects without interpreting them as facts."""
    def indexed_matches(state: Any) -> dict[str, dict]:
        matches = (state.knockout or {}).get("matches", [])
        return {
            match["match_id"]: match
            for match in matches
            if isinstance(match, dict) and isinstance(match.get("match_id"), str)
        }

    current_matches = indexed_matches(current)
    incoming_matches = indexed_matches(incoming)
    changes: list[dict] = []
    for match_id in sorted(set(current_matches) | set(incoming_matches)):
        before = current_matches.get(match_id)
        after = incoming_matches.get(match_id)
        if before == after:
            continue
        if before is None:
            change_type = "added"
        elif after is None:
            change_type = "removed"
        else:
            change_type = "changed"
        reference = after or before or {}
        changes.append({
            "match_id": match_id,
            "round": reference.get("round"),
            "home": reference.get("home"),
            "away": reference.get("away"),
            "change_type": change_type,
            "current_completed": bool((before or {}).get("winner")),
            "incoming_completed": bool((after or {}).get("winner")),
            "current_snapshot_recorded": isinstance(
                (before or {}).get("prediction_snapshot"), dict
            ),
            "incoming_snapshot_recorded": isinstance(
                (after or {}).get("prediction_snapshot"), dict
            ),
        })
    return {
        "items": changes[:limit],
        "total": len(changes),
        "truncated": len(changes) > limit,
    }


def preview_wc_tournament_import(encoded: str) -> dict:
    """Validate an import and report bounded local-state replacement risks."""
    incoming, error = _decode_wc_tournament_import(encoded)
    if error:
        return error
    current = _wc_tournament_state()
    current_result_ids = set(current.results)
    incoming_result_ids = set(incoming.results)
    changed_results = sum(
        current.results.get(match_id) != incoming.results.get(match_id)
        for match_id in current_result_ids & incoming_result_ids
    )
    current_counts = _wc_import_state_counts(current)
    incoming_counts = _wc_import_state_counts(incoming)
    result_change_ledger = _wc_import_result_change_ledger(current, incoming)
    knockout_change_ledger = _wc_import_knockout_change_ledger(current, incoming)
    return _clean_json_value({
        "schema": "scoutfootball.world-cup-tournament-import-preview",
        "version": "1.0.0",
        "status": "ok",
        "recording_scope": "local application tournament state",
        "current_state_fingerprint": _wc_tournament_state_fingerprint(current),
        "incoming": {
            "schema_version": incoming.schema_version,
            "matches": len(incoming.matches),
            **incoming_counts,
        },
        "current": {
            "schema_version": current.schema_version,
            "matches": len(current.matches),
            **current_counts,
        },
        "differences": {
            "group_results_added": len(incoming_result_ids - current_result_ids),
            "group_results_removed": len(current_result_ids - incoming_result_ids),
            "group_results_changed": changed_results,
            "knockout_snapshots_removed": max(
                0,
                current_counts["knockout_prediction_snapshots"]
                - incoming_counts["knockout_prediction_snapshots"],
            ),
        },
        "result_changes": result_change_ledger,
        "knockout_changes": knockout_change_ledger,
        "requires_confirmation": True,
        "limitations": [
            "Preview validates the encoded local tournament state but does not write it.",
            "Confirming import replaces the entire local application tournament "
            "state; it is not a merge or official result synchronization.",
        ],
    })


def import_wc_tournament_state(
    encoded: str, *, expected_current_fingerprint: str | None = None
) -> dict:
    """Import a shared tournament state and persist it after UI confirmation.

    Programmatic callers remain supported; the application UI first calls the
    preview endpoint and requires an explicit confirmation before this write.
    """
    from scoutfootball.worldcup.tournament import DEFAULT_STATE_PATH, save_state

    state, error = _decode_wc_tournament_import(encoded)
    if error:
        return error

    if expected_current_fingerprint is not None:
        current_fingerprint = _wc_tournament_state_fingerprint(_wc_tournament_state())
        if current_fingerprint != expected_current_fingerprint:
            return _clean_json_value({
                "status": "error",
                "code": "stale_preview",
                "message": (
                    "Local tournament state changed after preview; "
                    "preview again before importing."
                ),
                "recording_scope": "local application tournament state",
            })

    save_state(state, DEFAULT_STATE_PATH)
    return _clean_json_value({
        "status": "ok",
        "imported": True,
        "schema_version": state.schema_version,
        "matches": len(state.matches),
        "results": len(state.results),
        "has_knockout": bool(state.knockout),
        "saved_to": str(DEFAULT_STATE_PATH),
    })
