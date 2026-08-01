"""Build bounded season-proxy player features from local Understat snapshots."""

from __future__ import annotations

import logging

import pandas as pd

from scoutfootball.entities.normalize import normalize_person_name
from scoutfootball.features.player_match import build_player_match_features

UNDERSTAT_COMPETITION_IDS = {
    "EPL": "ENG-Premier League",
    "La_Liga": "ESP-La Liga",
    "Bundesliga": "GER-Bundesliga",
    "Serie_A": "ITA-Serie A",
    "Ligue_1": "FRA-Ligue 1",
}

logger = logging.getLogger(__name__)


def _season_code(value: object) -> str:
    """Convert Understat's ``202324`` style season to ``2324``."""
    text = str(value).strip()
    if len(text) == 6 and text.isdigit():
        return text[2:]
    return ""


def _position_group(value: object) -> str:
    """Map Understat's broad position codes without inventing a sub-position."""
    code = str(value or "").strip().upper()
    if code.startswith("GK"):
        return "GK"
    if code.startswith("D"):
        return "DF"
    if code.startswith("M"):
        return "MF"
    if code.startswith("F"):
        return "FW"
    return "UNK"


def _season_end_date(season_id: object) -> pd.Timestamp:
    text = str(season_id)
    if len(text) == 4 and text.isdigit():
        return pd.Timestamp(year=2000 + int(text[2:]), month=5, day=31)
    return pd.NaT


def build_understat_season_proxy(
    frame: pd.DataFrame,
    *,
    excluded_season_ids: set[str] | None = None,
) -> pd.DataFrame:
    """Convert local Understat aggregate rows into explicit season proxies.

    Only Big Five rows are kept, because those are the competitions with an
    aligned Football-Data team-results history.  ``excluded_season_ids`` lets
    a higher-fidelity source (currently FBref) remain authoritative where the
    two sources overlap.  The output is season-level, not match-level data.
    """
    required = {"id", "player_name", "team_title", "league", "season", "time", "games"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Understat player snapshot missing columns: {', '.join(missing)}")
    if frame.empty:
        return pd.DataFrame()

    excluded = {str(value) for value in (excluded_season_ids or set())}
    work = frame.copy()
    work["season_id"] = work["season"].map(_season_code)
    work["competition_id"] = work["league"].map(UNDERSTAT_COMPETITION_IDS)
    work["minutes_played"] = pd.to_numeric(work["time"], errors="coerce")
    work["matches_played"] = pd.to_numeric(work["games"], errors="coerce")
    work = work[
        work["competition_id"].notna()
        & work["season_id"].ne("")
        & ~work["season_id"].isin(excluded)
        & work["player_name"].notna()
        & work["team_title"].notna()
        & work["minutes_played"].gt(0)
    ].copy()
    if work.empty:
        return pd.DataFrame()

    numeric_columns = {
        "goals": "goals",
        "assists": "assists",
        "shots": "shots",
        "npxg": "npxG",
        "xa": "xA",
    }
    for target, source in numeric_columns.items():
        work[target] = pd.to_numeric(work.get(source), errors="coerce")

    work["player_name"] = work["player_name"].astype("string").str.strip()
    work["team_name"] = work["team_title"].astype("string").str.strip()

    # Understat aggregates season stats across all clubs a player appeared for,
    # joining multi-team rows with commas (e.g. "Hull,West Ham" for a
    # mid-season transfer).  We cannot split minutes/goals per team without
    # per-team breakdowns, so we keep the first club as the primary team and
    # flag multi-team rows.  This prevents comma-polluted team names from
    # corrupting team-level aggregations, team-name matching, and rating
    # feature matrix grouping.
    multi_team_mask = work["team_name"].str.contains(",", na=False)
    if multi_team_mask.any():
        multi_count = int(multi_team_mask.sum())
        first_teams = work.loc[multi_team_mask, "team_name"].str.split(",").str[0]
        work.loc[multi_team_mask, "team_name"] = first_teams
        work["multi_team_season"] = multi_team_mask
        logger.info(
            "Resolved %d multi-team Understat rows (comma-separated team_title) "
            "to first club only; multi_team_season flag set",
            multi_count,
        )
    else:
        work["multi_team_season"] = False

    position = work["position"] if "position" in work.columns else pd.Series("", index=work.index)
    work["position_group"] = position.map(_position_group)
    work["player_id"] = "understat|" + work["id"].astype("string")
    work["team_id"] = (
        "understat|"
        + work["league"].astype("string")
        + "|"
        + work["team_name"].map(normalize_person_name).astype("string")
    )
    work["match_id"] = (
        "understat-season-proxy|"
        + work["season_id"].astype("string")
        + "|"
        + work["competition_id"].astype("string")
        + "|"
        + work["team_id"].astype("string")
        + "|"
        + work["player_id"].astype("string")
    )
    work["match_date"] = work["season_id"].map(_season_end_date)
    work["started"] = 0  # Understat aggregate snapshot has no starts field.
    work["data_granularity"] = "season_proxy"
    work["source_name"] = "understat"
    proxy_columns = [
        "match_id", "match_date", "player_id", "player_name", "team_id", "team_name",
        "competition_id", "season_id", "position_group", "minutes_played", "matches_played",
        "started", "goals", "assists", "shots", "npxg", "xa", "data_granularity", "source_name",
        "multi_team_season",
    ]
    return build_player_match_features(work[proxy_columns])
