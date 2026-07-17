"""Tests for truthful contract-quality baseline reporting."""

from __future__ import annotations

import pytest

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.contract_quality import build_contract_quality_report
from scoutfootball.evaluation.quality_audit_ledger import (
    append_quality_audit_record,
    append_quality_threshold_record,
    build_quality_audit_record,
    build_quality_threshold_record,
)
from scoutfootball.evaluation.source_policy_ledger import (
    append_source_policy_record,
    build_source_policy_record,
)


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
    policy = _check(report, "source_retention_and_deletion_policies")
    assert policy["status"] == "baseline_required"
    assert policy["sources_with_complete_policy"] == 0
    assert policy["sources_missing_policy"]
    assert _check(report, "preflight_content_readability")["status"] == "not_recorded"
    assert _check(report, "explicit_source_snapshots")["status"] == "baseline_required"


def test_contract_quality_fails_with_an_unregistered_active_raw_directory(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    (settings.raw_root / "legacy_unregistered_source").mkdir(parents=True)

    report = build_contract_quality_report(settings)
    raw_directories = _check(report, "unregistered_raw_directories")

    assert raw_directories["status"] == "fail"
    assert raw_directories["unregistered_raw_directories"] == ["legacy_unregistered_source"]
    assert raw_directories["unregistered_raw_directory_details"][0]["file_count"] == 0
    assert "unregistered_raw_directories" in report["failed_checks"]


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


def test_contract_quality_accepts_only_the_sources_declared_in_a_policy_ledger(tmp_path) -> None:
    ledger = tmp_path / "source_policies.jsonl"
    record = build_source_policy_record(
        source_id="football_data",
        retention_mode="days",
        retention_days=30,
        deletion_trigger="A recorded deletion request or rights change.",
        deletion_strategy="Remove raw files only after explicit confirmation.",
        derived_artifact_action="Invalidate dependent artifacts for regeneration.",
        decision="Fixture policy declaration.",
        recorded_at="2026-07-17T00:00:00Z",
    )
    append_source_policy_record(record, ledger)

    report = build_contract_quality_report(
        PlatformSettings.from_root(tmp_path), policy_ledger_path=str(ledger)
    )
    policy = _check(report, "source_retention_and_deletion_policies")

    assert report["scope"]["policy_ledger_supplied"] is True
    assert policy["status"] == "baseline_required"
    assert policy["sources_with_complete_policy"] == 1
    assert {item["source_id"] for item in policy["sources_missing_policy"]} == {
        "clubelo",
        "fbref",
        "statsbomb_open",
        "transfermarkt_manual",
        "understat",
    }


def test_contract_quality_exposes_audited_error_rates_without_calling_them_a_pass(tmp_path) -> None:
    ledger = tmp_path / "quality_audits.jsonl"
    identity = build_quality_audit_record(
        audit_kind="identity_resolution",
        source_id="transfermarkt_manual",
        sample_id="identity-001",
        outcome="confirmed_correct",
        reviewer="maintainer",
        evidence_reference="local-review:identity-001",
        decision="Reviewed against the local permitted snapshot.",
        recorded_at="2026-07-17T00:00:00Z",
    )
    claim = build_quality_audit_record(
        audit_kind="source_claim",
        source_id="football_data",
        sample_id="claim-001",
        outcome="confirmed_error",
        reviewer="maintainer",
        evidence_reference="local-review:claim-001",
        decision="Reviewed an external factual claim against the local input.",
        recorded_at="2026-07-17T00:01:00Z",
    )
    append_quality_audit_record(identity, ledger)
    append_quality_audit_record(claim, ledger)

    report = build_contract_quality_report(
        PlatformSettings.from_root(tmp_path), audit_ledger_path=str(ledger)
    )
    identity_rate = _check(report, "identity_conflict_error_rate")
    claim_rate = _check(report, "source_claim_error_rate")

    assert report["scope"]["audit_ledger_supplied"] is True
    assert identity_rate["status"] == "baseline_required"
    assert identity_rate["audit_status"] == "observed"
    assert identity_rate["audited_sample_count"] == 1
    assert identity_rate["observed_error_rate"] == 0.0
    assert claim_rate["audit_status"] == "observed"
    assert claim_rate["confirmed_error_count"] == 1
    assert claim_rate["observed_error_rate"] == 1.0
    assert report["overall_status"] == "incomplete"


def test_contract_quality_applies_only_an_explicit_threshold_with_enough_samples(tmp_path) -> None:
    audit_ledger = tmp_path / "quality_audits.jsonl"
    threshold_ledger = tmp_path / "quality_thresholds.jsonl"
    audit = build_quality_audit_record(
        audit_kind="identity_resolution",
        source_id="transfermarkt_manual",
        sample_id="identity-001",
        outcome="confirmed_correct",
        reviewer="maintainer",
        evidence_reference="local-review:identity-001",
        decision="Reviewed against the local permitted snapshot.",
        recorded_at="2026-07-17T00:00:00Z",
    )
    threshold = build_quality_threshold_record(
        audit_kind="identity_resolution",
        maximum_error_rate=0.0,
        minimum_sample_count=1,
        decision="One reviewed fixture is sufficient only for this test scope.",
        recorded_at="2026-07-17T00:01:00Z",
    )
    append_quality_audit_record(audit, audit_ledger)
    append_quality_threshold_record(threshold, threshold_ledger)

    report = build_contract_quality_report(
        PlatformSettings.from_root(tmp_path),
        audit_ledger_path=str(audit_ledger),
        threshold_ledger_path=str(threshold_ledger),
    )
    identity_rate = _check(report, "identity_conflict_error_rate")
    source_claim_rate = _check(report, "source_claim_error_rate")

    assert report["scope"]["threshold_ledger_supplied"] is True
    assert identity_rate["status"] == "pass"
    assert identity_rate["threshold_status"] == "met"
    assert identity_rate["threshold"]["threshold_id"] == threshold["threshold_id"]
    assert source_claim_rate["status"] == "baseline_required"
    assert source_claim_rate["threshold_status"] == "not_recorded"


def test_contract_quality_fails_when_a_recorded_threshold_is_exceeded(tmp_path) -> None:
    audit_ledger = tmp_path / "quality_audits.jsonl"
    threshold_ledger = tmp_path / "quality_thresholds.jsonl"
    audit = build_quality_audit_record(
        audit_kind="source_claim",
        source_id="football_data",
        sample_id="claim-001",
        outcome="confirmed_error",
        reviewer="maintainer",
        evidence_reference="local-review:claim-001",
        decision="Reviewed against the local permitted input.",
        recorded_at="2026-07-17T00:00:00Z",
    )
    threshold = build_quality_threshold_record(
        audit_kind="source_claim",
        maximum_error_rate=0.0,
        minimum_sample_count=1,
        decision="Reject any confirmed source claim error in this test scope.",
        recorded_at="2026-07-17T00:01:00Z",
    )
    append_quality_audit_record(audit, audit_ledger)
    append_quality_threshold_record(threshold, threshold_ledger)

    report = build_contract_quality_report(
        PlatformSettings.from_root(tmp_path),
        audit_ledger_path=str(audit_ledger),
        threshold_ledger_path=str(threshold_ledger),
    )
    claim_rate = _check(report, "source_claim_error_rate")

    assert claim_rate["status"] == "fail"
    assert claim_rate["threshold_status"] == "not_met"
    assert report["failed_checks"] == ["source_claim_error_rate"]
