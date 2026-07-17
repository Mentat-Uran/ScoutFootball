from __future__ import annotations

import pytest

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.source_health import (
    build_source_health_report,
    format_source_health_report,
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
