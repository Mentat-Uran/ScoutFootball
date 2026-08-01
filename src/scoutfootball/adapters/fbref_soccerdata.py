"""Helpers for low-frequency FBref pulls via soccerdata with Bundesliga fallback."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

BIG5_COMBINED = "Big 5 European Leagues Combined"
BUNDESLIGA = "GER-Bundesliga"

# Extended league constants (not part of Big 5 Combined view)
PRIMEIRA_LIGA = "POR-Primeira Liga"
EREDIVISIE = "NED-Eredivisie"
SUPER_LIG = "TUR-Süper Lig"
SCOTTISH_PREMIERSHIP = "SCO-Scottish Premiership"
FIRST_DIVISION_A = "BEL-First Division A"

SUPPORTED_LEAGUES = {
    "ENG-Premier League",
    "ESP-La Liga",
    "FRA-Ligue 1",
    "GER-Bundesliga",
    "ITA-Serie A",
    PRIMEIRA_LIGA,
    EREDIVISIE,
    SUPER_LIG,
    SCOTTISH_PREMIERSHIP,
    FIRST_DIVISION_A,
}

# Backward-compatible alias
EXPECTED_BIG5_LEAGUES = {
    "ENG-Premier League",
    "ESP-La Liga",
    "FRA-Ligue 1",
    "GER-Bundesliga",
    "ITA-Serie A",
}

EXTENDED_LEAGUES = {
    PRIMEIRA_LIGA,
    EREDIVISIE,
    SUPER_LIG,
    SCOTTISH_PREMIERSHIP,
    FIRST_DIVISION_A,
}


def read_player_season_stats_with_bundesliga_fallback(
    season: str,
    *,
    stat_type: str,
) -> pd.DataFrame:
    """Read FBref season stats and backfill Bundesliga when Big 5 combined omits it."""

    import soccerdata as sd

    big5_frame = sd.FBref(leagues=[BIG5_COMBINED], seasons=[season]).read_player_season_stats(
        stat_type=stat_type
    )
    big5_frame = normalize_big5_combined_frame(big5_frame)
    if not bundesliga_is_missing(big5_frame):
        return big5_frame

    bundesliga_frame = sd.FBref(leagues=[BUNDESLIGA], seasons=[season]).read_player_season_stats(
        stat_type=stat_type
    )
    return merge_stat_frames(big5_frame, bundesliga_frame)


def bundesliga_is_missing(frame: pd.DataFrame) -> bool:
    """Return True when a soccerdata FBref frame does not contain Bundesliga rows."""

    return BUNDESLIGA not in _extract_leagues(frame)


def normalize_big5_combined_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Map missing league labels in soccerdata Big 5 output back to Bundesliga."""

    if not isinstance(frame.index, pd.MultiIndex) or "league" not in frame.index.names:
        return frame
    if BUNDESLIGA in _extract_leagues(frame):
        return frame

    index_frame = frame.index.to_frame(index=False)
    missing_mask = index_frame["league"].isna()
    if not missing_mask.any():
        return frame

    normalized = frame.copy()
    index_frame.loc[missing_mask, "league"] = BUNDESLIGA
    normalized.index = pd.MultiIndex.from_frame(index_frame)
    return normalized.sort_index()


def merge_stat_frames(*frames: pd.DataFrame) -> pd.DataFrame:
    """Combine season stat frames and drop duplicate index entries."""

    non_empty = [normalize_big5_combined_frame(frame) for frame in frames if not frame.empty]
    if not non_empty:
        return pd.DataFrame()

    combined = pd.concat(non_empty, axis=0)
    if combined.index.has_duplicates:
        combined = combined[~combined.index.duplicated(keep="first")]
    return combined.sort_index()


def _extract_leagues(frame: pd.DataFrame) -> set[str]:
    if not isinstance(frame.index, pd.MultiIndex) or "league" not in frame.index.names:
        return set()
    return {
        str(value)
        for value in _iter_unique(frame.index.get_level_values("league"))
        if pd.notna(value) and str(value) != "nan"
    }


def _iter_unique(values: Iterable[object]) -> list[object]:
    seen: list[object] = []
    for value in values:
        if any(_values_equal(value, item) for item in seen):
            continue
        seen.append(value)
    return seen


def _values_equal(left: object, right: object) -> bool:
    if pd.isna(left) and pd.isna(right):
        return True
    return bool(left == right)


def read_player_season_stats_extended(
    season: str,
    *,
    stat_type: str,
    leagues: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Fetch player season stats for non-Big5 leagues individually.

    These leagues are not included in the Big 5 Combined view on FBref,
    so each must be fetched separately via soccerdata.

    Args:
        season: Season string like "2024-2025".
        stat_type: FBref stat type (standard, shooting, passing, etc.).
        leagues: Iterable of league names to fetch. Defaults to EXTENDED_LEAGUES.

    Returns:
        Combined DataFrame with all requested league data.
    """
    import soccerdata as sd

    if leagues is None:
        leagues = EXTENDED_LEAGUES

    frames: list[pd.DataFrame] = []
    for league in leagues:
        try:
            fbref = sd.FBref(leagues=[league], seasons=[season])
            frame = fbref.read_player_season_stats(stat_type=stat_type)
            if not frame.empty:
                frames.append(frame)
        except Exception:
            # Some leagues may not have all stat_types available; skip gracefully
            continue

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, axis=0)
    if combined.index.has_duplicates:
        combined = combined[~combined.index.duplicated(keep="first")]
    return combined.sort_index()
