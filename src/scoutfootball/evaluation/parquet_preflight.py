"""Content-level Parquet preflight checks.

Resolves the "footer says N rows but content won't decode" truth conflicts
documented in ``AGENTS.md``. Existing ``validation.py`` only checks file
existence and ``len(pd.read_parquet(path))``; it does not separate footer
metadata from a real content decode, does not capture schema/dtype, and does
not fingerprint files for cross-run reproducibility. This module fills that
gap for the local-first, personal, non-commercial ScoutFootball project.

Design points:

- DuckDB is the primary reader (already a project dependency). A pandas
  fallback is attempted only when DuckDB cannot open the file, so that
  reader disagreement is itself surfaced as a signal rather than hidden.
- Footer metadata (row-group count, footer-declared row count, column
  names) is captured separately from the content decode. A mismatch
  between the two is reported as ``footer_content_mismatch``.
- ``content_hash`` is a lightweight fingerprint (sha256 of canonical
  row_count + sorted columns + dtypes + null counts) — enough to detect
  content drift across runs without hashing every byte.
- Quarantine is opt-in and reversible: unreadable files are moved to
  ``data/quarantine/`` with a sidecar manifest. By default the tool only
  reports. Moving user data is never done silently.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from scoutfootball.config import PlatformSettings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParquetPreflightReport:
    """Content-level inspection result for a single Parquet file.

    ``footer_*`` fields come from parquet metadata (cheap, footer-only).
    ``row_count`` / ``columns`` / ``dtypes`` / ``null_counts`` come from a
    real content decode. The two are deliberately separate so a footer that
    lies (e.g. reports 2187 rows but the file decodes empty) is detectable.
    """

    path: str
    relative_path: str
    exists: bool
    size_bytes: int | None
    mtime_iso: str | None

    readable: bool
    read_error: str | None
    reader: str | None  # "duckdb" | "pandas" | None

    # Content-level (from a real decode)
    row_count: int | None
    column_count: int | None
    columns: tuple[str, ...] | None
    dtypes: dict[str, str] | None
    null_counts: dict[str, int] | None
    sample_ok: bool | None

    # Footer-level (from parquet metadata, no content decode)
    num_row_groups: int | None
    footer_row_count: int | None
    footer_columns: tuple[str, ...] | None
    writer_version: str | None

    # Derived signals
    footer_content_mismatch: bool
    schema_hash: str | None
    content_hash: str | None
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        """True when the file decodes cleanly and footer agrees with content."""
        return bool(
            self.exists
            and self.readable
            and self.row_count is not None
            and self.row_count >= 0
            and not self.footer_content_mismatch
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # tuples -> lists for JSON
        if d.get("columns") is not None:
            d["columns"] = list(d["columns"])
        if d.get("footer_columns") is not None:
            d["footer_columns"] = list(d["footer_columns"])
        d["notes"] = list(d.get("notes") or [])
        return d


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stat_file(path: Path) -> tuple[int | None, str | None]:
    try:
        st = path.stat()
        return int(st.st_size), datetime.fromtimestamp(st.st_mtime, UTC).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    except OSError:
        return None, None


def _footer_metadata(path: Path) -> dict[str, Any]:
    """Read parquet footer metadata without a full content decode.

    Uses pyarrow (the parquet engine pandas already depends on) as the
    primary source because it returns clean top-level column names. DuckDB's
    ``path_in_schema`` encodes nested paths with ', ' which collides with
    legitimate column names containing ', ' (e.g. pandas MultiIndex tuples
    like ``('Per 90 Minutes', 'Ast')``), so DuckDB is only a fallback for
    row counts when pyarrow is unavailable.

    Returns a dict with ``num_row_groups``, ``footer_row_count``,
    ``footer_columns`` and ``writer_version``. Any failure returns an empty
    dict; the caller treats missing fields as "unknown".
    """
    out: dict[str, Any] = {}
    # Primary: pyarrow (clean top-level column names).
    try:
        import pyarrow.parquet as pq

        pf = pq.ParquetFile(path)
        md = pf.metadata
        out["footer_row_count"] = int(md.num_rows)
        out["num_row_groups"] = int(md.num_row_groups)
        out["writer_version"] = (
            md.created_by if md.created_by else None
        )
        # schema.names returns top-level column names only (nested fields are
        # under each column's type, not flattened into the list).
        out["footer_columns"] = tuple(pf.schema_arrow.names)
        return out
    except Exception as exc:  # noqa: BLE001 - footer probe must never crash preflight
        logger.debug("pyarrow footer metadata failed for %s: %s", path, exc)

    # Fallback: DuckDB for row counts only (column names unreliable here).
    try:
        import duckdb

        con = duckdb.connect()
        try:
            meta = con.execute(
                "SELECT num_rows, num_row_groups, created_by "
                "FROM parquet_file_metadata(?)",
                [str(path)],
            ).fetchone()
            if meta is not None:
                out["footer_row_count"] = int(meta[0]) if meta[0] is not None else None
                out["num_row_groups"] = int(meta[1]) if meta[1] is not None else None
                out["writer_version"] = str(meta[2]) if meta[2] is not None else None
        finally:
            con.close()
    except Exception as exc:  # noqa: BLE001
        logger.debug("duckdb footer metadata failed for %s: %s", path, exc)
    return out


def _read_content_duckdb(path: Path) -> tuple[pd.DataFrame, str]:
    """Fully decode a parquet file via DuckDB. Raises on any failure."""
    import duckdb

    con = duckdb.connect()
    try:
        return con.execute(
            "SELECT * FROM read_parquet(?)",
            [str(path)],
        ).fetchdf(), "duckdb"
    finally:
        con.close()


def _read_content_pandas(path: Path) -> tuple[pd.DataFrame, str]:
    """Fallback reader via pandas (pyarrow engine). Raises on any failure."""
    return pd.read_parquet(path), "pandas"


def _dtype_to_str(dtype: Any) -> str:
    try:
        return str(dtype)
    except Exception:  # noqa: BLE001
        return "unknown"


def _compute_hashes(
    row_count: int | None,
    columns: tuple[str, ...] | None,
    dtypes: dict[str, str] | None,
    null_counts: dict[str, int] | None,
) -> tuple[str | None, str | None]:
    """Return (schema_hash, content_hash).

    ``schema_hash`` is sha256 of sorted column names + dtypes — stable across
    runs and identifies the contract. ``content_hash`` additionally folds in
    row_count and null_counts, so it changes when content changes even if the
    schema is unchanged. Both are cheap; neither hashes row bytes.
    """
    schema_hash = None
    content_hash = None
    if columns is not None:
        cols = sorted(columns)
        dtypes_for_schema = {k: (dtypes or {}).get(k, "") for k in cols}
        schema_payload = {"columns": cols, "dtypes": dtypes_for_schema}
        schema_hash = hashlib.sha256(
            json.dumps(schema_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
    if row_count is not None and columns is not None:
        content_payload = {
            "row_count": int(row_count),
            "columns": sorted(columns),
            "null_counts": {k: int(v) for k, v in (null_counts or {}).items()},
        }
        content_hash = hashlib.sha256(
            json.dumps(content_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
    return schema_hash, content_hash


def preflight_parquet(
    path: Path | str,
    settings: PlatformSettings | None = None,
    expected_columns: Iterable[str] | None = None,
) -> ParquetPreflightReport:
    """Inspect a single Parquet file at the content level.

    *path* may be absolute or relative to ``settings.data_root`` (when
    *settings* is given). ``expected_columns`` is an optional contract to
    check against the decoded columns; missing/extra columns are recorded as
    notes, never as hard failures (readability is the only hard gate).
    """
    settings = settings or PlatformSettings.from_root()
    src = Path(path)
    if not src.is_absolute():
        resolved = settings.data_root / src
    else:
        resolved = src

    relative = (
        str(resolved.relative_to(settings.data_root)).replace("\\", "/")
        if resolved.is_relative_to(settings.data_root)
        else str(resolved)
    )
    size_bytes, mtime_iso = _stat_file(resolved)

    if not resolved.exists() or resolved.suffix != ".parquet":
        return ParquetPreflightReport(
            path=str(resolved),
            relative_path=relative,
            exists=resolved.exists(),
            size_bytes=size_bytes,
            mtime_iso=mtime_iso,
            readable=False,
            read_error="not a readable parquet path (missing or wrong suffix)"
            if resolved.exists()
            else "file does not exist",
            reader=None,
            row_count=None,
            column_count=None,
            columns=None,
            dtypes=None,
            null_counts=None,
            sample_ok=None,
            num_row_groups=None,
            footer_row_count=None,
            footer_columns=None,
            writer_version=None,
            footer_content_mismatch=False,
            schema_hash=None,
            content_hash=None,
            notes=(),
        )

    # Footer metadata first (cheap, may fail independently of content).
    footer = _footer_metadata(resolved)
    num_row_groups = footer.get("num_row_groups")
    footer_row_count = footer.get("footer_row_count")
    footer_columns = footer.get("footer_columns")
    writer_version = footer.get("writer_version")

    notes: list[str] = []
    df: pd.DataFrame | None = None
    reader: str | None = None
    read_error: str | None = None

    # Content decode: DuckDB first, pandas fallback.
    try:
        df, reader = _read_content_duckdb(resolved)
    except Exception as exc_primary:  # noqa: BLE001 - we want to try the fallback
        try:
            df, reader = _read_content_pandas(resolved)
            notes.append(f"duckdb read failed ({exc_primary}); fell back to pandas")
        except Exception as exc_fallback:  # noqa: BLE001
            read_error = f"duckdb: {exc_primary} | pandas: {exc_fallback}"

    if df is None:
        return ParquetPreflightReport(
            path=str(resolved),
            relative_path=relative,
            exists=True,
            size_bytes=size_bytes,
            mtime_iso=mtime_iso,
            readable=False,
            read_error=read_error,
            reader=None,
            row_count=None,
            column_count=None,
            columns=None,
            dtypes=None,
            null_counts=None,
            sample_ok=False,
            num_row_groups=num_row_groups,
            footer_row_count=footer_row_count,
            footer_columns=footer_columns,
            writer_version=writer_version,
            footer_content_mismatch=False,
            schema_hash=None,
            content_hash=None,
            notes=tuple(notes),
        )

    columns = tuple(str(c) for c in df.columns)
    dtypes = {str(c): _dtype_to_str(df[c].dtype) for c in df.columns}
    row_count = int(len(df))
    null_counts = {str(c): int(df[c].isnull().sum()) for c in df.columns}

    sample_ok = True
    try:
        _ = df.head(5)
    except Exception as exc:  # noqa: BLE001
        sample_ok = False
        notes.append(f"head(5) decode failed: {exc}")

    # Footer vs content mismatch detection.
    mismatch = False
    if footer_row_count is not None and footer_row_count != row_count:
        mismatch = True
        notes.append(
            f"footer_row_count={footer_row_count} != content_row_count={row_count}"
        )
    if footer_columns is not None and tuple(sorted(footer_columns)) != tuple(sorted(columns)):
        mismatch = True
        missing_in_content = sorted(set(footer_columns) - set(columns))
        extra_in_content = sorted(set(columns) - set(footer_columns))
        if missing_in_content:
            notes.append(f"footer has columns missing from content: {missing_in_content}")
        if extra_in_content:
            notes.append(f"content has columns missing from footer: {extra_in_content}")

    if row_count == 0:
        notes.append("content decodes to 0 rows (empty after decode)")

    if expected_columns is not None:
        expected = set(expected_columns)
        actual = set(columns)
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        if missing:
            notes.append(f"missing expected columns: {missing}")
        if extra:
            notes.append(f"unexpected extra columns: {extra}")

    schema_hash, content_hash = _compute_hashes(row_count, columns, dtypes, null_counts)

    return ParquetPreflightReport(
        path=str(resolved),
        relative_path=relative,
        exists=True,
        size_bytes=size_bytes,
        mtime_iso=mtime_iso,
        readable=True,
        read_error=None,
        reader=reader,
        row_count=row_count,
        column_count=len(columns),
        columns=columns,
        dtypes=dtypes,
        null_counts=null_counts,
        sample_ok=sample_ok,
        num_row_groups=num_row_groups,
        footer_row_count=footer_row_count,
        footer_columns=footer_columns,
        writer_version=writer_version,
        footer_content_mismatch=mismatch,
        schema_hash=schema_hash,
        content_hash=content_hash,
        notes=tuple(notes),
    )


# ---------------------------------------------------------------------------
# Project-aware key artifacts
# ---------------------------------------------------------------------------


# Files explicitly flagged in AGENTS.md as having footer/content conflicts or
# being referenced by CLI but missing, plus the core pipeline inputs/outputs.
KEY_RAW_ARTIFACTS: tuple[str, ...] = (
    "raw/football_data/combined_results.parquet",
    "raw/statsbomb_open/matches_all.parquet",
    "raw/statsbomb_open/big5_matches.parquet",
    "raw/statsbomb_open/events_sample.parquet",
    "raw/statsbomb_open/lineups_all.parquet",
    "raw/understat/players_10seasons.parquet",
    "raw/fbref/player_standard_5seasons.parquet",
    "raw/fbref/player_shooting_5seasons.parquet",
    "raw/fbref/player_misc_5seasons.parquet",
)

KEY_GOLD_ARTIFACTS: tuple[str, ...] = (
    "gold/feature_store/player_match.parquet",
    "gold/feature_store/team_match.parquet",
    "gold/feature_store/match_features.parquet",
    "gold/feature_store/team_features.parquet",
    "gold/feature_store/player_rolling.parquet",
    "gold/feature_store/team_rolling.parquet",
    "gold/feature_store/player_ratings.parquet",
    "gold/feature_store/player_truth_labels.parquet",
    "gold/feature_store/player_value_metrics.parquet",
    "gold/feature_store/player_vaep.parquet",
    "gold/feature_store/player_action_value.parquet",
    "gold/feature_store/rating_feature_matrix.parquet",
)


def key_artifact_paths(
    target: str = "key",
    settings: PlatformSettings | None = None,
) -> list[str]:
    """Return relative paths under ``data_root`` to preflight.

    *target* is one of ``raw``, ``gold``, ``sample``, ``key`` (raw+gold) or
    ``all``. Only paths that exist on disk are returned for ``raw``/``gold``
    scopes so the report focuses on real artifacts rather than 404 noise;
    ``key`` keeps AGENTS.md-flagged conflict files even when missing so the
    gap is surfaced explicitly.
    """
    settings = settings or PlatformSettings.from_root()
    rels: list[str] = []
    if target in {"raw", "key", "all"}:
        rels.extend(KEY_RAW_ARTIFACTS)
    if target in {"gold", "key", "all"}:
        rels.extend(KEY_GOLD_ARTIFACTS)
    if target == "sample":
        sample_dir = settings.data_root / "sample"
        if sample_dir.exists():
            rels.extend(
                f"sample/{p.name}" for p in sorted(sample_dir.glob("*.parquet"))
            )
    if target == "all":
        # Add any parquet under raw/ and gold/ not already listed, so the
        # scope is genuinely "all" rather than "key only".
        for sub in ("raw", "gold"):
            sub_dir = settings.data_root / sub
            if sub_dir.exists():
                for p in sorted(sub_dir.rglob("*.parquet")):
                    rel = str(p.relative_to(settings.data_root)).replace("\\", "/")
                    if rel not in rels:
                        rels.append(rel)

    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for r in rels:
        if r in seen:
            continue
        seen.add(r)
        unique.append(r)

    # For raw/gold scopes, drop missing files so the report focuses on real
    # artifacts rather than 404 noise. ``key`` and ``all`` keep AGENTS.md-
    # flagged conflict files even when missing, so the gap is surfaced
    # explicitly rather than silently dropped.
    if target in {"raw", "gold"}:
        unique = [r for r in unique if (settings.data_root / r).exists()]
    return unique


def preflight_key_artifacts(
    target: str = "key",
    settings: PlatformSettings | None = None,
) -> list[ParquetPreflightReport]:
    """Run preflight across the project's key artifacts."""
    settings = settings or PlatformSettings.from_root()
    paths = key_artifact_paths(target, settings)
    return [preflight_parquet(p, settings) for p in paths]


