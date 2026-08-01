"""Availability shortcut diagnostic for the rating system.

Detects and quantifies the extent to which availability (minutes/starts/matches)
dominates player ratings, which is a known bias in the current system.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Default availability-related feature names.
DEFAULT_AVAILABILITY_FEATURES: tuple[str, ...] = (
    "minutes_played",
    "started",
    "matches_played",
)


@dataclass(frozen=True)
class AvailabilityDiagnosticReport:
    """Diagnostic report for availability shortcut detection."""

    permutation_importance: pd.DataFrame  # feature -> importance
    position_availability_weights: pd.DataFrame  # position -> availability_weight
    team_aggregation_weights: pd.DataFrame  # team -> aggregation_weight_distribution
    availability_driven_players: pd.DataFrame  # top N players where availability > 50% of score
    summary: dict[str, Any]


def compute_permutation_importance(
    feature_matrix: pd.DataFrame,
    ratings: pd.Series,
    *,
    availability_features: tuple[str, ...] = DEFAULT_AVAILABILITY_FEATURES,
    n_repeats: int = 10,
    random_state: int = 42,
) -> pd.DataFrame:
    """Compute permutation importance of availability features vs other features.

    Uses a simple RandomForest as the surrogate model to measure how much
    availability features contribute to the rating compared to performance features.
    Falls back to a correlation-based importance if sklearn is unavailable.

    Args:
        feature_matrix: Numeric feature matrix (from rating_feature_matrix)
        ratings: Player ratings (target variable)
        availability_features: Column names for availability-related features
        n_repeats: Number of permutation repeats
        random_state: Random seed

    Returns:
        DataFrame with columns: feature, importance, is_availability
    """
    if feature_matrix.empty or ratings.empty:
        return pd.DataFrame(columns=["feature", "importance", "is_availability"])

    # Align indices and drop NaN
    common_idx = feature_matrix.index.intersection(ratings.index)
    if len(common_idx) == 0:
        return pd.DataFrame(columns=["feature", "importance", "is_availability"])

    x_mat = feature_matrix.loc[common_idx].copy()
    y_vec = ratings.loc[common_idx].copy()

    # Keep only numeric columns for importance computation
    numeric_cols = [
        c for c in x_mat.columns if pd.api.types.is_numeric_dtype(x_mat[c])
    ]
    x_mat = x_mat[numeric_cols]

    # Drop columns that are all NaN or constant
    valid_cols = []
    for col in x_mat.columns:
        if x_mat[col].isna().all():
            continue
        if x_mat[col].nunique(dropna=True) <= 1:
            continue
        valid_cols.append(col)

    if not valid_cols:
        return pd.DataFrame(columns=["feature", "importance", "is_availability"])

    x_mat = x_mat[valid_cols].fillna(0.0)

    # Drop rows where y is NaN
    valid_y_mask = y_vec.notna()
    x_mat = x_mat[valid_y_mask]
    y_vec = y_vec[valid_y_mask]

    if len(x_mat) < 10:
        return pd.DataFrame(columns=["feature", "importance", "is_availability"])

    try:
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.inspection import permutation_importance as _perm_imp

        model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=random_state,
            n_jobs=-1,
        )
        model.fit(x_mat, y_vec)

        result = _perm_imp(
            model,
            x_mat,
            y_vec,
            n_repeats=n_repeats,
            random_state=random_state,
        )

        importance_values = result.importances_mean
    except ImportError:
        # Fallback: correlation-based importance
        logger.info("sklearn not available; using correlation-based importance fallback")
        importance_values = _correlation_importance(x_mat, y_vec)

    rows = []
    for i, col in enumerate(x_mat.columns):
        rows.append(
            {
                "feature": col,
                "importance": float(importance_values[i]),
                "is_availability": col in availability_features,
            },
        )

    df = pd.DataFrame(rows)
    df = df.sort_values("importance", ascending=False).reset_index(drop=True)
    return df


def _correlation_importance(x_mat: pd.DataFrame, y_vec: pd.Series) -> np.ndarray:
    """Compute absolute Pearson correlation as a simple importance fallback."""
    correlations = x_mat.corrwith(y_vec, method="pearson").abs().fillna(0.0).values
    return correlations


def compute_position_availability_weights(
    feature_matrix: pd.DataFrame,
    ratings: pd.Series,
    *,
    position_col: str = "position_group",
    availability_features: tuple[str, ...] = DEFAULT_AVAILABILITY_FEATURES,
) -> pd.DataFrame:
    """Compute the average weight/contribution of availability features per position.

    Uses correlation between availability features and ratings, grouped by position.

    Args:
        feature_matrix: Feature matrix with position column
        ratings: Player ratings
        position_col: Column name for position group
        availability_features: Column names for availability features

    Returns:
        DataFrame with columns: position, availability_correlation,
        non_availability_correlation
    """
    if feature_matrix.empty or ratings.empty:
        return pd.DataFrame(
            columns=["position", "availability_correlation", "non_availability_correlation"],
        )

    if position_col not in feature_matrix.columns:
        return pd.DataFrame(
            columns=["position", "availability_correlation", "non_availability_correlation"],
        )

    common_idx = feature_matrix.index.intersection(ratings.index)
    if len(common_idx) == 0:
        return pd.DataFrame(
            columns=["position", "availability_correlation", "non_availability_correlation"],
        )

    df = feature_matrix.loc[common_idx].copy()
    df["_rating"] = ratings.loc[common_idx]

    # Drop rows with NaN rating
    df = df.dropna(subset=["_rating"])

    if df.empty:
        return pd.DataFrame(
            columns=["position", "availability_correlation", "non_availability_correlation"],
        )

    avail_cols = [c for c in availability_features if c in df.columns]
    non_avail_cols = [
        c
        for c in df.columns
        if c not in availability_features
        and c != "_rating"
        and c != position_col
        and pd.api.types.is_numeric_dtype(df[c])
    ]

    rows = []
    for position, group in df.groupby(position_col, dropna=True):
        if len(group) < 3:
            continue

        # Mean absolute correlation of availability features with rating
        avail_corrs = []
        for col in avail_cols:
            if group[col].isna().all() or group["_rating"].isna().all():
                continue
            corr = group[col].corr(group["_rating"], method="pearson")
            if pd.notna(corr):
                avail_corrs.append(abs(corr))

        non_avail_corrs = []
        for col in non_avail_cols:
            if group[col].isna().all() or group["_rating"].isna().all():
                continue
            corr = group[col].corr(group["_rating"], method="pearson")
            if pd.notna(corr):
                non_avail_corrs.append(abs(corr))

        rows.append(
            {
                "position": position,
                "availability_correlation": float(np.mean(avail_corrs)) if avail_corrs else 0.0,
                "non_availability_correlation": (
                    float(np.mean(non_avail_corrs)) if non_avail_corrs else 0.0
                ),
            },
        )

    if not rows:
        return pd.DataFrame(
            columns=["position", "availability_correlation", "non_availability_correlation"],
        )

    return pd.DataFrame(rows).reset_index(drop=True)


def compute_team_aggregation_weights(
    player_ratings: pd.DataFrame,
    *,
    team_col: str = "team_name",
    rating_col: str = "rating",
    minutes_col: str = "minutes_played",
) -> pd.DataFrame:
    """Compute team-level aggregation weight distribution.

    Shows how much each team's average rating is driven by high-minute players.

    Args:
        player_ratings: DataFrame with player ratings and minutes
        team_col: Team name column
        rating_col: Rating column
        minutes_col: Minutes played column

    Returns:
        DataFrame with columns: team, top_player_minute_share, rating_std, n_players
    """
    required = {team_col, rating_col, minutes_col}
    missing = sorted(required.difference(player_ratings.columns))
    if missing:
        return pd.DataFrame(columns=["team", "top_player_minute_share", "rating_std", "n_players"])

    if player_ratings.empty:
        return pd.DataFrame(columns=["team", "top_player_minute_share", "rating_std", "n_players"])

    df = player_ratings[[team_col, rating_col, minutes_col]].copy()
    df = df.dropna(subset=[rating_col, minutes_col])

    if df.empty:
        return pd.DataFrame(columns=["team", "top_player_minute_share", "rating_std", "n_players"])

    rows = []
    for team, group in df.groupby(team_col, dropna=True):
        n_players = len(group)
        if n_players == 0:
            continue

        total_minutes = group[minutes_col].sum()
        if total_minutes <= 0:
            top_share = 0.0
        else:
            # Share of minutes held by the top-minute player
            top_minutes = group[minutes_col].max()
            top_share = float(top_minutes / total_minutes)

        rating_std = float(group[rating_col].std()) if n_players > 1 else 0.0

        rows.append(
            {
                "team": team,
                "top_player_minute_share": top_share,
                "rating_std": rating_std,
                "n_players": n_players,
            },
        )

    if not rows:
        return pd.DataFrame(columns=["team", "top_player_minute_share", "rating_std", "n_players"])

    return pd.DataFrame(rows).reset_index(drop=True)


def identify_availability_driven_players(
    feature_matrix: pd.DataFrame,
    ratings: pd.Series,
    *,
    availability_features: tuple[str, ...] = DEFAULT_AVAILABILITY_FEATURES,
    threshold: float = 0.50,
    top_n: int = 20,
) -> pd.DataFrame:
    """Identify players whose rating is primarily driven by availability.

    A player is "availability-driven" if the ratio of availability feature
    correlation to total feature correlation exceeds the threshold for their
    position group.

    Args:
        feature_matrix: Feature matrix
        ratings: Player ratings
        availability_features: Column names for availability features
        threshold: Minimum availability contribution ratio (default 0.50)
        top_n: Number of top players to return

    Returns:
        DataFrame with columns: player_name, team_name, position_group, rating,
            availability_contribution_ratio
    """
    if feature_matrix.empty or ratings.empty:
        return pd.DataFrame(
            columns=[
                "player_name",
                "team_name",
                "position_group",
                "rating",
                "availability_contribution_ratio",
            ],
        )

    common_idx = feature_matrix.index.intersection(ratings.index)
    if len(common_idx) == 0:
        return pd.DataFrame(
            columns=[
                "player_name",
                "team_name",
                "position_group",
                "rating",
                "availability_contribution_ratio",
            ],
        )

    df = feature_matrix.loc[common_idx].copy()
    df["_rating"] = ratings.loc[common_idx]
    df = df.dropna(subset=["_rating"])

    if df.empty:
        return pd.DataFrame(
            columns=[
                "player_name",
                "team_name",
                "position_group",
                "rating",
                "availability_contribution_ratio",
            ],
        )

    # Compute per-position availability contribution ratio
    avail_cols = [c for c in availability_features if c in df.columns]
    non_avail_numeric_cols = [
        c
        for c in df.columns
        if c not in availability_features
        and c != "_rating"
        and c not in ("player_name", "team_name", "position_group", "player_id")
        and pd.api.types.is_numeric_dtype(df[c])
    ]

    position_col = "position_group" if "position_group" in df.columns else None

    # Compute per-position availability ratio
    position_ratios: dict[str, float] = {}
    if position_col:
        for position, group in df.groupby(position_col, dropna=True):
            if len(group) < 3:
                position_ratios[position] = 0.0
                continue
            avail_corrs = []
            for col in avail_cols:
                corr = group[col].corr(group["_rating"], method="pearson")
                if pd.notna(corr):
                    avail_corrs.append(abs(corr))
            non_avail_corrs = []
            for col in non_avail_numeric_cols:
                corr = group[col].corr(group["_rating"], method="pearson")
                if pd.notna(corr):
                    non_avail_corrs.append(abs(corr))

            total = sum(avail_corrs) + sum(non_avail_corrs)
            position_ratios[position] = float(sum(avail_corrs) / total) if total > 0 else 0.0
    else:
        # Global ratio
        avail_corrs = []
        for col in avail_cols:
            corr = df[col].corr(df["_rating"], method="pearson")
            if pd.notna(corr):
                avail_corrs.append(abs(corr))
        non_avail_corrs = []
        for col in non_avail_numeric_cols:
            corr = df[col].corr(df["_rating"], method="pearson")
            if pd.notna(corr):
                non_avail_corrs.append(abs(corr))
        total = sum(avail_corrs) + sum(non_avail_corrs)
        global_ratio = float(sum(avail_corrs) / total) if total > 0 else 0.0
        position_ratios["ALL"] = global_ratio

    # Assign ratio to each player
    if position_col:
        df["_availability_ratio"] = df[position_col].map(position_ratios).fillna(0.0)
    else:
        df["_availability_ratio"] = position_ratios.get("ALL", 0.0)

    # Filter to availability-driven players
    driven = df[df["_availability_ratio"] >= threshold].copy()

    if driven.empty:
        # Return empty with correct columns
        name_col = "player_name" if "player_name" in df.columns else None
        team_col = "team_name" if "team_name" in df.columns else None
        pos_col = position_col
        return pd.DataFrame(
            columns=[
                name_col or "player_name",
                team_col or "team_name",
                pos_col or "position_group",
                "rating",
                "availability_contribution_ratio",
            ],
        )

    # Sort by availability ratio descending, take top_n
    driven = driven.sort_values("_availability_ratio", ascending=False).head(top_n)

    result = pd.DataFrame()
    result["player_name"] = driven["player_name"] if "player_name" in driven.columns else "unknown"
    result["team_name"] = driven["team_name"] if "team_name" in driven.columns else "unknown"
    result["position_group"] = (
        driven[position_col] if position_col and position_col in driven.columns else "unknown"
    )
    result["rating"] = driven["_rating"]
    result["availability_contribution_ratio"] = driven["_availability_ratio"]

    return result.reset_index(drop=True)


def generate_availability_diagnostic(
    feature_matrix_path: str | None = None,
    ratings_path: str | None = None,
    *,
    settings: Any = None,
) -> AvailabilityDiagnosticReport:
    """Generate a complete availability diagnostic report.

    Reads the rating feature matrix and player ratings, runs all diagnostic
    checks, and returns a comprehensive report.

    Args:
        feature_matrix_path: Path to rating_feature_matrix.parquet
        ratings_path: Path to player_ratings_optimized.parquet
        settings: PlatformSettings (used to resolve default paths)

    Returns:
        Complete diagnostic report
    """
    from scoutfootball.config import PlatformSettings

    resolved = settings or PlatformSettings.from_root()

    # Resolve paths
    if feature_matrix_path is None:
        fm_path = resolved.gold_root / "feature_store" / "rating_feature_matrix.parquet"
    else:
        fm_path = __import__("pathlib").Path(feature_matrix_path)

    if ratings_path is None:
        r_path = resolved.model_root / "player_ratings_optimized.parquet"
    else:
        r_path = __import__("pathlib").Path(ratings_path)

    # Load data
    feature_matrix = _safe_read_parquet(fm_path)
    ratings_df = _safe_read_parquet(r_path)

    if feature_matrix.empty and ratings_df.empty:
        logger.warning("Both feature matrix and ratings files are empty or missing")
        return _empty_report("no_data")

    # Try to merge feature matrix with ratings
    if not feature_matrix.empty and not ratings_df.empty:
        # Determine merge keys
        merge_keys: list[str] = []
        for key in ("player_id", "season_id"):
            if key in feature_matrix.columns and key in ratings_df.columns:
                merge_keys.append(key)

        if merge_keys:
            # Find rating column in ratings_df
            rating_col = _find_rating_column(ratings_df)
            if rating_col:
                merged = feature_matrix.merge(
                    ratings_df[merge_keys + [rating_col]],
                    on=merge_keys,
                    how="inner",
                )
                ratings_series = merged[rating_col]
                fm_for_diag = merged.drop(columns=[rating_col])
            else:
                fm_for_diag = feature_matrix
                ratings_series = pd.Series(dtype=float)
        else:
            fm_for_diag = feature_matrix
            ratings_series = pd.Series(dtype=float)
    elif not feature_matrix.empty:
        fm_for_diag = feature_matrix
        # Try to find a rating-like column in the feature matrix itself
        rating_col = _find_rating_column(feature_matrix)
        if rating_col:
            ratings_series = fm_for_diag[rating_col]
            fm_for_diag = fm_for_diag.drop(columns=[rating_col])
        else:
            ratings_series = pd.Series(dtype=float)
    else:
        # Only ratings available — limited diagnostics
        fm_for_diag = pd.DataFrame()
        rating_col = _find_rating_column(ratings_df)
        ratings_series = ratings_df[rating_col] if rating_col else pd.Series(dtype=float)

    # Run diagnostics
    perm_importance = compute_permutation_importance(fm_for_diag, ratings_series)

    position_weights = compute_position_availability_weights(fm_for_diag, ratings_series)

    # Team aggregation needs player-level data with team and minutes
    if not ratings_df.empty and "team_name" in ratings_df.columns:
        rating_col = _find_rating_column(ratings_df) or "rating"
        if rating_col not in ratings_df.columns:
            rating_col = None
        team_weights = compute_team_aggregation_weights(
            ratings_df,
            rating_col=rating_col or "rating",
        )
    elif not fm_for_diag.empty and "team_name" in fm_for_diag.columns:
        team_weights = compute_team_aggregation_weights(
            fm_for_diag,
            rating_col="_rating" if "_rating" in fm_for_diag.columns else "rating",
        )
    else:
        team_weights = pd.DataFrame(
            columns=["team", "top_player_minute_share", "rating_std", "n_players"],
        )

    driven_players = identify_availability_driven_players(fm_for_diag, ratings_series)

    # Build summary
    summary = _build_summary(perm_importance, position_weights, team_weights, driven_players)

    return AvailabilityDiagnosticReport(
        permutation_importance=perm_importance,
        position_availability_weights=position_weights,
        team_aggregation_weights=team_weights,
        availability_driven_players=driven_players,
        summary=summary,
    )


def _find_rating_column(df: pd.DataFrame) -> str | None:
    """Find the most likely rating column in a DataFrame."""
    candidates = ["rating", "overall_rating", "player_rating", "optimized_rating"]
    for col in candidates:
        if col in df.columns:
            return col
    # Fallback: any column with 'rating' in the name
    for col in df.columns:
        if "rating" in col.lower() and pd.api.types.is_numeric_dtype(df[col]):
            return col
    return None


def _safe_read_parquet(path: Any) -> pd.DataFrame:
    """Read a parquet file, returning empty DataFrame on failure."""
    try:
        from pathlib import Path

        p = Path(path)
        if p.exists() and p.suffix == ".parquet":
            df = pd.read_parquet(p)
            if df is not None and not df.empty:
                return df
    except Exception as exc:
        logger.warning("Failed to read parquet at %s: %s", path, exc)
    return pd.DataFrame()


def _build_summary(
    perm_importance: pd.DataFrame,
    position_weights: pd.DataFrame,
    team_weights: pd.DataFrame,
    driven_players: pd.DataFrame,
) -> dict[str, Any]:
    """Build a summary dict from diagnostic components."""
    summary: dict[str, Any] = {}

    # Permutation importance summary
    if not perm_importance.empty:
        avail_importance = perm_importance[perm_importance["is_availability"]]["importance"]
        non_avail_importance = perm_importance[~perm_importance["is_availability"]]["importance"]
        total_importance = perm_importance["importance"].sum()
        avail_share = (
            float(avail_importance.sum() / total_importance) if total_importance > 0 else 0.0
        )
        summary["availability_importance_share"] = round(avail_share, 4)
        summary["top_availability_feature"] = (
            perm_importance[perm_importance["is_availability"]].iloc[0]["feature"]
            if avail_importance.any()
            else None
        )
        summary["top_performance_feature"] = (
            perm_importance[~perm_importance["is_availability"]].iloc[0]["feature"]
            if non_avail_importance.any()
            else None
        )
    else:
        summary["availability_importance_share"] = None
        summary["top_availability_feature"] = None
        summary["top_performance_feature"] = None

    # Position weights summary
    if not position_weights.empty:
        summary["position_with_highest_availability_weight"] = position_weights.loc[
            position_weights["availability_correlation"].idxmax(), "position"
        ]
        summary["mean_availability_correlation"] = round(
            float(position_weights["availability_correlation"].mean()), 4,
        )
    else:
        summary["position_with_highest_availability_weight"] = None
        summary["mean_availability_correlation"] = None

    # Team aggregation summary
    if not team_weights.empty:
        summary["mean_top_player_minute_share"] = round(
            float(team_weights["top_player_minute_share"].mean()), 4,
        )
        summary["teams_with_dominant_player"] = int(
            (team_weights["top_player_minute_share"] > 0.30).sum(),
        )
    else:
        summary["mean_top_player_minute_share"] = None
        summary["teams_with_dominant_player"] = None

    # Availability-driven players summary
    summary["n_availability_driven_players"] = len(driven_players)

    return summary


def _empty_report(reason: str) -> AvailabilityDiagnosticReport:
    """Return an empty diagnostic report with a reason in the summary."""
    return AvailabilityDiagnosticReport(
        permutation_importance=pd.DataFrame(columns=["feature", "importance", "is_availability"]),
        position_availability_weights=pd.DataFrame(
            columns=["position", "availability_correlation", "non_availability_correlation"],
        ),
        team_aggregation_weights=pd.DataFrame(
            columns=["team", "top_player_minute_share", "rating_std", "n_players"],
        ),
        availability_driven_players=pd.DataFrame(
            columns=[
                "player_name",
                "team_name",
                "position_group",
                "rating",
                "availability_contribution_ratio",
            ],
        ),
        summary={"reason": reason},
    )


def save_availability_diagnostic(
    report: AvailabilityDiagnosticReport,
    output_dir: str | Any,
) -> str:
    """Save an availability diagnostic report to parquet files.

    Args:
        report: The diagnostic report to save
        output_dir: Directory path to save files into

    Returns:
        Status message
    """
    from pathlib import Path

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    report.permutation_importance.to_parquet(out / "permutation_importance.parquet", index=False)
    report.position_availability_weights.to_parquet(
        out / "position_availability_weights.parquet", index=False,
    )
    report.team_aggregation_weights.to_parquet(
        out / "team_aggregation_weights.parquet", index=False,
    )
    report.availability_driven_players.to_parquet(
        out / "availability_driven_players.parquet", index=False,
    )

    # Save summary as JSON
    import json

    with open(out / "summary.json", "w", encoding="utf-8") as f:
        json.dump(report.summary, f, indent=2, ensure_ascii=False, default=str)

    n_driven = report.summary.get("n_availability_driven_players", 0)
    avail_share = report.summary.get("availability_importance_share", "N/A")
    return f"ok (availability_share={avail_share}, driven_players={n_driven})"
