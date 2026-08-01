"""Tests for the canonical identity registry (PRS-1 R-005 slice 2).

Covers:
- ``validate_record`` accepts valid confirmed / revoked records and rejects
  every schema violation (wrong type/version, missing fields, oversized
  fields, invalid action, revoked with canonical, bad revision).
- ``build_decision`` enforces confirmed-requires-canonical and
  revoked-cannot-select-canonical, and propagates supersedes_decision_id.
- ``read_registry`` returns [] for a missing file, validates every line,
  rejects blank lines, invalid JSON, wrong record_type, and revision gaps.
- ``append_decision`` creates the file on first append, refuses a stale
  revision (concurrent writer detection), and persists the record verbatim.
- ``lookup`` returns the latest active confirmed record, clears on revoke,
  and returns None for unresolved keys.
- ``active_canonical_map`` accumulates confirmed records and clears on
  revoke; (source, source_id) keys are isolated across sources.
- ``registry_summary`` reports counts by action and by source.
- Cross-source isolation: the same source_player_id under two source_name
  values is two independent keys.
- Round-trip: append -> read -> lookup returns the appended record.
"""

from __future__ import annotations

import json

import pytest

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.identity_registry import (
    REGISTRY_TYPE,
    REGISTRY_VERSION,
    active_canonical_map,
    append_decision,
    build_decision,
    lookup,
    read_registry,
    registry_path,
    registry_summary,
    validate_record,
)

# ---------------------------------------------------------------------------
# Valid record fixtures
# ---------------------------------------------------------------------------


def _valid_confirmed_record(**overrides) -> dict:
    base = {
        "record_type": REGISTRY_TYPE,
        "record_version": REGISTRY_VERSION,
        "decision_id": "11111111-1111-1111-1111-111111111111",
        "revision": 1,
        "recorded_at": "2026-07-31T00:00:00Z",
        "action": "confirmed",
        "source_name": "fbref",
        "source_player_id": "lara|1998|ar",
        "canonical_player_id": "canonical:fbref:lara:1998:ar",
        "evidence": "transfermarkt market-value snapshot links this fbref composite to one person",
        "decided_by": "maintainer",
        "notes": "",
    }
    base.update(overrides)
    return base


def _valid_revoked_record(**overrides) -> dict:
    base = _valid_confirmed_record(action="revoked")
    base.pop("canonical_player_id", None)
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# validate_record
# ---------------------------------------------------------------------------


