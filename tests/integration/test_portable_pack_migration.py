"""Integration tests for cross-environment portable pack migration.

The unit tests in ``tests/unit/test_portable_pack.py`` exercise the export
and import logic with both stores patched to share a single ``tmp_path``.
That is enough to verify the schema/hash/conflict contract, but it does
NOT verify the actual use case the portable pack exists for: migrating
maintainer-authored recruitment briefs and opposition briefings from one
data root to another, simulating a move to a new machine or a restore
from backup.

These integration tests do the full chain end-to-end:

1. Point ``SCOUTFOOTBALL_DATA_ROOT`` at a *source* temp data root.
2. Populate the source with briefs and briefings via the real store API.
3. Export a portable pack — exercised through the public
   :func:`scoutfootball.api.export_local_pack` entry point, which reads
   ``_settings().report_root`` on each call.
4. Switch ``SCOUTFOOTBALL_DATA_ROOT`` to a *target* temp data root.
5. Import the pack via :func:`scoutfootball.api.import_local_pack`.
6. Verify the records physically landed under the target data root, by:
   - Reading them back through the store API in the target environment.
   - Re-exporting a pack from the target and comparing counts/hashes
     to the original source pack.
   - Hitting ``GET /recruitment/briefs`` and ``GET /opposition/briefings``
     on a freshly-built FastAPI app — this is the reference workflow a
     maintainer would run after migration to confirm the new environment
     is usable.

The two data roots are independent ``tmp_path`` subdirectories, so any
leakage between source and target (e.g. a cached module-level store
singleton, an absolute path baked into the pack) would fail these tests.
"""

from __future__ import annotations

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

pytestmark = pytest.mark.integration


# ── Helpers ───────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _valid_brief_payload(
    brief_id: str, *, title: str = "Migration brief", **overrides
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
    briefing_id: str, *, title: str = "Migration briefing", **overrides
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
        "match_id": "fd-match-70001",
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


def _seed_source_stores(data_root: Path) -> tuple[list[str], list[str]]:
    """Populate the source data root with a known set of briefs and
    briefings using the real store API (no monkeypatching of internals).

    Returns the list of brief_ids and briefing_ids that were written, so
    tests can assert the target contains exactly these records.
    """
    from scoutfootball.opposition.store import BriefingStore
    from scoutfootball.recruitment.store import BriefStore

    brief_root = data_root / "reports" / "recruitment" / "briefs"
    briefing_root = data_root / "reports" / "opposition" / "briefings"
    brief_root.mkdir(parents=True, exist_ok=True)
    briefing_root.mkdir(parents=True, exist_ok=True)

    brief_store = BriefStore(brief_root)
    briefing_store = BriefingStore(briefing_root)

    brief_ids = ["brief-migrate-001", "brief-migrate-002", "brief-migrate-003"]
    for i, bid in enumerate(brief_ids):
        brief_store.save(
            bid,
            _valid_brief_payload(
                bid,
                title=f"Source brief {i + 1}",
                team=["Arsenal", "Liverpool", "Bayern Munich"][i],
            ),
        )

    briefing_ids = ["briefing-migrate-001", "briefing-migrate-002"]
    for i, bid in enumerate(briefing_ids):
        briefing_store.save(
            bid,
            _valid_briefing_payload(
                bid,
                title=f"Source briefing {i + 1}",
                home_team=["Arsenal", "Real Madrid"][i],
                away_team=["Chelsea", "Barcelona"][i],
            ),
        )

    return brief_ids, briefing_ids


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def source_data_root(tmp_path: Path, monkeypatch) -> Path:
    """A data root populated with source briefs and briefings."""
    data_root = tmp_path / "source" / "data"
    data_root.mkdir(parents=True)
    monkeypatch.setenv("SCOUTFOOTBALL_DATA_ROOT", str(data_root))
    _seed_source_stores(data_root)
    return data_root


@pytest.fixture
def target_data_root(tmp_path: Path, monkeypatch) -> Path:
    """A fresh, empty data root for the target environment.

    Tests that need to switch from source to target must call
    ``_switch_env_to_target`` themselves because fixture ordering would
    otherwise leave the env pointing at whichever fixture ran last.
    """
    data_root = tmp_path / "target" / "data"
    data_root.mkdir(parents=True)
    # Don't setenv here — source fixture sets it first, test switches.
    return data_root


