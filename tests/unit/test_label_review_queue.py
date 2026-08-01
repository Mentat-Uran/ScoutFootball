"""Tests for the PRS-LABEL-005 label review queue diagnostic (PRS-3 slice 2).

Covers:

- ``_parse_recorded_at`` accepts ISO-8601 with trailing Z, with offset,
  naive (treated as UTC); rejects garbage and empty.
- ``_normalise_pairwise_pair`` maps (A vs B, prefer a) and (B vs A,
  prefer b) to the same (sorted_pair, "first"); preserves tie; handles
  self-comparison defensively.
- ``detect_pairwise_conflicts``:
  - no conflict when only one preference direction
  - conflict when prefer-a and prefer-b coexist on same pair+window
  - (A vs B, prefer a) vs (B vs A, prefer b) NOT a conflict (same)
  - (A vs B, prefer a) vs (B vs A, prefer a) IS a conflict (contradiction)
  - tie does not conflict with prefer-a
  - different observation_window => no conflict
  - different cohort_hash => no conflict
  - revoked records excluded from conflict detection
  - conflict group includes all decision_ids in the group (incl. tie)
- ``detect_tier_conflicts``:
  - no conflict when span < threshold
  - conflict when span >= threshold (default 2)
  - custom threshold respected
  - different player => no conflict
  - different observation_window => no conflict
- ``low_confidence_queue``:
  - confidence=low enters queue
  - evidence < min_chars enters queue (even if confidence=high)
  - both reasons can coexist
  - custom evidence_min_chars respected
  - revoked records excluded
- ``retest_queue``:
  - aged records enter queue
  - young records do not
  - custom max_age_days respected
  - bad recorded_at skipped, counted in skipped_count
  - queue sorted oldest-first
  - ``now`` parameter respected for deterministic tests
- ``build_review_queue``:
  - empty ledger => status=ok, all queues empty
  - status=review_needed when any queue non-empty
  - schema and schema_version present
  - parameters echoed in report
  - summary counts consistent with queues
  - conflict_decision_ids_count deduplicates across pairwise+tier
  - limitations list non-empty
  - JSON-serialisable
  - active_label_count matches active_labels length
  - revoked records do not contribute to any queue
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from scoutfootball.evaluation.label_ledger import LEDGER_TYPE, LEDGER_VERSION
from scoutfootball.evaluation.label_review_queue import (
    DEFAULT_EVIDENCE_MIN_CHARS,
    DEFAULT_MAX_AGE_DAYS,
    DEFAULT_TIER_CONFLICT_THRESHOLD,
    REVIEW_QUEUE_SCHEMA,
    REVIEW_QUEUE_SCHEMA_VERSION,
    _normalise_pairwise_pair,
    _parse_recorded_at,
    build_review_queue,
    detect_pairwise_conflicts,
    detect_tier_conflicts,
    low_confidence_queue,
    retest_queue,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_COHORT_A = "0123456789abcdef"
_COHORT_B = "fedcba9876543210"
_WINDOW_1 = "2024-08-01/2025-05-31"
_WINDOW_2 = "2023-08-01/2024-05-31"
_PLAYER_1 = "unresolved:understat:u|1"
_PLAYER_2 = "unresolved:understat:u|2"
_PLAYER_3 = "unresolved:understat:u|3"
_UUID_A = "11111111-1111-1111-1111-111111111111"
_UUID_B = "22222222-2222-2222-2222-222222222222"
_UUID_C = "33333333-3333-3333-3333-333333333333"
_UUID_D = "44444444-4444-4444-4444-444444444444"
_UUID_E = "55555555-5555-5555-5555-555555555555"
_LONG_EVIDENCE = (
    "Player A had 2.3 interceptions/90 vs Player B 1.1; A was "
    "visibly stronger in aerial duels and progressive carries."
)
_SHORT_EVIDENCE = "A was better."  # < 50 chars


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
        "decided_by": "maintainer",
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
        "decided_by": "maintainer",
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
        "label_type": "human_pairwise_preference",
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
# _parse_recorded_at
# ---------------------------------------------------------------------------


class TestParseRecordedAt:
    def test_iso_with_z_suffix(self) -> None:
        dt = _parse_recorded_at("2026-07-31T12:34:56Z")
        assert dt is not None
        assert dt.tzinfo is not None
        assert dt.year == 2026 and dt.hour == 12

    def test_iso_with_offset(self) -> None:
        dt = _parse_recorded_at("2026-07-31T12:34:56+00:00")
        assert dt is not None
        assert dt.tzinfo is not None

    def test_naive_treated_as_utc(self) -> None:
        dt = _parse_recorded_at("2026-07-31T12:34:56")
        assert dt is not None
        assert dt.tzinfo is UTC

    def test_garbage_returns_none(self) -> None:
        assert _parse_recorded_at("not a date") is None

    def test_empty_returns_none(self) -> None:
        assert _parse_recorded_at("") is None

    def test_none_returns_none(self) -> None:
        assert _parse_recorded_at(None) is None  # type: ignore[arg-type]

    def test_non_string_returns_none(self) -> None:
        assert _parse_recorded_at(12345) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _normalise_pairwise_pair
# ---------------------------------------------------------------------------


class TestNormalisePairwisePair:
    def test_already_sorted_prefer_a(self) -> None:
        # player_1 < player_2, prefer a => a is first in sorted => "first"
        pair, pref = _normalise_pairwise_pair(_PLAYER_1, _PLAYER_2, "a")
        assert pair == (_PLAYER_1, _PLAYER_2)
        assert pref == "first"

    def test_already_sorted_prefer_b(self) -> None:
        pair, pref = _normalise_pairwise_pair(_PLAYER_1, _PLAYER_2, "b")
        assert pair == (_PLAYER_1, _PLAYER_2)
        assert pref == "second"

    def test_reversed_prefer_b_maps_to_first(self) -> None:
        # (player_2 vs player_1, prefer b): b=player_1=first in sorted
        pair, pref = _normalise_pairwise_pair(_PLAYER_2, _PLAYER_1, "b")
        assert pair == (_PLAYER_1, _PLAYER_2)
        assert pref == "first"

    def test_reversed_prefer_a_maps_to_second(self) -> None:
        # (player_2 vs player_1, prefer a): a=player_2=second in sorted
        pair, pref = _normalise_pairwise_pair(_PLAYER_2, _PLAYER_1, "a")
        assert pair == (_PLAYER_1, _PLAYER_2)
        assert pref == "second"

    def test_tie_preserved(self) -> None:
        pair, pref = _normalise_pairwise_pair(_PLAYER_2, _PLAYER_1, "tie")
        assert pair == (_PLAYER_1, _PLAYER_2)
        assert pref == "tie"

    def test_self_comparison_normalised_to_tie(self) -> None:
        """Self-comparison is a structural violation handled elsewhere;
        normalisation maps it to tie so it never triggers a false conflict."""
        pair, pref = _normalise_pairwise_pair(_PLAYER_1, _PLAYER_1, "a")
        assert pair == (_PLAYER_1, _PLAYER_1)
        assert pref == "tie"

    def test_round_trip_equivalence(self) -> None:
        """(A vs B, prefer a) and (B vs A, prefer b) both map to first."""
        pair1, pref1 = _normalise_pairwise_pair(_PLAYER_1, _PLAYER_2, "a")
        pair2, pref2 = _normalise_pairwise_pair(_PLAYER_2, _PLAYER_1, "b")
        assert pair1 == pair2
        assert pref1 == "first"
        assert pref2 == "first"


# ---------------------------------------------------------------------------
# detect_pairwise_conflicts
# ---------------------------------------------------------------------------


class TestDetectPairwiseConflicts:
    def test_empty_records_no_conflicts(self) -> None:
        assert detect_pairwise_conflicts([]) == []

    def test_single_record_no_conflict(self) -> None:
        records = [_pairwise(_UUID_A)]
        assert detect_pairwise_conflicts(records) == []

    def test_same_direction_no_conflict(self) -> None:
        """Two records both preferring a => no conflict."""
        records = [
            _pairwise(_UUID_A, preferred="a"),
            _pairwise(_UUID_B, preferred="a"),
        ]
        assert detect_pairwise_conflicts(records) == []

    def test_opposite_preferences_is_conflict(self) -> None:
        """prefer-a vs prefer-b on same pair+window => conflict."""
        records = [
            _pairwise(_UUID_A, preferred="a"),
            _pairwise(_UUID_B, preferred="b"),
        ]
        conflicts = detect_pairwise_conflicts(records)
        assert len(conflicts) == 1
        c = conflicts[0]
        assert c["conflict_type"] == "pairwise_preference_contradiction"
        assert c["player_pair"] == sorted([_PLAYER_1, _PLAYER_2])
        assert set(c["decision_ids"]) == {_UUID_A, _UUID_B}
        assert sorted(c["preferences_seen"]) == ["first", "second"]

    def test_reversed_pair_same_preference_not_conflict(self) -> None:
        """(A vs B, prefer a) vs (B vs A, prefer b) => both prefer A => no conflict."""
        records = [
            _pairwise(_UUID_A, player_a=_PLAYER_1, player_b=_PLAYER_2, preferred="a"),
            _pairwise(_UUID_B, player_a=_PLAYER_2, player_b=_PLAYER_1, preferred="b"),
        ]
        assert detect_pairwise_conflicts(records) == []

    def test_reversed_pair_opposite_preference_is_conflict(self) -> None:
        """(A vs B, prefer a) vs (B vs A, prefer a) => prefer A vs prefer B => conflict."""
        records = [
            _pairwise(_UUID_A, player_a=_PLAYER_1, player_b=_PLAYER_2, preferred="a"),
            _pairwise(_UUID_B, player_a=_PLAYER_2, player_b=_PLAYER_1, preferred="a"),
        ]
        conflicts = detect_pairwise_conflicts(records)
        assert len(conflicts) == 1

    def test_tie_does_not_conflict_with_preference(self) -> None:
        records = [
            _pairwise(_UUID_A, preferred="a"),
            _pairwise(_UUID_B, preferred="tie"),
        ]
        assert detect_pairwise_conflicts(records) == []

    def test_two_ties_no_conflict(self) -> None:
        records = [
            _pairwise(_UUID_A, preferred="tie"),
            _pairwise(_UUID_B, preferred="tie"),
        ]
        assert detect_pairwise_conflicts(records) == []

    def test_different_window_no_conflict(self) -> None:
        records = [
            _pairwise(_UUID_A, preferred="a", window=_WINDOW_1),
            _pairwise(_UUID_B, preferred="b", window=_WINDOW_2),
        ]
        assert detect_pairwise_conflicts(records) == []

    def test_different_cohort_no_conflict(self) -> None:
        records = [
            _pairwise(_UUID_A, preferred="a", cohort=_COHORT_A),
            _pairwise(_UUID_B, preferred="b", cohort=_COHORT_B),
        ]
        assert detect_pairwise_conflicts(records) == []

    def test_different_role_no_conflict(self) -> None:
        records = [
            _pairwise(_UUID_A, preferred="a", role="CB"),
            _pairwise(_UUID_B, preferred="b", role="ST"),
        ]
        assert detect_pairwise_conflicts(records) == []

    def test_different_season_no_conflict(self) -> None:
        records = [
            _pairwise(_UUID_A, preferred="a", season="2425"),
            _pairwise(_UUID_B, preferred="b", season="2324"),
        ]
        assert detect_pairwise_conflicts(records) == []

    def test_conflict_group_includes_tie_record(self) -> None:
        """When a conflict exists, tie records in the same group are
        included in decision_ids for full context."""
        records = [
            _pairwise(_UUID_A, preferred="a"),
            _pairwise(_UUID_B, preferred="b"),
            _pairwise(_UUID_C, preferred="tie"),
        ]
        conflicts = detect_pairwise_conflicts(records)
        assert len(conflicts) == 1
        assert set(conflicts[0]["decision_ids"]) == {_UUID_A, _UUID_B, _UUID_C}

    def test_revoked_record_excluded(self) -> None:
        """A revoked record should not participate in conflict detection."""
        records = [
            _pairwise(_UUID_A, preferred="a"),
            _pairwise(_UUID_B, preferred="b"),
            _revoke(_UUID_C, target_decision_id=_UUID_A),
        ]
        # _UUID_A is revoked, so only _UUID_B remains active => no conflict
        assert detect_pairwise_conflicts(records) == []

    def test_multiple_independent_conflicts(self) -> None:
        """Two different player pairs each with a conflict => 2 groups."""
        records = [
            _pairwise(_UUID_A, player_a=_PLAYER_1, player_b=_PLAYER_2, preferred="a"),
            _pairwise(_UUID_B, player_a=_PLAYER_1, player_b=_PLAYER_2, preferred="b"),
            _pairwise(_UUID_C, player_a=_PLAYER_1, player_b=_PLAYER_3, preferred="a"),
            _pairwise(_UUID_D, player_a=_PLAYER_1, player_b=_PLAYER_3, preferred="b"),
        ]
        conflicts = detect_pairwise_conflicts(records)
        assert len(conflicts) == 2


# ---------------------------------------------------------------------------
# detect_tier_conflicts
# ---------------------------------------------------------------------------


class TestDetectTierConflicts:
    def test_empty_records_no_conflicts(self) -> None:
        assert detect_tier_conflicts([]) == []

    def test_single_record_no_conflict(self) -> None:
        assert detect_tier_conflicts([_tier(_UUID_A)]) == []

    def test_small_span_no_conflict(self) -> None:
        """tier 2 vs tier 3 (span 1) < default threshold 2 => no conflict."""
        records = [
            _tier(_UUID_A, tier=2),
            _tier(_UUID_B, tier=3),
        ]
        assert detect_tier_conflicts(records) == []

    def test_large_span_is_conflict(self) -> None:
        """tier 1 vs tier 3 (span 2) >= default threshold 2 => conflict."""
        records = [
            _tier(_UUID_A, tier=1),
            _tier(_UUID_B, tier=3),
        ]
        conflicts = detect_tier_conflicts(records)
        assert len(conflicts) == 1
        c = conflicts[0]
        assert c["conflict_type"] == "tier_span_exceeds_threshold"
        assert c["canonical_player_id"] == _PLAYER_3
        assert c["tier_range"] == [1, 3]
        assert set(c["decision_ids"]) == {_UUID_A, _UUID_B}

    def test_custom_threshold(self) -> None:
        """threshold=1 => span 1 counts as conflict."""
        records = [
            _tier(_UUID_A, tier=2),
            _tier(_UUID_B, tier=3),
        ]
        conflicts = detect_tier_conflicts(records, threshold=1)
        assert len(conflicts) == 1

    def test_different_player_no_conflict(self) -> None:
        records = [
            _tier(_UUID_A, player=_PLAYER_1, tier=1),
            _tier(_UUID_B, player=_PLAYER_2, tier=5),
        ]
        assert detect_tier_conflicts(records) == []

    def test_different_window_no_conflict(self) -> None:
        records = [
            _tier(_UUID_A, tier=1, window=_WINDOW_1),
            _tier(_UUID_B, tier=5, window=_WINDOW_2),
        ]
        assert detect_tier_conflicts(records) == []

    def test_different_cohort_no_conflict(self) -> None:
        records = [
            _tier(_UUID_A, tier=1, cohort=_COHORT_A),
            _tier(_UUID_B, tier=5, cohort=_COHORT_B),
        ]
        assert detect_tier_conflicts(records) == []

    def test_three_way_conflict(self) -> None:
        """Three tier labels on same player with span >= 2 => one group."""
        records = [
            _tier(_UUID_A, tier=1),
            _tier(_UUID_B, tier=3),
            _tier(_UUID_C, tier=5),
        ]
        conflicts = detect_tier_conflicts(records)
        assert len(conflicts) == 1
        assert conflicts[0]["tier_range"] == [1, 5]
        assert len(conflicts[0]["decision_ids"]) == 3

    def test_revoked_record_excluded(self) -> None:
        records = [
            _tier(_UUID_A, tier=1),
            _tier(_UUID_B, tier=5),
            _revoke(_UUID_C, target_decision_id=_UUID_A),
        ]
        # _UUID_A is revoked (revoke record has pairwise type but
        # supersedes _UUID_A). active_labels will drop _UUID_A.
        # Only _UUID_B remains => no conflict.
        assert detect_tier_conflicts(records) == []


# ---------------------------------------------------------------------------
# low_confidence_queue
# ---------------------------------------------------------------------------


class TestLowConfidenceQueue:
    def test_empty_records(self) -> None:
        assert low_confidence_queue([]) == []

    def test_high_confidence_long_evidence_not_queued(self) -> None:
        records = [_pairwise(_UUID_A, confidence="high", evidence=_LONG_EVIDENCE)]
        assert low_confidence_queue(records) == []

    def test_low_confidence_queued(self) -> None:
        records = [_pairwise(_UUID_A, confidence="low", evidence=_LONG_EVIDENCE)]
        queue = low_confidence_queue(records)
        assert len(queue) == 1
        assert queue[0]["decision_id"] == _UUID_A
        assert "low_confidence" in queue[0]["reasons"]

    def test_thin_evidence_queued_even_if_high_confidence(self) -> None:
        records = [_pairwise(_UUID_A, confidence="high", evidence=_SHORT_EVIDENCE)]
        queue = low_confidence_queue(records)
        assert len(queue) == 1
        assert "thin_evidence" in queue[0]["reasons"]
        assert "low_confidence" not in queue[0]["reasons"]

    def test_both_reasons_coexist(self) -> None:
        records = [_pairwise(_UUID_A, confidence="low", evidence=_SHORT_EVIDENCE)]
        queue = low_confidence_queue(records)
        assert len(queue) == 1
        assert "low_confidence" in queue[0]["reasons"]
        assert "thin_evidence" in queue[0]["reasons"]

    def test_custom_evidence_min_chars(self) -> None:
        # Evidence of 10 chars, min=100 => queued
        records = [_pairwise(_UUID_A, confidence="high", evidence="A was better.")]
        queue = low_confidence_queue(records, evidence_min_chars=100)
        assert len(queue) == 1

    def test_tier_label_queued_too(self) -> None:
        records = [_tier(_UUID_A, confidence="low", evidence=_LONG_EVIDENCE)]
        queue = low_confidence_queue(records)
        assert len(queue) == 1
        assert queue[0]["label_type"] == "human_tier"

    def test_revoked_record_excluded(self) -> None:
        records = [
            _pairwise(_UUID_A, confidence="low", evidence=_SHORT_EVIDENCE),
            _revoke(_UUID_B, target_decision_id=_UUID_A),
        ]
        assert low_confidence_queue(records) == []


# ---------------------------------------------------------------------------
# retest_queue
# ---------------------------------------------------------------------------


class TestRetestQueue:
    def test_empty_records(self) -> None:
        queue, skipped = retest_queue([])
        assert queue == []
        assert skipped == 0

    def test_young_record_not_queued(self) -> None:
        now = datetime(2026, 7, 31, tzinfo=UTC)
        records = [_pairwise(_UUID_A, recorded_at="2026-07-30T00:00:00Z")]
        queue, skipped = retest_queue(records, max_age_days=180, now=now)
        assert queue == []
        assert skipped == 0

    def test_aged_record_queued(self) -> None:
        now = datetime(2026, 7, 31, tzinfo=UTC)
        # 200 days old => >= 180
        old = (now - timedelta(days=200)).strftime("%Y-%m-%dT%H:%M:%SZ")
        records = [_pairwise(_UUID_A, recorded_at=old)]
        queue, skipped = retest_queue(records, max_age_days=180, now=now)
        assert len(queue) == 1
        assert queue[0]["decision_id"] == _UUID_A
        assert queue[0]["age_days"] >= 180
        assert skipped == 0

    def test_custom_max_age_days(self) -> None:
        now = datetime(2026, 7, 31, tzinfo=UTC)
        # 10 days old
        old = (now - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        records = [_pairwise(_UUID_A, recorded_at=old)]
        # max_age=5 => queued; max_age=20 => not queued
        queue1, _ = retest_queue(records, max_age_days=5, now=now)
        assert len(queue1) == 1
        queue2, _ = retest_queue(records, max_age_days=20, now=now)
        assert queue2 == []

    def test_bad_timestamp_skipped(self) -> None:
        records = [_pairwise(_UUID_A, recorded_at="not-a-date")]
        queue, skipped = retest_queue(records, max_age_days=180)
        assert queue == []
        assert skipped == 1

    def test_queue_sorted_oldest_first(self) -> None:
        now = datetime(2026, 7, 31, tzinfo=UTC)
        older = (now - timedelta(days=300)).strftime("%Y-%m-%dT%H:%M:%SZ")
        newer = (now - timedelta(days=200)).strftime("%Y-%m-%dT%H:%M:%SZ")
        records = [
            _pairwise(_UUID_A, recorded_at=newer),
            _pairwise(_UUID_B, recorded_at=older),
        ]
        queue, _ = retest_queue(records, max_age_days=180, now=now)
        assert len(queue) == 2
        # Oldest (highest age_days) first
        assert queue[0]["age_days"] > queue[1]["age_days"]
        assert queue[0]["decision_id"] == _UUID_B

    def test_revoked_record_excluded(self) -> None:
        now = datetime(2026, 7, 31, tzinfo=UTC)
        old = (now - timedelta(days=300)).strftime("%Y-%m-%dT%H:%M:%SZ")
        records = [
            _pairwise(_UUID_A, recorded_at=old),
            _revoke(_UUID_B, target_decision_id=_UUID_A, recorded_at=old),
        ]
        queue, _ = retest_queue(records, max_age_days=180, now=now)
        assert queue == []


# ---------------------------------------------------------------------------
# build_review_queue
# ---------------------------------------------------------------------------


class TestBuildReviewQueue:
    def test_empty_ledger_status_ok(self) -> None:
        report = build_review_queue([])
        assert report["status"] == "ok"
        assert report["summary"]["total_review_items"] == 0
        assert report["summary"]["active_label_count"] == 0

    def test_schema_and_version(self) -> None:
        report = build_review_queue([])
        assert report["schema"] == REVIEW_QUEUE_SCHEMA
        assert report["schema_version"] == REVIEW_QUEUE_SCHEMA_VERSION

    def test_parameters_echoed(self) -> None:
        report = build_review_queue(
            [],
            tier_conflict_threshold=3,
            evidence_min_chars=100,
            max_age_days=365,
        )
        p = report["parameters"]
        assert p["tier_conflict_threshold"] == 3
        assert p["evidence_min_chars"] == 100
        assert p["max_age_days"] == 365

    def test_default_parameters_match_constants(self) -> None:
        report = build_review_queue([])
        p = report["parameters"]
        assert p["tier_conflict_threshold"] == DEFAULT_TIER_CONFLICT_THRESHOLD
        assert p["evidence_min_chars"] == DEFAULT_EVIDENCE_MIN_CHARS
        assert p["max_age_days"] == DEFAULT_MAX_AGE_DAYS

    def test_status_review_needed_when_conflict(self) -> None:
        records = [
            _pairwise(_UUID_A, preferred="a"),
            _pairwise(_UUID_B, preferred="b"),
        ]
        report = build_review_queue(records)
        assert report["status"] == "review_needed"

    def test_status_review_needed_when_low_confidence(self) -> None:
        records = [_pairwise(_UUID_A, confidence="low", evidence=_LONG_EVIDENCE)]
        report = build_review_queue(records)
        assert report["status"] == "review_needed"

    def test_status_review_needed_when_aged(self) -> None:
        now = datetime(2026, 7, 31, tzinfo=UTC)
        old = (now - timedelta(days=300)).strftime("%Y-%m-%dT%H:%M:%SZ")
        records = [_pairwise(_UUID_A, recorded_at=old)]
        report = build_review_queue(records, now=now)
        assert report["status"] == "review_needed"

    def test_summary_counts_consistent(self) -> None:
        now = datetime(2026, 7, 31, tzinfo=UTC)
        old = (now - timedelta(days=300)).strftime("%Y-%m-%dT%H:%M:%SZ")
        records = [
            # 1 pairwise conflict group (2 records)
            _pairwise(_UUID_A, preferred="a"),
            _pairwise(_UUID_B, preferred="b"),
            # 1 tier conflict group (2 records)
            _tier(_UUID_C, tier=1),
            _tier(_UUID_D, tier=5),
            # 1 low-confidence (also thin evidence)
            _pairwise(_UUID_E, confidence="low", evidence=_SHORT_EVIDENCE, recorded_at=old),
        ]
        report = build_review_queue(records, now=now)
        s = report["summary"]
        assert s["pairwise_conflict_groups"] == 1
        assert s["tier_conflict_groups"] == 1
        # _UUID_E is both low-confidence and thin-evidence and aged
        assert s["low_confidence_items"] == 1
        assert s["retest_items"] == 1
        # total = 1 (pairwise conflict) + 1 (tier conflict) + 1 (low conf) + 1 (retest)
        assert s["total_review_items"] == 4
        assert s["active_label_count"] == 5

    def test_conflict_decision_ids_count_deduplicates(self) -> None:
        """A record in a conflict group also counted in low_confidence
        should still be counted once in conflict_decision_ids_count."""
        records = [
            _pairwise(_UUID_A, preferred="a", confidence="low", evidence=_SHORT_EVIDENCE),
            _pairwise(_UUID_B, preferred="b"),
        ]
        report = build_review_queue(records)
        # _UUID_A and _UUID_B are in the conflict group
        assert report["summary"]["conflict_decision_ids_count"] == 2

    def test_limitations_non_empty(self) -> None:
        report = build_review_queue([])
        assert len(report["limitations"]) > 0

    def test_json_serialisable(self) -> None:
        records = [
            _pairwise(_UUID_A, preferred="a"),
            _pairwise(_UUID_B, preferred="b"),
        ]
        report = build_review_queue(records)
        # Must not raise
        json.dumps(report, ensure_ascii=False)

    def test_active_label_count_matches_active_labels(self) -> None:
        records = [
            _pairwise(_UUID_A, preferred="a"),
            _revoke(_UUID_B, target_decision_id=_UUID_A),
        ]
        report = build_review_queue(records)
        # _UUID_A is revoked, so active count is 0 (revoke record is not
        # a confirmed label, it's an action record)
        assert report["summary"]["active_label_count"] == 0

    def test_revoked_records_do_not_contribute(self) -> None:
        """A revoked conflict should not appear in any queue."""
        records = [
            _pairwise(_UUID_A, preferred="a", confidence="low", evidence=_SHORT_EVIDENCE),
            _pairwise(_UUID_B, preferred="b"),
            _revoke(_UUID_C, target_decision_id=_UUID_A),
        ]
        report = build_review_queue(records)
        # _UUID_A revoked => only _UUID_B active => no conflict, no low-conf
        assert report["status"] == "ok"
        assert report["summary"]["total_review_items"] == 0

    def test_now_parameter_respected(self) -> None:
        """Passing now=2020 should make all 2026 records aged."""
        records = [_pairwise(_UUID_A, recorded_at="2026-07-31T00:00:00Z")]
        now = datetime(2026, 8, 1, tzinfo=UTC)  # 1 day later
        report = build_review_queue(records, max_age_days=180, now=now)
        assert report["summary"]["retest_items"] == 0

        now_old = datetime(2027, 6, 1, tzinfo=UTC)  # ~10 months later
        report2 = build_review_queue(records, max_age_days=180, now=now_old)
        assert report2["summary"]["retest_items"] == 1


# ---------------------------------------------------------------------------
# Integration: conflict + low_confidence + retest combined
# ---------------------------------------------------------------------------


class TestIntegrationCombined:
    def test_full_report_with_all_three_queue_types(self) -> None:
        now = datetime(2026, 7, 31, tzinfo=UTC)
        old = (now - timedelta(days=300)).strftime("%Y-%m-%dT%H:%M:%SZ")
        records = [
            # Pairwise conflict (2 records, same pair, opposite prefs)
            _pairwise(_UUID_A, preferred="a", recorded_at=old),
            _pairwise(_UUID_B, preferred="b", recorded_at=old),
            # Tier conflict (2 records, same player, span 4)
            _tier(_UUID_C, tier=1, recorded_at=old),
            _tier(_UUID_D, tier=5, recorded_at=old),
            # Low confidence (1 record, also thin evidence, also aged)
            _pairwise(
                _UUID_E, preferred="a", confidence="low",
                evidence=_SHORT_EVIDENCE, recorded_at=old,
            ),
        ]
        report = build_review_queue(records, now=now)

        assert report["status"] == "review_needed"
        assert len(report["conflict_queue"]["pairwise"]) == 1
        assert len(report["conflict_queue"]["tier"]) == 1
        assert len(report["low_confidence_queue"]) == 1
        assert len(report["retest_queue"]) == 5  # all 5 records are aged

        # Verify the low-confidence record's reasons
        lc = report["low_confidence_queue"][0]
        assert "low_confidence" in lc["reasons"]
        assert "thin_evidence" in lc["reasons"]

    def test_clean_ledger_after_revoke(self) -> None:
        """Revoke all conflicting records => status returns to ok."""
        records = [
            _pairwise(_UUID_A, preferred="a"),
            _pairwise(_UUID_B, preferred="b"),
            _revoke(_UUID_C, target_decision_id=_UUID_A),
            _revoke(_UUID_D, target_decision_id=_UUID_B),
        ]
        report = build_review_queue(records)
        assert report["status"] == "ok"
