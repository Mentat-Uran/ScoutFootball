"""Data validation checks that gate training and downstream pipelines."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

from scoutfootball.config import PlatformSettings


@dataclass(frozen=True)
class ValidationCheckResult:
    check_name: str
    passed: bool
    message: str


@dataclass
class ValidationReport:
    checks: list[ValidationCheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failures(self) -> list[ValidationCheckResult]:
        return [c for c in self.checks if not c.passed]

    def summary(self) -> str:
        total = len(self.checks)
        failed = len(self.failures)
        status = "PASS" if self.passed else "FAIL"
        lines = [f"Validation: {status} ({total - failed}/{total} checks passed)"]
        for f in self.failures:
            lines.append(f"  FAIL [{f.check_name}]: {f.message}")
        return "\n".join(lines)


def validate_parquet_exists(
    relative_path: str,
    settings: PlatformSettings | None = None,
) -> ValidationCheckResult:
    resolved = (settings or PlatformSettings.from_root()).data_root / relative_path
    name = f"parquet_exists:{relative_path}"
    if resolved.exists() and resolved.suffix == ".parquet":
        return ValidationCheckResult(name, True, f"Found {resolved}")
    return ValidationCheckResult(name, False, f"Missing {resolved}")


def validate_row_count(
    relative_path: str,
    min_rows: int = 1,
    settings: PlatformSettings | None = None,
) -> ValidationCheckResult:
    resolved = (settings or PlatformSettings.from_root()).data_root / relative_path
    name = f"row_count:{relative_path}"
    if not resolved.exists():
        return ValidationCheckResult(name, False, f"File missing: {resolved}")
    df = pd.read_parquet(resolved)
    n = len(df)
    if n >= min_rows:
        return ValidationCheckResult(name, True, f"{n} rows (>= {min_rows})")
    return ValidationCheckResult(name, False, f"{n} rows (< {min_rows})")


def validate_date_range(
    relative_path: str,
    date_column: str,
    min_date: date | None = None,
    settings: PlatformSettings | None = None,
) -> ValidationCheckResult:
    resolved = (settings or PlatformSettings.from_root()).data_root / relative_path
    name = f"date_range:{relative_path}"
    if not resolved.exists():
        return ValidationCheckResult(name, False, f"File missing: {resolved}")
    df = pd.read_parquet(resolved)
    if date_column not in df.columns:
        return ValidationCheckResult(name, False, f"Column '{date_column}' not found")
    dates = pd.to_datetime(df[date_column], errors="coerce").dropna()
    if dates.empty:
        return ValidationCheckResult(name, False, "No valid dates found")
    max_date = dates.max().date()
    if min_date is not None and max_date < min_date:
        return ValidationCheckResult(name, False, f"Latest date {max_date} < required {min_date}")
    return ValidationCheckResult(name, True, f"Date range OK, latest={max_date}")


def validate_no_null_keys(
    relative_path: str,
    key_columns: tuple[str, ...],
    settings: PlatformSettings | None = None,
) -> ValidationCheckResult:
    resolved = (settings or PlatformSettings.from_root()).data_root / relative_path
    name = f"no_null_keys:{relative_path}"
    if not resolved.exists():
        return ValidationCheckResult(name, False, f"File missing: {resolved}")
    df = pd.read_parquet(resolved)
    missing_cols = [c for c in key_columns if c not in df.columns]
    if missing_cols:
        return ValidationCheckResult(name, False, f"Missing columns: {missing_cols}")
    null_counts = {c: int(df[c].isnull().sum()) for c in key_columns}
    has_nulls = any(v > 0 for v in null_counts.values())
    if has_nulls:
        return ValidationCheckResult(name, False, f"Null keys: {null_counts}")
    return ValidationCheckResult(name, True, "No null keys")


def validate_no_null_values(
    relative_path: str,
    value_columns: tuple[str, ...],
    settings: PlatformSettings | None = None,
) -> ValidationCheckResult:
    """Validate that value columns contain no null values.

    Distinct from ``validate_no_null_keys``: key columns identify rows and
    must never be null, while value columns carry measurements that may
    legitimately be NaN in some datasets (e.g. xg for matches without
    shots). This check is for value columns where NaN indicates data
    corruption rather than a meaningful missing measurement — for example
    ``goals_for``/``goals_against`` in ``team_match.parquet``, where NaN
    silently corrupts Dixon-Coles fitting (see WORKFLOW_LOG.md reference
    workflow 3).
    """
    resolved = (settings or PlatformSettings.from_root()).data_root / relative_path
    name = f"no_null_values:{relative_path}"
    if not resolved.exists():
        return ValidationCheckResult(name, False, f"File missing: {resolved}")
    df = pd.read_parquet(resolved)
    missing_cols = [c for c in value_columns if c not in df.columns]
    if missing_cols:
        return ValidationCheckResult(name, False, f"Missing columns: {missing_cols}")
    null_counts = {c: int(df[c].isnull().sum()) for c in value_columns}
    has_nulls = any(v > 0 for v in null_counts.values())
    if has_nulls:
        return ValidationCheckResult(name, False, f"Null values: {null_counts}")
    return ValidationCheckResult(name, True, "No null values")


def validate_no_negative_values(
    relative_path: str,
    value_columns: tuple[str, ...],
    settings: PlatformSettings | None = None,
) -> ValidationCheckResult:
    resolved = (settings or PlatformSettings.from_root()).data_root / relative_path
    name = f"no_negative_values:{relative_path}"
    if not resolved.exists():
        return ValidationCheckResult(name, False, f"File missing: {resolved}")
    df = pd.read_parquet(resolved)
    missing_cols = [c for c in value_columns if c not in df.columns]
    if missing_cols:
        return ValidationCheckResult(name, False, f"Missing columns: {missing_cols}")
    neg_counts = {c: int((df[c] < 0).sum()) for c in value_columns}
    has_negs = any(v > 0 for v in neg_counts.values())
    if has_negs:
        return ValidationCheckResult(name, False, f"Negative values: {neg_counts}")
    return ValidationCheckResult(name, True, "No negative values")


def validate_unique_keys(
    relative_path: str,
    key_columns: tuple[str, ...],
    settings: PlatformSettings | None = None,
) -> ValidationCheckResult:
    resolved = (settings or PlatformSettings.from_root()).data_root / relative_path
    name = f"unique_keys:{relative_path}"
    if not resolved.exists():
        return ValidationCheckResult(name, False, f"File missing: {resolved}")
    df = pd.read_parquet(resolved)
    missing_cols = [c for c in key_columns if c not in df.columns]
    if missing_cols:
        return ValidationCheckResult(name, False, f"Missing columns: {missing_cols}")
    dup_count = int(df.duplicated(subset=list(key_columns)).sum())
    if dup_count > 0:
        return ValidationCheckResult(
            name,
            False,
            f"{dup_count} duplicate rows for keys {list(key_columns)}",
        )
    return ValidationCheckResult(name, True, f"Keys {list(key_columns)} are unique")


def validate_manifest_exists(
    parquet_relative_path: str,
    settings: PlatformSettings | None = None,
) -> ValidationCheckResult:
    """Validate that a parquet file has a sidecar manifest with required fields.

    Manifest is expected at ``{parquet_stem}_manifest.json`` next to the
    parquet file (matches ``features.manifest.write_manifest`` convention).
    Required fields mirror the aligned schema in DATA_CONTRACTS.md 7.1:
    ``artifact``, ``schema_version``, ``total_rows``, ``column_count``,
    ``columns``, ``input_hash``, ``source_lineage``, ``timestamp``.

    Returns FAIL when:
    - parquet file is missing (cannot infer manifest path reliably)
    - manifest file is missing (build-features did not run or failed)
    - manifest is not valid JSON
    - manifest is missing any required field

    Does NOT validate manifest freshness vs parquet content — that is
    ``validate_manifest_freshness``'s responsibility.
    """
    resolved = (settings or PlatformSettings.from_root()).data_root / parquet_relative_path
    name = f"manifest_exists:{parquet_relative_path}"
    if not resolved.exists():
        return ValidationCheckResult(name, False, f"Parquet missing: {resolved}")
    manifest_path = resolved.parent / f"{resolved.stem}_manifest.json"
    if not manifest_path.exists():
        return ValidationCheckResult(
            name, False, f"Manifest missing: {manifest_path.name} (run build-features)"
        )
    try:
        with open(manifest_path, encoding="utf-8") as f:
            payload = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        return ValidationCheckResult(name, False, f"Manifest unreadable: {exc}")
    required = (
        "artifact",
        "schema_version",
        "total_rows",
        "column_count",
        "columns",
        "input_hash",
        "source_lineage",
        "timestamp",
    )
    missing = [f for f in required if f not in payload]
    if missing:
        return ValidationCheckResult(
            name, False, f"Manifest missing fields: {missing}"
        )
    return ValidationCheckResult(
        name,
        True,
        f"Manifest OK ({manifest_path.name}, artifact={payload['artifact']}, "
        f"schema={payload['schema_version']})",
    )


def validate_manifest_freshness(
    parquet_relative_path: str,
    settings: PlatformSettings | None = None,
) -> ValidationCheckResult:
    """Validate that the sidecar manifest row count matches the parquet.

    Detects stale manifests: build-features wrote the manifest, then a
    later partial rebuild (manual edit, separate pipeline step, or
    failed run) changed the parquet without refreshing the manifest.
    A stale manifest misleads consumers about input hashes and row
    counts even when the schema is present.

    Returns FAIL when:
    - parquet file is missing
    - manifest file is missing (delegates to validate_manifest_exists)
    - manifest is unreadable
    - manifest.total_rows != actual parquet row count
    - manifest.column_count != actual parquet column count

    Does NOT re-hash inputs (expensive); use ``contract-quality`` for
    full content-level manifest verification.
    """
    resolved = (settings or PlatformSettings.from_root()).data_root / parquet_relative_path
    name = f"manifest_freshness:{parquet_relative_path}"
    if not resolved.exists():
        return ValidationCheckResult(name, False, f"Parquet missing: {resolved}")
    manifest_path = resolved.parent / f"{resolved.stem}_manifest.json"
    if not manifest_path.exists():
        return ValidationCheckResult(
            name, False, f"Manifest missing: {manifest_path.name}"
        )
    try:
        with open(manifest_path, encoding="utf-8") as f:
            payload = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        return ValidationCheckResult(name, False, f"Manifest unreadable: {exc}")

    manifest_rows = payload.get("total_rows")
    manifest_cols = payload.get("column_count")
    if manifest_rows is None or manifest_cols is None:
        return ValidationCheckResult(
            name, False, "Manifest missing total_rows or column_count"
        )

    df = pd.read_parquet(resolved)
    actual_rows = int(len(df))
    actual_cols = int(len(df.columns))
    if int(manifest_rows) != actual_rows:
        return ValidationCheckResult(
            name,
            False,
            f"Row count drift: manifest={manifest_rows}, parquet={actual_rows}",
        )
    if int(manifest_cols) != actual_cols:
        return ValidationCheckResult(
            name,
            False,
            f"Column count drift: manifest={manifest_cols}, parquet={actual_cols}",
        )
    return ValidationCheckResult(
        name,
        True,
        f"Manifest fresh (rows={actual_rows}, cols={actual_cols})",
    )


def run_pre_training_validation(
    settings: PlatformSettings | None = None,
) -> ValidationReport:
    report = ValidationReport()
    report.checks.append(
        validate_parquet_exists("gold/feature_store/player_match.parquet", settings)
    )
    report.checks.append(validate_parquet_exists("gold/feature_store/team_match.parquet", settings))
    report.checks.append(
        validate_row_count(
            "gold/feature_store/player_match.parquet",
            min_rows=10,
            settings=settings,
        )
    )
    report.checks.append(
        validate_row_count(
            "gold/feature_store/team_match.parquet",
            min_rows=10,
            settings=settings,
        )
    )
    report.checks.append(
        validate_no_null_keys(
            "gold/feature_store/player_match.parquet",
            ("match_id", "player_id"),
            settings,
        )
    )
    report.checks.append(
        validate_no_null_keys(
            "gold/feature_store/team_match.parquet",
            ("match_id", "team_id"),
            settings,
        )
    )
    # Goals completeness: NaN goals_for/goals_against in team_match.parquet
    # silently corrupts Dixon-Coles fitting. The source-level filter in
    # _build_team_match_from_football_data is the primary gate; this check
    # is a pre-training defense-in-depth that catches source-filter regressions,
    # manual edits, or new data sources before they reach model training.
    report.checks.append(
        validate_no_null_values(
            "gold/feature_store/team_match.parquet",
            ("goals_for", "goals_against"),
            settings,
        )
    )
    # Player-match core metric completeness: goals, assists, and minutes
    # are the foundation of all downstream rating and projection features.
    # NaN in these columns means the aggregation pipeline silently dropped
    # values or a new data source introduced null measurements.
    report.checks.append(
        validate_no_null_values(
            "gold/feature_store/player_match.parquet",
            ("goals", "assists", "minutes_played"),
            settings,
        )
    )
    # Non-negativity: core count metrics can never be negative. Negative
    # values indicate arithmetic errors, sign flips, or corrupt imports.
    report.checks.append(
        validate_no_negative_values(
            "gold/feature_store/team_match.parquet",
            ("goals_for", "goals_against"),
            settings,
        )
    )
    report.checks.append(
        validate_no_negative_values(
            "gold/feature_store/player_match.parquet",
            ("goals", "assists", "minutes_played"),
            settings,
        )
    )
    # Rating matrix row uniqueness: each player-season must appear exactly
    # once. Duplicate rows would double-count players in rating training
    # or silently merge incompatible records from different identity
    # resolution paths.
    report.checks.append(
        validate_unique_keys(
            "gold/feature_store/rating_feature_matrix.parquet",
            ("player_id", "season_id"),
            settings,
        )
    )
    return report
