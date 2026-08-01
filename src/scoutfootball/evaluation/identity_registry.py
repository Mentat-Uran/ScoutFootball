"""Canonical identity registry for the player rating research system.

PRS-1 R-005 (see ``docs/PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md``) requires that
canonical ``player_id`` runs through every rating artifact. Before any
canonical migration can land, the maintainer needs a stable place to record
explicit human decisions of the form::

    (source_name, source_player_id) -> canonical_player_id

This module is that place. It is an append-only JSONL ledger of explicit
human decisions. It does **not** auto-resolve identities, fuzzy-match
display names, or modify ``player_match.parquet``. Any (source, source_id)
pair that has no recorded decision remains ``unresolved`` — that is the
honest default and the registry never silently merges two source IDs into
one canonical ID.

Design mirrors ``transfermarkt_identity_review.py`` (append-only JSONL,
record_type + record_version, revision monotonicity, fsync on append) but
differs in two ways:

1. The business key is the stable pair ``(source_name, source_player_id)``,
   not ``(snapshot_sha256, feature_matrix_sha256, season, source_row)``.
   This means a single decision applies across every snapshot, season and
   row that references that source ID — which is exactly what "canonical"
   requires.
2. There is no review queue. ``confirmed`` records a positive mapping;
   ``revoked`` records that a previous mapping was wrong and there is no
   replacement. ``lookup`` walks the revision history and returns the
   latest ``confirmed`` that has not been revoked.

Schema (one JSON object per line in ``data/gold/identity_registry/decisions.jsonl``)::

    {
      "record_type": "scoutfootball.identity_registry",
      "record_version": "1.0",
      "decision_id": "<uuid4>",
      "revision": <int, monotonic starting at 1>,
      "recorded_at": "<ISO8601 UTC>",
      "action": "confirmed" | "revoked",
      "source_name": "<str, non-empty>",
      "source_player_id": "<str, non-empty>",
      "canonical_player_id": "<str, non-empty; required for confirmed, omitted for revoked>",
      "evidence": "<str, <=500 chars; why this decision was made>",
      "decided_by": "<str, non-empty; maintainer identity>",
      "notes": "<str, <=500 chars; optional>",
      "supersedes_decision_id": "<uuid4; optional; the prior confirmed decision this corrects>"
    }
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from scoutfootball.config import PlatformSettings

REGISTRY_TYPE = "scoutfootball.identity_registry"
REGISTRY_VERSION = "1.0"
_ACTIONS = {"confirmed", "revoked"}
_EVIDENCE_MAX = 500
_NOTES_MAX = 500
_SOURCE_PLAYER_ID_MAX = 200
_CANONICAL_PLAYER_ID_MAX = 200
_SOURCE_NAME_MAX = 100
_DECIDED_BY_MAX = 100


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def registry_path(settings: PlatformSettings) -> Path:
    """Return the canonical identity registry JSONL path."""
    return settings.gold_root / "identity_registry" / "decisions.jsonl"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _require_str(value: Any, *, field: str, max_len: int) -> str:
    if value is None:
        raise ValueError(f"identity_registry_{field}_empty")
    if not isinstance(value, str):
        raise ValueError(f"identity_registry_{field}_not_string")
    if not value:
        raise ValueError(f"identity_registry_{field}_empty")
    if len(value) > max_len:
        raise ValueError(f"identity_registry_{field}_too_long:{len(value)}")
    return value


def validate_record(record: dict[str, Any]) -> dict[str, Any]:
    """Validate the schema of one registry record.

    Returns the record on success; raises ``ValueError`` on any violation.
    Validation is intentionally strict so a corrupt line cannot be silently
    promoted to a canonical decision.
    """
    if not isinstance(record, dict):
        raise ValueError("identity_registry_record_not_dict")
    if record.get("record_type") != REGISTRY_TYPE:
        raise ValueError("identity_registry_record_type_invalid")
    if record.get("record_version") != REGISTRY_VERSION:
        raise ValueError("identity_registry_record_version_invalid")

    decision_id = record.get("decision_id")
    if not isinstance(decision_id, str) or not decision_id:
        raise ValueError("identity_registry_decision_id_invalid")

    revision = record.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        raise ValueError("identity_registry_revision_invalid")

    recorded_at = record.get("recorded_at")
    if not isinstance(recorded_at, str) or not recorded_at:
        raise ValueError("identity_registry_recorded_at_invalid")

    action = record.get("action")
    if action not in _ACTIONS:
        raise ValueError("identity_registry_action_invalid")

    _require_str(
        record.get("source_name"), field="source_name", max_len=_SOURCE_NAME_MAX
    )
    _require_str(
        record.get("source_player_id"),
        field="source_player_id",
        max_len=_SOURCE_PLAYER_ID_MAX,
    )

    canonical_player_id = record.get("canonical_player_id")
    if action == "confirmed":
        _require_str(
            canonical_player_id,
            field="canonical_player_id",
            max_len=_CANONICAL_PLAYER_ID_MAX,
        )
    else:  # revoked
        if canonical_player_id is not None and canonical_player_id != "":
            raise ValueError("identity_registry_revoked_cannot_select_canonical")

    _require_str(
        record.get("evidence"), field="evidence", max_len=_EVIDENCE_MAX
    )
    _require_str(
        record.get("decided_by"), field="decided_by", max_len=_DECIDED_BY_MAX
    )

    notes = record.get("notes", "")
    if not isinstance(notes, str):
        raise ValueError("identity_registry_notes_not_string")
    if len(notes) > _NOTES_MAX:
        raise ValueError(f"identity_registry_notes_too_long:{len(notes)}")

    supersedes = record.get("supersedes_decision_id")
    if supersedes is not None:
        if not isinstance(supersedes, str) or not supersedes:
            raise ValueError("identity_registry_supersedes_invalid")

    return record


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def read_registry(
    path: Path | str | None = None,
    *,
    settings: PlatformSettings | None = None,
) -> list[dict[str, Any]]:
    """Read and validate every record in the registry JSONL.

    Returns an empty list if the file does not exist. Raises ``ValueError``
    on any structural violation (blank line, invalid JSON, wrong record_type,
    revision gap, or schema failure) so a corrupt registry cannot be silently
    used.
    """
    if path is None:
        if settings is None:
            raise ValueError("identity_registry_read_requires_path_or_settings")
        path = registry_path(settings)
    ledger = Path(path).resolve()
    if not ledger.exists():
        return []
    records: list[dict[str, Any]] = []
    for number, line in enumerate(
        ledger.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            raise ValueError(f"identity_registry_blank_line:{number}")
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"identity_registry_invalid_json:{number}") from exc
        try:
            validate_record(record)
        except ValueError as exc:
            raise ValueError(f"identity_registry_record_invalid:{number}:{exc}") from exc
        if record["revision"] != len(records) + 1:
            raise ValueError(
                f"identity_registry_revision_gap:{number}:{record['revision']}:"
                f"expected:{len(records) + 1}"
            )
        records.append(record)
    return records


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def build_decision(
    *,
    source_name: str,
    source_player_id: str,
    action: str,
    canonical_player_id: str | None = None,
    evidence: str,
    decided_by: str,
    notes: str = "",
    supersedes_decision_id: str | None = None,
    revision: int,
    recorded_at: str | None = None,
    decision_id: str | None = None,
) -> dict[str, Any]:
    """Build and validate one registry decision record.

    The caller must pass ``revision = len(existing_records) + 1``. The
    registry never auto-assigns revisions because the append path is the
    only writer and must detect a concurrent writer via a revision gap.
    """
    record: dict[str, Any] = {
        "record_type": REGISTRY_TYPE,
        "record_version": REGISTRY_VERSION,
        "decision_id": decision_id or str(uuid4()),
        "revision": revision,
        "recorded_at": recorded_at or _now(),
        "action": action,
        "source_name": source_name,
        "source_player_id": source_player_id,
        "evidence": evidence,
        "decided_by": decided_by,
        "notes": notes,
    }
    if action == "confirmed":
        if not isinstance(canonical_player_id, str) or not canonical_player_id:
            raise ValueError("identity_registry_confirmed_requires_canonical")
        record["canonical_player_id"] = canonical_player_id
    else:  # revoked
        if canonical_player_id is not None and canonical_player_id != "":
            raise ValueError("identity_registry_revoked_cannot_select_canonical")
    if supersedes_decision_id is not None:
        record["supersedes_decision_id"] = supersedes_decision_id
    validate_record(record)
    return record


def append_decision(
    record: dict[str, Any],
    path: Path | str | None = None,
    *,
    settings: PlatformSettings | None = None,
) -> Path:
    """Append one validated decision record to the registry JSONL.

    Detects concurrent writers via revision monotonicity and refuses to
    write if the registry has advanced since the caller computed
    ``revision``.
    """
    if path is None:
        if settings is None:
            raise ValueError("identity_registry_append_requires_path_or_settings")
        path = registry_path(settings)
    ledger = Path(path).resolve()
    existing = read_registry(ledger)
    if record["revision"] != len(existing) + 1:
        raise ValueError(
            f"identity_registry_revision_conflict:{record['revision']}:"
            f"expected:{len(existing) + 1}"
        )
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return ledger


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


def _records_for_key(
    records: list[dict[str, Any]],
    *,
    source_name: str,
    source_player_id: str,
) -> list[dict[str, Any]]:
    """Return every record matching the key, in ascending revision order."""
    return [
        r
        for r in records
        if r["source_name"] == source_name
        and r["source_player_id"] == source_player_id
    ]


def lookup(
    records: list[dict[str, Any]],
    *,
    source_name: str,
    source_player_id: str,
) -> dict[str, Any] | None:
    """Return the latest active decision for one (source, source_id) pair.

    Semantics:

    - Walk records in revision order.
    - A ``confirmed`` record updates the active mapping.
    - A ``revoked`` record clears the active mapping (sets it to ``None``).
    - The final state is returned. ``None`` means the pair is unresolved:
      either no record exists, or the most recent record was a revoke.
    """
    active: dict[str, Any] | None = None
    for record in _records_for_key(
        records,
        source_name=source_name,
        source_player_id=source_player_id,
    ):
        if record["action"] == "confirmed":
            active = record
        else:  # revoked
            active = None
    return active


def active_canonical_map(
    records: list[dict[str, Any]],
) -> dict[tuple[str, str], str]:
    """Return the current ``{(source, source_id): canonical_player_id}`` map.

    Every key whose latest action is ``confirmed`` appears here. Any key
    whose latest action is ``revoked`` or that has no record is omitted —
    callers must treat absence as ``unresolved`` rather than guessing.
    """
    out: dict[tuple[str, str], str] = {}
    for record in records:
        key = (record["source_name"], record["source_player_id"])
        if record["action"] == "confirmed":
            out[key] = record["canonical_player_id"]
        else:  # revoked
            out.pop(key, None)
    return out


def registry_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a read-only summary of registry contents.

    Used by the ``identity-registry stats`` CLI and by upstream health
    reports that need to surface "how many source IDs have been
    canonicalised so far" without exposing the underlying decisions.
    """
    active = active_canonical_map(records)
    by_source: dict[str, int] = {}
    by_action: dict[str, int] = {"confirmed": 0, "revoked": 0}
    for record in records:
        by_action[record["action"]] = by_action.get(record["action"], 0) + 1
    for (source_name, _source_player_id) in active:
        by_source[source_name] = by_source.get(source_name, 0) + 1
    return {
        "schema": REGISTRY_TYPE,
        "schema_version": REGISTRY_VERSION,
        "total_records": len(records),
        "active_mapping_count": len(active),
        "records_by_action": by_action,
        "active_mappings_by_source": by_source,
        "latest_revision": records[-1]["revision"] if records else 0,
        "latest_recorded_at": records[-1]["recorded_at"] if records else None,
    }


__all__ = [
    "REGISTRY_TYPE",
    "REGISTRY_VERSION",
    "active_canonical_map",
    "append_decision",
    "build_decision",
    "lookup",
    "read_registry",
    "registry_path",
    "registry_summary",
    "validate_record",
]
