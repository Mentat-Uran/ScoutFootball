"""Unit tests for :mod:`scoutfootball.storage.record_diff`.

Covers:
- Empty / None inputs
- Envelope-only changes (revision bump, stored_at change)
- Payload key detection (``brief`` vs ``briefing`` vs ambiguous)
- Dict additions / removals / changes
- List additions / removals / element changes
- Nested structures
- Shape mismatches (dict vs list vs scalar)
- JSON normalisation (key ordering, scalar type strictness)
- Sort order of the returned entries
"""

from __future__ import annotations

from scoutfootball.storage.record_diff import diff_records


def _envelope(payload_key: str, payload, *, revision=1, stored_at="2026-07-23T10:00:00+00:00"):
    return {
        "schema": f"scoutfootball.{payload_key}-record",
        "version": "1.0.0",
        "server_revision": revision,
        "stored_at": stored_at,
        payload_key: payload,
    }


# ── Empty / None ───────────────────────────────────────────────────────


class TestDiffEmpty:
    def test_both_none_returns_empty(self):
        assert diff_records(None, None) == []

    def test_old_none_is_added(self):
        new = _envelope("brief", {"brief_id": "b1"})
        result = diff_records(None, new)
        assert len(result) == 1
        assert result[0]["change"] == "added"
        assert result[0]["new"] is new

    def test_new_none_is_removed(self):
        old = _envelope("brief", {"brief_id": "b1"})
        result = diff_records(old, None)
        assert len(result) == 1
        assert result[0]["change"] == "removed"
        assert result[0]["old"] is old


# ── Envelope-level changes ────────────────────────────────────────────


class TestDiffEnvelope:
    def test_revision_change_produces_envelope_entry(self):
        old = _envelope("brief", {"brief_id": "b1", "title": "x"}, revision=1)
        new = _envelope("brief", {"brief_id": "b1", "title": "x"}, revision=2)
        result = diff_records(old, new)
        # Only the envelope entry; payload is identical.
        assert len(result) == 1
        assert result[0]["path"] == "__envelope__"
        assert result[0]["change"] == "changed"
        assert result[0]["old"]["server_revision"] == 1
        assert result[0]["new"]["server_revision"] == 2

    def test_stored_at_change_produces_envelope_entry(self):
        old = _envelope("brief", {"brief_id": "b1"}, stored_at="2026-07-23T10:00:00+00:00")
        new = _envelope("brief", {"brief_id": "b1"}, stored_at="2026-07-23T11:00:00+00:00")
        result = diff_records(old, new)
        assert len(result) == 1
        assert result[0]["path"] == "__envelope__"

    def test_identical_records_return_empty(self):
        old = _envelope("brief", {"brief_id": "b1", "title": "x"})
        new = _envelope("brief", {"brief_id": "b1", "title": "x"})
        assert diff_records(old, new) == []


# ── Payload key detection ─────────────────────────────────────────────


class TestDiffPayloadKey:
    def test_brief_payload_key_detected(self):
        old = _envelope("brief", {"brief_id": "b1", "title": "old"})
        new = _envelope("brief", {"brief_id": "b1", "title": "new"})
        result = diff_records(old, new)
        assert len(result) == 1
        assert result[0]["path"] == "brief.title"

    def test_briefing_payload_key_detected(self):
        old = _envelope("briefing", {"briefing_id": "bf1", "title": "old"})
        new = _envelope("briefing", {"briefing_id": "bf1", "title": "new"})
        result = diff_records(old, new)
        assert len(result) == 1
        assert result[0]["path"] == "briefing.title"

    def test_ambiguous_payload_falls_back_to_root_diff(self):
        # Two non-envelope keys → ambiguous → root dict diff.
        old = {"schema": "x", "version": "1", "server_revision": 1, "stored_at": "a",
               "brief": {"id": 1}, "extra": {"k": "old"}}
        new = {"schema": "x", "version": "1", "server_revision": 1, "stored_at": "a",
               "brief": {"id": 1}, "extra": {"k": "new"}}
        result = diff_records(old, new)
        paths = [r["path"] for r in result]
        assert "extra.k" in paths


# ── Dict / list changes ───────────────────────────────────────────────


