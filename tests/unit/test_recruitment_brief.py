"""Unit tests for recruitment brief validation and the BriefStore.

Covers:
- ``RecruitmentBrief`` model: valid construction, field defaults, validators
- ``validate_brief_id``: filename-safe id enforcement
- ``validate_brief_payload``: dict/non-dict, missing fields, semantic errors
- ``BriefStore``: save/load/list/count/delete round-trip
- Atomic writes: temp file cleaned up on success
- Backups: update creates a backup before overwriting
- Optimistic concurrency: ``expected_revision`` If-Match semantics
- ``BriefStoreError`` codes: not_found, precondition_required, revision_conflict
- Round-trip: brief → store → load → same brief
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from scoutfootball.recruitment.brief import (
    BRIEF_SCHEMA,
    BRIEF_VERSION,
    BriefValidationError,
    RecruitmentBrief,
    validate_brief_id,
    validate_brief_payload,
)
from scoutfootball.recruitment.store import (
    BRIEF_RECORD_SCHEMA,
    BRIEF_RECORD_VERSION,
    BriefStore,
    BriefStoreError,
)

# ── Helpers ────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _valid_payload(
    brief_id: str = "brief-test-001",
    *,
    title: str = "Test brief",
    position_group: str = "DF",
    **overrides,
) -> dict:
    payload = {
        "schema": BRIEF_SCHEMA,
        "version": BRIEF_VERSION,
        "brief_id": brief_id,
        "revision": 1,
        "created_at": _now(),
        "updated_at": _now(),
        "author": "maintainer",
        "title": title,
        "team": "Arsenal",
        "position_group": position_group,
        "position_detail": "LB",
        "role": "attacking_fullback",
        "budget_eur": 30_000_000,
        "age_min": 21,
        "age_max": 27,
        "contract_years_min": 3,
        "league_preferences": ["Premier League", "La Liga"],
        "language_preferences": ["English"],
        "risk_tolerance": "medium",
        "minimum_minutes": 1500,
        "notes": "Priority window: summer 2026.",
        "limitations": ["Brief is a personal local object; not an external fact."],
    }
    payload.update(overrides)
    return payload


# ── RecruitmentBrief model ─────────────────────────────────────────────


class TestRecruitmentBriefModel:
    def test_valid_brief_construction(self):
        brief = RecruitmentBrief.model_validate(_valid_payload())
        assert brief.brief_id == "brief-test-001"
        assert brief.position_group == "DF"
        assert brief.budget_eur == 30_000_000

    def test_defaults_applied(self):
        payload = _valid_payload()
        del payload["budget_eur"]
        del payload["age_min"]
        del payload["team"]
        brief = RecruitmentBrief.model_validate(payload)
        assert brief.budget_eur is None
        assert brief.age_min is None
        assert brief.team == ""

    def test_schema_constant(self):
        assert BRIEF_SCHEMA == "scoutfootball.recruitment-brief"

    def test_version_constant(self):
        assert BRIEF_VERSION == "1.0.0"

    def test_invalid_position_group_rejected(self):
        payload = _valid_payload(position_group="XX")
        with pytest.raises(BriefValidationError):
            validate_brief_payload(payload)

    def test_invalid_risk_tolerance_rejected(self):
        payload = _valid_payload(risk_tolerance="extreme")
        with pytest.raises(BriefValidationError):
            validate_brief_payload(payload)

    def test_age_max_below_age_min_rejected(self):
        payload = _valid_payload(age_min=25, age_max=20)
        with pytest.raises(BriefValidationError):
            validate_brief_payload(payload)

    def test_extra_field_rejected(self):
        payload = _valid_payload()
        payload["unknown_field"] = "value"
        with pytest.raises(BriefValidationError):
            validate_brief_payload(payload)

    def test_to_storage_payload_converts_tuples_to_lists(self):
        brief = RecruitmentBrief.model_validate(_valid_payload())
        payload = brief.to_storage_payload()
        assert isinstance(payload["league_preferences"], list)
        assert isinstance(payload["language_preferences"], list)
        assert isinstance(payload["limitations"], list)

    def test_from_storage_payload_round_trip(self):
        brief = RecruitmentBrief.model_validate(_valid_payload())
        payload = brief.to_storage_payload()
        brief2 = RecruitmentBrief.from_storage_payload(payload)
        assert brief2.brief_id == brief.brief_id
        assert brief2.title == brief.title

    def test_model_is_frozen(self):
        brief = RecruitmentBrief.model_validate(_valid_payload())
        with pytest.raises((TypeError, ValueError)):
            brief.title = "changed"


# ── validate_brief_id ─────────────────────────────────────────────────


class TestValidateBriefId:
    def test_valid_simple_id(self):
        assert validate_brief_id("brief-001") == "brief-001"

    def test_valid_with_underscores_and_dashes(self):
        assert validate_brief_id("brief_2026-07-23_abc") == "brief_2026-07-23_abc"

    def test_valid_alphanumeric_start(self):
        assert validate_brief_id("a1-b2_c3") == "a1-b2_c3"

    def test_empty_rejected(self):
        with pytest.raises(BriefValidationError):
            validate_brief_id("")

    def test_non_string_rejected(self):
        with pytest.raises(BriefValidationError):
            validate_brief_id(123)

    def test_starts_with_dash_rejected(self):
        with pytest.raises(BriefValidationError):
            validate_brief_id("-brief")

    def test_starts_with_dot_rejected(self):
        with pytest.raises(BriefValidationError):
            validate_brief_id(".brief")

    def test_contains_slash_rejected(self):
        with pytest.raises(BriefValidationError):
            validate_brief_id("brief/001")

    def test_too_long_rejected(self):
        with pytest.raises(BriefValidationError):
            validate_brief_id("a" * 129)

    def test_max_length_accepted(self):
        long_id = "a" * 128
        assert validate_brief_id(long_id) == long_id


# ── validate_brief_payload ────────────────────────────────────────────


class TestValidateBriefPayload:
    def test_valid_payload_returns_brief(self):
        brief = validate_brief_payload(_valid_payload())
        assert isinstance(brief, RecruitmentBrief)
        assert brief.brief_id == "brief-test-001"

    def test_non_dict_rejected(self):
        with pytest.raises(BriefValidationError, match="must be a JSON object"):
            validate_brief_payload("not a dict")

    def test_missing_brief_id_rejected(self):
        payload = _valid_payload()
        del payload["brief_id"]
        with pytest.raises(BriefValidationError, match="brief_id is required"):
            validate_brief_payload(payload)

    def test_brief_id_non_string_rejected(self):
        payload = _valid_payload()
        payload["brief_id"] = 123
        with pytest.raises(BriefValidationError, match="brief_id is required"):
            validate_brief_payload(payload)

    def test_invalid_brief_id_format_rejected(self):
        payload = _valid_payload(brief_id="invalid/id")
        with pytest.raises(BriefValidationError):
            validate_brief_payload(payload)

    def test_missing_required_title_rejected(self):
        payload = _valid_payload()
        del payload["title"]
        with pytest.raises(BriefValidationError):
            validate_brief_payload(payload)

    def test_missing_required_position_group_rejected(self):
        payload = _valid_payload()
        del payload["position_group"]
        with pytest.raises(BriefValidationError):
            validate_brief_payload(payload)

    def test_wrong_schema_rejected(self):
        payload = _valid_payload()
        payload["schema"] = "scoutfootball.wrong-schema"
        with pytest.raises(BriefValidationError):
            validate_brief_payload(payload)

    def test_wrong_version_rejected(self):
        payload = _valid_payload()
        payload["version"] = "2.0.0"
        with pytest.raises(BriefValidationError):
            validate_brief_payload(payload)


# ── BriefStore: save / load ───────────────────────────────────────────


class TestBriefStoreSaveLoad:
    def test_save_new_brief_creates_file(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        record = store.save("brief-001", _valid_payload("brief-001"), expected_revision=0)
        assert record["schema"] == BRIEF_RECORD_SCHEMA
        assert record["version"] == BRIEF_RECORD_VERSION
        assert record["server_revision"] == 1
        assert record["brief"]["brief_id"] == "brief-001"
        assert (store.root / "brief-001.json").exists()

    def test_load_returns_stored_record(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_payload("brief-001"), expected_revision=0)
        record = store.load("brief-001")
        assert record["brief"]["brief_id"] == "brief-001"
        assert record["server_revision"] == 1

    def test_load_not_found_raises(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        with pytest.raises(BriefStoreError) as exc_info:
            store.load("nonexistent")
        assert exc_info.value.code == "brief_not_found"
        assert exc_info.value.http_status == 404

    def test_save_accepts_recruitment_brief_model(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        brief = RecruitmentBrief.model_validate(_valid_payload("brief-001"))
        record = store.save("brief-001", brief, expected_revision=0)
        assert record["brief"]["brief_id"] == "brief-001"

    def test_save_with_brief_model_id_mismatch_raises(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        brief = RecruitmentBrief.model_validate(_valid_payload("brief-001"))
        with pytest.raises(BriefStoreError, match="brief_id_mismatch"):
            store.save("brief-002", brief, expected_revision=0)

    def test_save_with_dict_id_mismatch_raises(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        payload = _valid_payload("brief-001")
        with pytest.raises(BriefStoreError, match="brief_id_mismatch"):
            store.save("brief-002", payload, expected_revision=0)


# ── BriefStore: optimistic concurrency ────────────────────────────────


class TestBriefStoreConcurrency:
    def test_update_requires_expected_revision(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_payload("brief-001"), expected_revision=0)
        with pytest.raises(BriefStoreError) as exc_info:
            store.save("brief-001", _valid_payload("brief-001"))
        assert exc_info.value.code == "brief_precondition_required"
        assert exc_info.value.http_status == 428

    def test_update_with_stale_revision_raises_conflict(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_payload("brief-001"), expected_revision=0)
        with pytest.raises(BriefStoreError) as exc_info:
            store.save("brief-001", _valid_payload("brief-001"), expected_revision=99)
        assert exc_info.value.code == "brief_revision_conflict"
        assert exc_info.value.http_status == 409

    def test_update_with_correct_revision_increments(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_payload("brief-001"), expected_revision=0)
        record = store.save("brief-001", _valid_payload("brief-001"), expected_revision=1)
        assert record["server_revision"] == 2

    def test_new_save_with_nonzero_expected_raises_conflict(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        with pytest.raises(BriefStoreError) as exc_info:
            store.save("brief-001", _valid_payload("brief-001"), expected_revision=5)
        assert exc_info.value.code == "brief_revision_conflict"


# ── BriefStore: backups ───────────────────────────────────────────────


class TestBriefStoreBackups:
    def test_update_creates_backup(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_payload("brief-001"), expected_revision=0)
        assert not store.backup_root.exists()
        store.save("brief-001", _valid_payload("brief-001"), expected_revision=1)
        assert store.backup_root.exists()
        backups = list(store.backup_root.glob("brief-001.rev-1.*.json"))
        assert len(backups) == 1

    def test_delete_creates_backup(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_payload("brief-001"), expected_revision=0)
        store.delete("brief-001", expected_revision=1)
        backups = list(store.backup_root.glob("brief-001.deleted-*.json"))
        assert len(backups) == 1


# ── BriefStore: list / count ──────────────────────────────────────────


class TestBriefStoreListCount:
    def test_count_empty_store(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        assert store.count() == 0

    def test_count_after_save(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_payload("brief-001"), expected_revision=0)
        store.save("brief-002", _valid_payload("brief-002"), expected_revision=0)
        assert store.count() == 2

    def test_list_empty_store(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        assert store.list_records() == []

    def test_list_returns_summaries(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_payload("brief-001", title="First"), expected_revision=0)
        records = store.list_records()
        assert len(records) == 1
        summary = records[0]
        assert summary["brief_id"] == "brief-001"
        assert summary["title"] == "First"
        assert summary["server_revision"] == 1
        assert "brief" not in summary  # Summary should NOT include the full brief

    def test_list_sorted_most_recent_first(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_payload("brief-001", title="First"), expected_revision=0)
        store.save("brief-002", _valid_payload("brief-002", title="Second"), expected_revision=0)
        records = store.list_records()
        assert records[0]["brief_id"] == "brief-002"
        assert records[1]["brief_id"] == "brief-001"

    def test_list_respects_limit(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        for i in range(5):
            store.save(f"brief-{i:03d}", _valid_payload(f"brief-{i:03d}"), expected_revision=0)
        records = store.list_records(limit=3)
        assert len(records) == 3


# ── BriefStore: delete ────────────────────────────────────────────────


class TestBriefStoreDelete:
    def test_delete_removes_file(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_payload("brief-001"), expected_revision=0)
        store.delete("brief-001", expected_revision=1)
        assert not (store.root / "brief-001.json").exists()
        assert store.count() == 0

    def test_delete_not_found_raises(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        with pytest.raises(BriefStoreError) as exc_info:
            store.delete("nonexistent", expected_revision=1)
        assert exc_info.value.code == "brief_not_found"

    def test_delete_requires_expected_revision(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_payload("brief-001"), expected_revision=0)
        with pytest.raises(BriefStoreError) as exc_info:
            store.delete("brief-001")
        assert exc_info.value.code == "brief_precondition_required"

    def test_delete_returns_summary(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_payload("brief-001"), expected_revision=0)
        result = store.delete("brief-001", expected_revision=1)
        assert result["brief_id"] == "brief-001"
        assert result["server_revision"] == 1
        assert "deleted_at" in result
        assert "backup_path" in result


# ── BriefStore: corrupted record handling ─────────────────────────────


class TestBriefStoreCorruption:
    def test_load_corrupted_json_raises(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.root.mkdir(parents=True)
        (store.root / "brief-001.json").write_text("not json", encoding="utf-8")
        with pytest.raises(BriefStoreError) as exc_info:
            store.load("brief-001")
        assert exc_info.value.code == "brief_record_invalid"

    def test_load_wrong_schema_raises(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.root.mkdir(parents=True)
        bad_record = {"schema": "wrong", "version": "1.0.0", "server_revision": 1, "brief": {}}
        (store.root / "brief-001.json").write_text(
            json.dumps(bad_record), encoding="utf-8"
        )
        with pytest.raises(BriefStoreError) as exc_info:
            store.load("brief-001")
        assert exc_info.value.code == "brief_record_invalid"

    def test_load_brief_id_mismatch_raises(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.root.mkdir(parents=True)
        record = {
            "schema": BRIEF_RECORD_SCHEMA,
            "version": BRIEF_RECORD_VERSION,
            "server_revision": 1,
            "stored_at": _now(),
            "brief": _valid_payload("brief-002"),  # ID doesn't match filename
        }
        (store.root / "brief-001.json").write_text(
            json.dumps(record), encoding="utf-8"
        )
        with pytest.raises(BriefStoreError) as exc_info:
            store.load("brief-001")
        assert exc_info.value.code == "brief_record_invalid"

    def test_list_skips_corrupted_records(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_payload("brief-001"), expected_revision=0)
        # Write a corrupted file alongside the valid one.
        (store.root / "brief-corrupt.json").write_text("bad", encoding="utf-8")
        records = store.list_records()
        assert len(records) == 1
        assert records[0]["brief_id"] == "brief-001"


# ── Round-trip ─────────────────────────────────────────────────────────


class TestRoundTrip:
    def test_brief_round_trip_through_store(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        original_payload = _valid_payload("brief-001")
        store.save("brief-001", original_payload, expected_revision=0)
        record = store.load("brief-001")
        loaded_brief = validate_brief_payload(record["brief"])
        assert loaded_brief.brief_id == original_payload["brief_id"]
        assert loaded_brief.title == original_payload["title"]
        assert loaded_brief.position_group == original_payload["position_group"]
        assert loaded_brief.budget_eur == original_payload["budget_eur"]

    def test_brief_id_filename_safety(self, tmp_path):
        """A brief_id with path separators must be rejected before touching disk."""
        store = BriefStore(tmp_path / "briefs")
        with pytest.raises(BriefValidationError):
            store.save("../escape", _valid_payload("../escape"), expected_revision=0)
