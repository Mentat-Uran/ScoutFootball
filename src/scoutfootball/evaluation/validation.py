"""Data validation checks that gate training and downstream pipelines."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

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
    return report
