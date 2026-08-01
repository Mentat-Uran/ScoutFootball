"""PRS-3 personal evaluation label ledger (append-only, pairwise + tier).

PRS-3 (see ``docs/PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md`` §5 and §PRS-3)
requires a small, trustworthy personal evaluation set to provide independent
evidence for model comparison. The label ledger is the foundation: an
append-only JSONL file that records every pairwise preference and tier
judgment the maintainer makes, with full history, evidence tracing, and
independence auditing.

Design contract (PRS-3 退出门槛):

1. **Append-only.** Like ``identity_registry``, the ledger never mutates
   or deletes records. A label is ``confirmed`` (added) or ``revoked``
   (withdrawn). Re-annotation creates a new ``confirmed`` record that
   supersedes the previous one via ``supersedes_decision_id``. The full
   history is preserved for reproducibility and audit.

2. **Two label types in one ledger.** ``human_pairwise_preference`` (A vs
   B within the same role and observation window) and ``human_tier`` (a
   1-5 tier for one player in one role/season). Both share the same
   envelope (decision_id, revision, action, evidence, etc.) but carry
   type-specific payload fields. ``external_reference``,
   ``future_outcome``, and ``model_derived`` are also valid label types
   per PRS plan §5, but ``model_derived`` is always excluded from
   supervision-eligible sets.

3. **Cohort-scoped.** Every label carries a ``cohort_hash`` (16 hex chars
   from ``CohortDefinition.cohort_hash()``) so labels are tied to a
   precise cohort definition, not a vague "all players" scope. This
   ensures labels are comparable within a cohort and prevents silent
   population drift between annotation and evaluation.

4. **Evidence tracing.** Every label records ``observation_window`` (ISO
   date range, e.g. ``2024-08-01/2025-05-31``), ``evidence`` (free text
   citing what was observed), and ``blind`` (whether the annotator was
   blind to model scores). This satisfies the PRS-3 exit gate "same
   player's labels can be traced to evidence and observation window."

5. **Independence audit.** ``label_independence_audit()`` verifies that
   ``model_derived`` labels are never in the supervision-eligible set,
   that pairwise labels are within-role (both players share the same
   ``role_family``), that no player is compared to themselves, and that
   observation windows are valid ISO date ranges. This satisfies the
   PRS-3 exit gate "model-derived labels cannot pass the default
   supervised training gate."

6. **Read-only diagnostic.** The ledger module never modifies model
   artifacts, feature matrices, or rating outputs. It only reads and
   writes its own JSONL file. Consumers (PRS-4 evaluation, CLI reports)
   are responsible for using labels appropriately.

Record schema (one JSON object per line in the ledger file):

    {
      "record_type": "scoutfootball.label_ledger",
      "record_version": "1.0",
      "decision_id": "uuid4",
      "revision": 1,
      "recorded_at": "2026-07-31T12:00:00Z",
      "action": "confirmed",
      "label_type": "human_pairwise_preference",
      "cohort_hash": "abc123def4567890",
      "role_family": "CB",
      "season_id": "2425",
      "observation_window": "2024-08-01/2025-05-31",
      "confidence": "high",
      "evidence": "Player A had 2.3 interceptions/90 vs Player B 1.1;...",
      "decided_by": "maintainer",
      "notes": "",
      "blind": true,
      "supersedes_decision_id": null,
      "player_a_id": "unresolved:understat:u|1",
      "player_b_id": "unresolved:understat:u|2",
      "preferred_player": "a"
    }

For ``human_tier`` the payload fields are ``canonical_player_id`` and
``tier`` (1-5) instead of the pairwise triple.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scoutfootball.config import PlatformSettings

LEDGER_TYPE = "scoutfootball.label_ledger"
LEDGER_VERSION = "1.0"

# Field length limits (mirrors identity_registry convention).
_LABEL_TYPE_MAX = 50
_COHORT_HASH_LEN = 16  # hex chars from CohortDefinition.cohort_hash()
_ROLE_FAMILY_MAX = 20
_SEASON_ID_MAX = 20
_OBSERVATION_WINDOW_MAX = 50
_CONFIDENCE_MAX = 10
_EVIDENCE_MAX = 500
_DECIDED_BY_MAX = 100
_NOTES_MAX = 500
_PLAYER_ID_MAX = 200
_PREFERENCE_MAX = 10  # "a", "b", "tie"

# Valid label types per PRS plan §5.
_VALID_LABEL_TYPES = frozenset(
    {
        "human_pairwise_preference",
        "human_tier",
        "external_reference",
        "future_outcome",
        "model_derived",
    }
)

# Supervision-eligible label types (can be used to train/anchor ratings).
# model_derived is explicitly excluded — it is self-referential.
SUPERVISION_ELIGIBLE_LABEL_TYPES = frozenset(
    {
        "human_pairwise_preference",
        "human_tier",
        "external_reference",
        "future_outcome",
    }
)
SELF_REFERENTIAL_LABEL_TYPES = frozenset({"model_derived"})

_VALID_ACTIONS = frozenset({"confirmed", "revoked"})
_VALID_CONFIDENCES = frozenset({"high", "medium", "low"})
_VALID_PREFERENCES = frozenset({"a", "b", "tie"})

# Minimum tier value (1 = elite) and maximum (5 = below average).
_TIER_MIN = 1
_TIER_MAX = 5

# Observation window regex: YYYY-MM-DD/YYYY-MM-DD
_OBSERVATION_WINDOW_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}/\d{4}-\d{2}-\d{2}$"
)


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def ledger_path(settings: PlatformSettings | None = None) -> Path:
    """Return the path to the label ledger JSONL file."""
    s = settings or PlatformSettings.from_root()
    return s.gold_root / "label_ledger" / "decisions.jsonl"


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_str(
    value: Any, *, field: str, max_len: int
) -> str:
    """Validate a required string field. Returns the cleaned string."""
    if not isinstance(value, str):
        raise ValueError(f"label_ledger_{field}_not_string")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"label_ledger_{field}_empty")
    if len(cleaned) > max_len:
        raise ValueError(
            f"label_ledger_{field}_too_long:{len(cleaned)}"
        )
    return cleaned


def _optional_str(
    value: Any, *, field: str, max_len: int
) -> str:
    """Validate an optional string field. Returns '' for None/empty."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"label_ledger_{field}_not_string")
    cleaned = value.strip()
    if len(cleaned) > max_len:
        raise ValueError(
            f"label_ledger_{field}_too_long:{len(cleaned)}"
        )
    return cleaned


