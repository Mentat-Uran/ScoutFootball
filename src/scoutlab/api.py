"""FastAPI service layer draft for ScoutLab."""

from __future__ import annotations

from dataclasses import dataclass

from scoutlab.app.data_loader import (
    data_source_label,
    load_league_metrics,
    load_model_meta,
    load_oof_predictions,
    load_player_match,
    load_player_ratings,
    load_score_prediction,
    load_team_match,
)


@dataclass(frozen=True)
class HealthResponse:
    status: str
    data_source: str
    version: str


@dataclass(frozen=True)
class PlayerListResponse:
    player_count: int
    players: list[str]


def health_check() -> HealthResponse:
    from scoutlab import __version__

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
    except ValueError as exc:
        return {"error": str(exc)}
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
        return {"status": "no_data", "players": []}

    # Filter out records with suspiciously low market values (Transfermarkt placeholder)
    # Values <= 200k are almost certainly data errors, not real valuations
    if "actual_market_value" in oof.columns:
        oof = oof[oof["actual_market_value"] > 200000].copy()

    # Build player-level value data
    import math
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
        player_data.append(record)

    return {
        "status": "ok",
        "sample_count": len(oof),
        "fairness_distribution": oof["fairness_label"].value_counts().to_dict()
        if "fairness_label" in oof.columns
        else {},
        "mean_residual_log": float(oof["residual_log"].mean())
        if "residual_log" in oof.columns
        else None,
        "players": player_data,
    }


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
    import math

    for record in players:
        for key, value in record.items():
            if isinstance(value, float) and math.isnan(value):
                record[key] = None

    return {"count": len(players), "players": players}


def get_ratings_meta() -> dict:
    """Return model metadata and league metrics."""
    meta_df = load_model_meta()
    league_df = load_league_metrics()

    meta = {}
    if not meta_df.empty:
        row = meta_df.iloc[0].to_dict()
        for key, value in row.items():
            if isinstance(value, float) and value != value:
                row[key] = None
        meta = row

    leagues = league_df.to_dict(orient="records") if not league_df.empty else []
    for record in leagues:
        for key, value in record.items():
            if isinstance(value, float) and value != value:
                record[key] = None

    return {"model_meta": meta, "league_metrics": leagues}


def get_artifacts_summary() -> dict:
    """Return artifact counts and data health for the overview page."""
    ratings = load_player_ratings()
    player_match = load_player_match()
    team_match = load_team_match()
    oof = load_oof_predictions()

    # Count events from StatsBomb
    events_count = 0
    from scoutlab.config import PlatformSettings
    settings = PlatformSettings.from_root()
    events_path = settings.data_root / "gold" / "feature_store" / "events_all.parquet"
    if events_path.exists():
        import pandas as pd
        events_count = len(pd.read_parquet(events_path))

    # Data health flags
    has_oof = not oof.empty
    has_truth = False
    truth_path = settings.data_root / "gold" / "feature_store" / "player_truth_labels.parquet"
    if truth_path.exists():
        import pandas as pd
        truth_df = pd.read_parquet(truth_path)
        has_truth = len(truth_df) > 0

    # Player match coverage
    pm_coverage = ""
    if not player_match.empty and "data_granularity" in player_match.columns:
        match_count = (player_match["data_granularity"] == "match").sum()
        proxy_count = (player_match["data_granularity"] == "season_proxy").sum()
        pm_coverage = f"{match_count} real + {proxy_count} season proxy"

    return {
        "player_match_rows": len(player_match),
        "team_match_rows": len(team_match),
        "rating_rows": len(ratings),
        "event_samples": events_count,
        "data_health": {
            "oof_available": has_oof,
            "truth_labels_available": has_truth,
            "player_match_coverage": pm_coverage,
        },
    }


def get_review_queue(limit: int = 200) -> dict:
    """Return low-confidence players from ratings data as a review queue."""
    df = load_player_ratings()
    if df.empty or "confidence_level" not in df.columns:
        return {"count": 0, "players": []}

    # Normalize confidence_level to uppercase
    df["confidence_level"] = df["confidence_level"].str.upper()

    low_conf = df[df["confidence_level"] == "LOW"]
    if low_conf.empty:
        return {"count": 0, "players": []}

    # Sort by optimized_score descending so the most interesting low-conf players appear first
    if "optimized_score" in low_conf.columns:
        low_conf = low_conf.sort_values("optimized_score", ascending=False)

    low_conf = low_conf.head(limit)
    players = low_conf.to_dict(orient="records")

    import math
    for record in players:
        for key, value in record.items():
            if isinstance(value, float) and math.isnan(value):
                record[key] = None

    return {"count": len(players), "players": players}


def get_model_runs() -> dict:
    """Return model run registry from local artifacts."""
    import json

    from scoutlab.config import PlatformSettings

    settings = PlatformSettings.from_root()
    runs = []

    # Check data/models/runs/ directory
    runs_dir = settings.data_root / "models" / "runs"
    if runs_dir.exists():
        for run_dir in sorted(runs_dir.iterdir()):
            meta_path = run_dir / "meta.json"
            if meta_path.exists():
                with open(meta_path) as f:
                    meta = json.load(f)
                meta["run_id"] = run_dir.name
                runs.append(meta)

    # Fallback: read optimized_params_meta.json
    if not runs:
        meta_path = settings.data_root / "gold" / "feature_store" / "optimized_params_meta.json"
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            meta["run_id"] = "latest"
            runs.append(meta)

    return {"runs": runs, "count": len(runs)}


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
    row = rows.loc[rows["optimized_score"].idxmax()]

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

    return {
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
    }
