"""Unified data loader: reads local Parquet when available, falls back to demo data."""
from __future__ import annotations

import logging
from functools import lru_cache

import pandas as pd

from scoutlab.config import PlatformSettings

logger = logging.getLogger(__name__)


def _settings() -> PlatformSettings:
    return PlatformSettings.from_root()


def _parquet_path(relative_path: str):
    return _settings().data_root / relative_path


def _parquet_exists(relative_path: str) -> bool:
    path = _parquet_path(relative_path)
    return path.exists() and path.suffix == ".parquet"


def _mark_synthetic(df: pd.DataFrame) -> pd.DataFrame:
    """Add is_synthetic=True column to a demo DataFrame."""
    df = df.copy()
    df["is_synthetic"] = True
    return df


def load_player_match() -> pd.DataFrame:
    rel = "gold/feature_store/player_match.parquet"
    if _parquet_exists(rel):
        return pd.read_parquet(_parquet_path(rel))
    logger.warning("player_match.parquet not found — falling back to synthetic demo data")
    from scoutlab.app.demo_data import generate_player_match

    return _mark_synthetic(generate_player_match())


def load_team_match() -> pd.DataFrame:
    rel = "gold/feature_store/team_match.parquet"
    if _parquet_exists(rel):
        return pd.read_parquet(_parquet_path(rel))
    logger.warning("team_match.parquet not found — falling back to synthetic demo data")
    from scoutlab.app.demo_data import generate_team_match

    return _mark_synthetic(generate_team_match())


@lru_cache(maxsize=2)
def load_player_rolling() -> pd.DataFrame:
    rel = "gold/feature_store/player_rolling.parquet"
    if _parquet_exists(rel):
        return pd.read_parquet(_parquet_path(rel))
    logger.warning("player_rolling.parquet not found — falling back to synthetic demo data")
    from scoutlab.app.demo_data import generate_player_match, generate_player_rolling

    return _mark_synthetic(generate_player_rolling(generate_player_match()))


@lru_cache(maxsize=2)
def load_team_rolling() -> pd.DataFrame:
    rel = "gold/feature_store/team_rolling.parquet"
    if _parquet_exists(rel):
        return pd.read_parquet(_parquet_path(rel))
    logger.warning("team_rolling.parquet not found — falling back to synthetic demo data")
    from scoutlab.app.demo_data import generate_team_match, generate_team_rolling

    return _mark_synthetic(generate_team_rolling(generate_team_match()))


def load_oof_predictions() -> pd.DataFrame:
    rel = "models/oof_predictions/value_fairness_oof.parquet"
    if _parquet_exists(rel):
        return pd.read_parquet(_parquet_path(rel))
    logger.warning("value_fairness_oof.parquet not found — falling back to synthetic demo data")
    from scoutlab.app.demo_data import generate_oof_predictions

    return _mark_synthetic(generate_oof_predictions())


def load_score_prediction(home_team: str | None = None, away_team: str | None = None):
    if _parquet_exists("models/artifacts/poisson_baseline_results.parquet"):
        from scoutlab.models.match_prediction import (
            fit_independent_poisson,
            predict_match,
        )

        team_match = load_team_match()
        model = fit_independent_poisson(team_match)
        team_id_series = team_match.get("team_id", pd.Series(dtype="string"))
        team_ids = [
            team_id
            for team_id in team_id_series.dropna().astype(str).unique()
        ]
        if len(team_ids) >= 2:
            resolved_home = _resolve_team_id(home_team, team_ids) if home_team else team_ids[0]
            resolved_away = _resolve_team_id(away_team, team_ids) if away_team else team_ids[1]
            if resolved_home is None:
                raise ValueError(
                    f"Home team '{home_team}' not found. "
                    f"Available: {', '.join(sorted(team_ids)[:15])}..."
                )
            if resolved_away is None:
                raise ValueError(
                    f"Away team '{away_team}' not found. "
                    f"Available: {', '.join(sorted(team_ids)[:15])}..."
                )
            return predict_match(model, resolved_home, resolved_away)
    logger.warning("Poisson artifacts not found — falling back to synthetic demo prediction")
    from scoutlab.app.demo_data import generate_score_matrix

    return generate_score_matrix()


def _resolve_team_id(name: str, team_ids: list[str]) -> str | None:
    """Resolve a team name to a team_id with case-insensitive fallback."""
    # Exact match
    if name in team_ids:
        return name
    # Case-insensitive match
    lower_map = {tid.lower(): tid for tid in team_ids}
    if name.lower() in lower_map:
        return lower_map[name.lower()]
    # Substring containment (e.g., "Man" matches "Man City" or "Man United")
    candidates = [tid for tid in team_ids if name.lower() in tid.lower()]
    if len(candidates) == 1:
        return candidates[0]
    return None


def data_source_label() -> str:
    """Return a granular label describing the data source state."""
    has_player_match = _parquet_exists("gold/feature_store/player_match.parquet")
    has_oof = _parquet_exists("models/oof_predictions/value_fairness_oof.parquet")
    has_poisson = _parquet_exists("models/artifacts/poisson_baseline_results.parquet")

    if not has_player_match:
        return "Demo data (synthetic)"

    # Check granularity of player_match
    try:
        pm = pd.read_parquet(_parquet_path("gold/feature_store/player_match.parquet"))
        if "data_granularity" in pm.columns:
            match_count = (pm["data_granularity"] == "match").sum()
            proxy_count = (pm["data_granularity"] == "season_proxy").sum()
            if match_count > 0 and proxy_count > 0:
                detail = f"real matches ({match_count}) + season proxy ({proxy_count})"
            elif match_count > 0:
                detail = "real match-level data"
            else:
                detail = "season proxy only (FBref)"
        else:
            detail = "local Parquet"
    except Exception:
        detail = "local Parquet"

    parts = [detail]
    if has_oof:
        parts.append("value_fairness OOF")
    if has_poisson:
        parts.append("Poisson model")
    return " | ".join(parts)