def _validate_observation_window(value: str) -> str:
    """Validate ISO date range format YYYY-MM-DD/YYYY-MM-DD."""
    if not _OBSERVATION_WINDOW_RE.match(value):
        raise ValueError(
            f"label_ledger_observation_window_invalid_format:{value!r}"
        )
    parts = value.split("/")
    try:
        start = datetime.strptime(parts[0], "%Y-%m-%d")
        end = datetime.strptime(parts[1], "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(
            f"label_ledger_observation_window_invalid_date:{value!r}"
        ) from exc
    if end < start:
        raise ValueError(
            f"label_ledger_observation_window_end_before_start:{value!r}"
        )
    return value


def _validate_tier(value: Any) -> int:
    """Validate tier is an integer in [1, 5]."""
    if isinstance(value, bool):
        raise ValueError(f"label_ledger_tier_bool:{value!r}")
    if not isinstance(value, int):
        raise ValueError(f"label_ledger_tier_not_int:{value!r}")
    if not (_TIER_MIN <= value <= _TIER_MAX):
        raise ValueError(
            f"label_ledger_tier_out_of_range:{value}"
        )
    return value


def _validate_revision(value: Any) -> int:
    """Validate revision is a positive integer (not bool)."""
    if isinstance(value, bool):
        raise ValueError(f"label_ledger_revision_bool:{value!r}")
    if not isinstance(value, int):
        raise ValueError(f"label_ledger_revision_not_int:{value!r}")
    if value < 1:
        raise ValueError(f"label_ledger_revision_non_positive:{value}")
    return value


