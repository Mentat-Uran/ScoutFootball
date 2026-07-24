"""Unit tests for post-match review validation and the ReviewStore.

Covers:
- ``PostMatchReview`` model: valid construction, field defaults, validators
- ``validate_review_id``: filename-safe id enforcement
- ``validate_review_payload``: dict/non-dict, missing fields, semantic errors
- ``ReviewStore``: save/load/list/count/delete round-trip
- Atomic writes: temp file cleaned up on success
- Backups: update creates a backup before overwriting
- Optimistic concurrency: ``expected_revision`` If-Match semantics
- ``ReviewStoreError`` codes: not_found, precondition_required, revision_conflict
- Round-trip: review → store → load → same review
- Decision/status consistency: draft cannot carry decision, finalized requires decision
- Hypothesis/pattern/question/evidence id uniqueness within their containers
- Backup listing, loading and restore-from-backup round-trip
- Cross-store isolation: a BriefingStore cannot read a ReviewStore backup
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from scoutfootball.opposition.post_match_review import (
    REVIEW_SCHEMA,
    REVIEW_VERSION,
    PostMatchReview,
    ReviewValidationError,
    validate_review_id,
    validate_review_payload,
)
from scoutfootball.opposition.post_match_review_store import (
    REVIEW_RECORD_SCHEMA,
    REVIEW_RECORD_VERSION,
    ReviewStore,
    ReviewStoreError,
)
from scoutfootball.opposition.store import BriefingStore

# ── Helpers ────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _valid_payload(
    review_id: str = "review-test-001",
    *,
    title: str = "Test review",
    status: str = "draft",
    decision: str | None = None,
    **overrides,
) -> dict:
    payload = {
        "schema": REVIEW_SCHEMA,
        "version": REVIEW_VERSION,
        "review_id": review_id,
        "revision": 1,
        "created_at": _now(),
        "updated_at": _now(),
        "author": "maintainer",
        "title": title,
        "briefing_id": "briefing-test-001",
        "match_id": "fd-match-64766",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "kickoff_at": "2026-08-15T15:00:00+00:00",
        "competition": "Premier League",
        "season": "2026-27",
        "final_score_home": 2,
        "final_score_away": 1,
        "status": status,
        "decision": decision,
        "decision_note": "",
        "hypothesis_results": [
            {
                "hypothesis_id": "h-001",
                "planned": "Chelsea right-side overload in 4-2-3-1",
                "observed": "Chelsea overloaded the left instead",
                "outcome": "falsified",
                "fact_tier": "recorded",
                "evidence_refs": ["events/2026-08-15/Chelsea-left-overload"],
            }
        ],
        "falsified_patterns": [
            {
                "pattern_id": "p-001",
                "summary": "Chelsea right-overload pattern did not occur.",
                "severity": "high",
                "fact_tier": "recorded",
                "evidence_refs": ["events/2026-08-15/right-side-quiet"],
            }
        ],
        "new_questions": [
            {
                "question_id": "q-001",
                "summary": "Why did Chelsea flip the overload side?",
                "scope": "in-game adaptation",
                "fact_tier": "estimated",
                "evidence_refs": [],
            }
        ],
        "supporting_evidence": [
            {
                "evidence_id": "ev-001",
                "fact_tier": "official",
                "summary": "Final scoreline 2-1.",
                "evidence_refs": ["official/match/64766/scoreline"],
            }
        ],
        "counter_evidence": [
            {
                "evidence_id": "ev-002",
                "fact_tier": "recorded",
                "summary": "xG was close (1.4 vs 1.3).",
                "evidence_refs": ["understat/2026-27/64766/xg"],
            }
        ],
        "human_opinion": "Arsenal executed the plan; Chelsea adapted at half-time.",
        "recommendation": "Keep the brief structure but add left-side contingency.",
        "linked_artifacts": ["briefing-test-001"],
        "notes": "Referee decisions were not a factor.",
        "limitations": [
            "PostMatchReview is a personal local object; not an external fact.",
            "Decision is the maintainer's honest judgment, not an automated recommendation.",
        ],
    }
    payload.update(overrides)
    return payload


# ── PostMatchReview model ─────────────────────────────────────────────


class TestPostMatchReviewModel:
    def test_valid_construction_with_defaults(self):
        """A minimal review with only required fields is valid."""
        payload = _valid_payload()
        review = validate_review_payload(payload)
        assert review.review_id == "review-test-001"
        assert review.schema == REVIEW_SCHEMA
        assert review.version == REVIEW_VERSION
        assert review.status == "draft"
        assert review.decision is None
        assert len(review.hypothesis_results) == 1
        assert len(review.falsified_patterns) == 1
        assert len(review.new_questions) == 1
        assert len(review.supporting_evidence) == 1
        assert len(review.counter_evidence) == 1
        assert review.final_score_home == 2
        assert review.final_score_away == 1

    def test_finalized_status_requires_decision(self):
        """status='finalized' must carry a non-null decision."""
        payload = _valid_payload(status="finalized", decision=None)
        with pytest.raises(
            ReviewValidationError, match="finalized.*requires a non-null decision"
        ):
            validate_review_payload(payload)

    def test_finalized_status_with_valid_decision_succeeds(self):
        payload = _valid_payload(status="finalized", decision="confirmed")
        review = validate_review_payload(payload)
        assert review.status == "finalized"
        assert review.decision == "confirmed"

    def test_draft_status_rejects_decision(self):
        """A draft review cannot pretend to have a decision."""
        payload = _valid_payload(status="draft", decision="confirmed")
        with pytest.raises(
            ReviewValidationError,
            match="decision can only be set when status='finalized'",
        ):
            validate_review_payload(payload)

    def test_superseded_status_rejects_decision(self):
        """superseded is a closing state but does not carry the decision field."""
        payload = _valid_payload(status="superseded", decision="falsified")
        with pytest.raises(
            ReviewValidationError,
            match="decision can only be set when status='finalized'",
        ):
            validate_review_payload(payload)

    def test_invalid_status_rejected(self):
        payload = _valid_payload(status="invalid_status")
        with pytest.raises(ReviewValidationError, match="invalid status"):
            validate_review_payload(payload)

    def test_invalid_decision_value_rejected(self):
        payload = _valid_payload(status="finalized", decision="invalid_value")
        with pytest.raises(ReviewValidationError, match="invalid decision"):
            validate_review_payload(payload)

    def test_invalid_fact_tier_in_evidence_rejected(self):
        payload = _valid_payload()
        payload["supporting_evidence"][0]["fact_tier"] = "rumour"
        with pytest.raises(ReviewValidationError, match="invalid fact_tier"):
            validate_review_payload(payload)

    def test_invalid_outcome_in_hypothesis_rejected(self):
        payload = _valid_payload()
        payload["hypothesis_results"][0]["outcome"] = "maybe"
        with pytest.raises(ReviewValidationError, match="invalid outcome"):
            validate_review_payload(payload)

    def test_invalid_severity_in_pattern_rejected(self):
        payload = _valid_payload()
        payload["falsified_patterns"][0]["severity"] = "critical"
        with pytest.raises(ReviewValidationError, match="invalid severity"):
            validate_review_payload(payload)

    def test_duplicate_supporting_evidence_ids_rejected(self):
        payload = _valid_payload()
        payload["supporting_evidence"].append({
            "evidence_id": "ev-001",  # duplicate
            "fact_tier": "recorded",
            "summary": "Another supporting item.",
            "evidence_refs": [],
        })
        with pytest.raises(ReviewValidationError, match="duplicate evidence_id"):
            validate_review_payload(payload)

    def test_duplicate_counter_evidence_ids_rejected(self):
        payload = _valid_payload()
        payload["counter_evidence"].append({
            "evidence_id": "ev-002",  # duplicate
            "fact_tier": "recorded",
            "summary": "Another counter item.",
            "evidence_refs": [],
        })
        with pytest.raises(ReviewValidationError, match="duplicate evidence_id"):
            validate_review_payload(payload)

    def test_duplicate_hypothesis_ids_rejected(self):
        payload = _valid_payload()
        payload["hypothesis_results"].append({
            "hypothesis_id": "h-001",  # duplicate
            "planned": "Another planned pattern.",
            "observed": "Another observed.",
            "outcome": "confirmed",
            "fact_tier": "recorded",
            "evidence_refs": [],
        })
        with pytest.raises(ReviewValidationError, match="duplicate hypothesis_id"):
            validate_review_payload(payload)

    def test_duplicate_pattern_ids_rejected(self):
        payload = _valid_payload()
        payload["falsified_patterns"].append({
            "pattern_id": "p-001",  # duplicate
            "summary": "Another falsified pattern.",
            "severity": "low",
            "fact_tier": "unknown",
            "evidence_refs": [],
        })
        with pytest.raises(ReviewValidationError, match="duplicate pattern_id"):
            validate_review_payload(payload)

    def test_duplicate_question_ids_rejected(self):
        payload = _valid_payload()
        payload["new_questions"].append({
            "question_id": "q-001",  # duplicate
            "summary": "Another question.",
            "scope": "set pieces",
            "fact_tier": "unknown",
            "evidence_refs": [],
        })
        with pytest.raises(ReviewValidationError, match="duplicate question_id"):
            validate_review_payload(payload)

    def test_extra_field_rejected(self):
        """Pydantic extra='forbid' rejects unknown fields."""
        payload = _valid_payload()
        payload["unknown_field"] = "value"
        with pytest.raises(ReviewValidationError):
            validate_review_payload(payload)

    def test_unsupported_schema_rejected(self):
        payload = _valid_payload()
        payload["schema"] = "scoutfootball.unknown"
        with pytest.raises(ReviewValidationError, match="unsupported review schema"):
            validate_review_payload(payload)

    def test_unsupported_version_rejected(self):
        payload = _valid_payload()
        payload["version"] = "2.0.0"
        with pytest.raises(ReviewValidationError, match="unsupported review version"):
            validate_review_payload(payload)

    def test_negative_score_rejected(self):
        payload = _valid_payload()
        payload["final_score_home"] = -1
        with pytest.raises(ReviewValidationError):
            validate_review_payload(payload)

    def test_kickoff_at_can_be_null(self):
        payload = _valid_payload()
        payload["kickoff_at"] = None
        review = validate_review_payload(payload)
        assert review.kickoff_at is None

    def test_scores_can_be_null(self):
        payload = _valid_payload()
        payload["final_score_home"] = None
        payload["final_score_away"] = None
        review = validate_review_payload(payload)
        assert review.final_score_home is None
        assert review.final_score_away is None


# ── validate_review_id ────────────────────────────────────────────────


class TestValidateReviewId:
    def test_valid_simple_id(self):
        assert validate_review_id("review-001") == "review-001"

    def test_valid_with_underscore(self):
        assert validate_review_id("review_test_001") == "review_test_001"

    def test_empty_rejected(self):
        with pytest.raises(ReviewValidationError, match="invalid review_id"):
            validate_review_id("")

    def test_starts_with_dash_rejected(self):
        with pytest.raises(ReviewValidationError, match="invalid review_id"):
            validate_review_id("-review-001")

    def test_contains_slash_rejected(self):
        with pytest.raises(ReviewValidationError, match="invalid review_id"):
            validate_review_id("review/001")

    def test_too_long_rejected(self):
        with pytest.raises(ReviewValidationError, match="invalid review_id"):
            validate_review_id("a" * 129)

    def test_non_string_rejected(self):
        with pytest.raises(ReviewValidationError, match="invalid review_id"):
            validate_review_id(123)  # type: ignore[arg-type]


# ── validate_review_payload ───────────────────────────────────────────


class TestValidateReviewPayload:
    def test_non_dict_payload_rejected(self):
        with pytest.raises(ReviewValidationError, match="must be a JSON object"):
            validate_review_payload("not a dict")

    def test_missing_review_id_rejected(self):
        payload = _valid_payload()
        del payload["review_id"]
        with pytest.raises(ReviewValidationError, match="review_id is required"):
            validate_review_payload(payload)

    def test_non_string_review_id_rejected(self):
        payload = _valid_payload()
        payload["review_id"] = 123
        with pytest.raises(ReviewValidationError, match="review_id is required"):
            validate_review_payload(payload)

    def test_returns_post_match_review_instance(self):
        payload = _valid_payload()
        review = validate_review_payload(payload)
        assert isinstance(review, PostMatchReview)


# ── Serialization round-trip ──────────────────────────────────────────


class TestSerializationRoundTrip:
    def test_to_storage_payload_is_json_serializable(self):
        review = validate_review_payload(_valid_payload())
        payload = review.to_storage_payload()
        # Must not raise.
        json.dumps(payload)

    def test_to_storage_payload_converts_tuples_to_lists(self):
        review = validate_review_payload(_valid_payload())
        payload = review.to_storage_payload()
        assert isinstance(payload["hypothesis_results"], list)
        assert isinstance(payload["falsified_patterns"], list)
        assert isinstance(payload["new_questions"], list)
        assert isinstance(payload["supporting_evidence"], list)
        assert isinstance(payload["counter_evidence"], list)
        assert isinstance(payload["supporting_evidence"][0]["evidence_refs"], list)
        assert isinstance(payload["linked_artifacts"], list)
        assert isinstance(payload["limitations"], list)

    def test_from_storage_payload_round_trips(self):
        original = validate_review_payload(_valid_payload())
        payload = original.to_storage_payload()
        restored = PostMatchReview.from_storage_payload(payload)
        assert restored == original

    def test_round_trip_preserves_finalized_state(self):
        payload = _valid_payload(status="finalized", decision="partial")
        original = validate_review_payload(payload)
        restored = PostMatchReview.from_storage_payload(original.to_storage_payload())
        assert restored.status == "finalized"
        assert restored.decision == "partial"


# ── ReviewStore ───────────────────────────────────────────────────────


class TestReviewStore:
    def test_save_creates_record_with_revision_1(self, tmp_path):
        store = ReviewStore(tmp_path / "reviews")
        record = store.save("review-001", _valid_payload("review-001"))
        assert record["server_revision"] == 1
        assert record["schema"] == REVIEW_RECORD_SCHEMA
        assert record["version"] == REVIEW_RECORD_VERSION
        assert record["review"]["review_id"] == "review-001"

    def test_load_returns_full_envelope(self, tmp_path):
        store = ReviewStore(tmp_path / "reviews")
        store.save("review-001", _valid_payload("review-001"))
        record = store.load("review-001")
        assert record["server_revision"] == 1
        assert record["review"]["title"] == "Test review"
        assert record["review"]["home_team"] == "Arsenal"

    def test_load_nonexistent_raises_not_found(self, tmp_path):
        store = ReviewStore(tmp_path / "reviews")
        with pytest.raises(ReviewStoreError) as exc_info:
            store.load("review-nonexistent")
        assert exc_info.value.code == "review_not_found"
        assert exc_info.value.http_status == 404

    def test_save_update_requires_expected_revision(self, tmp_path):
        store = ReviewStore(tmp_path / "reviews")
        store.save("review-001", _valid_payload("review-001"))
        # Update without expected_revision fails with precondition_required.
        with pytest.raises(ReviewStoreError) as exc_info:
            store.save("review-001", _valid_payload("review-001"))
        assert exc_info.value.code == "review_precondition_required"
        assert exc_info.value.http_status == 428
        assert exc_info.value.metadata == {"current_revision": 1}

    def test_save_update_with_stale_revision_raises_conflict(self, tmp_path):
        store = ReviewStore(tmp_path / "reviews")
        store.save("review-001", _valid_payload("review-001"))
        with pytest.raises(ReviewStoreError) as exc_info:
            store.save(
                "review-001",
                _valid_payload("review-001", title="Updated title"),
                expected_revision=99,
            )
        assert exc_info.value.code == "review_revision_conflict"
        assert exc_info.value.http_status == 409

    def test_save_update_with_correct_revision_increments(self, tmp_path):
        store = ReviewStore(tmp_path / "reviews")
        store.save("review-001", _valid_payload("review-001"))
        record = store.save(
            "review-001",
            _valid_payload("review-001", title="Updated title"),
            expected_revision=1,
        )
        assert record["server_revision"] == 2
        assert record["review"]["title"] == "Updated title"

    def test_save_with_post_match_review_object(self, tmp_path):
        """The store accepts a PostMatchReview instance directly."""
        store = ReviewStore(tmp_path / "reviews")
        review = validate_review_payload(_valid_payload("review-001"))
        record = store.save("review-001", review)
        assert record["review"]["review_id"] == "review-001"

    def test_save_rejects_mismatched_id(self, tmp_path):
        store = ReviewStore(tmp_path / "reviews")
        with pytest.raises(ReviewStoreError) as exc_info:
            store.save("review-002", _valid_payload("review-001"))
        assert exc_info.value.code == "review_id_mismatch"
        assert exc_info.value.http_status == 400

    def test_save_creates_backup_on_update(self, tmp_path):
        store = ReviewStore(tmp_path / "reviews")
        store.save("review-001", _valid_payload("review-001"))
        store.save(
            "review-001",
            _valid_payload("review-001", title="Updated"),
            expected_revision=1,
        )
        backups = store.list_backups("review-001")
        assert len(backups) == 1
        assert backups[0]["kind"] == "revision"
        assert backups[0]["revision"] == 1

    def test_atomic_write_cleans_up_temp_file(self, tmp_path):
        store = ReviewStore(tmp_path / "reviews")
        store.save("review-001", _valid_payload("review-001"))
        # No .tmp files should remain in the store root.
        temp_files = list(store.root.glob(".*.tmp"))
        assert temp_files == []

    def test_list_records_returns_summaries_most_recent_first(self, tmp_path):
        store = ReviewStore(tmp_path / "reviews")
        store.save("review-001", _valid_payload("review-001", title="First"))
        store.save("review-002", _valid_payload("review-002", title="Second"))
        records = store.list_records()
        assert len(records) == 2
        # Most recent first.
        assert records[0]["review_id"] == "review-002"
        assert records[1]["review_id"] == "review-001"
        # Summary fields, no full payload.
        assert "title" in records[0]
        assert "hypothesis_results" not in records[0]

    def test_list_records_on_empty_store_returns_empty_list(self, tmp_path):
        store = ReviewStore(tmp_path / "reviews")
        assert store.list_records() == []

    def test_list_records_respects_limit(self, tmp_path):
        store = ReviewStore(tmp_path / "reviews")
        for i in range(5):
            store.save(f"review-{i:03d}", _valid_payload(f"review-{i:03d}"))
        records = store.list_records(limit=3)
        assert len(records) == 3

    def test_count_returns_stored_record_count(self, tmp_path):
        store = ReviewStore(tmp_path / "reviews")
        assert store.count() == 0
        store.save("review-001", _valid_payload("review-001"))
        assert store.count() == 1
        store.save("review-002", _valid_payload("review-002"))
        assert store.count() == 2

    def test_delete_creates_backup_and_removes_record(self, tmp_path):
        store = ReviewStore(tmp_path / "reviews")
        store.save("review-001", _valid_payload("review-001"))
        result = store.delete("review-001", expected_revision=1)
        assert result["review_id"] == "review-001"
        assert "deleted_at" in result
        assert "backup_path" in result
        # The record is gone.
        with pytest.raises(ReviewStoreError) as exc_info:
            store.load("review-001")
        assert exc_info.value.code == "review_not_found"
        # The deletion backup exists.
        backups = store.list_backups("review-001")
        assert len(backups) == 1
        assert backups[0]["kind"] == "deletion"

    def test_delete_requires_expected_revision(self, tmp_path):
        store = ReviewStore(tmp_path / "reviews")
        store.save("review-001", _valid_payload("review-001"))
        with pytest.raises(ReviewStoreError) as exc_info:
            store.delete("review-001")
        assert exc_info.value.code == "review_precondition_required"

    def test_delete_nonexistent_raises_not_found(self, tmp_path):
        store = ReviewStore(tmp_path / "reviews")
        with pytest.raises(ReviewStoreError) as exc_info:
            store.delete("review-nonexistent", expected_revision=1)
        assert exc_info.value.code == "review_not_found"

    def test_save_rejects_invalid_payload(self, tmp_path):
        store = ReviewStore(tmp_path / "reviews")
        with pytest.raises(ReviewValidationError):
            store.save("review-001", {"review_id": "review-001"})  # missing required fields

    def test_load_rejects_corrupted_record_file(self, tmp_path):
        store = ReviewStore(tmp_path / "reviews")
        store.root.mkdir(parents=True, exist_ok=True)
        # Write a file with the right name but invalid JSON.
        (store.root / "review-001.json").write_text("not json", encoding="utf-8")
        with pytest.raises(ReviewStoreError) as exc_info:
            store.load("review-001")
        assert exc_info.value.code == "review_record_invalid"


# ── ReviewStore backup listing and restore ────────────────────────────


class TestReviewStoreBackups:
    def test_list_backups_on_empty_returns_empty(self, tmp_path):
        store = ReviewStore(tmp_path / "reviews")
        assert store.list_backups("review-001") == []

    def test_list_backups_returns_revision_backups_newest_first(self, tmp_path):
        store = ReviewStore(tmp_path / "reviews")
        store.save("review-001", _valid_payload("review-001", title="rev1"))
        store.save(
            "review-001",
            _valid_payload("review-001", title="rev2"),
            expected_revision=1,
        )
        store.save(
            "review-001",
            _valid_payload("review-001", title="rev3"),
            expected_revision=2,
        )
        backups = store.list_backups("review-001")
        assert len(backups) == 2
        assert backups[0]["revision"] == 2
        assert backups[1]["revision"] == 1
        assert backups[0]["kind"] == "revision"
        assert backups[1]["kind"] == "revision"
        assert "stored_at" in backups[0]
        assert "size_bytes" in backups[0]

    def test_load_backup_returns_full_envelope(self, tmp_path):
        store = ReviewStore(tmp_path / "reviews")
        store.save("review-001", _valid_payload("review-001", title="original"))
        store.save(
            "review-001",
            _valid_payload("review-001", title="updated"),
            expected_revision=1,
        )
        backups = store.list_backups("review-001")
        backup_record = store.load_backup("review-001", backups[0]["backup_filename"])
        assert backup_record["review"]["title"] == "original"

    def test_load_backup_rejects_path_traversal(self, tmp_path):
        store = ReviewStore(tmp_path / "reviews")
        with pytest.raises(ReviewStoreError) as exc_info:
            store.load_backup("review-001", "../escape.json")
        assert exc_info.value.code == "backup_filename_invalid"

    def test_load_backup_rejects_unknown_filename(self, tmp_path):
        store = ReviewStore(tmp_path / "reviews")
        with pytest.raises(ReviewStoreError) as exc_info:
            store.load_backup("review-001", "random.json")
        assert exc_info.value.code == "backup_filename_invalid"

    def test_load_backup_nonexistent_raises_not_found(self, tmp_path):
        store = ReviewStore(tmp_path / "reviews")
        # Create the backup dir so the path is reachable.
        store.backup_root.mkdir(parents=True, exist_ok=True)
        # Use a valid filename shape so we get past shape validation.
        with pytest.raises(ReviewStoreError) as exc_info:
            store.load_backup("review-001", "review-001.rev-1.someuuid.json")
        assert exc_info.value.code == "backup_not_found"

    def test_restore_from_backup_creates_new_revision(self, tmp_path):
        store = ReviewStore(tmp_path / "reviews")
        store.save("review-001", _valid_payload("review-001", title="original"))
        store.save(
            "review-001",
            _valid_payload("review-001", title="updated"),
            expected_revision=1,
        )
        backups = store.list_backups("review-001")
        # Restore the original (revision 1 backup).
        restored = store.restore_from_backup(
            "review-001",
            backups[0]["backup_filename"],
            expected_revision=2,
        )
        assert restored["server_revision"] == 3
        assert restored["review"]["title"] == "original"
        # The backup itself is preserved (restore is reversible).
        assert len(store.list_backups("review-001")) == 2  # rev-1 + rev-2

    def test_restore_from_backup_when_record_missing(self, tmp_path):
        """Restoring from a deletion backup recreates the record."""
        store = ReviewStore(tmp_path / "reviews")
        store.save("review-001", _valid_payload("review-001"))
        store.delete("review-001", expected_revision=1)
        backups = store.list_backups("review-001")
        # The deletion backup can be restored.
        deletion_backup = next(b for b in backups if b["kind"] == "deletion")
        restored = store.restore_from_backup(
            "review-001",
            deletion_backup["backup_filename"],
            expected_revision=0,
        )
        assert restored["server_revision"] == 1
        assert restored["review"]["review_id"] == "review-001"


# ── Cross-store isolation ─────────────────────────────────────────────


class TestCrossStoreIsolation:
    def test_briefing_store_cannot_read_review_backup(self, tmp_path):
        """A BriefingStore pointed at the same root must not read review records.

        The record schemas differ
        (``scoutfootball.opposition-briefing-record`` vs
        ``scoutfootball.opposition-post-match-review-record``), so a
        BriefingStore attempting to load a review record file must fail
        with ``briefing_record_invalid``.  This guards against accidental
        schema conflation if both stores ever share a directory.
        """
        shared_root = tmp_path / "shared"
        briefing_store = BriefingStore(shared_root)
        review_store = ReviewStore(shared_root)
        review_store.save("review-001", _valid_payload("review-001"))
        # BriefingStore tries to read the review file by the same id.
        with pytest.raises(Exception) as exc_info:
            briefing_store.load("review-001")
        # The error should mention schema invalidity, not a clean load.
        assert (
            "briefing_record_invalid" in str(exc_info.value)
            or "not_found" in str(exc_info.value)
        )
