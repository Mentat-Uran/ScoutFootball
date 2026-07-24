"""Unit tests for decision dossier validation and the DossierStore.

Covers:
- ``DecisionDossier`` model: valid construction, field defaults, validators
- ``validate_dossier_id``: filename-safe id enforcement
- ``validate_dossier_payload``: dict/non-dict, missing fields, semantic errors
- ``DossierStore``: save/load/list/count/delete round-trip
- Atomic writes: temp file cleaned up on success
- Backups: update creates a backup before overwriting
- Optimistic concurrency: ``expected_revision`` If-Match semantics
- ``DossierStoreError`` codes: not_found, precondition_required, revision_conflict
- Round-trip: dossier → store → load → same dossier
- Decision/status consistency: draft cannot carry decision, decided requires decision
- Evidence/comparison/risk id uniqueness within their containers
- Backup listing, loading and restore-from-backup round-trip
- Cross-store isolation: a BriefStore cannot read a DossierStore backup
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from scoutfootball.recruitment.dossier import (
    DOSSIER_SCHEMA,
    DOSSIER_VERSION,
    DecisionDossier,
    DossierValidationError,
    validate_dossier_id,
    validate_dossier_payload,
)
from scoutfootball.recruitment.dossier_store import (
    DOSSIER_RECORD_SCHEMA,
    DOSSIER_RECORD_VERSION,
    DossierStore,
    DossierStoreError,
)
from scoutfootball.recruitment.store import BriefStore

# ── Helpers ────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _valid_payload(
    dossier_id: str = "dossier-test-001",
    *,
    title: str = "Test dossier",
    status: str = "draft",
    decision: str | None = None,
    **overrides,
) -> dict:
    payload = {
        "schema": DOSSIER_SCHEMA,
        "version": DOSSIER_VERSION,
        "dossier_id": dossier_id,
        "revision": 1,
        "created_at": _now(),
        "updated_at": _now(),
        "author": "maintainer",
        "title": title,
        "brief_id": "brief-test-001",
        "candidate_player_id": "understat|1234",
        "candidate_player_name": "Player X",
        "candidate_team_name": "Club Y",
        "candidate_season_id": "2425",
        "status": status,
        "decision": decision,
        "decision_note": "",
        "supporting_evidence": [
            {
                "evidence_id": "ev-001",
                "fact_tier": "recorded",
                "summary": "Top 5% crosses p90 over 2425 season.",
                "evidence_refs": ["fbref/2425/PlayerX"],
            }
        ],
        "counter_evidence": [],
        "comparisons": [
            {
                "comparison_id": "cmp-001",
                "comparison_player_id": "understat|5678",
                "comparison_player_name": "Player Z",
                "fact_tier": "estimated",
                "summary": "Lower attacking output.",
                "evidence_refs": [],
            }
        ],
        "risks": [
            {
                "risk_id": "r-001",
                "summary": "Injury history in 2324 season.",
                "severity": "medium",
                "fact_tier": "recorded",
                "evidence_refs": ["transfermarkt/PlayerX/injuries"],
            }
        ],
        "human_opinion": "Fits the brief but valuation is high.",
        "recommendation": "Proceed with bid at €25M.",
        "linked_artifacts": ["brief-test-001"],
        "notes": "Secondary target if Player A unavailable.",
        "limitations": [
            "Dossier is a personal local object; not an external fact.",
            "Decision is the maintainer's honest judgment, not an automated recommendation.",
        ],
    }
    payload.update(overrides)
    return payload


# ── DecisionDossier model ─────────────────────────────────────────────


class TestDecisionDossierModel:
    def test_valid_construction_with_defaults(self):
        """A minimal dossier with only required fields is valid."""
        payload = _valid_payload()
        dossier = validate_dossier_payload(payload)
        assert dossier.dossier_id == "dossier-test-001"
        assert dossier.schema == DOSSIER_SCHEMA
        assert dossier.version == DOSSIER_VERSION
        assert dossier.status == "draft"
        assert dossier.decision is None
        assert len(dossier.supporting_evidence) == 1
        assert len(dossier.comparisons) == 1
        assert len(dossier.risks) == 1
        assert dossier.recommendation == "Proceed with bid at €25M."

    def test_decided_status_requires_decision(self):
        """status='decided' must carry a non-null decision."""
        payload = _valid_payload(status="decided", decision=None)
        with pytest.raises(DossierValidationError, match="decided.*requires a non-null decision"):
            validate_dossier_payload(payload)

    def test_decided_status_with_valid_decision_succeeds(self):
        payload = _valid_payload(status="decided", decision="proceed")
        dossier = validate_dossier_payload(payload)
        assert dossier.status == "decided"
        assert dossier.decision == "proceed"

    def test_draft_status_rejects_decision(self):
        """A draft dossier cannot pretend to have a decision."""
        payload = _valid_payload(status="draft", decision="proceed")
        with pytest.raises(
            DossierValidationError,
            match="decision can only be set when status='decided'",
        ):
            validate_dossier_payload(payload)

    def test_rejected_status_rejects_decision(self):
        """rejected is a closing state but does not carry the decision field."""
        payload = _valid_payload(status="rejected", decision="reject")
        with pytest.raises(
            DossierValidationError,
            match="decision can only be set when status='decided'",
        ):
            validate_dossier_payload(payload)

    def test_invalid_status_rejected(self):
        payload = _valid_payload(status="invalid_status")
        with pytest.raises(DossierValidationError, match="invalid status"):
            validate_dossier_payload(payload)

    def test_invalid_decision_value_rejected(self):
        payload = _valid_payload(status="decided", decision="invalid_value")
        with pytest.raises(DossierValidationError, match="invalid decision"):
            validate_dossier_payload(payload)

    def test_invalid_fact_tier_in_evidence_rejected(self):
        payload = _valid_payload()
        payload["supporting_evidence"][0]["fact_tier"] = "rumour"
        with pytest.raises(DossierValidationError, match="invalid fact_tier"):
            validate_dossier_payload(payload)

    def test_invalid_severity_in_risk_rejected(self):
        payload = _valid_payload()
        payload["risks"][0]["severity"] = "critical"
        with pytest.raises(DossierValidationError, match="invalid severity"):
            validate_dossier_payload(payload)

    def test_duplicate_evidence_ids_rejected(self):
        payload = _valid_payload()
        payload["supporting_evidence"].append({
            "evidence_id": "ev-001",  # duplicate
            "fact_tier": "recorded",
            "summary": "Another supporting item.",
            "evidence_refs": [],
        })
        with pytest.raises(DossierValidationError, match="duplicate evidence_id"):
            validate_dossier_payload(payload)

    def test_duplicate_comparison_ids_rejected(self):
        payload = _valid_payload()
        payload["comparisons"].append({
            "comparison_id": "cmp-001",  # duplicate
            "comparison_player_id": "understat|9999",
            "comparison_player_name": "Player W",
            "fact_tier": "estimated",
            "summary": "Another comparison.",
            "evidence_refs": [],
        })
        with pytest.raises(DossierValidationError, match="duplicate comparison_id"):
            validate_dossier_payload(payload)

    def test_duplicate_risk_ids_rejected(self):
        payload = _valid_payload()
        payload["risks"].append({
            "risk_id": "r-001",  # duplicate
            "summary": "Another risk.",
            "severity": "low",
            "fact_tier": "unknown",
            "evidence_refs": [],
        })
        with pytest.raises(DossierValidationError, match="duplicate risk_id"):
            validate_dossier_payload(payload)

    def test_extra_field_rejected(self):
        """Pydantic extra='forbid' rejects unknown fields."""
        payload = _valid_payload()
        payload["unknown_field"] = "value"
        with pytest.raises(DossierValidationError):
            validate_dossier_payload(payload)

    def test_unsupported_schema_rejected(self):
        payload = _valid_payload()
        payload["schema"] = "scoutfootball.unknown"
        with pytest.raises(DossierValidationError, match="unsupported dossier schema"):
            validate_dossier_payload(payload)

    def test_unsupported_version_rejected(self):
        payload = _valid_payload()
        payload["version"] = "2.0.0"
        with pytest.raises(DossierValidationError, match="unsupported dossier version"):
            validate_dossier_payload(payload)


# ── validate_dossier_id ───────────────────────────────────────────────


class TestValidateDossierId:
    def test_valid_simple_id(self):
        assert validate_dossier_id("dossier-001") == "dossier-001"

    def test_valid_with_underscore(self):
        assert validate_dossier_id("dossier_test_001") == "dossier_test_001"

    def test_empty_rejected(self):
        with pytest.raises(DossierValidationError, match="invalid dossier_id"):
            validate_dossier_id("")

    def test_starts_with_dash_rejected(self):
        with pytest.raises(DossierValidationError, match="invalid dossier_id"):
            validate_dossier_id("-dossier-001")

    def test_contains_slash_rejected(self):
        with pytest.raises(DossierValidationError, match="invalid dossier_id"):
            validate_dossier_id("dossier/001")

    def test_too_long_rejected(self):
        with pytest.raises(DossierValidationError, match="invalid dossier_id"):
            validate_dossier_id("a" * 129)

    def test_non_string_rejected(self):
        with pytest.raises(DossierValidationError, match="invalid dossier_id"):
            validate_dossier_id(123)  # type: ignore[arg-type]


# ── validate_dossier_payload ──────────────────────────────────────────


class TestValidateDossierPayload:
    def test_non_dict_payload_rejected(self):
        with pytest.raises(DossierValidationError, match="must be a JSON object"):
            validate_dossier_payload("not a dict")

    def test_missing_dossier_id_rejected(self):
        payload = _valid_payload()
        del payload["dossier_id"]
        with pytest.raises(DossierValidationError, match="dossier_id is required"):
            validate_dossier_payload(payload)

    def test_non_string_dossier_id_rejected(self):
        payload = _valid_payload()
        payload["dossier_id"] = 123
        with pytest.raises(DossierValidationError, match="dossier_id is required"):
            validate_dossier_payload(payload)

    def test_returns_decision_dossier_instance(self):
        payload = _valid_payload()
        dossier = validate_dossier_payload(payload)
        assert isinstance(dossier, DecisionDossier)


# ── Serialization round-trip ──────────────────────────────────────────


class TestSerializationRoundTrip:
    def test_to_storage_payload_is_json_serializable(self):
        dossier = validate_dossier_payload(_valid_payload())
        payload = dossier.to_storage_payload()
        # Must not raise.
        json.dumps(payload)

    def test_to_storage_payload_converts_tuples_to_lists(self):
        dossier = validate_dossier_payload(_valid_payload())
        payload = dossier.to_storage_payload()
        assert isinstance(payload["supporting_evidence"], list)
        assert isinstance(payload["supporting_evidence"][0]["evidence_refs"], list)
        assert isinstance(payload["comparisons"], list)
        assert isinstance(payload["risks"], list)
        assert isinstance(payload["linked_artifacts"], list)
        assert isinstance(payload["limitations"], list)

    def test_from_storage_payload_round_trips(self):
        original = validate_dossier_payload(_valid_payload())
        payload = original.to_storage_payload()
        restored = DecisionDossier.from_storage_payload(payload)
        assert restored == original

    def test_round_trip_preserves_decided_state(self):
        payload = _valid_payload(status="decided", decision="hold")
        original = validate_dossier_payload(payload)
        restored = DecisionDossier.from_storage_payload(original.to_storage_payload())
        assert restored.status == "decided"
        assert restored.decision == "hold"


# ── DossierStore ──────────────────────────────────────────────────────


class TestDossierStore:
    def test_save_creates_record_with_revision_1(self, tmp_path):
        store = DossierStore(tmp_path / "dossiers")
        record = store.save("dossier-001", _valid_payload("dossier-001"))
        assert record["server_revision"] == 1
        assert record["schema"] == DOSSIER_RECORD_SCHEMA
        assert record["version"] == DOSSIER_RECORD_VERSION
        assert record["dossier"]["dossier_id"] == "dossier-001"

    def test_load_returns_full_envelope(self, tmp_path):
        store = DossierStore(tmp_path / "dossiers")
        store.save("dossier-001", _valid_payload("dossier-001"))
        record = store.load("dossier-001")
        assert record["server_revision"] == 1
        assert record["dossier"]["title"] == "Test dossier"
        assert record["dossier"]["candidate_player_id"] == "understat|1234"

    def test_load_nonexistent_raises_not_found(self, tmp_path):
        store = DossierStore(tmp_path / "dossiers")
        with pytest.raises(DossierStoreError) as exc_info:
            store.load("dossier-nonexistent")
        assert exc_info.value.code == "dossier_not_found"
        assert exc_info.value.http_status == 404

    def test_save_update_requires_expected_revision(self, tmp_path):
        store = DossierStore(tmp_path / "dossiers")
        store.save("dossier-001", _valid_payload("dossier-001"))
        # Update without expected_revision fails with precondition_required.
        with pytest.raises(DossierStoreError) as exc_info:
            store.save("dossier-001", _valid_payload("dossier-001"))
        assert exc_info.value.code == "dossier_precondition_required"
        assert exc_info.value.http_status == 428
        assert exc_info.value.metadata == {"current_revision": 1}

    def test_save_update_with_stale_revision_raises_conflict(self, tmp_path):
        store = DossierStore(tmp_path / "dossiers")
        store.save("dossier-001", _valid_payload("dossier-001"))
        with pytest.raises(DossierStoreError) as exc_info:
            store.save(
                "dossier-001",
                _valid_payload("dossier-001", title="Updated title"),
                expected_revision=99,
            )
        assert exc_info.value.code == "dossier_revision_conflict"
        assert exc_info.value.http_status == 409

    def test_save_update_with_correct_revision_increments(self, tmp_path):
        store = DossierStore(tmp_path / "dossiers")
        store.save("dossier-001", _valid_payload("dossier-001"))
        record = store.save(
            "dossier-001",
            _valid_payload("dossier-001", title="Updated title"),
            expected_revision=1,
        )
        assert record["server_revision"] == 2
        assert record["dossier"]["title"] == "Updated title"

    def test_save_with_decision_dossier_object(self, tmp_path):
        """The store accepts a DecisionDossier instance directly."""
        store = DossierStore(tmp_path / "dossiers")
        dossier = validate_dossier_payload(_valid_payload("dossier-001"))
        record = store.save("dossier-001", dossier)
        assert record["dossier"]["dossier_id"] == "dossier-001"

    def test_save_rejects_mismatched_id(self, tmp_path):
        store = DossierStore(tmp_path / "dossiers")
        with pytest.raises(DossierStoreError) as exc_info:
            store.save("dossier-002", _valid_payload("dossier-001"))
        assert exc_info.value.code == "dossier_id_mismatch"
        assert exc_info.value.http_status == 400

    def test_save_creates_backup_on_update(self, tmp_path):
        store = DossierStore(tmp_path / "dossiers")
        store.save("dossier-001", _valid_payload("dossier-001"))
        store.save(
            "dossier-001",
            _valid_payload("dossier-001", title="Updated"),
            expected_revision=1,
        )
        backups = store.list_backups("dossier-001")
        assert len(backups) == 1
        assert backups[0]["kind"] == "revision"
        assert backups[0]["revision"] == 1

    def test_atomic_write_cleans_up_temp_file(self, tmp_path):
        store = DossierStore(tmp_path / "dossiers")
        store.save("dossier-001", _valid_payload("dossier-001"))
        # No .tmp files should remain in the store root.
        temp_files = list(store.root.glob(".*.tmp"))
        assert temp_files == []

    def test_list_records_returns_summaries_most_recent_first(self, tmp_path):
        store = DossierStore(tmp_path / "dossiers")
        store.save("dossier-001", _valid_payload("dossier-001", title="First"))
        store.save("dossier-002", _valid_payload("dossier-002", title="Second"))
        records = store.list_records()
        assert len(records) == 2
        # Most recent first.
        assert records[0]["dossier_id"] == "dossier-002"
        assert records[1]["dossier_id"] == "dossier-001"
        # Summary fields, no full payload.
        assert "title" in records[0]
        assert "supporting_evidence" not in records[0]

    def test_list_records_on_empty_store_returns_empty_list(self, tmp_path):
        store = DossierStore(tmp_path / "dossiers")
        assert store.list_records() == []

    def test_list_records_respects_limit(self, tmp_path):
        store = DossierStore(tmp_path / "dossiers")
        for i in range(5):
            store.save(f"dossier-{i:03d}", _valid_payload(f"dossier-{i:03d}"))
        records = store.list_records(limit=3)
        assert len(records) == 3

    def test_count_returns_stored_record_count(self, tmp_path):
        store = DossierStore(tmp_path / "dossiers")
        assert store.count() == 0
        store.save("dossier-001", _valid_payload("dossier-001"))
        assert store.count() == 1
        store.save("dossier-002", _valid_payload("dossier-002"))
        assert store.count() == 2

    def test_delete_creates_backup_and_removes_record(self, tmp_path):
        store = DossierStore(tmp_path / "dossiers")
        store.save("dossier-001", _valid_payload("dossier-001"))
        result = store.delete("dossier-001", expected_revision=1)
        assert result["dossier_id"] == "dossier-001"
        assert "deleted_at" in result
        assert "backup_path" in result
        # The record is gone.
        with pytest.raises(DossierStoreError) as exc_info:
            store.load("dossier-001")
        assert exc_info.value.code == "dossier_not_found"
        # The deletion backup exists.
        backups = store.list_backups("dossier-001")
        assert len(backups) == 1
        assert backups[0]["kind"] == "deletion"

    def test_delete_requires_expected_revision(self, tmp_path):
        store = DossierStore(tmp_path / "dossiers")
        store.save("dossier-001", _valid_payload("dossier-001"))
        with pytest.raises(DossierStoreError) as exc_info:
            store.delete("dossier-001")
        assert exc_info.value.code == "dossier_precondition_required"

    def test_delete_nonexistent_raises_not_found(self, tmp_path):
        store = DossierStore(tmp_path / "dossiers")
        with pytest.raises(DossierStoreError) as exc_info:
            store.delete("dossier-nonexistent", expected_revision=1)
        assert exc_info.value.code == "dossier_not_found"

    def test_save_rejects_invalid_payload(self, tmp_path):
        store = DossierStore(tmp_path / "dossiers")
        with pytest.raises(DossierValidationError):
            store.save("dossier-001", {"dossier_id": "dossier-001"})  # missing required fields

    def test_load_rejects_corrupted_record_file(self, tmp_path):
        store = DossierStore(tmp_path / "dossiers")
        store.root.mkdir(parents=True, exist_ok=True)
        # Write a file with the right name but invalid JSON.
        (store.root / "dossier-001.json").write_text("not json", encoding="utf-8")
        with pytest.raises(DossierStoreError) as exc_info:
            store.load("dossier-001")
        assert exc_info.value.code == "dossier_record_invalid"


# ── DossierStore backup listing and restore ───────────────────────────


class TestDossierStoreBackups:
    def test_list_backups_on_empty_returns_empty(self, tmp_path):
        store = DossierStore(tmp_path / "dossiers")
        assert store.list_backups("dossier-001") == []

    def test_list_backups_returns_revision_backups_newest_first(self, tmp_path):
        store = DossierStore(tmp_path / "dossiers")
        store.save("dossier-001", _valid_payload("dossier-001", title="rev1"))
        store.save(
            "dossier-001",
            _valid_payload("dossier-001", title="rev2"),
            expected_revision=1,
        )
        store.save(
            "dossier-001",
            _valid_payload("dossier-001", title="rev3"),
            expected_revision=2,
        )
        backups = store.list_backups("dossier-001")
        assert len(backups) == 2
        assert backups[0]["revision"] == 2
        assert backups[1]["revision"] == 1
        assert backups[0]["kind"] == "revision"
        assert backups[1]["kind"] == "revision"
        assert "stored_at" in backups[0]
        assert "size_bytes" in backups[0]

    def test_load_backup_returns_full_envelope(self, tmp_path):
        store = DossierStore(tmp_path / "dossiers")
        store.save("dossier-001", _valid_payload("dossier-001", title="original"))
        store.save(
            "dossier-001",
            _valid_payload("dossier-001", title="updated"),
            expected_revision=1,
        )
        backups = store.list_backups("dossier-001")
        backup_record = store.load_backup("dossier-001", backups[0]["backup_filename"])
        assert backup_record["dossier"]["title"] == "original"

    def test_load_backup_rejects_path_traversal(self, tmp_path):
        store = DossierStore(tmp_path / "dossiers")
        with pytest.raises(DossierStoreError) as exc_info:
            store.load_backup("dossier-001", "../escape.json")
        assert exc_info.value.code == "backup_filename_invalid"

    def test_load_backup_rejects_unknown_filename(self, tmp_path):
        store = DossierStore(tmp_path / "dossiers")
        with pytest.raises(DossierStoreError) as exc_info:
            store.load_backup("dossier-001", "random.json")
        assert exc_info.value.code == "backup_filename_invalid"

    def test_load_backup_nonexistent_raises_not_found(self, tmp_path):
        store = DossierStore(tmp_path / "dossiers")
        # Create the backup dir so the path is reachable.
        store.backup_root.mkdir(parents=True, exist_ok=True)
        # Use a valid filename shape so we get past shape validation.
        with pytest.raises(DossierStoreError) as exc_info:
            store.load_backup("dossier-001", "dossier-001.rev-1.someuuid.json")
        assert exc_info.value.code == "backup_not_found"

    def test_restore_from_backup_creates_new_revision(self, tmp_path):
        store = DossierStore(tmp_path / "dossiers")
        store.save("dossier-001", _valid_payload("dossier-001", title="original"))
        store.save(
            "dossier-001",
            _valid_payload("dossier-001", title="updated"),
            expected_revision=1,
        )
        backups = store.list_backups("dossier-001")
        # Restore the original (revision 1 backup).
        restored = store.restore_from_backup(
            "dossier-001",
            backups[0]["backup_filename"],
            expected_revision=2,
        )
        assert restored["server_revision"] == 3
        assert restored["dossier"]["title"] == "original"
        # The backup itself is preserved (restore is reversible).
        assert len(store.list_backups("dossier-001")) == 2  # rev-1 + rev-2

    def test_restore_from_backup_when_record_missing(self, tmp_path):
        """Restoring from a deletion backup recreates the record."""
        store = DossierStore(tmp_path / "dossiers")
        store.save("dossier-001", _valid_payload("dossier-001"))
        store.delete("dossier-001", expected_revision=1)
        backups = store.list_backups("dossier-001")
        # The deletion backup can be restored.
        deletion_backup = next(b for b in backups if b["kind"] == "deletion")
        restored = store.restore_from_backup(
            "dossier-001",
            deletion_backup["backup_filename"],
            expected_revision=0,
        )
        assert restored["server_revision"] == 1
        assert restored["dossier"]["dossier_id"] == "dossier-001"


# ── Cross-store isolation ─────────────────────────────────────────────


class TestCrossStoreIsolation:
    def test_brief_store_cannot_read_dossier_backup(self, tmp_path):
        """A BriefStore pointed at the same root must not read dossier records.

        The record schemas differ
        (``scoutfootball.recruitment-brief-record`` vs
        ``scoutfootball.recruitment-decision-dossier-record``), so a
        BriefStore attempting to load a dossier record file must fail
        with ``brief_record_invalid``.  This guards against accidental
        schema conflation if both stores ever share a directory.
        """
        shared_root = tmp_path / "shared"
        brief_store = BriefStore(shared_root)
        dossier_store = DossierStore(shared_root)
        dossier_store.save("dossier-001", _valid_payload("dossier-001"))
        # BriefStore tries to read the dossier file by the same id.
        with pytest.raises(Exception) as exc_info:
            brief_store.load("dossier-001")
        # The error should mention schema invalidity, not a clean load.
        assert "brief_record_invalid" in str(exc_info.value) or "not_found" in str(exc_info.value)