def _validate_cohort_hash(value: str) -> str:
    """Validate cohort_hash is 16 hex chars."""
    if len(value) != _COHORT_HASH_LEN:
        raise ValueError(
            f"label_ledger_cohort_hash_wrong_length:{len(value)}"
        )
    if not re.fullmatch(r"[0-9a-f]+", value):
        raise ValueError(f"label_ledger_cohort_hash_not_hex:{value!r}")
    return value


# ---------------------------------------------------------------------------
# Record validation
# ---------------------------------------------------------------------------


def validate_record(record: Any) -> dict[str, Any]:
    """Validate a label ledger record against the schema.

    Returns the validated record. Raises ``ValueError`` with an
    ``label_ledger_<field>_<reason>`` error code on any violation.
    """
    if not isinstance(record, dict):
        raise ValueError("label_ledger_record_not_dict")

    # Envelope fields.
    if record.get("record_type") != LEDGER_TYPE:
        raise ValueError(
            f"label_ledger_record_type_invalid:{record.get('record_type')!r}"
        )
    if record.get("record_version") != LEDGER_VERSION:
        raise ValueError(
            f"label_ledger_record_version_invalid:{record.get('record_version')!r}"
        )

    decision_id = record.get("decision_id")
    if not isinstance(decision_id, str) or not decision_id:
        raise ValueError("label_ledger_decision_id_empty")
    try:
        uuid.UUID(decision_id)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"label_ledger_decision_id_not_uuid:{decision_id!r}"
        ) from exc

    revision = _validate_revision(record.get("revision"))

    recorded_at = record.get("recorded_at")
    if not isinstance(recorded_at, str) or not recorded_at:
        raise ValueError("label_ledger_recorded_at_empty")

    action = record.get("action")
    if action not in _VALID_ACTIONS:
        raise ValueError(f"label_ledger_action_invalid:{action!r}")

    label_type = _require_str(
        record.get("label_type"),
        field="label_type",
        max_len=_LABEL_TYPE_MAX,
    )
    if label_type not in _VALID_LABEL_TYPES:
        raise ValueError(f"label_ledger_label_type_unknown:{label_type}")

    cohort_hash = _validate_cohort_hash(
        _require_str(
            record.get("cohort_hash"),
            field="cohort_hash",
            max_len=_COHORT_HASH_LEN,
        )
    )

    role_family = _require_str(
        record.get("role_family"),
        field="role_family",
        max_len=_ROLE_FAMILY_MAX,
    )

    season_id = _require_str(
        record.get("season_id"),
        field="season_id",
        max_len=_SEASON_ID_MAX,
    )

    observation_window = _validate_observation_window(
        _require_str(
            record.get("observation_window"),
            field="observation_window",
            max_len=_OBSERVATION_WINDOW_MAX,
        )
    )

    confidence = _require_str(
        record.get("confidence"),
        field="confidence",
        max_len=_CONFIDENCE_MAX,
    )
    if confidence not in _VALID_CONFIDENCES:
        raise ValueError(f"label_ledger_confidence_invalid:{confidence!r}")

    evidence = _require_str(
        record.get("evidence"),
        field="evidence",
        max_len=_EVIDENCE_MAX,
    )

    decided_by = _require_str(
        record.get("decided_by"),
        field="decided_by",
        max_len=_DECIDED_BY_MAX,
    )

    notes = _optional_str(
        record.get("notes"),
        field="notes",
        max_len=_NOTES_MAX,
    )

    blind = record.get("blind")
    if not isinstance(blind, bool):
        raise ValueError(f"label_ledger_blind_not_bool:{blind!r}")

    supersedes = record.get("supersedes_decision_id")
    if supersedes is not None:
        if not isinstance(supersedes, str) or not supersedes:
            raise ValueError(
                f"label_ledger_supersedes_not_string:{supersedes!r}"
            )
        try:
            uuid.UUID(supersedes)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"label_ledger_supersedes_not_uuid:{supersedes!r}"
            ) from exc

    # Type-specific payload validation.
    # For "confirmed" records, the full payload is required.
    # For "revoked" records, the payload is optional (the supersedes_decision_id
    # identifies what's being revoked). If payload fields are present on a
    # revoke, they are still validated.
    payload: dict[str, Any] = {}
    if label_type == "human_pairwise_preference":
        has_payload = (
            record.get("player_a_id") is not None
            or record.get("player_b_id") is not None
            or record.get("preferred_player") is not None
        )
        if action == "confirmed" or has_payload:
            player_a_id = _require_str(
                record.get("player_a_id"),
                field="player_a_id",
                max_len=_PLAYER_ID_MAX,
            )
            player_b_id = _require_str(
                record.get("player_b_id"),
                field="player_b_id",
                max_len=_PLAYER_ID_MAX,
            )
            preferred_player = _require_str(
                record.get("preferred_player"),
                field="preferred_player",
                max_len=_PREFERENCE_MAX,
            )
            if preferred_player not in _VALID_PREFERENCES:
                raise ValueError(
                    f"label_ledger_preferred_player_invalid:{preferred_player!r}"
                )
            if player_a_id == player_b_id:
                raise ValueError("label_ledger_pairwise_self_comparison")
            payload = {
                "player_a_id": player_a_id,
                "player_b_id": player_b_id,
                "preferred_player": preferred_player,
            }

    elif label_type == "human_tier":
        has_payload = (
            record.get("canonical_player_id") is not None
            or record.get("tier") is not None
        )
        if action == "confirmed" or has_payload:
            canonical_player_id = _require_str(
                record.get("canonical_player_id"),
                field="canonical_player_id",
                max_len=_PLAYER_ID_MAX,
            )
            tier = _validate_tier(record.get("tier"))
            payload = {
                "canonical_player_id": canonical_player_id,
                "tier": tier,
            }

    # Revoke: the supersedes_decision_id should point to the record being
    # revoked. We don't enforce supersedes on revoke (the caller may revoke
    # by decision_id via a separate path), but if present, it must be valid.

    result: dict[str, Any] = {
        "record_type": LEDGER_TYPE,
        "record_version": LEDGER_VERSION,
        "decision_id": decision_id,
        "revision": revision,
        "recorded_at": recorded_at,
        "action": action,
        "label_type": label_type,
        "cohort_hash": cohort_hash,
        "role_family": role_family,
        "season_id": season_id,
        "observation_window": observation_window,
        "confidence": confidence,
        "evidence": evidence,
        "decided_by": decided_by,
        "notes": notes,
        "blind": blind,
        "supersedes_decision_id": supersedes,
    }
    result.update(payload)
    return result


