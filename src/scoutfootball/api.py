"""FastAPI read-only service layer for ScoutFootball."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scoutfootball.app.data_loader import (
    data_source_label,
    load_league_metrics,
    load_model_meta,
    load_oof_predictions,
    load_player_match,
    load_player_ratings,
    load_player_value_metrics,
    load_score_prediction,
    load_team_match,
)
from scoutfootball.evaluation.scouting_queue import build_scouting_queues


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


def _artifact_file_info(path: Path, label: str, *, rows: int | None = None) -> dict[str, Any]:
    return {
        "label": label,
        "path": str(path),
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
    df = load_player_match()
    if "player_name" not in df.columns:
        return PlayerListResponse(player_count=0, players=[])
    names = sorted(df["player_name"].dropna().unique().tolist())
    return PlayerListResponse(player_count=len(names), players=names[:100])


def list_teams() -> list[str]:
    """Return team names from ratings data (covers all 5 leagues)."""
    df = load_player_ratings()
    if "team" in df.columns:
        return sorted(df["team"].dropna().unique().tolist())
    # Fallback to team_match
    tm = load_team_match()
    if "team_name" in tm.columns:
        return sorted(tm["team_name"].dropna().unique().tolist())[:200]
    return []


def get_match_prediction(home_team: str, away_team: str) -> dict:
    try:
        prediction = load_score_prediction(home_team, away_team)
    except Exception as exc:
        return {"error": str(exc)}
    if isinstance(prediction, dict):
        return prediction
    return {
        "home_team": home_team,
        "away_team": away_team,
        "home_lambda": prediction.home_lambda,
        "away_lambda": prediction.away_lambda,
        "home_win": prediction.summary.home_win,
        "draw": prediction.summary.draw,
        "away_win": prediction.summary.away_win,
        "over_2_5": prediction.summary.over_2_5,
        "btts_yes": prediction.summary.btts_yes,
    }


def get_value_summary() -> dict:
    oof = load_oof_predictions()
    if oof.empty:
        return {"status": "no_data", "players": [], "metrics": {}}

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
            import pandas as pd

            results_df = pd.read_parquet(results_path)
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
        "status": "ok",
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


def get_prediction_summary() -> dict[str, Any]:
    """Return baseline prediction artifact metadata."""
    artifact_path = (
        _settings().data_root
        / "models"
        / "artifacts"
        / "poisson_baseline_results.parquet"
    )
    if not artifact_path.exists():
        return {"status": "no_data"}

    import pandas as pd

    try:
        frame = pd.read_parquet(artifact_path)
    except Exception:
        return {"status": "no_data"}
    if frame.empty:
        return {"status": "no_data"}
    row = frame.iloc[0].to_dict()
    row["status"] = "ok"
    return _clean_json_value(row)


def get_action_value_summary(limit: int = 20) -> dict[str, Any]:
    frame = load_player_value_metrics()
    if frame.empty:
        return {"status": "no_data", "count": 0, "players": []}

    working = frame.copy()
    if "composite_score" in working.columns:
        working = working.sort_values("composite_score", ascending=False)

    summary = {
        "status": "ok",
        "count": len(working),
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
        "players": _clean_json_value(working.head(limit).to_dict(orient="records")),
    }
    return summary


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
            import pandas as pd
            events_count = len(pd.read_parquet(events_path))
        except Exception:
            events_count = 0

    # Data health flags
    has_oof = not oof.empty
    has_truth = False
    truth_rows = 0
    truth_path = settings.data_root / "gold" / "feature_store" / "player_truth_labels.parquet"
    if truth_path.exists():
        try:
            import pandas as pd
            truth_df = pd.read_parquet(truth_path)
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
        ),
        _artifact_file_info(
            settings.data_root / "gold" / "feature_store" / "team_match.parquet",
            "team_match",
            rows=len(team_match),
        ),
        _artifact_file_info(
            settings.data_root / "gold" / "feature_store" / "player_ratings_optimized.parquet",
            "player_ratings_optimized",
            rows=len(ratings),
        ),
        _artifact_file_info(events_path, "events_all", rows=events_count),
        _artifact_file_info(
            settings.data_root / "models" / "oof_predictions" / "value_fairness_oof.parquet",
            "value_fairness_oof",
            rows=len(oof),
        ),
        _artifact_file_info(truth_path, "player_truth_labels", rows=truth_rows),
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
        },
    })


def get_review_queue(limit: int = 200) -> dict:
    """Return low-confidence players from ratings data as a review queue."""
    df = load_player_ratings()
    if df.empty:
        return {"count": 0, "players": []}

    queues = build_scouting_queues(
        df,
        run_id=_latest_run_id(),
        reports_root=_settings().data_root / "reports",
    )
    return _queue_payload(queues.review_queue, limit=limit)


def get_watchlist(limit: int = 100) -> dict:
    df = load_player_ratings()
    if df.empty:
        return {"count": 0, "players": []}
    queues = build_scouting_queues(
        df,
        run_id=_latest_run_id(),
        reports_root=_settings().data_root / "reports",
    )
    return _queue_payload(queues.watchlist, limit=limit)


def get_shortlist(limit: int = 100) -> dict:
    df = load_player_ratings()
    if df.empty:
        return {"count": 0, "players": []}
    queues = build_scouting_queues(
        df,
        run_id=_latest_run_id(),
        reports_root=_settings().data_root / "reports",
    )
    return _queue_payload(queues.shortlist, limit=limit)


def get_model_runs() -> dict:
    """Return model run registry from local artifacts."""
    settings = _settings()
    runs = []

    # Check data/models/runs/ directory
    runs_dir = settings.data_root / "models" / "runs"
    if runs_dir.exists():
        for run_dir in sorted(runs_dir.iterdir(), reverse=True):
            meta_path = run_dir / "meta.json"
            if meta_path.exists():
                meta = _read_json(meta_path)
                meta["run_id"] = run_dir.name
                meta["updated_at"] = meta_path.stat().st_mtime
                runs.append(meta)

    # Fallback: read optimized_params_meta.json
    if not runs:
        meta_path = settings.data_root / "gold" / "feature_store" / "optimized_params_meta.json"
        if meta_path.exists():
            meta = _read_json(meta_path)
            meta["run_id"] = "latest"
            meta["updated_at"] = meta_path.stat().st_mtime
            runs.append(meta)

    return _clean_json_value({"runs": runs, "count": len(runs)})


def get_player_profile(player_name: str, season: str | None = None) -> dict:
    """Return detailed player profile with radar dimensions."""
    import pandas as pd

    df = load_player_ratings()

    # Alias sub_position → position_group for frontend compatibility
    if "sub_position" in df.columns and "position_group" not in df.columns:
        df["position_group"] = df["sub_position"]

    mask = df["player"] == player_name
    if season:
        mask = mask & (df["season"] == season)
    rows = df[mask]
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

    return _clean_json_value({
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
        "npg_p90": round(npg, 3),
        "assists_p90": round(assists, 3),
        "defense_composite": round(defense, 2) if defense == defense else None,
        "possession_composite": round(possession, 2) if possession == possession else None,
        "radar": radar,
        "seasons": seasons,
    })
