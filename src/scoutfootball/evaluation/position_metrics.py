"""Position-specific metrics and explanation templates.

Defines core dimensions for each position (GK/CB/FB/DM/CM/AM/W/ST),
computes within-position percentile ranks, and generates natural language
explanations for player ratings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

# Position dimension definitions
# Each position has 3-6 core dimensions
# Each dimension maps to one or more feature columns and a display label
POSITION_DIMENSIONS: dict[str, dict[str, dict[str, Any]]] = {
    "GK": {
        "shot_stopping": {
            "label": "扑救",
            "columns": ["saves", "psxg_minus_ga"],
            "direction": "higher_better",
        },
        "command": {
            "label": "指挥",
            "columns": ["claims", "punches"],
            "direction": "higher_better",
        },
        "distribution": {
            "label": "出球",
            "columns": ["passes_completed_pct", "goal_kicks"],
            "direction": "higher_better",
        },
        "availability": {
            "label": "出勤",
            "columns": ["minutes_played", "matches_played"],
            "direction": "higher_better",
        },
    },
    "CB": {
        "defending": {
            "label": "防守",
            "columns": ["tackles", "interceptions", "clearances"],
            "direction": "higher_better",
        },
        "aerial": {
            "label": "争顶",
            "columns": ["aerials_won_pct"],
            "direction": "higher_better",
        },
        "availability": {
            "label": "出勤",
            "columns": ["minutes_played", "matches_played"],
            "direction": "higher_better",
        },
        "league_strength": {
            "label": "联赛强度",
            "columns": ["league_strength"],
            "direction": "higher_better",
        },
    },
    "FB": {
        "defending": {
            "label": "防守",
            "columns": ["tackles", "interceptions"],
            "direction": "higher_better",
        },
        "attacking": {
            "label": "进攻",
            "columns": ["assists", "xa"],
            "direction": "higher_better",
        },
        "progression": {
            "label": "推进",
            "columns": ["progressive_carries", "progressive_passes"],
            "direction": "higher_better",
        },
        "availability": {
            "label": "出勤",
            "columns": ["minutes_played", "matches_played"],
            "direction": "higher_better",
        },
    },
    "DM": {
        "defending": {
            "label": "防守",
            "columns": ["tackles", "interceptions"],
            "direction": "higher_better",
        },
        "progression": {
            "label": "推进",
            "columns": ["progressive_passes", "passes_completed_pct"],
            "direction": "higher_better",
        },
        "availability": {
            "label": "出勤",
            "columns": ["minutes_played", "matches_played"],
            "direction": "higher_better",
        },
        "league_strength": {
            "label": "联赛强度",
            "columns": ["league_strength"],
            "direction": "higher_better",
        },
    },
    "CM": {
        "progression": {
            "label": "推进",
            "columns": ["progressive_passes", "progressive_carries"],
            "direction": "higher_better",
        },
        "creation": {
            "label": "创造",
            "columns": ["assists", "xa", "key_passes"],
            "direction": "higher_better",
        },
        "control": {
            "label": "控球",
            "columns": ["passes_completed_pct", "touches"],
            "direction": "higher_better",
        },
        "availability": {
            "label": "出勤",
            "columns": ["minutes_played", "matches_played"],
            "direction": "higher_better",
        },
    },
    "AM": {
        "creation": {
            "label": "创造",
            "columns": ["assists", "xa", "key_passes"],
            "direction": "higher_better",
        },
        "finishing": {
            "label": "终结",
            "columns": ["goals", "npxg", "finishing_shrunk"],
            "direction": "higher_better",
        },
        "progression": {
            "label": "推进",
            "columns": ["progressive_passes", "progressive_carries"],
            "direction": "higher_better",
        },
        "availability": {
            "label": "出勤",
            "columns": ["minutes_played", "matches_played"],
            "direction": "higher_better",
        },
    },
    "W": {
        "finishing": {
            "label": "终结",
            "columns": ["goals", "npxg", "finishing_shrunk"],
            "direction": "higher_better",
        },
        "creation": {
            "label": "创造",
            "columns": ["assists", "xa"],
            "direction": "higher_better",
        },
        "progression": {
            "label": "推进",
            "columns": ["progressive_carries", "dribbles_completed"],
            "direction": "higher_better",
        },
        "availability": {
            "label": "出勤",
            "columns": ["minutes_played", "matches_played"],
            "direction": "higher_better",
        },
    },
    "ST": {
        "finishing": {
            "label": "终结",
            "columns": ["goals", "npxg", "finishing_shrunk"],
            "direction": "higher_better",
        },
        "progression": {
            "label": "推进",
            "columns": ["progressive_carries", "dribbles_completed"],
            "direction": "higher_better",
        },
        "availability": {
            "label": "出勤",
            "columns": ["minutes_played", "matches_played"],
            "direction": "higher_better",
        },
        "league_strength": {
            "label": "联赛强度",
            "columns": ["league_strength"],
            "direction": "higher_better",
        },
    },
}

# Map position_group values to our standard positions
POSITION_GROUP_MAP: dict[str, str] = {
    "GK": "GK",
    "DF": "CB",  # Default DF maps to CB
    "MF": "CM",  # Default MF maps to CM
    "FW": "ST",  # Default FW maps to ST
    "CB": "CB",
    "FB": "FB",
    "DM": "DM",
    "CM": "CM",
    "AM": "AM",
    "W": "W",
    "ST": "ST",
}


@dataclass(frozen=True)
class PositionDimensionScore:
    """Score for a single position dimension."""

    dimension: str
    label: str
    percentile: float
    raw_value: float | None
    is_missing: bool


@dataclass(frozen=True)
class PlayerPositionMetrics:
    """Complete position metrics for a player."""

    player_name: str
    position: str
    dimensions: tuple[PositionDimensionScore, ...]
    overall_percentile: float
    explanation: str


def _resolve_position(player_row: pd.Series, position: str | None = None) -> str:
    """Resolve the standard position from a player row."""
    if position is not None:
        return POSITION_GROUP_MAP.get(position, position)
    raw = str(player_row.get("position_group", ""))
    return POSITION_GROUP_MAP.get(raw, raw)


def _single_column_percentile(
    value: float,
    pool_values: pd.Series,
    direction: str = "higher_better",
) -> float:
    """Compute percentile rank of *value* within *pool_values*.

    Returns a value in [0, 100].  Missing/NaN pool values are dropped.
    If the pool is empty after dropping NaN, returns 50.0 (neutral).
    """
    clean = pd.to_numeric(pool_values, errors="coerce").dropna()
    if clean.empty:
        return 50.0
    if direction == "higher_better":
        return float((clean < value).mean() * 100)
    # lower_better (not currently used but reserved)
    return float((clean > value).mean() * 100)


def compute_dimension_percentile(
    df: pd.DataFrame,
    dimension_config: dict[str, Any],
    player_row: pd.Series,
) -> float:
    """Compute percentile rank for a single dimension within position.

    Averages the percentile ranks of all columns in the dimension.
    Missing columns (not in *df*) are skipped.  If no columns are
    available, returns 50.0 (neutral).
    """
    columns = dimension_config.get("columns", [])
    direction = dimension_config.get("direction", "higher_better")

    percentiles: list[float] = []
    for col in columns:
        if col not in df.columns:
            continue
        val = pd.to_numeric(player_row.get(col), errors="coerce")
        if pd.isna(val):
            continue
        pool = df[col]
        pct = _single_column_percentile(val, pool, direction)
        percentiles.append(pct)

    if not percentiles:
        return 50.0
    return sum(percentiles) / len(percentiles)


def compute_player_position_metrics(
    player_row: pd.Series,
    position_pool: pd.DataFrame,
    *,
    position: str | None = None,
) -> PlayerPositionMetrics:
    """Compute position-specific metrics for a single player.

    Args:
        player_row: Single row from feature matrix for the player
        position_pool: All players in the same position group
        position: Override position (if None, uses position_group from player_row)

    Returns:
        Complete position metrics with percentile ranks and explanation
    """
    resolved = _resolve_position(player_row, position)
    dim_defs = POSITION_DIMENSIONS.get(resolved, {})

    player_name = str(player_row.get("player_name", "Unknown"))

    dimension_scores: list[PositionDimensionScore] = []
    for dim_key, dim_cfg in dim_defs.items():
        label = dim_cfg.get("label", dim_key)
        columns = dim_cfg.get("columns", [])

        # Determine raw value: average of available columns
        raw_vals: list[float] = []
        for col in columns:
            if col not in player_row.index:
                continue
            v = pd.to_numeric(player_row.get(col), errors="coerce")
            if pd.notna(v):
                raw_vals.append(v)

        raw_value: float | None = (
            sum(raw_vals) / len(raw_vals) if raw_vals else None
        )

        # Check if all dimension columns are missing from the pool
        pool_has_any = any(col in position_pool.columns for col in columns)
        player_has_any = any(
            col in player_row.index
            and pd.notna(pd.to_numeric(player_row.get(col), errors="coerce"))
            for col in columns
        )
        is_missing = not pool_has_any or not player_has_any

        percentile = compute_dimension_percentile(
            position_pool, dim_cfg, player_row,
        )

        dimension_scores.append(
            PositionDimensionScore(
                dimension=dim_key,
                label=label,
                percentile=percentile,
                raw_value=raw_value,
                is_missing=is_missing,
            ),
        )

    # Overall percentile: average of dimension percentiles
    if dimension_scores:
        overall = sum(d.percentile for d in dimension_scores) / len(dimension_scores)
    else:
        overall = 50.0

    explanation = generate_explanation(
        player_name,
        resolved,
        tuple(dimension_scores),
    )

    return PlayerPositionMetrics(
        player_name=player_name,
        position=resolved,
        dimensions=tuple(dimension_scores),
        overall_percentile=overall,
        explanation=explanation,
    )


def generate_explanation(
    player_name: str,
    position: str,
    dimension_scores: tuple[PositionDimensionScore, ...],
) -> str:
    """Generate natural language explanation for a player's position metrics.

    Example output:
    "该球员终结能力位于 ST 前 10%，但出勤可靠性仅前 50%"
    """
    if not dimension_scores:
        return f"{player_name}（{position}）：无可用位置维度数据"

    # Sort by percentile descending to highlight strengths first
    sorted_dims = sorted(dimension_scores, key=lambda d: d.percentile, reverse=True)

    parts: list[str] = []
    for dim in sorted_dims:
        pct = dim.percentile
        if dim.is_missing:
            tier = "数据缺失"
        elif pct >= 90:
            tier = "前 10%"
        elif pct >= 75:
            tier = "前 25%"
        elif pct >= 50:
            tier = "前 50%"
        elif pct >= 25:
            tier = "前 75%"
        else:
            tier = "后 25%"

        parts.append(f"{dim.label}{tier}")

    # Build explanation: strengths first, weaknesses last
    strengths = [
        p for d, p in zip(sorted_dims, parts, strict=True)
        if d.percentile >= 75 and not d.is_missing
    ]
    weaknesses = [
        p for d, p in zip(sorted_dims, parts, strict=True)
        if d.percentile < 50 and not d.is_missing
    ]
    missing = [
        p for d, p in zip(sorted_dims, parts, strict=True)
        if d.is_missing
    ]

    fragments: list[str] = []
    if strengths:
        fragments.append("强项：" + "、".join(strengths))
    if weaknesses:
        fragments.append("不足：" + "、".join(weaknesses))
    if missing:
        fragments.append("缺失：" + "、".join(missing))

    detail = "；".join(fragments)
    return f"{player_name}（{position}）—— {detail}"


def _assign_ratings(
    df: pd.DataFrame,
    ratings: pd.Series,
    rating_col: str,
) -> pd.DataFrame:
    """Assign rating values to df, handling length mismatches."""
    if len(ratings) <= len(df):
        df[rating_col] = ratings.values[: len(df)]
    else:
        df[rating_col] = ratings.reindex(df.index).values
    return df


def compute_position_rankings(
    feature_matrix: pd.DataFrame,
    ratings: pd.Series,
    *,
    position_col: str = "position_group",
    rating_col: str = "rating",
) -> dict[str, pd.DataFrame]:
    """Compute within-position rankings.

    Returns a dict mapping position name to a DataFrame of players ranked
    within that position.

    Each DataFrame has columns: player_name, team_name, rating,
    position_percentile
    """
    if feature_matrix.empty or ratings.empty:
        return {}

    df = _assign_ratings(feature_matrix.copy(), ratings, rating_col)

    result: dict[str, pd.DataFrame] = {}
    for raw_pos, group in df.groupby(position_col, sort=False):
        pos = POSITION_GROUP_MAP.get(raw_pos, raw_pos)
        keep = [
            c for c in ("player_name", "team_name", rating_col)
            if c in group.columns
        ]
        ranked = group[keep].copy()
        if rating_col in group.columns:
            rated = pd.to_numeric(group[rating_col], errors="coerce")
        else:
            rated = pd.Series(dtype=float)
        ranked["position_percentile"] = rated.rank(pct=True) * 100
        sort_col = rating_col if rating_col in ranked.columns else "position_percentile"
        ranked = ranked.sort_values(sort_col, ascending=False)
        result[pos] = ranked.reset_index(drop=True)

    return result


def compute_cross_position_ranking(
    feature_matrix: pd.DataFrame,
    ratings: pd.Series,
    *,
    position_col: str = "position_group",
    rating_col: str = "rating",
) -> pd.DataFrame:
    """Compute cross-position overall ranking.

    Returns a DataFrame with all players ranked across positions,
    with position labels.

    Columns: player_name, team_name, position_group, rating, overall_rank
    """
    if feature_matrix.empty or ratings.empty:
        return pd.DataFrame(
            columns=["player_name", "team_name", position_col, rating_col, "overall_rank"],
        )

    df = _assign_ratings(feature_matrix.copy(), ratings, rating_col)

    keep_cols = [
        c for c in ("player_name", "team_name", position_col, rating_col)
        if c in df.columns
    ]
    result = df[keep_cols].copy()
    numeric_rating = pd.to_numeric(result[rating_col], errors="coerce")
    result["overall_rank"] = numeric_rating.rank(
        ascending=False, method="min",
    ).astype("Int64")
    result = result.sort_values("overall_rank").reset_index(drop=True)

    return result