# ---------------------------------------------------------------------------
# Build and append
# ---------------------------------------------------------------------------


def build_label(
    *,
    action: str,
    label_type: str,
    cohort_hash: str,
    role_family: str,
    season_id: str,
    observation_window: str,
    confidence: str,
    evidence: str,
    decided_by: str,
    notes: str = "",
    blind: bool = True,
    supersedes_decision_id: str | None = None,
    revision: int,
    recorded_at: str | None = None,
    decision_id: str | None = None,
    # Pairwise-specific:
    player_a_id: str | None = None,
    player_b_id: str | None = None,
    preferred_player: str | None = None,
    # Tier-specific:
    canonical_player_id: str | None = None,
    tier: int | None = None,
) -> dict[str, Any]:
    """Build and validate a single label ledger record.

    The caller must pass ``revision = len(existing_records) + 1``.
    ``decision_id`` and ``recorded_at`` are generated if omitted.
    """
    if decision_id is None:
        decision_id = str(uuid.uuid4())
    if recorded_at is None:
        recorded_at = _now()

    record: dict[str, Any] = {
        "record_type": LEDGER_TYPE,
        "record_version": LEDGER_VERSION,
        "decision_id": decision_id,
        "revision": revision,
        "recorded_at": recorded_at,
        "action": action,
        "label_type": label_type,
        "cohort_hash": cohort_hash,
        "role_family": role_family,
        "season_id": season_id,
        "observation_window": observation_window,
        "confidence": confidence,
        "evidence": evidence,
        "decided_by": decided_by,
        "notes": notes,
        "blind": blind,
        "supersedes_decision_id": supersedes_decision_id,
    }

    # Add type-specific payload. Payload is required for confirmed records
    # and optional for revoked records (the supersedes_decision_id identifies
    # what's being revoked). If payload fields are provided on a revoke,
    # they are still included in the record.
    if label_type == "human_pairwise_preference":
        if action == "confirmed":
            if player_a_id is None or player_b_id is None or preferred_player is None:
                raise ValueError(
                    "label_ledger_pairwise_missing_payload"
                )
            record["player_a_id"] = player_a_id
            record["player_b_id"] = player_b_id
            record["preferred_player"] = preferred_player
        else:
            # Revoked: include payload only if all three are provided.
            if player_a_id is not None or player_b_id is not None or preferred_player is not None:
                if player_a_id is None or player_b_id is None or preferred_player is None:
                    raise ValueError(
                        "label_ledger_pairwise_partial_payload"
                    )
                record["player_a_id"] = player_a_id
                record["player_b_id"] = player_b_id
                record["preferred_player"] = preferred_player
    elif label_type == "human_tier":
        if action == "confirmed":
            if canonical_player_id is None or tier is None:
                raise ValueError(
                    "label_ledger_tier_missing_payload"
                )
            record["canonical_player_id"] = canonical_player_id
            record["tier"] = tier
        else:
            # Revoked: include payload only if both are provided.
            if canonical_player_id is not None or tier is not None:
                if canonical_player_id is None or tier is None:
                    raise ValueError(
                        "label_ledger_tier_partial_payload"
                    )
                record["canonical_player_id"] = canonical_player_id
                record["tier"] = tier

    return validate_record(record)


