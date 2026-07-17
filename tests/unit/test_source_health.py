from __future__ import annotations

import pytest

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.source_health import (
    DEFAULT_DATA_HEALTH_DIR,
    DEFAULT_SOURCE_POLICY_LEDGER_FILENAME,
    DEFAULT_SOURCE_SNAPSHOT_LEDGER_FILENAME,
    build_source_health_report,
    format_source_health_report,
    resolve_local_ledger_path,
    source_license_policy_status,
)
from scoutfootball.evaluation.source_policy_ledger import (
    append_source_policy_record,
    build_source_policy_record,
)
from scoutfootball.schemas.storage import SourceLicense


def test_source_health_marks_local_observation_separately_from_snapshot(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    source_file = settings.data_root / "raw" / "football_data" / "results.csv"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("date,result\n", encoding="utf-8")
    (settings.data_root / "raw" / "unregistered_source").mkdir()

    report = build_source_health_report(settings)

    football_data = next(
        item for item in report["registered_sources"] if item["source_id"] == "football_data"
    )
    assert football_data["license"]["status"] == "recorded"
    assert football_data["license"]["policy"]["status"] == "baseline_required"
    assert football_data["license"]["policy"]["missing_fields"] == [
        "retention_policy_days",
        "deletion_strategy",
    ]
    assert football_data["local_observation"]["file_count"] == 1
    assert football_data["snapshot"]["status"] == "not_recorded"
    assert report["unregistered_raw_directories"] == ["unregistered_source"]
    details = report["unregistered_raw_directory_details"]
    assert details[0]["directory"] == "unregistered_source"
    assert details[0]["file_count"] == 0
    assert details[0]["newest_local_mtime"] is None


def test_source_health_exposes_only_local_metadata_for_unregistered_files(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    legacy_file = settings.raw_root / "legacy_source" / "nested" / "input.csv"
    legacy_file.parent.mkdir(parents=True)
    legacy_file.write_text("private local content\n", encoding="utf-8")

    report = build_source_health_report(settings)
    detail = report["unregistered_raw_directory_details"][0]

    assert detail["directory"] == "legacy_source"
    assert detail["file_count"] == 1
    assert detail["total_bytes"] == legacy_file.stat().st_size
    assert detail["files"][0]["relative_path"] == "legacy_source/nested/input.csv"
    assert detail["files"][0]["bytes"] == legacy_file.stat().st_size
    assert detail["files"][0]["local_mtime"]
    assert "private local content" not in str(detail)


def test_source_health_attaches_only_valid_raw_inspections(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    evidence = {
        "report_type": "scoutfootball.parquet_preflight_evidence",
        "generated_at": "2026-07-17T00:00:00Z",
        "artifacts": [
            {
                "artifact_path": "raw/football_data/results.parquet",
                "inspection": {"content_hash": "abc", "row_count": 2, "reader": "duckdb"},
            }
        ],
    }

    report = build_source_health_report(settings, preflight_evidence=evidence)

    football_data = next(
        item for item in report["registered_sources"] if item["source_id"] == "football_data"
    )
    assert football_data["inspection_capture"][0]["content_hash"] == "abc"


def test_source_health_accepts_raw_csv_inspection(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    evidence = {
        "report_type": "scoutfootball.raw_source_file_inspection",
        "generated_at": "2026-07-17T00:00:00Z",
        "source_id": "reep",
        "artifacts": [
            {
                "artifact_path": "raw/reep/people.csv",
                "inspection": {"content_hash": "abc", "row_count": 2, "reader": "python_csv_utf8"},
            }
        ],
    }

    report = build_source_health_report(settings, preflight_evidence=evidence)

    reep = next(item for item in report["registered_sources"] if item["source_id"] == "reep")
    assert reep["inspection_capture"][0]["content_hash"] == "abc"


def test_source_health_rejects_evidence_path_escape(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    evidence = {
        "report_type": "scoutfootball.parquet_preflight_evidence",
        "artifacts": [{"artifact_path": "../secret.parquet", "inspection": {}}],
    }

    with pytest.raises(ValueError, match="evidence_artifact_path_invalid"):
        build_source_health_report(settings, preflight_evidence=evidence)


def test_source_health_exposes_only_explicit_ledger_snapshots(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    ledger = tmp_path / "snapshots.jsonl"
    ledger.write_text(
        '{"record_type":"scoutfootball.source_snapshot_ledger","snapshot_id":"id","source_id":"football_data","snapshot_date":"2026-07-16","recorded_at":"2026-07-17T00:00:00Z","evidence":{"artifact_count":1}}\n',
        encoding="utf-8",
    )

    report = build_source_health_report(settings, snapshot_ledger_path=str(ledger))

    football_data = next(
        item for item in report["registered_sources"] if item["source_id"] == "football_data"
    )
    assert football_data["snapshot"]["status"] == "recorded"
    assert football_data["snapshot"]["as_of"] == "2026-07-16"


def test_source_health_uses_an_explicit_local_policy_ledger(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    ledger = tmp_path / "source_policies.jsonl"
    record = build_source_policy_record(
        source_id="football_data",
        retention_mode="until_manual_deletion",
        retention_days=None,
        deletion_trigger="Maintainer requests deletion.",
        deletion_strategy="Remove local raw source files after confirmation.",
        derived_artifact_action="Invalidate dependent artifacts for regeneration.",
        decision="Local policy approved by maintainer.",
        recorded_at="2026-07-17T00:00:00Z",
    )
    append_source_policy_record(record, ledger)

    report = build_source_health_report(settings, policy_ledger_path=str(ledger))
    football_data = next(
        item for item in report["registered_sources"] if item["source_id"] == "football_data"
    )

    assert report["policy_ledger_supplied"] is True
    assert football_data["license"]["policy"]["status"] == "recorded"
    assert football_data["license"]["policy"]["policy_source"] == "local_policy_ledger"
    assert football_data["license"]["policy"]["retention_mode"] == "until_manual_deletion"


def test_source_license_policy_status_requires_explicit_retention_and_deletion_terms() -> None:
    incomplete = source_license_policy_status(
        SourceLicense(source_name="local_fixture", license_name="local test")
    )
    complete = source_license_policy_status(
        SourceLicense(
            source_name="local_fixture",
            license_name="local test",
            retention_policy_days=30,
            deletion_strategy=(
                "Remove local raw data and derived artifacts on a documented request."
            ),
        )
    )

    assert incomplete["status"] == "baseline_required"
    assert complete["status"] == "recorded"
    assert complete["missing_fields"] == []


def test_source_health_formatter_accepts_a_legacy_report_without_policy_field() -> None:
    rendered = format_source_health_report(
        {
            "registered_source_count": 1,
            "registered_sources": [
                {
                    "source_id": "legacy_source",
                    "license": {"status": "recorded"},
                    "local_observation": {"status": "empty", "file_count": 0},
                    "snapshot": {"status": "not_recorded"},
                }
            ],
            "unregistered_raw_directories": [],
        }
    )

    assert "policy=not_recorded" in rendered


def test_resolve_local_ledger_path_returns_none_when_no_default_exists(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)

    assert resolve_local_ledger_path(settings, None, "missing.jsonl") is None


def test_resolve_local_ledger_path_returns_explicit_path_even_when_file_missing(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    explicit = str(tmp_path / "user_supplied.jsonl")

    assert resolve_local_ledger_path(settings, explicit, "missing.jsonl") == explicit


def test_resolve_local_ledger_path_auto_discovers_canonical_default(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    default_dir = settings.report_root / DEFAULT_DATA_HEALTH_DIR
    default_dir.mkdir(parents=True)
    default_file = default_dir / DEFAULT_SOURCE_POLICY_LEDGER_FILENAME
    default_file.write_text("", encoding="utf-8")

    resolved = resolve_local_ledger_path(
        settings, None, DEFAULT_SOURCE_POLICY_LEDGER_FILENAME
    )

    assert resolved == str(default_file)


def test_resolve_local_ledger_path_explicit_overrides_existing_default(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    default_dir = settings.report_root / DEFAULT_DATA_HEALTH_DIR
    default_dir.mkdir(parents=True)
    (default_dir / DEFAULT_SOURCE_POLICY_LEDGER_FILENAME).write_text("", encoding="utf-8")
    explicit = str(tmp_path / "override.jsonl")

    assert resolve_local_ledger_path(
        settings, explicit, DEFAULT_SOURCE_POLICY_LEDGER_FILENAME
    ) == explicit


def test_source_health_auto_discovers_default_policy_ledger(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    ledger_dir = settings.report_root / DEFAULT_DATA_HEALTH_DIR
    ledger_dir.mkdir(parents=True)
    ledger_path = ledger_dir / DEFAULT_SOURCE_POLICY_LEDGER_FILENAME
    record = build_source_policy_record(
        source_id="football_data",
        retention_mode="until_manual_deletion",
        retention_days=None,
        deletion_trigger="Maintainer requests deletion.",
        deletion_strategy="Remove local raw source files after confirmation.",
        derived_artifact_action="Invalidate dependent artifacts for regeneration.",
        decision="Local policy approved by maintainer.",
        recorded_at="2026-07-17T00:00:00Z",
    )
    append_source_policy_record(record, ledger_path)

    # No explicit ledger path supplied; auto-discovery must surface the recorded policy.
    report = build_source_health_report(settings)

    assert report["policy_ledger_supplied"] is True
    assert report["snapshot_ledger_supplied"] is False
    football_data = next(
        item for item in report["registered_sources"] if item["source_id"] == "football_data"
    )
    assert football_data["license"]["policy"]["status"] == "recorded"
    assert football_data["license"]["policy"]["policy_source"] == "local_policy_ledger"


def test_source_health_auto_discovers_default_snapshot_ledger(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    ledger_dir = settings.report_root / DEFAULT_DATA_HEALTH_DIR
    ledger_dir.mkdir(parents=True)
    ledger_path = ledger_dir / DEFAULT_SOURCE_SNAPSHOT_LEDGER_FILENAME
    ledger_path.write_text(
        '{"record_type":"scoutfootball.source_snapshot_ledger","snapshot_id":"id",'
        '"source_id":"football_data","snapshot_date":"2026-07-16",'
        '"recorded_at":"2026-07-17T00:00:00Z","evidence":{"artifact_count":1}}\n',
        encoding="utf-8",
    )

    report = build_source_health_report(settings)

    assert report["snapshot_ledger_supplied"] is True
    football_data = next(
        item for item in report["registered_sources"] if item["source_id"] == "football_data"
    )
    assert football_data["snapshot"]["status"] == "recorded"
    assert football_data["snapshot"]["as_of"] == "2026-07-16"


def test_source_health_explicit_policy_ledger_overrides_default(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    default_dir = settings.report_root / DEFAULT_DATA_HEALTH_DIR
    default_dir.mkdir(parents=True)
    default_ledger = default_dir / DEFAULT_SOURCE_POLICY_LEDGER_FILENAME
    # Record a policy for football_data in the default ledger.
    default_record = build_source_policy_record(
        source_id="football_data",
        retention_mode="until_manual_deletion",
        retention_days=None,
        deletion_trigger="Maintainer requests deletion.",
        deletion_strategy="Remove local raw source files after confirmation.",
        derived_artifact_action="Invalidate dependent artifacts for regeneration.",
        decision="Default-ledger policy declaration.",
        recorded_at="2026-07-17T00:00:00Z",
    )
    append_source_policy_record(default_record, default_ledger)
    # Explicit override ledger records a policy for clubelo instead.
    override_ledger = tmp_path / "override_policy.jsonl"
    override_record = build_source_policy_record(
        source_id="clubelo",
        retention_mode="until_manual_deletion",
        retention_days=None,
        deletion_trigger="Maintainer requests deletion.",
        deletion_strategy="Remove local raw source files after confirmation.",
        derived_artifact_action="Invalidate dependent artifacts for regeneration.",
        decision="Override-ledger policy declaration.",
        recorded_at="2026-07-17T00:00:00Z",
    )
    append_source_policy_record(override_record, override_ledger)

    report = build_source_health_report(
        settings, policy_ledger_path=str(override_ledger)
    )

    # The override ledger is consumed; the default ledger is ignored.
    football_data = next(
        item for item in report["registered_sources"] if item["source_id"] == "football_data"
    )
    clubelo = next(
        item for item in report["registered_sources"] if item["source_id"] == "clubelo"
    )
    assert football_data["license"]["policy"]["status"] == "baseline_required"
    assert clubelo["license"]["policy"]["status"] == "recorded"
    assert clubelo["license"]["policy"]["policy_source"] == "local_policy_ledger"


def test_source_health_empty_default_workspace_keeps_baseline_required(tmp_path) -> None:
    """Auto-discovery must not invent evidence when the default ledger file is absent."""
    settings = PlatformSettings.from_root(tmp_path)

    report = build_source_health_report(settings)

    assert report["policy_ledger_supplied"] is False
    assert report["snapshot_ledger_supplied"] is False
    football_data = next(
        item for item in report["registered_sources"] if item["source_id"] == "football_data"
    )
    assert football_data["license"]["policy"]["status"] == "baseline_required"
    assert football_data["snapshot"]["status"] == "not_recorded"
