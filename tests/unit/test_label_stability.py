"""Tests for the PRS-LABEL-006 label stability diagnostic (PRS-3 slice 3).

Covers:

- ``_pairwise_label_value`` order-independent normalisation:
  (a, b, prefer a) and (b, a, prefer b) both map to ``first``; tie
  preserved; self-comparison → tie; missing fields → None.
- ``_tier_label_value``: returns int tier, rejects bool, rejects
  non-tier label types.
- ``_values_consistent``: pairwise equality; tier tolerance; None
  values → None; unknown label type → None.
- ``compute_retest_pairs``:
  - empty records → []
  - single confirmed (no supersedes) → []
  - confirmed superseding another confirmed → one pair
  - consistent when label values match (pairwise same direction)
  - inconsistent when label values differ (pairwise opposite)
  - consistent when tier values within tolerance
  - inconsistent when tier values outside tolerance
  - revoked retest excluded
  - different label_type excluded
  - days_between computed correctly
  - same_decided_by flag
  - order-independent pairwise normalisation
  - missing original (orphan supersedes) → no pair
- ``compute_annotator_agreement``:
  - empty records → []
  - single annotator → [] (no agreement signal)
  - two annotators same value → consistent
  - two annotators different value → inconsistent
  - tier tolerance respected
  - superseded confirmed records included
  - revoked records excluded
  - order-independent pairwise business key
- ``build_stability_report``:
  - empty ledger → status=ok, 0/0/0/0, rates None
  - schema and schema_version present
  - summary counts consistent with queues
  - thresholds echoed
  - limitations non-empty
  - JSON-serialisable
  - active_label_count matches active_labels
  - active_by_decided_by distribution
  - custom tier_tolerance reflected
"""

from __future__ import annotations

import json