class TestValidateRecord:
    def test_valid_confirmed_record_passes(self) -> None:
        record = _valid_confirmed_record()
        assert validate_record(record) is record

    def test_valid_revoked_record_without_canonical_passes(self) -> None:
        record = _valid_revoked_record()
        assert validate_record(record) is record

    def test_revoked_with_canonical_rejected(self) -> None:
        record = _valid_revoked_record(canonical_player_id="canonical:x")
        with pytest.raises(ValueError, match="revoked_cannot_select_canonical"):
            validate_record(record)

    def test_revoked_with_empty_canonical_passes(self) -> None:
        # Empty string is treated as "no canonical" for revoked.
        record = _valid_revoked_record(canonical_player_id="")
        assert validate_record(record) is record

    def test_wrong_record_type_rejected(self) -> None:
        record = _valid_confirmed_record(record_type="scoutfootball.other")
        with pytest.raises(ValueError, match="record_type_invalid"):
            validate_record(record)

    def test_wrong_record_version_rejected(self) -> None:
        record = _valid_confirmed_record(record_version="2.0")
        with pytest.raises(ValueError, match="record_version_invalid"):
            validate_record(record)

    def test_invalid_action_rejected(self) -> None:
        record = _valid_confirmed_record(action="rejected")
        with pytest.raises(ValueError, match="action_invalid"):
            validate_record(record)

    def test_missing_decision_id_rejected(self) -> None:
        record = _valid_confirmed_record()
        record.pop("decision_id")
        with pytest.raises(ValueError, match="decision_id_invalid"):
            validate_record(record)

    def test_zero_revision_rejected(self) -> None:
        record = _valid_confirmed_record(revision=0)
        with pytest.raises(ValueError, match="revision_invalid"):
            validate_record(record)

    def test_bool_revision_rejected(self) -> None:
        # bool is a subclass of int; must be rejected explicitly.
        record = _valid_confirmed_record(revision=True)
        with pytest.raises(ValueError, match="revision_invalid"):
            validate_record(record)

    def test_empty_source_name_rejected(self) -> None:
        record = _valid_confirmed_record(source_name="")
        with pytest.raises(ValueError, match="source_name_empty"):
            validate_record(record)

    def test_oversized_evidence_rejected(self) -> None:
        record = _valid_confirmed_record(evidence="x" * 501)
        with pytest.raises(ValueError, match="evidence_too_long"):
            validate_record(record)

    def test_oversized_canonical_player_id_rejected(self) -> None:
        record = _valid_confirmed_record(canonical_player_id="x" * 201)
        with pytest.raises(ValueError, match="canonical_player_id_too_long"):
            validate_record(record)

    def test_oversized_notes_rejected(self) -> None:
        record = _valid_confirmed_record(notes="x" * 501)
        with pytest.raises(ValueError, match="notes_too_long"):
            validate_record(record)

    def test_empty_decided_by_rejected(self) -> None:
        record = _valid_confirmed_record(decided_by="")
        with pytest.raises(ValueError, match="decided_by_empty"):
            validate_record(record)

    def test_missing_canonical_on_confirmed_rejected(self) -> None:
        record = _valid_confirmed_record()
        record.pop("canonical_player_id")
        with pytest.raises(ValueError, match="canonical_player_id_empty"):
            validate_record(record)

    def test_supersedes_decision_id_passes_when_set(self) -> None:
        record = _valid_confirmed_record(
            supersedes_decision_id="22222222-2222-2222-2222-222222222222"
        )
        assert validate_record(record) is record

    def test_empty_supersedes_decision_id_rejected(self) -> None:
        record = _valid_confirmed_record(supersedes_decision_id="")
        with pytest.raises(ValueError, match="supersedes_invalid"):
            validate_record(record)

    def test_non_dict_record_rejected(self) -> None:
        with pytest.raises(ValueError, match="record_not_dict"):
            validate_record("not a dict")  # type: ignore[arg-type]

    def test_notes_default_to_empty_string(self) -> None:
        # If notes is omitted entirely, validate_record should not crash.
        record = _valid_confirmed_record()
        record.pop("notes")
        # Missing notes is allowed (defaults to "").
        assert validate_record(record) is record


# ---------------------------------------------------------------------------
# build_decision
# ---------------------------------------------------------------------------


class TestBuildDecision:
    def test_confirmed_record_includes_canonical(self) -> None:
        record = build_decision(
            source_name="fbref",
            source_player_id="lara|1998|ar",
            action="confirmed",
            canonical_player_id="canonical:fbref:lara:1998:ar",
            evidence="manual review of fbref composite against transfermarkt snapshot",
            decided_by="maintainer",
            revision=1,
        )
        assert record["action"] == "confirmed"
        assert record["canonical_player_id"] == "canonical:fbref:lara:1998:ar"
        assert record["record_type"] == REGISTRY_TYPE
        assert record["record_version"] == REGISTRY_VERSION
        assert record["revision"] == 1
        assert record["decision_id"]
        assert record["recorded_at"]
        assert "supersedes_decision_id" not in record

    def test_confirmed_without_canonical_raises(self) -> None:
        with pytest.raises(ValueError, match="confirmed_requires_canonical"):
            build_decision(
                source_name="fbref",
                source_player_id="x",
                action="confirmed",
                canonical_player_id=None,
                evidence="some evidence",
                decided_by="maintainer",
                revision=1,
            )

    def test_revoked_record_omits_canonical(self) -> None:
        record = build_decision(
            source_name="fbref",
            source_player_id="lara|1998|ar",
            action="revoked",
            canonical_player_id=None,
            evidence="previous mapping was wrong; no replacement yet",
            decided_by="maintainer",
            revision=2,
        )
        assert record["action"] == "revoked"
        assert "canonical_player_id" not in record

    def test_revoked_with_canonical_raises(self) -> None:
        with pytest.raises(ValueError, match="revoked_cannot_select_canonical"):
            build_decision(
                source_name="fbref",
                source_player_id="x",
                action="revoked",
                canonical_player_id="canonical:x",
                evidence="some evidence",
                decided_by="maintainer",
                revision=2,
            )

    def test_supersedes_decision_id_propagated(self) -> None:
        record = build_decision(
            source_name="fbref",
            source_player_id="x",
            action="confirmed",
            canonical_player_id="canonical:x",
            evidence="corrected mapping after re-review",
            decided_by="maintainer",
            revision=2,
            supersedes_decision_id="22222222-2222-2222-2222-222222222222",
        )
        assert record["supersedes_decision_id"] == "22222222-2222-2222-2222-222222222222"

    def test_invalid_action_raises(self) -> None:
        with pytest.raises(ValueError, match="action_invalid"):
            build_decision(
                source_name="fbref",
                source_player_id="x",
                action="rejected",
                canonical_player_id=None,
                evidence="some evidence",
                decided_by="maintainer",
                revision=1,
            )


