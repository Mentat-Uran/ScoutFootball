"""Dataset manifest writers for gold feature_store parquet artifacts.

Aligns with ``rating_feature_matrix_manifest.json`` schema (total_rows,
columns[name/dtype/source/missing_rate], input_hash, timestamp) and
extends it with:

- ``artifact``: logical name (e.g. ``team_match``).
- ``column_count``: explicit column count.
- ``schema_version``: manifest schema version (currently ``1.0``).
- ``source_lineage``: per-input-file name, relative path, row count and
  sha256[:16] hash. Lets consumers detect input drift without re-reading
  the underlying raw parquet bytes.
- ``source_breakdown`` (player_match only): per-source row counts, since
  player_match is the concatenation of statsbomb_open + fbref + understat.

Manifests are written next to the parquet file as ``{stem}_manifest.json``
and are intended for personal audit, reproducibility checks and
pre-training validation. They are NOT uploaded anywhere and do not modify
the parquet file itself.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

MANIFEST_SCHEMA_VERSION = "1.0"


# ---------------------------------------------------------------------------
# Column source categorization
# ---------------------------------------------------------------------------

# Team-match columns: grouped by conceptual role. ``source`` here means
# "where the column conceptually comes from" — mirroring the rating_feature_matrix
# manifest convention. All team_match columns are derived from football_data
# raw input, but the category tells consumers whether a NaN in e.g.
# ``goals_for`` is corruption (metric) vs expected (xg when source lacks it).
TEAM_MATCH_COLUMN_SOURCES: dict[str, str] = {
    # Identifiers
    "match_id": "identifier",
    "team_id": "identifier",
    "team_name": "identifier",
    "opponent_team_id": "identifier",
    "opponent_team_name": "identifier",
    # Temporal
    "match_date": "temporal",
    # Categorical
    "competition_id": "category",
    "season_id": "category",
    # Core match metrics (read from raw)
    "goals_for": "metric",
    "goals_against": "metric",
    "shots": "metric",
    "shots_on_target": "metric",
    "xg": "metric",
    "xg_against": "metric",
    # Derived metrics (computed from raw metrics)
    "goal_diff": "derived",
    "result_points": "derived",
    "xg_diff": "derived",
    "rest_days": "derived",
    # Elo (derived from external ClubElo input merged post-build)
    "elo_pre": "derived",
    "opponent_elo_pre": "derived",
    "elo_diff": "derived",
    # Boolean flags
    "is_home": "flag",
    "has_shots_data": "flag",
    "has_shots_on_target_data": "flag",
    "has_xg_data": "flag",
}

# Player-match columns: similar grouping. Note that ``source_name`` and
# ``data_granularity`` are meta columns recording which raw source a row
# came from, not measurements.
PLAYER_MATCH_COLUMN_SOURCES: dict[str, str] = {
    # Identifiers
    "match_id": "identifier",
    "player_id": "identifier",
    "player_name": "identifier",
    "team_id": "identifier",
    "team_name": "identifier",
    "opponent_team_id": "identifier",
    # Temporal
    "match_date": "temporal",
    # Categorical
    "competition_id": "category",
    "season_id": "category",
    "position_group": "category",
    # Core metrics (from raw)
    "minutes_played": "metric",
    "goals": "metric",
    "assists": "metric",
    "shots": "metric",
    "shots_on_target": "metric",
    "npxg": "metric",
    "xa": "metric",
    "passes": "metric",
    "tackles": "metric",
    "xT_added": "metric",
    "matches_played": "metric",
    # Boolean flags
    "started": "flag",
    "is_home": "flag",
    "has_expected_metrics": "flag",
    "has_ball_value_data": "flag",
    "multi_team_season": "flag",
    # Derived metrics (computed from raw metrics)
    "starts": "derived",
    "available_flag": "derived",
    "minutes_share": "derived",
    # Meta (source attribution, not measurements)
    "data_granularity": "meta",
    "source_name": "meta",
    "nation": "meta",
    "born": "meta",
}


# Team-rolling columns: inherits all team_match columns (the rolling
# builder copies team_match_df and appends windowed aggregates). Windowed
# columns (prior_matches_{w}, {stat}_{w}, points_per_match_{w},
# elo_pre_mean_{w}, rest_days_mean_{w}, etc.) are all leak-safe aggregates
# over prior matches and default to "derived" via build_manifest_payload's
# fallback. Only the inherited columns need explicit categories here.
TEAM_ROLLING_COLUMN_SOURCES: dict[str, str] = {
    **TEAM_MATCH_COLUMN_SOURCES,
}


# Player-rolling columns: inherits all player_match columns (the rolling
# builder copies player_match_df and appends windowed aggregates). The
# inherited ``source_name`` column is preserved, so player_rolling still
# carries multi-source attribution — ``source_breakdown`` is computed
# the same way as player_match. Windowed columns (prior_minutes_{w},
# {stat}_{w}, {stat}_p90_raw_{w}, {stat}_p90_shrunk_{w}, sot_rate_{w},
# shrink_factor_{w}, etc.) all default to "derived" via
# build_manifest_payload's fallback.
PLAYER_ROLLING_COLUMN_SOURCES: dict[str, str] = {
    **PLAYER_MATCH_COLUMN_SOURCES,
}


# ---------------------------------------------------------------------------
# Source lineage
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceLineageEntry:
    """Single input file lineage record.

    Parameters
    ----------
    name:
        Logical source name (e.g. ``football_data``, ``statsbomb_open``).
    relative_path:
        Path relative to ``settings.data_root``, forward-slashed for
        cross-platform stability.
    rows_read:
        Row count of the input file as observed during this build. May
        be ``None`` when the file was missing or unreadable.
    input_hash:
        sha256[:16] of the input file bytes. ``None`` when the file was
        missing.
    notes:
        Optional free-form note (e.g. filter applied before match_id).
    """

    name: str
    relative_path: str
    rows_read: int | None
    input_hash: str | None
    notes: str | None = None


def hash_file(path: Path) -> str | None:
    """Return sha256[:16] of *path* bytes, or None if the file is missing."""
    if not path.exists():
        return None
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()[:16]


def count_parquet_rows(path: Path) -> int | None:
    """Return parquet row count, or None if file missing/unreadable.

    Prefers reading parquet footer metadata via pyarrow (cheap, no content
    decode). Falls back to reading a single column, then to a full read.
    ``pd.read_parquet(path, columns=[])`` returns 0 rows on this pandas
    build and is NOT a valid row-count probe.
    """
    if not path.exists():
        return None

    # 1. Footer metadata via pyarrow (no content decode)
    try:
        import pyarrow.parquet as pq

        meta = pq.read_metadata(str(path))
        return int(meta.num_rows)
    except Exception:
        pass

    # 2. Read first column only
    try:
        df = pd.read_parquet(path)
        return int(len(df))
    except Exception as exc:
        logger.warning("Failed to count rows in %s: %s", path, exc)
        return None


def relative_to_data_root(path: Path, settings) -> str:
    """Return *path* relative to ``settings.data_root``, forward-slashed."""
    try:
        rel = path.resolve().relative_to(settings.data_root.resolve())
    except ValueError:
        # Fall back to absolute path if path is outside data_root.
        rel = Path(path)
    return str(rel).replace("\\", "/")


def extract_lineage_attrs(df: pd.DataFrame) -> tuple[
    list[SourceLineageEntry], str | None
]:
    """Pop ``_source_lineage`` and ``_input_hash`` from ``df.attrs``.

    Use this before ``df.to_parquet()`` to avoid pandas trying to
    JSON-serialize non-serializable ``SourceLineageEntry`` dataclass
    instances (which raises ``TypeError`` on some pandas builds and
    silently drops attrs on others). After extraction, the parquet
    writer sees an empty attrs dict and writes cleanly, while the
    manifest writer still receives the lineage via explicit parameters.

    Returns ``(lineage, input_hash)``. Missing keys return ``[]`` and
    ``None`` respectively, so callers can use the result unconditionally.
    """
    lineage = df.attrs.pop("_source_lineage", []) or []
    input_hash = df.attrs.pop("_input_hash", None)
    return list(lineage), input_hash


# ---------------------------------------------------------------------------
# DataFrame hashing
# ---------------------------------------------------------------------------


def compute_dataframe_hash(*dfs: pd.DataFrame) -> str:
    """Compute a SHA256 hash of DataFrame contents for reproducibility.

    Mirrors ``rating_matrix._compute_dataframe_hash`` but is exposed as a
    public helper so other feature modules can record input hashes without
    importing a private symbol.
    """
    hasher = hashlib.sha256()
    for df in dfs:
        if df is None or df.empty:
            continue
        try:
            hasher.update(df.to_parquet(index=False))
        except Exception:
            # Fallback: hash column names and row count
            hasher.update(",".join(map(str, df.columns)).encode())
            hasher.update(str(len(df)).encode())
    return hasher.hexdigest()[:16]


# ---------------------------------------------------------------------------
# Manifest payload + writer
# ---------------------------------------------------------------------------


def build_manifest_payload(
    df: pd.DataFrame,
    *,
    artifact_name: str,
    column_sources: dict[str, str],
    source_lineage: list[SourceLineageEntry],
    input_hash: str | None = None,
    extra: dict | None = None,
) -> dict:
    """Build a manifest dict aligned with ``rating_feature_matrix_manifest.json``.

    Aligned fields (present in both schemas):
        - ``total_rows``
        - ``columns`` (list of {name, dtype, source, missing_rate})
        - ``input_hash``
        - ``timestamp``

    Extended fields (this schema only):
        - ``artifact``: logical name
        - ``column_count``: explicit column count
        - ``schema_version``: manifest schema version
        - ``source_lineage``: per-input-file lineage

    Parameters
    ----------
    df:
        The DataFrame that was written to parquet. Manifest is built from
        its in-memory state.
    artifact_name:
        Logical artifact name (e.g. ``team_match``).
    column_sources:
        Mapping of column name -> source category. Columns not in the map
        default to ``"derived"``.
    source_lineage:
        List of input file lineage entries.
    input_hash:
        Optional combined input hash. If None, a hash of *df* itself is
        used as a fallback (matches the rating_feature_matrix behavior
        when ``matrix.attrs["_input_hash"]`` is absent).
    extra:
        Optional additional top-level fields (e.g. ``source_breakdown``).
    """
    columns_info: list[dict] = []
    for col in df.columns:
        source = column_sources.get(col, "derived")
        missing_rate = float(df[col].isna().mean()) if len(df) > 0 else 0.0
        columns_info.append({
            "name": str(col),
            "dtype": str(df[col].dtype),
            "source": source,
            "missing_rate": round(missing_rate, 4),
        })

    payload: dict = {
        "artifact": artifact_name,
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "total_rows": int(len(df)),
        "column_count": int(len(df.columns)),
        "columns": columns_info,
        "input_hash": input_hash if input_hash else compute_dataframe_hash(df),
        "source_lineage": [asdict(entry) for entry in source_lineage],
        "timestamp": datetime.now(tz=UTC).isoformat(),
    }
    if extra:
        for key, value in extra.items():
            if key not in payload:
                payload[key] = value
    return payload


def write_manifest(payload: dict, output_path: Path) -> Path:
    """Write *payload* as ``{stem}_manifest.json`` next to *output_path*.

    Returns the manifest path.
    """
    manifest_path = output_path.parent / f"{output_path.stem}_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    logger.info("Manifest written to %s", manifest_path)
    return manifest_path


def write_team_match_manifest(
    team_match: pd.DataFrame,
    output_path: Path,
    *,
    source_lineage: list[SourceLineageEntry] | None = None,
    input_hash: str | None = None,
) -> Path:
    """Write ``team_match_manifest.json`` next to *output_path*.

    Reads ``source_lineage`` and ``input_hash`` from ``team_match.attrs``
    when the parameters are None, so callers can either pass them
    explicitly or attach them to the DataFrame via ``df.attrs``.
    """
    lineage = source_lineage
    if lineage is None:
        lineage = team_match.attrs.get("_source_lineage", []) or []
    hash_value = input_hash
    if hash_value is None:
        hash_value = team_match.attrs.get("_input_hash")

    payload = build_manifest_payload(
        team_match,
        artifact_name="team_match",
        column_sources=TEAM_MATCH_COLUMN_SOURCES,
        source_lineage=lineage,
        input_hash=hash_value,
    )
    return write_manifest(payload, output_path)


def write_player_match_manifest(
    player_match: pd.DataFrame,
    output_path: Path,
    *,
    source_lineage: list[SourceLineageEntry] | None = None,
    input_hash: str | None = None,
) -> Path:
    """Write ``player_match_manifest.json`` next to *output_path*.

    Adds ``source_breakdown`` (per-source row counts) on top of the
    shared schema, since player_match is the concatenation of multiple
    raw sources.
    """
    lineage = source_lineage
    if lineage is None:
        lineage = player_match.attrs.get("_source_lineage", []) or []
    hash_value = input_hash
    if hash_value is None:
        hash_value = player_match.attrs.get("_input_hash")

    source_breakdown: dict[str, int] = {}
    if "source_name" in player_match.columns:
        counts = player_match["source_name"].value_counts(dropna=False)
        for key, value in counts.items():
            label = "unknown" if pd.isna(key) else str(key)
            source_breakdown[label] = int(value)

    extra: dict = {}
    if source_breakdown:
        extra["source_breakdown"] = source_breakdown

    payload = build_manifest_payload(
        player_match,
        artifact_name="player_match",
        column_sources=PLAYER_MATCH_COLUMN_SOURCES,
        source_lineage=lineage,
        input_hash=hash_value,
        extra=extra,
    )
    return write_manifest(payload, output_path)


def write_team_rolling_manifest(
    team_rolling: pd.DataFrame,
    output_path: Path,
    *,
    source_lineage: list[SourceLineageEntry] | None = None,
    input_hash: str | None = None,
) -> Path:
    """Write ``team_rolling_manifest.json`` next to *output_path*.

    ``team_rolling`` is built from ``team_match`` via leak-safe grouped
    rolling sums/means; its manifest records ``team_match.parquet`` as
    the single upstream lineage entry, closing the
    ``rating_feature_matrix -> team_rolling -> team_match -> raw``
    provenance chain. Windowed columns default to ``"derived"`` via
    ``build_manifest_payload``'s fallback.
    """
    lineage = source_lineage
    if lineage is None:
        lineage = team_rolling.attrs.get("_source_lineage", []) or []
    hash_value = input_hash
    if hash_value is None:
        hash_value = team_rolling.attrs.get("_input_hash")

    payload = build_manifest_payload(
        team_rolling,
        artifact_name="team_rolling",
        column_sources=TEAM_ROLLING_COLUMN_SOURCES,
        source_lineage=lineage,
        input_hash=hash_value,
    )
    return write_manifest(payload, output_path)


def write_player_rolling_manifest(
    player_rolling: pd.DataFrame,
    output_path: Path,
    *,
    source_lineage: list[SourceLineageEntry] | None = None,
    input_hash: str | None = None,
) -> Path:
    """Write ``player_rolling_manifest.json`` next to *output_path*.

    ``player_rolling`` is built from ``player_match`` via leak-safe
    grouped rolling sums/means; its manifest records
    ``player_match.parquet`` as the single upstream lineage entry,
    closing the ``rating_feature_matrix -> player_rolling -> player_match
    -> raw`` provenance chain. The inherited ``source_name`` column is
    preserved, so ``source_breakdown`` is computed the same way as
    ``player_match`` (per-source row counts).
    """
    lineage = source_lineage
    if lineage is None:
        lineage = player_rolling.attrs.get("_source_lineage", []) or []
    hash_value = input_hash
    if hash_value is None:
        hash_value = player_rolling.attrs.get("_input_hash")

    source_breakdown: dict[str, int] = {}
    if "source_name" in player_rolling.columns:
        counts = player_rolling["source_name"].value_counts(dropna=False)
        for key, value in counts.items():
            label = "unknown" if pd.isna(key) else str(key)
            source_breakdown[label] = int(value)

    extra: dict = {}
    if source_breakdown:
        extra["source_breakdown"] = source_breakdown

    payload = build_manifest_payload(
        player_rolling,
        artifact_name="player_rolling",
        column_sources=PLAYER_ROLLING_COLUMN_SOURCES,
        source_lineage=lineage,
        input_hash=hash_value,
        extra=extra,
    )
    return write_manifest(payload, output_path)


def load_manifest(manifest_path: Path) -> dict:
    """Load a manifest JSON file. Used by tests and consumers."""
    with open(manifest_path, encoding="utf-8") as f:
        return json.load(f)