# ---------------------------------------------------------------------------
# Summaries & quarantine
# ---------------------------------------------------------------------------


def summarize_reports(
    reports: list[ParquetPreflightReport],
    fmt: str = "text",
) -> str:
    """Render a preflight summary.

    ``fmt="text"`` produces a human-readable block matching the style of
    ``validation.ValidationReport.summary()``. ``fmt="json"`` produces a JSON
    document suitable for a manifest or CI artifact.
    """
    if fmt == "json":
        payload = {
            "generated_at": _now_iso(),
            "total": len(reports),
            "ok": sum(1 for r in reports if r.ok),
            "unreadable": sum(1 for r in reports if not r.readable),
            "mismatch": sum(1 for r in reports if r.footer_content_mismatch),
            "reports": [r.to_dict() for r in reports],
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)

    total = len(reports)
    ok = sum(1 for r in reports if r.ok)
    unreadable = [r for r in reports if not r.readable]
    mismatches = [r for r in reports if r.footer_content_mismatch]
    flagged = [r for r in reports if r.readable and not r.ok]

    lines = [
        f"Parquet preflight: {ok}/{total} ok, "
        f"{len(unreadable)} unreadable, {len(mismatches)} footer/content mismatch, "
        f"{len(flagged)} flagged"
    ]
    if unreadable:
        lines.append("  UNREADABLE:")
        for r in unreadable:
            lines.append(f"    - {r.relative_path}: {r.read_error}")
    if mismatches:
        lines.append("  FOOTER/CONTENT MISMATCH:")
        for r in mismatches:
            lines.append(
                f"    - {r.relative_path}: "
                f"footer_rows={r.footer_row_count} content_rows={r.row_count}"
            )
            for note in r.notes:
                lines.append(f"        {note}")
    if flagged:
        lines.append("  FLAGGED:")
        for r in flagged:
            for note in r.notes:
                lines.append(f"    - {r.relative_path}: {note}")
    # Compact per-file table for readable ones.
    readable = [r for r in reports if r.readable]
    if readable:
        lines.append("  READABLE:")
        for r in readable:
            status = "ok" if r.ok else "FLAGGED"
            lines.append(
                f"    - {r.relative_path}: rows={r.row_count} cols={r.column_count} "
                f"reader={r.reader} row_groups={r.num_row_groups} [{status}]"
            )
    return "\n".join(lines)


