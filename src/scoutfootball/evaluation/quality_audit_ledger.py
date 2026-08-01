"""Append-only local records for human-reviewed C1 quality samples.

The ledger is deliberately narrow: it stores the maintainer's review of one
identity-resolution or external-source claim sample.  It does not fetch data,
infer an audit outcome, or turn an observed error rate into a release target.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scoutfootball.architecture import build_data_contract_registry

QUALITY_AUDIT_LEDGER_TYPE = "scoutfootball.quality_audit_ledger"
QUALITY_AUDIT_LEDGER_VERSION = "1.0"
QUALITY_THRESHOLD_LEDGER_TYPE = "scoutfootball.quality_threshold_ledger"
QUALITY_THRESHOLD_LEDGER_VERSION = "1.0"
AUDIT_KINDS = frozenset({"identity_resolution", "source_claim"})
AUDIT_OUTCOMES = frozenset({"confirmed_correct", "confirmed_error"})


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


def _audit_id(record: dict[str, Any]) -> str:
    fingerprint = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{record['audit_kind']}:{hashlib.sha256(fingerprint).hexdigest()[:16]}"


def build_quality_audit_record(
    *,
    audit_kind: str,
    source_id: str,
    sample_id: str,
    outcome: str,
    reviewer: str,
    evidence_reference: str,
    decision: str,
    supersedes_audit_id: str | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Build one maintainer-reviewed quality audit record.

    ``sample_id`` and ``evidence_reference`` are opaque local references.  The
    ledger intentionally avoids embedding third-party source content or user
    data, while preserving enough information for a maintainer to find the
    reviewed sample again.
    """
    if audit_kind not in AUDIT_KINDS:
        raise ValueError("audit_kind_invalid")
    if source_id not in _registered_raw_source_ids():
        raise ValueError("source_not_registered")
    if outcome not in AUDIT_OUTCOMES:
        raise ValueError("audit_outcome_invalid")
    supersedes = None
    if supersedes_audit_id is not None:
        supersedes = _required_text(supersedes_audit_id, "supersedes_audit_id")
    audit = {
        "audit_kind": audit_kind,
        "source_id": source_id,
        "sample_id": _required_text(sample_id, "sample_id"),
        "outcome": outcome,
        "reviewer": _required_text(reviewer, "reviewer"),
        "evidence_reference": _required_text(evidence_reference, "evidence_reference"),
        "decision": _required_text(decision, "decision"),
        "supersedes_audit_id": supersedes,
    }
    return {
        "record_type": QUALITY_AUDIT_LEDGER_TYPE,
        "record_version": QUALITY_AUDIT_LEDGER_VERSION,
        "audit_id": _audit_id(audit),
        **audit,
        "recorded_at": _validated_recorded_at(recorded_at or _now_iso()),
        "limitations": [
            "This is a maintainer-recorded local review, not a generated audit outcome.",
            "Observed error rates do not define an acceptable threshold or release decision.",
        ],
    }


def _validate_quality_audit_record(record: object, line_number: int) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("record_type") != QUALITY_AUDIT_LEDGER_TYPE:
        raise ValueError(f"quality_audit_ledger_record_type_invalid:{line_number}")
    if record.get("record_version") != QUALITY_AUDIT_LEDGER_VERSION:
        raise ValueError(f"quality_audit_ledger_record_version_invalid:{line_number}")
    if not isinstance(record.get("audit_id"), str) or not record["audit_id"]:
        raise ValueError(f"quality_audit_ledger_audit_id_invalid:{line_number}")
    try:
        expected = build_quality_audit_record(
            audit_kind=record.get("audit_kind"),
            source_id=record.get("source_id"),
            sample_id=record.get("sample_id"),
            outcome=record.get("outcome"),
            reviewer=record.get("reviewer"),
            evidence_reference=record.get("evidence_reference"),
            decision=record.get("decision"),
            supersedes_audit_id=record.get("supersedes_audit_id"),
            recorded_at=record.get("recorded_at"),
        )
    except ValueError as exc:
        raise ValueError(f"quality_audit_ledger_record_invalid:{line_number}") from exc
    if record["audit_id"] != expected["audit_id"]:
        raise ValueError(f"quality_audit_ledger_audit_id_mismatch:{line_number}")
    return record


def read_quality_audit_ledger(path: Path | str) -> list[dict[str, Any]]:
    """Read audit history strictly; malformed rows are never ignored."""
    ledger = Path(path).resolve()
    if not ledger.exists():
        return []
    records: list[dict[str, Any]] = []
    for number, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"quality_audit_ledger_blank_line:{number}")
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"quality_audit_ledger_invalid_json:{number}") from exc
        records.append(_validate_quality_audit_record(record, number))
    return records


def append_quality_audit_record(record: dict[str, Any], path: Path | str) -> Path:
    """Durably append a reviewed sample and validate an optional correction link."""
    _validate_quality_audit_record(record, 0)
    ledger = Path(path).resolve()
    existing = read_quality_audit_ledger(ledger)
    if any(item["audit_id"] == record["audit_id"] for item in existing):
        raise FileExistsError(f"quality_audit_already_recorded: {record['audit_id']}")
    if record["supersedes_audit_id"]:
        predecessor = next(
            (item for item in existing if item["audit_id"] == record["supersedes_audit_id"]),
            None,
        )
        if predecessor is None:
            raise ValueError("quality_audit_superseded_record_missing")
        if any(item.get("supersedes_audit_id") == predecessor["audit_id"] for item in existing):
            raise ValueError("quality_audit_superseded_record_already_replaced")
        for key in ("audit_kind", "source_id", "sample_id"):
            if record[key] != predecessor[key]:
                raise ValueError("quality_audit_superseded_record_scope_mismatch")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
    with ledger.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    return ledger


