"""Append-only local declarations for source retention and deletion policy.

These records capture a maintainer decision; they never infer a retention
period or deletion procedure from a third-party licence name or local files.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scoutfootball.architecture import build_data_contract_registry

POLICY_LEDGER_TYPE = "scoutfootball.source_policy_ledger"
POLICY_LEDGER_VERSION = "1.0"
RETENTION_MODES = frozenset({"days", "until_manual_deletion", "until_rights_change"})


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _registered_raw_source_ids() -> set[str]:
    return {
        contract.license.source_name
        for contract in build_data_contract_registry().contracts
        if contract.layer == "raw" and contract.license is not None
    }


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name}_required")
    return value.strip()


def _validated_recorded_at(value: object) -> str:
    timestamp = _required_text(value, "recorded_at")
    try:
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("recorded_at_invalid") from exc
    return timestamp


def _policy_id(record: dict[str, Any]) -> str:
    fingerprint = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{record['source_id']}:{hashlib.sha256(fingerprint).hexdigest()[:16]}"


def build_source_policy_record(
    *,
    source_id: str,
    retention_mode: str,
    retention_days: int | None,
    deletion_trigger: str,
    deletion_strategy: str,
    derived_artifact_action: str,
    decision: str,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Build one explicit, local source-policy declaration.

    ``retention_mode`` deliberately supports both a bounded number of days and
    explicit local manual retention.  The latter is not silently treated as a
    numeric retention period.
    """
    if source_id not in _registered_raw_source_ids():
        raise ValueError("source_not_registered")
    if retention_mode not in RETENTION_MODES:
        raise ValueError("retention_mode_invalid")
    if retention_mode == "days":
        if retention_days is None or retention_days < 1:
            raise ValueError("retention_days_invalid")
    elif retention_days is not None:
        raise ValueError("retention_days_not_applicable")

    policy = {
        "source_id": source_id,
        "retention": {
            "mode": retention_mode,
            "days": retention_days,
        },
        "deletion": {
            "trigger": _required_text(deletion_trigger, "deletion_trigger"),
            "strategy": _required_text(deletion_strategy, "deletion_strategy"),
            "derived_artifact_action": _required_text(
                derived_artifact_action, "derived_artifact_action"
            ),
        },
        "decision": _required_text(decision, "decision"),
    }
    return {
        "record_type": POLICY_LEDGER_TYPE,
        "record_version": POLICY_LEDGER_VERSION,
        "policy_id": _policy_id(policy),
        **policy,
        "recorded_at": _validated_recorded_at(recorded_at or _now_iso()),
        "limitations": [
            (
                "This is a maintainer-recorded local policy, not an interpretation "
                "of third-party terms."
            ),
            "Recording a policy does not delete source files or derived artifacts.",
        ],
    }


def _validate_policy_record(record: object, line_number: int) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("record_type") != POLICY_LEDGER_TYPE:
        raise ValueError(f"policy_ledger_record_type_invalid:{line_number}")
    if record.get("record_version") != POLICY_LEDGER_VERSION:
        raise ValueError(f"policy_ledger_record_version_invalid:{line_number}")
    source_id = record.get("source_id")
    if not isinstance(source_id, str) or source_id not in _registered_raw_source_ids():
        raise ValueError(f"policy_ledger_source_invalid:{line_number}")
    if not isinstance(record.get("policy_id"), str) or not record["policy_id"]:
        raise ValueError(f"policy_ledger_policy_id_invalid:{line_number}")
    retention = record.get("retention")
    deletion = record.get("deletion")
    if not isinstance(retention, dict) or not isinstance(deletion, dict):
        raise ValueError(f"policy_ledger_record_invalid:{line_number}")
    mode = retention.get("mode")
    days = retention.get("days")
    if mode not in RETENTION_MODES:
        raise ValueError(f"policy_ledger_retention_mode_invalid:{line_number}")
    if mode == "days":
        if not isinstance(days, int) or isinstance(days, bool) or days < 1:
            raise ValueError(f"policy_ledger_retention_days_invalid:{line_number}")
    elif days is not None:
        raise ValueError(f"policy_ledger_retention_days_invalid:{line_number}")
    try:
        _required_text(deletion.get("trigger"), "deletion_trigger")
        _required_text(deletion.get("strategy"), "deletion_strategy")
        _required_text(deletion.get("derived_artifact_action"), "derived_artifact_action")
        _required_text(record.get("decision"), "decision")
    except ValueError as exc:
        raise ValueError(f"policy_ledger_record_invalid:{line_number}") from exc
    try:
        _validated_recorded_at(record.get("recorded_at"))
    except ValueError as exc:
        raise ValueError(f"policy_ledger_recorded_at_invalid:{line_number}") from exc
    expected_policy = {
        "source_id": source_id,
        "retention": {"mode": mode, "days": days},
        "deletion": {
            "trigger": deletion["trigger"].strip(),
            "strategy": deletion["strategy"].strip(),
            "derived_artifact_action": deletion["derived_artifact_action"].strip(),
        },
        "decision": record["decision"].strip(),
    }
    if record["policy_id"] != _policy_id(expected_policy):
        raise ValueError(f"policy_ledger_policy_id_mismatch:{line_number}")
    return record


def read_source_policy_ledger(path: Path | str) -> list[dict[str, Any]]:
    """Read policy history strictly; malformed records are never ignored."""
    ledger = Path(path).resolve()
    if not ledger.exists():
        return []
    records: list[dict[str, Any]] = []
    for number, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"policy_ledger_blank_line:{number}")
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"policy_ledger_invalid_json:{number}") from exc
        records.append(_validate_policy_record(record, number))
    return records


def append_source_policy_record(record: dict[str, Any], path: Path | str) -> Path:
    """Durably append an immutable policy declaration without duplicate IDs."""
    _validate_policy_record(record, 0)
    ledger = Path(path).resolve()
    existing = read_source_policy_ledger(ledger)
    if any(item["policy_id"] == record["policy_id"] for item in existing):
        raise FileExistsError(f"policy_already_recorded: {record['policy_id']}")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
    with ledger.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    return ledger


def latest_policy_by_source(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Select the latest declaration per source without mutating policy history."""
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        source_id = record["source_id"]
        if source_id not in latest or record["recorded_at"] > latest[source_id]["recorded_at"]:
            latest[source_id] = record
    return latest