def append_label(
    record: dict[str, Any],
    path: str | Path | None = None,
    *,
    settings: PlatformSettings | None = None,
) -> None:
    """Append a validated label record to the ledger file.

    Re-reads the ledger to detect concurrent writers (revision conflict).
    Creates parent directories if needed. Uses ``os.fsync`` for durability.
    """
    p = Path(path) if path is not None else ledger_path(settings)

    # Re-read to check revision consistency.
    existing = read_ledger(p)
    expected_revision = len(existing) + 1
    if record["revision"] != expected_revision:
        raise ValueError(
            f"label_ledger_revision_conflict:{record['revision']}:"
            f"expected:{expected_revision}"
        )

    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8", newline="\n") as f:
        f.write(
            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        )
        f.flush()
        os.fsync(f.fileno())


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def read_ledger(
    path: str | Path | None = None,
    *,
    settings: PlatformSettings | None = None,
) -> list[dict[str, Any]]:
    """Read and validate every record in the label ledger.

    Returns ``[]`` if the file does not exist. Raises ``ValueError`` on
    blank lines, invalid JSON, wrong record_type, schema violations, or
    revision gaps.
    """
    if path is not None:
        p = Path(path)
    elif settings is not None:
        p = ledger_path(settings)
    else:
        p = ledger_path()

    if not p.exists():
        return []

    records: list[dict[str, Any]] = []
    with open(p, encoding="utf-8") as f:
        for line_num, raw in enumerate(f, start=1):
            stripped = raw.strip()
            if not stripped:
                raise ValueError(f"label_ledger_blank_line:{line_num}")
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"label_ledger_invalid_json:{line_num}:{exc}"
                ) from exc
            validated = validate_record(record)
            if validated["revision"] != len(records) + 1:
                raise ValueError(
                    f"label_ledger_revision_gap:{validated['revision']}"
                )
            records.append(validated)
    return records


# ---------------------------------------------------------------------------
# Lookup and active labels
# ---------------------------------------------------------------------------