@dataclass(frozen=True)
class QuarantineResult:
    moved: tuple[str, ...]
    skipped: tuple[str, ...]
    manifest_path: str | None


def _quarantine_destination(quarantine_dir: Path, report: ParquetPreflightReport) -> Path:
    """Compute a safe destination path under *quarantine_dir*.

    Files under ``data_root`` keep their relative subdirectory structure so
    the user can see where they came from. Files outside ``data_root``
    (e.g. explicit CLI path args) are flattened to a hash-prefixed filename
    to avoid the absolute path hijacking ``Path /`` on Windows — joining
    ``quarantine_dir / "C:\\foo\\bar.parquet"`` resolves to ``C:\\foo\\bar.parquet``
    rather than a path under quarantine, which would move the file nowhere.
    """
    rel = report.relative_path
    src = Path(report.path)
    # If the stored relative_path is actually a sub-path of data_root (no
    # drive letter, not absolute), preserve structure.
    if rel and not Path(rel).is_absolute() and "\\" not in rel[:1] and ":" not in rel[:2]:
        return quarantine_dir / rel
    # Otherwise flatten: short hash of the full path + original filename.
    h = hashlib.sha1(str(src).encode("utf-8")).hexdigest()[:8]
    return quarantine_dir / f"{h}_{src.name}"