def _switch_env(monkeypatch, data_root: Path) -> None:
    """Repoint ``SCOUTFOOTBALL_DATA_ROOT`` at a new data root."""
    monkeypatch.setenv("SCOUTFOOTBALL_DATA_ROOT", str(data_root))


# ── Cross-data-root migration ─────────────────────────────────────────


class TestCrossDataRootMigration:
    """Verify the portable pack actually moves records between two
    independent data roots, not just within a single tmp_path.
    """

    def test_export_from_source_produces_non_empty_pack(self, source_data_root):
        """Sanity: the source environment actually contains records
        before we attempt to migrate them.
        """
        result = export_local_pack()
        assert result["status"] == "ok"
        pack = result["pack"]
        assert pack["sections"]["recruitment_briefs"]["count"] == 3
        assert pack["sections"]["opposition_briefings"]["count"] == 2

    def test_import_into_target_lands_records_in_target_root(
        self, source_data_root, target_data_root, monkeypatch
    ):
        """End-to-end migration:

        - Export pack from source env.
        - Switch env to target (independent directory).
        - Import pack into target.
        - Read back from target via the store API and confirm records
          physically landed under ``target_data_root``.
        """
        # Export from source (env currently points at source_data_root).
        source_pack = export_local_pack()["pack"]

        # Switch to target and import.
        _switch_env(monkeypatch, target_data_root)
        result = import_local_pack(source_pack)
        assert result["status"] == "ok", f"import failed: {result}"
        assert result["summary"]["total_imported"] == 5
        assert result["summary"]["total_conflicts"] == 0
        assert result["summary"]["total_skipped"] == 0

        # Records must be physically present under the target root.
        target_brief_root = (
            target_data_root / "reports" / "recruitment" / "briefs"
        )
        target_briefing_root = (
            target_data_root / "reports" / "opposition" / "briefings"
        )
        assert target_brief_root.exists(), "brief root missing in target"
        assert target_briefing_root.exists(), "briefing root missing in target"

        brief_files = sorted(target_brief_root.glob("*.json"))
        briefing_files = sorted(target_briefing_root.glob("*.json"))
        assert len(brief_files) == 3, (
            f"expected 3 brief files in target, got {len(brief_files)}: "
            f"{[p.name for p in brief_files]}"
        )
        assert len(briefing_files) == 2, (
            f"expected 2 briefing files in target, got {len(briefing_files)}: "
            f"{[p.name for p in briefing_files]}"
        )

        # Verify the source data root is untouched (still has 3 + 2 records).
        source_brief_files = sorted(
            (source_data_root / "reports" / "recruitment" / "briefs").glob("*.json")
        )
        source_briefing_files = sorted(
            (source_data_root / "reports" / "opposition" / "briefings").glob("*.json")
        )
        assert len(source_brief_files) == 3
        assert len(source_briefing_files) == 2

    def test_target_pack_re_export_matches_source_counts(
        self, source_data_root, target_data_root, monkeypatch
    ):
        """After migration, re-exporting from the target must yield a
        pack with the same section counts and the same record IDs, even
        though the envelope fields (``server_revision``, ``stored_at``)
        are intentionally NOT preserved.

        Section hashes will differ because envelope fields differ, so we
        compare content semantically, not by hash.
        """
        source_pack = export_local_pack()["pack"]

        _switch_env(monkeypatch, target_data_root)
        import_result = import_local_pack(source_pack)
        assert import_result["status"] == "ok"
        assert import_result["summary"]["total_imported"] == 5

        # Re-export from target.
        target_pack = export_local_pack()["pack"]

        # Section counts must match.
        assert (
            target_pack["sections"]["recruitment_briefs"]["count"]
            == source_pack["sections"]["recruitment_briefs"]["count"]
            == 3
        )
        assert (
            target_pack["sections"]["opposition_briefings"]["count"]
            == source_pack["sections"]["opposition_briefings"]["count"]
            == 2
        )

        # The set of brief_ids / briefing_ids must match.
        source_brief_ids = {
            r["brief"]["brief_id"]
            for r in source_pack["sections"]["recruitment_briefs"]["records"]
        }
        target_brief_ids = {
            r["brief"]["brief_id"]
            for r in target_pack["sections"]["recruitment_briefs"]["records"]
        }
        assert source_brief_ids == target_brief_ids == {
            "brief-migrate-001",
            "brief-migrate-002",
            "brief-migrate-003",
        }

        source_briefing_ids = {
            r["briefing"]["briefing_id"]
            for r in source_pack["sections"]["opposition_briefings"]["records"]
        }
        target_briefing_ids = {
            r["briefing"]["briefing_id"]
            for r in target_pack["sections"]["opposition_briefings"]["records"]
        }
        assert source_briefing_ids == target_briefing_ids == {
            "briefing-migrate-001",
            "briefing-migrate-002",
        }

        # The user-authored payload (title, team, home_team, etc.) must
        # round-trip exactly. Envelope fields like ``server_revision``
        # are reset to 1 in the target.
        for source_record in source_pack["sections"]["recruitment_briefs"]["records"]:
            brief_id = source_record["brief"]["brief_id"]
            target_record = next(
                r
                for r in target_pack["sections"]["recruitment_briefs"]["records"]
                if r["brief"]["brief_id"] == brief_id
            )
            assert target_record["brief"]["title"] == source_record["brief"]["title"]
            assert target_record["brief"]["team"] == source_record["brief"]["team"]
            # server_revision is reset to 1 in target (not preserved).
            assert target_record["server_revision"] == 1

    def test_imported_records_are_visible_via_api_in_target(
        self, source_data_root, target_data_root, monkeypatch
    ):
        """Reference workflow: after migration, the maintainer opens the
        API in the new environment and the imported records are visible
        through ``GET /recruitment/briefs`` and ``GET /opposition/briefings``.

        This confirms the migration actually produced a usable target
        environment, not just files on disk.
        """
        source_pack = export_local_pack()["pack"]
        _switch_env(monkeypatch, target_data_root)
        import_result = import_local_pack(source_pack)
        assert import_result["status"] == "ok"

        # Build the FastAPI app AFTER switching the env so the app's
        # store factories resolve to the target data root.
        client = TestClient(create_app())

        briefs_response = client.get("/recruitment/briefs")
        assert briefs_response.status_code == 200
        briefs_body = briefs_response.json()
        assert briefs_body["status"] == "ok"
        assert briefs_body["count"] == 3
        brief_ids = {b["brief_id"] for b in briefs_body["briefs"]}
        assert brief_ids == {
            "brief-migrate-001",
            "brief-migrate-002",
            "brief-migrate-003",
        }

        briefings_response = client.get("/opposition/briefs")
        assert briefings_response.status_code == 200
        briefings_body = briefings_response.json()
        assert briefings_body["status"] == "ok"
        assert briefings_body["count"] == 2
        briefing_ids = {b["briefing_id"] for b in briefings_body["briefings"]}
        assert briefing_ids == {
            "briefing-migrate-001",
            "briefing-migrate-002",
        }

    def test_individual_record_load_via_api_in_target(
        self, source_data_root, target_data_root, monkeypatch
    ):
        """Reference workflow continued: load one specific brief by ID
        in the target environment to confirm the store can read the
        migrated record, not just list its summary.
        """
        source_pack = export_local_pack()["pack"]
        _switch_env(monkeypatch, target_data_root)
        import_result = import_local_pack(source_pack)
        assert import_result["status"] == "ok"

        client = TestClient(create_app())
        response = client.get("/recruitment/briefs/brief-migrate-002")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["record"]["brief"]["brief_id"] == "brief-migrate-002"
        assert body["record"]["brief"]["team"] == "Liverpool"
        assert body["record"]["server_revision"] == 1


