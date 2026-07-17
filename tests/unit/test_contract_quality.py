"""Tests for truthful contract-quality baseline reporting."""

from __future__ import annotations

import pytest

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.contract_quality import build_contract_quality_report


def _evidence(*, ok: bool = True) -> dict:
    return {
        "report_type": "scoutfootball.parquet_preflight_evidence",
        "generated_at": "2026-07-17T00:00:00Z",
        "artifacts": [
            {
                "artifact_path": "raw/football_data/results.parquet",
                "inspection": {
                    "exists": True,
                    "readable": ok,
                    "row_count": 2 if ok else None,
                    "footer_content_mismatch": False,
                    "sample_ok": ok,
                },
            }
        ],
    }


def _check(report: dict, name: str) -> dict:
    return next(item for item in report["checks"] if item["name"] == name)


def test_contract_quality_never_calls_missing_snapshot_evidence_a_pass(tmp_path) -> None:
    report = build_contract_quality_report(PlatformSettings.from_root(tmp_path))

    assert report["overall_status"] == "incomplete"
    assert _check(report, "raw_source_licenses")["status"] == "pass"
    assert _check(report, "preflight_content_readability")["status"] == "not_recorded"
    assert _check(report, "explicit_source_snapshots")["status"] == "baseline_required"


def test_contract_quality_accepts_content_evidence_but_keeps_snapshot_baseline_honest(
    tmp_path,
) -> None:
    report = build_contract_quality_report(
        PlatformSettings.from_root(tmp_path), preflight_evidence=_evidence()
    )

    preflight = _check(report, "preflight_content_readability")
    assert preflight["status"] == "pass"
    assert preflight["passing_artifact_count"] == 1
    assert report["overall_status"] == "incomplete"


def test_contract_quality_fails_a_recorded_unreadable_artifact(tmp_path) -> None:
    report = build_contract_quality_report(
        PlatformSettings.from_root(tmp_path), preflight_evidence=_evidence(ok=False)
    )

    assert report["overall_status"] == "fail"
    assert report["failed_checks"] == ["preflight_content_readability"]


def test_contract_quality_rejects_unsafe_evidence_paths(tmp_path) -> None:
    evidence = _evidence()
    evidence["artifacts"][0]["artifact_path"] = "../outside.parquet"

    with pytest.raises(ValueError, match="evidence_artifact_path_invalid"):
        build_contract_quality_report(
            PlatformSettings.from_root(tmp_path), preflight_evidence=evidence
        )


def test_contract_quality_reports_explicit_snapshot_observation_without_threshold(tmp_path) -> None:
    ledger = tmp_path / "snapshots.jsonl"
    ledger.write_text(
        '{"record_type":"scoutfootball.source_snapshot_ledger","snapshot_id":"id","source_id":"football_data","snapshot_date":"2026-07-16","recorded_at":"2026-07-17T00:00:00Z","evidence":{"artifact_count":1}}\n',
        encoding="utf-8",
    )

    report = build_contract_quality_report(
        PlatformSettings.from_root(tmp_path), snapshot_ledger_path=str(ledger)
    )

    snapshots = _check(report, "explicit_source_snapshots")
    assert snapshots["status"] == "observed"
    assert snapshots["explicit_snapshot_sources"] == ["football_data"]
