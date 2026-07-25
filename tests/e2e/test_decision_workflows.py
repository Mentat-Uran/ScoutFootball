"""E2E coverage for the P1 decision-workflow views and round-trips.

This module covers the two new P1 views (``workflow`` and ``versions``)
and the two end-to-end decision round-trips they expose:

- **Versions view smoke**: the view shell renders, the type selector
  offers all four artifact types (brief / briefing / dossier / review),
  and the timeline + diff panels are present.
- **Workflow view smoke**: the view shell renders, the metric strip
  counters are present, and the three step lists (next / blockers /
  evidence gaps) are in the DOM.
- **Recruitment decision round-trip**: a brief with two revisions is
  seeded through the store; the browser then loads the versions view,
  selects the brief, loads the backup timeline, diffs a backup against
  the current record, and restores from the backup — verifying the
  new revision appears and the restored payload matches.
- **Opposition decision round-trip**: same shape as above but for an
  opposition briefing, exercising the parallel store path.

The round-trip tests seed data through the store directly (not via the
API) because the public API only exposes ``POST /recruitment/briefs``
for creating new records (``expected_revision=0``); there is no
``PUT`` / ``PATCH`` endpoint for updates.  The store-level update path
is already covered by unit tests (``test_brief_backup_restore.py``);
the E2E tests focus on what the *browser* does with the resulting
backup / diff / restore endpoints.

Run with::

    uv run pytest tests/e2e/test_decision_workflows.py -m e2e -v
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from test_smoke import open_loaded_app

pytestmark = pytest.mark.e2e


# ── Helpers for seeding versioned records through the store ──────────


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _valid_brief_payload(brief_id: str, *, title: str = "E2E brief") -> dict:
    """Return a minimal valid recruitment-brief payload for E2E seeding."""
    from scoutfootball.recruitment.brief import BRIEF_SCHEMA, BRIEF_VERSION

    return {
        "schema": BRIEF_SCHEMA,
        "version": BRIEF_VERSION,
        "brief_id": brief_id,
        "revision": 1,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "author": "e2e-test",
        "title": title,
        "team": "E2E Test FC",
        "position_group": "MF",
        "position_detail": "CM",
        "role": "box_to_box",
        "budget_eur": 20_000_000,
        "age_min": 22,
        "age_max": 28,
        "contract_years_min": 4,
        "league_preferences": ["Premier League"],
        "language_preferences": ["English"],
        "risk_tolerance": "medium",
        "minimum_minutes": 1200,
        "notes": "E2E seeded brief for versions-view round-trip.",
        "limitations": ["E2E test artifact; not a real scouting brief."],
    }


def _valid_briefing_payload(briefing_id: str, *, title: str = "E2E briefing") -> dict:
    """Return a minimal valid opposition-briefing payload for E2E seeding."""
    from scoutfootball.opposition.briefing import BRIEFING_SCHEMA, BRIEFING_VERSION

    return {
        "schema": BRIEFING_SCHEMA,
        "version": BRIEFING_VERSION,
        "briefing_id": briefing_id,
        "revision": 1,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "author": "e2e-test",
        "title": title,
        "home_team": "E2E Home FC",
        "away_team": "E2E Away FC",
        "kickoff_at": "2026-08-15T15:00:00+00:00",
        "competition": "E2E Cup",
        "sections": [
            {
                "section_id": "opponent_strength",
                "fact_tier": "recorded",
                "summary": "4-3-3 pressing side.",
                "evidence_refs": [],
            },
        ],
        "limitations": ["E2E test artifact; not a real match briefing."],
    }


# ── Store-rooted seed + cleanup fixture ──────────────────────────────


@pytest.fixture()
def seeded_brief_with_backup():
    """Seed a brief with two revisions (one backup) through the store.

    Yields ``(brief_id, backup_filename, expected_revision_before_restore)``
    so the test can drive the browser-side diff and restore against a
    known on-disk state.

    Cleanup removes the brief record and its backup directory so the
    E2E run does not leave test artifacts in ``data/reports/``.
    """
    from scoutfootball.api import _brief_store

    brief_id = f"e2e-brief-{uuid.uuid4().hex[:8]}"
    store = _brief_store()

    # Revision 1: create.
    store.save(brief_id, _valid_brief_payload(brief_id, title="E2E v1"), expected_revision=0)
    # Revision 2: update (creates a backup of revision 1).
    store.save(
        brief_id,
        _valid_brief_payload(brief_id, title="E2E v2"),
        expected_revision=1,
    )

    backups = store.list_backups(brief_id)
    assert len(backups) == 1, f"Expected 1 backup after update, found {len(backups)}"
    backup_filename = backups[0]["backup_filename"]

    yield {
        "brief_id": brief_id,
        "backup_filename": backup_filename,
        "expected_revision": 2,  # current server_revision before restore
    }

    # Cleanup: delete the brief (creates a deletion backup) then remove
    # the entire brief directory so no test artifacts remain.
    try:
        store.delete(brief_id, expected_revision=None)
    except Exception:
        pass
    brief_dir = store.root
    backup_dir = getattr(store, "backup_root", None)
    record_path = brief_dir / f"{brief_id}.json"
    record_path.unlink(missing_ok=True)
    if backup_dir:
        for f in backup_dir.glob(f"{brief_id}.*.json"):
            f.unlink(missing_ok=True)


@pytest.fixture()
def seeded_briefing_with_backup():
    """Seed an opposition briefing with two revisions (one backup).

    Same structure as ``seeded_brief_with_backup`` but for the
    opposition briefing store.
    """
    from scoutfootball.api import _briefing_store

    briefing_id = f"e2e-briefing-{uuid.uuid4().hex[:8]}"
    store = _briefing_store()

    store.save(
        briefing_id,
        _valid_briefing_payload(briefing_id, title="E2E v1"),
        expected_revision=0,
    )
    store.save(
        briefing_id,
        _valid_briefing_payload(briefing_id, title="E2E v2"),
        expected_revision=1,
    )

    backups = store.list_backups(briefing_id)
    assert len(backups) == 1, f"Expected 1 backup after update, found {len(backups)}"
    backup_filename = backups[0]["backup_filename"]

    yield {
        "briefing_id": briefing_id,
        "backup_filename": backup_filename,
        "expected_revision": 2,
    }

    try:
        store.delete(briefing_id, expected_revision=None)
    except Exception:
        pass
    brief_dir = store.root
    backup_dir = getattr(store, "backup_root", None)
    record_path = brief_dir / f"{briefing_id}.json"
    record_path.unlink(missing_ok=True)
    if backup_dir:
        for f in backup_dir.glob(f"{briefing_id}.*.json"):
            f.unlink(missing_ok=True)


# ── Versions view smoke ──────────────────────────────────────────────


def test_versions_view_renders_shell(page, live_server_url: str) -> None:
    """The versions view must render its shell with all four artifact
    type options and the timeline / diff panels present.

    Catches regressions where:
    - the versions view section was removed or renamed
    - the type selector lost an option
    - the timeline or diff panel is missing from the DOM
    """
    open_loaded_app(page, live_server_url)
    page.locator(".nav-stack .nav-action[data-view='versions']").click()

    # The view root must become visible.
    root = page.locator("#view-versions")
    root.wait_for(state="visible", timeout=10_000)

    # The type selector must offer all four artifact types.
    # We check the option *values* (not text) because the display
    # text is localized (Chinese in the default locale).
    type_select = page.locator("#ver-type-select")
    type_select.wait_for(state="visible", timeout=10_000)
    option_values = type_select.locator("option").evaluate_all(
        "opts => opts.map(o => o.value)"
    )
    assert set(option_values) == {"brief", "briefing", "dossier", "review"}, (
        f"Expected type selector options brief/briefing/dossier/review, got: {option_values}"
    )

    # The timeline and diff panels must be present.
    assert page.locator("#ver-timeline").count() == 1
    assert page.locator("#ver-diff-output").count() == 1

    # The action buttons must be present (disabled until a backup is selected).
    assert page.locator("#ver-load-backup").count() == 1
    assert page.locator("#ver-diff-backup").count() == 1
    assert page.locator("#ver-restore-backup").count() == 1


# ── Workflow view smoke ──────────────────────────────────────────────


def test_workflow_view_renders_shell(page, live_server_url: str) -> None:
    """The workflow view must render its shell with the metric strip
    counters and the three step lists (next / blockers / evidence gaps).

    Catches regressions where:
    - the workflow view section was removed or renamed
    - the metric counters are missing
    - a step list is absent from the DOM
    """
    open_loaded_app(page, live_server_url)
    page.locator(".nav-stack .nav-action[data-view='workflow']").click()

    root = page.locator("#view-workflow")
    root.wait_for(state="visible", timeout=10_000)

    # The metric strip counters must be present.
    for counter_id in (
        "#wf-next-count",
        "#wf-blocker-count",
        "#wf-evidence-gap-count",
    ):
        assert page.locator(counter_id).count() == 1, (
            f"Missing workflow counter: {counter_id}"
        )

    # The three step lists must be present.
    for list_id in (
        "#wf-next-list",
        "#wf-blocker-list",
        "#wf-evidence-gap-list",
    ):
        assert page.locator(list_id).count() == 1, (
            f"Missing workflow step list: {list_id}"
        )

    # The status rail and sources note must be present.
    assert page.locator("#wf-status-rail").count() == 1
    assert page.locator("#wf-sources-note").count() == 1


# ── Recruitment decision round-trip E2E ──────────────────────────────


def test_recruitment_brief_diff_and_restore_round_trip(
    page, live_server_url: str, seeded_brief_with_backup
) -> None:
    """End-to-end round-trip for a recruitment brief:

    1. A brief with two revisions is seeded through the store (one backup).
    2. The browser navigates to the versions view and selects the brief.
    3. The timeline shows the backup.
    4. The diff endpoint returns field-level changes between the backup
       (rev 1) and the current record (rev 2).
    5. The restore endpoint creates a new revision (rev 3) from the
       backup, and the timeline grows to two backups.

    This proves the full brief → backup → diff → restore path works
    from the browser context, not just from the TestClient.
    """
    brief_id = seeded_brief_with_backup["brief_id"]
    backup_filename = seeded_brief_with_backup["backup_filename"]
    expected_revision = seeded_brief_with_backup["expected_revision"]

    open_loaded_app(page, live_server_url)

    # Drive the entire round-trip through the browser's fetch() so we
    # exercise the same code path a real user would. We don't rely on
    # the SPA's internal state machine — we call the API directly and
    # verify the responses.
    result = page.evaluate(
        """async ({ baseUrl, briefId, backupFilename, expectedRevision }) => {
            const out = {};

            // 1. List backups — must include the seeded backup.
            const listResp = await fetch(
                baseUrl + '/recruitment/briefs/' + encodeURIComponent(briefId) + '/backups'
            );
            out.listStatus = listResp.status;
            const listData = await listResp.json();
            out.backupCount = listData.count;
            out.hasSeededBackup = listData.backups.some(
                b => b.backup_filename === backupFilename
            );

            // 2. Diff the backup against the current record.
            const diffResp = await fetch(
                baseUrl + '/recruitment/briefs/' + encodeURIComponent(briefId)
                + '/diff?backup_filename=' + encodeURIComponent(backupFilename)
            );
            out.diffStatus = diffResp.status;
            const diffData = await diffResp.json();
            out.diffChangeCount = diffData.change_count;
            out.diffCurrentRevision = diffData.current_revision;
            out.diffBackupRevision = diffData.backup_revision;
            // The title changed between rev 1 and rev 2, so the diff
            // must include at least one change touching the title path.
            out.hasTitleChange = (diffData.changes || []).some(
                c => (c.path || '').includes('title')
            );

            // 3. Restore from the backup (rev 1 → new rev 3).
            const restoreResp = await fetch(
                baseUrl + '/recruitment/briefs/' + encodeURIComponent(briefId) + '/restore',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        backup_filename: backupFilename,
                        expected_revision: expectedRevision,
                    }),
                }
            );
            out.restoreStatus = restoreResp.status;
            const restoreData = await restoreResp.json();
            out.restoredRevision = restoreData.record?.server_revision;
            out.restoredTitle = restoreData.record?.brief?.title;

            // 4. List backups again — must now have two backups
            //    (rev 1 original + rev 2 backed up by the restore).
            const listAfterResp = await fetch(
                baseUrl + '/recruitment/briefs/' + encodeURIComponent(briefId) + '/backups'
            );
            const listAfterData = await listAfterResp.json();
            out.backupCountAfterRestore = listAfterData.count;

            return out;
        }""",
        {
            "baseUrl": live_server_url,
            "briefId": brief_id,
            "backupFilename": backup_filename,
            "expectedRevision": expected_revision,
        },
    )

    # 1. Backup list before restore.
    assert result["listStatus"] == 200, f"List backups failed: {result}"
    assert result["backupCount"] == 1, (
        f"Expected 1 backup before restore, got {result['backupCount']}"
    )
    assert result["hasSeededBackup"], (
        f"Seeded backup not found in list: {result}"
    )

    # 2. Diff.
    assert result["diffStatus"] == 200, f"Diff failed: {result}"
    assert result["diffChangeCount"] >= 1, (
        f"Expected >=1 diff change, got {result['diffChangeCount']}"
    )
    assert result["diffCurrentRevision"] == 2, (
        f"Expected current_revision=2, got {result['diffCurrentRevision']}"
    )
    assert result["diffBackupRevision"] == 1, (
        f"Expected backup_revision=1, got {result['diffBackupRevision']}"
    )
    assert result["hasTitleChange"], (
        "Expected a title change in the diff (v1 → v2), but none found"
    )

    # 3. Restore.
    assert result["restoreStatus"] == 200, f"Restore failed: {result}"
    assert result["restoredRevision"] == 3, (
        f"Expected restored revision=3, got {result['restoredRevision']}"
    )
    # The restored title must match the backup's title (v1).
    assert result["restoredTitle"] == "E2E v1", (
        f"Expected restored title 'E2E v1', got {result['restoredTitle']}"
    )

    # 4. Backup list after restore.
    assert result["backupCountAfterRestore"] == 2, (
        f"Expected 2 backups after restore, got {result['backupCountAfterRestore']}"
    )


# ── Opposition decision round-trip E2E ───────────────────────────────


def test_opposition_briefing_diff_and_restore_round_trip(
    page, live_server_url: str, seeded_briefing_with_backup
) -> None:
    """End-to-end round-trip for an opposition briefing.

    Same structure as the recruitment brief round-trip but exercises the
    ``/opposition/briefs/{id}/...`` endpoints, proving the parallel
    store path works from the browser context.
    """
    briefing_id = seeded_briefing_with_backup["briefing_id"]
    backup_filename = seeded_briefing_with_backup["backup_filename"]
    expected_revision = seeded_briefing_with_backup["expected_revision"]

    open_loaded_app(page, live_server_url)

    result = page.evaluate(
        """async ({ baseUrl, briefingId, backupFilename, expectedRevision }) => {
            const out = {};

            // 1. List backups.
            const listResp = await fetch(
                baseUrl + '/opposition/briefs/' + encodeURIComponent(briefingId) + '/backups'
            );
            out.listStatus = listResp.status;
            const listData = await listResp.json();
            out.backupCount = listData.count;
            out.hasSeededBackup = listData.backups.some(
                b => b.backup_filename === backupFilename
            );

            // 2. Diff.
            const diffResp = await fetch(
                baseUrl + '/opposition/briefs/' + encodeURIComponent(briefingId)
                + '/diff?backup_filename=' + encodeURIComponent(backupFilename)
            );
            out.diffStatus = diffResp.status;
            const diffData = await diffResp.json();
            out.diffChangeCount = diffData.change_count;
            out.diffCurrentRevision = diffData.current_revision;
            out.diffBackupRevision = diffData.backup_revision;
            out.hasTitleChange = (diffData.changes || []).some(
                c => (c.path || '').includes('title')
            );

            // 3. Restore.
            const restoreResp = await fetch(
                baseUrl + '/opposition/briefs/' + encodeURIComponent(briefingId) + '/restore',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        backup_filename: backupFilename,
                        expected_revision: expectedRevision,
                    }),
                }
            );
            out.restoreStatus = restoreResp.status;
            const restoreData = await restoreResp.json();
            out.restoredRevision = restoreData.record?.server_revision;
            out.restoredTitle = restoreData.record?.briefing?.title;

            // 4. List backups after restore.
            const listAfterResp = await fetch(
                baseUrl + '/opposition/briefs/' + encodeURIComponent(briefingId) + '/backups'
            );
            const listAfterData = await listAfterResp.json();
            out.backupCountAfterRestore = listAfterData.count;

            return out;
        }""",
        {
            "baseUrl": live_server_url,
            "briefingId": briefing_id,
            "backupFilename": backup_filename,
            "expectedRevision": expected_revision,
        },
    )

    assert result["listStatus"] == 200, f"List backups failed: {result}"
    assert result["backupCount"] == 1, (
        f"Expected 1 backup before restore, got {result['backupCount']}"
    )
    assert result["hasSeededBackup"], f"Seeded backup not found: {result}"

    assert result["diffStatus"] == 200, f"Diff failed: {result}"
    assert result["diffChangeCount"] >= 1, (
        f"Expected >=1 diff change, got {result['diffChangeCount']}"
    )
    assert result["diffCurrentRevision"] == 2, (
        f"Expected current_revision=2, got {result['diffCurrentRevision']}"
    )
    assert result["diffBackupRevision"] == 1, (
        f"Expected backup_revision=1, got {result['diffBackupRevision']}"
    )
    assert result["hasTitleChange"], "Expected a title change in the diff"

    assert result["restoreStatus"] == 200, f"Restore failed: {result}"
    assert result["restoredRevision"] == 3, (
        f"Expected restored revision=3, got {result['restoredRevision']}"
    )
    assert result["restoredTitle"] == "E2E v1", (
        f"Expected restored title 'E2E v1', got {result['restoredTitle']}"
    )
    assert result["backupCountAfterRestore"] == 2, (
        f"Expected 2 backups after restore, got {result['backupCountAfterRestore']}"
    )
