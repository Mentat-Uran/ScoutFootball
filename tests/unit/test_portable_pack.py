"""Unit tests for ``export_local_pack`` and ``import_local_pack``.

The portable pack is the L1 "本地包、备份和导入导出复核" mechanism: it
bundles every recruitment brief and opposition briefing into a single
JSON document with per-section SHA-256 hashes, so the maintainer can
migrate data between machines or restore from backup without cloud
sync.  These tests cover:

- Export: schema/version/sections, hash computation, skipped corrupt
  records, empty store.
- Import: pack-level validation (schema/version/size), section-level
  hash verification (fail-closed per section), record-level conflict
  handling (``overwrite`` flag), corrupt record skipping, envelope
  fields not preserved.
- Round-trip: export from store A → import into fresh store B yields
  equivalent records.
- API endpoint: ``POST /local-pack/import`` accepts the pack body and
  the ``overwrite`` query parameter.

The store-level correctness (atomic writes, revision backups, optimistic
concurrency) is covered by ``test_recruitment_brief.py`` /
``test_opposition_briefing.py`` and is not duplicated here.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scoutfootball.api import (
    export_local_pack,
    import_local_pack,
)
from scoutfootball.api_server import create_app
from scoutfootball.opposition.briefing import (
    BRIEFING_SCHEMA,
    BRIEFING_VERSION,
)
from scoutfootball.recruitment.brief import (
    BRIEF_SCHEMA,
    BRIEF_VERSION,
)

# ── Helpers ───────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _valid_brief_payload(
    brief_id: str = "brief-pack-001",
    *,
    title: str = "Pack test brief",
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
        "position_group": "DF",
        "position_detail": "LB",
        "role": "attacking_fullback",
        "budget_eur": 30_000_000,
        "age_min": 21,
        "age_max": 27,
        "contract_years_min": 3,
        "league_preferences": ["Premier League"],
        "language_preferences": ["English"],
        "risk_tolerance": "medium",
        "minimum_minutes": 1500,
        "notes": "",
        "limitations": [],
    }
    payload.update(overrides)
    return payload


def _valid_briefing_payload(
    briefing_id: str = "briefing-pack-001",
    *,
    title: str = "Pack test briefing",
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
            {
                "section_id": "opponent_strength",
                "fact_tier": "recorded",
                "summary": "Chelsea are 4th in the table.",
                "evidence_refs": ["fbref/2026-27/Chelsea"],
            },
        ],
        "linked_pattern_card_ids": [],
        "linked_scenario_tree_id": None,
        "linked_post_match_review_id": None,
        "notes": "",
        "limitations": [],
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def patched_stores(tmp_path: Path, monkeypatch):
    """Patch ``_brief_store()`` and ``_briefing_store()`` to point at
    isolated tmp_path roots so tests never touch the real report_root.
    """
    from scoutfootball.opposition.store import BriefingStore
    from scoutfootball.recruitment.store import BriefStore

    brief_root = tmp_path / "recruitment" / "briefs"
    briefing_root = tmp_path / "opposition" / "briefings"
    brief_root.mkdir(parents=True, exist_ok=True)
    briefing_root.mkdir(parents=True, exist_ok=True)

    brief_store = BriefStore(brief_root)
    briefing_store = BriefingStore(briefing_root)

    monkeypatch.setattr("scoutfootball.api._brief_store", lambda: brief_store)
    monkeypatch.setattr("scoutfootball.api._briefing_store", lambda: briefing_store)
    return brief_store, briefing_store


def _save_brief(store, brief_id: str, **overrides) -> dict:
    """Save a brief via the store API (creates revision 1 by default)."""
    return store.save(
        brief_id, _valid_brief_payload(brief_id=brief_id, **overrides)
    )


def _save_briefing(store, briefing_id: str, **overrides) -> dict:
    return store.save(
        briefing_id, _valid_briefing_payload(briefing_id=briefing_id, **overrides)
    )


def _build_pack(briefs: list[dict], briefings: list[dict]) -> dict:
    """Build a minimal valid pack from already-stored record envelopes."""
    response = export_local_pack()
    # export_local_pack reads from the patched stores; we pre-populate
    # them with ``briefs`` and ``briefings`` before calling this.
    return response["pack"]


def _tamper_section_hash(pack: dict, section_name: str) -> dict:
    """Return a copy of ``pack`` with ``section_hashes[section_name]``
    replaced by an invalid 64-char hex string.
    """
    tampered = copy.deepcopy(pack)
    tampered["section_hashes"][section_name] = "0" * 64
    return tampered


# ── Export tests ──────────────────────────────────────────────────────


class TestExportLocalPack:
    def test_export_returns_ok_with_pack(self, patched_stores):
        result = export_local_pack()
        assert result["status"] == "ok"
        assert "pack" in result
        pack = result["pack"]
        assert pack["schema"] == "scoutfootball.portable-pack"
        assert pack["version"] == "1.0.0"
        assert "exported_at" in pack
        assert "app_version" in pack

    def test_export_includes_both_sections(self, patched_stores):
        pack = export_local_pack()["pack"]
        assert set(pack["sections"].keys()) == {
            "recruitment_briefs",
            "opposition_briefings",
        }
        assert set(pack["section_hashes"].keys()) == {
            "recruitment_briefs",
            "opposition_briefings",
        }

    def test_export_empty_store_produces_zero_count(self, patched_stores):
        pack = export_local_pack()["pack"]
        assert pack["sections"]["recruitment_briefs"]["count"] == 0
        assert pack["sections"]["opposition_briefings"]["count"] == 0
        assert pack["sections"]["recruitment_briefs"]["records"] == []
        assert pack["sections"]["opposition_briefings"]["records"] == []

    def test_export_includes_stored_brief_records(self, patched_stores):
        brief_store, _ = patched_stores
        _save_brief(brief_store, "brief-export-001", title="Export test")
        pack = export_local_pack()["pack"]
        section = pack["sections"]["recruitment_briefs"]
        assert section["count"] == 1
        assert section["records"][0]["brief"]["brief_id"] == "brief-export-001"
        assert section["records"][0]["brief"]["title"] == "Export test"

    def test_export_section_hashes_match_canonical_json(self, patched_stores):
        """The recorded section_hashes must match SHA-256 of the canonical
        JSON of each section. This is the contract import_local_pack
        relies on.
        """
        brief_store, briefing_store = patched_stores
        _save_brief(brief_store, "brief-hash-001")
        _save_briefing(briefing_store, "briefing-hash-001")
        pack = export_local_pack()["pack"]
        for name, section in pack["sections"].items():
            canonical = json.dumps(
                section, ensure_ascii=False, sort_keys=True, indent=2
            )
            expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            assert pack["section_hashes"][name] == expected

    def test_export_skips_corrupt_record_without_aborting(
        self, patched_stores, monkeypatch
    ):
        """A corrupt record on disk should appear in ``skipped`` and not
        abort the export — matches the fail-soft contract documented in
        ``export_local_pack``.
        """
        brief_store, _ = patched_stores
        _save_brief(brief_store, "brief-ok-001")
        # Write a corrupt JSON file directly into the store root.
        corrupt_path = brief_store.root / "brief-corrupt-001.json"
        corrupt_path.write_text("{not valid json", encoding="utf-8")
        result = export_local_pack()
        pack = result["pack"]
        assert pack["sections"]["recruitment_briefs"]["count"] == 1
        skipped = pack["skipped"]["recruitment_briefs"]
        assert any(
            s.get("brief_id") == "brief-corrupt-001" for s in skipped
        ), f"corrupt brief not in skipped: {skipped}"


# ── Import: pack-level validation (fail-closed) ───────────────────────


class TestImportPackLevelValidation:
    def test_import_rejects_non_dict_pack(self, patched_stores):
        result = import_local_pack("not a dict")  # type: ignore[arg-type]
        assert result["status"] == "error"
        assert result["code"] == "invalid_pack"

    def test_import_rejects_wrong_schema(self, patched_stores):
        pack = export_local_pack()["pack"]
        pack["schema"] = "scoutfootball.other-pack"
        result = import_local_pack(pack)
        assert result["status"] == "error"
        assert result["code"] == "incompatible_schema"

    def test_import_rejects_wrong_version(self, patched_stores):
        pack = export_local_pack()["pack"]
        pack["version"] = "2.0.0"
        result = import_local_pack(pack)
        assert result["status"] == "error"
        assert result["code"] == "incompatible_version"

    def test_import_rejects_missing_sections(self, patched_stores):
        result = import_local_pack(
            {
                "schema": "scoutfootball.portable-pack",
                "version": "1.0.0",
            }
        )
        assert result["status"] == "error"
        assert result["code"] == "invalid_pack"


# ── Import: section-level hash verification ───────────────────────────


class TestImportSectionHash:
    def test_hash_mismatch_skips_entire_section(self, patched_stores):
        """A corrupted section hash must skip that section but still
        import other sections. The skipped section is reported in
        ``section_errors``.
        """
        brief_store, briefing_store = patched_stores
        _save_brief(brief_store, "brief-section-001")
        _save_briefing(briefing_store, "briefing-section-001")
        pack = export_local_pack()["pack"]

        # Tamper the briefs section hash; briefings section still valid.
        tampered = _tamper_section_hash(pack, "recruitment_briefs")

        # Clear target stores so import doesn't see conflicts.
        for path in brief_store.root.glob("*.json"):
            path.unlink()
        for path in briefing_store.root.glob("*.json"):
            path.unlink()

        result = import_local_pack(tampered)
        assert result["status"] == "ok"
        section_errors = result["section_errors"]
        assert any(
            e["section"] == "recruitment_briefs" and e["code"] == "hash_mismatch"
            for e in section_errors
        ), f"expected hash_mismatch for recruitment_briefs: {section_errors}"
        # Briefings section was still imported.
        briefing_section = next(
            s for s in result["section_results"] if s["section"] == "opposition_briefings"
        )
        assert briefing_section["imported"] == 1
        assert briefing_section["imported"] == 1

    def test_missing_hash_string_skips_section(self, patched_stores):
        brief_store, _ = patched_stores
        _save_brief(brief_store, "brief-nohash-001")
        pack = export_local_pack()["pack"]
        # Replace the hash with a non-string.
        pack["section_hashes"]["recruitment_briefs"] = None
        for path in brief_store.root.glob("*.json"):
            path.unlink()
        result = import_local_pack(pack)
        assert result["status"] == "ok"
        assert any(
            e["code"] == "missing_or_invalid_hash"
            and e["section"] == "recruitment_briefs"
            for e in result["section_errors"]
        )

    def test_valid_hash_imports_section(self, patched_stores):
        """Sanity: an untouched pack imports both sections successfully."""
        brief_store, briefing_store = patched_stores
        _save_brief(brief_store, "brief-valid-001")
        _save_briefing(briefing_store, "briefing-valid-001")
        pack = export_local_pack()["pack"]
        # Clear target stores.
        for path in brief_store.root.glob("*.json"):
            path.unlink()
        for path in briefing_store.root.glob("*.json"):
            path.unlink()
        result = import_local_pack(pack)
        assert result["status"] == "ok"
        assert result["section_errors"] == []
        assert result["summary"]["total_imported"] == 2


# ── Import: record-level conflict handling ────────────────────────────


class TestImportConflictHandling:
    def test_default_overwrite_false_skips_existing_records(
        self, patched_stores
    ):
        """When ``overwrite=False`` (default), records whose ID already
        exists locally are reported in ``conflicts`` and not modified.
        """
        brief_store, _ = patched_stores
        _save_brief(brief_store, "brief-conflict-001", title="Local version")
        pack = export_local_pack()["pack"]
        # The local store still has the record; import without overwrite.
        result = import_local_pack(pack, overwrite=False)
        assert result["status"] == "ok"
        section = next(
            s for s in result["section_results"]
            if s["section"] == "recruitment_briefs"
        )
        assert section["imported"] == 0
        assert len(section["conflicts"]) == 1
        assert section["conflicts"][0]["brief_id"] == "brief-conflict-001"
        # Local record unchanged.
        local = brief_store.load("brief-conflict-001")
        assert local["brief"]["title"] == "Local version"
        assert local["server_revision"] == 1

    def test_overwrite_true_replaces_existing_via_revision_bump(
        self, patched_stores
    ):
        """When ``overwrite=True``, existing records are replaced by
        calling ``save(expected_revision=current)``, which bumps
        ``server_revision`` and creates a revision backup.
        """
        brief_store, _ = patched_stores
        _save_brief(brief_store, "brief-overwrite-001", title="Local v1")
        # Mutate the local title to simulate divergence.
        original = brief_store.load("brief-overwrite-001")
        pack = export_local_pack()["pack"]
        # Modify the pack's brief title to verify the overwrite actually
        # replaces local content.
        pack["sections"]["recruitment_briefs"]["records"][0]["brief"]["title"] = (
            "Pack v2 (overwrites local)"
        )
        # Recompute the section hash so the pack is still valid.
        section = pack["sections"]["recruitment_briefs"]
        canonical = json.dumps(section, ensure_ascii=False, sort_keys=True, indent=2)
        pack["section_hashes"]["recruitment_briefs"] = (
            hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        )

        result = import_local_pack(pack, overwrite=True)
        assert result["status"] == "ok"
        section_result = next(
            s for s in result["section_results"]
            if s["section"] == "recruitment_briefs"
        )
        assert section_result["imported"] == 1
        assert section_result["conflicts"] == []
        # Local record now has the pack's title and bumped revision.
        local = brief_store.load("brief-overwrite-001")
        assert local["brief"]["title"] == "Pack v2 (overwrites local)"
        assert local["server_revision"] == original["server_revision"] + 1
        # A revision backup was created.
        backups = brief_store.list_backups("brief-overwrite-001")
        assert len(backups) >= 1

    def test_mixed_new_and_conflicting_records(self, patched_stores):
        """A pack with both new and existing records: new ones imported,
        existing ones reported as conflicts (overwrite=False).
        """
        brief_store, _ = patched_stores
        _save_brief(brief_store, "brief-existing-001", title="Local")
        _save_brief(brief_store, "brief-existing-002", title="Local")
        pack = export_local_pack()["pack"]
        # Add a new record to the pack that doesn't exist locally.
        new_payload = _valid_brief_payload(
            brief_id="brief-new-003", title="Only in pack"
        )
        new_envelope = {
            "schema": "scoutfootball.recruitment-brief-record",
            "version": "1.0.0",
            "server_revision": 1,
            "stored_at": _now(),
            "brief": new_payload,
        }
        pack["sections"]["recruitment_briefs"]["records"].append(new_envelope)
        pack["sections"]["recruitment_briefs"]["count"] = 3
        # Recompute hash.
        section = pack["sections"]["recruitment_briefs"]
        canonical = json.dumps(section, ensure_ascii=False, sort_keys=True, indent=2)
        pack["section_hashes"]["recruitment_briefs"] = (
            hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        )

        result = import_local_pack(pack, overwrite=False)
        section_result = next(
            s for s in result["section_results"]
            if s["section"] == "recruitment_briefs"
        )
        assert section_result["imported"] == 1  # only the new one
        assert len(section_result["conflicts"]) == 2


# ── Import: record-level fail-soft ────────────────────────────────────


class TestImportRecordLevelFailSoft:
    def test_corrupt_record_in_pack_is_skipped(self, patched_stores):
        """A record with invalid payload (e.g. missing required field)
        is reported in ``skipped`` and does not abort the import of
        other valid records in the same section.
        """
        brief_store, _ = patched_stores
        _save_brief(brief_store, "brief-ok-001")
        pack = export_local_pack()["pack"]
        # Add a corrupt record: missing required 'brief_id' in payload.
        corrupt_envelope = {
            "schema": "scoutfootball.recruitment-brief-record",
            "version": "1.0.0",
            "server_revision": 1,
            "stored_at": _now(),
            "brief": {
                "schema": BRIEF_SCHEMA,
                "version": BRIEF_VERSION,
                # missing brief_id, title, position_group, etc.
            },
        }
        pack["sections"]["recruitment_briefs"]["records"].append(corrupt_envelope)
        pack["sections"]["recruitment_briefs"]["count"] = 2
        # Recompute hash so the pack is valid as a whole.
        section = pack["sections"]["recruitment_briefs"]
        canonical = json.dumps(section, ensure_ascii=False, sort_keys=True, indent=2)
        pack["section_hashes"]["recruitment_briefs"] = (
            hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        )
        # Clear local store so the valid record has no conflict.
        for path in brief_store.root.glob("*.json"):
            path.unlink()

        result = import_local_pack(pack)
        section_result = next(
            s for s in result["section_results"]
            if s["section"] == "recruitment_briefs"
        )
        assert section_result["imported"] == 1  # only the valid one
        assert len(section_result["skipped"]) == 1

    def test_non_dict_record_is_skipped(self, patched_stores):
        pack = export_local_pack()["pack"]
        pack["sections"]["recruitment_briefs"]["records"].append("not a dict")
        pack["sections"]["recruitment_briefs"]["count"] = 1
        section = pack["sections"]["recruitment_briefs"]
        canonical = json.dumps(section, ensure_ascii=False, sort_keys=True, indent=2)
        pack["section_hashes"]["recruitment_briefs"] = (
            hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        )
        result = import_local_pack(pack)
        section_result = next(
            s for s in result["section_results"]
            if s["section"] == "recruitment_briefs"
        )
        assert len(section_result["skipped"]) == 1


# ── Import: envelope fields not preserved ─────────────────────────────


class TestImportEnvelopeFields:
    def test_server_revision_not_preserved(self, patched_stores):
        """The pack's ``server_revision`` envelope field must NOT be
        preserved on import — the target store manages its own revision
        counter. A pack record with ``server_revision=99`` becomes
        ``server_revision=1`` on the target.
        """
        brief_store, _ = patched_stores
        _save_brief(brief_store, "brief-revision-001")
        pack = export_local_pack()["pack"]
        # Tamper the envelope server_revision to 99.
        pack["sections"]["recruitment_briefs"]["records"][0]["server_revision"] = 99
        section = pack["sections"]["recruitment_briefs"]
        canonical = json.dumps(section, ensure_ascii=False, sort_keys=True, indent=2)
        pack["section_hashes"]["recruitment_briefs"] = (
            hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        )
        # Clear local store.
        for path in brief_store.root.glob("*.json"):
            path.unlink()

        result = import_local_pack(pack)
        assert result["status"] == "ok"
        local = brief_store.load("brief-revision-001")
        # Target store reset revision to 1, not 99.
        assert local["server_revision"] == 1


# ── Round-trip: export → import → verify ──────────────────────────────


class TestRoundTrip:
    def test_round_trip_preserves_brief_payload(self, patched_stores):
        """Export from store A, import into a fresh store B, verify the
        brief payload (user-authored content) is identical.
        """
        brief_store, briefing_store = patched_stores
        _save_brief(
            brief_store, "brief-rt-001",
            title="Round trip brief",
            team="Liverpool",
        )
        _save_briefing(
            briefing_store, "briefing-rt-001",
            title="Round trip briefing",
        )
        pack = export_local_pack()["pack"]

        # Wipe both stores to simulate a fresh target machine.
        for path in brief_store.root.glob("*.json"):
            path.unlink()
        for path in briefing_store.root.glob("*.json"):
            path.unlink()

        result = import_local_pack(pack)
        assert result["status"] == "ok"
        assert result["summary"]["total_imported"] == 2
        assert result["summary"]["total_conflicts"] == 0
        assert result["summary"]["total_skipped"] == 0

        # Verify brief payload round-trips.
        local_brief = brief_store.load("brief-rt-001")
        assert local_brief["brief"]["title"] == "Round trip brief"
        assert local_brief["brief"]["team"] == "Liverpool"
        # Verify briefing payload round-trips.
        local_briefing = briefing_store.load("briefing-rt-001")
        assert local_briefing["briefing"]["title"] == "Round trip briefing"
        assert local_briefing["briefing"]["home_team"] == "Arsenal"

    def test_round_trip_with_empty_pack_is_noop(self, patched_stores):
        """Exporting from an empty store and importing into another empty
        store is a no-op that returns status=ok with zero counts.
        """
        pack = export_local_pack()["pack"]
        result = import_local_pack(pack)
        assert result["status"] == "ok"
        assert result["summary"]["total_imported"] == 0
        assert result["summary"]["total_conflicts"] == 0
        assert result["summary"]["total_skipped"] == 0


# ── API endpoint integration ──────────────────────────────────────────


class TestApiEndpoint:
    def test_endpoint_returns_200_with_valid_pack(self, patched_stores):
        """POST /local-pack/import with a valid pack body returns 200
        and the same schema as the programmatic API.
        """
        pack = export_local_pack()["pack"]
        client = TestClient(create_app())
        response = client.post("/local-pack/import", json=pack)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["schema"] == "scoutfootball.portable-pack-import"
        assert body["version"] == "1.0.0"

    def test_endpoint_accepts_overwrite_query_param(self, patched_stores):
        """Both ``overwrite=true`` and ``overwrite=false`` must be
        accepted without a 422.
        """
        brief_store, _ = patched_stores
        _save_brief(brief_store, "brief-api-001", title="Local")
        pack = export_local_pack()["pack"]
        client = TestClient(create_app())
        for value in ("true", "false"):
            response = client.post(
                f"/local-pack/import?overwrite={value}", json=pack
            )
            assert response.status_code == 200, f"overwrite={value} failed"
            assert response.json()["status"] == "ok"

    def test_endpoint_rejects_invalid_overwrite(self, patched_stores):
        """Non-boolean ``overwrite`` values must be rejected with 422."""
        pack = export_local_pack()["pack"]
        client = TestClient(create_app())
        response = client.post(
            "/local-pack/import?overwrite=maybe", json=pack
        )
        assert response.status_code == 422

    def test_endpoint_accepts_pack_wrapped_in_pack_key(self, patched_stores):
        """The endpoint also accepts ``{"pack": {...}}`` (the full export
        response shape) for convenience — callers don't need to unwrap.
        """
        export_response = export_local_pack()
        client = TestClient(create_app())
        response = client.post(
            "/local-pack/import", json=export_response
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_endpoint_rejects_wrong_schema_with_error_status(
        self, patched_stores
    ):
        """A pack with wrong schema returns 200 with status=error in the
        body — matches the programmatic API's fail-closed behavior. The
        HTTP layer doesn't translate domain errors to 4xx because the
        request itself was well-formed JSON.
        """
        pack = export_local_pack()["pack"]
        pack["schema"] = "scoutfootball.wrong"
        client = TestClient(create_app())
        response = client.post("/local-pack/import", json=pack)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "error"
        assert body["code"] == "incompatible_schema"