class TestDiffDictChanges:
    def test_added_field(self):
        old = _envelope("brief", {"brief_id": "b1", "title": "x"})
        new = _envelope("brief", {"brief_id": "b1", "title": "x", "team": "Arsenal"})
        result = diff_records(old, new)
        assert len(result) == 1
        assert result[0] == {
            "path": "brief.team",
            "change": "added",
            "old": None,
            "new": "Arsenal",
        }

    def test_removed_field(self):
        old = _envelope("brief", {"brief_id": "b1", "title": "x", "team": "Arsenal"})
        new = _envelope("brief", {"brief_id": "b1", "title": "x"})
        result = diff_records(old, new)
        assert len(result) == 1
        assert result[0]["change"] == "removed"
        assert result[0]["old"] == "Arsenal"

    def test_changed_scalar(self):
        old = _envelope("brief", {"brief_id": "b1", "title": "old"})
        new = _envelope("brief", {"brief_id": "b1", "title": "new"})
        result = diff_records(old, new)
        assert len(result) == 1
        assert result[0]["change"] == "changed"
        assert result[0]["old"] == "old"
        assert result[0]["new"] == "new"

    def test_nested_dict_change(self):
        old = _envelope("brief", {"brief_id": "b1", "meta": {"a": 1, "b": 2}})
        new = _envelope("brief", {"brief_id": "b1", "meta": {"a": 1, "b": 3, "c": 4}})
        result = diff_records(old, new)
        paths = {r["path"]: r for r in result}
        assert paths["brief.meta.b"]["change"] == "changed"
        assert paths["brief.meta.b"]["old"] == 2
        assert paths["brief.meta.b"]["new"] == 3
        assert paths["brief.meta.c"]["change"] == "added"
        assert paths["brief.meta.c"]["new"] == 4
        # brief.meta.a unchanged → not in diff
        assert "brief.meta.a" not in paths


class TestDiffListChanges:
    def test_list_element_change(self):
        old = _envelope("brief", {"brief_id": "b1", "tags": ["a", "b", "c"]})
        new = _envelope("brief", {"brief_id": "b1", "tags": ["a", "B", "c"]})
        result = diff_records(old, new)
        assert len(result) == 1
        assert result[0]["path"] == "brief.tags[1]"
        assert result[0]["old"] == "b"
        assert result[0]["new"] == "B"

    def test_list_element_added(self):
        old = _envelope("brief", {"brief_id": "b1", "tags": ["a", "b"]})
        new = _envelope("brief", {"brief_id": "b1", "tags": ["a", "b", "c"]})
        result = diff_records(old, new)
        assert len(result) == 1
        assert result[0]["path"] == "brief.tags[2]"
        assert result[0]["change"] == "added"

    def test_list_element_removed(self):
        old = _envelope("brief", {"brief_id": "b1", "tags": ["a", "b", "c"]})
        new = _envelope("brief", {"brief_id": "b1", "tags": ["a", "b"]})
        result = diff_records(old, new)
        assert len(result) == 1
        assert result[0]["path"] == "brief.tags[2]"
        assert result[0]["change"] == "removed"

    def test_list_of_dicts_diff(self):
        old = _envelope("brief", {"sections": [{"id": "a", "text": "old"}]})
        new = _envelope("brief", {"sections": [{"id": "a", "text": "new"}]})
        result = diff_records(old, new)
        assert len(result) == 1
        assert result[0]["path"] == "brief.sections[0].text"


# ── Type / shape mismatches ──────────────────────────────────────────


class TestDiffShapeMismatch:
    def test_dict_vs_list(self):
        old = _envelope("brief", {"field": {"a": 1}})
        new = _envelope("brief", {"field": [1, 2]})
        result = diff_records(old, new)
        # The whole field is reported as changed (no recursion into mismatched types).
        assert len(result) == 1
        assert result[0]["path"] == "brief.field"
        assert result[0]["change"] == "changed"

    def test_scalar_vs_dict(self):
        old = _envelope("brief", {"field": "scalar"})
        new = _envelope("brief", {"field": {"a": 1}})
        result = diff_records(old, new)
        assert len(result) == 1
        assert result[0]["change"] == "changed"

    def test_root_shape_mismatch(self):
        result = diff_records([1, 2], {"a": 1})  # type: ignore[arg-type]
        assert len(result) == 1
        assert result[0]["path"] == "__root__"
        assert result[0]["change"] == "shape_mismatch"


# ── Normalisation & sorting ──────────────────────────────────────────


class TestDiffNormalisation:
    def test_key_ordering_irrelevant(self):
        old = _envelope("brief", {"a": 1, "b": 2})
        new = _envelope("brief", {"b": 2, "a": 1})
        # Same content, different key order → no diff.
        assert diff_records(old, new) == []

    def test_int_one_vs_bool_true_treated_equal(self):
        # Python's 1 == True is True; brief payloads do not mix int/bool,
        # so the diff treats them as equal (documented behaviour).
        old = _envelope("brief", {"flag": 1})
        new = _envelope("brief", {"flag": True})
        result = diff_records(old, new)
        assert result == []

    def test_entries_sorted_by_path(self):
        old = _envelope("brief", {"z": 1, "a": 1, "m": 1})
        new = _envelope("brief", {"z": 2, "a": 2, "m": 2})
        result = diff_records(old, new)
        paths = [r["path"] for r in result]
        assert paths == sorted(paths)
        assert paths == ["brief.a", "brief.m", "brief.z"]
