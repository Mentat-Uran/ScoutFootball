"""Unit tests for BriefStore backup listing, loading and restore.

Covers both :class:`scoutfootball.recruitment.store.BriefStore` and
:class:`scoutfootball.opposition.store.BriefingStore` since they share
the same backup file-naming convention.

Covers:
- ``list_backups``: empty, after single update, after multiple updates,
  after delete, ordering (newest revision first, deletions last)
- ``load_backup``: valid filename, missing backup, path traversal
  rejection, unknown kind, mismatched brief_id
- ``restore_from_backup``: creates a new revision preserving payload,
  respects ``expected_revision`` If-Match semantics, leaves the backup
  in place, works after delete (restore from deletion backup)
- Cross-store isolation: a brief backup cannot be loaded via the
  briefing store and vice versa
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from scoutfootball.opposition.briefing import (
    BRIEFING_SCHEMA,
    BRIEFING_VERSION,
)
from scoutfootball.opposition.store import (
    BriefingStore,
    BriefingStoreError,
)
from scoutfootball.recruitment.brief import (
    BRIEF_SCHEMA,
    BRIEF_VERSION,
    BriefValidationError,
)
from scoutfootball.recruitment.store import (
    BriefStore,
    BriefStoreError,
)


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _valid_brief_payload(
    brief_id: str = "brief-test-001",
    *,
    title: str = "Test brief",
    revision: int = 1,
) -> dict:
    return {
        "schema": BRIEF_SCHEMA,
        "version": BRIEF_VERSION,
        "brief_id": brief_id,
        "revision": revision,
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
        "notes": "Priority window.",
        "limitations": ["Personal local object."],
    }


def _valid_briefing_payload(
    briefing_id: str = "briefing-test-001",
    *,
    title: str = "Test briefing",
    revision: int = 1,
) -> dict:
    return {
        "schema": BRIEFING_SCHEMA,
        "version": BRIEFING_VERSION,
        "briefing_id": briefing_id,
        "revision": revision,
        "created_at": _now(),
        "updated_at": _now(),
        "author": "maintainer",
        "title": title,
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "kickoff_at": "2026-08-15T15:00:00+00:00",
        "competition": "Premier League",
        "sections": [
            {
                "section_id": "opponent_strength",
                "fact_tier": "recorded",
                "summary": "4-3-3 with inverted fullbacks.",
                "evidence_refs": [],
            },
        ],
        "limitations": ["Personal local object."],
    }


# ── BriefStore.list_backups ──────────────────────────────────────────


class TestBriefListBackups:
    def test_empty_when_no_backups(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        assert store.list_backups("brief-001") == []

    def test_empty_when_no_backup_dir(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_brief_payload("brief-001"), expected_revision=0)
        # No update yet → no backup dir.
        assert store.list_backups("brief-001") == []

    def test_lists_revision_backups_newest_first(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_brief_payload("brief-001", title="v1"), expected_revision=0)
        store.save("brief-001", _valid_brief_payload("brief-001", title="v2"), expected_revision=1)
        store.save("brief-001", _valid_brief_payload("brief-001", title="v3"), expected_revision=2)
        backups = store.list_backups("brief-001")
        assert len(backups) == 2
        # Newest revision (rev-2) first.
        assert backups[0]["kind"] == "revision"
        assert backups[0]["revision"] == 2
        assert backups[1]["revision"] == 1
        # Each entry has the required fields.
        for entry in backups:
            assert "backup_filename" in entry
            assert "stored_at" in entry
            assert "size_bytes" in entry
            assert entry["brief_id"] == "brief-001"

    def test_lists_deletion_backup_after_deletion(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_brief_payload("brief-001"), expected_revision=0)
        store.delete("brief-001", expected_revision=1)
        backups = store.list_backups("brief-001")
        assert len(backups) == 1
        assert backups[0]["kind"] == "deletion"
        assert backups[0]["revision"] is None

    def test_deletions_sorted_after_revisions(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_brief_payload("brief-001", title="v1"), expected_revision=0)
        store.save("brief-001", _valid_brief_payload("brief-001", title="v2"), expected_revision=1)
        store.delete("brief-001", expected_revision=2)
        backups = store.list_backups("brief-001")
        # Newest revision first, then deletion.
        assert [b["kind"] for b in backups] == ["revision", "deletion"]
        assert backups[0]["revision"] == 1

    def test_invalid_brief_id_rejected(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        with pytest.raises(BriefValidationError):
            store.list_backups("../escape")


# ── BriefStore.load_backup ───────────────────────────────────────────


class TestBriefLoadBackup:
    def test_load_revision_backup(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_brief_payload("brief-001", title="v1"), expected_revision=0)
        store.save("brief-001", _valid_brief_payload("brief-001", title="v2"), expected_revision=1)
        backups = store.list_backups("brief-001")
        backup = store.load_backup("brief-001", backups[0]["backup_filename"])
        assert backup["server_revision"] == 1
        assert backup["brief"]["title"] == "v1"

    def test_load_missing_backup_raises_not_found(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_brief_payload("brief-001"), expected_revision=0)
        with pytest.raises(BriefStoreError) as exc_info:
            store.load_backup("brief-001", "brief-001.rev-99.nonexistent.json")
        assert exc_info.value.code == "backup_not_found"

    def test_path_traversal_rejected(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_brief_payload("brief-001"), expected_revision=0)
        with pytest.raises(BriefStoreError) as exc_info:
            store.load_backup("brief-001", "../etc/passwd")
        assert exc_info.value.code == "backup_filename_invalid"

    def test_windows_path_traversal_rejected(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_brief_payload("brief-001"), expected_revision=0)
        with pytest.raises(BriefStoreError) as exc_info:
            store.load_backup("brief-001", "..\\windows\\system32\\config.json")
        assert exc_info.value.code == "backup_filename_invalid"

    def test_unknown_kind_rejected(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_brief_payload("brief-001"), expected_revision=0)
        with pytest.raises(BriefStoreError) as exc_info:
            store.load_backup("brief-001", "brief-001.weird-kind.abc.json")
        assert exc_info.value.code == "backup_filename_invalid"

    def test_mismatched_brief_id_rejected(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_brief_payload("brief-001"), expected_revision=0)
        store.save("brief-001", _valid_brief_payload("brief-001", title="v2"), expected_revision=1)
        # Try to load brief-001's backup using a different brief_id.
        with pytest.raises(BriefStoreError) as exc_info:
            store.load_backup("brief-002", "brief-001.rev-1.fake.json")
        assert exc_info.value.code == "backup_filename_invalid"


# ── BriefStore.restore_from_backup ──────────────────────────────────


class TestBriefRestoreFromBackup:
    def test_restore_creates_new_revision_with_old_payload(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_brief_payload("brief-001", title="v1"), expected_revision=0)
        store.save("brief-001", _valid_brief_payload("brief-001", title="v2"), expected_revision=1)
        backups = store.list_backups("brief-001")
        # Current revision is 2; restore from the v1 backup (rev-1).
        restored = store.restore_from_backup(
            "brief-001", backups[0]["backup_filename"], expected_revision=2,
        )
        # New revision is 3, but payload title is back to v1.
        assert restored["server_revision"] == 3
        assert restored["brief"]["title"] == "v1"

    def test_restore_leaves_backup_in_place(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_brief_payload("brief-001", title="v1"), expected_revision=0)
        store.save("brief-001", _valid_brief_payload("brief-001", title="v2"), expected_revision=1)
        backups_before = store.list_backups("brief-001")
        store.restore_from_backup(
            "brief-001", backups_before[0]["backup_filename"], expected_revision=2,
        )
        backups_after = store.list_backups("brief-001")
        # The original backup is still there, plus a new backup for rev-2.
        assert len(backups_after) == len(backups_before) + 1

    def test_restore_after_delete(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_brief_payload("brief-001", title="v1"), expected_revision=0)
        store.delete("brief-001", expected_revision=1)
        backups = store.list_backups("brief-001")
        # Only the deletion backup exists; restore from it.
        deletion_backup = next(b for b in backups if b["kind"] == "deletion")
        restored = store.restore_from_backup(
            "brief-001", deletion_backup["backup_filename"], expected_revision=None,
        )
        # New revision is 1 (record was missing), payload is v1.
        assert restored["server_revision"] == 1
        assert restored["brief"]["title"] == "v1"

    def test_restore_with_stale_revision_raises_conflict(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_brief_payload("brief-001", title="v1"), expected_revision=0)
        store.save("brief-001", _valid_brief_payload("brief-001", title="v2"), expected_revision=1)
        backups = store.list_backups("brief-001")
        with pytest.raises(BriefStoreError) as exc_info:
            store.restore_from_backup(
                "brief-001", backups[0]["backup_filename"], expected_revision=99,
            )
        assert exc_info.value.code == "brief_revision_conflict"

    def test_restore_requires_expected_revision_when_record_exists(self, tmp_path):
        store = BriefStore(tmp_path / "briefs")
        store.save("brief-001", _valid_brief_payload("brief-001", title="v1"), expected_revision=0)
        store.save("brief-001", _valid_brief_payload("brief-001", title="v2"), expected_revision=1)
        backups = store.list_backups("brief-001")
        with pytest.raises(BriefStoreError) as exc_info:
            store.restore_from_backup(
                "brief-001", backups[0]["backup_filename"], expected_revision=None,
            )
        assert exc_info.value.code == "brief_precondition_required"


# ── BriefingStore mirrors BriefStore ────────────────────────────────


class TestBriefingListBackups:
    def test_lists_revision_backups(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        store.save(
            "briefing-001",
            _valid_briefing_payload("briefing-001", title="v1"),
            expected_revision=0,
        )
        store.save(
            "briefing-001",
            _valid_briefing_payload("briefing-001", title="v2"),
            expected_revision=1,
        )
        backups = store.list_backups("briefing-001")
        assert len(backups) == 1
        assert backups[0]["kind"] == "revision"
        assert backups[0]["revision"] == 1
        assert backups[0]["briefing_id"] == "briefing-001"


class TestBriefingLoadBackup:
    def test_load_revision_backup(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        store.save(
            "briefing-001",
            _valid_briefing_payload("briefing-001", title="v1"),
            expected_revision=0,
        )
        store.save(
            "briefing-001",
            _valid_briefing_payload("briefing-001", title="v2"),
            expected_revision=1,
        )
        backups = store.list_backups("briefing-001")
        backup = store.load_backup("briefing-001", backups[0]["backup_filename"])
        assert backup["server_revision"] == 1
        assert backup["briefing"]["title"] == "v1"

    def test_path_traversal_rejected(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        store.save(
            "briefing-001",
            _valid_briefing_payload("briefing-001"),
            expected_revision=0,
        )
        with pytest.raises(BriefingStoreError) as exc_info:
            store.load_backup("briefing-001", "../etc/passwd")
        assert exc_info.value.code == "backup_filename_invalid"


class TestBriefingRestoreFromBackup:
    def test_restore_creates_new_revision(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        store.save(
            "briefing-001",
            _valid_briefing_payload("briefing-001", title="v1"),
            expected_revision=0,
        )
        store.save(
            "briefing-001",
            _valid_briefing_payload("briefing-001", title="v2"),
            expected_revision=1,
        )
        backups = store.list_backups("briefing-001")
        restored = store.restore_from_backup(
            "briefing-001", backups[0]["backup_filename"], expected_revision=2,
        )
        assert restored["server_revision"] == 3
        assert restored["briefing"]["title"] == "v1"

    def test_restore_after_delete(self, tmp_path):
        store = BriefingStore(tmp_path / "briefings")
        store.save(
            "briefing-001",
            _valid_briefing_payload("briefing-001", title="v1"),
            expected_revision=0,
        )
        store.delete("briefing-001", expected_revision=1)
        backups = store.list_backups("briefing-001")
        deletion_backup = next(b for b in backups if b["kind"] == "deletion")
        restored = store.restore_from_backup(
            "briefing-001", deletion_backup["backup_filename"], expected_revision=None,
        )
        assert restored["server_revision"] == 1
        assert restored["briefing"]["title"] == "v1"


# ── Cross-store isolation ───────────────────────────────────────────


class TestCrossStoreIsolation:
    def test_brief_backup_not_visible_to_briefing_store(self, tmp_path):
        brief_store = BriefStore(tmp_path / "briefs")
        briefing_store = BriefingStore(tmp_path / "briefings")
        brief_store.save(
            "brief-001", _valid_brief_payload("brief-001"), expected_revision=0,
        )
        brief_store.save(
            "brief-001",
            _valid_brief_payload("brief-001", title="v2"),
            expected_revision=1,
        )
        # The briefing store has no backups.
        assert briefing_store.list_backups("brief-001") == []
        # The brief backup filename cannot be loaded via the briefing store
        # because the briefing_id validation differs (actually same here, but
        # the briefing store's backup dir is empty).
        with pytest.raises(BriefingStoreError) as exc_info:
            briefing_store.load_backup("brief-001", "brief-001.rev-1.fake.json")
        assert exc_info.value.code == "backup_not_found"