from scoutfootball.evaluation.label_ledger import LEDGER_TYPE, LEDGER_VERSION
from scoutfootball.evaluation.label_stability import (
    DEFAULT_TIER_AGREEMENT_TOLERANCE,
    LABEL_STABILITY_SCHEMA,
    LABEL_STABILITY_VERSION,
    _pairwise_label_value,
    _tier_label_value,
    _values_consistent,
    build_stability_report,
    compute_annotator_agreement,
    compute_retest_pairs,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_COHORT_A = "0123456789abcdef"
_COHORT_B = "fedcba9876543210"
_WINDOW_1 = "2024-08-01/2025-05-31"
_PLAYER_1 = "unresolved:understat:u|1"
_PLAYER_2 = "unresolved:understat:u|2"
_PLAYER_3 = "unresolved:understat:u|3"
_UUID_A = "11111111-1111-1111-1111-111111111111"
_UUID_B = "22222222-2222-2222-2222-222222222222"
_UUID_C = "33333333-3333-3333-3333-333333333333"
_UUID_D = "44444444-4444-4444-4444-444444444444"
_LONG_EVIDENCE = (
    "Player A had 2.3 interceptions/90 vs Player B 1.1; A was "
    "visibly stronger in aerial duels and progressive carries."
)


def _pairwise(
    decision_id: str,
    *,
    player_a: str = _PLAYER_1,
    player_b: str = _PLAYER_2,
    preferred: str = "a",
    cohort: str = _COHORT_A,
    role: str = "CB",
    season: str = "2425",
    window: str = _WINDOW_1,
    confidence: str = "high",
    evidence: str = _LONG_EVIDENCE,
    recorded_at: str = "2026-07-31T00:00:00Z",
    revision: int = 1,
    action: str = "confirmed",
    supersedes: str | None = None,
    decided_by: str = "maintainer",
) -> dict:
    return {
        "record_type": LEDGER_TYPE,
        "record_version": LEDGER_VERSION,
        "decision_id": decision_id,
        "revision": revision,
        "recorded_at": recorded_at,
        "action": action,
        "label_type": "human_pairwise_preference",
        "cohort_hash": cohort,
        "role_family": role,
        "season_id": season,
        "observation_window": window,
        "confidence": confidence,
        "evidence": evidence,
        "decided_by": decided_by,
        "notes": "",
        "blind": True,
        "supersedes_decision_id": supersedes,
        "player_a_id": player_a,
        "player_b_id": player_b,
        "preferred_player": preferred,
    }


def _tier(
    decision_id: str,
    *,
    player: str = _PLAYER_3,
    tier: int = 2,
    cohort: str = _COHORT_A,
    role: str = "ST",
    season: str = "2425",
    window: str = _WINDOW_1,
    confidence: str = "medium",
    evidence: str = _LONG_EVIDENCE,
    recorded_at: str = "2026-07-31T00:00:00Z",
    revision: int = 1,
    action: str = "confirmed",
    supersedes: str | None = None,
    decided_by: str = "maintainer",
) -> dict:
    return {
        "record_type": LEDGER_TYPE,
        "record_version": LEDGER_VERSION,
        "decision_id": decision_id,
        "revision": revision,
        "recorded_at": recorded_at,
        "action": action,
        "label_type": "human_tier",
        "cohort_hash": cohort,
        "role_family": role,
        "season_id": season,
        "observation_window": window,
        "confidence": confidence,
        "evidence": evidence,
        "decided_by": decided_by,
        "notes": "",
        "blind": True,
        "supersedes_decision_id": supersedes,
        "canonical_player_id": player,
        "tier": tier,
    }


def _revoke(
    decision_id: str,
    target_decision_id: str,
    *,
    label_type: str = "human_pairwise_preference",
    recorded_at: str = "2026-07-31T01:00:00Z",
    revision: int = 2,
) -> dict:
    return {
        "record_type": LEDGER_TYPE,
        "record_version": LEDGER_VERSION,
        "decision_id": decision_id,
        "revision": revision,
        "recorded_at": recorded_at,
        "action": "revoked",
        "label_type": label_type,
        "cohort_hash": _COHORT_A,
        "role_family": "CB",
        "season_id": "2425",
        "observation_window": _WINDOW_1,
        "confidence": "low",
        "evidence": "Re-review showed the original label was wrong.",
        "decided_by": "maintainer",
        "notes": "",
        "blind": False,
        "supersedes_decision_id": target_decision_id,
    }


# ---------------------------------------------------------------------------
# _pairwise_label_value
# ---------------------------------------------------------------------------


class TestPairwiseLabelValue:
    def test_prefer_a_when_a_lt_b_maps_to_first(self) -> None:
        record = _pairwise(_UUID_A, player_a=_PLAYER_1, player_b=_PLAYER_2, preferred="a")
        assert _pairwise_label_value(record) == "first"

    def test_prefer_b_when_a_lt_b_maps_to_second(self) -> None:
        record = _pairwise(_UUID_A, player_a=_PLAYER_1, player_b=_PLAYER_2, preferred="b")
        assert _pairwise_label_value(record) == "second"

    def test_prefer_a_when_b_lt_a_maps_to_second(self) -> None:
        # (b, a, prefer a) — b < a so prefer-a means prefer the second
        # element in sorted order.
        record = _pairwise(_UUID_A, player_a=_PLAYER_2, player_b=_PLAYER_1, preferred="a")
        assert _pairwise_label_value(record) == "second"

    def test_prefer_b_when_b_lt_a_maps_to_first(self) -> None:
        record = _pairwise(_UUID_A, player_a=_PLAYER_2, player_b=_PLAYER_1, preferred="b")
        assert _pairwise_label_value(record) == "first"

    def test_order_independence(self) -> None:
        # (P1, P2, prefer a) and (P2, P1, prefer b) both prefer the
        # physically same player (P1), so both map to "first".
        r1 = _pairwise(_UUID_A, player_a=_PLAYER_1, player_b=_PLAYER_2, preferred="a")
        r2 = _pairwise(_UUID_B, player_a=_PLAYER_2, player_b=_PLAYER_1, preferred="b")
        assert _pairwise_label_value(r1) == _pairwise_label_value(r2) == "first"

    def test_tie_preserved(self) -> None:
        record = _pairwise(_UUID_A, preferred="tie")
        assert _pairwise_label_value(record) == "tie"

    def test_self_comparison_returns_tie(self) -> None:
        record = _pairwise(_UUID_A, player_a=_PLAYER_1, player_b=_PLAYER_1, preferred="a")
        assert _pairwise_label_value(record) == "tie"

    def test_missing_player_a_returns_none(self) -> None:
        record = _pairwise(_UUID_A)
        record.pop("player_a_id")
        assert _pairwise_label_value(record) is None

    def test_missing_preferred_returns_none(self) -> None:
        record = _pairwise(_UUID_A)
        record.pop("preferred_player")
        assert _pairwise_label_value(record) is None

    def test_invalid_preferred_returns_none(self) -> None:
        record = _pairwise(_UUID_A, preferred="invalid")
        assert _pairwise_label_value(record) is None


# ---------------------------------------------------------------------------
# _tier_label_value
# ---------------------------------------------------------------------------


class TestTierLabelValue:
    def test_valid_tier_returns_int(self) -> None:
        record = _tier(_UUID_A, tier=3)
        assert _tier_label_value(record) == 3

    def test_non_tier_label_type_returns_none(self) -> None:
        record = _pairwise(_UUID_A)
        assert _tier_label_value(record) is None

    def test_bool_tier_rejected(self) -> None:
        record = _tier(_UUID_A, tier=2)
        record["tier"] = True  # bool is subclass of int
        assert _tier_label_value(record) is None

    def test_missing_tier_returns_none(self) -> None:
        record = _tier(_UUID_A)
        record.pop("tier")
        assert _tier_label_value(record) is None


# ---------------------------------------------------------------------------
# _values_consistent
# ---------------------------------------------------------------------------


class TestValuesConsistent:
    def test_pairwise_same_value_consistent(self) -> None:
        assert _values_consistent(
            "first", "first", label_type="human_pairwise_preference", tier_tolerance=1
        ) is True

    def test_pairwise_different_value_inconsistent(self) -> None:
        assert _values_consistent(
            "first", "second", label_type="human_pairwise_preference", tier_tolerance=1
        ) is False

    def test_tier_within_tolerance_consistent(self) -> None:
        assert _values_consistent(
            2, 3, label_type="human_tier", tier_tolerance=1
        ) is True

    def test_tier_outside_tolerance_inconsistent(self) -> None:
        assert _values_consistent(
            1, 4, label_type="human_tier", tier_tolerance=1
        ) is False

    def test_none_value_returns_none(self) -> None:
        assert _values_consistent(
            None, "first", label_type="human_pairwise_preference", tier_tolerance=1
        ) is None

    def test_unknown_label_type_returns_none(self) -> None:
        assert _values_consistent(
            "x", "y", label_type="unknown_type", tier_tolerance=1
        ) is None


# ---------------------------------------------------------------------------
# compute_retest_pairs
# ---------------------------------------------------------------------------


class TestComputeRetestPairs:
    def test_empty_records(self) -> None:
        assert compute_retest_pairs([]) == []

    def test_single_confirmed_no_supersedes(self) -> None:
        records = [_pairwise(_UUID_A)]
        assert compute_retest_pairs(records) == []

    def test_confirmed_superseding_confirmed_produces_pair(self) -> None:
        original = _pairwise(_UUID_A, recorded_at="2026-07-01T00:00:00Z", revision=1)
        retest = _pairwise(
            _UUID_B,
            supersedes=_UUID_A,
            recorded_at="2026-07-31T00:00:00Z",
            revision=2,
        )
        pairs = compute_retest_pairs([original, retest])
        assert len(pairs) == 1
        p = pairs[0]
        assert p["original_decision_id"] == _UUID_A
        assert p["retest_decision_id"] == _UUID_B
        assert p["label_type"] == "human_pairwise_preference"

    def test_consistent_pairwise_same_direction(self) -> None:
        original = _pairwise(_UUID_A, preferred="a", recorded_at="2026-07-01T00:00:00Z", revision=1)
        retest = _pairwise(
            _UUID_B, preferred="a", supersedes=_UUID_A,
            recorded_at="2026-07-31T00:00:00Z", revision=2,
        )
        pairs = compute_retest_pairs([original, retest])
        assert pairs[0]["consistent"] is True
        assert pairs[0]["original_value"] == "first"
        assert pairs[0]["retest_value"] == "first"

    def test_inconsistent_pairwise_opposite_direction(self) -> None:
        original = _pairwise(_UUID_A, preferred="a", recorded_at="2026-07-01T00:00:00Z", revision=1)
        retest = _pairwise(
            _UUID_B, preferred="b", supersedes=_UUID_A,
            recorded_at="2026-07-31T00:00:00Z", revision=2,
        )
        pairs = compute_retest_pairs([original, retest])
        assert pairs[0]["consistent"] is False

    def test_order_independent_pairwise_consistency(self) -> None:
        # Original: (P1, P2, prefer a) → "first"
        # Retest: (P2, P1, prefer b) → "first" (same physical preference)
        original = _pairwise(
            _UUID_A, player_a=_PLAYER_1, player_b=_PLAYER_2, preferred="a",
            recorded_at="2026-07-01T00:00:00Z", revision=1,
        )
        retest = _pairwise(
            _UUID_B, player_a=_PLAYER_2, player_b=_PLAYER_1, preferred="b",
            supersedes=_UUID_A, recorded_at="2026-07-31T00:00:00Z", revision=2,
        )
        pairs = compute_retest_pairs([original, retest])
        assert pairs[0]["consistent"] is True

    def test_consistent_tier_within_tolerance(self) -> None:
        original = _tier(_UUID_A, tier=2, recorded_at="2026-07-01T00:00:00Z", revision=1)
        retest = _tier(
            _UUID_B, tier=3, supersedes=_UUID_A,
            recorded_at="2026-07-31T00:00:00Z", revision=2,
        )
        pairs = compute_retest_pairs([original, retest])
        assert pairs[0]["consistent"] is True

    def test_inconsistent_tier_outside_tolerance(self) -> None:
        original = _tier(_UUID_A, tier=1, recorded_at="2026-07-01T00:00:00Z", revision=1)
        retest = _tier(
            _UUID_B, tier=4, supersedes=_UUID_A,
            recorded_at="2026-07-31T00:00:00Z", revision=2,
        )
        pairs = compute_retest_pairs([original, retest])
        assert pairs[0]["consistent"] is False

    def test_custom_tier_tolerance(self) -> None:
        original = _tier(_UUID_A, tier=1, recorded_at="2026-07-01T00:00:00Z", revision=1)
        retest = _tier(
            _UUID_B, tier=4, supersedes=_UUID_A,
            recorded_at="2026-07-31T00:00:00Z", revision=2,
        )
        # tolerance=3 → |1-4|=3 <= 3 → consistent
        pairs = compute_retest_pairs([original, retest], tier_tolerance=3)
        assert pairs[0]["consistent"] is True

    def test_revoked_retest_excluded(self) -> None:
        original = _pairwise(_UUID_A, recorded_at="2026-07-01T00:00:00Z", revision=1)
        revoke = _revoke(_UUID_B, _UUID_A, recorded_at="2026-07-31T00:00:00Z", revision=2)
        pairs = compute_retest_pairs([original, revoke])
        assert pairs == []

    def test_different_label_type_excluded(self) -> None:
        # Original is pairwise, retest is tier — supersedes points at
        # original but label types differ, so no pair.
        original = _pairwise(_UUID_A, recorded_at="2026-07-01T00:00:00Z", revision=1)
        retest = _tier(
            _UUID_B, supersedes=_UUID_A,
            recorded_at="2026-07-31T00:00:00Z", revision=2,
        )
        pairs = compute_retest_pairs([original, retest])
        assert pairs == []

    def test_days_between_computed(self) -> None:
        original = _pairwise(_UUID_A, recorded_at="2026-07-01T00:00:00Z", revision=1)
        retest = _pairwise(
            _UUID_B, supersedes=_UUID_A,
            recorded_at="2026-07-31T00:00:00Z", revision=2,
        )
        pairs = compute_retest_pairs([original, retest])
        assert pairs[0]["days_between"] == 30

    def test_same_decided_by_flag(self) -> None:
        original = _pairwise(
            _UUID_A, decided_by="alice",
            recorded_at="2026-07-01T00:00:00Z", revision=1,
        )
        retest = _pairwise(
            _UUID_B, decided_by="alice", supersedes=_UUID_A,
            recorded_at="2026-07-31T00:00:00Z", revision=2,
        )
        pairs = compute_retest_pairs([original, retest])
        assert pairs[0]["same_decided_by"] is True
        assert pairs[0]["original_decided_by"] == "alice"
        assert pairs[0]["retest_decided_by"] == "alice"

    def test_different_decided_by_flag(self) -> None:
        original = _pairwise(
            _UUID_A, decided_by="alice",
            recorded_at="2026-07-01T00:00:00Z", revision=1,
        )
        retest = _pairwise(
            _UUID_B, decided_by="bob", supersedes=_UUID_A,
            recorded_at="2026-07-31T00:00:00Z", revision=2,
        )
        pairs = compute_retest_pairs([original, retest])
        assert pairs[0]["same_decided_by"] is False

    def test_orphan_supersedes_no_pair(self) -> None:
        # Retest points at a decision_id that doesn't exist.
        retest = _pairwise(
            _UUID_B, supersedes=_UUID_A,
            recorded_at="2026-07-31T00:00:00Z", revision=1,
        )
        pairs = compute_retest_pairs([retest])
        assert pairs == []

    def test_multiple_pairs(self) -> None:
        original_1 = _pairwise(
            _UUID_A, recorded_at="2026-07-01T00:00:00Z", revision=1,
        )
        retest_1 = _pairwise(
            _UUID_B, supersedes=_UUID_A,
            recorded_at="2026-07-15T00:00:00Z", revision=2,
        )
        original_2 = _tier(
            _UUID_C, tier=2, recorded_at="2026-07-05T00:00:00Z", revision=3,
        )
        retest_2 = _tier(
            _UUID_D, tier=3, supersedes=_UUID_C,
            recorded_at="2026-07-20T00:00:00Z", revision=4,
        )
        pairs = compute_retest_pairs([original_1, retest_1, original_2, retest_2])
        assert len(pairs) == 2
        # Sorted by retest_recorded_at: retest_1 (07-15) before retest_2 (07-20)
        assert pairs[0]["retest_decision_id"] == _UUID_B
        assert pairs[1]["retest_decision_id"] == _UUID_D


# ---------------------------------------------------------------------------
# compute_annotator_agreement
# ---------------------------------------------------------------------------


class TestComputeAnnotatorAgreement:
    def test_empty_records(self) -> None:
        assert compute_annotator_agreement([]) == []

    def test_single_annotator_no_group(self) -> None:
        records = [
            _pairwise(_UUID_A, decided_by="alice"),
            _pairwise(_UUID_B, decided_by="alice", preferred="b"),
        ]
        # Same business key, same annotator → no agreement group.
        assert compute_annotator_agreement(records) == []

    def test_two_annotators_same_value_consistent(self) -> None:
        records = [
            _pairwise(_UUID_A, decided_by="alice", preferred="a"),
            _pairwise(_UUID_B, decided_by="bob", preferred="a"),
        ]
        groups = compute_annotator_agreement(records)
        assert len(groups) == 1
        g = groups[0]
        assert g["annotators"] == ["alice", "bob"]
        assert g["consistent"] is True
        assert g["annotation_count"] == 2

    def test_two_annotators_different_value_inconsistent(self) -> None:
        records = [
            _pairwise(_UUID_A, decided_by="alice", preferred="a"),
            _pairwise(_UUID_B, decided_by="bob", preferred="b"),
        ]
        groups = compute_annotator_agreement(records)
        assert len(groups) == 1
        assert groups[0]["consistent"] is False

    def test_order_independent_pairwise_business_key(self) -> None:
        # (P1, P2, prefer a) by alice and (P2, P1, prefer b) by bob
        # both prefer P1 → consistent.
        records = [
            _pairwise(
                _UUID_A, player_a=_PLAYER_1, player_b=_PLAYER_2,
                preferred="a", decided_by="alice",
            ),
            _pairwise(
                _UUID_B, player_a=_PLAYER_2, player_b=_PLAYER_1,
                preferred="b", decided_by="bob",
            ),
        ]
        groups = compute_annotator_agreement(records)
        assert len(groups) == 1
        assert groups[0]["consistent"] is True

    def test_tier_within_tolerance_consistent(self) -> None:
        records = [
            _tier(_UUID_A, tier=2, decided_by="alice"),
            _tier(_UUID_B, tier=3, decided_by="bob"),
        ]
        groups = compute_annotator_agreement(records)
        assert len(groups) == 1
        assert groups[0]["consistent"] is True

    def test_tier_outside_tolerance_inconsistent(self) -> None:
        records = [
            _tier(_UUID_A, tier=1, decided_by="alice"),
            _tier(_UUID_B, tier=4, decided_by="bob"),
        ]
        groups = compute_annotator_agreement(records)
        assert len(groups) == 1
        assert groups[0]["consistent"] is False

    def test_custom_tier_tolerance(self) -> None:
        records = [
            _tier(_UUID_A, tier=1, decided_by="alice"),
            _tier(_UUID_B, tier=4, decided_by="bob"),
        ]
        groups = compute_annotator_agreement(records, tier_tolerance=3)
        assert groups[0]["consistent"] is True

    def test_different_business_keys_separate_groups(self) -> None:
        records = [
            _pairwise(_UUID_A, decided_by="alice", preferred="a"),
            _pairwise(
                _UUID_B, player_b=_PLAYER_3, decided_by="bob", preferred="a",
            ),
        ]
        groups = compute_annotator_agreement(records)
        # Different player_b → different business keys → no multi-annotator
        # group (each key has only one annotator).
        assert groups == []

    def test_superseded_confirmed_included(self) -> None:
        # Original by alice, superseded by retest by bob — both confirmed,
        # both included in agreement analysis.
        original = _pairwise(
            _UUID_A, decided_by="alice", preferred="a",
            recorded_at="2026-07-01T00:00:00Z", revision=1,
        )
        retest = _pairwise(
            _UUID_B, decided_by="bob", preferred="a", supersedes=_UUID_A,
            recorded_at="2026-07-31T00:00:00Z", revision=2,
        )
        groups = compute_annotator_agreement([original, retest])
        assert len(groups) == 1
        assert groups[0]["annotation_count"] == 2

    def test_revoked_excluded(self) -> None:
        original = _pairwise(
            _UUID_A, decided_by="alice", preferred="a",
            recorded_at="2026-07-01T00:00:00Z", revision=1,
        )
        revoke = _revoke(_UUID_B, _UUID_A, recorded_at="2026-07-31T00:00:00Z", revision=2)
        groups = compute_annotator_agreement([original, revoke])
        # Only one confirmed record (original) → single annotator → no group.
        assert groups == []

    def test_different_cohort_separate_groups(self) -> None:
        records = [
            _pairwise(_UUID_A, cohort=_COHORT_A, decided_by="alice"),
            _pairwise(_UUID_B, cohort=_COHORT_B, decided_by="bob"),
        ]
        groups = compute_annotator_agreement(records)
        assert groups == []

    def test_three_annotators_mixed_values(self) -> None:
        records = [
            _pairwise(_UUID_A, decided_by="alice", preferred="a"),
            _pairwise(_UUID_B, decided_by="bob", preferred="a"),
            _pairwise(_UUID_C, decided_by="carol", preferred="b"),
        ]
        groups = compute_annotator_agreement(records)
        assert len(groups) == 1
        assert groups[0]["annotation_count"] == 3
        assert groups[0]["consistent"] is False  # not all same


# ---------------------------------------------------------------------------
# build_stability_report
# ---------------------------------------------------------------------------


class TestBuildStabilityReport:
    def test_empty_ledger(self) -> None:
        report = build_stability_report([])
        assert report["status"] == "ok"
        assert report["summary"]["total_retest_pairs"] == 0
        assert report["summary"]["consistent_retest_pairs"] == 0
        assert report["summary"]["retest_consistency_rate"] is None
        assert report["summary"]["total_agreement_groups"] == 0
        assert report["summary"]["consistent_agreement_groups"] == 0
        assert report["summary"]["agreement_rate"] is None
        assert report["summary"]["active_label_count"] == 0
        assert report["retest_pairs"] == []
        assert report["annotator_agreement"] == []

    def test_schema_and_version(self) -> None:
        report = build_stability_report([])
        assert report["schema"] == LABEL_STABILITY_SCHEMA
        assert report["schema_version"] == LABEL_STABILITY_VERSION

    def test_generated_at_present(self) -> None:
        report = build_stability_report([])
        assert "generated_at" in report
        assert isinstance(report["generated_at"], str)

    def test_thresholds_echoed(self) -> None:
        report = build_stability_report([], tier_tolerance=2)
        assert report["thresholds"]["tier_agreement_tolerance"] == 2

    def test_default_threshold(self) -> None:
        report = build_stability_report([])
        assert (
            report["thresholds"]["tier_agreement_tolerance"]
            == DEFAULT_TIER_AGREEMENT_TOLERANCE
        )

    def test_limitations_non_empty(self) -> None:
        report = build_stability_report([])
        assert len(report["limitations"]) > 0

    def test_json_serialisable(self) -> None:
        original = _pairwise(
            _UUID_A, decided_by="alice", preferred="a",
            recorded_at="2026-07-01T00:00:00Z", revision=1,
        )
        retest = _pairwise(
            _UUID_B, decided_by="bob", preferred="a", supersedes=_UUID_A,
            recorded_at="2026-07-31T00:00:00Z", revision=2,
        )
        report = build_stability_report([original, retest])
        json.dumps(report)

    def test_summary_counts_consistent(self) -> None:
        original = _pairwise(
            _UUID_A, decided_by="alice", preferred="a",
            recorded_at="2026-07-01T00:00:00Z", revision=1,
        )
        retest = _pairwise(
            _UUID_B, decided_by="bob", preferred="a", supersedes=_UUID_A,
            recorded_at="2026-07-31T00:00:00Z", revision=2,
        )
        report = build_stability_report([original, retest])
        s = report["summary"]
        assert s["total_retest_pairs"] == len(report["retest_pairs"])
        assert s["total_agreement_groups"] == len(report["annotator_agreement"])
        assert s["consistent_retest_pairs"] == sum(
            1 for p in report["retest_pairs"] if p["consistent"] is True
        )
        assert s["consistent_agreement_groups"] == sum(
            1 for g in report["annotator_agreement"] if g["consistent"] is True
        )

    def test_retest_consistency_rate(self) -> None:
        # Two retest pairs: one consistent, one inconsistent.
        original_1 = _pairwise(
            _UUID_A, preferred="a", decided_by="alice",
            recorded_at="2026-07-01T00:00:00Z", revision=1,
        )
        retest_1 = _pairwise(
            _UUID_B, preferred="a", supersedes=_UUID_A, decided_by="alice",
            recorded_at="2026-07-15T00:00:00Z", revision=2,
        )
        original_2 = _pairwise(
            _UUID_C, preferred="a", decided_by="alice",
            recorded_at="2026-07-02T00:00:00Z", revision=3,
        )
        retest_2 = _pairwise(
            _UUID_D, preferred="b", supersedes=_UUID_C, decided_by="alice",
            recorded_at="2026-07-20T00:00:00Z", revision=4,
        )
        report = build_stability_report([original_1, retest_1, original_2, retest_2])
        s = report["summary"]
        assert s["total_retest_pairs"] == 2
        assert s["consistent_retest_pairs"] == 1
        assert s["retest_consistency_rate"] == 0.5

    def test_agreement_rate(self) -> None:
        # Two agreement groups: one consistent, one inconsistent.
        records = [
            _pairwise(_UUID_A, decided_by="alice", preferred="a"),
            _pairwise(_UUID_B, decided_by="bob", preferred="a"),
            _tier(_UUID_C, tier=1, decided_by="alice", player=_PLAYER_1),
            _tier(_UUID_D, tier=4, decided_by="bob", player=_PLAYER_1),
        ]
        report = build_stability_report(records)
        s = report["summary"]
        assert s["total_agreement_groups"] == 2
        assert s["consistent_agreement_groups"] == 1
        assert s["agreement_rate"] == 0.5

    def test_active_label_count(self) -> None:
        original = _pairwise(
            _UUID_A, recorded_at="2026-07-01T00:00:00Z", revision=1,
        )
        retest = _pairwise(
            _UUID_B, supersedes=_UUID_A, preferred="b",
            recorded_at="2026-07-31T00:00:00Z", revision=2,
        )
        report = build_stability_report([original, retest])
        # retest supersedes original → only retest is active.
        assert report["summary"]["active_label_count"] == 1

    def test_active_by_decided_by(self) -> None:
        records = [
            _pairwise(_UUID_A, decided_by="alice"),
            _tier(_UUID_B, decided_by="bob", player=_PLAYER_3),
        ]
        report = build_stability_report(records)
        abd = report["summary"]["active_by_decided_by"]
        assert abd.get("alice") == 1
        assert abd.get("bob") == 1

    def test_custom_tier_tolerance_reflected(self) -> None:
        original = _tier(
            _UUID_A, tier=1, decided_by="alice",
            recorded_at="2026-07-01T00:00:00Z", revision=1,
        )
        retest = _tier(
            _UUID_B, tier=4, supersedes=_UUID_A, decided_by="alice",
            recorded_at="2026-07-31T00:00:00Z", revision=2,
        )
        report = build_stability_report([original, retest], tier_tolerance=3)
        assert report["thresholds"]["tier_agreement_tolerance"] == 3
        assert report["retest_pairs"][0]["consistent"] is True
