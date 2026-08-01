"""Label stability and inter-annotator agreement diagnostics.

PRS-3 slice 3 (PRS-LABEL-006): on top of ``label_ledger``, surface two
maintainer-facing diagnostics that quantify annotation stability:

1. ``retest_pairs`` — re-annotation pairs traced via
   ``supersedes_decision_id``. For each confirmed record that supersedes
   another confirmed record, compare the original label value against
   the retest label value and report whether they are consistent.

2. ``annotator_agreement`` — groups of confirmed labels (including
   superseded ones) on the same business key that were decided by
   different annotators. For each group, report whether the annotators
   agreed on the label value.

The module is read-only and does not modify the ledger file. It does not
participate in the fail-closed verdict — stability metrics are signals
for the maintainer, not gates. An empty ledger returns 0/0/0/0 honestly.

Pairwise preference normalisation reuses the same order-independent
``first``/``second``/``tie`` mapping as ``label_review_queue``: a pair
``(a, b, prefer a)`` and a pair ``(b, a, prefer b)`` both map to the
same value when the player ids are sorted, so the same physical
preference is compared regardless of which player was listed first.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from scoutfootball.evaluation.label_ledger import active_labels

LABEL_STABILITY_SCHEMA = "scoutfootball.label-stability"
LABEL_STABILITY_VERSION = "1.0.0"

DEFAULT_TIER_AGREEMENT_TOLERANCE = 1


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso8601(value: Any) -> datetime | None:
    """Parse an ISO 8601 timestamp like ``2026-07-31T00:00:00Z``."""
    if not isinstance(value, str) or not value:
        return None
    try:
        # Python 3.11+ datetime.fromisoformat handles the ``Z`` suffix
        # via the ``+00:00`` substitution below for older runtimes.
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _pairwise_business_key(record: dict[str, Any]) -> tuple[str, ...] | None:
    """Return the order-independent business key for a pairwise label."""
    if record.get("label_type") != "human_pairwise_preference":
        return None
    a = record.get("player_a_id")
    b = record.get("player_b_id")
    if not isinstance(a, str) or not isinstance(b, str):
        return None
    first, second = (a, b) if a <= b else (b, a)
    return (
        record.get("cohort_hash", ""),
        record.get("role_family", ""),
        record.get("season_id", ""),
        first,
        second,
    )


def _tier_business_key(record: dict[str, Any]) -> tuple[str, ...] | None:
    """Return the business key for a tier label."""
    if record.get("label_type") != "human_tier":
        return None
    pid = record.get("canonical_player_id")
    if not isinstance(pid, str):
        return None
    return (
        record.get("cohort_hash", ""),
        record.get("role_family", ""),
        record.get("season_id", ""),
        pid,
    )


def _pairwise_label_value(record: dict[str, Any]) -> str | None:
    """Return the normalised preference direction.

    Maps ``(player_a_id, player_b_id, preferred_player)`` to
    ``first``/``second``/``tie`` where ``first``/``second`` refer to the
    sorted pair. This is order-independent: ``(a, b, prefer a)`` and
    ``(b, a, prefer b)`` both map to the same value.
    """
    a = record.get("player_a_id")
    b = record.get("player_b_id")
    preferred = record.get("preferred_player")
    if not isinstance(a, str) or not isinstance(b, str):
        return None
    if not isinstance(preferred, str):
        return None
    if a == b:
        return "tie"
    if preferred == "tie":
        return "tie"
    if a < b:
        if preferred == "a":
            return "first"
        if preferred == "b":
            return "second"
        return None
    if preferred == "a":
        return "second"
    if preferred == "b":
        return "first"
    return None


def _tier_label_value(record: dict[str, Any]) -> int | None:
    """Return the tier value as int, or None if not a valid tier label."""
    if record.get("label_type") != "human_tier":
        return None
    tier = record.get("tier")
    if isinstance(tier, bool) or not isinstance(tier, int):
        return None
    return tier


def _label_value(record: dict[str, Any]) -> Any:
    """Return the comparable label value for any supported label type."""
    if record.get("label_type") == "human_pairwise_preference":
        return _pairwise_label_value(record)
    if record.get("label_type") == "human_tier":
        return _tier_label_value(record)
    return None


def _values_consistent(
    value_a: Any,
    value_b: Any,
    *,
    label_type: str,
    tier_tolerance: int,
) -> bool | None:
    """Return whether two label values are consistent.

    Returns ``None`` when consistency cannot be determined (e.g. either
    value is missing or the label type is unsupported).
    """
    if value_a is None or value_b is None:
        return None
    if label_type == "human_pairwise_preference":
        return value_a == value_b
    if label_type == "human_tier":
        return abs(value_a - value_b) <= tier_tolerance
    return None


def compute_retest_pairs(
    records: list[dict[str, Any]],
    *,
    tier_tolerance: int = DEFAULT_TIER_AGREEMENT_TOLERANCE,
) -> list[dict[str, Any]]:
    """Trace re-annotation pairs via ``supersedes_decision_id``.

    A retest pair is ``(original, retest)`` where:

    - ``original`` is a confirmed record.
    - ``retest`` is a confirmed record whose ``supersedes_decision_id``
      points at ``original``.
    - Both records share the same ``label_type``.

    Revoked retests do not produce retest pairs — a revoke is a
    withdrawal, not a re-annotation. Pairs are sorted by
    ``retest_recorded_at`` for deterministic output.
    """
    confirmed_by_id: dict[str, dict[str, Any]] = {
        r["decision_id"]: r
        for r in records
        if r.get("action") == "confirmed"
    }

    pairs: list[dict[str, Any]] = []
    for retest in records:
        if retest.get("action") != "confirmed":
            continue
        target_id = retest.get("supersedes_decision_id")
        if not isinstance(target_id, str) or not target_id:
            continue
        original = confirmed_by_id.get(target_id)
        if original is None:
            continue
        if original.get("label_type") != retest.get("label_type"):
            continue

        original_value = _label_value(original)
        retest_value = _label_value(retest)
        consistent = _values_consistent(
            original_value,
            retest_value,
            label_type=retest.get("label_type", ""),
            tier_tolerance=tier_tolerance,
        )

        original_ts = _parse_iso8601(original.get("recorded_at"))
        retest_ts = _parse_iso8601(retest.get("recorded_at"))
        days_between: int | None = None
        if original_ts is not None and retest_ts is not None:
            delta = (retest_ts - original_ts).total_seconds()
            days_between = max(0, int(delta // 86400))

        pairs.append({
            "original_decision_id": original["decision_id"],
            "retest_decision_id": retest["decision_id"],
            "label_type": retest.get("label_type"),
            "original_value": original_value,
            "retest_value": retest_value,
            "consistent": consistent,
            "days_between": days_between,
            "same_decided_by": (
                original.get("decided_by") == retest.get("decided_by")
            ),
            "original_decided_by": original.get("decided_by"),
            "retest_decided_by": retest.get("decided_by"),
            "original_recorded_at": original.get("recorded_at"),
            "retest_recorded_at": retest.get("recorded_at"),
        })

    pairs.sort(key=lambda p: (p["retest_recorded_at"] or "", p["retest_decision_id"]))
    return pairs


def compute_annotator_agreement(
    records: list[dict[str, Any]],
    *,
    tier_tolerance: int = DEFAULT_TIER_AGREEMENT_TOLERANCE,
) -> list[dict[str, Any]]:
    """Group confirmed labels by business key and report annotator agreement.

    Only groups with at least 2 distinct ``decided_by`` values are
    reported. Superseded confirmed records are included (they represent
    prior annotations); revoked records are excluded.
    """
    confirmed = [r for r in records if r.get("action") == "confirmed"]

    groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for r in confirmed:
        key = _pairwise_business_key(r) or _tier_business_key(r)
        if key is None:
            continue
        groups.setdefault(key, []).append(r)

    agreement_groups: list[dict[str, Any]] = []
    for key, group in groups.items():
        decided_by_values = {r.get("decided_by") for r in group}
        if len(decided_by_values) < 2:
            continue  # Single annotator: no agreement signal.

        label_type = group[0].get("label_type", "")
        values = [
            (_label_value(r), r.get("decided_by"), r.get("recorded_at"))
            for r in group
        ]

        non_none_values = [v for v, _, _ in values if v is not None]
        consistent: bool | None = None
        if label_type == "human_pairwise_preference" and non_none_values:
            consistent = len(set(non_none_values)) == 1
        elif label_type == "human_tier" and non_none_values:
            consistent = (
                max(non_none_values) - min(non_none_values) <= tier_tolerance
            )

        agreement_groups.append({
            "label_type": label_type,
            "business_key_parts": list(key),
            "annotators": sorted(str(d) for d in decided_by_values if d),
            "annotation_count": len(group),
            "values": [
                {"decided_by": d, "value": v, "recorded_at": ts}
                for v, d, ts in values
            ],
            "consistent": consistent,
        })

    agreement_groups.sort(
        key=lambda g: (g["label_type"], g["business_key_parts"])
    )
    return agreement_groups


def build_stability_report(
    records: list[dict[str, Any]],
    *,
    tier_tolerance: int = DEFAULT_TIER_AGREEMENT_TOLERANCE,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the PRS-LABEL-006 label stability report.

    Returns a read-only diagnostic report with two sections:

    - ``retest_pairs``: re-annotation pairs traced via
      ``supersedes_decision_id``.
    - ``annotator_agreement``: groups with multiple distinct annotators.

    The report does not participate in the fail-closed verdict —
    stability metrics are signals for the maintainer, not gates. An
    empty ledger returns 0/0/0/0 honestly.
    """
    retest_pairs = compute_retest_pairs(records, tier_tolerance=tier_tolerance)
    agreement_groups = compute_annotator_agreement(
        records, tier_tolerance=tier_tolerance
    )

    consistent_retest = sum(
        1 for p in retest_pairs if p["consistent"] is True
    )
    consistent_agreement = sum(
        1 for g in agreement_groups if g["consistent"] is True
    )

    retest_rate: float | None = (
        consistent_retest / len(retest_pairs) if retest_pairs else None
    )
    agreement_rate: float | None = (
        consistent_agreement / len(agreement_groups)
        if agreement_groups
        else None
    )

    active = active_labels(records)
    active_by_decided_by: dict[str, int] = {}
    for r in active:
        d = str(r.get("decided_by", ""))
        active_by_decided_by[d] = active_by_decided_by.get(d, 0) + 1

    return {
        "schema": LABEL_STABILITY_SCHEMA,
        "schema_version": LABEL_STABILITY_VERSION,
        "status": "ok",
        "generated_at": _now(),
        "summary": {
            "total_retest_pairs": len(retest_pairs),
            "consistent_retest_pairs": consistent_retest,
            "retest_consistency_rate": retest_rate,
            "total_agreement_groups": len(agreement_groups),
            "consistent_agreement_groups": consistent_agreement,
            "agreement_rate": agreement_rate,
            "active_label_count": len(active),
            "active_by_decided_by": active_by_decided_by,
        },
        "retest_pairs": retest_pairs,
        "annotator_agreement": agreement_groups,
        "thresholds": {
            "tier_agreement_tolerance": tier_tolerance,
        },
        "limitations": [
            "Stability metrics are signals for the maintainer, not gates.",
            "retest_pairs only trace supersedes_decision_id chains; "
            "independent re-annotations without supersedes are not detected.",
            "annotator_agreement only reports groups with >= 2 distinct "
            "decided_by values; a single annotator produces no agreement "
            "signal.",
            "An empty ledger returns 0/0/0/0 honestly; absence of retest "
            "or agreement signals does not mean labels are correct or "
            "supervision-ready.",
            "The report does not prove annotators were truly blind or that "
            "evidence is correct; it only compares label values structurally.",
        ],
    }


__all__ = [
    "DEFAULT_TIER_AGREEMENT_TOLERANCE",
    "LABEL_STABILITY_SCHEMA",
    "LABEL_STABILITY_VERSION",
    "build_stability_report",
    "compute_annotator_agreement",
    "compute_retest_pairs",
]
