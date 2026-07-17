from __future__ import annotations

import pytest

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.source_health import build_source_health_report


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
    assert football_data["local_observation"]["file_count"] == 1
    assert football_data["snapshot"]["status"] == "not_recorded"
    assert report["unregistered_raw_directories"] == ["unregistered_source"]


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