class TestCrossDataRootConflictHandling:
    """Conflict behavior between two independent data roots.

    The unit tests cover conflict handling within a single store; these
    tests confirm the same semantics hold when the source and target are
    different physical data roots.
    """

    def test_reimport_into_target_without_overwrite_reports_conflicts(
        self, source_data_root, target_data_root, monkeypatch
    ):
        """Importing the same pack twice into a target without
        ``overwrite`` must report every record as a conflict on the
        second pass, and must NOT mutate the target records.
        """
        source_pack = export_local_pack()["pack"]
        _switch_env(monkeypatch, target_data_root)

        first = import_local_pack(source_pack)
        assert first["status"] == "ok"
        assert first["summary"]["total_imported"] == 5
        assert first["summary"]["total_conflicts"] == 0

        # Second import with overwrite=False: every record already exists.
        second = import_local_pack(source_pack, overwrite=False)
        assert second["status"] == "ok"
        assert second["summary"]["total_imported"] == 0
        assert second["summary"]["total_conflicts"] == 5
        assert second["summary"]["total_skipped"] == 0

    def test_reimport_into_target_with_overwrite_replaces_records(
        self, source_data_root, target_data_root, monkeypatch
    ):
        """Re-importing with ``overwrite=True`` replaces existing target
        records by bumping ``server_revision`` and creating a revision
        backup. The target ends up with the same record IDs but bumped
        revisions.
        """
        source_pack = export_local_pack()["pack"]
        _switch_env(monkeypatch, target_data_root)

        first = import_local_pack(source_pack)
        assert first["summary"]["total_imported"] == 5

        second = import_local_pack(source_pack, overwrite=True)
        assert second["status"] == "ok"
        assert second["summary"]["total_imported"] == 5
        assert second["summary"]["total_conflicts"] == 0

        # Every record now has server_revision=2 (1 from first import,
        # +1 from the overwrite save).
        client = TestClient(create_app())
        response = client.get("/recruitment/briefs/brief-migrate-001")
        assert response.status_code == 200
        record = response.json()["record"]
        assert record["server_revision"] == 2

        # Revision backups exist for each overwritten record.
        from scoutfootball.recruitment.store import BriefStore

        brief_store = BriefStore(
            target_data_root / "reports" / "recruitment" / "briefs"
        )
        backups = brief_store.list_backups("brief-migrate-001")
        assert len(backups) >= 1, (
            f"expected >=1 backup for brief-migrate-001, got {backups}"
        )


