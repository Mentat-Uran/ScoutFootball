"""Tests for explicit, append-only local source policy declarations."""

from __future__ import annotations

import json

import pytest

from scoutfootball.evaluation.source_policy_ledger import (
    append_source_policy_record,
    build_source_policy_record,
    latest_policy_by_source,
    read_source_policy_ledger,
)


def _record(*, recorded_at: str = "2026-07-17T00:00:00Z", **overrides):
    payload = {
        "source_id": "football_data",
        "retention_mode": "until_manual_deletion",
        "retention_days": None,
        "deletion_trigger": "Maintainer requests removal or source terms change.",
        "deletion_strategy": "Remove local raw snapshots after an explicit confirmation.",
        "derived_artifact_action": "Mark dependent local artifacts invalid for regeneration.",
        "decision": "Personal local use policy recorded after rights review.",
        "recorded_at": recorded_at,
    }
    payload.update(overrides)
    return build_source_policy_record(**payload)


def test_policy_ledger_records_explicit_non_numeric_local_retention(tmp_path) -> None:
    ledger = tmp_path / "source_policies.jsonl"
    record = _record()

    append_source_policy_record(record, ledger)

    assert read_source_policy_ledger(ledger) == [record]
    assert record["retention"] == {"mode": "until_manual_deletion", "days": None}
    assert latest_policy_by_source([record])["football_data"]["policy_id"] == record["policy_id"]
    with pytest.raises(FileExistsError, match="policy_already_recorded"):
        append_source_policy_record(record, ledger)


def test_policy_ledger_requires_registered_source_complete_deletion_and_valid_retention() -> None:
    with pytest.raises(ValueError, match="source_not_registered"):
        _record(source_id="not_a_source")
    with pytest.raises(ValueError, match="retention_days_invalid"):
        _record(retention_mode="days", retention_days=0)
    with pytest.raises(ValueError, match="retention_days_not_applicable"):
        _record(retention_days=90)
    with pytest.raises(ValueError, match="derived_artifact_action_required"):
        _record(derived_artifact_action="")
    with pytest.raises(ValueError, match="recorded_at_invalid"):
        _record(recorded_at="not-a-timestamp")


def test_policy_ledger_rejects_tampered_policy_ids(tmp_path) -> None:
    ledger = tmp_path / "source_policies.jsonl"
    record = _record()
    record["decision"] = "A different policy decision."
    ledger.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="policy_ledger_policy_id_mismatch:1"):
        read_source_policy_ledger(ledger)