def effective_quality_audits(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return current records after explicit append-only corrections are applied."""
    superseded = {
        record["supersedes_audit_id"] for record in records if record["supersedes_audit_id"]
    }
    return [record for record in records if record["audit_id"] not in superseded]


def summarize_quality_audits(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Summarize reviewed denominators without inventing an acceptable error rate."""
    effective = effective_quality_audits(records)
    summary: dict[str, dict[str, Any]] = {}
    for audit_kind in sorted(AUDIT_KINDS):
        items = [record for record in effective if record["audit_kind"] == audit_kind]
        errors = sum(record["outcome"] == "confirmed_error" for record in items)
        correct = len(items) - errors
        summary[audit_kind] = {
            "record_count": len(items),
            "confirmed_correct_count": correct,
            "confirmed_error_count": errors,
            "error_rate": errors / len(items) if items else None,
            "audited_sources": sorted({record["source_id"] for record in items}),
            "correction_count": sum(record["supersedes_audit_id"] is not None for record in items),
        }
    return summary


def _threshold_id(record: dict[str, Any]) -> str:
    fingerprint = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{record['audit_kind']}:{hashlib.sha256(fingerprint).hexdigest()[:16]}"


def _validated_error_rate(value: object) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 1:
        raise ValueError("maximum_error_rate_invalid")
    return float(value)


def _validated_minimum_sample_count(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError("minimum_sample_count_invalid")
    return value


def build_quality_threshold_record(
    *,
    audit_kind: str,
    maximum_error_rate: float,
    minimum_sample_count: int,
    decision: str,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Build a maintainer-selected quality threshold for one audit dimension."""
    if audit_kind not in AUDIT_KINDS:
        raise ValueError("audit_kind_invalid")
    threshold = {
        "audit_kind": audit_kind,
        "maximum_error_rate": _validated_error_rate(maximum_error_rate),
        "minimum_sample_count": _validated_minimum_sample_count(minimum_sample_count),
        "decision": _required_text(decision, "decision"),
    }
    return {
        "record_type": QUALITY_THRESHOLD_LEDGER_TYPE,
        "record_version": QUALITY_THRESHOLD_LEDGER_VERSION,
        "threshold_id": _threshold_id(threshold),
        **threshold,
        "recorded_at": _validated_recorded_at(recorded_at or _now_iso()),
        "limitations": [
            "This is a maintainer-selected local acceptance threshold.",
            "It does not make unreviewed samples correct or replace source-level review.",
        ],
    }


def _validate_quality_threshold_record(record: object, line_number: int) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("record_type") != QUALITY_THRESHOLD_LEDGER_TYPE:
        raise ValueError(f"quality_threshold_ledger_record_type_invalid:{line_number}")
    if record.get("record_version") != QUALITY_THRESHOLD_LEDGER_VERSION:
        raise ValueError(f"quality_threshold_ledger_record_version_invalid:{line_number}")
    if not isinstance(record.get("threshold_id"), str) or not record["threshold_id"]:
        raise ValueError(f"quality_threshold_ledger_threshold_id_invalid:{line_number}")
    try:
        expected = build_quality_threshold_record(
            audit_kind=record.get("audit_kind"),
            maximum_error_rate=record.get("maximum_error_rate"),
            minimum_sample_count=record.get("minimum_sample_count"),
            decision=record.get("decision"),
            recorded_at=record.get("recorded_at"),
        )
    except ValueError as exc:
        raise ValueError(f"quality_threshold_ledger_record_invalid:{line_number}") from exc
    if record["threshold_id"] != expected["threshold_id"]:
        raise ValueError(f"quality_threshold_ledger_threshold_id_mismatch:{line_number}")
    return record


def read_quality_threshold_ledger(path: Path | str) -> list[dict[str, Any]]:
    """Read threshold history strictly; malformed rows are never ignored."""
    ledger = Path(path).resolve()
    if not ledger.exists():
        return []
    records: list[dict[str, Any]] = []
    for number, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"quality_threshold_ledger_blank_line:{number}")
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"quality_threshold_ledger_invalid_json:{number}") from exc
        records.append(_validate_quality_threshold_record(record, number))
    return records


def append_quality_threshold_record(record: dict[str, Any], path: Path | str) -> Path:
    """Durably append an immutable, maintainer-selected threshold declaration."""
    _validate_quality_threshold_record(record, 0)
    ledger = Path(path).resolve()
    existing = read_quality_threshold_ledger(ledger)
    if any(item["threshold_id"] == record["threshold_id"] for item in existing):
        raise FileExistsError(f"quality_threshold_already_recorded: {record['threshold_id']}")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
    with ledger.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    return ledger


def latest_threshold_by_kind(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Select the latest declared threshold per audit dimension without rewriting history."""
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        audit_kind = record["audit_kind"]
        if audit_kind not in latest or record["recorded_at"] > latest[audit_kind]["recorded_at"]:
            latest[audit_kind] = record
    return latest
