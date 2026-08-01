"""Rolling player feature builders."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

ROLLING_PLAYER_STATS = ("goals", "assists", "shots", "shots_on_target", "npxg", "xa", "xT_added")


def build_player_rolling_features(
    player_match_df: pd.DataFrame,
    windows: Iterable[int],
    *,
    shrinkage_minutes: int = 270,
) -> pd.DataFrame:
    """Build leakage-safe rolling player features using only prior matches."""

    required = {
        "match_id",
        "match_date",
        "player_id",
        "minutes_played",
        "starts",
        "available_flag",
    }
    missing = sorted(required.difference(player_match_df.columns))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"player_match_df is missing required columns: {missing_text}")

    features = (
        player_match_df.copy()
        .sort_values(
            ["player_id", "match_date", "match_id"],
        )
        .reset_index(drop=True)
    )
    features["match_date"] = pd.to_datetime(features["match_date"], errors="raise")
    group_labels = features["player_id"]

    for window in _normalize_windows(windows):
        prior_minutes = _grouped_rolling_sum(features["minutes_played"], group_labels, window)
        prior_appearances = _grouped_rolling_sum(features["available_flag"], group_labels, window)
        prior_starts = _grouped_rolling_sum(features["starts"], group_labels, window)
        features[f"prior_minutes_{window}"] = prior_minutes
        features[f"prior_appearances_{window}"] = prior_appearances
        features[f"prior_starts_{window}"] = prior_starts
        features[f"shrink_factor_{window}"] = prior_minutes / (prior_minutes + shrinkage_minutes)

        for stat_name in ROLLING_PLAYER_STATS:
            if stat_name not in features.columns:
                features[stat_name] = pd.NA
            stat_sum = _grouped_rolling_sum(features[stat_name], group_labels, window)
            features[f"{stat_name}_{window}"] = stat_sum
            raw_per90 = stat_sum.mul(90).div(prior_minutes.where(prior_minutes > 0))
            features[f"{stat_name}_p90_raw_{window}"] = raw_per90
            features[f"{stat_name}_p90_shrunk_{window}"] = (
                raw_per90 * features[f"shrink_factor_{window}"]
            )

        shots = features[f"shots_{window}"]
        shots_on_target = features[f"shots_on_target_{window}"]
        features[f"sot_rate_{window}"] = shots_on_target / shots.where(shots > 0)

    return features


def _normalize_windows(windows: Iterable[int]) -> tuple[int, ...]:
    normalized = tuple(int(window) for window in windows)
    if not normalized:
        raise ValueError("windows must contain at least one positive integer")
    if any(window <= 0 for window in normalized):
        raise ValueError("windows must contain only positive integers")
    return normalized


def _grouped_rolling_sum(series: pd.Series, group_labels: pd.Series, window: int) -> pd.Series:
    shifted = series.groupby(group_labels, sort=False).shift(1)
    numeric = pd.to_numeric(shifted, errors="coerce")
    return (
        numeric.groupby(group_labels, sort=False)
        .rolling(window=window, min_periods=1)
        .sum()
        .reset_index(level=0, drop=True)
    )
