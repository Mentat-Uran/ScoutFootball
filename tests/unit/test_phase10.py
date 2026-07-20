"""Tests for Phase 10: validation, calibration, pipeline, API."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scoutfootball.evaluation.calibration import (
    brier_score,
    calibrate_probabilities_isotonic,
)
from scoutfootball.evaluation.validation import (
    ValidationCheckResult,
    ValidationReport,
    run_pre_training_validation,
    validate_manifest_exists,
    validate_manifest_freshness,
    validate_no_negative_values,
    validate_no_null_keys,
    validate_no_null_values,
    validate_parquet_exists,
    validate_row_count,
    validate_source_lineage_freshness,
    validate_unique_keys,
)


def _data_dir(tmp_path):
    return tmp_path / "data"


def _make_settings(tmp_path):
    from scoutfootball.config import PlatformSettings

    return PlatformSettings.from_root(tmp_path)


class TestValidationReport:
    def test_passed_when_all_pass(self):
        report = ValidationReport(
            checks=[
                ValidationCheckResult("a", True, "ok"),
                ValidationCheckResult("b", True, "ok"),
            ]
        )
        assert report.passed
        assert len(report.failures) == 0

    def test_failed_when_any_fails(self):
        report = ValidationReport(
            checks=[
                ValidationCheckResult("a", True, "ok"),
                ValidationCheckResult("b", False, "bad"),
            ]
        )
        assert not report.passed
        assert len(report.failures) == 1
        assert "FAIL" in report.summary()

    def test_empty_report_passes(self):
        report = ValidationReport()
        assert report.passed


class TestValidateParquetExists:
    def test_missing_file(self, tmp_path):
        result = validate_parquet_exists(
            "nonexistent.parquet",
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "Missing" in result.message

    def test_existing_file(self, tmp_path):
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        df = pd.DataFrame({"x": [1, 2]})
        df.to_parquet(gold / "test.parquet")
        result = validate_parquet_exists(
            "gold/feature_store/test.parquet",
            settings=_make_settings(tmp_path),
        )
        assert result.passed


class TestValidateRowCount:
    def test_below_minimum(self, tmp_path):
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        df = pd.DataFrame({"x": [1]})
        df.to_parquet(gold / "small.parquet")
        result = validate_row_count(
            "gold/feature_store/small.parquet",
            min_rows=10,
            settings=_make_settings(tmp_path),
        )
        assert not result.passed

    def test_above_minimum(self, tmp_path):
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        df = pd.DataFrame({"x": range(20)})
        df.to_parquet(gold / "big.parquet")
        result = validate_row_count(
            "gold/feature_store/big.parquet",
            min_rows=10,
            settings=_make_settings(tmp_path),
        )
        assert result.passed


class TestValidateNoNullKeys:
    def test_with_nulls(self, tmp_path):
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        df = pd.DataFrame({"match_id": ["a", None], "player_id": ["p1", "p2"]})
        df.to_parquet(gold / "nulls.parquet")
        result = validate_no_null_keys(
            "gold/feature_store/nulls.parquet",
            ("match_id", "player_id"),
            settings=_make_settings(tmp_path),
        )
        assert not result.passed

    def test_without_nulls(self, tmp_path):
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        df = pd.DataFrame({"match_id": ["a", "b"], "player_id": ["p1", "p2"]})
        df.to_parquet(gold / "clean.parquet")
        result = validate_no_null_keys(
            "gold/feature_store/clean.parquet",
            ("match_id", "player_id"),
            settings=_make_settings(tmp_path),
        )
        assert result.passed


class TestValidateNoNullValues:
    """Value-column completeness checks (distinct from key-column checks).

    Regression coverage for the goals_for/goals_against NaN corruption
    chain fixed in WORKFLOW_LOG.md reference workflow 3. The source-level
    filter in _build_team_match_from_football_data is the primary gate;
    this validation check is a pre-training defense-in-depth.
    """

    def test_missing_file(self, tmp_path):
        result = validate_no_null_values(
            "gold/feature_store/nonexistent.parquet",
            ("goals_for", "goals_against"),
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "missing" in result.message.lower()

    def test_with_null_values(self, tmp_path):
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        df = pd.DataFrame(
            {
                "match_id": ["m1", "m2", "m3"],
                "team_id": ["t1", "t2", "t3"],
                "goals_for": [2, np.nan, 1],
                "goals_against": [1, 1, np.nan],
            }
        )
        df.to_parquet(gold / "null_goals.parquet")
        result = validate_no_null_values(
            "gold/feature_store/null_goals.parquet",
            ("goals_for", "goals_against"),
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "Null values" in result.message
        # Both columns must report their null counts.
        assert "goals_for" in result.message
        assert "goals_against" in result.message

    def test_without_null_values(self, tmp_path):
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        df = pd.DataFrame(
            {
                "match_id": ["m1", "m2"],
                "team_id": ["t1", "t2"],
                "goals_for": [2, 1],
                "goals_against": [1, 1],
            }
        )
        df.to_parquet(gold / "clean_goals.parquet")
        result = validate_no_null_values(
            "gold/feature_store/clean_goals.parquet",
            ("goals_for", "goals_against"),
            settings=_make_settings(tmp_path),
        )
        assert result.passed
        assert "No null values" in result.message

    def test_missing_columns(self, tmp_path):
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        df = pd.DataFrame({"match_id": ["m1"], "team_id": ["t1"]})
        df.to_parquet(gold / "no_goals_cols.parquet")
        result = validate_no_null_values(
            "gold/feature_store/no_goals_cols.parquet",
            ("goals_for", "goals_against"),
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "Missing columns" in result.message


class TestValidateNoNegativeValues:
    """Non-negativity checks for core count metrics.

    Negative goals, assists, or minutes indicate arithmetic errors,
    sign flips, or corrupt imports. These checks catch regressions
    in the feature-building pipeline before they reach model training.
    """

    def test_missing_file(self, tmp_path):
        result = validate_no_negative_values(
            "gold/feature_store/nonexistent.parquet",
            ("goals", "assists"),
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "missing" in result.message.lower()

    def test_with_negative_values(self, tmp_path):
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        df = pd.DataFrame(
            {
                "player_id": ["p1", "p2", "p3"],
                "goals": [2, -1, 1],
                "assists": [1, 1, -3],
            }
        )
        df.to_parquet(gold / "neg_metrics.parquet")
        result = validate_no_negative_values(
            "gold/feature_store/neg_metrics.parquet",
            ("goals", "assists"),
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "Negative values" in result.message
        assert "goals" in result.message
        assert "assists" in result.message

    def test_without_negative_values(self, tmp_path):
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        df = pd.DataFrame(
            {
                "player_id": ["p1", "p2"],
                "goals": [2, 0],
                "assists": [1, 0],
            }
        )
        df.to_parquet(gold / "clean_metrics.parquet")
        result = validate_no_negative_values(
            "gold/feature_store/clean_metrics.parquet",
            ("goals", "assists"),
            settings=_make_settings(tmp_path),
        )
        assert result.passed
        assert "No negative values" in result.message

    def test_zero_values_are_valid(self, tmp_path):
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        df = pd.DataFrame(
            {"player_id": ["p1"], "goals": [0], "assists": [0]}
        )
        df.to_parquet(gold / "zero_metrics.parquet")
        result = validate_no_negative_values(
            "gold/feature_store/zero_metrics.parquet",
            ("goals", "assists"),
            settings=_make_settings(tmp_path),
        )
        assert result.passed

    def test_missing_columns(self, tmp_path):
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        df = pd.DataFrame({"player_id": ["p1"]})
        df.to_parquet(gold / "no_goals_col.parquet")
        result = validate_no_negative_values(
            "gold/feature_store/no_goals_col.parquet",
            ("goals", "assists"),
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "Missing columns" in result.message


class TestValidateUniqueKeys:
    """Primary key uniqueness checks.

    Duplicate rows in aggregated tables (e.g. one player-season
    appearing twice) would double-count training samples or silently
    merge incompatible identity resolution paths.
    """

    def test_missing_file(self, tmp_path):
        result = validate_unique_keys(
            "gold/feature_store/nonexistent.parquet",
            ("player_id", "season_id"),
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "missing" in result.message.lower()

    def test_with_duplicate_keys(self, tmp_path):
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        df = pd.DataFrame(
            {
                "player_id": ["p1", "p1", "p2"],
                "season_id": ["s1", "s1", "s1"],
                "goals": [2, 3, 1],
            }
        )
        df.to_parquet(gold / "dup_keys.parquet")
        result = validate_unique_keys(
            "gold/feature_store/dup_keys.parquet",
            ("player_id", "season_id"),
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "duplicate" in result.message.lower()
        assert "1" in result.message

    def test_without_duplicate_keys(self, tmp_path):
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        df = pd.DataFrame(
            {
                "player_id": ["p1", "p2", "p3"],
                "season_id": ["s1", "s1", "s1"],
                "goals": [2, 1, 0],
            }
        )
        df.to_parquet(gold / "unique_keys.parquet")
        result = validate_unique_keys(
            "gold/feature_store/unique_keys.parquet",
            ("player_id", "season_id"),
            settings=_make_settings(tmp_path),
        )
        assert result.passed
        assert "unique" in result.message.lower()

    def test_missing_columns(self, tmp_path):
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        df = pd.DataFrame({"player_id": ["p1"], "goals": [1]})
        df.to_parquet(gold / "no_season_col.parquet")
        result = validate_unique_keys(
            "gold/feature_store/no_season_col.parquet",
            ("player_id", "season_id"),
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "Missing columns" in result.message


class TestValidateManifestExists:
    """Sidecar manifest existence and schema-field checks.

    Validates that a parquet file has a ``{stem}_manifest.json`` next to
    it with the required schema fields. Missing manifest means
    build-features did not run or failed silently; consumers cannot
    detect input drift without it.
    """

    def _write_parquet(self, gold, name="team_match.parquet"):
        df = pd.DataFrame({"match_id": ["m1"], "team_id": ["t1"], "goals_for": [1]})
        df.to_parquet(gold / name)

    def test_fails_when_parquet_missing(self, tmp_path):
        """Missing parquet cannot have a manifest path inferred."""
        result = validate_manifest_exists(
            "gold/feature_store/missing.parquet",
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "Parquet missing" in result.message

    def test_fails_when_manifest_missing(self, tmp_path):
        """Parquet exists but no sidecar manifest → build-features did
        not run or manifest write failed."""
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_parquet(gold)

        result = validate_manifest_exists(
            "gold/feature_store/team_match.parquet",
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "Manifest missing" in result.message

    def test_fails_when_manifest_is_invalid_json(self, tmp_path):
        """Corrupt manifest JSON is a FAIL, not a silent pass."""

        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_parquet(gold)
        (gold / "team_match_manifest.json").write_text(
            "{not valid json", encoding="utf-8"
        )

        result = validate_manifest_exists(
            "gold/feature_store/team_match.parquet",
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "Manifest unreadable" in result.message

    def test_fails_when_required_field_missing(self, tmp_path):
        """Manifest exists but is missing required schema fields."""
        import json

        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_parquet(gold)
        # Missing source_lineage and timestamp.
        (gold / "team_match_manifest.json").write_text(
            json.dumps({
                "artifact": "team_match",
                "schema_version": "1.0",
                "total_rows": 1,
                "column_count": 3,
                "columns": [],
                "input_hash": "h",
            }),
            encoding="utf-8",
        )

        result = validate_manifest_exists(
            "gold/feature_store/team_match.parquet",
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "Manifest missing fields" in result.message
        assert "source_lineage" in result.message
        assert "timestamp" in result.message

    def test_passes_when_all_required_fields_present(self, tmp_path):
        """New-schema manifest with all required fields passes."""
        import json

        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_parquet(gold)
        (gold / "team_match_manifest.json").write_text(
            json.dumps({
                "artifact": "team_match",
                "schema_version": "1.0",
                "total_rows": 1,
                "column_count": 3,
                "columns": [],
                "input_hash": "h",
                "source_lineage": [],
                "timestamp": "2026-07-20T00:00:00Z",
            }),
            encoding="utf-8",
        )

        result = validate_manifest_exists(
            "gold/feature_store/team_match.parquet",
            settings=_make_settings(tmp_path),
        )
        assert result.passed
        assert "artifact=team_match" in result.message
        assert "schema=1.0" in result.message

    def test_legacy_schema_passes_with_reduced_required_fields(self, tmp_path):
        """Legacy manifest schema (no artifact/schema_version/source_lineage)
        passes when caller passes reduced required_fields. This keeps
        the check usable on third-party parquet files that predate the
        new manifest schema, even though all in-tree manifests now use
        the new schema."""
        import json

        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_parquet(gold, "rating_feature_matrix.parquet")
        (gold / "rating_feature_matrix_manifest.json").write_text(
            json.dumps({
                "total_rows": 1,
                "columns": [],
                "input_hash": "h",
                "timestamp": "2026-07-20T00:00:00Z",
            }),
            encoding="utf-8",
        )

        result = validate_manifest_exists(
            "gold/feature_store/rating_feature_matrix.parquet",
            settings=_make_settings(tmp_path),
            required_fields=("total_rows", "columns", "input_hash", "timestamp"),
        )
        assert result.passed
        assert "schema=<legacy>" in result.message


class TestValidateManifestFreshness:
    """Detect stale manifests where parquet was rebuilt but manifest was not.

    A stale manifest misleads consumers about input hashes and row counts
    even when the schema is present. This is the cheap content-level
    check (row/col count drift); full input-hash verification lives in
    contract-quality.
    """

    def _write_parquet(self, gold, name="team_match.parquet", rows=5, cols=3):
        df = pd.DataFrame(
            {f"col{i}": list(range(rows)) for i in range(cols)}
        )
        df.to_parquet(gold / name)

    def test_fails_when_parquet_missing(self, tmp_path):
        result = validate_manifest_freshness(
            "gold/feature_store/missing.parquet",
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "Parquet missing" in result.message

    def test_fails_when_manifest_missing(self, tmp_path):
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_parquet(gold)

        result = validate_manifest_freshness(
            "gold/feature_store/team_match.parquet",
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "Manifest missing" in result.message

    def test_fails_on_row_count_drift(self, tmp_path):
        """Manifest says 5 rows, parquet has 10 → stale manifest."""
        import json

        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_parquet(gold, rows=10, cols=3)
        (gold / "team_match_manifest.json").write_text(
            json.dumps({
                "total_rows": 5,
                "column_count": 3,
            }),
            encoding="utf-8",
        )

        result = validate_manifest_freshness(
            "gold/feature_store/team_match.parquet",
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "Row count drift" in result.message
        assert "manifest=5" in result.message
        assert "parquet=10" in result.message

    def test_fails_on_column_count_drift(self, tmp_path):
        """Manifest says 3 cols, parquet has 4 → schema drift."""
        import json

        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_parquet(gold, rows=5, cols=4)
        (gold / "team_match_manifest.json").write_text(
            json.dumps({
                "total_rows": 5,
                "column_count": 3,
            }),
            encoding="utf-8",
        )

        result = validate_manifest_freshness(
            "gold/feature_store/team_match.parquet",
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "Column count drift" in result.message

    def test_passes_when_manifest_matches_parquet(self, tmp_path):
        """Manifest row/col counts match parquet content → fresh."""
        import json

        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_parquet(gold, rows=7, cols=4)
        (gold / "team_match_manifest.json").write_text(
            json.dumps({
                "total_rows": 7,
                "column_count": 4,
            }),
            encoding="utf-8",
        )

        result = validate_manifest_freshness(
            "gold/feature_store/team_match.parquet",
            settings=_make_settings(tmp_path),
        )
        assert result.passed
        assert "rows=7" in result.message
        assert "cols=4" in result.message

    def test_fails_when_manifest_missing_total_rows(self, tmp_path):
        """Manifest JSON exists but lacks total_rows."""
        import json

        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_parquet(gold)
        (gold / "team_match_manifest.json").write_text(
            json.dumps({"column_count": 3}),  # no total_rows
            encoding="utf-8",
        )

        result = validate_manifest_freshness(
            "gold/feature_store/team_match.parquet",
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "Manifest missing total_rows" in result.message

    def test_legacy_manifest_without_column_count_passes(self, tmp_path):
        """Legacy rating_feature_matrix_manifest.json schema has no
        column_count field. validate_manifest_freshness must not fail
        on its absence — only on row count drift or schema-field
        corruption. This keeps the check forward-compatible with
        manifests written before the new schema was introduced."""
        import json

        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_parquet(gold, rows=5, cols=3)
        # No column_count field — legacy schema.
        (gold / "team_match_manifest.json").write_text(
            json.dumps({"total_rows": 5}),
            encoding="utf-8",
        )

        result = validate_manifest_freshness(
            "gold/feature_store/team_match.parquet",
            settings=_make_settings(tmp_path),
        )
        assert result.passed


class TestValidateSourceLineageFreshness:
    """Detect stale source_lineage entries where an upstream parquet was
    rebuilt but the downstream manifest was not.

    The companion ``validate_manifest_freshness`` checks a parquet's own
    row/column counts against its manifest. This check goes one level
    deeper: for each ``source_lineage`` entry, it re-hashes the upstream
    parquet and compares to the recorded ``input_hash``. Catches the
    partial-rebuild scenario that ``validate_manifest_freshness`` misses.
    """

    def _write_parquet(self, gold, name="team_match.parquet", rows=5, cols=3):
        df = pd.DataFrame(
            {f"col{i}": list(range(rows)) for i in range(cols)}
        )
        df.to_parquet(gold / name)

    def _write_manifest(self, gold, name, source_lineage):
        import json

        manifest_path = gold / f"{Path(name).stem}_manifest.json"
        manifest_path.write_text(
            json.dumps({
                "total_rows": 5,
                "column_count": 3,
                "source_lineage": source_lineage,
            }),
            encoding="utf-8",
        )

    def test_fails_when_parquet_missing(self, tmp_path):
        result = validate_source_lineage_freshness(
            "gold/feature_store/missing.parquet",
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "Parquet missing" in result.message

    def test_fails_when_manifest_missing(self, tmp_path):
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_parquet(gold)

        result = validate_source_lineage_freshness(
            "gold/feature_store/team_match.parquet",
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "Manifest missing" in result.message

    def test_passes_when_source_lineage_empty(self, tmp_path):
        """Empty source_lineage → nothing to verify, PASS."""
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_parquet(gold)
        self._write_manifest(gold, "team_match.parquet", source_lineage=[])

        result = validate_source_lineage_freshness(
            "gold/feature_store/team_match.parquet",
            settings=_make_settings(tmp_path),
        )
        assert result.passed
        assert "No source_lineage entries" in result.message

    def test_passes_when_upstream_hash_matches(self, tmp_path):
        """Upstream parquet hash matches recorded input_hash → fresh."""
        from scoutfootball.features.manifest import hash_file

        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        # Upstream parquet (football_data raw).
        raw_dir = _data_dir(tmp_path) / "raw" / "football_data"
        raw_dir.mkdir(parents=True)
        upstream_path = raw_dir / "combined_results.parquet"
        pd.DataFrame({"x": list(range(20))}).to_parquet(upstream_path)
        # Downstream parquet + manifest pointing at upstream.
        self._write_parquet(gold)
        self._write_manifest(
            gold,
            "team_match.parquet",
            source_lineage=[{
                "name": "football_data",
                "relative_path": "raw/football_data/combined_results.parquet",
                "rows_read": 20,
                "input_hash": hash_file(upstream_path),
                "notes": None,
            }],
        )

        result = validate_source_lineage_freshness(
            "gold/feature_store/team_match.parquet",
            settings=_make_settings(tmp_path),
        )
        assert result.passed
        assert "All 1 upstream hash(es) match" in result.message

    def test_fails_on_upstream_hash_drift(self, tmp_path):
        """Upstream rebuilt with new content → recorded hash stale."""
        from scoutfootball.features.manifest import hash_file

        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        raw_dir = _data_dir(tmp_path) / "raw" / "football_data"
        raw_dir.mkdir(parents=True)
        upstream_path = raw_dir / "combined_results.parquet"
        # Write v1, hash it, then overwrite with v2 (different content).
        pd.DataFrame({"x": list(range(20))}).to_parquet(upstream_path)
        stale_hash = hash_file(upstream_path)
        pd.DataFrame({"x": list(range(99))}).to_parquet(upstream_path)
        # Manifest records the v1 hash; current upstream is v2.
        self._write_parquet(gold)
        self._write_manifest(
            gold,
            "team_match.parquet",
            source_lineage=[{
                "name": "football_data",
                "relative_path": "raw/football_data/combined_results.parquet",
                "rows_read": 20,
                "input_hash": stale_hash,
                "notes": None,
            }],
        )

        result = validate_source_lineage_freshness(
            "gold/feature_store/team_match.parquet",
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "hash drift" in result.message
        assert "football_data" in result.message
        assert stale_hash in result.message

    def test_fails_when_upstream_file_missing(self, tmp_path):
        """Upstream parquet deleted → cannot verify, FAIL."""
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_parquet(gold)
        self._write_manifest(
            gold,
            "team_match.parquet",
            source_lineage=[{
                "name": "football_data",
                "relative_path": "raw/football_data/combined_results.parquet",
                "rows_read": 20,
                "input_hash": "abc123def456",
                "notes": None,
            }],
        )

        result = validate_source_lineage_freshness(
            "gold/feature_store/team_match.parquet",
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "upstream missing" in result.message
        assert "raw/football_data/combined_results.parquet" in result.message

    def test_skips_entries_with_none_input_hash(self, tmp_path):
        """Entries with input_hash=None are skipped (manifest already
        records the gap; re-checking adds no signal)."""
        from scoutfootball.features.manifest import hash_file

        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        raw_dir = _data_dir(tmp_path) / "raw" / "football_data"
        raw_dir.mkdir(parents=True)
        upstream_path = raw_dir / "combined_results.parquet"
        pd.DataFrame({"x": list(range(20))}).to_parquet(upstream_path)
        self._write_parquet(gold)
        self._write_manifest(
            gold,
            "team_match.parquet",
            source_lineage=[
                {
                    "name": "football_data",
                    "relative_path": "raw/football_data/combined_results.parquet",
                    "rows_read": 20,
                    "input_hash": hash_file(upstream_path),
                    "notes": None,
                },
                {
                    "name": "future_source",
                    "relative_path": "raw/future/data.parquet",
                    "rows_read": None,
                    "input_hash": None,
                    "notes": "not yet ingested",
                },
            ],
        )

        result = validate_source_lineage_freshness(
            "gold/feature_store/team_match.parquet",
            settings=_make_settings(tmp_path),
        )
        assert result.passed
        assert "All 1 upstream hash(es) match" in result.message
        assert "1 skipped" in result.message

    def test_fails_on_unreadable_manifest(self, tmp_path):
        """Manifest JSON corrupted → cannot parse, FAIL."""
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_parquet(gold)
        (gold / "team_match_manifest.json").write_text(
            "{not valid json",
            encoding="utf-8",
        )

        result = validate_source_lineage_freshness(
            "gold/feature_store/team_match.parquet",
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "Manifest unreadable" in result.message

    def test_reports_multiple_failures_in_one_message(self, tmp_path):
        """Multiple stale/missing upstreams are aggregated into one
        failure message so the maintainer sees the full picture."""
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_parquet(gold)
        self._write_manifest(
            gold,
            "team_match.parquet",
            source_lineage=[
                {
                    "name": "source_a",
                    "relative_path": "raw/a/data.parquet",
                    "rows_read": 10,
                    "input_hash": "aaaa1111aaaa1111",
                    "notes": None,
                },
                {
                    "name": "source_b",
                    "relative_path": "raw/b/data.parquet",
                    "rows_read": 10,
                    "input_hash": "bbbb2222bbbb2222",
                    "notes": None,
                },
            ],
        )

        result = validate_source_lineage_freshness(
            "gold/feature_store/team_match.parquet",
            settings=_make_settings(tmp_path),
        )
        assert not result.passed
        assert "2 stale/missing" in result.message
        assert "source_a" in result.message
        assert "source_b" in result.message


class TestRunPreTrainingValidation:
    """Verify run_pre_training_validation gates and coverage.

    These checks are the pre-training defense-in-depth layer.  The
    pipeline validates existence, row counts, key completeness, and
    value integrity for core tables before any model training runs.
    """

    def _write_minimal_valid_store(self, gold):
        """Write minimal parquets that pass all current checks.

        Writes sidecar manifests for team_match, player_match,
        rating_feature_matrix, team_rolling and player_rolling so the
        manifest_exists and manifest_freshness checks added to
        run_pre_training_validation also pass. Manifests use the new
        schema (artifact, schema_version, source_lineage, ...) for all
        five artifacts — matching what build-features currently writes
        on disk.
        """
        import json
        from datetime import UTC, datetime

        pd.DataFrame(
            {
                "match_id": [f"m{i}" for i in range(12)],
                "player_id": [f"p{i}" for i in range(12)],
                "goals": list(range(12)),
                "assists": list(range(12)),
                "minutes_played": [i * 90 for i in range(12)],
            }
        ).to_parquet(gold / "player_match.parquet")
        pd.DataFrame(
            {
                "match_id": [f"m{i}" for i in range(12)],
                "team_id": [f"t{i}" for i in range(12)],
                "goals_for": list(range(12)),
                "goals_against": list(range(12)),
            }
        ).to_parquet(gold / "team_match.parquet")
        pd.DataFrame(
            {
                "player_id": [f"p{i}" for i in range(12)],
                "season_id": ["s2526"] * 12,
            }
        ).to_parquet(gold / "rating_feature_matrix.parquet")
        # team_rolling inherits team_match columns and adds windowed
        # aggregates. Same row count (12) as team_match.
        pd.DataFrame(
            {
                "match_id": [f"m{i}" for i in range(12)],
                "team_id": [f"t{i}" for i in range(12)],
                "goals_for": list(range(12)),
                "prior_matches_3": [0.0] * 12,
            }
        ).to_parquet(gold / "team_rolling.parquet")
        # player_rolling inherits player_match columns and adds windowed
        # aggregates. Same row count (12) as player_match.
        pd.DataFrame(
            {
                "match_id": [f"m{i}" for i in range(12)],
                "player_id": [f"p{i}" for i in range(12)],
                "goals": list(range(12)),
                "prior_minutes_3": [0.0] * 12,
            }
        ).to_parquet(gold / "player_rolling.parquet")
        # player_truth_labels: supervision target for
        # train_player_rating_nn_from_files. Must pass
        # validate_truth_labels (8-column schema, valid enum values,
        # unique player_id+season+label_source keys) and the new
        # pre-training checks (existence, row_count>=10, no null keys,
        # no null label_value, schema).
        pd.DataFrame(
            {
                "player_id": [f"p{i}" for i in range(12)],
                "season": ["2526"] * 12,
                "label_source": ["transfermarkt_value"] * 12,
                "label_confidence": ["high"] * 12,
                "label_value": [float(i) for i in range(12)],
                "as_of_date": ["2025-05-31"] * 12,
                "position_scope": ["all"] * 12,
                "manual_review_flag": [False] * 12,
            }
        ).to_parquet(gold / "player_truth_labels.parquet")

        # New-schema manifests for all five artifacts. column_count
        # must match the actual parquet content so
        # validate_manifest_freshness passes. All use the same schema
        # (artifact, schema_version, total_rows, column_count, columns,
        # input_hash, source_lineage, timestamp).
        new_schema_common = {
            "schema_version": "1.0",
            "columns": [],
            "input_hash": "test-hash",
            "source_lineage": [],
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }
        with open(gold / "team_match_manifest.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "artifact": "team_match",
                    "total_rows": 12,
                    "column_count": 4,
                    **new_schema_common,
                },
                f,
            )
        with open(gold / "player_match_manifest.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "artifact": "player_match",
                    "total_rows": 12,
                    "column_count": 5,
                    **new_schema_common,
                },
                f,
            )
        # rating_feature_matrix.parquet has 2 cols (player_id, season_id).
        with open(gold / "rating_feature_matrix_manifest.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "artifact": "rating_feature_matrix",
                    "total_rows": 12,
                    "column_count": 2,
                    **new_schema_common,
                },
                f,
            )
        # team_rolling has 4 cols (match_id, team_id, goals_for,
        # prior_matches_3).
        with open(gold / "team_rolling_manifest.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "artifact": "team_rolling",
                    "total_rows": 12,
                    "column_count": 4,
                    **new_schema_common,
                },
                f,
            )
        # player_rolling has 4 cols (match_id, player_id, goals,
        # prior_minutes_3).
        with open(gold / "player_rolling_manifest.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "artifact": "player_rolling",
                    "total_rows": 12,
                    "column_count": 4,
                    **new_schema_common,
                },
                f,
            )

    def test_includes_team_match_goals_completeness_check(self, tmp_path):
        """The goals_for/goals_against NaN check must be part of the
        pre-training validation report so that source-filter regressions
        are caught before model training."""
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_minimal_valid_store(gold)

        report = run_pre_training_validation(_make_settings(tmp_path))
        check_names = [c.check_name for c in report.checks]
        assert any("no_null_values" in name and "team_match" in name for name in check_names), (
            f"run_pre_training_validation must include goals-completeness check "
            f"for team_match.parquet; got checks: {check_names}"
        )
        assert report.passed

    def test_includes_player_match_core_metric_checks(self, tmp_path):
        """Player-match goals/assists/minutes must be checked for both
        nulls and negatives — these are the foundation of all rating
        and projection features."""
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_minimal_valid_store(gold)

        report = run_pre_training_validation(_make_settings(tmp_path))
        check_names = [c.check_name for c in report.checks]
        assert any("no_null_values" in name and "player_match" in name for name in check_names)
        assert any("no_negative_values" in name and "player_match" in name for name in check_names)
        assert any("no_negative_values" in name and "team_match" in name for name in check_names)
        assert report.passed

    def test_includes_rating_matrix_uniqueness_check(self, tmp_path):
        """Rating feature matrix must have unique player-season rows;
        duplicates would double-count training samples."""
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_minimal_valid_store(gold)

        report = run_pre_training_validation(_make_settings(tmp_path))
        check_names = [c.check_name for c in report.checks]
        assert any(
            "unique_keys" in name and "rating_feature_matrix" in name
            for name in check_names
        )
        assert report.passed

    def test_fails_when_team_match_has_nan_goals(self, tmp_path):
        """If team_match.parquet contains NaN goals, validation must fail
        before training is allowed to proceed."""
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_minimal_valid_store(gold)
        # Overwrite team_match with NaN goals.
        pd.DataFrame(
            {
                "match_id": [f"m{i}" for i in range(12)],
                "team_id": [f"t{i}" for i in range(12)],
                "goals_for": [0, 1, np.nan, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                "goals_against": list(range(12)),
            }
        ).to_parquet(gold / "team_match.parquet")

        report = run_pre_training_validation(_make_settings(tmp_path))
        assert not report.passed
        failures = {c.check_name for c in report.failures}
        assert any("no_null_values" in name for name in failures), (
            f"NaN goals must trigger a no_null_values failure; got failures: {failures}"
        )

    def test_fails_when_player_match_has_negative_minutes(self, tmp_path):
        """Negative minutes in player_match must be caught before
        any rating or projection features are computed."""
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_minimal_valid_store(gold)
        # Overwrite player_match with negative minutes.
        pd.DataFrame(
            {
                "match_id": [f"m{i}" for i in range(12)],
                "player_id": [f"p{i}" for i in range(12)],
                "goals": list(range(12)),
                "assists": list(range(12)),
                "minutes_played": [i * 90 if i != 3 else -100 for i in range(12)],
            }
        ).to_parquet(gold / "player_match.parquet")

        report = run_pre_training_validation(_make_settings(tmp_path))
        assert not report.passed
        failures = {c.check_name for c in report.failures}
        assert any("no_negative_values" in name and "player_match" in name for name in failures)

    def test_fails_when_rating_matrix_has_duplicate_player_seasons(self, tmp_path):
        """Duplicate player-season rows in rating_feature_matrix must
        fail validation to prevent double-counting in training."""
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_minimal_valid_store(gold)
        # Overwrite rating matrix with duplicate keys.
        pd.DataFrame(
            {
                "player_id": ["p0", "p0", "p1", "p2"],
                "season_id": ["s2526", "s2526", "s2526", "s2526"],
            }
        ).to_parquet(gold / "rating_feature_matrix.parquet")

        report = run_pre_training_validation(_make_settings(tmp_path))
        assert not report.passed
        failures = {c.check_name for c in report.failures}
        assert any("unique_keys" in name for name in failures)

    def test_includes_manifest_exists_and_freshness_checks(self, tmp_path):
        """run_pre_training_validation must include manifest_exists,
        manifest_freshness, and source_lineage_freshness checks for all
        five feature_store parquets (team_match, player_match,
        rating_feature_matrix, team_rolling, player_rolling). Without
        these checks, a missing manifest, stale manifest, or stale
        upstream reference would silently pass and consumers could not
        detect input drift via the validation report."""
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_minimal_valid_store(gold)

        report = run_pre_training_validation(_make_settings(tmp_path))
        check_names = [c.check_name for c in report.checks]
        # manifest_exists for all five artifacts.
        assert any(
            "manifest_exists" in name and "team_match" in name for name in check_names
        ), f"Missing manifest_exists:team_match in {check_names}"
        assert any(
            "manifest_exists" in name and "player_match" in name for name in check_names
        )
        assert any(
            "manifest_exists" in name and "rating_feature_matrix" in name
            for name in check_names
        )
        assert any(
            "manifest_exists" in name and "team_rolling" in name
            for name in check_names
        ), f"Missing manifest_exists:team_rolling in {check_names}"
        assert any(
            "manifest_exists" in name and "player_rolling" in name
            for name in check_names
        ), f"Missing manifest_exists:player_rolling in {check_names}"
        # manifest_freshness for all five artifacts.
        assert any(
            "manifest_freshness" in name and "team_match" in name
            for name in check_names
        )
        assert any(
            "manifest_freshness" in name and "player_match" in name
            for name in check_names
        )
        assert any(
            "manifest_freshness" in name and "rating_feature_matrix" in name
            for name in check_names
        )
        assert any(
            "manifest_freshness" in name and "team_rolling" in name
            for name in check_names
        )
        assert any(
            "manifest_freshness" in name and "player_rolling" in name
            for name in check_names
        )
        # source_lineage_freshness for all five artifacts. The minimal
        # store uses empty source_lineage lists, so each check passes
        # with "No source_lineage entries to verify".
        for artifact in (
            "team_match",
            "player_match",
            "rating_feature_matrix",
            "team_rolling",
            "player_rolling",
        ):
            assert any(
                "source_lineage_freshness" in name and artifact in name
                for name in check_names
            ), f"Missing source_lineage_freshness:{artifact} in {check_names}"
        assert report.passed, (
            f"Minimal valid store must pass all checks; failures: "
            f"{[(c.check_name, c.message) for c in report.failures]}"
        )

    def test_fails_when_team_match_manifest_missing(self, tmp_path):
        """Missing team_match_manifest.json must fail validation so
        build-features regressions are caught before training."""
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_minimal_valid_store(gold)
        (gold / "team_match_manifest.json").unlink()

        report = run_pre_training_validation(_make_settings(tmp_path))
        assert not report.passed
        failures = {c.check_name for c in report.failures}
        assert any(
            "manifest_exists" in name and "team_match" in name for name in failures
        )

    def test_fails_when_player_match_manifest_stale(self, tmp_path):
        """Stale player_match_manifest.json (row count drift) must fail
        validation. Detects partial rebuilds where the parquet was
        rewritten but the manifest was not refreshed."""
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_minimal_valid_store(gold)
        # Rewrite player_match.parquet with a different row count, but
        # leave the manifest untouched — simulates a partial rebuild.
        pd.DataFrame(
            {
                "match_id": [f"m{i}" for i in range(20)],
                "player_id": [f"p{i}" for i in range(20)],
                "goals": list(range(20)),
                "assists": list(range(20)),
                "minutes_played": [i * 90 for i in range(20)],
            }
        ).to_parquet(gold / "player_match.parquet")

        report = run_pre_training_validation(_make_settings(tmp_path))
        assert not report.passed
        failures = {c.check_name for c in report.failures}
        assert any(
            "manifest_freshness" in name and "player_match" in name
            for name in failures
        )

    def test_includes_player_truth_labels_checks(self, tmp_path):
        """run_pre_training_validation must include existence, row_count,
        no_null_keys, no_null_values, and schema checks for
        player_truth_labels.parquet. This file is the supervision target
        for train_player_rating_nn_from_files and was previously not
        covered by any validation check despite being read directly by
        the NN training pipeline."""
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_minimal_valid_store(gold)

        report = run_pre_training_validation(_make_settings(tmp_path))
        check_names = [c.check_name for c in report.checks]
        assert any(
            "parquet_exists" in name and "player_truth_labels" in name
            for name in check_names
        ), f"Missing parquet_exists:player_truth_labels in {check_names}"
        assert any(
            "row_count" in name and "player_truth_labels" in name
            for name in check_names
        )
        assert any(
            "no_null_keys" in name and "player_truth_labels" in name
            for name in check_names
        )
        assert any(
            "no_null_values" in name and "player_truth_labels" in name
            for name in check_names
        )
        assert any(
            "truth_labels_schema" in name and "player_truth_labels" in name
            for name in check_names
        )
        assert report.passed, (
            f"Minimal valid store must pass all checks; failures: "
            f"{[(c.check_name, c.message) for c in report.failures]}"
        )

    def test_fails_when_player_truth_labels_missing(self, tmp_path):
        """Missing player_truth_labels.parquet must fail validation so
        the NN training pipeline does not silently fall through to
        'skipped: missing player_truth_labels.parquet' without any
        upstream signal."""
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_minimal_valid_store(gold)
        (gold / "player_truth_labels.parquet").unlink()

        report = run_pre_training_validation(_make_settings(tmp_path))
        assert not report.passed
        failures = {c.check_name for c in report.failures}
        assert any(
            "parquet_exists" in name and "player_truth_labels" in name
            for name in failures
        )

    def test_fails_when_player_truth_labels_has_null_label_value(self, tmp_path):
        """NaN label_value silently corrupts NN supervision targets —
        the loss is finite but the gradient points at nothing. This
        must be caught before training is allowed to proceed."""
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_minimal_valid_store(gold)
        # Overwrite with one NaN label_value.
        pd.DataFrame(
            {
                "player_id": [f"p{i}" for i in range(12)],
                "season": ["2526"] * 12,
                "label_source": ["transfermarkt_value"] * 12,
                "label_confidence": ["high"] * 12,
                "label_value": [float(i) if i != 3 else np.nan for i in range(12)],
                "as_of_date": ["2025-05-31"] * 12,
                "position_scope": ["all"] * 12,
                "manual_review_flag": [False] * 12,
            }
        ).to_parquet(gold / "player_truth_labels.parquet")

        report = run_pre_training_validation(_make_settings(tmp_path))
        assert not report.passed
        failures = {c.check_name for c in report.failures}
        assert any(
            "no_null_values" in name and "player_truth_labels" in name
            for name in failures
        )

    def test_fails_when_player_truth_labels_has_invalid_source(self, tmp_path):
        """Invalid label_source enum value breaks the
        SUPERVISION_ELIGIBLE_SOURCES policy filter silently — the row
        is excluded from supervision-eligible labels without any error,
        which means the NN trains on a quietly smaller label set."""
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_minimal_valid_store(gold)
        pd.DataFrame(
            {
                "player_id": [f"p{i}" for i in range(12)],
                "season": ["2526"] * 12,
                "label_source": ["invalid_source"] * 12,
                "label_confidence": ["high"] * 12,
                "label_value": [float(i) for i in range(12)],
                "as_of_date": ["2025-05-31"] * 12,
                "position_scope": ["all"] * 12,
                "manual_review_flag": [False] * 12,
            }
        ).to_parquet(gold / "player_truth_labels.parquet")

        report = run_pre_training_validation(_make_settings(tmp_path))
        assert not report.passed
        failures = {c.check_name for c in report.failures}
        assert any(
            "truth_labels_schema" in name and "player_truth_labels" in name
            for name in failures
        )

    def test_fails_when_player_truth_labels_has_duplicate_keys(self, tmp_path):
        """Duplicate player_id+season+label_source rows break the
        schema's duplicate-key invariant and silently double-count
        labels in NN training."""
        gold = _data_dir(tmp_path) / "gold" / "feature_store"
        gold.mkdir(parents=True)
        self._write_minimal_valid_store(gold)
        # 12 rows but two share the same (player_id, season, label_source).
        pd.DataFrame(
            {
                "player_id": [f"p{i // 2}" for i in range(12)],
                "season": ["2526"] * 12,
                "label_source": ["transfermarkt_value"] * 12,
                "label_confidence": ["high"] * 12,
                "label_value": [float(i) for i in range(12)],
                "as_of_date": ["2025-05-31"] * 12,
                "position_scope": ["all"] * 12,
                "manual_review_flag": [False] * 12,
            }
        ).to_parquet(gold / "player_truth_labels.parquet")

        report = run_pre_training_validation(_make_settings(tmp_path))
        assert not report.passed
        failures = {c.check_name for c in report.failures}
        assert any(
            "truth_labels_schema" in name and "player_truth_labels" in name
            for name in failures
        )


class TestCalibration:
    def test_isotonic_improves_or_maintains(self):
        rng = np.random.default_rng(99)
        y_true = rng.binomial(1, 0.3, size=500)
        y_prob = np.clip(y_true * 0.5 + rng.normal(0, 0.2, size=500), 0, 1)
        calibrated, result = calibrate_probabilities_isotonic(y_true, y_prob)
        assert result.method == "isotonic"
        assert result.brier_after <= result.brier_before + 1e-6
        assert len(calibrated) == len(y_prob)

    def test_brier_score_perfect(self):
        y_true = np.array([1.0, 0.0, 1.0])
        y_prob = np.array([1.0, 0.0, 1.0])
        assert brier_score(y_true, y_prob) == pytest.approx(0.0)

    def test_brier_score_worst(self):
        y_true = np.array([1.0, 0.0])
        y_prob = np.array([0.0, 1.0])
        assert brier_score(y_true, y_prob) == pytest.approx(1.0)

    def test_small_sample_returns_uncalibrated(self):
        y_true = np.array([1.0, 0.0])
        y_prob = np.array([0.8, 0.2])
        calibrated, result = calibrate_probabilities_isotonic(y_true, y_prob)
        assert result.improvement == 0.0


class TestPipeline:
    def test_daily_ingest_isolated_from_repository_data(self, tmp_path):
        from scoutfootball.pipeline import run_daily_ingest

        settings = _make_settings(tmp_path)
        results = run_daily_ingest(sources=("statsbomb_open",), settings=settings)

        assert results["statsbomb_open"] == "skipped: no cached StatsBomb match directory"
        assert not settings.raw_root.exists()

    def test_build_features_fails_gracefully_with_empty_local_data_root(self, tmp_path):
        from scoutfootball.pipeline import run_build_features

        settings = _make_settings(tmp_path)
        results = run_build_features(settings=settings)

        assert results["features"].startswith("failed:")
        assert not settings.gold_root.exists()

    def test_build_features_includes_post_build_validation_result(self, tmp_path):
        """``run_build_features`` must include a post-build validation result.

        Defense-in-depth complement to the pre-training validation gate in
        ``run_weekly_train``. Without this, a manifest write failure or
        partial rebuild leaves the disk inconsistent but ``build-features``
        returns "ok" — the maintainer only finds out when they separately
        run ``validate`` or ``train``. Post-build validation closes this
        gap by running the same 26-check validation immediately after the
        write phase.

        With an empty data root, the build fails and validation also fails
        (all parquets missing). The test verifies both signals are present.
        """
        from scoutfootball.pipeline import run_build_features

        settings = _make_settings(tmp_path)
        results = run_build_features(settings=settings)

        # Build fails because the data root is empty.
        assert results["features"].startswith("failed:")
        # Post-build validation must be present and must report failure
        # (all parquets missing). It must not raise or silently skip.
        assert "validation" in results
        validation = results["validation"]
        assert validation.startswith("FAIL") or validation.startswith("skipped")

    def test_weekly_train_skips_on_validation_failure(self, tmp_path):
        from scoutfootball.pipeline import run_weekly_train

        results = run_weekly_train(
            skip_if_validation_fails=True,
            settings=_make_settings(tmp_path),
        )
        assert results.get("status") == "skipped"

    def test_cli_train_defaults_to_skip_on_validation_failure(self, monkeypatch):
        """CLI ``scoutfootball train`` must default to fail-closed.

        Regression for a G0-B gate bypass: ``_cmd_train`` previously called
        ``run_weekly_train(skip_if_validation_fails=False)``, explicitly
        disabling the 26-check pre-training validation gate. The function
        default (``True``) and WORKFLOW_LOG.md reference workflow 5 both
        claim the gate is active, but the CLI override made it a no-op.
        After the fix, the CLI defaults to ``skip_if_validation_fails=True``
        and only ``--force`` overrides.
        """
        import argparse

        from scoutfootball import __main__ as main_module

        captured: dict[str, bool] = {}

        def fake_run_weekly_train(*, skip_if_validation_fails: bool, **_kwargs):
            captured["skip_if_validation_fails"] = skip_if_validation_fails
            return {"validation": "Validation: PASS"}

        monkeypatch.setattr(
            main_module, "run_weekly_train", fake_run_weekly_train, raising=False
        )
        # The import inside _cmd_train looks up run_weekly_train on the
        # pipeline module, so patch there too.
        from scoutfootball import pipeline

        monkeypatch.setattr(pipeline, "run_weekly_train", fake_run_weekly_train)

        args = argparse.Namespace(force=False)
        main_module._cmd_train(args)
        assert captured["skip_if_validation_fails"] is True

    def test_cli_train_force_flag_overrides_validation_gate(self, monkeypatch):
        """``scoutfootball train --force`` explicitly overrides the gate.

        The ``--force`` flag is the supported escape hatch for debugging or
        for training on known-incomplete data at the maintainer's risk. It
        must pass ``skip_if_validation_fails=False`` so the maintainer can
        still train when validation fails for a known, accepted reason.
        """
        import argparse

        from scoutfootball import __main__ as main_module
        from scoutfootball import pipeline

        captured: dict[str, bool] = {}

        def fake_run_weekly_train(*, skip_if_validation_fails: bool, **_kwargs):
            captured["skip_if_validation_fails"] = skip_if_validation_fails
            return {"validation": "Validation: PASS"}

        monkeypatch.setattr(
            main_module, "run_weekly_train", fake_run_weekly_train, raising=False
        )
        monkeypatch.setattr(pipeline, "run_weekly_train", fake_run_weekly_train)

        args = argparse.Namespace(force=True)
        main_module._cmd_train(args)
        assert captured["skip_if_validation_fails"] is False

    def test_cli_train_subparser_parses_force_flag(self):
        """The ``train`` subparser must accept ``--force`` and default to False."""
        from scoutfootball.__main__ import build_parser

        parser = build_parser()
        # Default: no --force
        args_no_force = parser.parse_args(["train"])
        assert args_no_force.force is False
        # Explicit --force
        args_force = parser.parse_args(["train", "--force"])
        assert args_force.force is True

    def test_cli_train_rating_nn_defaults_to_skip_on_validation_failure(
        self, monkeypatch, capsys
    ):
        """CLI ``scoutfootball train-rating-nn`` must default to fail-closed.

        Regression for a G0-B gate asymmetry: Round 17 fixed the ``train``
        command to default to ``skip_if_validation_fails=True``, but
        ``train-rating-nn`` — a parallel path that produces the same NN
        candidate artifacts — had no validation gate at all. A maintainer
        could silently train an NN candidate on inconsistent data by using
        ``train-rating-nn`` instead of ``train``. After the fix, the gate
        runs first and skips training when validation fails (unless
        ``--force``).
        """
        import argparse

        from scoutfootball import __main__ as main_module
        from scoutfootball.evaluation.validation import ValidationReport

        # Failed report: one failing check.
        failed_report = ValidationReport(
            checks=[ValidationCheckResult("fake_check", False, "fake failure")]
        )

        def fake_run_pre_training_validation(*_args, **_kwargs):
            return failed_report

        train_called: list[bool] = []

        def fake_train(*_args, **_kwargs):
            train_called.append(True)
            return None

        monkeypatch.setattr(
            main_module,
            "run_pre_training_validation",
            fake_run_pre_training_validation,
            raising=False,
        )
        # The import inside _cmd_train_rating_nn looks up
        # run_pre_training_validation on the validation module, so patch there too.
        from scoutfootball.evaluation import validation as validation_module

        monkeypatch.setattr(
            validation_module, "run_pre_training_validation", fake_run_pre_training_validation
        )
        # Patch train_player_rating_nn_from_files on the module where it's
        # imported (player_rating_nn), so the local import inside the cmd
        # function picks up the fake.
        from scoutfootball.models import player_rating_nn as nn_module

        monkeypatch.setattr(nn_module, "train_player_rating_nn_from_files", fake_train)

        args = argparse.Namespace(
            force=False, min_labels=200, max_iter=300, seed=42, output_dir=None
        )
        main_module._cmd_train_rating_nn(args)

        # Training must NOT have been called.
        assert train_called == []
        captured = capsys.readouterr()
        assert "Skipping training" in captured.out
        assert "pre-training validation failed" in captured.out

    def test_cli_train_rating_nn_force_flag_overrides_validation_gate(
        self, monkeypatch, capsys
    ):
        """``scoutfootball train-rating-nn --force`` overrides the gate.

        The ``--force`` flag is the supported escape hatch for debugging or
        for training on known-incomplete data at the maintainer's risk. It
        must let training proceed even when validation fails.
        """
        import argparse

        from scoutfootball import __main__ as main_module
        from scoutfootball.evaluation.validation import ValidationReport

        failed_report = ValidationReport(
            checks=[ValidationCheckResult("fake_check", False, "fake failure")]
        )

        def fake_run_pre_training_validation(*_args, **_kwargs):
            return failed_report

        train_called: list[bool] = []

        class FakeResult:
            status = "trained (fake)"
            metrics = {}

        def fake_train(*_args, **_kwargs):
            train_called.append(True)
            return FakeResult()

        monkeypatch.setattr(
            main_module,
            "run_pre_training_validation",
            fake_run_pre_training_validation,
            raising=False,
        )
        from scoutfootball.evaluation import validation as validation_module

        monkeypatch.setattr(
            validation_module, "run_pre_training_validation", fake_run_pre_training_validation
        )
        from scoutfootball.models import player_rating_nn as nn_module

        monkeypatch.setattr(nn_module, "train_player_rating_nn_from_files", fake_train)

        args = argparse.Namespace(
            force=True, min_labels=200, max_iter=300, seed=42, output_dir=None
        )
        main_module._cmd_train_rating_nn(args)

        # Training MUST have been called despite validation failure.
        assert train_called == [True]
        captured = capsys.readouterr()
        assert "trained (fake)" in captured.out

    def test_cli_train_rating_nn_proceeds_when_validation_passes(
        self, monkeypatch, capsys
    ):
        """When validation passes, ``train-rating-nn`` must proceed to train.

        This is the normal happy path: validation gate opens and training
        runs. Verifies the gate doesn't false-positive on a passing report.
        """
        import argparse

        from scoutfootball import __main__ as main_module
        from scoutfootball.evaluation.validation import ValidationReport

        passed_report = ValidationReport(
            checks=[ValidationCheckResult("fake_check", True, "ok")]
        )

        def fake_run_pre_training_validation(*_args, **_kwargs):
            return passed_report

        train_called: list[bool] = []

        class FakeResult:
            status = "trained (fake)"
            metrics = {}

        def fake_train(*_args, **_kwargs):
            train_called.append(True)
            return FakeResult()

        monkeypatch.setattr(
            main_module,
            "run_pre_training_validation",
            fake_run_pre_training_validation,
            raising=False,
        )
        from scoutfootball.evaluation import validation as validation_module

        monkeypatch.setattr(
            validation_module, "run_pre_training_validation", fake_run_pre_training_validation
        )
        from scoutfootball.models import player_rating_nn as nn_module

        monkeypatch.setattr(nn_module, "train_player_rating_nn_from_files", fake_train)

        # force=False is the default; gate must open because validation passes.
        args = argparse.Namespace(
            force=False, min_labels=200, max_iter=300, seed=42, output_dir=None
        )
        main_module._cmd_train_rating_nn(args)

        assert train_called == [True]
        captured = capsys.readouterr()
        assert "trained (fake)" in captured.out

    def test_cli_train_rating_nn_subparser_parses_force_flag(self):
        """The ``train-rating-nn`` subparser must accept ``--force`` and default to False."""
        from scoutfootball.__main__ import build_parser

        parser = build_parser()
        # Default: no --force
        args_no_force = parser.parse_args(["train-rating-nn"])
        assert args_no_force.force is False
        # Explicit --force
        args_force = parser.parse_args(["train-rating-nn", "--force"])
        assert args_force.force is True

    def test_build_team_match_filters_nan_goals_placeholder_rows(self, tmp_path):
        """Football-Data future-match placeholder rows (NaN FTHG/FTAG) must be
        filtered before entering team_match.parquet.

        Regression for the root cause behind the fit_dixon_coles NaN bug: the
        football-data.co.uk results CSVs include scheduled-but-not-yet-played
        matches with NaN FTHG/FTAG/FTR. Without filtering, these rows produce
        NaN goals_for/goals_against in team_match.parquet and silently corrupt
        downstream model training. See WORKFLOW_LOG.md reference workflow 3.
        """
        from scoutfootball.pipeline import _build_team_match_from_football_data

        settings = _make_settings(tmp_path)
        raw_fd_dir = settings.raw_root / "football_data"
        raw_fd_dir.mkdir(parents=True)
        input_path = raw_fd_dir / "combined_results.parquet"

        # Mix of valid rows and one future-match placeholder (NaN FTHG/FTAG/FTR).
        # The placeholder mirrors the real Bastia vs Red Star 2025-12-05 row
        # observed in data/raw/football_data/combined_results.parquet.
        rows = [
            {
                "Div": "E0", "Date": "01/01/2025", "HomeTeam": "Arsenal",
                "AwayTeam": "Chelsea", "FTHG": 2, "FTAG": 1, "FTR": "H",
                "league": "Premier League", "season": "2425",
            },
            {
                "Div": "E0", "Date": "02/01/2025", "HomeTeam": "Liverpool",
                "AwayTeam": "Man City", "FTHG": 1, "FTAG": 1, "FTR": "D",
                "league": "Premier League", "season": "2425",
            },
            # Future-match placeholder: NaN goals across the board.
            {
                "Div": "F2", "Date": "05/12/2025", "HomeTeam": "Bastia",
                "AwayTeam": "Red Star", "FTHG": pd.NA, "FTAG": pd.NA,
                "FTR": pd.NA, "league": "Ligue 2", "season": "2526",
            },
        ]
        pd.DataFrame(rows).to_parquet(input_path, index=False)

        team_match = _build_team_match_from_football_data(settings)

        # 2 valid matches × 2 teams per match = 4 rows; placeholder dropped.
        assert len(team_match) == 4
        assert team_match["goals_for"].notna().all()
        assert team_match["goals_against"].notna().all()
        # Placeholder teams must not appear in the output.
        assert "Bastia" not in set(team_match["team_name"])
        assert "Red Star" not in set(team_match["team_name"])

    def test_build_team_match_all_nan_raises(self, tmp_path):
        """If every Football-Data row has NaN goals, the build must fail loudly
        rather than producing an empty or NaN-filled team_match.parquet."""
        from scoutfootball.pipeline import _build_team_match_from_football_data

        settings = _make_settings(tmp_path)
        raw_fd_dir = settings.raw_root / "football_data"
        raw_fd_dir.mkdir(parents=True)
        input_path = raw_fd_dir / "combined_results.parquet"

        rows = [
            {
                "Div": "E0", "Date": "01/01/2025", "HomeTeam": "Arsenal",
                "AwayTeam": "Chelsea", "FTHG": pd.NA, "FTAG": pd.NA,
                "FTR": pd.NA, "league": "Premier League", "season": "2425",
            },
        ]
        pd.DataFrame(rows).to_parquet(input_path, index=False)

        with pytest.raises(ValueError, match="future-match placeholders"):
            _build_team_match_from_football_data(settings)

    def test_load_team_match_from_gold_reads_gold_parquet(self, monkeypatch):
        """``_load_team_match_from_gold`` must read the gold parquet and return
        only the columns required by backtest/tune/optimize commands.

        Regression for the dual-source-of-truth gap: ``backtest``,
        ``tune-predictions``, and ``optimize-ensemble`` previously rebuilt a
        separate team_match frame from raw ``combined_results.parquet`` with
        different ``match_id`` format (``{home}_{away}_{date}`` vs gold's
        ``fd-match-{N}``) and different ``team_id`` values
        (``normalize_team_name(HomeTeam)`` vs raw ``HomeTeam``). That meant
        decay values tuned by ``tune-predictions`` and ensemble weights
        computed by ``optimize-ensemble`` were optimized on a different frame
        than ``train`` actually uses. The fix unifies on the gold artifact.
        """
        from pathlib import Path

        from scoutfootball import __main__ as main_module

        # Controlled gold parquet content with required columns + extras.
        fake_gold = pd.DataFrame(
            {
                "match_id": [
                    "fd-match-1", "fd-match-1", "fd-match-2", "fd-match-2",
                ],
                "match_date": pd.to_datetime(
                    ["2025-01-01", "2025-01-01", "2025-01-08", "2025-01-08"]
                ),
                "team_id": ["Arsenal", "Chelsea", "Liverpool", "Man City"],
                "is_home": [True, False, True, False],
                "goals_for": [2, 1, 1, 1],
                "goals_against": [1, 2, 1, 1],
                # Extra columns must be filtered out by the function.
                "competition_id": ["EPL", "EPL", "EPL", "EPL"],
                "team_name": ["Arsenal", "Chelsea", "Liverpool", "Man City"],
            }
        )

        def fake_read_parquet(path, **_kwargs):
            return fake_gold.copy()

        monkeypatch.setattr(main_module.pd, "read_parquet", fake_read_parquet)
        monkeypatch.setattr(Path, "exists", lambda self: True)

        result = main_module._load_team_match_from_gold()

        # Must return ONLY the 6 required columns (extras filtered out).
        expected_cols = {
            "match_id", "match_date", "team_id", "is_home",
            "goals_for", "goals_against",
        }
        assert set(result.columns) == expected_cols
        assert len(result) == 4
        # Verify match_id format matches gold (fd-match-{N}), not the old
        # raw format ({home}_{away}_{date}).
        assert all(mid.startswith("fd-match-") for mid in result["match_id"])

    def test_load_team_match_from_gold_exits_when_parquet_missing(
        self, monkeypatch, capsys
    ):
        """If the gold team_match.parquet does not exist, the function must
        exit with code 1 and print a helpful message telling the maintainer
        to run ``scoutfootball build-features``.

        Without this guard, the backtest/tune/optimize commands would later
        crash with an opaque FileNotFoundError deep inside the model code.
        """
        from pathlib import Path

        from scoutfootball import __main__ as main_module

        monkeypatch.setattr(Path, "exists", lambda self: False)

        with pytest.raises(SystemExit) as exc_info:
            main_module._load_team_match_from_gold()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "gold team_match.parquet not found" in captured.out
        assert "build-features" in captured.out

    def test_load_team_match_from_gold_exits_when_required_columns_missing(
        self, monkeypatch, capsys
    ):
        """If the gold parquet exists but is missing required columns (e.g.,
        a partial rebuild or schema drift), the function must exit with code 1
        rather than passing a malformed frame to the model code.
        """
        from pathlib import Path

        from scoutfootball import __main__ as main_module

        # Missing is_home, goals_for, goals_against.
        fake_gold = pd.DataFrame(
            {
                "match_id": ["fd-match-1"],
                "match_date": pd.to_datetime(["2025-01-01"]),
                "team_id": ["Arsenal"],
            }
        )

        def fake_read_parquet(path, **_kwargs):
            return fake_gold.copy()

        monkeypatch.setattr(main_module.pd, "read_parquet", fake_read_parquet)
        monkeypatch.setattr(Path, "exists", lambda self: True)

        with pytest.raises(SystemExit) as exc_info:
            main_module._load_team_match_from_gold()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "missing required columns" in captured.out


class TestAPI:
    def test_health_check(self):
        from scoutfootball.api import health_check

        resp = health_check()
        assert resp.status == "ok"
        assert resp.version == "1.0.3"

    def test_list_players(self):
        from scoutfootball.api import list_players

        resp = list_players()
        assert resp.player_count >= 0
        assert isinstance(resp.players, list)

    def test_list_teams(self):
        from scoutfootball.api import list_teams

        teams = list_teams()
        assert isinstance(teams, list)

    def test_get_match_prediction(self):
        from scoutfootball.api import get_match_prediction

        result = get_match_prediction("Arsenal", "Chelsea")
        if "error" in result:
            # If real data isn't available, verify error response structure
            assert isinstance(result["error"], str)
        else:
            assert "home_win" in result
            assert "away_win" in result
            assert result["home_team"] == "Arsenal"
            assert result["away_team"] == "Chelsea"

    def test_get_value_summary(self):
        from scoutfootball.api import get_value_summary

        result = get_value_summary()
        assert "sample_count" in result

    def test_get_artifacts_summary(self):
        from scoutfootball.api import get_artifacts_summary

        result = get_artifacts_summary()
        assert "player_match_rows" in result
        assert "artifacts" in result
        assert isinstance(result["artifacts"], list)

    def test_artifacts_license_attribution_covers_registered_sources(self):
        """license_attribution must cover all 6 architecture-registered sources."""
        from scoutfootball.api import get_artifacts_summary

        result = get_artifacts_summary()
        attribution = result.get("license_attribution", {})
        # The 6 sources registered in architecture.py planned_components
        required = {"statsbomb", "fbref", "football_data", "understat", "clubelo", "transfermarkt"}
        missing = required - set(attribution.keys())
        assert not missing, f"license_attribution missing registered sources: {missing}"

    def test_get_prediction_summary(self):
        from scoutfootball.api import get_prediction_summary

        result = get_prediction_summary()
        assert "poisson" in result
        assert "dixon_coles" in result
        assert "available_models" in result

    def test_get_model_runs(self):
        from scoutfootball.api import get_model_runs

        result = get_model_runs()
        assert "count" in result
        assert "runs" in result

    def test_get_watchlist(self):
        from scoutfootball.api import get_watchlist

        result = get_watchlist(limit=10)
        assert "count" in result
        assert "players" in result

    def test_get_shortlist(self):
        from scoutfootball.api import get_shortlist

        result = get_shortlist(limit=10)
        assert "count" in result
        assert "players" in result

    def test_get_action_value_summary(self):
        from scoutfootball.api import get_action_value_summary

        result = get_action_value_summary(limit=5)
        assert "status" in result
        assert "players" in result
        if result["status"] == "ok":
            assert len(result["xt_players"]) <= 5
            assert len(result["vaep_players"]) <= 5
            assert result["model_granularity"]["vaep"] == "player_team_career"
            assert result["identity_coverage"]["total_rows"] == result["metrics"]["vaep_rows"]