# ---------------------------------------------------------------------------
# read_registry
# ---------------------------------------------------------------------------


class TestReadRegistry:
    def test_missing_file_returns_empty(self, tmp_path) -> None:
        path = tmp_path / "decisions.jsonl"
        assert read_registry(path) == []

    def test_round_trip_one_record(self, tmp_path) -> None:
        path = tmp_path / "decisions.jsonl"
        record = build_decision(
            source_name="fbref",
            source_player_id="lara|1998|ar",
            action="confirmed",
            canonical_player_id="canonical:fbref:lara:1998:ar",
            evidence="manual review",
            decided_by="maintainer",
            revision=1,
        )
        append_decision(record, path)
        loaded = read_registry(path)
        assert len(loaded) == 1
        assert loaded[0]["source_player_id"] == "lara|1998|ar"
        assert loaded[0]["canonical_player_id"] == "canonical:fbref:lara:1998:ar"

    def test_blank_line_rejected(self, tmp_path) -> None:
        path = tmp_path / "decisions.jsonl"
        valid_first = _valid_confirmed_record(revision=1)
        path.write_text(
            json.dumps(valid_first) + "\n\n", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="blank_line:2"):
            read_registry(path)

    def test_invalid_json_rejected(self, tmp_path) -> None:
        path = tmp_path / "decisions.jsonl"
        path.write_text("{not json}\n", encoding="utf-8")
        with pytest.raises(ValueError, match="invalid_json:1"):
            read_registry(path)

    def test_wrong_record_type_rejected(self, tmp_path) -> None:
        path = tmp_path / "decisions.jsonl"
        bad = _valid_confirmed_record(record_type="scoutfootball.other")
        path.write_text(json.dumps(bad) + "\n", encoding="utf-8")
        with pytest.raises(ValueError, match="record_invalid:1"):
            read_registry(path)

    def test_revision_gap_rejected(self, tmp_path) -> None:
        path = tmp_path / "decisions.jsonl"
        r1 = _valid_confirmed_record(revision=1)
        r2 = _valid_confirmed_record(revision=5)  # gap
        path.write_text(
            json.dumps(r1) + "\n" + json.dumps(r2) + "\n", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="revision_gap:2"):
            read_registry(path)

    def test_read_via_settings(self, tmp_path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        path = registry_path(settings)
        assert path == tmp_path / "data" / "gold" / "identity_registry" / "decisions.jsonl"
        # No file yet → empty.
        assert read_registry(settings=settings) == []
        record = build_decision(
            source_name="understat",
            source_player_id="understat|12345",
            action="confirmed",
            canonical_player_id="canonical:understat:12345",
            evidence="transfermarkt id 12345 cross-checked",
            decided_by="maintainer",
            revision=1,
        )
        append_decision(record, settings=settings)
        loaded = read_registry(settings=settings)
        assert len(loaded) == 1
        assert loaded[0]["source_player_id"] == "understat|12345"

    def test_read_requires_path_or_settings(self) -> None:
        with pytest.raises(ValueError, match="read_requires_path_or_settings"):
            read_registry()


# ---------------------------------------------------------------------------
# append_decision
# ---------------------------------------------------------------------------


class TestAppendDecision:
    def test_first_append_creates_file_and_parent(self, tmp_path) -> None:
        path = tmp_path / "nested" / "dir" / "decisions.jsonl"
        record = build_decision(
            source_name="fbref",
            source_player_id="x",
            action="confirmed",
            canonical_player_id="canonical:x",
            evidence="some evidence",
            decided_by="maintainer",
            revision=1,
        )
        append_decision(record, path)
        assert path.exists()
        line = path.read_text(encoding="utf-8").strip()
        loaded = json.loads(line)
        assert loaded["decision_id"] == record["decision_id"]
        assert loaded["canonical_player_id"] == "canonical:x"

    def test_stale_revision_rejected(self, tmp_path) -> None:
        path = tmp_path / "decisions.jsonl"
        r1 = build_decision(
            source_name="fbref",
            source_player_id="x",
            action="confirmed",
            canonical_player_id="canonical:x",
            evidence="first",
            decided_by="maintainer",
            revision=1,
        )
        append_decision(r1, path)
        # Another writer appends revision 2.
        r2 = build_decision(
            source_name="fbref",
            source_player_id="y",
            action="confirmed",
            canonical_player_id="canonical:y",
            evidence="second",
            decided_by="maintainer",
            revision=2,
        )
        append_decision(r2, path)
        # Caller that computed revision=2 before r2 landed now tries to write.
        stale = build_decision(
            source_name="fbref",
            source_player_id="z",
            action="confirmed",
            canonical_player_id="canonical:z",
            evidence="stale",
            decided_by="maintainer",
            revision=2,
        )
        with pytest.raises(ValueError, match="revision_conflict:2:expected:3"):
            append_decision(stale, path)

    def test_append_preserves_record_verbatim(self, tmp_path) -> None:
        path = tmp_path / "decisions.jsonl"
        record = build_decision(
            source_name="fbref",
            source_player_id="lara|1998|ar",
            action="confirmed",
            canonical_player_id="canonical:fbref:lara:1998:ar",
            evidence="manual review evidence",
            decided_by="maintainer",
            notes="optional note",
            revision=1,
            supersedes_decision_id="22222222-2222-2222-2222-222222222222",
        )
        append_decision(record, path)
        # Re-read and check every field survived the JSONL round-trip.
        loaded = read_registry(path)
        assert len(loaded) == 1
        for key, value in record.items():
            assert loaded[0][key] == value

    def test_keys_sorted_in_file(self, tmp_path) -> None:
        # sort_keys=True ensures deterministic file content for diff/review.
        path = tmp_path / "decisions.jsonl"
        record = build_decision(
            source_name="fbref",
            source_player_id="x",
            action="confirmed",
            canonical_player_id="canonical:x",
            evidence="e",
            decided_by="maintainer",
            revision=1,
        )
        append_decision(record, path)
        line = path.read_text(encoding="utf-8").strip()
        keys = list(json.loads(line).keys())
        assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# lookup
# ---------------------------------------------------------------------------


class TestLookup:
    def test_unresolved_key_returns_none(self) -> None:
        records: list[dict] = []
        assert lookup(records, source_name="fbref", source_player_id="x") is None

    def test_confirmed_returns_record(self) -> None:
        records = [
            _valid_confirmed_record(source_name="fbref", source_player_id="x"),
        ]
        result = lookup(records, source_name="fbref", source_player_id="x")
        assert result is not None
        assert result["canonical_player_id"] == "canonical:fbref:lara:1998:ar"

    def test_revoked_clears_active_mapping(self) -> None:
        records = [
            _valid_confirmed_record(
                source_name="fbref",
                source_player_id="x",
                revision=1,
            ),
            _valid_revoked_record(
                source_name="fbref",
                source_player_id="x",
                revision=2,
            ),
        ]
        assert lookup(records, source_name="fbref", source_player_id="x") is None

    def test_latest_confirmed_wins(self) -> None:
        records = [
            _valid_confirmed_record(
                source_name="fbref",
                source_player_id="x",
                canonical_player_id="canonical:old",
                revision=1,
            ),
            _valid_confirmed_record(
                source_name="fbref",
                source_player_id="x",
                canonical_player_id="canonical:new",
                revision=2,
            ),
        ]
        result = lookup(records, source_name="fbref", source_player_id="x")
        assert result is not None
        assert result["canonical_player_id"] == "canonical:new"

    def test_revoke_then_reconfirm_restores_mapping(self) -> None:
        records = [
            _valid_confirmed_record(
                source_name="fbref",
                source_player_id="x",
                canonical_player_id="canonical:first",
                revision=1,
            ),
            _valid_revoked_record(
                source_name="fbref",
                source_player_id="x",
                revision=2,
            ),
            _valid_confirmed_record(
                source_name="fbref",
                source_player_id="x",
                canonical_player_id="canonical:second",
                revision=3,
            ),
        ]
        result = lookup(records, source_name="fbref", source_player_id="x")
        assert result is not None
        assert result["canonical_player_id"] == "canonical:second"

    def test_cross_source_isolation(self) -> None:
        # Same source_player_id under different source_name is two keys.
        records = [
            _valid_confirmed_record(
                source_name="fbref",
                source_player_id="lara",
                canonical_player_id="canonical:fbref:lara",
                revision=1,
            ),
            _valid_confirmed_record(
                source_name="understat",
                source_player_id="lara",
                canonical_player_id="canonical:understat:lara",
                revision=2,
            ),
        ]
        fbref_result = lookup(records, source_name="fbref", source_player_id="lara")
        understat_result = lookup(records, source_name="understat", source_player_id="lara")
        assert fbref_result is not None
        assert understat_result is not None
        assert fbref_result["canonical_player_id"] != understat_result["canonical_player_id"]

    def test_revoked_for_one_key_does_not_affect_other(self) -> None:
        records = [
            _valid_confirmed_record(
                source_name="fbref",
                source_player_id="x",
                canonical_player_id="canonical:x",
                revision=1,
            ),
            _valid_confirmed_record(
                source_name="fbref",
                source_player_id="y",
                canonical_player_id="canonical:y",
                revision=2,
            ),
            _valid_revoked_record(
                source_name="fbref",
                source_player_id="x",
                revision=3,
            ),
        ]
        assert lookup(records, source_name="fbref", source_player_id="x") is None
        result = lookup(records, source_name="fbref", source_player_id="y")
        assert result is not None
        assert result["canonical_player_id"] == "canonical:y"


# ---------------------------------------------------------------------------
# active_canonical_map
# ---------------------------------------------------------------------------


class TestActiveCanonicalMap:
    def test_empty_records_returns_empty_map(self) -> None:
        assert active_canonical_map([]) == {}

    def test_confirmed_records_accumulate(self) -> None:
        records = [
            _valid_confirmed_record(
                source_name="fbref",
                source_player_id="x",
                canonical_player_id="canonical:x",
                revision=1,
            ),
            _valid_confirmed_record(
                source_name="understat",
                source_player_id="understat|9",
                canonical_player_id="canonical:understat:9",
                revision=2,
            ),
        ]
        result = active_canonical_map(records)
        assert result == {
            ("fbref", "x"): "canonical:x",
            ("understat", "understat|9"): "canonical:understat:9",
        }

    def test_revoked_record_clears_key(self) -> None:
        records = [
            _valid_confirmed_record(
                source_name="fbref",
                source_player_id="x",
                canonical_player_id="canonical:x",
                revision=1,
            ),
            _valid_revoked_record(
                source_name="fbref",
                source_player_id="x",
                revision=2,
            ),
        ]
        assert active_canonical_map(records) == {}

    def test_correction_replaces_value(self) -> None:
        records = [
            _valid_confirmed_record(
                source_name="fbref",
                source_player_id="x",
                canonical_player_id="canonical:wrong",
                revision=1,
            ),
            _valid_confirmed_record(
                source_name="fbref",
                source_player_id="x",
                canonical_player_id="canonical:right",
                revision=2,
            ),
        ]
        assert active_canonical_map(records) == {("fbref", "x"): "canonical:right"}


# ---------------------------------------------------------------------------
# registry_summary
# ---------------------------------------------------------------------------


class TestRegistrySummary:
    def test_empty_registry_summary(self) -> None:
        summary = registry_summary([])
        assert summary["schema"] == REGISTRY_TYPE
        assert summary["schema_version"] == REGISTRY_VERSION
        assert summary["total_records"] == 0
        assert summary["active_mapping_count"] == 0
        assert summary["records_by_action"] == {"confirmed": 0, "revoked": 0}
        assert summary["active_mappings_by_source"] == {}
        assert summary["latest_revision"] == 0
        assert summary["latest_recorded_at"] is None

    def test_summary_with_mixed_actions(self) -> None:
        records = [
            _valid_confirmed_record(
                source_name="fbref",
                source_player_id="x",
                canonical_player_id="canonical:x",
                revision=1,
            ),
            _valid_confirmed_record(
                source_name="understat",
                source_player_id="understat|9",
                canonical_player_id="canonical:understat:9",
                revision=2,
            ),
            _valid_revoked_record(
                source_name="fbref",
                source_player_id="x",
                revision=3,
            ),
        ]
        summary = registry_summary(records)
        assert summary["total_records"] == 3
        assert summary["active_mapping_count"] == 1  # only understat remains
        assert summary["records_by_action"] == {"confirmed": 2, "revoked": 1}
        assert summary["active_mappings_by_source"] == {"understat": 1}
        assert summary["latest_revision"] == 3
        assert summary["latest_recorded_at"] == records[-1]["recorded_at"]


# ---------------------------------------------------------------------------
# End-to-end round-trip via PlatformSettings
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_append_then_lookup_returns_record(self, tmp_path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        # No file yet.
        assert read_registry(settings=settings) == []

        # Append one confirmed mapping.
        r1 = build_decision(
            source_name="fbref",
            source_player_id="lara|1998|ar",
            action="confirmed",
            canonical_player_id="canonical:fbref:lara:1998:ar",
            evidence="transfermarkt snapshot 2026-07-31 row 12 maps to this fbref composite",
            decided_by="maintainer",
            revision=1,
        )
        append_decision(r1, settings=settings)

        # Lookup must return it.
        loaded = read_registry(settings=settings)
        result = lookup(
            loaded,
            source_name="fbref",
            source_player_id="lara|1998|ar",
        )
        assert result is not None
        assert result["decision_id"] == r1["decision_id"]

        # Unrelated key is unresolved.
        assert lookup(
            loaded,
            source_name="fbref",
            source_player_id="someone_else",
        ) is None

        # Revoke it.
        r2 = build_decision(
            source_name="fbref",
            source_player_id="lara|1998|ar",
            action="revoked",
            canonical_player_id=None,
            evidence="recheck showed the fbref composite was actually two different people",
            decided_by="maintainer",
            revision=2,
            supersedes_decision_id=r1["decision_id"],
        )
        append_decision(r2, settings=settings)

        loaded = read_registry(settings=settings)
        assert lookup(
            loaded,
            source_name="fbref",
            source_player_id="lara|1998|ar",
        ) is None
        assert active_canonical_map(loaded) == {}
        summary = registry_summary(loaded)
        assert summary["total_records"] == 2
        assert summary["active_mapping_count"] == 0
        assert summary["records_by_action"] == {"confirmed": 1, "revoked": 1}

    def test_file_path_under_gold_identity_registry(self, tmp_path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        path = registry_path(settings)
        assert path == (
            tmp_path / "data" / "gold" / "identity_registry" / "decisions.jsonl"
        )


# ---------------------------------------------------------------------------
# Schema stability
# ---------------------------------------------------------------------------


class TestSchemaStability:
    def test_registry_type_constant(self) -> None:
        assert REGISTRY_TYPE == "scoutfootball.identity_registry"

    def test_registry_version_constant(self) -> None:
        assert REGISTRY_VERSION == "1.0"

    def test_record_serializes_to_json(self) -> None:
        # Every value must be JSON-serializable for the JSONL format.
        record = build_decision(
            source_name="fbref",
            source_player_id="x",
            action="confirmed",
            canonical_player_id="canonical:x",
            evidence="e",
            decided_by="maintainer",
            notes="n",
            revision=1,
            supersedes_decision_id="22222222-2222-2222-2222-222222222222",
        )
        text = json.dumps(record, ensure_ascii=False, sort_keys=True)
        # Round-trips.
        assert json.loads(text) == record
