"""Unit tests for the source-limited match briefing model and store.

Covers:
- ``OppositionBriefing`` model: valid construction, defaults, validators
- ``BriefingSection``: fact_tier classification, section_id taxonomy + custom
- ``validate_briefing_id``: filename-safe id enforcement
- ``validate_briefing_payload``: dict/non-dict, missing fields, semantic errors
- ``BriefingStore``: save/load/list/count/delete round-trip
- Atomic writes: temp file cleaned up on success
- Backups: update + delete create backups before overwriting/removing
- Optimistic concurrency: ``expected_revision`` If-Match semantics
- ``BriefingStoreError`` codes: not_found, precondition_required, revision_conflict,
  briefing_id_mismatch, briefing_record_invalid
- Round-trip: briefing → store → load → same briefing
- Corruption: bad JSON, wrong schema, briefing_id mismatch all caught at read
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from scoutfootball.opposition.briefing import (
    BRIEFING_SCHEMA,
    BRIEFING_VERSION,
    VALID_FACT_TIERS,
    VALID_SECTION_IDS,
    BriefingValidationError,
    OppositionBriefing,
    validate_briefing_id,
    validate_briefing_payload,
)
from scoutfootball.opposition.store import (
    BRIEFING_RECORD_SCHEMA,
    BRIEFING_RECORD_VERSION,
    BriefingStore,
    BriefingStoreError,
)

# ── Helpers ────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _valid_section(
    section_id: str = "opponent_strength",
    *,
    fact_tier: str = "recorded",
    summary: str = "Chelsea are 4th in the table.",
    evidence_refs: tuple[str, ...] = ("fbref/2026-27/Chelsea",),
) -> dict:
    return {
        "section_id": section_id,
        "fact_tier": fact_tier,
        "summary": summary,
        "evidence_refs": list(evidence_refs),
    }


def _valid_payload(
    briefing_id: str = "briefing-test-001",
    *,
    title: str = "Match briefing: Arsenal vs Chelsea",
    **overrides,
) -> dict:
    payload = {
        "schema": BRIEFING_SCHEMA,
        "version": BRIEFING_VERSION,
        "briefing_id": briefing_id,
        "revision": 1,
        "created_at": _now(),
        "updated_at": _now(),
        "author": "maintainer",
        "title": title,
        "match_id": "fd-match-64766",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "kickoff_at": "2026-08-15T15:00:00+00:00",
        "competition": "Premier League",
        "season": "2026-27",
        "sections": [
            _valid_section("opponent_strength", fact_tier="recorded"),
            _valid_section("key_players", fact_tier="official"),
        ],
        "linked_pattern_card_ids": ["pattern-chelsea-right-overload"],
        "linked_scenario_tree_id": None,
        "linked_post_match_review_id": None,
        "notes": "Watch for Chelsea's right-side overload in 4-2-3-1.",
        "limitations": [
            "Briefing is a personal local object; not an external fact.",
            "fact_tier is the maintainer's honest classification, not automated.",
        ],
    }
    payload.update(overrides)
    return payload


# ── BriefingSection / OppositionBriefing model ─────────────────────────


class TestBriefingSection:
    def test_valid_standard_section_ids_accepted(self):
        for sid in VALID_SECTION_IDS:
            section = _valid_section(sid)
            # Round-trip through the parent briefing to trigger validation.
            payload = _valid_payload(sections=[section])
            brief = validate_briefing_payload(payload)
            assert brief.sections[0].section_id == sid

    def test_fact_tier_defaults_to_unknown(self):
        section = _valid_section()
        del section["fact_tier"]
        payload = _valid_payload(sections=[section])
        brief = validate_briefing_payload(payload)
        assert brief.sections[0].fact_tier == "unknown"

    def test_invalid_fact_tier_rejected(self):
        section = _valid_section(fact_tier="rumour")
        payload = _valid_payload(sections=[section])
        with pytest.raises(BriefingValidationError):
            validate_briefing_payload(payload)

    def test_all_four_fact_tiers_accepted(self):
        for tier in VALID_FACT_TIERS:
            section = _valid_section(fact_tier=tier)
            payload = _valid_payload(sections=[section])
            brief = validate_briefing_payload(payload)
            assert brief.sections[0].fact_tier == tier

    def test_custom_section_id_accepted(self):
        section = _valid_section("custom:set_pieces_zone14")
        payload = _valid_payload(sections=[section])
        brief = validate_briefing_payload(payload)
        assert brief.sections[0].section_id == "custom:set_pieces_zone14"

    def test_custom_section_id_invalid_tail_rejected(self):
        section = _valid_section("custom:")
        payload = _valid_payload(sections=[section])
        with pytest.raises(BriefingValidationError):
            validate_briefing_payload(payload)

    def test_custom_section_id_with_slash_rejected(self):
        section = _valid_section("custom:bad/tail")
        payload = _valid_payload(sections=[section])
        with pytest.raises(BriefingValidationError):
            validate_briefing_payload(payload)

    def test_unknown_section_id_without_custom_prefix_rejected(self):
        section = _valid_section("random_section")
        payload = _valid_payload(sections=[section])
        with pytest.raises(BriefingValidationError):
            validate_briefing_payload(payload)

    def test_duplicate_section_ids_rejected(self):
        section = _valid_section("opponent_strength")
        payload = _valid_payload(sections=[section, section])
        with pytest.raises(BriefingValidationError, match="duplicate section_id"):
            validate_briefing_payload(payload)


class TestOppositionBriefingModel:
    def test_valid_briefing_construction(self):
        brief = OppositionBriefing.model_validate(_valid_payload())
        assert brief.briefing_id == "briefing-test-001"
        assert brief.home_team == "Arsenal"
        assert brief.away_team == "Chelsea"
        assert brief.competition == "Premier League"
        assert len(brief.sections) == 2

    def test_defaults_applied_for_minimal_briefing(self):
        payload = _valid_payload()
        # Strip optional fields to confirm defaults.
        for field in ("match_id", "home_team", "away_team", "competition", "season",
                      "sections", "linked_pattern_card_ids", "notes", "limitations"):
            del payload[field]
        brief = OppositionBriefing.model_validate(payload)
        assert brief.match_id == ""
        assert brief.home_team == ""
        assert brief.away_team == ""
        assert brief.competition == ""
        assert brief.sections == ()
        assert brief.linked_pattern_card_ids == ()
        assert brief.notes == ""
        assert brief.limitations == ()
        # linked_*_id default to None.
        assert brief.linked_scenario_tree_id is None
        assert brief.linked_post_match_review_id is None

    def test_kickoff_at_optional(self):
        payload = _valid_payload()
        payload["kickoff_at"] = None
        brief = OppositionBriefing.model_validate(payload)
        assert brief.kickoff_at is None

    def test_schema_constant(self):
        assert BRIEFING_SCHEMA == "scoutfootball.opposition-briefing"

    def test_version_constant(self):
        assert BRIEFING_VERSION == "1.0.0"

    def test_wrong_schema_rejected(self):
        payload = _valid_payload()
        payload["schema"] = "scoutfootball.wrong-schema"
        with pytest.raises(BriefingValidationError):
            validate_briefing_payload(payload)

    def test_wrong_version_rejected(self):
        payload = _valid_payload()
        payload["version"] = "2.0.0"
        with pytest.raises(BriefingValidationError):
            validate_briefing_payload(payload)

    def test_extra_field_rejected(self):
        payload = _valid_payload()
        payload["unknown_field"] = "value"
        with pytest.raises(BriefingValidationError):
            validate_briefing_payload(payload)

    def test_to_storage_payload_converts_tuples_to_lists(self):
        brief = OppositionBriefing.model_validate(_valid_payload())
        payload = brief.to_storage_payload()
        assert isinstance(payload["sections"], list)
        assert isinstance(payload["linked_pattern_card_ids"], list)
        assert isinstance(payload["limitations"], list)

    def test_from_storage_payload_round_trip(self):
        brief = OppositionBriefing.model_validate(_valid_payload())
        payload = brief.to_storage_payload()
        brief2 = OppositionBriefing.from_storage_payload(payload)
        assert brief2.briefing_id == brief.briefing_id
        assert brief2.title == brief.title
        assert brief2.home_team == brief.home_team
        assert len(brief2.sections) == len(brief.sections)

    def test_model_is_frozen(self):
        brief = OppositionBriefing.model_validate(_valid_payload())
        with pytest.raises((TypeError, ValueError)):
            brief.title = "changed"


# ── validate_briefing_id ───────────────────────────────────────────────


class TestValidateBriefingId:
    def test_valid_simple_id(self):
        assert validate_briefing_id("briefing-001") == "briefing-001"

    def test_valid_with_underscores_and_dashes(self):
        assert (
            validate_briefing_id("briefing_2026-07-23_abc")
            == "briefing_2026-07-23_abc"
        )

    def test_valid_alphanumeric_start(self):
        assert validate_briefing_id("a1-b2_c3") == "a1-b2_c3"

    def test_empty_rejected(self):
        with pytest.raises(BriefingValidationError):
            validate_briefing_id("")

    def test_non_string_rejected(self):
        with pytest.raises(BriefingValidationError):
            validate_briefing_id(123)

    def test_starts_with_dash_rejected(self):
        with pytest.raises(BriefingValidationError):
            validate_briefing_id("-briefing")

    def test_starts_with_dot_rejected(self):
        with pytest.raises(BriefingValidationError):
            validate_briefing_id(".briefing")

    def test_contains_slash_rejected(self):
        with pytest.raises(BriefingValidationError):
            validate_briefing_id("briefing/001")

    def test_contains_space_rejected(self):
        with pytest.raises(BriefingValidationError):
            validate_briefing_id("briefing 001")

    def test_too_long_rejected(self):
        with pytest.raises(BriefingValidationError):
            validate_briefing_id("a" * 129)

    def test_max_length_accepted(self):
        long_id = "a" * 128
        assert validate_briefing_id(long_id) == long_id


# ── validate_briefing_payload ──────────────────────────────────────────


class TestValidateBriefingPayload:
    def test_valid_payload_returns_briefing(self):
        brief = validate_briefing_payload(_valid_payload())
        assert isinstance(brief, OppositionBriefing)
        assert brief.briefing_id == "briefing-test-001"

    def test_non_dict_rejected(self):
        with pytest.raises(BriefingValidationError, match="must be a JSON object"):
            validate_briefing_payload("not a dict")

    def test_missing_briefing_id_rejected(self):
        payload = _valid_payload()
        del payload["briefing_id"]
        with pytest.raises(BriefingValidationError, match="briefing_id is required"):
            validate_briefing_payload(payload)

    def test_briefing_id_non_string_rejected(self):
        payload = _valid_payload()
        payload["briefing_id"] = 123
        with pytest.raises(BriefingValidationError, match="briefing_id is required"):
            validate_briefing_payload(payload)

    def test_invalid_briefing_id_format_rejected(self):
        payload = _valid_payload(briefing_id="invalid/id")
        with pytest.raises(BriefingValidationError):
            validate_briefing_payload(payload)

    def test_missing_required_title_rejected(self):
        payload = _valid_payload()
        del payload["title"]
        with pytest.raises(BriefingValidationError):
            validate_briefing_payload(payload)

    def test_missing_required_created_at_rejected(self):
        payload = _valid_payload()
        del payload["created_at"]
        with pytest.raises(BriefingValidationError):
            validate_briefing_payload(payload)


# ── BriefingStore: save / load ─────────────────────────────────────────


class TestBriefingStoreSaveLoad:
    def test_save_new_briefing_creates_file(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        record = store.save(
            "briefing-001", _valid_payload("briefing-001"), expected_revision=0
        )
        assert record["schema"] == BRIEFING_RECORD_SCHEMA
        assert record["version"] == BRIEFING_RECORD_VERSION
        assert record["server_revision"] == 1
        assert record["briefing"]["briefing_id"] == "briefing-001"
        assert (store.root / "briefing-001.json").exists()

    def test_load_returns_stored_record(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        store.save("briefing-001", _valid_payload("briefing-001"), expected_revision=0)
        record = store.load("briefing-001")
        assert record["briefing"]["briefing_id"] == "briefing-001"
        assert record["server_revision"] == 1

    def test_load_not_found_raises(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        with pytest.raises(BriefingStoreError) as exc_info:
            store.load("nonexistent")
        assert exc_info.value.code == "briefing_not_found"
        assert exc_info.value.http_status == 404

    def test_save_accepts_opposition_briefing_model(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        brief = OppositionBriefing.model_validate(_valid_payload("briefing-001"))
        record = store.save("briefing-001", brief, expected_revision=0)
        assert record["briefing"]["briefing_id"] == "briefing-001"

    def test_save_with_briefing_model_id_mismatch_raises(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        brief = OppositionBriefing.model_validate(_valid_payload("briefing-001"))
        with pytest.raises(BriefingStoreError, match="briefing_id_mismatch"):
            store.save("briefing-002", brief, expected_revision=0)

    def test_save_with_dict_id_mismatch_raises(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        payload = _valid_payload("briefing-001")
        with pytest.raises(BriefingStoreError, match="briefing_id_mismatch"):
            store.save("briefing-002", payload, expected_revision=0)


# ── BriefingStore: optimistic concurrency ──────────────────────────────


class TestBriefingStoreConcurrency:
    def test_update_requires_expected_revision(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        store.save("briefing-001", _valid_payload("briefing-001"), expected_revision=0)
        with pytest.raises(BriefingStoreError) as exc_info:
            store.save("briefing-001", _valid_payload("briefing-001"))
        assert exc_info.value.code == "briefing_precondition_required"
        assert exc_info.value.http_status == 428

    def test_update_with_stale_revision_raises_conflict(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        store.save("briefing-001", _valid_payload("briefing-001"), expected_revision=0)
        with pytest.raises(BriefingStoreError) as exc_info:
            store.save(
                "briefing-001", _valid_payload("briefing-001"), expected_revision=99
            )
        assert exc_info.value.code == "briefing_revision_conflict"
        assert exc_info.value.http_status == 409

    def test_update_with_correct_revision_increments(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        store.save("briefing-001", _valid_payload("briefing-001"), expected_revision=0)
        record = store.save(
            "briefing-001", _valid_payload("briefing-001"), expected_revision=1
        )
        assert record["server_revision"] == 2

    def test_new_save_with_nonzero_expected_raises_conflict(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        with pytest.raises(BriefingStoreError) as exc_info:
            store.save(
                "briefing-001", _valid_payload("briefing-001"), expected_revision=5
            )
        assert exc_info.value.code == "briefing_revision_conflict"


# ── BriefingStore: backups ─────────────────────────────────────────────


class TestBriefingStoreBackups:
    def test_update_creates_backup(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        store.save("briefing-001", _valid_payload("briefing-001"), expected_revision=0)
        assert not store.backup_root.exists()
        store.save("briefing-001", _valid_payload("briefing-001"), expected_revision=1)
        assert store.backup_root.exists()
        backups = list(store.backup_root.glob("briefing-001.rev-1.*.json"))
        assert len(backups) == 1

    def test_delete_creates_backup(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        store.save("briefing-001", _valid_payload("briefing-001"), expected_revision=0)
        store.delete("briefing-001", expected_revision=1)
        backups = list(store.backup_root.glob("briefing-001.deleted-*.json"))
        assert len(backups) == 1


# ── BriefingStore: list / count ────────────────────────────────────────


class TestBriefingStoreListCount:
    def test_count_empty_store(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        assert store.count() == 0

    def test_count_after_save(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        store.save("briefing-001", _valid_payload("briefing-001"), expected_revision=0)
        store.save("briefing-002", _valid_payload("briefing-002"), expected_revision=0)
        assert store.count() == 2

    def test_list_empty_store(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        assert store.list_records() == []

    def test_list_returns_summaries(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        store.save(
            "briefing-001",
            _valid_payload("briefing-001", title="First"),
            expected_revision=0,
        )
        records = store.list_records()
        assert len(records) == 1
        summary = records[0]
        assert summary["briefing_id"] == "briefing-001"
        assert summary["title"] == "First"
        assert summary["server_revision"] == 1
        # Summary must NOT include the full briefing payload.
        assert "briefing" not in summary
        # Summary must include key fields used by list views.
        for key in (
            "briefing_id",
            "server_revision",
            "briefing_revision",
            "title",
            "home_team",
            "away_team",
            "kickoff_at",
            "competition",
            "updated_at",
            "stored_at",
        ):
            assert key in summary

    def test_list_sorted_most_recent_first(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        store.save(
            "briefing-001", _valid_payload("briefing-001", title="First"),
            expected_revision=0,
        )
        store.save(
            "briefing-002", _valid_payload("briefing-002", title="Second"),
            expected_revision=0,
        )
        records = store.list_records()
        assert records[0]["briefing_id"] == "briefing-002"
        assert records[1]["briefing_id"] == "briefing-001"

    def test_list_respects_limit(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        for i in range(5):
            store.save(
                f"briefing-{i:03d}",
                _valid_payload(f"briefing-{i:03d}"),
                expected_revision=0,
            )
        records = store.list_records(limit=3)
        assert len(records) == 3


# ── BriefingStore: delete ──────────────────────────────────────────────


class TestBriefingStoreDelete:
    def test_delete_removes_file(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        store.save("briefing-001", _valid_payload("briefing-001"), expected_revision=0)
        store.delete("briefing-001", expected_revision=1)
        assert not (store.root / "briefing-001.json").exists()
        assert store.count() == 0

    def test_delete_not_found_raises(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        with pytest.raises(BriefingStoreError) as exc_info:
            store.delete("nonexistent", expected_revision=1)
        assert exc_info.value.code == "briefing_not_found"

    def test_delete_requires_expected_revision(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        store.save("briefing-001", _valid_payload("briefing-001"), expected_revision=0)
        with pytest.raises(BriefingStoreError) as exc_info:
            store.delete("briefing-001")
        assert exc_info.value.code == "briefing_precondition_required"

    def test_delete_returns_summary(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        store.save("briefing-001", _valid_payload("briefing-001"), expected_revision=0)
        result = store.delete("briefing-001", expected_revision=1)
        assert result["briefing_id"] == "briefing-001"
        assert result["server_revision"] == 1
        assert "deleted_at" in result
        assert "backup_path" in result


# ── BriefingStore: corrupted record handling ───────────────────────────


class TestBriefingStoreCorruption:
    def test_load_corrupted_json_raises(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        store.root.mkdir(parents=True)
        (store.root / "briefing-001.json").write_text("not json", encoding="utf-8")
        with pytest.raises(BriefingStoreError) as exc_info:
            store.load("briefing-001")
        assert exc_info.value.code == "briefing_record_invalid"

    def test_load_wrong_schema_raises(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        store.root.mkdir(parents=True)
        bad_record = {
            "schema": "wrong",
            "version": "1.0.0",
            "server_revision": 1,
            "briefing": {},
        }
        (store.root / "briefing-001.json").write_text(
            json.dumps(bad_record), encoding="utf-8"
        )
        with pytest.raises(BriefingStoreError) as exc_info:
            store.load("briefing-001")
        assert exc_info.value.code == "briefing_record_invalid"

    def test_load_briefing_id_mismatch_raises(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        store.root.mkdir(parents=True)
        record = {
            "schema": BRIEFING_RECORD_SCHEMA,
            "version": BRIEFING_RECORD_VERSION,
            "server_revision": 1,
            "stored_at": _now(),
            "briefing": _valid_payload("briefing-002"),  # ID doesn't match filename
        }
        (store.root / "briefing-001.json").write_text(
            json.dumps(record), encoding="utf-8"
        )
        with pytest.raises(BriefingStoreError) as exc_info:
            store.load("briefing-001")
        assert exc_info.value.code == "briefing_record_invalid"

    def test_list_skips_corrupted_records(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        store.save("briefing-001", _valid_payload("briefing-001"), expected_revision=0)
        # Write a corrupted file alongside the valid one.
        (store.root / "briefing-corrupt.json").write_text("bad", encoding="utf-8")
        records = store.list_records()
        assert len(records) == 1
        assert records[0]["briefing_id"] == "briefing-001"


# ── Round-trip ─────────────────────────────────────────────────────────


class TestRoundTrip:
    def test_briefing_round_trip_through_store(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        original_payload = _valid_payload("briefing-001")
        store.save("briefing-001", original_payload, expected_revision=0)
        record = store.load("briefing-001")
        loaded_brief = validate_briefing_payload(record["briefing"])
        assert loaded_brief.briefing_id == original_payload["briefing_id"]
        assert loaded_brief.title == original_payload["title"]
        assert loaded_brief.home_team == original_payload["home_team"]
        assert loaded_brief.away_team == original_payload["away_team"]
        assert loaded_brief.competition == original_payload["competition"]
        assert len(loaded_brief.sections) == len(original_payload["sections"])

    def test_briefing_id_filename_safety(self, tmp_path):
        """A briefing_id with path separators must be rejected before touching disk."""
        store = BriefingStore(tmp_path / "briefings")
        with pytest.raises(BriefingValidationError):
            store.save("../escape", _valid_payload("../escape"), expected_revision=0)

    def test_briefing_with_no_sections_round_trips(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        payload = _valid_payload("briefing-empty", sections=[])
        store.save("briefing-empty", payload, expected_revision=0)
        record = store.load("briefing-empty")
        brief = validate_briefing_payload(record["briefing"])
        assert brief.sections == ()
