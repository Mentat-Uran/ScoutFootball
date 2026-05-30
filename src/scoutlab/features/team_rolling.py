"""Rolling team feature builders."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

ROLLING_TEAM_STATS = (
    "result_points",
    "goals_for",
    "goals_against",
    "goal_diff",
    "shots",
    "shots_on_target",
    "xg",
    "xg_against",
    "xg_diff",
)


def build_team_rolling_features(
    team_match_df: pd.DataFrame,
    windows: Iterable[int],
) -> pd.DataFrame:
    """Build leakage-safe rolling team features from team-match rows."""

    required = {"match_id", "match_date", "team_id", "result_points", "goals_for", "goals_against"}
    missing = sorted(required.difference(team_match_df.columns))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"team_match_df is missing required columns: {missing_text}")

    features = team_match_df.copy().sort_values(
        ["team_id", "match_date", "match_id"],
    ).reset_index(drop=True)
    features["match_date"] = pd.to_datetime(features["match_date"], errors="raise")
    group_labels = features["team_id"]

    for window in _normalize_windows(windows):
        prior_matches = _grouped_rolling_sum(
            pd.Series(1, index=features.index, dtype="float64"),
            group_labels,
            window,
        )
        features[f"prior_matches_{window}"] = prior_matches
        for stat_name in ROLLING_TEAM_STATS:
            if stat_name not in features.columns:
                features[stat_name] = pd.NA
            stat_sum = _grouped_rolling_sum(features[stat_name], group_labels, window)
            features[f"{stat_name}_{window}"] = stat_sum

        features[f"points_per_match_{window}"] = (
            features[f"result_points_{window}"] / prior_matches.where(prior_matches > 0)
        )
        features[f"goal_diff_per_match_{window}"] = (
            features[f"goal_diff_{window}"] / prior_matches.where(prior_matches > 0)
        )
        if "elo_pre" in features.columns:
            features[f"elo_pre_mean_{window}"] = _grouped_rolling_mean(
                features["elo_pre"],
                group_labels,
                window,
            )
        if "rest_days" in features.columns:
            features[f"rest_days_mean_{window}"] = _grouped_rolling_mean(
                features["rest_days"],
                group_labels,
                window,
            )

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


def _grouped_rolling_mean(series: pd.Series, group_labels: pd.Series, window: int) -> pd.Series:
    shifted = series.groupby(group_labels, sort=False).shift(1)
    numeric = pd.to_numeric(shifted, errors="coerce")
    return (
        numeric.groupby(group_labels, sort=False)
        .rolling(window=window, min_periods=1)
        .mean()
        .reset_index(level=0, drop=True)
    )