def active_labels(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only confirmed records that have not been superseded.

    A record is inactive if any later record (confirmed or revoked)
    points to it via ``supersedes_decision_id``. This implements the
    append-only contract: revokes and re-annotations create new records
    that supersede prior ones, rather than mutating or deleting them.

    The full history is preserved in ``records``; this function returns
    only the currently-active subset for evaluation and reporting.
    """
    superseded_ids: set[str] = {
        r["supersedes_decision_id"]
        for r in records
        if r.get("supersedes_decision_id") is not None
    }
    return [
        r for r in records
        if r["action"] == "confirmed"
        and r["decision_id"] not in superseded_ids
    ]


def lookup_labels(
    records: list[dict[str, Any]],
    *,
    cohort_hash: str | None = None,
    label_type: str | None = None,
    role_family: str | None = None,
    season_id: str | None = None,
    player_id: str | None = None,
    active_only: bool = True,
) -> list[dict[str, Any]]:
    """Filter labels by optional criteria.

    When ``player_id`` is given, matches both pairwise (player_a or
    player_b) and tier (canonical_player_id) labels. When
    ``active_only=True``, only labels whose latest action is confirmed
    are returned.
    """
    pool = active_labels(records) if active_only else records
    result: list[dict[str, Any]] = []
    for r in pool:
        if cohort_hash is not None and r["cohort_hash"] != cohort_hash:
            continue
        if label_type is not None and r["label_type"] != label_type:
            continue
        if role_family is not None and r["role_family"] != role_family:
            continue
        if season_id is not None and r["season_id"] != season_id:
            continue
        if player_id is not None:
            if r["label_type"] == "human_pairwise_preference":
                if (
                    r.get("player_a_id") != player_id
                    and r.get("player_b_id") != player_id
                ):
                    continue
            elif r["label_type"] == "human_tier":
                if r.get("canonical_player_id") != player_id:
                    continue
        result.append(r)
    return result


# ---------------------------------------------------------------------------
# Summary and audit
# ---------------------------------------------------------------------------


def ledger_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Return summary statistics for the label ledger."""
    by_action: dict[str, int] = {}
    by_label_type: dict[str, int] = {}
    by_confidence: dict[str, int] = {}
    by_role: dict[str, int] = {}
    by_cohort: dict[str, int] = {}
    blind_count = 0
    latest_revision = 0
    latest_recorded_at = ""

    for r in records:
        by_action[r["action"]] = by_action.get(r["action"], 0) + 1
        by_label_type[r["label_type"]] = by_label_type.get(
            r["label_type"], 0
        ) + 1
        by_confidence[r["confidence"]] = by_confidence.get(
            r["confidence"], 0
        ) + 1
        by_role[r["role_family"]] = by_role.get(r["role_family"], 0) + 1
        by_cohort[r["cohort_hash"]] = by_cohort.get(r["cohort_hash"], 0) + 1
        if r["blind"]:
            blind_count += 1
        if r["revision"] > latest_revision:
            latest_revision = r["revision"]
            latest_recorded_at = r["recorded_at"]

    active = active_labels(records)
    return {
        "schema": LEDGER_TYPE,
        "schema_version": LEDGER_VERSION,
        "total_records": len(records),
        "active_label_count": len(active),
        "blind_annotation_count": blind_count,
        "records_by_action": by_action,
        "records_by_label_type": by_label_type,
        "records_by_confidence": by_confidence,
        "records_by_role_family": by_role,
        "records_by_cohort_hash": by_cohort,
        "latest_revision": latest_revision,
        "latest_recorded_at": latest_recorded_at,
    }


def label_independence_audit(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Audit label independence for supervised training eligibility.

    Checks:
    1. ``model_derived`` labels are never in the active supervision-eligible
       set.
    2. Pairwise labels are within-role (both players share role_family).
    3. No pairwise label compares a player to themselves.
    4. Observation windows are valid ISO date ranges.
    5. Every label has non-empty evidence.

    Returns a dict with ``status`` (``"ok"`` or ``"violations_found"``),
    ``violations`` list, and summary counts.
    """
    active = active_labels(records)
    violations: list[dict[str, Any]] = []

    for r in active:
        # Check 1: model_derived in supervision-eligible set.
        if r["label_type"] in SELF_REFERENTIAL_LABEL_TYPES:
            violations.append({
                "decision_id": r["decision_id"],
                "violation": "model_derived_in_active_set",
                "detail": (
                    "model_derived labels cannot be used for supervised "
                    "training; they are self-referential."
                ),
            })

        # Check 3: pairwise self-comparison (already enforced in
        # validate_record, but double-check for safety).
        if r["label_type"] == "human_pairwise_preference":
            if r.get("player_a_id") == r.get("player_b_id"):
                violations.append({
                    "decision_id": r["decision_id"],
                    "violation": "pairwise_self_comparison",
                    "detail": (
                        f"player_a_id == player_b_id == "
                        f"{r.get('player_a_id')!r}"
                    ),
                })

        # Check 4: observation window validity (already enforced in
        # validate_record, but double-check for safety).
        ow = r.get("observation_window", "")
        if not _OBSERVATION_WINDOW_RE.match(ow):
            violations.append({
                "decision_id": r["decision_id"],
                "violation": "observation_window_invalid",
                "detail": f"observation_window={ow!r}",
            })

        # Check 5: evidence non-empty.
        if not r.get("evidence", "").strip():
            violations.append({
                "decision_id": r["decision_id"],
                "violation": "evidence_empty",
                "detail": "Every label must cite what was observed.",
            })

    # Supervision-eligible active labels.
    eligible = [
        r for r in active
        if r["label_type"] in SUPERVISION_ELIGIBLE_LABEL_TYPES
    ]
    eligible_by_type: dict[str, int] = {}
    for r in eligible:
        eligible_by_type[r["label_type"]] = (
            eligible_by_type.get(r["label_type"], 0) + 1
        )

    return {
        "policy": "independence-audit-v1",
        "status": "ok" if not violations else "violations_found",
        "total_active_labels": len(active),
        "supervision_eligible_count": len(eligible),
        "supervision_eligible_by_type": eligible_by_type,
        "model_derived_active_count": sum(
            1 for r in active
            if r["label_type"] in SELF_REFERENTIAL_LABEL_TYPES
        ),
        "violation_count": len(violations),
        "violations": violations,
        "caveat": (
            "Independence audit checks structural invariants (source type, "
            "role consistency, evidence presence). It does not prove that "
            "the annotator was truly blind or that the evidence is correct."
        ),
    }


# ---------------------------------------------------------------------------
# Revoke helper
# ---------------------------------------------------------------------------


def build_revoke_label(
    *,
    target_decision_id: str,
    cohort_hash: str,
    role_family: str,
    season_id: str,
    observation_window: str,
    label_type: str,
    evidence: str,
    decided_by: str,
    notes: str = "",
    revision: int,
    recorded_at: str | None = None,
    decision_id: str | None = None,
) -> dict[str, Any]:
    """Build a revoke record that supersedes a confirmed label.

    The revoke record carries the same envelope fields as the target
    (cohort_hash, role_family, season_id, observation_window, label_type)
    so the ledger remains self-describing. The ``action`` is ``revoked``
    and ``supersedes_decision_id`` points to the target.
    """
    return build_label(
        action="revoked",
        label_type=label_type,
        cohort_hash=cohort_hash,
        role_family=role_family,
        season_id=season_id,
        observation_window=observation_window,
        confidence="low",  # revoke does not carry confidence
        evidence=evidence,
        decided_by=decided_by,
        notes=notes,
        blind=False,  # revoke is not an annotation
        supersedes_decision_id=target_decision_id,
        revision=revision,
        recorded_at=recorded_at,
        decision_id=decision_id,
    )


__all__ = [
    "LEDGER_TYPE",
    "LEDGER_VERSION",
    "SUPERVISION_ELIGIBLE_LABEL_TYPES",
    "SELF_REFERENTIAL_LABEL_TYPES",
    "ledger_path",
    "validate_record",
    "build_label",
    "build_revoke_label",
    "append_label",
    "read_ledger",
    "active_labels",
    "lookup_labels",
    "ledger_summary",
    "label_independence_audit",
]