class TestCrossDataRootEdgeCases:
    """Edge cases that only make sense in a real cross-root scenario."""

    def test_empty_source_pack_migrates_to_empty_target(
        self, tmp_path: Path, monkeypatch
    ):
        """Exporting from an empty source and importing into an empty
        target must be a no-op that returns status=ok with zero counts.
        """
        source_root = tmp_path / "empty-source" / "data"
        source_root.mkdir(parents=True)
        target_root = tmp_path / "empty-target" / "data"
        target_root.mkdir(parents=True)

        _switch_env(monkeypatch, source_root)
        pack = export_local_pack()["pack"]
        assert pack["sections"]["recruitment_briefs"]["count"] == 0
        assert pack["sections"]["opposition_briefings"]["count"] == 0

        _switch_env(monkeypatch, target_root)
        result = import_local_pack(pack)
        assert result["status"] == "ok"
        assert result["summary"]["total_imported"] == 0
        assert result["summary"]["total_conflicts"] == 0
        assert result["summary"]["total_skipped"] == 0

        # No brief/briefing directories were created in target.
        assert not (target_root / "reports" / "recruitment" / "briefs").exists()
        assert not (target_root / "reports" / "opposition" / "briefings").exists()

    def test_pack_is_portable_across_data_roots_via_serialized_json(
        self, source_data_root, target_data_root, tmp_path: Path, monkeypatch
    ):
        """The pack must survive being serialized to JSON and read back,
        because real migration writes the pack to a file (or transfers
        it over a side channel) before importing.

        This catches accidental reliance on in-memory object identity.
        """
        source_pack = export_local_pack()["pack"]
        pack_path = tmp_path / "migration.json"
        pack_path.write_text(
            json.dumps(source_pack, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        _switch_env(monkeypatch, target_data_root)
        reloaded = json.loads(pack_path.read_text(encoding="utf-8"))
        result = import_local_pack(reloaded)
        assert result["status"] == "ok"
        assert result["summary"]["total_imported"] == 5
