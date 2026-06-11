"""Rating feature matrix builder with missing field handling."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# High-order field group definitions for missing-field detection.
FIELD_GROUPS: dict[str, list[str]] = {
    "defense": [
        "tackles",
        "interceptions",
        "clearances",
        "blocks",
        "tackles_won",
        "fouls_committed",
        "fouls_drawn",
        "crosses",
        "own_goals",
    ],
    "possession": ["touches", "dribbles", "dispossessed"],
    "xT_VAEP": ["xT_added", "vaep_value"],
    "goalkeeper": ["saves", "goals_conceded", "psxg"],
}

# Numeric feature columns to include in the rating matrix.
RATING_NUMERIC_COLUMNS: list[str] = [
    "goals",
    "assists",
    "shots",
    "shots_on_target",
    "npxg",
    "xa",
    "minutes_played",
    "starts",
    "available_flag",
    "tackles",
    "passes",
    "xT_added",
    "tackles_won",
    "interceptions",
    "fouls_committed",
    "fouls_drawn",
    "crosses",
    "own_goals",
]

# Category columns to include in the rating matrix.
RATING_CATEGORY_COLUMNS: list[str] = [
    "position_group",
    "competition_id",
    "season_id",
]

# Identifier columns for aggregation to player-season level.
RATING_ID_COLUMNS: list[str] = [
    "player_id",
    "player_name",
    "team_id",
    "team_name",
    "season_id",
    "competition_id",
    "position_group",
]


def compute_finishing_shrinkage(
    df: pd.DataFrame,
    *,
    goals_col: str = "goals",
    xg_col: str = "npxg",
    shots_col: str = "shots",
    shrinkage_k: float = 50.0,
) -> pd.Series:
    """Compute empirical Bayes shrinkage for finishing signal.

    Uses the formula::

        shrunk_finishing = (n / (n + K)) * raw_finishing

    where:

        n = number of shots (sample size)
        K = shrinkage factor (default 50, ~5 matches worth of shots)
        raw_finishing = (goals - xG) / shots

    For players with few shots, the finishing signal is pulled toward 0.
    For players with many shots, the signal is mostly preserved.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with player stats.
    goals_col : str
        Column name for goals.
    xg_col : str
        Column name for non-penalty xG (npxg).
    shots_col : str
        Column name for shot count.
    shrinkage_k : float
        Shrinkage factor K (default 50).

    Returns
    -------
    pd.Series
        Series with shrunk finishing values, same index as *df*.
    """
    goals = pd.to_numeric(df.get(goals_col, 0), errors="coerce").fillna(0)
    xg = pd.to_numeric(df.get(xg_col, 0), errors="coerce").fillna(0)
    shots = pd.to_numeric(df.get(shots_col, 0), errors="coerce").fillna(0)

    # raw_finishing = (goals - xG) / shots, only where shots > 0
    raw_finishing = pd.Series(0.0, index=df.index, dtype="float64")
    has_shots = shots > 0
    raw_finishing[has_shots] = (goals[has_shots] - xg[has_shots]) / shots[has_shots]

    # Shrink toward 0 based on sample size
    shrunk = (shots / (shots + shrinkage_k)) * raw_finishing
    return shrunk


def mark_missing_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Mark high-order field groups as missing when all fields in a group are NaN.

    For each group defined in ``FIELD_GROUPS``, if ALL fields in that group are
    NaN/missing for a row, the ``{group}_missing`` column is set to True.
    If any field has data, it is set to False.

    Parameters
    ----------
    df : pd.DataFrame
        Player-level DataFrame that may contain columns matching field group names.

    Returns
    -------
    pd.DataFrame
        The input DataFrame with additional ``{group}_missing`` boolean columns.
    """
    result = df.copy()

    for group_name, field_list in FIELD_GROUPS.items():
        existing_fields = [f for f in field_list if f in result.columns]
        if not existing_fields:
            # No columns from this group exist at all — mark as missing.
            result[f"{group_name}_missing"] = True
            continue

        all_nan = result[existing_fields].isna().all(axis=1)
        result[f"{group_name}_missing"] = all_nan

    return result


