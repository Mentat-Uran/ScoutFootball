"""Append-only, local records for explicitly declared source snapshots."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from scoutfootball.architecture import build_data_contract_registry

SNAPSHOT_LEDGER_TYPE = "scoutfootball.source_snapshot_ledger"
SNAPSHOT_LEDGER_VERSION = "1.0"
PREFLIGHT_EVIDENCE_TYPE = "scoutfootball.parquet_preflight_evidence"


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _raw_source_roots() -> dict[str, str]:
    roots: dict[str, str] = {}
    for contract in build_data_contract_registry().contracts:
        if contract.layer != "raw" or contract.license is None:
            continue
        roots[contract.license.source_name] = contract.artifact_id.replace("\\", "/").strip("/")
    return roots


def _read_evidence(path: Path | str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).resolve().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"evidence_unreadable: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("report_type") != PREFLIGHT_EVIDENCE_TYPE:
        raise ValueError("evidence_report_type_invalid")
    if not isinstance(payload.get("artifacts"), list):
        raise ValueError("evidence_artifacts_invalid")
    return payload


def _normalize_relative_path(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("evidence_artifact_path_invalid")
    normalized = value.replace("\\", "/").strip("/")
    windows_absolute = len(normalized) >= 2 and normalized[1] == ":"
    if not normalized or value.startswith(("/", "\\")) or windows_absolute:
        raise ValueError("evidence_artifact_path_invalid")
    if ".." in normalized.split("/"):
        raise ValueError("evidence_artifact_path_invalid")
    return normalized


def _snapshot_id(source_id: str, snapshot_date: str, artifacts: list[dict[str, Any]]) -> str:
    fingerprint = json.dumps(
        {"source_id": source_id, "snapshot_date": snapshot_date, "artifacts": artifacts},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"{source_id}:{snapshot_date}:{hashlib.sha256(fingerprint).hexdigest()[:16]}"


def build_source_snapshot_record(
    *,
    source_id: str,
    snapshot_date: str,
    evidence_path: Path | str,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Build one explicit source-snapshot record from a local evidence report."""
    try:
        as_of = date.fromisoformat(snapshot_date)
    except (TypeError, ValueError) as exc:
        raise ValueError("snapshot_date_invalid") from exc

    roots = _raw_source_roots()
    source_root = roots.get(source_id)
    if source_root is None:
        raise ValueError("source_not_registered")
    evidence = _read_evidence(evidence_path)
    artifacts: list[dict[str, Any]] = []
    for artifact in evidence["artifacts"]:
        if not isinstance(artifact, dict) or not isinstance(artifact.get("inspection"), dict):
            raise ValueError("evidence_artifact_invalid")
        artifact_path = _normalize_relative_path(artifact.get("artifact_path"))
        if artifact_path != source_root and not artifact_path.startswith(f"{source_root}/"):
            continue
        inspection = artifact["inspection"]
        artifacts.append(
            {
                "artifact_path": artifact_path,
                "content_hash": inspection.get("content_hash"),
                "schema_hash": inspection.get("schema_hash"),
                "row_count": inspection.get("row_count"),
                "reader": inspection.get("reader"),
            }
        )
    if not artifacts:
        raise ValueError("evidence_has_no_artifacts_for_source")

    artifacts.sort(key=lambda item: item["artifact_path"])
    normalized_date = as_of.isoformat()
    return {
        "record_type": SNAPSHOT_LEDGER_TYPE,
        "record_version": SNAPSHOT_LEDGER_VERSION,
        "snapshot_id": _snapshot_id(source_id, normalized_date, artifacts),
        "source_id": source_id,
        "snapshot_date": normalized_date,
        "recorded_at": recorded_at or _now_iso(),
        "evidence": {
            "report_type": evidence["report_type"],
            "report_version": evidence.get("report_version"),
            "generated_at": evidence.get("generated_at"),
            "artifact_count": len(artifacts),
        },
        "artifacts": artifacts,
        "limitations": [
            (
                "snapshot_date is explicitly supplied by the local maintainer; "
                "it is not inferred from file metadata."
            ),
            (
                "This record proves only the listed local inspection inputs, "
                "not upstream freshness beyond the declared date."
            ),
        ],
    }


def read_source_snapshot_ledger(path: Path | str) -> list[dict[str, Any]]:
    """Read a ledger strictly; malformed history is never silently skipped."""
    ledger = Path(path).resolve()
    if not ledger.exists():
        return []
    records = []
    for number, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"ledger_blank_line:{number}")
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"ledger_invalid_json:{number}") from exc
        if not isinstance(record, dict) or record.get("record_type") != SNAPSHOT_LEDGER_TYPE:
            raise ValueError(f"ledger_record_type_invalid:{number}")
        if (
            not isinstance(record.get("source_id"), str)
            or not isinstance(record.get("snapshot_id"), str)
            or not isinstance(record.get("snapshot_date"), str)
            or not isinstance(record.get("recorded_at"), str)
            or not isinstance(record.get("evidence"), dict)
        ):
            raise ValueError(f"ledger_record_invalid:{number}")
        try:
            date.fromisoformat(record["snapshot_date"])
        except ValueError as exc:
            raise ValueError(f"ledger_snapshot_date_invalid:{number}") from exc
        records.append(record)
    return records


def append_source_snapshot_record(record: dict[str, Any], path: Path | str) -> Path:
    """Append one record durably, refusing a duplicate immutable snapshot ID."""
    ledger = Path(path).resolve()
    existing = read_source_snapshot_ledger(ledger)
    if any(item["snapshot_id"] == record["snapshot_id"] for item in existing):
        raise FileExistsError(f"snapshot_already_recorded: {record['snapshot_id']}")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
    with ledger.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    return ledger


def latest_snapshot_by_source(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Choose the latest recorded entry per source without altering ledger history."""
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        source_id = record["source_id"]
        if source_id not in latest or record.get("recorded_at", "") > latest[source_id].get(
            "recorded_at", ""
        ):
            latest[source_id] = record
    return latest