def quarantine_unreadable(
    reports: list[ParquetPreflightReport],
    settings: PlatformSettings | None = None,
    dry_run: bool = True,
) -> QuarantineResult:
    """Move unreadable parquet files into ``data/quarantine/``.

    Quarantine is reversible: a manifest is written next to the moved files
    recording the original path, so a user can restore manually. By default
    *dry_run* is True and nothing is moved — the returned manifest path is
    None and ``moved`` is empty; callers use the result to preview. Only
    files that exist but failed content decode are candidates; missing files
    and readable files are always skipped.
    """
    settings = settings or PlatformSettings.from_root()
    quarantine_dir = settings.data_root / "quarantine"
    moved: list[str] = []
    skipped: list[str] = []

    candidates = [
        r for r in reports if r.exists and not r.readable and r.relative_path
    ]
    if not candidates:
        return QuarantineResult(moved=(), skipped=(), manifest_path=None)

    if dry_run:
        for r in candidates:
            skipped.append(r.relative_path)
        return QuarantineResult(moved=(), skipped=tuple(skipped), manifest_path=None)

    quarantine_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    ts = _now_iso().replace(":", "").replace("-", "")
    manifest_path = quarantine_dir / f"quarantine_manifest_{ts}.json"

    for r in candidates:
        src = Path(r.path)
        dst = _quarantine_destination(quarantine_dir, r)
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            # Never overwrite: if a quarantined copy already exists, suffix it.
            if dst.exists():
                dst = dst.with_name(f"{dst.stem}_dup{dst.suffix}")
            # Guard against src == dst (would happen if data_root itself were
            # under quarantine, which should never occur but is cheap to check).
            if src.resolve() == dst.resolve():
                skipped.append(r.relative_path)
                continue
            shutil.move(str(src), str(dst))
            moved.append(r.relative_path)
            manifest.append(
                {
                    "original_path": r.path,
                    "relative_path": r.relative_path,
                    "quarantine_path": str(dst),
                    "read_error": r.read_error,
                    "moved_at": _now_iso(),
                }
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to quarantine %s: %s", src, exc)
            skipped.append(r.relative_path)

    try:
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError as exc:
        logger.warning("Failed to write quarantine manifest: %s", exc)
        return QuarantineResult(
            moved=tuple(moved), skipped=tuple(skipped), manifest_path=None
        )

    return QuarantineResult(
        moved=tuple(moved), skipped=tuple(skipped), manifest_path=str(manifest_path)
    )
