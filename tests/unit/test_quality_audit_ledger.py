"""Tests for explicit local quality-audit denominators and corrections."""

from __future__ import annotations

import json

import pytest

from scoutfootball.evaluation.quality_audit_ledger import (
    append_quality_audit_record,
    append_quality_threshold_record,
    build_quality_audit_record,
    build_quality_threshold_record,
    effective_quality_audits,
    latest_threshold_by_kind,
    read_quality_audit_ledger,
    read_quality_threshold_ledger,
    summarize_quality_audits,
)


def _record(
    *,
    audit_kind: str = "identity_resolution",
    sample_id: str = "tm-review-001",
    outcome: str = "confirmed_correct",
    supersedes_audit_id: str | None = None,
    recorded_at: str = "2026-07-17T00:00:00Z",
):
    return build_quality_audit_record(
        audit_kind=audit_kind,
        source_id="transfermarkt_manual",
        sample_id=sample_id,
        outcome=outcome,
        reviewer="maintainer",
        evidence_reference="local-review:tm-review-001",
        decision="Reviewed against the permitted local source snapshot.",
        supersedes_audit_id=supersedes_audit_id,
        recorded_at=recorded_at,
    )


def test_quality_audit_ledger_records_reviewed_denominator_and_error_rate(tmp_path) -> None:
    ledger = tmp_path / "quality_audits.jsonl"
    identity = _record()
    claim = _record(
        audit_kind="source_claim",
        sample_id="claim-001",
        outcome="confirmed_error",
        recorded_at="2026-07-17T00:01:00Z",
    )

    append_quality_audit_record(identity, ledger)
    append_quality_audit_record(claim, ledger)

    records = read_quality_audit_ledger(ledger)
    summary = summarize_quality_audits(records)
    assert records == [identity, claim]
    assert summary["identity_resolution"]["record_count"] == 1
    assert summary["identity_resolution"]["error_rate"] == 0.0
    assert summary["source_claim"]["confirmed_error_count"] == 1
    assert summary["source_claim"]["error_rate"] == 1.0
    with pytest.raises(FileExistsError, match="quality_audit_already_recorded"):
        append_quality_audit_record(identity, ledger)


def test_quality_audit_ledger_requires_explicit_scope_outcome_and_evidence() -> None:
    with pytest.raises(ValueError, match="audit_kind_invalid"):
        _record(audit_kind="invented")
    with pytest.raises(ValueError, match="source_not_registered"):
        build_quality_audit_record(
            audit_kind="identity_resolution",
            source_id="unregistered",
            sample_id="sample",
            outcome="confirmed_correct",
            reviewer="maintainer",
            evidence_reference="local:sample",
            decision="Reviewed manually.",
        )
    with pytest.raises(ValueError, match="evidence_reference_required"):
        build_quality_audit_record(
            audit_kind="identity_resolution",
            source_id="transfermarkt_manual",
            sample_id="sample",
            outcome="confirmed_correct",
            reviewer="maintainer",
            evidence_reference="",
            decision="Reviewed manually.",
        )


def test_quality_audit_correction_replaces_only_its_matching_prior_sample(tmp_path) -> None:
    ledger = tmp_path / "quality_audits.jsonl"
    original = _record(outcome="confirmed_error")
    append_quality_audit_record(original, ledger)
    correction = _record(
        outcome="confirmed_correct",
        supersedes_audit_id=original["audit_id"],
        recorded_at="2026-07-17T00:02:00Z",
    )

    append_quality_audit_record(correction, ledger)

    effective = effective_quality_audits(read_quality_audit_ledger(ledger))
    summary = summarize_quality_audits(read_quality_audit_ledger(ledger))
    assert effective == [correction]
    assert summary["identity_resolution"]["confirmed_error_count"] == 0
    assert summary["identity_resolution"]["correction_count"] == 1
    wrong_scope = _record(
        sample_id="another-sample",
        supersedes_audit_id=original["audit_id"],
        recorded_at="2026-07-17T00:03:00Z",
    )
    with pytest.raises(ValueError, match="quality_audit_superseded_record_already_replaced"):
        append_quality_audit_record(wrong_scope, ledger)


def test_quality_audit_ledger_rejects_tampered_identifier(tmp_path) -> None:
    ledger = tmp_path / "quality_audits.jsonl"
    record = _record()
    record["decision"] = "Different decision."
    ledger.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="quality_audit_ledger_audit_id_mismatch:1"):
        read_quality_audit_ledger(ledger)


def test_quality_threshold_ledger_requires_explicit_rate_and_minimum_sample_count(tmp_path) -> None:
    ledger = tmp_path / "quality_thresholds.jsonl"
    threshold = build_quality_threshold_record(
        audit_kind="identity_resolution",
        maximum_error_rate=0.05,
        minimum_sample_count=40,
        decision="Require a reviewed sample before relying on this local rate.",
        recorded_at="2026-07-17T00:00:00Z",
    )

    append_quality_threshold_record(threshold, ledger)

    assert read_quality_threshold_ledger(ledger) == [threshold]
    assert latest_threshold_by_kind([threshold])["identity_resolution"] == threshold
    with pytest.raises(FileExistsError, match="quality_threshold_already_recorded"):
        append_quality_threshold_record(threshold, ledger)
    with pytest.raises(ValueError, match="maximum_error_rate_invalid"):
        build_quality_threshold_record(
            audit_kind="identity_resolution",
            maximum_error_rate=1.1,
            minimum_sample_count=1,
            decision="Invalid fixture.",
        )
    with pytest.raises(ValueError, match="minimum_sample_count_invalid"):
        build_quality_threshold_record(
            audit_kind="source_claim",
            maximum_error_rate=0.1,
            minimum_sample_count=0,
            decision="Invalid fixture.",
        )
