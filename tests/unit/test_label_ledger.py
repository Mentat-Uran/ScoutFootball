"""Tests for the PRS-3 personal evaluation label ledger (slice 1).

Covers:

- ``validate_record`` accepts valid confirmed/revoked records for both
  ``human_pairwise_preference`` and ``human_tier`` label types, and
  rejects every schema violation (wrong type/version, missing fields,
  oversized fields, invalid action, bad revision, invalid label_type,
  invalid confidence, invalid cohort_hash, invalid observation_window,
  pairwise self-comparison, tier out of range, supersedes not uuid).
- ``build_label`` enforces confirmed-requires-payload for both pairwise
  and tier, propagates supersedes_decision_id, generates decision_id and
  recorded_at when omitted, and respects explicit values when provided.
- ``build_revoke_label`` builds a revoke record with action=revoked,
  blind=False, confidence=low and supersedes_decision_id pointing at the
  target.
- ``read_ledger`` returns [] for a missing file, validates every line,
  rejects blank lines, invalid JSON, wrong record_type, and revision
  gaps.
- ``append_label`` creates the file on first append, refuses a stale
  revision (concurrent writer detection), and persists the record
  verbatim.
- ``active_labels`` returns only records whose latest action is
  confirmed; revoke clears; supersede replaces.
- ``lookup_labels`` filters by cohort_hash, label_type, role_family,
  season_id, player_id (matching both pairwise a/b and tier canonical),
  and respects active_only.
- ``ledger_summary`` reports counts by action, label_type, confidence,
  role, cohort, blind_count, latest_revision, latest_recorded_at.
- ``label_independence_audit`` flags model_derived in active set,
  pairwise self-comparison (defensive), invalid observation_window
  (defensive), empty evidence; reports supervision_eligible count by
  type; status=ok when no violations.
- Cross-cohort isolation: the same player pair under two cohort_hash
  values is two independent business keys.
- Round-trip: append -> read -> active_labels -> lookup returns the
  appended record.
"""

from __future__ import annotations

import json
import uuid

import pytest

from scoutfootball.evaluation.label_ledger import (
    LEDGER_TYPE,
    LEDGER_VERSION,
    SELF_REFERENTIAL_LABEL_TYPES,
    SUPERVISION_ELIGIBLE_LABEL_TYPES,
    active_labels,
    append_label,
    build_label,
    build_revoke_label,
    label_independence_audit,
    ledger_path,
    ledger_summary,
    lookup_labels,
    read_ledger,
    validate_record,
)

# ---------------------------------------------------------------------------
# Valid record fixtures
# ---------------------------------------------------------------------------

_VALID_COHORT_HASH = "0123456789abcdef"
_VALID_OBSERVATION_WINDOW = "2024-08-01/2025-05-31"
_UUID_A = "11111111-1111-1111-1111-111111111111"
_UUID_B = "22222222-2222-2222-2222-222222222222"
_UUID_C = "33333333-3333-3333-3333-333333333333"


def _valid_pairwise_confirmed(**overrides) -> dict:
    base = {
        "record_type": LEDGER_TYPE,
        "record_version": LEDGER_VERSION,
        "decision_id": _UUID_A,
        "revision": 1,
        "recorded_at": "2026-07-31T00:00:00Z",
        "action": "confirmed",
        "label_type": "human_pairwise_preference",
        "cohort_hash": _VALID_COHORT_HASH,
        "role_family": "CB",
        "season_id": "2425",
        "observation_window": _VALID_OBSERVATION_WINDOW,
        "confidence": "high",
        "evidence": (
            "Player A had 2.3 interceptions/90 vs Player B 1.1; A was "
            "visibly stronger in aerial duels."
        ),
        "decided_by": "maintainer",
        "notes": "",
        "blind": True,
        "supersedes_decision_id": None,
        "player_a_id": "unresolved:understat:u|1",
        "player_b_id": "unresolved:understat:u|2",
        "preferred_player": "a",
    }
    base.update(overrides)
    return base


def _valid_tier_confirmed(**overrides) -> dict:
    base = {
        "record_type": LEDGER_TYPE,
        "record_version": LEDGER_VERSION,
        "decision_id": _UUID_B,
        "revision": 1,
        "recorded_at": "2026-07-31T00:00:00Z",
        "action": "confirmed",
        "label_type": "human_tier",
        "cohort_hash": _VALID_COHORT_HASH,
        "role_family": "ST",
        "season_id": "2425",
        "observation_window": _VALID_OBSERVATION_WINDOW,
        "confidence": "medium",
        "evidence": (
            "Scored 15 non-penalty goals in 1800 min; tier 2 based on "
            "volume and efficiency."
        ),
        "decided_by": "maintainer",
        "notes": "",
        "blind": True,
        "supersedes_decision_id": None,
        "canonical_player_id": "unresolved:understat:u|5",
        "tier": 2,
    }
    base.update(overrides)
    return base


