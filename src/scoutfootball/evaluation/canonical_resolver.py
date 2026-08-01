"""Canonical player ID resolver for the player rating research system.

PRS-1 R-005 (see ``docs/PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md``) requires that
``canonical_player_id`` runs through every rating artifact. The identity
registry (``evaluation/identity_registry.py``) is the append-only ledger where
the maintainer records explicit human decisions of the form::

    (source_name, source_player_id) -> canonical_player_id

This module is the read-only resolver that applies those decisions to a
**derived view** of ``player_match.parquet``. It does **not** modify the
original parquet, does **not** auto-align sources, and does **not** silently
promote a source-specific ID to canonical status.

Resolution rules (in order):

1. If ``(source_name, source_player_id)`` has an active ``confirmed`` mapping
   in the registry, use the recorded ``canonical_player_id``.
2. If the pair is unresolved (no record, or the most recent record was
   ``revoked``), emit the explicit marker
   ``unresolved:<source_name>:<source_player_id>``. This is the
   source-stable fallback: it is deterministic, traceable, and makes the
   unresolved state visible in every downstream artifact instead of
   hiding it behind a source-specific ID.
3. If ``source_name`` or ``source_player_id`` is missing on a row, emit
   ``unresolved:unknown:missing`` (or ``unresolved:<source>:missing`` /
   ``unresolved:unknown:<id>`` when only one side is missing). This is a
   defensive fallback — current builders always populate both columns, but
   the resolver must not crash on a malformed row.

The business key in the registry is the stable pair
``(source_name, source_player_id)`` where ``source_player_id`` is the
``player_id`` value stored in ``player_match.parquet`` (e.g.
``understat|12345`` or ``lara|1998|ar``). The CLI
``identity-registry-append --source-id`` documents this contract.

This module is read-only and side-effect-free. ``resolve_canonical_ids`` is
a pure function on a DataFrame; ``build_canonical_resolution_report`` and
``load_resolved_player_match`` are the only I/O entry points.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from scoutfootball.config import PlatformSettings

CANONICAL_RESOLVER_SCHEMA = "scoutfootball.canonical-resolver"
CANONICAL_RESOLVER_VERSION = "1.0.0"

UNRESOLVED_PREFIX = "unresolved"
UNRESOLVED_UNKNOWN_SOURCE = "unknown"
UNRESOLVED_MISSING_ID = "missing"

DEFAULT_SOURCE_NAME_COL = "source_name"
DEFAULT_SOURCE_PLAYER_ID_COL = "player_id"
DEFAULT_CANONICAL_COL = "canonical_player_id"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def unresolved_canonical_id(source_name: str, source_player_id: str) -> str:
    """Build the explicit unresolved marker for one source ID.

    The marker is ``unresolved:<source_name>:<source_player_id>``. It is
    deterministic and source-stable: the same source ID always produces the
    same marker, so unresolved rows can be grouped and counted without
    being silently merged with resolved canonical IDs.
    """
    return f"{UNRESOLVED_PREFIX}:{source_name}:{source_player_id}"


def is_unresolved(canonical_player_id: Any) -> bool:
    """Return True if a ``canonical_player_id`` value is an unresolved marker.

    Non-string and missing values return False; callers that need to detect
    missing values separately should check ``isna()`` first.
    """
    if not isinstance(canonical_player_id, str):
        return False
    return canonical_player_id.startswith(f"{UNRESOLVED_PREFIX}:")


def _coerce_str(value: Any) -> str | None:
    """Return the value as a non-empty str, or None if missing/NaN/empty."""
    if value is None:
        return None
    if isinstance(value, str):
        return value if value else None
    # pandas NaN is a float; bools are not valid IDs.
    if isinstance(value, bool):
        return None
    if isinstance(value, float):
        # NaN check without importing numpy
        if value != value:  # pragma: no cover — NaN guard
            return None
        # Numeric IDs (e.g. StatsBomb int stored as float) are coerced to
        # str so the registry lookup matches the player_id column value
        # produced by the pipeline (which str-coerces everything).
        if value.is_integer():
            return str(int(value))
        return str(value)
    if isinstance(value, int):
        return str(value)
    return str(value) if value else None


def resolve_canonical_ids(
    df: Any,
    records: list[dict[str, Any]],
    *,
    source_name_col: str = DEFAULT_SOURCE_NAME_COL,
    source_player_id_col: str = DEFAULT_SOURCE_PLAYER_ID_COL,
    canonical_col: str = DEFAULT_CANONICAL_COL,
) -> Any:
    """Add a ``canonical_player_id`` column to a derived copy of ``df``.

    Returns a new DataFrame; the input is never mutated. Raises
    ``ValueError`` if the input already has a column named ``canonical_col``
    (the caller must drop it first — the resolver never silently overwrites
    an existing canonical decision).

    ``records`` is the list returned by ``identity_registry.read_registry``.
    The resolver builds an ``active_canonical_map`` from it once and looks
    up each row's ``(source_name, source_player_id)`` pair.
    """
    import pandas as pd

    from scoutfootball.evaluation.identity_registry import active_canonical_map

    if canonical_col in df.columns:
        raise ValueError(
            f"canonical_resolver_input_already_has_column:{canonical_col}"
        )

    active = active_canonical_map(records)
    out = df.copy()

    has_source_col = source_name_col in out.columns
    has_id_col = source_player_id_col in out.columns

    if not has_source_col and not has_id_col:
        # Both key columns missing — every row is unresolved:unknown:missing.
        out[canonical_col] = unresolved_canonical_id(
            UNRESOLVED_UNKNOWN_SOURCE, UNRESOLVED_MISSING_ID
        )
        return out

    source_series = out[source_name_col] if has_source_col else None
    id_series = out[source_player_id_col] if has_id_col else None

    canonical_values: list[str] = []
    for pos in range(len(out)):
        sn_raw = source_series.iloc[pos] if source_series is not None else None
        spid_raw = id_series.iloc[pos] if id_series is not None else None
        sn = _coerce_str(sn_raw)
        spid = _coerce_str(spid_raw)
        if sn is None and spid is None:
            canonical_values.append(
                unresolved_canonical_id(UNRESOLVED_UNKNOWN_SOURCE, UNRESOLVED_MISSING_ID)
            )
        elif sn is None:
            canonical_values.append(
                unresolved_canonical_id(UNRESOLVED_UNKNOWN_SOURCE, spid)  # type: ignore[arg-type]
            )
        elif spid is None:
            canonical_values.append(
                unresolved_canonical_id(sn, UNRESOLVED_MISSING_ID)  # type: ignore[arg-type]
            )
        else:
            mapped = active.get((sn, spid))
            if mapped is not None:
                canonical_values.append(mapped)
            else:
                canonical_values.append(unresolved_canonical_id(sn, spid))

    out[canonical_col] = pd.Series(canonical_values, index=out.index, dtype="object")
    return out


def resolution_summary(
    df: Any,
    *,
    canonical_col: str = DEFAULT_CANONICAL_COL,
    source_name_col: str = DEFAULT_SOURCE_NAME_COL,
) -> dict[str, Any]:
    """Return a read-only summary of canonical resolution in ``df``.

    ``df`` must already have the ``canonical_col`` (typically produced by
    ``resolve_canonical_ids``). The summary reports resolved vs unresolved
    row counts, distinct canonical IDs, distinct unresolved markers, and a
    per-source breakdown.
    """
    total_rows = int(len(df))
    if canonical_col not in df.columns:
        return {
            "status": "unavailable",
            "evidence": {"reason": f"{canonical_col} column missing"},
        }
    if total_rows == 0:
        return {
            "total_rows": 0,
            "resolved_rows": 0,
            "unresolved_rows": 0,
            "distinct_canonical_ids": 0,
            "distinct_unresolved_markers": 0,
            "by_source": {},
        }

    unresolved_mask = df[canonical_col].apply(is_unresolved)
    resolved_mask = ~unresolved_mask
    resolved_rows = int(resolved_mask.sum())
    unresolved_rows = int(unresolved_mask.sum())
    distinct_canonical = int(df.loc[resolved_mask, canonical_col].nunique())
    distinct_unresolved = int(df.loc[unresolved_mask, canonical_col].nunique())

    by_source: dict[str, dict[str, int]] = {}
    if source_name_col in df.columns:
        for source, group in df.groupby(source_name_col, dropna=False):
            source_str = _coerce_str(source) or UNRESOLVED_UNKNOWN_SOURCE
            group_unresolved = int(group[canonical_col].apply(is_unresolved).sum())
            group_resolved = int(len(group) - group_unresolved)
            by_source[source_str] = {
                "resolved": group_resolved,
                "unresolved": group_unresolved,
            }

    return {
        "total_rows": total_rows,
        "resolved_rows": resolved_rows,
        "unresolved_rows": unresolved_rows,
        "distinct_canonical_ids": distinct_canonical,
        "distinct_unresolved_markers": distinct_unresolved,
        "by_source": by_source,
    }


def _player_match_path(settings: PlatformSettings):
    return settings.gold_root / "feature_store" / "player_match.parquet"


def _read_player_match(settings: PlatformSettings):
    """Read player_match.parquet; return (df, error_message)."""
    path = _player_match_path(settings)
    if not path.exists():
        return None, "player_match.parquet missing"
    try:
        import pandas as pd

        df = pd.read_parquet(path)
    except Exception as exc:  # noqa: BLE001 — read-only diagnostic
        return None, f"player_match.parquet read failed: {exc}"
    if df is None or len(df) == 0:
        return None, "player_match.parquet has 0 rows"
    return df, None


def _player_ratings_path(settings: PlatformSettings):
    """Path to the legacy optimized ratings parquet."""
    return settings.gold_root / "feature_store" / "player_ratings_optimized.parquet"


def _read_player_ratings(settings: PlatformSettings):
    """Read player_ratings_optimized.parquet; return (df, error_message)."""
    path = _player_ratings_path(settings)
    if not path.exists():
        return None, "player_ratings_optimized.parquet missing"
    try:
        import pandas as pd

        df = pd.read_parquet(path)
    except Exception as exc:  # noqa: BLE001 — read-only diagnostic
        return None, f"player_ratings_optimized.parquet read failed: {exc}"
    if df is None or len(df) == 0:
        return None, "player_ratings_optimized.parquet has 0 rows"
    return df, None


def load_resolved_player_match(
    settings: PlatformSettings | None = None,
) -> Any:
    """Load ``player_match.parquet`` and return a resolved view.

    The returned DataFrame is a copy with a ``canonical_player_id`` column
    added by applying the identity registry's active mappings. The original
    parquet is never modified.

    Raises ``ValueError`` if ``player_match.parquet`` is missing, empty or
    unreadable, or if the registry is corrupt. Callers that prefer a
    non-raising path should use ``build_canonical_resolution_report``.
    """
    from scoutfootball.evaluation.identity_registry import read_registry

    resolved = settings or PlatformSettings.from_root()
    df, error = _read_player_match(resolved)
    if df is None:
        raise ValueError(f"canonical_resolver_load_failed:{error}")
    records = read_registry(settings=resolved)
    return resolve_canonical_ids(df, records)


def load_resolved_player_ratings(
    settings: PlatformSettings | None = None,
    ratings_df: Any | None = None,
) -> Any:
    """Load a legacy ratings frame and return a resolved view.

    The returned DataFrame is a copy of the legacy ratings table with
    ``player_id``, ``source_name``, ``canonical_player_id`` and
    ``canonical_match_ambiguous`` columns added. The original parquet is
    never modified.

    PRS-1 R-005 requires that ``canonical_player_id`` runs through every
    rating artifact. The legacy ratings table does not carry ``player_id``
    or ``source_name`` (it only has the human-readable ``player`` column),
    so this function recovers the source key pair by joining to
    ``player_match.parquet`` on ``(player, season)`` →
    ``(player_name, season_id)`` and then applying the identity registry's
    active mappings via ``resolve_canonical_ids``.

    When multiple ``player_match`` rows match the same
    ``(player_name, season_id)`` (the same-name aliasing risk documented in
    the PRS-1 identity audit), the first match is used for the source key
    and the row is flagged with ``canonical_match_ambiguous=True`` so
    downstream consumers can detect the aliasing risk instead of trusting
    the canonical ID silently. Rows without any match get
    ``player_id=None``, ``source_name=None`` and
    ``canonical_player_id=unresolved:unknown:missing`` (the defensive
    fallback in ``resolve_canonical_ids``).

    When ``ratings_df`` is omitted, the frame is loaded from
    ``player_ratings_optimized.parquet``. Callers that already loaded or
    filtered the frame may pass it explicitly; it is copied before any
    derived columns are added. This keeps the API path on the same resolver
    contract without reading the ratings artifact twice.

    Raises ``ValueError`` if the ratings frame is missing, empty or unreadable.
    A missing or unreadable
    ``player_match.parquet`` is not fatal: every row gets
    ``canonical_player_id=unresolved:unknown:missing`` so the legacy
    ratings table is still honest about its unresolved state.
    """
    import pandas as pd

    from scoutfootball.evaluation.identity_registry import read_registry

    resolved = settings or PlatformSettings.from_root()
    if ratings_df is None:
        ratings_df, error = _read_player_ratings(resolved)
        if ratings_df is None:
            raise ValueError(f"canonical_resolver_load_failed:{error}")
    else:
        if not isinstance(ratings_df, pd.DataFrame):
            raise ValueError("canonical_resolver_ratings_frame_invalid")
        ratings_df = ratings_df.copy()
        if ratings_df.empty:
            raise ValueError("canonical_resolver_load_failed:player ratings has 0 rows")

    # Defensive: if the ratings table already carries a canonical_player_id
    # column, the caller must drop it first. The resolver never silently
    # overwrites an existing canonical decision.
    if DEFAULT_CANONICAL_COL in ratings_df.columns:
        raise ValueError(
            "canonical_resolver_input_already_has_column:"
            f"{DEFAULT_CANONICAL_COL}"
        )

    pm_df, pm_error = _read_player_match(resolved)

    if pm_df is None:
        # No player_match — every row gets unresolved:unknown:missing.
        # This is the honest fallback: we cannot recover the source key
        # without player_match, so we do not pretend to.
        ratings_df[DEFAULT_SOURCE_PLAYER_ID_COL] = None
        ratings_df[DEFAULT_SOURCE_NAME_COL] = None
        ratings_df["canonical_match_ambiguous"] = False
        records = read_registry(settings=resolved)
        return resolve_canonical_ids(ratings_df, records)

    # Build (player_name, season_id) → (player_id, source_name, match_count)
    # map from player_match. We only need the key columns; drop NaN keys
    # so they do not produce false matches.
    pm_keys = pm_df[
        ["player_name", "season_id", DEFAULT_SOURCE_PLAYER_ID_COL, DEFAULT_SOURCE_NAME_COL]
    ].copy()
    pm_keys["player_name"] = pm_keys["player_name"].astype(str)
    pm_keys["season_id"] = pm_keys["season_id"].astype(str)
    pm_keys = pm_keys.replace({"nan": pd.NA})
    pm_keys = pm_keys.dropna(subset=["player_name", "season_id"])

    pm_grouped = pm_keys.groupby(["player_name", "season_id"], observed=True)
    pm_first = pm_grouped.first().reset_index()
    pm_counts = pm_grouped.size().reset_index(name="_pm_match_count")
    pm_map = pm_first.merge(pm_counts, on=["player_name", "season_id"])

    # Join ratings to the player_match map. The ratings table uses
    # ``player`` + ``season`` as the human-readable key; player_match uses
    # ``player_name`` + ``season_id``. We normalise both to strings so
    # numeric season IDs (e.g. 2021) match their string counterparts.
    out = ratings_df.copy()
    out["player"] = out["player"].astype(str)
    out["season"] = out["season"].astype(str)
    out = out.replace({"nan": pd.NA})

    out = out.merge(
        pm_map[
            [
                "player_name",
                "season_id",
                DEFAULT_SOURCE_PLAYER_ID_COL,
                DEFAULT_SOURCE_NAME_COL,
                "_pm_match_count",
            ]
        ],
        left_on=["player", "season"],
        right_on=["player_name", "season_id"],
        how="left",
    )

    # Flag ambiguous matches (multiple player_ids for same player_name +
    # season). The first match was used for the source key; downstream
    # consumers must not trust the canonical ID silently on these rows.
    out["canonical_match_ambiguous"] = out["_pm_match_count"].fillna(0).gt(1)

    # Drop the join helper columns; keep player_id and source_name so
    # resolve_canonical_ids can use them as the business key.
    out = out.drop(
        columns=["player_name", "season_id", "_pm_match_count"],
        errors="ignore",
    )

    records = read_registry(settings=resolved)
    return resolve_canonical_ids(out, records)


def build_canonical_resolution_report(
    settings: PlatformSettings | None = None,
) -> dict[str, Any]:
    """Read-only audit: resolve ``player_match.parquet`` against the registry.

    Returns a dict suitable for inclusion in the research-health report.
    Never raises — on any read failure returns ``status=unavailable`` with
    the reason in ``evidence``. An all-unresolved result is ``status=ok``
    because unresolved is the honest default, not a failure.
    """
    from scoutfootball.evaluation.identity_registry import read_registry

    resolved = settings or PlatformSettings.from_root()
    df, error = _read_player_match(resolved)
    if df is None:
        return {
            "schema": CANONICAL_RESOLVER_SCHEMA,
            "schema_version": CANONICAL_RESOLVER_VERSION,
            "generated_at": _now(),
            "status": "unavailable",
            "evidence": {"reason": error},
        }

    try:
        records = read_registry(settings=resolved)
    except Exception as exc:  # read-only diagnostic; never raise
        return {
            "schema": CANONICAL_RESOLVER_SCHEMA,
            "schema_version": CANONICAL_RESOLVER_VERSION,
            "generated_at": _now(),
            "status": "unavailable",
            "evidence": {"reason": f"identity registry read failed: {exc}"},
        }

    try:
        resolved_df = resolve_canonical_ids(df, records)
        summary = resolution_summary(resolved_df)
    except Exception as exc:  # noqa: BLE001 — read-only diagnostic
        return {
            "schema": CANONICAL_RESOLVER_SCHEMA,
            "schema_version": CANONICAL_RESOLVER_VERSION,
            "generated_at": _now(),
            "status": "unavailable",
            "evidence": {"reason": f"resolve failed: {exc}"},
        }

    return {
        "schema": CANONICAL_RESOLVER_SCHEMA,
        "schema_version": CANONICAL_RESOLVER_VERSION,
        "generated_at": _now(),
        "status": "ok",
        "evidence": summary,
    }


__all__ = [
    "CANONICAL_RESOLVER_SCHEMA",
    "CANONICAL_RESOLVER_VERSION",
    "DEFAULT_CANONICAL_COL",
    "DEFAULT_SOURCE_NAME_COL",
    "DEFAULT_SOURCE_PLAYER_ID_COL",
    "UNRESOLVED_PREFIX",
    "build_canonical_resolution_report",
    "is_unresolved",
    "load_resolved_player_match",
    "load_resolved_player_ratings",
    "resolution_summary",
    "resolve_canonical_ids",
    "unresolved_canonical_id",
]