def fill_missing_with_position_median(
    df: pd.DataFrame,
    missing_cols: dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    """Fill NaN values in missing field groups with position-group median.

    For each group marked as missing (``{group}_missing == True``), fill the
    NaN values of that group's fields with the median of the same position
    group (GK/DF/MF/FW). Falls back to global median if no position_group
    column exists or no peers are available.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with ``{group}_missing`` columns and the corresponding
        field columns.
    missing_cols : dict[str, list[str]] or None
        Mapping of group names to their field lists. If None, uses
        ``FIELD_GROUPS``.

    Returns
    -------
    pd.DataFrame
        The input DataFrame with NaN values filled by position median.
    """
    group_defs = missing_cols if missing_cols is not None else FIELD_GROUPS
    result = df.copy()

    for group_name, field_list in group_defs.items():
        missing_flag = f"{group_name}_missing"
        if missing_flag not in result.columns:
            continue

        existing_fields = [f for f in field_list if f in result.columns]
        if not existing_fields:
            continue

        missing_mask = result[missing_flag] == True  # noqa: E712 — intentional bool comparison

        if not missing_mask.any():
            continue

        has_position = "position_group" in result.columns

        for field in existing_fields:
            # Ensure numeric dtype to avoid FutureWarning on fillna downcasting
            field_values = pd.to_numeric(result[field], errors="coerce")
            fill_indices = result.index[missing_mask & field_values.isna()]

            if fill_indices.empty:
                continue

            if has_position:
                position_medians = result.groupby("position_group")[field].transform(
                    "median",
                )
                position_medians = pd.to_numeric(position_medians, errors="coerce")
                field_values = field_values.fillna(position_medians)
            else:
                global_median = field_values.median()
                if pd.notna(global_median):
                    field_values = field_values.fillna(global_median)

            # Only fill the rows that were marked as missing — leave other NaN
            # values (from partial coverage) untouched.
            result.loc[fill_indices, field] = field_values.loc[fill_indices]

    return result


def build_rating_feature_matrix(
    player_match: pd.DataFrame,
    player_rolling: pd.DataFrame,
) -> pd.DataFrame:
    """Build a rating feature matrix with one row per player-season.

    Combines player_match and player_rolling data, adds missing field
    markers, source coverage flags, and computes input file hashes.

    Parameters
    ----------
    player_match : pd.DataFrame
        Per-player-per-match feature DataFrame.
    player_rolling : pd.DataFrame
        Per-player rolling feature DataFrame.

    Returns
    -------
    pd.DataFrame
        Rating feature matrix with one row per player-season, including
        missing field markers and source coverage flags.
    """
    if player_match.empty:
        return pd.DataFrame()

    pm = player_match.copy()

    # --- Apply missing field marking and fallback ---
    pm = mark_missing_fields(pm)
    pm = fill_missing_with_position_median(pm)

    # --- Determine aggregation level ---
    # Prefer season_id for season-level aggregation; fall back to competition_id.
    agg_keys = [c for c in RATING_ID_COLUMNS if c in pm.columns]
    if not agg_keys:
        logger.warning("No identifier columns found for rating matrix aggregation")
        return pd.DataFrame()

    # Ensure player_id is in the aggregation keys
    if "player_id" not in agg_keys:
        logger.warning("player_id column missing; cannot build rating matrix")
        return pd.DataFrame()

    # --- Aggregate to player-season level ---
    # Numeric columns: sum or mean depending on semantics
    sum_cols = ["goals", "assists", "shots", "shots_on_target", "minutes_played", "starts"]
    mean_cols = ["npxg", "xa", "available_flag", "tackles", "passes", "xT_added"]

    agg_dict: dict[str, str] = {}
    for col in sum_cols:
        if col in pm.columns:
            agg_dict[col] = "sum"
    for col in mean_cols:
        if col in pm.columns:
            agg_dict[col] = "mean"

    if not agg_dict:
        logger.warning("No numeric columns available for aggregation")
        return pd.DataFrame()

    # Take first value for category/id columns
    first_cols = [c for c in agg_keys if c not in ("player_id", "season_id")]
    for col in first_cols:
        agg_dict[col] = "first"

    # Missing flags: any True means the group was missing for at least one match
    missing_flag_cols = [c for c in pm.columns if c.endswith("_missing")]
    for col in missing_flag_cols:
        agg_dict[col] = "max"  # True > False, so max = any True

    matrix = pm.groupby(["player_id", "season_id"], as_index=False).agg(agg_dict)

    # --- Merge FBref misc defensive stats ---
    matrix = _merge_fbref_misc_defense(matrix)

    # --- Re-evaluate defense_missing after misc merge ---
    # The initial mark_missing_fields ran before misc data was available,
    # so defense_missing may be True even though misc fields now have data.
    defense_fields = FIELD_GROUPS.get("defense", [])
    existing_defense = [f for f in defense_fields if f in matrix.columns]
    if existing_defense:
        matrix["defense_missing"] = matrix[existing_defense].isna().all(axis=1)
    else:
        matrix["defense_missing"] = True

    # --- Compute finishing shrinkage ---
    # raw_finishing = (goals - xG) / shots; shrunk = (shots/(shots+K)) * raw
    has_shots = (
        matrix["shots"] > 0
        if "shots" in matrix.columns
        else pd.Series(False, index=matrix.index)
    )
    raw_finishing = pd.Series(0.0, index=matrix.index, dtype="float64")
    if has_shots.any():
        goals_agg = pd.to_numeric(matrix["goals"], errors="coerce").fillna(0)
        xg_agg = pd.to_numeric(matrix.get("npxg", 0), errors="coerce").fillna(0)
        shots_agg = pd.to_numeric(matrix["shots"], errors="coerce").fillna(0)
        raw_finishing[has_shots] = (goals_agg[has_shots] - xg_agg[has_shots]) / shots_agg[has_shots]
    matrix["finishing_raw"] = raw_finishing
    matrix["finishing_shrunk"] = compute_finishing_shrinkage(matrix)

    # --- Add data source coverage markers ---
    if "source_name" in pm.columns:
        source_names = pm["source_name"].dropna().unique()
        for source in source_names:
            source_flag = f"{source}_source_covered"
            player_has_source = pm[pm["source_name"] == source]["player_id"].unique()
            matrix[source_flag] = matrix["player_id"].isin(player_has_source)
    else:
        matrix["unknown_source_covered"] = True

    # --- Add input file hash ---
    matrix.attrs["_input_hash"] = _compute_dataframe_hash(player_match, player_rolling)

    # --- Add has_expected_metrics and has_ball_value_data if present ---
    for flag_col in ("has_expected_metrics", "has_ball_value_data"):
        if flag_col in pm.columns:
            agg_flag = pm.groupby(["player_id", "season_id"])[flag_col].any().reset_index()
            matrix = matrix.merge(agg_flag, on=["player_id", "season_id"], how="left")

    return matrix


def write_feature_manifest(
    matrix: pd.DataFrame,
    output_path: Path,
) -> None:
    """Write a JSON manifest alongside the rating feature matrix parquet.

    The manifest contains column metadata, row count, input hashes, and
    timestamp for reproducibility and audit purposes.

    Parameters
    ----------
    matrix : pd.DataFrame
        The rating feature matrix that was saved as parquet.
    output_path : Path
        Path where the parquet file was written. The manifest will be
        written as ``{stem}_manifest.json`` in the same directory.
    """
    manifest_path = output_path.parent / f"{output_path.stem}_manifest.json"

    columns_info = []
    for col in matrix.columns:
        dtype_str = str(matrix[col].dtype)
        missing_rate = float(matrix[col].isna().mean()) if len(matrix) > 0 else 0.0

        # Determine source category
        if col.endswith("_missing"):
            source = "missing_marker"
        elif col.endswith("_source_covered"):
            source = "source_coverage"
        elif col in RATING_NUMERIC_COLUMNS:
            source = "player_stats"
        elif col in RATING_CATEGORY_COLUMNS:
            source = "category"
        else:
            source = "derived"

        columns_info.append({
            "name": col,
            "dtype": dtype_str,
            "source": source,
            "missing_rate": round(missing_rate, 4),
        })

    manifest = {
        "total_rows": len(matrix),
        "columns": columns_info,
        "input_hash": matrix.attrs.get("_input_hash", "unknown"),
        "timestamp": datetime.now(tz=UTC).isoformat(),
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    logger.info("Feature manifest written to %s", manifest_path)


# FBref misc column name mapping: (multi-index column) -> rating matrix field name
_FBREF_MISC_FIELD_MAP: dict[tuple[str, str], str] = {
    ("Performance", "TklW"): "tackles_won",
    ("Performance", "Int"): "interceptions",
    ("Performance", "Fls"): "fouls_committed",
    ("Performance", "Fld"): "fouls_drawn",
    ("Performance", "Crs"): "crosses",
    ("Performance", "OG"): "own_goals",
}


def _merge_fbref_misc_defense(matrix: pd.DataFrame) -> pd.DataFrame:
    """Merge FBref misc table defensive stats into the rating feature matrix.

    Reads ``data/raw/fbref/player_misc_5seasons.parquet``, extracts the
    mapped defensive fields, and merges them onto *matrix* using
    player_name + season_id as keys.

    If the misc file is missing or empty, the new columns are added as NaN.
    """
    from scoutfootball.config import PlatformSettings

    resolved = PlatformSettings.from_root()
    misc_path = resolved.raw_root / "fbref" / "player_misc_5seasons.parquet"

    # Define the new columns to add
    new_cols = list(_FBREF_MISC_FIELD_MAP.values())

    if not misc_path.exists():
        logger.warning("FBref misc file not found: %s — defense fields will be NaN", misc_path)
        for col in new_cols:
            matrix[col] = pd.NA
        return matrix

    try:
        misc_raw = pd.read_parquet(misc_path)
    except Exception:
        logger.warning("Failed to read FBref misc file — defense fields will be NaN")
        for col in new_cols:
            matrix[col] = pd.NA
        return matrix

    if misc_raw.empty:
        for col in new_cols:
            matrix[col] = pd.NA
        return matrix

    # Reset MultiIndex to get flat columns
    # misc_raw has both a MultiIndex (league, season, team, player) and
    # a duplicate ('season', '') column, so reset_index() fails.
    # Use index.to_frame() instead.
    idx_df = misc_raw.index.to_frame(index=False)
    # Drop the duplicate ('season', '') column from data before combining
    data_cols = misc_raw.drop(
        columns=[c for c in misc_raw.columns if c == ("season", "")],
        errors="ignore",
    )
    misc_flat = pd.concat([idx_df, data_cols.reset_index(drop=True)], axis=1)

    # Build a clean DataFrame with mapped fields
    misc_clean = pd.DataFrame()
    misc_clean["player_name"] = misc_flat["player"].astype(str).str.strip()
    misc_clean["season_id"] = misc_flat["season"].astype(str).str.strip()
    misc_clean["competition_id"] = misc_flat["league"].astype(str).str.strip()

    for fbref_col, matrix_col in _FBREF_MISC_FIELD_MAP.items():
        if fbref_col in misc_flat.columns:
            misc_clean[matrix_col] = pd.to_numeric(misc_flat[fbref_col], errors="coerce")
        else:
            misc_clean[matrix_col] = pd.NA

    # Aggregate to player-season level (sum across teams if a player transferred)
    agg_fields = {col: "sum" for col in new_cols}
    agg_fields["competition_id"] = "first"
    misc_agg = misc_clean.groupby(["player_name", "season_id"], as_index=False).agg(agg_fields)

    # Merge onto matrix
    merge_keys = ["player_name", "season_id"]
    # Use left join to keep all existing rows; new columns NaN where no match
    matrix = matrix.merge(misc_agg, on=merge_keys, how="left", suffixes=("", "_misc"))

    # If merge created duplicate columns (e.g. competition_id_misc), drop them
    dup_cols = [c for c in matrix.columns if c.endswith("_misc")]
    if dup_cols:
        matrix = matrix.drop(columns=dup_cols)

    # Ensure numeric dtype for new columns
    for col in new_cols:
        if col in matrix.columns:
            matrix[col] = pd.to_numeric(matrix[col], errors="coerce")

    matched = matrix["tackles_won"].notna().sum() if "tackles_won" in matrix.columns else 0
    logger.info(
        "FBref misc defense merged: %d/%d rows matched (%.1f%%)",
        matched, len(matrix), 100 * matched / max(len(matrix), 1),
    )

    return matrix


def _compute_dataframe_hash(*dfs: pd.DataFrame) -> str:
    """Compute a SHA256 hash of DataFrame contents for reproducibility."""
    hasher = hashlib.sha256()
    for df in dfs:
        if df.empty:
            continue
        # Use parquet bytes for stable hashing
        try:
            hasher.update(df.to_parquet(index=False))
        except Exception:
            # Fallback: hash column names and row count
            hasher.update(",".join(df.columns).encode())
            hasher.update(str(len(df)).encode())
    return hasher.hexdigest()[:16]
