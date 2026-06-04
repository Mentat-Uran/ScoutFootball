"""Helpers for low-frequency FBref pulls via soccerdata with Bundesliga fallback."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

BIG5_COMBINED = "Big 5 European Leagues Combined"
BUNDESLIGA = "GER-Bundesliga"
EXPECTED_BIG5_LEAGUES = {
    "ENG-Premier League",
    "ESP-La Liga",
    "FRA-Ligue 1",
    "GER-Bundesliga",
    "ITA-Serie A",
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