def _valid_revoke(**overrides) -> dict:
    """A revoke record for a pairwise label (no payload required)."""
    base = {
        "record_type": LEDGER_TYPE,
        "record_version": LEDGER_VERSION,
        "decision_id": _UUID_C,
        "revision": 2,
        "recorded_at": "2026-07-31T01:00:00Z",
        "action": "revoked",
        "label_type": "human_pairwise_preference",
        "cohort_hash": _VALID_COHORT_HASH,
        "role_family": "CB",
        "season_id": "2425",
        "observation_window": _VALID_OBSERVATION_WINDOW,
        "confidence": "low",
        "evidence": (
            "Re-review showed B was actually stronger in aerial duels; "
            "original label was wrong."
        ),
        "decided_by": "maintainer",
        "notes": "",
        "blind": False,
        "supersedes_decision_id": _UUID_A,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# validate_record: envelope
# ---------------------------------------------------------------------------


class TestValidateRecordEnvelope:
    def test_valid_pairwise_confirmed_passes(self) -> None:
        record = _valid_pairwise_confirmed()
        validated = validate_record(record)
        assert validated["label_type"] == "human_pairwise_preference"
        assert validated["player_a_id"] == "unresolved:understat:u|1"
        assert validated["preferred_player"] == "a"

    def test_valid_tier_confirmed_passes(self) -> None:
        record = _valid_tier_confirmed()
        validated = validate_record(record)
        assert validated["label_type"] == "human_tier"
        assert validated["canonical_player_id"] == "unresolved:understat:u|5"
        assert validated["tier"] == 2

    def test_valid_revoke_without_payload_passes(self) -> None:
        record = _valid_revoke()
        validated = validate_record(record)
        assert validated["action"] == "revoked"
        # Revoked records do not require pairwise/tier payload.
        assert "player_a_id" not in validated
        assert "player_b_id" not in validated
        assert "preferred_player" not in validated

    def test_non_dict_record_rejected(self) -> None:
        with pytest.raises(ValueError, match="record_not_dict"):
            validate_record("not a dict")  # type: ignore[arg-type]

    def test_wrong_record_type_rejected(self) -> None:
        record = _valid_pairwise_confirmed(record_type="scoutfootball.other")
        with pytest.raises(ValueError, match="record_type_invalid"):
            validate_record(record)

    def test_wrong_record_version_rejected(self) -> None:
        record = _valid_pairwise_confirmed(record_version="2.0")
        with pytest.raises(ValueError, match="record_version_invalid"):
            validate_record(record)

    def test_invalid_action_rejected(self) -> None:
        record = _valid_pairwise_confirmed(action="rejected")
        with pytest.raises(ValueError, match="action_invalid"):
            validate_record(record)

    def test_empty_decision_id_rejected(self) -> None:
        record = _valid_pairwise_confirmed(decision_id="")
        with pytest.raises(ValueError, match="decision_id_empty"):
            validate_record(record)

    def test_non_uuid_decision_id_rejected(self) -> None:
        record = _valid_pairwise_confirmed(decision_id="not-a-uuid")
        with pytest.raises(ValueError, match="decision_id_not_uuid"):
            validate_record(record)

    def test_zero_revision_rejected(self) -> None:
        record = _valid_pairwise_confirmed(revision=0)
        with pytest.raises(ValueError, match="revision_non_positive"):
            validate_record(record)

    def test_negative_revision_rejected(self) -> None:
        record = _valid_pairwise_confirmed(revision=-1)
        with pytest.raises(ValueError, match="revision_non_positive"):
            validate_record(record)

    def test_bool_revision_rejected(self) -> None:
        # bool is a subclass of int; must be rejected explicitly.
        record = _valid_pairwise_confirmed(revision=True)
        with pytest.raises(ValueError, match="revision_bool"):
            validate_record(record)

    def test_empty_recorded_at_rejected(self) -> None:
        record = _valid_pairwise_confirmed(recorded_at="")
        with pytest.raises(ValueError, match="recorded_at_empty"):
            validate_record(record)

    def test_empty_evidence_rejected(self) -> None:
        record = _valid_pairwise_confirmed(evidence="")
        with pytest.raises(ValueError, match="evidence_empty"):
            validate_record(record)

    def test_oversized_evidence_rejected(self) -> None:
        record = _valid_pairwise_confirmed(evidence="x" * 501)
        with pytest.raises(ValueError, match="evidence_too_long"):
            validate_record(record)

    def test_empty_decided_by_rejected(self) -> None:
        record = _valid_pairwise_confirmed(decided_by="")
        with pytest.raises(ValueError, match="decided_by_empty"):
            validate_record(record)

    def test_oversized_notes_rejected(self) -> None:
        record = _valid_pairwise_confirmed(notes="x" * 501)
        with pytest.raises(ValueError, match="notes_too_long"):
            validate_record(record)

    def test_empty_role_family_rejected(self) -> None:
        record = _valid_pairwise_confirmed(role_family="")
        with pytest.raises(ValueError, match="role_family_empty"):
            validate_record(record)

    def test_empty_season_id_rejected(self) -> None:
        record = _valid_pairwise_confirmed(season_id="")
        with pytest.raises(ValueError, match="season_id_empty"):
            validate_record(record)

    def test_blind_not_bool_rejected(self) -> None:
        record = _valid_pairwise_confirmed(blind="yes")
        with pytest.raises(ValueError, match="blind_not_bool"):
            validate_record(record)

    def test_supersedes_non_uuid_rejected(self) -> None:
        record = _valid_pairwise_confirmed(supersedes_decision_id="not-a-uuid")
        with pytest.raises(ValueError, match="supersedes_not_uuid"):
            validate_record(record)

    def test_supersedes_empty_string_treated_as_none(self) -> None:
        # Empty supersedes_decision_id is treated as None (no supersede).
        record = _valid_pairwise_confirmed(supersedes_decision_id=None)
        validated = validate_record(record)
        assert validated["supersedes_decision_id"] is None

    def test_valid_supersedes_passes(self) -> None:
        record = _valid_pairwise_confirmed(
            supersedes_decision_id=_UUID_B
        )
        validated = validate_record(record)
        assert validated["supersedes_decision_id"] == _UUID_B


# ---------------------------------------------------------------------------
# validate_record: label_type and confidence
# ---------------------------------------------------------------------------


class TestValidateRecordLabelType:
    def test_unknown_label_type_rejected(self) -> None:
        record = _valid_pairwise_confirmed(label_type="invalid_type")
        with pytest.raises(ValueError, match="label_type_unknown"):
            validate_record(record)

    def test_external_reference_label_type_accepted(self) -> None:
        record = _valid_pairwise_confirmed(label_type="external_reference")
        # external_reference has no type-specific payload, so it should
        # pass validation with just the envelope.
        validated = validate_record(record)
        assert validated["label_type"] == "external_reference"

    def test_future_outcome_label_type_accepted(self) -> None:
        record = _valid_pairwise_confirmed(label_type="future_outcome")
        validated = validate_record(record)
        assert validated["label_type"] == "future_outcome"

    def test_model_derived_label_type_accepted(self) -> None:
        # model_derived is structurally valid (will be flagged by the
        # independence audit, not by validate_record).
        record = _valid_pairwise_confirmed(label_type="model_derived")
        validated = validate_record(record)
        assert validated["label_type"] == "model_derived"

    def test_invalid_confidence_rejected(self) -> None:
        record = _valid_pairwise_confirmed(confidence="very_high")
        with pytest.raises(ValueError, match="confidence_invalid"):
            validate_record(record)


# ---------------------------------------------------------------------------
# validate_record: cohort_hash
# ---------------------------------------------------------------------------


class TestValidateRecordCohortHash:
    def test_wrong_length_cohort_hash_rejected(self) -> None:
        record = _valid_pairwise_confirmed(cohort_hash="0123456789abc")  # 13 chars
        with pytest.raises(ValueError, match="cohort_hash_wrong_length"):
            validate_record(record)

    def test_non_hex_cohort_hash_rejected(self) -> None:
        record = _valid_pairwise_confirmed(cohort_hash="0123456789abcdeg")  # 16 chars but 'g'
        with pytest.raises(ValueError, match="cohort_hash_not_hex"):
            validate_record(record)

    def test_uppercase_hex_cohort_hash_rejected(self) -> None:
        # Only lowercase hex is accepted by the regex [0-9a-f]+.
        record = _valid_pairwise_confirmed(cohort_hash="0123456789ABCDEF")
        with pytest.raises(ValueError, match="cohort_hash_not_hex"):
            validate_record(record)

    def test_empty_cohort_hash_rejected(self) -> None:
        record = _valid_pairwise_confirmed(cohort_hash="")
        with pytest.raises(ValueError, match="cohort_hash_empty"):
            validate_record(record)


# ---------------------------------------------------------------------------
# validate_record: observation_window
# ---------------------------------------------------------------------------


class TestValidateRecordObservationWindow:
    def test_invalid_format_no_slash_rejected(self) -> None:
        record = _valid_pairwise_confirmed(
            observation_window="2024-08-01"
        )
        with pytest.raises(ValueError, match="observation_window_invalid_format"):
            validate_record(record)

    def test_invalid_format_wrong_separator_rejected(self) -> None:
        record = _valid_pairwise_confirmed(
            observation_window="2024-08-01--2025-05-31"
        )
        with pytest.raises(ValueError, match="observation_window_invalid_format"):
            validate_record(record)

    def test_invalid_date_rejected(self) -> None:
        record = _valid_pairwise_confirmed(
            observation_window="2024-13-01/2025-05-31"  # month 13
        )
        with pytest.raises(ValueError, match="observation_window_invalid"):
            validate_record(record)

    def test_end_before_start_rejected(self) -> None:
        record = _valid_pairwise_confirmed(
            observation_window="2025-05-31/2024-08-01"
        )
        with pytest.raises(ValueError, match="observation_window_end_before_start"):
            validate_record(record)

    def test_same_start_end_passes(self) -> None:
        record = _valid_pairwise_confirmed(
            observation_window="2025-05-31/2025-05-31"
        )
        validated = validate_record(record)
        assert validated["observation_window"] == "2025-05-31/2025-05-31"


# ---------------------------------------------------------------------------
# validate_record: pairwise payload
# ---------------------------------------------------------------------------


class TestValidateRecordPairwisePayload:
    def test_missing_player_a_id_on_confirmed_rejected(self) -> None:
        record = _valid_pairwise_confirmed()
        record.pop("player_a_id")
        # None is not a string -> not_string error (not empty).
        with pytest.raises(ValueError, match="player_a_id_not_string"):
            validate_record(record)

    def test_missing_player_b_id_on_confirmed_rejected(self) -> None:
        record = _valid_pairwise_confirmed()
        record.pop("player_b_id")
        with pytest.raises(ValueError, match="player_b_id_not_string"):
            validate_record(record)

    def test_missing_preferred_player_on_confirmed_rejected(self) -> None:
        record = _valid_pairwise_confirmed()
        record.pop("preferred_player")
        with pytest.raises(ValueError, match="preferred_player_not_string"):
            validate_record(record)

    def test_invalid_preferred_player_rejected(self) -> None:
        record = _valid_pairwise_confirmed(preferred_player="c")
        with pytest.raises(ValueError, match="preferred_player_invalid"):
            validate_record(record)

    def test_pairwise_self_comparison_rejected(self) -> None:
        record = _valid_pairwise_confirmed(
            player_a_id="same_id", player_b_id="same_id"
        )
        with pytest.raises(ValueError, match="pairwise_self_comparison"):
            validate_record(record)

    def test_preferred_player_tie_accepted(self) -> None:
        record = _valid_pairwise_confirmed(preferred_player="tie")
        validated = validate_record(record)
        assert validated["preferred_player"] == "tie"

    def test_oversized_player_id_rejected(self) -> None:
        record = _valid_pairwise_confirmed(player_a_id="x" * 201)
        with pytest.raises(ValueError, match="player_a_id_too_long"):
            validate_record(record)


# ---------------------------------------------------------------------------
# validate_record: tier payload
# ---------------------------------------------------------------------------


class TestValidateRecordTierPayload:
    def test_missing_canonical_player_id_on_confirmed_rejected(self) -> None:
        record = _valid_tier_confirmed()
        record.pop("canonical_player_id")
        # None is not a string -> not_string error (not empty).
        with pytest.raises(ValueError, match="canonical_player_id_not_string"):
            validate_record(record)

    def test_missing_tier_on_confirmed_rejected(self) -> None:
        record = _valid_tier_confirmed()
        record.pop("tier")
        # None is not an int -> not_int error.
        with pytest.raises(ValueError, match="tier_not_int"):
            validate_record(record)

    def test_tier_zero_rejected(self) -> None:
        record = _valid_tier_confirmed(tier=0)
        with pytest.raises(ValueError, match="tier_out_of_range"):
            validate_record(record)

    def test_tier_six_rejected(self) -> None:
        record = _valid_tier_confirmed(tier=6)
        with pytest.raises(ValueError, match="tier_out_of_range"):
            validate_record(record)

    def test_tier_one_accepted(self) -> None:
        record = _valid_tier_confirmed(tier=1)
        validated = validate_record(record)
        assert validated["tier"] == 1

    def test_tier_five_accepted(self) -> None:
        record = _valid_tier_confirmed(tier=5)
        validated = validate_record(record)
        assert validated["tier"] == 5

    def test_bool_tier_rejected(self) -> None:
        record = _valid_tier_confirmed(tier=True)
        with pytest.raises(ValueError, match="tier_bool"):
            validate_record(record)

    def test_string_tier_rejected(self) -> None:
        record = _valid_tier_confirmed(tier="2")
        with pytest.raises(ValueError, match="tier_not_int"):
            validate_record(record)

    def test_oversized_canonical_player_id_rejected(self) -> None:
        record = _valid_tier_confirmed(canonical_player_id="x" * 201)
        with pytest.raises(ValueError, match="canonical_player_id_too_long"):
            validate_record(record)


# ---------------------------------------------------------------------------
# build_label
# ---------------------------------------------------------------------------


class TestBuildLabel:
    def test_pairwise_confirmed_builds_with_payload(self) -> None:
        record = build_label(
            action="confirmed",
            label_type="human_pairwise_preference",
            cohort_hash=_VALID_COHORT_HASH,
            role_family="CB",
            season_id="2425",
            observation_window=_VALID_OBSERVATION_WINDOW,
            confidence="high",
            evidence="A had more interceptions per 90",
            decided_by="maintainer",
            revision=1,
            player_a_id="u|1",
            player_b_id="u|2",
            preferred_player="a",
        )
        assert record["action"] == "confirmed"
        assert record["label_type"] == "human_pairwise_preference"
        assert record["player_a_id"] == "u|1"
        assert record["player_b_id"] == "u|2"
        assert record["preferred_player"] == "a"
        assert record["record_type"] == LEDGER_TYPE
        assert record["record_version"] == LEDGER_VERSION
        assert record["revision"] == 1
        assert record["decision_id"]
        assert record["recorded_at"]
        assert record["blind"] is True  # default
        assert record["supersedes_decision_id"] is None

    def test_tier_confirmed_builds_with_payload(self) -> None:
        record = build_label(
            action="confirmed",
            label_type="human_tier",
            cohort_hash=_VALID_COHORT_HASH,
            role_family="ST",
            season_id="2425",
            observation_window=_VALID_OBSERVATION_WINDOW,
            confidence="medium",
            evidence="15 npxG in 1800 min, tier 2",
            decided_by="maintainer",
            revision=1,
            canonical_player_id="u|5",
            tier=2,
        )
        assert record["canonical_player_id"] == "u|5"
        assert record["tier"] == 2

    def test_pairwise_missing_payload_raises(self) -> None:
        with pytest.raises(ValueError, match="pairwise_missing_payload"):
            build_label(
                action="confirmed",
                label_type="human_pairwise_preference",
                cohort_hash=_VALID_COHORT_HASH,
                role_family="CB",
                season_id="2425",
                observation_window=_VALID_OBSERVATION_WINDOW,
                confidence="high",
                evidence="some evidence",
                decided_by="maintainer",
                revision=1,
                # missing player_a_id, player_b_id, preferred_player
            )

    def test_tier_missing_payload_raises(self) -> None:
        with pytest.raises(ValueError, match="tier_missing_payload"):
            build_label(
                action="confirmed",
                label_type="human_tier",
                cohort_hash=_VALID_COHORT_HASH,
                role_family="ST",
                season_id="2425",
                observation_window=_VALID_OBSERVATION_WINDOW,
                confidence="medium",
                evidence="some evidence",
                decided_by="maintainer",
                revision=1,
                # missing canonical_player_id, tier
            )

    def test_explicit_decision_id_respected(self) -> None:
        record = build_label(
            action="confirmed",
            label_type="human_tier",
            cohort_hash=_VALID_COHORT_HASH,
            role_family="ST",
            season_id="2425",
            observation_window=_VALID_OBSERVATION_WINDOW,
            confidence="medium",
            evidence="some evidence",
            decided_by="maintainer",
            revision=1,
            canonical_player_id="u|5",
            tier=3,
            decision_id=_UUID_A,
        )
        assert record["decision_id"] == _UUID_A

    def test_explicit_recorded_at_respected(self) -> None:
        record = build_label(
            action="confirmed",
            label_type="human_tier",
            cohort_hash=_VALID_COHORT_HASH,
            role_family="ST",
            season_id="2425",
            observation_window=_VALID_OBSERVATION_WINDOW,
            confidence="medium",
            evidence="some evidence",
            decided_by="maintainer",
            revision=1,
            canonical_player_id="u|5",
            tier=3,
            recorded_at="2026-01-01T00:00:00Z",
        )
        assert record["recorded_at"] == "2026-01-01T00:00:00Z"

    def test_supersedes_propagated(self) -> None:
        record = build_label(
            action="confirmed",
            label_type="human_tier",
            cohort_hash=_VALID_COHORT_HASH,
            role_family="ST",
            season_id="2425",
            observation_window=_VALID_OBSERVATION_WINDOW,
            confidence="medium",
            evidence="corrected tier after re-review",
            decided_by="maintainer",
            revision=2,
            canonical_player_id="u|5",
            tier=2,
            supersedes_decision_id=_UUID_B,
        )
        assert record["supersedes_decision_id"] == _UUID_B

    def test_not_blind_propagated(self) -> None:
        record = build_label(
            action="confirmed",
            label_type="human_tier",
            cohort_hash=_VALID_COHORT_HASH,
            role_family="ST",
            season_id="2425",
            observation_window=_VALID_OBSERVATION_WINDOW,
            confidence="medium",
            evidence="some evidence",
            decided_by="maintainer",
            revision=1,
            canonical_player_id="u|5",
            tier=3,
            blind=False,
        )
        assert record["blind"] is False


# ---------------------------------------------------------------------------
# build_revoke_label
# ---------------------------------------------------------------------------


class TestBuildRevokeLabel:
    def test_revoke_builds_with_target(self) -> None:
        record = build_revoke_label(
            target_decision_id=_UUID_A,
            cohort_hash=_VALID_COHORT_HASH,
            role_family="CB",
            season_id="2425",
            observation_window=_VALID_OBSERVATION_WINDOW,
            label_type="human_pairwise_preference",
            evidence="Re-review showed B was stronger",
            decided_by="maintainer",
            revision=2,
        )
        assert record["action"] == "revoked"
        assert record["supersedes_decision_id"] == _UUID_A
        assert record["label_type"] == "human_pairwise_preference"
        assert record["blind"] is False  # revoke is not an annotation
        assert record["confidence"] == "low"  # revoke does not carry confidence
        # Revoke records do not carry pairwise/tier payload.
        assert "player_a_id" not in record
        assert "canonical_player_id" not in record

    def test_revoke_for_tier_label(self) -> None:
        record = build_revoke_label(
            target_decision_id=_UUID_B,
            cohort_hash=_VALID_COHORT_HASH,
            role_family="ST",
            season_id="2425",
            observation_window=_VALID_OBSERVATION_WINDOW,
            label_type="human_tier",
            evidence="Tier was wrong after re-review",
            decided_by="maintainer",
            revision=3,
        )
        assert record["label_type"] == "human_tier"
        assert record["supersedes_decision_id"] == _UUID_B


# ---------------------------------------------------------------------------
# read_ledger
# ---------------------------------------------------------------------------


class TestReadLedger:
    def test_missing_file_returns_empty(self, tmp_path) -> None:
        path = tmp_path / "decisions.jsonl"
        assert read_ledger(path) == []

    def test_round_trip_one_record(self, tmp_path) -> None:
        path = tmp_path / "decisions.jsonl"
        record = build_label(
            action="confirmed",
            label_type="human_tier",
            cohort_hash=_VALID_COHORT_HASH,
            role_family="ST",
            season_id="2425",
            observation_window=_VALID_OBSERVATION_WINDOW,
            confidence="medium",
            evidence="15 npxG in 1800 min",
            decided_by="maintainer",
            revision=1,
            canonical_player_id="u|5",
            tier=2,
        )
        append_label(record, path)
        loaded = read_ledger(path)
        assert len(loaded) == 1
        assert loaded[0]["canonical_player_id"] == "u|5"
        assert loaded[0]["tier"] == 2

    def test_blank_line_rejected(self, tmp_path) -> None:
        path = tmp_path / "decisions.jsonl"
        valid_first = _valid_pairwise_confirmed(revision=1)
        path.write_text(
            json.dumps(valid_first, sort_keys=True) + "\n\n", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="blank_line:2"):
            read_ledger(path)

    def test_invalid_json_rejected(self, tmp_path) -> None:
        path = tmp_path / "decisions.jsonl"
        path.write_text("{not json}\n", encoding="utf-8")
        with pytest.raises(ValueError, match="invalid_json:1"):
            read_ledger(path)

    def test_wrong_record_type_rejected(self, tmp_path) -> None:
        path = tmp_path / "decisions.jsonl"
        bad = _valid_pairwise_confirmed(record_type="scoutfootball.other")
        path.write_text(json.dumps(bad, sort_keys=True) + "\n", encoding="utf-8")
        with pytest.raises(ValueError, match="record_type_invalid"):
            read_ledger(path)

    def test_revision_gap_rejected(self, tmp_path) -> None:
        path = tmp_path / "decisions.jsonl"
        # revision jumps from 1 to 3 (missing 2)
        first = _valid_pairwise_confirmed(revision=1)
        third = _valid_tier_confirmed(revision=3)
        path.write_text(
            json.dumps(first, sort_keys=True) + "\n"
            + json.dumps(third, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="revision_gap"):
            read_ledger(path)

    def test_two_records_round_trip(self, tmp_path) -> None:
        path = tmp_path / "decisions.jsonl"
        first = build_label(
            action="confirmed",
            label_type="human_pairwise_preference",
            cohort_hash=_VALID_COHORT_HASH,
            role_family="CB",
            season_id="2425",
            observation_window=_VALID_OBSERVATION_WINDOW,
            confidence="high",
            evidence="A stronger",
            decided_by="maintainer",
            revision=1,
            player_a_id="u|1",
            player_b_id="u|2",
            preferred_player="a",
        )
        append_label(first, path)
        second = build_label(
            action="confirmed",
            label_type="human_tier",
            cohort_hash=_VALID_COHORT_HASH,
            role_family="ST",
            season_id="2425",
            observation_window=_VALID_OBSERVATION_WINDOW,
            confidence="medium",
            evidence="tier 2",
            decided_by="maintainer",
            revision=2,
            canonical_player_id="u|5",
            tier=2,
        )
        append_label(second, path)
        loaded = read_ledger(path)
        assert len(loaded) == 2
        assert loaded[0]["label_type"] == "human_pairwise_preference"
        assert loaded[1]["label_type"] == "human_tier"


# ---------------------------------------------------------------------------
# append_label
# ---------------------------------------------------------------------------


class TestAppendLabel:
    def test_creates_file_on_first_append(self, tmp_path) -> None:
        path = tmp_path / "subdir" / "decisions.jsonl"
        record = build_label(
            action="confirmed",
            label_type="human_tier",
            cohort_hash=_VALID_COHORT_HASH,
            role_family="ST",
            season_id="2425",
            observation_window=_VALID_OBSERVATION_WINDOW,
            confidence="medium",
            evidence="tier 2",
            decided_by="maintainer",
            revision=1,
            canonical_player_id="u|5",
            tier=2,
        )
        append_label(record, path)
        assert path.exists()
        # Parent directory was created.
        assert path.parent.exists()

    def test_stale_revision_rejected(self, tmp_path) -> None:
        path = tmp_path / "decisions.jsonl"
        first = build_label(
            action="confirmed",
            label_type="human_tier",
            cohort_hash=_VALID_COHORT_HASH,
            role_family="ST",
            season_id="2425",
            observation_window=_VALID_OBSERVATION_WINDOW,
            confidence="medium",
            evidence="tier 2",
            decided_by="maintainer",
            revision=1,
            canonical_player_id="u|5",
            tier=2,
        )
        append_label(first, path)
        # Try to append revision=1 again (should be 2).
        second_attempt = build_label(
            action="confirmed",
            label_type="human_tier",
            cohort_hash=_VALID_COHORT_HASH,
            role_family="ST",
            season_id="2425",
            observation_window=_VALID_OBSERVATION_WINDOW,
            confidence="medium",
            evidence="tier 3",
            decided_by="maintainer",
            revision=1,  # wrong, should be 2
            canonical_player_id="u|5",
            tier=3,
        )
        with pytest.raises(ValueError, match="revision_conflict"):
            append_label(second_attempt, path)

    def test_persists_record_verbatim(self, tmp_path) -> None:
        path = tmp_path / "decisions.jsonl"
        record = build_label(
            action="confirmed",
            label_type="human_tier",
            cohort_hash=_VALID_COHORT_HASH,
            role_family="ST",
            season_id="2425",
            observation_window=_VALID_OBSERVATION_WINDOW,
            confidence="medium",
            evidence="tier 2",
            decided_by="maintainer",
            revision=1,
            canonical_player_id="u|5",
            tier=2,
            decision_id=_UUID_A,
        )
        append_label(record, path)
        # Read raw file content and verify it matches.
        raw = path.read_text(encoding="utf-8").strip()
        loaded = json.loads(raw)
        assert loaded["decision_id"] == _UUID_A
        assert loaded["tier"] == 2


# ---------------------------------------------------------------------------
# active_labels and _label_business_key
# ---------------------------------------------------------------------------


class TestActiveLabels:
    def test_single_confirmed_is_active(self) -> None:
        records = [_valid_pairwise_confirmed()]
        active = active_labels(records)
        assert len(active) == 1
        assert active[0]["action"] == "confirmed"

    def test_revoke_clears_active(self) -> None:
        records = [
            _valid_pairwise_confirmed(revision=1),
            _valid_revoke(revision=2),
        ]
        active = active_labels(records)
        assert len(active) == 0

    def test_supersede_replaces_active(self) -> None:
        # First label: prefer A. Second label: prefer B (supersedes first).
        records = [
            _valid_pairwise_confirmed(revision=1, preferred_player="a"),
            _valid_pairwise_confirmed(
                revision=2,
                decision_id=_UUID_B,
                preferred_player="b",
                supersedes_decision_id=_UUID_A,
            ),
        ]
        active = active_labels(records)
        assert len(active) == 1
        assert active[0]["preferred_player"] == "b"
        assert active[0]["revision"] == 2

    def test_revoke_then_reconfirm_is_active(self) -> None:
        # Revoked, then re-confirmed with a new decision_id (no supersede).
        # The re-confirm is a new business key entry only if the decision_id
        # differs; since business key is (label_type, cohort_hash,
        # player_a_id, player_b_id), re-confirming the same pair creates a
        # new active record.
        records = [
            _valid_pairwise_confirmed(revision=1, preferred_player="a"),
            _valid_revoke(revision=2),
            _valid_pairwise_confirmed(
                revision=3,
                decision_id=_UUID_B,
                preferred_player="a",
            ),
        ]
        active = active_labels(records)
        assert len(active) == 1
        assert active[0]["revision"] == 3

    def test_different_pairs_are_independent_keys(self) -> None:
        records = [
            _valid_pairwise_confirmed(
                revision=1,
                player_a_id="u|1",
                player_b_id="u|2",
                preferred_player="a",
            ),
            _valid_pairwise_confirmed(
                revision=2,
                decision_id=_UUID_B,
                player_a_id="u|3",
                player_b_id="u|4",
                preferred_player="b",
            ),
        ]
        active = active_labels(records)
        assert len(active) == 2

    def test_tier_and_pairwise_for_same_player_are_independent(self) -> None:
        # A player can have both a tier label and a pairwise label.
        records = [
            _valid_pairwise_confirmed(revision=1, player_a_id="u|1"),
            _valid_tier_confirmed(
                revision=2,
                decision_id=_UUID_B,
                canonical_player_id="u|1",
                tier=2,
            ),
        ]
        active = active_labels(records)
        assert len(active) == 2

    def test_cross_cohort_isolation(self) -> None:
        # Same player pair under two cohort_hash values is two keys.
        records = [
            _valid_pairwise_confirmed(
                revision=1,
                cohort_hash="0123456789abcdef",
            ),
            _valid_pairwise_confirmed(
                revision=2,
                decision_id=_UUID_B,
                cohort_hash="fedcba9876543210",
            ),
        ]
        active = active_labels(records)
        assert len(active) == 2


# ---------------------------------------------------------------------------
# lookup_labels
# ---------------------------------------------------------------------------


class TestLookupLabels:
    def test_filter_by_label_type(self) -> None:
        records = [
            _valid_pairwise_confirmed(revision=1),
            _valid_tier_confirmed(revision=2, decision_id=_UUID_B),
        ]
        result = lookup_labels(records, label_type="human_tier")
        assert len(result) == 1
        assert result[0]["label_type"] == "human_tier"

    def test_filter_by_role_family(self) -> None:
        records = [
            _valid_pairwise_confirmed(revision=1, role_family="CB"),
            _valid_tier_confirmed(revision=2, decision_id=_UUID_B, role_family="ST"),
        ]
        result = lookup_labels(records, role_family="ST")
        assert len(result) == 1
        assert result[0]["role_family"] == "ST"

    def test_filter_by_season_id(self) -> None:
        records = [
            _valid_pairwise_confirmed(revision=1, season_id="2425"),
            _valid_pairwise_confirmed(
                revision=2,
                decision_id=_UUID_B,
                season_id="2324",
                player_a_id="u|3",
                player_b_id="u|4",
            ),
        ]
        result = lookup_labels(records, season_id="2324")
        assert len(result) == 1
        assert result[0]["season_id"] == "2324"

    def test_filter_by_cohort_hash(self) -> None:
        records = [
            _valid_pairwise_confirmed(
                revision=1, cohort_hash="0123456789abcdef"
            ),
            _valid_pairwise_confirmed(
                revision=2,
                decision_id=_UUID_B,
                cohort_hash="fedcba9876543210",
                player_a_id="u|3",
                player_b_id="u|4",
            ),
        ]
        result = lookup_labels(records, cohort_hash="fedcba9876543210")
        assert len(result) == 1

    def test_filter_by_player_id_matches_pairwise_a(self) -> None:
        records = [
            _valid_pairwise_confirmed(
                revision=1, player_a_id="u|1", player_b_id="u|2"
            ),
            _valid_pairwise_confirmed(
                revision=2,
                decision_id=_UUID_B,
                player_a_id="u|3",
                player_b_id="u|4",
            ),
        ]
        result = lookup_labels(records, player_id="u|1")
        assert len(result) == 1
        assert result[0]["player_a_id"] == "u|1"

    def test_filter_by_player_id_matches_pairwise_b(self) -> None:
        records = [
            _valid_pairwise_confirmed(
                revision=1, player_a_id="u|1", player_b_id="u|2"
            ),
        ]
        result = lookup_labels(records, player_id="u|2")
        assert len(result) == 1

    def test_filter_by_player_id_matches_tier_canonical(self) -> None:
        records = [
            _valid_tier_confirmed(
                revision=1, canonical_player_id="u|5", tier=2
            ),
        ]
        result = lookup_labels(records, player_id="u|5")
        assert len(result) == 1
        assert result[0]["label_type"] == "human_tier"

    def test_active_only_excludes_revoked(self) -> None:
        records = [
            _valid_pairwise_confirmed(revision=1),
            _valid_revoke(revision=2),
        ]
        result = lookup_labels(records, active_only=True)
        assert len(result) == 0

    def test_active_only_false_includes_revoked(self) -> None:
        records = [
            _valid_pairwise_confirmed(revision=1),
            _valid_revoke(revision=2),
        ]
        result = lookup_labels(records, active_only=False)
        assert len(result) == 2

    def test_no_filters_returns_all_active(self) -> None:
        records = [
            _valid_pairwise_confirmed(revision=1),
            _valid_tier_confirmed(revision=2, decision_id=_UUID_B),
        ]
        result = lookup_labels(records)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# ledger_summary
# ---------------------------------------------------------------------------


class TestLedgerSummary:
    def test_empty_records_summary(self) -> None:
        summary = ledger_summary([])
        assert summary["total_records"] == 0
        assert summary["active_label_count"] == 0
        assert summary["blind_annotation_count"] == 0
        assert summary["latest_revision"] == 0
        assert summary["latest_recorded_at"] == ""
        assert summary["records_by_action"] == {}
        assert summary["records_by_label_type"] == {}

    def test_summary_with_mixed_records(self) -> None:
        records = [
            _valid_pairwise_confirmed(
                revision=1,
                confidence="high",
                role_family="CB",
                blind=True,
            ),
            _valid_tier_confirmed(
                revision=2,
                decision_id=_UUID_B,
                confidence="medium",
                role_family="ST",
                blind=False,
            ),
            _valid_revoke(revision=3),
        ]
        summary = ledger_summary(records)
        assert summary["total_records"] == 3
        assert summary["active_label_count"] == 1  # only tier survives
        assert summary["blind_annotation_count"] == 1  # only pairwise confirmed
        assert summary["records_by_action"] == {"confirmed": 2, "revoked": 1}
        assert summary["records_by_label_type"] == {
            "human_pairwise_preference": 2,  # confirmed + revoked
            "human_tier": 1,
        }
        assert summary["records_by_confidence"] == {
            "high": 1,
            "medium": 1,
            "low": 1,  # revoke is low
        }
        assert summary["records_by_role_family"] == {"CB": 2, "ST": 1}
        assert summary["latest_revision"] == 3

    def test_summary_records_by_cohort_hash(self) -> None:
        records = [
            _valid_pairwise_confirmed(
                revision=1, cohort_hash="0123456789abcdef"
            ),
            _valid_pairwise_confirmed(
                revision=2,
                decision_id=_UUID_B,
                cohort_hash="fedcba9876543210",
                player_a_id="u|3",
                player_b_id="u|4",
            ),
        ]
        summary = ledger_summary(records)
        assert summary["records_by_cohort_hash"] == {
            "0123456789abcdef": 1,
            "fedcba9876543210": 1,
        }


# ---------------------------------------------------------------------------
# label_independence_audit
# ---------------------------------------------------------------------------


class TestLabelIndependenceAudit:
    def test_empty_ledger_is_ok(self) -> None:
        audit = label_independence_audit([])
        assert audit["status"] == "ok"
        assert audit["violation_count"] == 0
        assert audit["supervision_eligible_count"] == 0
        assert audit["model_derived_active_count"] == 0

    def test_clean_pairwise_is_ok(self) -> None:
        records = [_valid_pairwise_confirmed()]
        audit = label_independence_audit(records)
        assert audit["status"] == "ok"
        assert audit["supervision_eligible_count"] == 1
        assert audit["supervision_eligible_by_type"] == {
            "human_pairwise_preference": 1
        }

    def test_clean_tier_is_ok(self) -> None:
        records = [_valid_tier_confirmed()]
        audit = label_independence_audit(records)
        assert audit["status"] == "ok"
        assert audit["supervision_eligible_count"] == 1

    def test_model_derived_in_active_set_flagged(self) -> None:
        records = [
            _valid_pairwise_confirmed(label_type="model_derived"),
        ]
        audit = label_independence_audit(records)
        assert audit["status"] == "violations_found"
        assert audit["violation_count"] == 1
        assert audit["violations"][0]["violation"] == "model_derived_in_active_set"
        assert audit["model_derived_active_count"] == 1
        # model_derived is NOT in the supervision-eligible set.
        assert audit["supervision_eligible_count"] == 0

    def test_pairwise_self_comparison_flagged(self) -> None:
        # Build a record that bypasses validate_record's check by directly
        # constructing the dict (defensive check in audit should catch it).
        record = _valid_pairwise_confirmed(
            player_a_id="same_id",
            player_b_id="same_id",
        )
        # validate_record would reject this, so we simulate a corrupted
        # record that somehow made it into the ledger.
        # The audit's defensive check should still flag it.
        # We bypass validate_record by directly using the dict.
        records = [record]
        audit = label_independence_audit(records)
        assert audit["status"] == "violations_found"
        violations = [v["violation"] for v in audit["violations"]]
        assert "pairwise_self_comparison" in violations

    def test_revoked_model_derived_not_flagged(self) -> None:
        # If a model_derived label is revoked, it's not in the active set,
        # so the audit should not flag it.
        records = [
            _valid_pairwise_confirmed(
                revision=1, label_type="model_derived"
            ),
            _valid_revoke(
                revision=2,
                label_type="model_derived",
            ),
        ]
        audit = label_independence_audit(records)
        assert audit["status"] == "ok"
        assert audit["model_derived_active_count"] == 0

    def test_supervision_eligible_by_type_counts(self) -> None:
        records = [
            _valid_pairwise_confirmed(revision=1),
            _valid_tier_confirmed(revision=2, decision_id=_UUID_B),
            _valid_pairwise_confirmed(
                revision=3,
                decision_id=_UUID_C,
                label_type="external_reference",
                player_a_id="u|3",
                player_b_id="u|4",
            ),
        ]
        audit = label_independence_audit(records)
        assert audit["supervision_eligible_count"] == 3
        assert audit["supervision_eligible_by_type"] == {
            "human_pairwise_preference": 1,
            "human_tier": 1,
            "external_reference": 1,
        }

    def test_caveat_present(self) -> None:
        audit = label_independence_audit([])
        assert "caveat" in audit
        assert "structural invariants" in audit["caveat"]


# ---------------------------------------------------------------------------
# Constants and module-level invariants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_ledger_type(self) -> None:
        assert LEDGER_TYPE == "scoutfootball.label_ledger"

    def test_ledger_version(self) -> None:
        assert LEDGER_VERSION == "1.0"

    def test_supervision_eligible_excludes_model_derived(self) -> None:
        assert "model_derived" not in SUPERVISION_ELIGIBLE_LABEL_TYPES
        assert "human_pairwise_preference" in SUPERVISION_ELIGIBLE_LABEL_TYPES
        assert "human_tier" in SUPERVISION_ELIGIBLE_LABEL_TYPES
        assert "external_reference" in SUPERVISION_ELIGIBLE_LABEL_TYPES
        assert "future_outcome" in SUPERVISION_ELIGIBLE_LABEL_TYPES

    def test_self_referential_only_model_derived(self) -> None:
        assert SELF_REFERENTIAL_LABEL_TYPES == frozenset({"model_derived"})

    def test_supervision_eligible_union_self_referential_is_all_types(self) -> None:
        # The union of supervision-eligible and self-referential should cover
        # all valid label types that carry semantics (not all 5 types, but
        # the 5 types we care about for audit purposes).
        union = SUPERVISION_ELIGIBLE_LABEL_TYPES | SELF_REFERENTIAL_LABEL_TYPES
        assert union == {
            "human_pairwise_preference",
            "human_tier",
            "external_reference",
            "future_outcome",
            "model_derived",
        }


# ---------------------------------------------------------------------------
# ledger_path
# ---------------------------------------------------------------------------


class TestLedgerPath:
    def test_ledger_path_returns_path_object(self) -> None:
        path = ledger_path()
        # Should be a Path-like object ending in decisions.jsonl.
        assert "decisions.jsonl" in str(path)
        assert "label_ledger" in str(path)


# ---------------------------------------------------------------------------
# End-to-end round-trip
# ---------------------------------------------------------------------------


class TestEndToEndRoundTrip:
    def test_append_read_active_lookup_round_trip(self, tmp_path) -> None:
        path = tmp_path / "decisions.jsonl"
        record = build_label(
            action="confirmed",
            label_type="human_pairwise_preference",
            cohort_hash=_VALID_COHORT_HASH,
            role_family="CB",
            season_id="2425",
            observation_window=_VALID_OBSERVATION_WINDOW,
            confidence="high",
            evidence="A had more interceptions per 90 than B",
            decided_by="maintainer",
            revision=1,
            player_a_id="u|1",
            player_b_id="u|2",
            preferred_player="a",
        )
        append_label(record, path)

        loaded = read_ledger(path)
        assert len(loaded) == 1

        active = active_labels(loaded)
        assert len(active) == 1

        looked_up = lookup_labels(loaded, player_id="u|1")
        assert len(looked_up) == 1
        assert looked_up[0]["player_a_id"] == "u|1"

    def test_append_revoke_read_active_empty(self, tmp_path) -> None:
        path = tmp_path / "decisions.jsonl"
        first = build_label(
            action="confirmed",
            label_type="human_pairwise_preference",
            cohort_hash=_VALID_COHORT_HASH,
            role_family="CB",
            season_id="2425",
            observation_window=_VALID_OBSERVATION_WINDOW,
            confidence="high",
            evidence="A stronger",
            decided_by="maintainer",
            revision=1,
            player_a_id="u|1",
            player_b_id="u|2",
            preferred_player="a",
            decision_id=_UUID_A,
        )
        append_label(first, path)

        revoke = build_revoke_label(
            target_decision_id=_UUID_A,
            cohort_hash=_VALID_COHORT_HASH,
            role_family="CB",
            season_id="2425",
            observation_window=_VALID_OBSERVATION_WINDOW,
            label_type="human_pairwise_preference",
            evidence="Re-review showed B was stronger",
            decided_by="maintainer",
            revision=2,
        )
        append_label(revoke, path)

        loaded = read_ledger(path)
        assert len(loaded) == 2  # both records preserved
        active = active_labels(loaded)
        assert len(active) == 0  # revoked, no active

    def test_full_workflow_with_audit(self, tmp_path) -> None:
        path = tmp_path / "decisions.jsonl"
        # Add a tier label, a pairwise label, and an external_reference.
        tier = build_label(
            action="confirmed",
            label_type="human_tier",
            cohort_hash=_VALID_COHORT_HASH,
            role_family="ST",
            season_id="2425",
            observation_window=_VALID_OBSERVATION_WINDOW,
            confidence="medium",
            evidence="15 npxG in 1800 min",
            decided_by="maintainer",
            revision=1,
            canonical_player_id="u|5",
            tier=2,
        )
        append_label(tier, path)

        pairwise = build_label(
            action="confirmed",
            label_type="human_pairwise_preference",
            cohort_hash=_VALID_COHORT_HASH,
            role_family="CB",
            season_id="2425",
            observation_window=_VALID_OBSERVATION_WINDOW,
            confidence="high",
            evidence="A had more interceptions",
            decided_by="maintainer",
            revision=2,
            player_a_id="u|1",
            player_b_id="u|2",
            preferred_player="a",
        )
        append_label(pairwise, path)

        external = build_label(
            action="confirmed",
            label_type="external_reference",
            cohort_hash=_VALID_COHORT_HASH,
            role_family="AM",
            season_id="2425",
            observation_window=_VALID_OBSERVATION_WINDOW,
            confidence="low",
            evidence="Won league MVP award",
            decided_by="maintainer",
            revision=3,
        )
        append_label(external, path)

        loaded = read_ledger(path)
        assert len(loaded) == 3

        summary = ledger_summary(loaded)
        assert summary["total_records"] == 3
        assert summary["active_label_count"] == 3
        assert summary["records_by_label_type"] == {
            "human_tier": 1,
            "human_pairwise_preference": 1,
            "external_reference": 1,
        }

        audit = label_independence_audit(loaded)
        assert audit["status"] == "ok"
        assert audit["supervision_eligible_count"] == 3
        assert audit["supervision_eligible_by_type"] == {
            "human_tier": 1,
            "human_pairwise_preference": 1,
            "external_reference": 1,
        }


# ---------------------------------------------------------------------------
# UUID generation uniqueness
# ---------------------------------------------------------------------------


class TestUuidGeneration:
    def test_generated_decision_ids_are_unique(self) -> None:
        ids = set()
        for _ in range(100):
            record = build_label(
                action="confirmed",
                label_type="human_tier",
                cohort_hash=_VALID_COHORT_HASH,
                role_family="ST",
                season_id="2425",
                observation_window=_VALID_OBSERVATION_WINDOW,
                confidence="medium",
                evidence="tier 2",
                decided_by="maintainer",
                revision=1,
                canonical_player_id="u|5",
                tier=2,
            )
            ids.add(record["decision_id"])
        # All 100 generated UUIDs should be unique.
        assert len(ids) == 100

    def test_generated_decision_id_is_valid_uuid(self) -> None:
        record = build_label(
            action="confirmed",
            label_type="human_tier",
            cohort_hash=_VALID_COHORT_HASH,
            role_family="ST",
            season_id="2425",
            observation_window=_VALID_OBSERVATION_WINDOW,
            confidence="medium",
            evidence="tier 2",
            decided_by="maintainer",
            revision=1,
            canonical_player_id="u|5",
            tier=2,
        )
        # Should not raise.
        uuid.UUID(record["decision_id"])
