"""Rating feature matrix builder with missing field handling."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import pandas as pd

from scoutfootball.features.manifest import (
    SourceLineageEntry,
    build_manifest_payload,
)

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
    "xT_VAEP": ["xt_total", "xt_per_90", "vaep_total", "vaep_per_90"],
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
    "xt_total",
    "xt_per_90",
    "vaep_total",
    "vaep_per_90",
]

# Category columns to include in the rating matrix.
RATING_CATEGORY_COLUMNS: list[str] = [
    "position_group",
    "competition_id",
    "season_id",
]

# Column source categories for rating_feature_matrix_manifest.json.
# Mirrors the source-category approach in features.manifest for
# team_match/player_match, so all three gold feature_store manifests
# share a consistent column-source vocabulary. Columns not in this map
# default to "derived" inside build_manifest_payload.
RATING_MATRIX_COLUMN_SOURCES: dict[str, str] = {
    # Identifiers and temporal keys.
    "player_id": "identifier",
    "season_id": "temporal",
    "competition_id": "category",
    # Player-profile categories.
    "position_group": "category",
    # Core match metrics (player_stats).
    "goals": "metric",
    "assists": "metric",
    "shots": "metric",
    "shots_on_target": "metric",
    "npxg": "metric",
    "xa": "metric",
    "minutes_played": "metric",
    "starts": "metric",
    "available_flag": "flag",
    # Defensive and possession metrics (FBref misc).
    "tackles": "metric",
    "passes": "metric",
    "tackles_won": "metric",
    "interceptions": "metric",
    "fouls_committed": "metric",
    "fouls_drawn": "metric",
    "crosses": "metric",
    "own_goals": "metric",
    # Action-value metrics (xT/VAEP).
    "xT_added": "metric",
    "xt_total": "metric",
    "xt_per_90": "metric",
    "vaep_total": "metric",
    "vaep_per_90": "metric",
    # Missing-field and source-coverage flags written by the rating
    # matrix builder itself (not read from any external source).
}

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

    # --- Merge xT and VAEP action-value data ---
    matrix = _merge_xt_vaep_data(matrix)

    # --- Re-evaluate defense_missing after misc merge ---
    # The initial mark_missing_fields ran before misc data was available,
    # so defense_missing may be True even though misc fields now have data.
    defense_fields = FIELD_GROUPS.get("defense", [])
    existing_defense = [f for f in defense_fields if f in matrix.columns]
    if existing_defense:
        matrix["defense_missing"] = matrix[existing_defense].isna().all(axis=1)
    else:
        matrix["defense_missing"] = True

    # --- Re-evaluate xT_VAEP_missing after action-value merge ---
    xt_vaep_fields = FIELD_GROUPS.get("xT_VAEP", [])
    existing_xt_vaep = [f for f in xt_vaep_fields if f in matrix.columns]
    if existing_xt_vaep:
        matrix["xT_VAEP_missing"] = matrix[existing_xt_vaep].isna().all(axis=1)
    else:
        matrix["xT_VAEP_missing"] = True

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
    *,
    source_lineage: list[SourceLineageEntry] | None = None,
    input_hash: str | None = None,
) -> None:
    """Write a JSON manifest alongside the rating feature matrix parquet.

    The manifest aligns with the new schema used by
    ``features.manifest.write_team_match_manifest`` and
    ``write_player_match_manifest``: ``artifact``, ``schema_version``,
    ``total_rows``, ``column_count``, ``columns``, ``input_hash``,
    ``source_lineage``, ``timestamp``. Legacy manifests written by
    previous versions of this function (which lacked ``artifact``,
    ``schema_version``, ``column_count`` and ``source_lineage``) are
    forward-compatible — consumers that only read ``total_rows`` /
    ``columns`` / ``input_hash`` / ``timestamp`` continue to work.

    Parameters
    ----------
    matrix : pd.DataFrame
        The rating feature matrix that was saved as parquet.
    output_path : Path
        Path where the parquet file was written. The manifest will be
        written as ``{stem}_manifest.json`` in the same directory.
    source_lineage:
        Per-input-file lineage entries. If None, reads from
        ``matrix.attrs["_source_lineage"]`` (matching
        ``write_team_match_manifest`` behavior). Pass explicitly when
        the caller has popped attrs before ``to_parquet`` to avoid
        pandas JSON-serialization of ``SourceLineageEntry`` dataclasses.
    input_hash:
        Combined input hash. If None, reads from
        ``matrix.attrs["_input_hash"]``; falls back to
        ``compute_dataframe_hash(matrix)`` when absent.
    """
    # Per-column source category. Precedence (matching the legacy
    # behavior callers may rely on): explicit suffix markers first, then
    # the RATING_MATRIX_COLUMN_SOURCES map, then fallback to "derived".
    column_sources: dict[str, str] = dict(RATING_MATRIX_COLUMN_SOURCES)
    for col in matrix.columns:
        if col.endswith("_missing"):
            column_sources[col] = "missing_marker"
        elif col.endswith("_source_covered"):
            column_sources[col] = "source_coverage"

    if source_lineage is None:
        source_lineage = matrix.attrs.get("_source_lineage", []) or []
    if input_hash is None:
        input_hash = matrix.attrs.get("_input_hash")

    payload = build_manifest_payload(
        matrix,
        artifact_name="rating_feature_matrix",
        column_sources=column_sources,
        source_lineage=source_lineage,
        input_hash=input_hash,
    )
    manifest_path = output_path.parent / f"{output_path.stem}_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

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


def _merge_xt_vaep_data(matrix: pd.DataFrame) -> pd.DataFrame:
    """Merge xT and VAEP action-value data into the rating feature matrix.

    Reads ``player_action_value.parquet`` (xT) and ``player_vaep.parquet``,
    extracts relevant fields, and merges them onto *matrix* using
    normalized player_name + season_id as keys.

    If the files are missing or empty, the new columns are added as NaN.
    """
    from scoutfootball.config import PlatformSettings
    from scoutfootball.entities.normalize import normalize_person_name

    resolved = PlatformSettings.from_root()
    xt_path = resolved.gold_root / "feature_store" / "player_action_value.parquet"
    vaep_path = resolved.gold_root / "feature_store" / "player_vaep.parquet"

    new_cols = ["xt_total", "xt_per_90", "vaep_total", "vaep_per_90"]

    # Build normalized player_name for matrix from player_id
    # player_id format: "name|year|country" — extract name part
    def _extract_name_from_pid(pid: str) -> str:
        return str(pid).split("|")[0].strip()

    matrix["_norm_name"] = matrix["player_id"].apply(
        lambda x: normalize_person_name(_extract_name_from_pid(str(x))),
    )

    # --- Merge xT data ---
    if xt_path.exists():
        try:
            xt_raw = pd.read_parquet(xt_path)
            if not xt_raw.empty and "player_name" in xt_raw.columns:
                xt_clean = pd.DataFrame()
                xt_clean["_norm_name"] = xt_raw["player_name"].apply(
                    lambda x: normalize_person_name(str(x)),
                )
                if "season" in xt_raw.columns:
                    # Convert "2022/2023" -> "2223" format
                    def _convert_season(s: str) -> str:
                        s = str(s).strip()
                        if "/" in s:
                            parts = s.split("/")
                            return parts[0][-2:] + parts[1][-2:]
                        return s
                    xt_clean["season_id"] = xt_raw["season"].apply(_convert_season)
                xt_clean["xt_total"] = pd.to_numeric(xt_raw.get("xt_total"), errors="coerce")
                xt_clean["xt_per_90"] = pd.to_numeric(xt_raw.get("xt_per_90"), errors="coerce")

                if "season_id" in xt_clean.columns:
                    xt_agg = xt_clean.groupby(["_norm_name", "season_id"], as_index=False).agg(
                        {"xt_total": "sum", "xt_per_90": "mean"},
                    )
                    matrix = matrix.merge(
                        xt_agg, on=["_norm_name", "season_id"],
                        how="left", suffixes=("", "_xt"),
                    )
                else:
                    xt_agg = xt_clean.groupby("_norm_name", as_index=False).agg(
                        {"xt_total": "sum", "xt_per_90": "mean"},
                    )
                    matrix = matrix.merge(xt_agg, on="_norm_name", how="left", suffixes=("", "_xt"))
                # Drop duplicate columns from merge
                dup_cols = [c for c in matrix.columns if c.endswith("_xt")]
                if dup_cols:
                    matrix = matrix.drop(columns=dup_cols)
            else:
                matrix["xt_total"] = pd.NA
                matrix["xt_per_90"] = pd.NA
        except Exception:
            logger.warning("Failed to read xT action-value file — xT fields will be NaN")
            matrix["xt_total"] = pd.NA
            matrix["xt_per_90"] = pd.NA
    else:
        logger.warning("xT action-value file not found: %s — xT fields will be NaN", xt_path)
        matrix["xt_total"] = pd.NA
        matrix["xt_per_90"] = pd.NA

    # --- Merge VAEP data ---
    # VAEP player_name is empty; use xT data as bridge to map StatsBomb player_id -> normalized name
    sb_id_to_norm_name: dict[str, str] = {}
    if xt_path.exists():
        try:
            xt_raw = pd.read_parquet(xt_path)
            if not xt_raw.empty and "player_name" in xt_raw.columns:
                xt_names = xt_raw[["player_id", "player_name"]].drop_duplicates()
                for _, row in xt_names.iterrows():
                    pid = str(row["player_id"]).strip()
                    norm = normalize_person_name(str(row["player_name"]))
                    if norm and pid not in sb_id_to_norm_name:
                        sb_id_to_norm_name[pid] = norm
        except Exception:
            pass

    if vaep_path.exists():
        try:
            vaep_raw = pd.read_parquet(vaep_path)
            if not vaep_raw.empty and "player_id" in vaep_raw.columns:
                vaep_clean = pd.DataFrame()
                # Map StatsBomb player_id to normalized name via xT bridge
                vaep_clean["_norm_name"] = vaep_raw["player_id"].apply(
                    lambda x: sb_id_to_norm_name.get(str(x).strip(), ""),
                )
                vaep_clean["vaep_total"] = pd.to_numeric(
                    vaep_raw.get("vaep_total"), errors="coerce",
                )
                vaep_clean["vaep_per_90"] = pd.to_numeric(
                    vaep_raw.get("vaep_per_90"), errors="coerce",
                )

                # Drop rows where name mapping failed
                vaep_clean = vaep_clean[vaep_clean["_norm_name"] != ""]

                # VAEP has no season column; aggregate to player level
                vaep_agg = vaep_clean.groupby("_norm_name", as_index=False).agg(
                    {"vaep_total": "sum", "vaep_per_90": "mean"},
                )
                matrix = matrix.merge(vaep_agg, on="_norm_name", how="left", suffixes=("", "_vaep"))
                dup_cols = [c for c in matrix.columns if c.endswith("_vaep")]
                if dup_cols:
                    matrix = matrix.drop(columns=dup_cols)
            else:
                matrix["vaep_total"] = pd.NA
                matrix["vaep_per_90"] = pd.NA
        except Exception:
            logger.warning("Failed to read VAEP file — VAEP fields will be NaN")
            matrix["vaep_total"] = pd.NA
            matrix["vaep_per_90"] = pd.NA
    else:
        logger.warning("VAEP file not found: %s — VAEP fields will be NaN", vaep_path)
        matrix["vaep_total"] = pd.NA
        matrix["vaep_per_90"] = pd.NA

    # Clean up temp column
    matrix = matrix.drop(columns=["_norm_name"])

    # Ensure numeric dtype for new columns
    for col in new_cols:
        if col in matrix.columns:
            matrix[col] = pd.to_numeric(matrix[col], errors="coerce")

    xt_matched = matrix["xt_total"].notna().sum() if "xt_total" in matrix.columns else 0
    vaep_matched = matrix["vaep_total"].notna().sum() if "vaep_total" in matrix.columns else 0
    logger.info(
        "xT/VAEP merged: xT %d/%d rows (%.1f%%), VAEP %d/%d rows (%.1f%%)",
        xt_matched, len(matrix), 100 * xt_matched / max(len(matrix), 1),
        vaep_matched, len(matrix), 100 * vaep_matched / max(len(matrix), 1),
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
