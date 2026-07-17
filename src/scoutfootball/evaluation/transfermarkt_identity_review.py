"""Append-only local decisions for conservative Transfermarkt identity reviews."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

LEDGER_TYPE = "scoutfootball.transfermarkt_identity_review_ledger"
LEDGER_VERSION = "1.0"
_ACTIONS = {"confirmed", "rejected", "revoked"}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _report_context(report: dict[str, Any]) -> dict[str, Any]:
    provenance = report.get("input_provenance")
    snapshot = provenance.get("snapshot") if isinstance(provenance, dict) else None
    matrix = provenance.get("feature_matrix") if isinstance(provenance, dict) else None
    if not isinstance(snapshot, dict) or not isinstance(matrix, dict):
        raise ValueError("identity_report_provenance_missing")
    snapshot_hash = snapshot.get("sha256")
    matrix_hash = matrix.get("sha256")
    season = report.get("season")
    if not all(isinstance(value, str) and value for value in (snapshot_hash, matrix_hash, season)):
        raise ValueError("identity_report_context_invalid")
    return {
        "snapshot_sha256": snapshot_hash,
        "feature_matrix_sha256": matrix_hash,
        "season": str(season),
    }


def read_identity_review_ledger(path: Path | str) -> list[dict[str, Any]]:
    ledger = Path(path).resolve()
    if not ledger.exists():
        return []
    records = []
    for number, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"identity_ledger_blank_line:{number}")
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"identity_ledger_invalid_json:{number}") from exc
        if not isinstance(record, dict) or record.get("record_type") != LEDGER_TYPE:
            raise ValueError(f"identity_ledger_record_type_invalid:{number}")
        if record.get("action") not in _ACTIONS or not isinstance(record.get("revision"), int):
            raise ValueError(f"identity_ledger_record_invalid:{number}")
        records.append(record)
    return records


def build_identity_review_decision(
    report: dict[str, Any],
    *,
    source_row: int,
    action: str,
    canonical_player_id: str | None = None,
    reason: str = "",
    revision: int,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Validate one explicit human decision against the reviewed candidate set."""
    if action not in _ACTIONS:
        raise ValueError("identity_decision_action_invalid")
    context = _report_context(report)
    queue = report.get("review_queue")
    if not isinstance(queue, list):
        raise ValueError("identity_report_review_queue_invalid")
    reviewed = next(
        (row for row in queue if isinstance(row, dict) and row.get("source_row") == source_row),
        None,
    )
    if reviewed is None:
        raise ValueError("identity_review_row_not_found")
    candidates = reviewed.get("candidate_player_ids")
    if not isinstance(candidates, list) or not all(isinstance(value, str) for value in candidates):
        raise ValueError("identity_review_candidates_invalid")
    if action == "confirmed":
        if canonical_player_id not in candidates:
            raise ValueError("identity_confirmation_not_a_review_candidate")
    elif canonical_player_id is not None:
        raise ValueError("identity_nonconfirmation_cannot_select_candidate")
    return {
        "record_type": LEDGER_TYPE,
        "record_version": LEDGER_VERSION,
        "decision_id": str(uuid4()),
        "revision": revision,
        "recorded_at": recorded_at or _now(),
        "action": action,
        "reason": reason[:500],
        "source_row": source_row,
        "candidate_player_ids": sorted(candidates),
        "canonical_player_id": canonical_player_id,
        **context,
    }


def append_identity_review_decision(record: dict[str, Any], path: Path | str) -> Path:
    ledger = Path(path).resolve()
    existing = read_identity_review_ledger(ledger)
    if record["revision"] != len(existing) + 1:
        raise ValueError("identity_ledger_revision_conflict")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return ledger


def append_review_decision_from_report(
    report_path: Path | str,
    ledger_path: Path | str,
    *,
    source_row: int,
    action: str,
    canonical_player_id: str | None = None,
    reason: str = "",
) -> dict[str, Any]:
    try:
        report = json.loads(Path(report_path).resolve().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"identity_report_unreadable: {exc}") from exc
    if not isinstance(report, dict):
        raise ValueError("identity_report_invalid")
    revision = len(read_identity_review_ledger(ledger_path)) + 1
    record = build_identity_review_decision(
        report,
        source_row=source_row,
        action=action,
        canonical_player_id=canonical_player_id,
        reason=reason,
        revision=revision,
    )
    append_identity_review_decision(record, ledger_path)
    return record


def active_decisions_for_context(
    records: list[dict[str, Any]],
    context: dict[str, str],
) -> dict[int, dict[str, Any]]:
    """Return the latest valid decision for each reviewed row in one input context."""
    expected = {
        "snapshot_sha256": context["snapshot_sha256"],
        "feature_matrix_sha256": context["feature_matrix_sha256"],
        "season": context["season"],
    }
    current: dict[int, dict[str, Any]] = {}
    for record in records:
        if not all(record.get(key) == value for key, value in expected.items()):
            continue
        source_row = record.get("source_row")
        if isinstance(source_row, int):
            current[source_row] = record
    return current
