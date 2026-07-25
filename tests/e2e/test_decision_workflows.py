"""E2E coverage for the P1 decision-workflow views and round-trips.

This module covers the two new P1 views (``workflow`` and ``versions``)
and the four end-to-end decision round-trips they expose:

- **Versions view smoke**: the view shell renders, the type selector
  offers all four artifact types (brief / briefing / dossier / review),
  and the timeline + diff panels are present.
- **Workflow view smoke**: the view shell renders, the metric strip
  counters are present, and the three step lists (next / blockers /
  evidence gaps) are in the DOM.
- **Workflow view OFFLINE state**: the four workflow API endpoints are
  route-aborted; the view must surface one blocker per artifact family
  (brief / briefing / dossier / review) and must NOT offer the online
  create-* next-steps.
- **Workflow view LIVE contract**: an adaptive contract test that fetches
  the live counts from the four list endpoints and asserts the
  bidirectional implications between store state and the inferred
  create-* / *-missing steps for all four artifact families.
- **Recruitment decision round-trip (brief)**: a brief with two
  revisions is seeded through the store; the browser then loads the
  versions view, selects the brief, loads the backup timeline, diffs a
  backup against the current record, and restores from the backup —
  verifying the new revision appears and the restored payload matches.
- **Opposition decision round-trip (briefing)**: same shape as above
  but for an opposition briefing, exercising the parallel store path.
- **Recruitment decision round-trip (dossier)**: same shape as the
  brief round-trip but for a decision dossier, exercising the
  ``/recruitment/dossiers/{id}/...`` endpoint family.
- **Opposition decision round-trip (review)**: same shape as the
  briefing round-trip but for a post-match review, exercising the
  ``/opposition/reviews/{id}/...`` endpoint family.

The round-trip tests seed data through the store directly (not via the
API) because the public API only exposes ``POST /recruitment/briefs``
(and the symmetric dossier / briefing / review create endpoints) for
creating new records (``expected_revision=0``); there is no ``PUT`` /
``PATCH`` endpoint for updates.  The store-level update path is
already covered by unit tests (``test_brief_backup_restore.py``);
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


def _valid_dossier_payload(dossier_id: str, *, title: str = "E2E dossier") -> dict:
    """Return a minimal valid decision-dossier payload for E2E seeding.

    The dossier stays in ``draft`` status so we can omit ``decision``
    (the model_validator requires ``decision`` only when
    ``status == "decided"``).
    """
    from scoutfootball.recruitment.dossier import DOSSIER_SCHEMA, DOSSIER_VERSION

    return {
        "schema": DOSSIER_SCHEMA,
        "version": DOSSIER_VERSION,
        "dossier_id": dossier_id,
        "revision": 1,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "author": "e2e-test",
        "title": title,
        "brief_id": "",
        "candidate_player_id": "understat|1234",
        "candidate_player_name": "E2E Player",
        "candidate_team_name": "E2E Club",
        "candidate_season_id": "2425",
        "status": "draft",
        "decision": None,
        "decision_note": "",
        "supporting_evidence": [],
        "counter_evidence": [],
        "comparisons": [],
        "risks": [],
        "human_opinion": "",
        "recommendation": "",
        "linked_artifacts": [],
        "notes": "E2E seeded dossier for versions-view round-trip.",
        "limitations": ["E2E test artifact; not a real scouting dossier."],
    }


def _valid_review_payload(review_id: str, *, title: str = "E2E review") -> dict:
    """Return a minimal valid post-match-review payload for E2E seeding.

    The review stays in ``draft`` status so we can omit ``decision``
    (the model_validator requires ``decision`` only when
    ``status == "finalized"``).
    """
    from scoutfootball.opposition.post_match_review import (
        REVIEW_SCHEMA,
        REVIEW_VERSION,
    )

    return {
        "schema": REVIEW_SCHEMA,
        "version": REVIEW_VERSION,
        "review_id": review_id,
        "revision": 1,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "author": "e2e-test",
        "title": title,
        "briefing_id": "",
        "match_id": "fd-match-e2e",
        "home_team": "E2E Home FC",
        "away_team": "E2E Away FC",
        "kickoff_at": "2026-08-15T15:00:00+00:00",
        "competition": "E2E Cup",
        "season": "2526",
        "final_score_home": 2,
        "final_score_away": 1,
        "status": "draft",
        "decision": None,
        "decision_note": "",
        "hypothesis_results": [],
        "falsified_patterns": [],
        "new_questions": [],
        "supporting_evidence": [],
        "counter_evidence": [],
        "human_opinion": "",
        "recommendation": "",
        "linked_artifacts": [],
        "notes": "E2E seeded review for versions-view round-trip.",
        "limitations": ["E2E test artifact; not a real post-match review."],
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


@pytest.fixture()
def seeded_dossier_with_backup():
    """Seed a decision dossier with two revisions (one backup) through the store.

    Same structure as ``seeded_brief_with_backup`` but for the
    decision-dossier store.  Cleanup removes the dossier record and its
    backup directory so the E2E run does not leave test artifacts in
    ``data/reports/``.
    """
    from scoutfootball.api import _dossier_store

    dossier_id = f"e2e-dossier-{uuid.uuid4().hex[:8]}"
    store = _dossier_store()

    store.save(
        dossier_id,
        _valid_dossier_payload(dossier_id, title="E2E v1"),
        expected_revision=0,
    )
    store.save(
        dossier_id,
        _valid_dossier_payload(dossier_id, title="E2E v2"),
        expected_revision=1,
    )

    backups = store.list_backups(dossier_id)
    assert len(backups) == 1, f"Expected 1 backup after update, found {len(backups)}"
    backup_filename = backups[0]["backup_filename"]

    yield {
        "dossier_id": dossier_id,
        "backup_filename": backup_filename,
        "expected_revision": 2,
    }

    try:
        store.delete(dossier_id, expected_revision=None)
    except Exception:
        pass
    dossier_dir = store.root
    backup_dir = getattr(store, "backup_root", None)
    record_path = dossier_dir / f"{dossier_id}.json"
    record_path.unlink(missing_ok=True)
    if backup_dir:
        for f in backup_dir.glob(f"{dossier_id}.*.json"):
            f.unlink(missing_ok=True)


@pytest.fixture()
def seeded_review_with_backup():
    """Seed a post-match review with two revisions (one backup).

    Same structure as ``seeded_dossier_with_backup`` but for the
    post-match-review store.
    """
    from scoutfootball.api import _review_store

    review_id = f"e2e-review-{uuid.uuid4().hex[:8]}"
    store = _review_store()

    store.save(
        review_id,
        _valid_review_payload(review_id, title="E2E v1"),
        expected_revision=0,
    )
    store.save(
        review_id,
        _valid_review_payload(review_id, title="E2E v2"),
        expected_revision=1,
    )

    backups = store.list_backups(review_id)
    assert len(backups) == 1, f"Expected 1 backup after update, found {len(backups)}"
    backup_filename = backups[0]["backup_filename"]

    yield {
        "review_id": review_id,
        "backup_filename": backup_filename,
        "expected_revision": 2,
    }

    try:
        store.delete(review_id, expected_revision=None)
    except Exception:
        pass
    review_dir = store.root
    backup_dir = getattr(store, "backup_root", None)
    record_path = review_dir / f"{review_id}.json"
    record_path.unlink(missing_ok=True)
    if backup_dir:
        for f in backup_dir.glob(f"{review_id}.*.json"):
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


# ── Workflow view state inference (OFFLINE + LIVE contract) ────────


def test_workflow_view_offline_state_shows_api_blockers(
    page, live_server_url: str
) -> None:
    """When the four workflow API endpoints are unreachable, the workflow
    view must surface one blocker per artifact family (brief / briefing /
    dossier / review) and must NOT offer the create-* next-steps that
    belong to the online branches.

    This is the OFFLINE / failure-state coverage for the decision layer
    of the golden workflows.  It is fully deterministic because route
    interception does not depend on existing store contents.

    Catches regressions where:
    - a fetch error is swallowed instead of being surfaced as a blocker
    - the offline branch falls through to the empty-state branch and
      pretends the store is empty rather than unreachable
    - a blocker is added for one artifact but dropped for another
    """
    # Abort the four endpoints the workflow view fetches.  We scope each
    # pattern to the list path so we do not disturb the initial /artifacts
    # load or other views.
    for pattern in (
        "**/recruitment/briefs*",
        "**/opposition/briefs*",
        "**/recruitment/dossiers*",
        "**/opposition/reviews*",
    ):
        page.route(pattern, lambda route: route.abort())

    open_loaded_app(page, live_server_url)
    page.locator(".nav-stack .nav-action[data-view='workflow']").click()
    page.locator("#view-workflow").wait_for(state="visible", timeout=10_000)

    # Each offline blocker is rendered as <li data-wf-step-id="...">.
    # Wait for all four to attach; if any is missing the locator wait
    # will time out and the test will fail with a clear message.
    for blocker_id in (
        "brief-api-offline",
        "briefing-api-offline",
        "dossier-api-offline",
        "review-api-offline",
    ):
        page.locator(
            f"#wf-blocker-list li[data-wf-step-id='{blocker_id}']"
        ).wait_for(state="attached", timeout=10_000)

    # Collect the full blocker list to assert completeness in one shot.
    blockers = page.evaluate(
        """() => [...document.querySelectorAll(
            "#wf-blocker-list li[data-wf-step-id]"
        )].map(li => li.dataset.wfStepId)"""
    )
    assert set(blockers) == {
        "brief-api-offline",
        "briefing-api-offline",
        "dossier-api-offline",
        "review-api-offline",
    }, f"Expected exactly the 4 offline blockers, got {blockers!r}"

    # The online create-* next-steps must NOT appear when the API is
    # offline (they live in the else-if-no-error branch).
    next_ids = page.evaluate(
        """() => [...document.querySelectorAll(
            "#wf-next-list li[data-wf-step-id]"
        )].map(li => li.dataset.wfStepId)"""
    )
    for online_step in ("create-brief", "create-briefing", "create-dossier", "create-review"):
        assert online_step not in next_ids, (
            f"{online_step} appeared in next-list while API is offline: {next_ids!r}"
        )


def test_workflow_view_inference_matches_api_state(
    page, live_server_url: str
) -> None:
    """The workflow view's inferred steps must match the actual API state.

    This is an adaptive contract test between the four list endpoints
    (/recruitment/briefs, /opposition/briefs, /recruitment/dossiers,
    /opposition/reviews) and the frontend ``_workflowInferSteps`` logic.
    It is deterministic regardless of how many records the maintainer
    currently has in the store: it fetches the live counts and asserts
    the bidirectional implications for each artifact family.

    For each artifact family the inference rule under test is:

        create-<x> in next   IFF   ( precursor count > 0 AND own count == 0 )
        <x>-missing in gaps  IFF   ( precursor count > 0 AND own count == 0 )
        create-<first> in next  IFF   own count == 0   (no precursor needed)
        <first>-missing in gaps  IFF   own count == 0

    Brief and briefing are the "first" artifacts (no precursor); dossier
    requires briefs > 0, review requires briefings > 0.

    Catches regressions where:
    - the workflow view shows create-brief even though briefs exist
    - the workflow view shows create-dossier even though a dossier exists
    - the workflow view offers a create-* step while an offline blocker
      is also shown (the blocker must short-circuit the create step)
    """
    open_loaded_app(page, live_server_url)

    # 1. Fetch the actual store state via the four list endpoints.  We
    #    read counts (not contents) so the assertion is independent of
    #    record shape and stays robust as the schema evolves.
    counts = page.evaluate(
        """async (baseUrl) => {
            const safe = async (path, key) => {
                try {
                    const r = await fetch(baseUrl + path);
                    if (!r.ok) return { count: 0, error: true };
                    const d = await r.json();
                    return { count: Array.isArray(d[key]) ? d[key].length : 0, error: false };
                } catch (e) {
                    return { count: 0, error: true };
                }
            };
            return {
                briefs:    await safe("/recruitment/briefs?limit=100", "briefs"),
                briefings: await safe("/opposition/briefs?limit=100", "briefings"),
                dossiers:  await safe("/recruitment/dossiers?limit=100", "dossiers"),
                reviews:   await safe("/opposition/reviews?limit=100", "reviews"),
            };
        }""",
        live_server_url,
    )

    # If any endpoint errored at the API level the contract test cannot
    # run cleanly; surface that as an explicit failure rather than letting
    # the implications below pass vacuously.
    for name, info in counts.items():
        assert not info["error"], (
            f"API endpoint for {name} returned an error; cannot run contract test: {info}"
        )

    briefs_n = counts["briefs"]["count"]
    briefings_n = counts["briefings"]["count"]
    dossiers_n = counts["dossiers"]["count"]
    reviews_n = counts["reviews"]["count"]

    # 2. Navigate to the workflow view.  renderWorkflow() fires the four
    #    fetches and re-renders after they settle.  We wait for the
    #    second render by polling until the next-list step IDs are stable
    #    across two reads 400ms apart; this avoids a hardcoded sleep
    #    while tolerating localhost fetch latency.
    page.locator(".nav-stack .nav-action[data-view='workflow']").click()
    page.locator("#view-workflow").wait_for(state="visible", timeout=10_000)

    def _collect_step_ids() -> dict:
        return page.evaluate(
            """() => {
                const ids = (sel) => [...document.querySelectorAll(
                    sel + " li[data-wf-step-id]"
                )].map(li => li.dataset.wfStepId);
                return {
                    next: ids("#wf-next-list"),
                    blockers: ids("#wf-blocker-list"),
                    gaps: ids("#wf-evidence-gap-list"),
                };
            }"""
        )

    # Poll until stable.  20 iterations × 400ms = 8s max, well within
    # the localhost fetch latency budget.
    prev = None
    for _ in range(20):
        cur = _collect_step_ids()
        if cur == prev and cur is not None:
            break
        prev = cur
        page.wait_for_timeout(400)
    assert cur is not None, "workflow view step IDs never became readable"
    assert cur == prev, (
        "workflow view step IDs did not stabilize within 8s; "
        f"last two reads differed:\n  {prev!r}\n  {cur!r}"
    )

    next_ids = set(cur["next"])
    blocker_ids = set(cur["blockers"])
    gap_ids = set(cur["gaps"])

    # 3. No offline blockers should be present when the API is up.
    for offline_blocker in (
        "brief-api-offline",
        "briefing-api-offline",
        "dossier-api-offline",
        "review-api-offline",
    ):
        assert offline_blocker not in blocker_ids, (
            f"{offline_blocker} shown while API is reachable: {blocker_ids!r}"
        )

    # 4. Bidirectional implications for each artifact family.
    #    Brief / briefing (first artifacts, no precursor).
    assert ("create-brief" in next_ids) == (briefs_n == 0), (
        f"create-brief presence mismatch: in_next={'create-brief' in next_ids}, "
        f"briefs_n={briefs_n}"
    )
    assert ("brief-missing" in gap_ids) == (briefs_n == 0), (
        f"brief-missing presence mismatch: in_gaps={'brief-missing' in gap_ids}, "
        f"briefs_n={briefs_n}"
    )
    assert ("create-briefing" in next_ids) == (briefings_n == 0), (
        f"create-briefing presence mismatch: in_next={'create-briefing' in next_ids}, "
        f"briefings_n={briefings_n}"
    )
    assert ("briefing-missing" in gap_ids) == (briefings_n == 0), (
        f"briefing-missing presence mismatch: in_gaps={'briefing-missing' in gap_ids}, "
        f"briefings_n={briefings_n}"
    )

    #    Dossier (requires briefs > 0 as precursor).
    dossier_should_suggest = (briefs_n > 0 and dossiers_n == 0)
    assert ("create-dossier" in next_ids) == dossier_should_suggest, (
        f"create-dossier presence mismatch: in_next={'create-dossier' in next_ids}, "
        f"briefs_n={briefs_n}, dossiers_n={dossiers_n}"
    )
    assert ("dossier-missing" in gap_ids) == dossier_should_suggest, (
        f"dossier-missing presence mismatch: in_gaps={'dossier-missing' in gap_ids}, "
        f"briefs_n={briefs_n}, dossiers_n={dossiers_n}"
    )

    #    Review (requires briefings > 0 as precursor).
    review_should_suggest = (briefings_n > 0 and reviews_n == 0)
    assert ("create-review" in next_ids) == review_should_suggest, (
        f"create-review presence mismatch: in_next={'create-review' in next_ids}, "
        f"briefings_n={briefings_n}, reviews_n={reviews_n}"
    )
    assert ("review-missing" in gap_ids) == review_should_suggest, (
        f"review-missing presence mismatch: in_gaps={'review-missing' in gap_ids}, "
        f"briefings_n={briefings_n}, reviews_n={reviews_n}"
    )


@pytest.fixture()
def seeded_workflow_field_gaps():
    """Seed two briefs and two briefings that exercise field-level gaps.

    Yields a dict with four IDs:

    - ``complete_brief_id``: a brief with ``budget_eur > 0`` and
      ``minimum_minutes > 0``.  Must NOT trigger ``brief-gap-*``.
    - ``incomplete_brief_id``: a brief with both fields ``None``.  MUST
      trigger ``brief-gap-*``.
    - ``classified_briefing_id``: a briefing with at least one section
      whose ``fact_tier != "unknown"``.  Must NOT trigger
      ``briefing-tier-*``.
    - ``unclassified_briefing_id``: a briefing whose every section has
      ``fact_tier == "unknown"``.  MUST trigger ``briefing-tier-*``.

    Cleanup removes all four records and their backup directories so
    the E2E run leaves no test artifacts in ``data/reports/``.
    """
    from scoutfootball.api import _brief_store, _briefing_store

    brief_store = _brief_store()
    briefing_store = _briefing_store()

    complete_brief_id = f"e2e-wf-complete-{uuid.uuid4().hex[:8]}"
    incomplete_brief_id = f"e2e-wf-incomplete-{uuid.uuid4().hex[:8]}"
    classified_briefing_id = f"e2e-wf-classified-{uuid.uuid4().hex[:8]}"
    unclassified_briefing_id = f"e2e-wf-uncategorized-{uuid.uuid4().hex[:8]}"

    # Complete brief: budget + minutes both set > 0.
    brief_store.save(
        complete_brief_id,
        _valid_brief_payload(complete_brief_id, title="E2E complete brief"),
        expected_revision=0,
    )
    # Incomplete brief: both fields None.
    incomplete_payload = _valid_brief_payload(
        incomplete_brief_id, title="E2E incomplete brief"
    )
    incomplete_payload["budget_eur"] = None
    incomplete_payload["minimum_minutes"] = None
    brief_store.save(incomplete_brief_id, incomplete_payload, expected_revision=0)

    # Classified briefing: one section with fact_tier="recorded".
    briefing_store.save(
        classified_briefing_id,
        _valid_briefing_payload(classified_briefing_id, title="E2E classified"),
        expected_revision=0,
    )
    # Unclassified briefing: all sections fact_tier="unknown".
    unclassified_payload = _valid_briefing_payload(
        unclassified_briefing_id, title="E2E unclassified"
    )
    unclassified_payload["sections"] = [
        {
            "section_id": "opponent_strength",
            "fact_tier": "unknown",
            "summary": "Not yet classified.",
            "evidence_refs": [],
        },
    ]
    briefing_store.save(
        unclassified_briefing_id, unclassified_payload, expected_revision=0
    )

    yield {
        "complete_brief_id": complete_brief_id,
        "incomplete_brief_id": incomplete_brief_id,
        "classified_briefing_id": classified_briefing_id,
        "unclassified_briefing_id": unclassified_briefing_id,
    }

    # Cleanup: best-effort delete + unlink for all four records.
    for store, bid in (
        (brief_store, complete_brief_id),
        (brief_store, incomplete_brief_id),
        (briefing_store, classified_briefing_id),
        (briefing_store, unclassified_briefing_id),
    ):
        try:
            store.delete(bid, expected_revision=None)
        except Exception:
            pass
        record_path = store.root / f"{bid}.json"
        record_path.unlink(missing_ok=True)
        backup_dir = getattr(store, "backup_root", None)
        if backup_dir:
            for f in backup_dir.glob(f"{bid}.*.json"):
                f.unlink(missing_ok=True)


def test_workflow_view_field_gaps_match_record_state(
    page, live_server_url: str, seeded_workflow_field_gaps
) -> None:
    """Field-level evidence gaps must reflect the actual record content.

    The count-based contract test
    (``test_workflow_view_inference_matches_api_state``) verifies the
    create-* / *-missing invariants.  This test complements it by
    verifying the *field-level* evidence gaps that depend on summary
    fields the list endpoints must surface:

    - A brief with ``budget_eur > 0`` and ``minimum_minutes > 0`` must
      NOT produce ``brief-gap-<id>``.
    - A brief with either field ``None`` MUST produce ``brief-gap-<id>``.
    - A briefing with at least one non-unknown ``fact_tier`` must NOT
      produce ``briefing-tier-<id>``.
    - A briefing whose sections are all ``fact_tier == "unknown"`` MUST
      produce ``briefing-tier-<id>``.

    Catches the regression where ``list_records`` summaries omitted
    ``budget_eur`` / ``minimum_minutes`` / ``sections`` and the workflow
    view flagged every brief and briefing as an evidence gap.
    """
    complete_brief = seeded_workflow_field_gaps["complete_brief_id"]
    incomplete_brief = seeded_workflow_field_gaps["incomplete_brief_id"]
    classified_briefing = seeded_workflow_field_gaps["classified_briefing_id"]
    unclassified_briefing = seeded_workflow_field_gaps["unclassified_briefing_id"]

    open_loaded_app(page, live_server_url)

    page.locator(".nav-stack .nav-action[data-view='workflow']").click()
    page.locator("#view-workflow").wait_for(state="visible", timeout=10_000)

    def _collect_gap_ids() -> set:
        return set(
            page.evaluate(
                """() => [...document.querySelectorAll(
                    "#wf-evidence-gap-list li[data-wf-step-id]"
                )].map(li => li.dataset.wfStepId)"""
            )
        )

    # Poll until stable across two reads 400ms apart (same pattern as the
    # count-based contract test).
    prev = None
    cur = None
    for _ in range(20):
        cur = _collect_gap_ids()
        if cur == prev and cur is not None:
            break
        prev = cur
        page.wait_for_timeout(400)
    assert cur is not None, "workflow view gap IDs never became readable"
    assert cur == prev, (
        "workflow view gap IDs did not stabilize within 8s; "
        f"last two reads differed:\n  {prev!r}\n  {cur!r}"
    )

    # Complete brief must NOT be flagged.
    assert f"brief-gap-{complete_brief}" not in cur, (
        f"Complete brief {complete_brief} was flagged as an evidence gap "
        f"even though budget_eur and minimum_minutes are both set > 0. "
        f"This is a false positive caused by list_records summaries "
        f"omitting the fields the workflow inference reads. gaps={cur!r}"
    )
    # Incomplete brief MUST be flagged.
    assert f"brief-gap-{incomplete_brief}" in cur, (
        f"Incomplete brief {incomplete_brief} (budget_eur=None, "
        f"minimum_minutes=None) was not flagged as an evidence gap. "
        f"gaps={cur!r}"
    )
    # Classified briefing must NOT be flagged.
    assert f"briefing-tier-{classified_briefing}" not in cur, (
        f"Classified briefing {classified_briefing} was flagged as an "
        f"evidence gap even though it has a section with "
        f"fact_tier='recorded'. gaps={cur!r}"
    )
    # Unclassified briefing MUST be flagged.
    assert f"briefing-tier-{unclassified_briefing}" in cur, (
        f"Unclassified briefing {unclassified_briefing} (all sections "
        f"fact_tier='unknown') was not flagged as an evidence gap. "
        f"gaps={cur!r}"
    )


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


# ── Recruitment decision round-trip E2E (dossier) ────────────────────


def test_recruitment_dossier_diff_and_restore_round_trip(
    page, live_server_url: str, seeded_dossier_with_backup
) -> None:
    """End-to-end round-trip for a decision dossier.

    Same structure as the recruitment brief round-trip but exercises the
    ``/recruitment/dossiers/{id}/...`` endpoint family, proving the
    dossier store + diff + restore path works from the browser context.
    This closes the G1 / P1 E2E coverage gap where only brief and
    briefing round-trips had real-browser coverage (CAPABILITIES.md).
    """
    dossier_id = seeded_dossier_with_backup["dossier_id"]
    backup_filename = seeded_dossier_with_backup["backup_filename"]
    expected_revision = seeded_dossier_with_backup["expected_revision"]

    open_loaded_app(page, live_server_url)

    result = page.evaluate(
        """async ({ baseUrl, dossierId, backupFilename, expectedRevision }) => {
            const out = {};

            // 1. List backups — must include the seeded backup.
            const listResp = await fetch(
                baseUrl + '/recruitment/dossiers/' + encodeURIComponent(dossierId) + '/backups'
            );
            out.listStatus = listResp.status;
            const listData = await listResp.json();
            out.backupCount = listData.count;
            out.hasSeededBackup = listData.backups.some(
                b => b.backup_filename === backupFilename
            );

            // 2. Diff the backup against the current record.
            const diffResp = await fetch(
                baseUrl + '/recruitment/dossiers/' + encodeURIComponent(dossierId)
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
                baseUrl + '/recruitment/dossiers/' + encodeURIComponent(dossierId) + '/restore',
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
            out.restoredTitle = restoreData.record?.dossier?.title;

            // 4. List backups again — must now have two backups.
            const listAfterResp = await fetch(
                baseUrl + '/recruitment/dossiers/' + encodeURIComponent(dossierId) + '/backups'
            );
            const listAfterData = await listAfterResp.json();
            out.backupCountAfterRestore = listAfterData.count;

            return out;
        }""",
        {
            "baseUrl": live_server_url,
            "dossierId": dossier_id,
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
        "Expected a title change in the dossier diff (v1 → v2), but none found"
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


# ── Opposition decision round-trip E2E (review) ──────────────────────


def test_opposition_review_diff_and_restore_round_trip(
    page, live_server_url: str, seeded_review_with_backup
) -> None:
    """End-to-end round-trip for a post-match review.

    Same structure as the opposition briefing round-trip but exercises
    the ``/opposition/reviews/{id}/...`` endpoint family, proving the
    review store + diff + restore path works from the browser context.
    This closes the G1 / P1 E2E coverage gap where only brief and
    briefing round-trips had real-browser coverage (CAPABILITIES.md).
    """
    review_id = seeded_review_with_backup["review_id"]
    backup_filename = seeded_review_with_backup["backup_filename"]
    expected_revision = seeded_review_with_backup["expected_revision"]

    open_loaded_app(page, live_server_url)

    result = page.evaluate(
        """async ({ baseUrl, reviewId, backupFilename, expectedRevision }) => {
            const out = {};

            // 1. List backups — must include the seeded backup.
            const listResp = await fetch(
                baseUrl + '/opposition/reviews/' + encodeURIComponent(reviewId) + '/backups'
            );
            out.listStatus = listResp.status;
            const listData = await listResp.json();
            out.backupCount = listData.count;
            out.hasSeededBackup = listData.backups.some(
                b => b.backup_filename === backupFilename
            );

            // 2. Diff the backup against the current record.
            const diffResp = await fetch(
                baseUrl + '/opposition/reviews/' + encodeURIComponent(reviewId)
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

            // 3. Restore from the backup (rev 1 → new rev 3).
            const restoreResp = await fetch(
                baseUrl + '/opposition/reviews/' + encodeURIComponent(reviewId) + '/restore',
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
            out.restoredTitle = restoreData.record?.review?.title;

            // 4. List backups again — must now have two backups.
            const listAfterResp = await fetch(
                baseUrl + '/opposition/reviews/' + encodeURIComponent(reviewId) + '/backups'
            );
            const listAfterData = await listAfterResp.json();
            out.backupCountAfterRestore = listAfterData.count;

            return out;
        }""",
        {
            "baseUrl": live_server_url,
            "reviewId": review_id,
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
        "Expected a title change in the review diff (v1 → v2), but none found"
    )

    # 3. Restore.
    assert result["restoreStatus"] == 200, f"Restore failed: {result}"
    assert result["restoredRevision"] == 3, (
        f"Expected restored revision=3, got {result['restoredRevision']}"
    )
    assert result["restoredTitle"] == "E2E v1", (
        f"Expected restored title 'E2E v1', got {result['restoredTitle']}"
    )

    # 4. Backup list after restore.
    assert result["backupCountAfterRestore"] == 2, (
        f"Expected 2 backups after restore, got {result['backupCountAfterRestore']}"
    )


# ── Versions view: create-dialog visibility ─────────────────────────


def test_versions_view_create_button_visibility(
    page, live_server_url: str
) -> None:
    """The create button must be hidden for brief/briefing and visible
    for dossier/review.

    Catches regressions where:
    - the create button is shown for brief/briefing (which have their own
      create flows in Scouting / Matches and must not be creatable here)
    - the create button is missing for dossier/review (the closing
      artifacts whose only create path used to be the CLI)
    - the create hint text is missing or not localised
    """
    open_loaded_app(page, live_server_url)
    page.locator(".nav-stack .nav-action[data-view='versions']").click()
    page.locator("#view-versions").wait_for(state="visible", timeout=10_000)

    type_select = page.locator("#ver-type-select")
    type_select.wait_for(state="visible", timeout=10_000)
    create_btn = page.locator("#ver-create")
    create_hint = page.locator("#ver-create-hint")

    # brief: not creatable here → button hidden, hint explains.
    type_select.select_option("brief")
    page.wait_for_timeout(150)
    assert create_btn.get_attribute("hidden") is not None, (
        "Create button should be hidden for brief type"
    )
    assert create_hint.inner_text().strip() != "", (
        "Create hint should not be empty when create is disabled"
    )

    # briefing: not creatable here → button hidden.
    type_select.select_option("briefing")
    page.wait_for_timeout(150)
    assert create_btn.get_attribute("hidden") is not None, (
        "Create button should be hidden for briefing type"
    )

    # dossier: creatable → button visible, hint localised.
    type_select.select_option("dossier")
    page.wait_for_timeout(150)
    assert create_btn.get_attribute("hidden") is None, (
        "Create button should be visible for dossier type"
    )
    assert create_hint.inner_text().strip() != "", (
        "Create hint should not be empty for dossier type"
    )

    # review: creatable → button visible.
    type_select.select_option("review")
    page.wait_for_timeout(150)
    assert create_btn.get_attribute("hidden") is None, (
        "Create button should be visible for review type"
    )
    assert create_hint.inner_text().strip() != "", (
        "Create hint should not be empty for review type"
    )


# ── Versions view: create dossier round-trip ─────────────────────────


def test_versions_view_create_dossier_round_trip(
    page, live_server_url: str
) -> None:
    """End-to-end create flow for a decision dossier via the browser.

    Drives the full UI flow:
    1. Open the versions view, switch to dossier type.
    2. Click the create button → dialog opens with a small form.
    3. Fill in a title (required) and leave the ID blank (auto-generated).
    4. Submit → the dialog closes, the new dossier appears in the list,
       and the live record can be fetched via the API.

    Catches regressions where:
    - the create dialog does not open from the toolbar button
    - required-field validation is missing (empty title accepted)
    - the auto-generated ID does not match the dossier- prefix pattern
    - the created record is not persisted (list / fetch fails)
    - the dialog does not close on success
    """
    open_loaded_app(page, live_server_url)
    page.locator(".nav-stack .nav-action[data-view='versions']").click()
    page.locator("#view-versions").wait_for(state="visible", timeout=10_000)

    type_select = page.locator("#ver-type-select")
    type_select.wait_for(state="visible", timeout=10_000)
    type_select.select_option("dossier")
    page.wait_for_timeout(200)

    # Snapshot dossier count before create.
    before_count = page.evaluate(
        """async (baseUrl) => {
            const r = await fetch(baseUrl + '/recruitment/dossiers?limit=100');
            const d = await r.json();
            return Array.isArray(d.dossiers) ? d.dossiers.length : 0;
        }""",
        live_server_url,
    )

    # Open the create dialog.
    page.locator("#ver-create").click()
    page.locator("#ver-create-dialog").wait_for(state="visible", timeout=5_000)

    # The dialog must contain the dossier form fields.
    assert page.locator("#ver-create-input-title").count() == 1
    assert page.locator("#ver-create-input-dossier_id").count() == 1
    assert page.locator("#ver-create-input-brief_id").count() == 1

    # Submit with an empty title — must be rejected client-side.
    page.locator("#ver-create-submit").click()
    # The dialog must still be open (validation failed).
    page.wait_for_timeout(200)
    is_still_open = page.evaluate(
        "() => !!document.getElementById('ver-create-dialog').open"
    )
    assert is_still_open, (
        "Dialog should still be open after submitting with empty title"
    )

    # Fill in a title and submit. The ID field is left blank so the
    # frontend auto-generates a dossier-YYYYMMDD-xxxxxxxx value.
    title_input = page.locator("#ver-create-input-title")
    title_input.fill("E2E created dossier")
    page.locator("#ver-create-submit").click()

    # The dialog must close on success. Poll for up to 5s.
    for _ in range(25):
        is_open = page.evaluate(
            "() => !!document.getElementById('ver-create-dialog').open"
        )
        if not is_open:
            break
        page.wait_for_timeout(200)
    assert not is_open, "Create dialog did not close after successful submit"

    # The new dossier must appear in the versions view record list.
    record_select = page.locator("#ver-record-select")
    for _ in range(25):
        options = record_select.locator("option").evaluate_all(
            "opts => opts.map(o => o.value)"
        )
        if any(o for o in options):
            break
        page.wait_for_timeout(200)
    assert any(o for o in options), (
        f"No dossier records in selector after create: {options!r}"
    )

    # The newly created record must be fetchable via the API.
    after_count = page.evaluate(
        """async (baseUrl) => {
            const r = await fetch(baseUrl + '/recruitment/dossiers?limit=100');
            const d = await r.json();
            return Array.isArray(d.dossiers) ? d.dossiers.length : 0;
        }""",
        live_server_url,
    )
    assert after_count == before_count + 1, (
        f"Expected dossier count {before_count + 1} after create, got {after_count}"
    )

    # The new record must carry the auto-generated dossier- prefix.
    new_records = page.evaluate(
        """async (baseUrl) => {
            const r = await fetch(baseUrl + '/recruitment/dossiers?limit=100');
            const d = await r.json();
            return (Array.isArray(d.dossiers) ? d.dossiers : [])
                .map(x => x.dossier_id || '');
        }""",
        live_server_url,
    )
    assert any(rid.startswith("dossier-") for rid in new_records), (
        f"Expected a dossier- prefixed ID in new records: {new_records!r}"
    )

    # Cleanup: delete the created dossier(s) via the store so no test
    # artifacts remain.
    from scoutfootball.api import _dossier_store

    store = _dossier_store()
    for cid in new_records:
        if not cid.startswith("dossier-"):
            continue
        try:
            store.delete(cid, expected_revision=None)
        except Exception:
            pass
        record_path = store.root / f"{cid}.json"
        record_path.unlink(missing_ok=True)
        backup_dir = getattr(store, "backup_root", None)
        if backup_dir:
            for f in backup_dir.glob(f"{cid}.*.json"):
                f.unlink(missing_ok=True)


# ── Versions view: create review round-trip ──────────────────────────


def test_versions_view_create_review_round_trip(
    page, live_server_url: str
) -> None:
    """End-to-end create flow for a post-match review via the browser.

    Same shape as the dossier create test but exercises the
    ``/opposition/reviews`` endpoint family and the review form fields.
    Catches regressions where the review create path diverges from the
    dossier path (e.g. wrong schema, missing fields, wrong ID prefix).
    """
    open_loaded_app(page, live_server_url)
    page.locator(".nav-stack .nav-action[data-view='versions']").click()
    page.locator("#view-versions").wait_for(state="visible", timeout=10_000)

    type_select = page.locator("#ver-type-select")
    type_select.wait_for(state="visible", timeout=10_000)
    type_select.select_option("review")
    page.wait_for_timeout(200)

    before_count = page.evaluate(
        """async (baseUrl) => {
            const r = await fetch(baseUrl + '/opposition/reviews?limit=100');
            const d = await r.json();
            return Array.isArray(d.reviews) ? d.reviews.length : 0;
        }""",
        live_server_url,
    )

    page.locator("#ver-create").click()
    page.locator("#ver-create-dialog").wait_for(state="visible", timeout=5_000)

    assert page.locator("#ver-create-input-title").count() == 1
    assert page.locator("#ver-create-input-review_id").count() == 1
    assert page.locator("#ver-create-input-briefing_id").count() == 1

    title_input = page.locator("#ver-create-input-title")
    title_input.fill("E2E created review")
    page.locator("#ver-create-submit").click()

    for _ in range(25):
        is_open = page.evaluate(
            "() => !!document.getElementById('ver-create-dialog').open"
        )
        if not is_open:
            break
        page.wait_for_timeout(200)
    assert not is_open, "Create dialog did not close after successful submit"

    after_count = page.evaluate(
        """async (baseUrl) => {
            const r = await fetch(baseUrl + '/opposition/reviews?limit=100');
            const d = await r.json();
            return Array.isArray(d.reviews) ? d.reviews.length : 0;
        }""",
        live_server_url,
    )
    assert after_count == before_count + 1, (
        f"Expected review count {before_count + 1} after create, got {after_count}"
    )

    new_records = page.evaluate(
        """async (baseUrl) => {
            const r = await fetch(baseUrl + '/opposition/reviews?limit=100');
            const d = await r.json();
            return (Array.isArray(d.reviews) ? d.reviews : [])
                .map(x => x.review_id || '');
        }""",
        live_server_url,
    )
    assert any(rid.startswith("review-") for rid in new_records), (
        f"Expected a review- prefixed ID in new records: {new_records!r}"
    )

    # Cleanup.
    from scoutfootball.api import _review_store

    store = _review_store()
    for rid in new_records:
        if not rid.startswith("review-"):
            continue
        try:
            store.delete(rid, expected_revision=None)
        except Exception:
            pass
        record_path = store.root / f"{rid}.json"
        record_path.unlink(missing_ok=True)
        backup_dir = getattr(store, "backup_root", None)
        if backup_dir:
            for f in backup_dir.glob(f"{rid}.*.json"):
                f.unlink(missing_ok=True)


# ── Workflow → versions create jump with pre-fill ────────────────────


@pytest.fixture()
def seeded_brief_for_create_jump():
    """Seed a single brief so the workflow's create-dossier step
    becomes available and the dossier create form has a brief_id to
    pre-fill.

    Cleanup removes the seeded brief and its backups.
    """
    from scoutfootball.api import _brief_store

    brief_id = f"e2e-wfjump-brief-{uuid.uuid4().hex[:8]}"
    store = _brief_store()
    store.save(
        brief_id,
        _valid_brief_payload(brief_id, title="E2E workflow jump brief"),
        expected_revision=0,
    )

    yield {"brief_id": brief_id}

    try:
        store.delete(brief_id, expected_revision=None)
    except Exception:
        pass
    record_path = store.root / f"{brief_id}.json"
    record_path.unlink(missing_ok=True)
    backup_dir = getattr(store, "backup_root", None)
    if backup_dir:
        for f in backup_dir.glob(f"{brief_id}.*.json"):
            f.unlink(missing_ok=True)


def test_workflow_create_dossier_jump_prefills_brief_id(
    page, live_server_url: str, seeded_brief_for_create_jump
) -> None:
    """Clicking the workflow's create-dossier step must jump to the
    versions view and auto-open the create dialog with the brief_id
    pre-filled.

    Catches regressions where:
    - the create-dossier step uses a plain jump instead of staging
      pendingCreate context
    - the pre-fill value is lost between the workflow view and the
      versions view
    - the create dialog does not auto-open on arrival
    - the brief_id <select> does not honour the pre-fill value
    """
    brief_id = seeded_brief_for_create_jump["brief_id"]

    open_loaded_app(page, live_server_url)
    page.locator(".nav-stack .nav-action[data-view='workflow']").click()
    page.locator("#view-workflow").wait_for(state="visible", timeout=10_000)

    # Wait for the workflow fetches to settle and the create-dossier step
    # to appear (it requires briefs > 0 and dossiers == 0).
    create_step_btn = None
    for _ in range(25):
        btn = page.locator(
            "#wf-next-list button[data-wf-create='dossier']"
        )
        if btn.count() > 0:
            create_step_btn = btn.first
            break
        page.wait_for_timeout(200)
    assert create_step_btn is not None, (
        "create-dossier step did not appear in workflow next-list "
        "(requires a seeded brief and no existing dossiers)"
    )

    # The pre-fill payload must be carried via the data-wf-prefill attr.
    prefill_attr = create_step_btn.get_attribute("data-wf-prefill") or "{}"
    import json as _json

    try:
        prefill = _json.loads(prefill_attr)
    except Exception:
        prefill = {}
    assert prefill.get("brief_id") == brief_id, (
        f"Expected prefill brief_id={brief_id!r}, got {prefill!r}"
    )

    # Click the step → must jump to versions view and auto-open dialog.
    create_step_btn.click()
    page.locator("#view-versions").wait_for(state="visible", timeout=10_000)
    page.locator("#ver-create-dialog").wait_for(
        state="visible", timeout=5_000
    )

    # The dossier form must be active (type selector synced).
    assert page.locator("#ver-type-select").input_value() == "dossier"

    # The brief_id <select> must be pre-filled with the seeded brief.
    brief_select = page.locator("#ver-create-input-brief_id")
    assert brief_select.input_value() == brief_id, (
        f"Expected brief_id select to be pre-filled with {brief_id!r}, "
        f"got {brief_select.input_value()!r}"
    )

    # Close the dialog and clean up any dossier that might have been
    # created by an earlier partial run.
    page.locator("#ver-create-cancel").click()
    page.wait_for_timeout(200)
    from scoutfootball.api import _dossier_store

    store = _dossier_store()
    for pattern in ("dossier-2026*.json", "dossier-2025*.json"):
        for f in store.root.glob(pattern):
            cid = f.stem
            try:
                store.delete(cid, expected_revision=None)
            except Exception:
                pass
            f.unlink(missing_ok=True)
            backup_dir = getattr(store, "backup_root", None)
            if backup_dir:
                for bf in backup_dir.glob(f"{cid}.*.json"):
                    bf.unlink(missing_ok=True)


# ── Versions view: edit-button visibility ────────────────────────────


def test_versions_view_edit_button_visibility(
    page, live_server_url: str
) -> None:
    """The edit button must be hidden for brief/briefing and visible for
    dossier/review only when a specific record is selected.

    Catches regressions where:
    - the edit button is shown for brief/briefing (which have no PUT
      endpoint and must not be editable here)
    - the edit button is shown for dossier/review when no record is
      selected (clicking it would have no target)
    - the edit button fails to appear after a record is selected
    - the edit-dialog open/close wiring is missing or wrong
    """
    open_loaded_app(page, live_server_url)
    page.locator(".nav-stack .nav-action[data-view='versions']").click()
    page.locator("#view-versions").wait_for(state="visible", timeout=10_000)

    type_select = page.locator("#ver-type-select")
    type_select.wait_for(state="visible", timeout=10_000)
    edit_btn = page.locator("#ver-edit")

    # brief / briefing: not editable here → button hidden.
    type_select.select_option("brief")
    page.wait_for_timeout(150)
    assert edit_btn.get_attribute("hidden") is not None, (
        "Edit button should be hidden for brief type"
    )

    type_select.select_option("briefing")
    page.wait_for_timeout(150)
    assert edit_btn.get_attribute("hidden") is not None, (
        "Edit button should be hidden for briefing type"
    )

    # dossier: editable, but button still hidden until a record is picked.
    type_select.select_option("dossier")
    page.wait_for_timeout(200)
    assert edit_btn.get_attribute("hidden") is not None, (
        "Edit button should be hidden for dossier when no record is selected"
    )

    # If a dossier record exists, selecting it must reveal the edit button.
    # We seed one through the store so the test is independent of the
    # maintainer's actual store contents.
    from scoutfootball.api import _dossier_store

    store = _dossier_store()
    dossier_id = f"e2e-edit-vis-{uuid.uuid4().hex[:8]}"
    store.save(
        dossier_id,
        _valid_dossier_payload(dossier_id, title="E2E edit visibility"),
        expected_revision=0,
    )
    try:
        # Refresh the versions view so the new dossier appears in the
        # record selector.
        page.locator("#ver-refresh").click()
        page.wait_for_timeout(300)

        record_select = page.locator("#ver-record-select")
        # Wait until the option is present, then select it.
        for _ in range(20):
            opts = record_select.locator("option").evaluate_all(
                "opts => opts.map(o => o.value)"
            )
            if dossier_id in opts:
                break
            page.wait_for_timeout(200)
        record_select.select_option(dossier_id)
        page.wait_for_timeout(200)

        assert edit_btn.get_attribute("hidden") is None, (
            "Edit button should be visible for dossier after a record is selected"
        )

        # review: same rule — visible only after a record is selected.
        type_select.select_option("review")
        page.wait_for_timeout(200)
        assert edit_btn.get_attribute("hidden") is not None, (
            "Edit button should be hidden for review when no record is selected"
        )
    finally:
        # Cleanup.
        try:
            store.delete(dossier_id, expected_revision=None)
        except Exception:
            pass
        record_path = store.root / f"{dossier_id}.json"
        record_path.unlink(missing_ok=True)
        backup_dir = getattr(store, "backup_root", None)
        if backup_dir:
            for f in backup_dir.glob(f"{dossier_id}.*.json"):
                f.unlink(missing_ok=True)


# ── Versions view: edit dossier round-trip ───────────────────────────


@pytest.fixture()
def seeded_dossier_for_edit():
    """Seed a single draft dossier for the edit round-trip tests.

    Yields ``dossier_id`` so the test can drive the browser-side edit
    flow against a known on-disk record.  Cleanup removes the record
    and any backups created during the test.
    """
    from scoutfootball.api import _dossier_store

    dossier_id = f"e2e-edit-dos-{uuid.uuid4().hex[:8]}"
    store = _dossier_store()
    store.save(
        dossier_id,
        _valid_dossier_payload(dossier_id, title="E2E edit v1"),
        expected_revision=0,
    )

    yield dossier_id

    try:
        store.delete(dossier_id, expected_revision=None)
    except Exception:
        pass
    record_path = store.root / f"{dossier_id}.json"
    record_path.unlink(missing_ok=True)
    backup_dir = getattr(store, "backup_root", None)
    if backup_dir:
        for f in backup_dir.glob(f"{dossier_id}.*.json"):
            f.unlink(missing_ok=True)


def test_versions_view_edit_dossier_round_trip(
    page, live_server_url: str, seeded_dossier_for_edit
) -> None:
    """End-to-end edit flow for a decision dossier via the browser.

    Drives the full UI flow:
    1. Open the versions view, switch to dossier type, select the record.
    2. Click the edit button → dialog opens with the form pre-filled
       with the current record's values.
    3. Change the title and submit.
    4. Verify the dialog closes, the new revision is server_revision=2,
       a backup of rev 1 exists, and the new title is persisted.

    Catches regressions where:
    - the edit dialog does not open from the toolbar button
    - the form fields are not pre-filled with the current record values
    - the PUT request body shape is wrong (missing expected_revision)
    - the success path does not refresh the versions view state
    - the backup is not created on edit
    """
    dossier_id = seeded_dossier_for_edit

    open_loaded_app(page, live_server_url)
    page.locator(".nav-stack .nav-action[data-view='versions']").click()
    page.locator("#view-versions").wait_for(state="visible", timeout=10_000)

    # Capture all network requests to PUT endpoints for debugging.
    put_requests: list[dict] = []
    page.on("request", lambda req: (
        put_requests.append({
            "url": req.url,
            "method": req.method,
        }) if req.method == "PUT" else None
    ))
    page.on("response", lambda resp: (
        put_requests.append({
            "url": resp.url,
            "status": resp.status,
            "method": resp.request.method,
        }) if resp.request.method == "PUT" else None
    ))

    type_select = page.locator("#ver-type-select")
    type_select.wait_for(state="visible", timeout=10_000)
    type_select.select_option("dossier")
    page.wait_for_timeout(200)

    # Refresh + select the seeded dossier.
    page.locator("#ver-refresh").click()
    page.wait_for_timeout(300)

    record_select = page.locator("#ver-record-select")
    for _ in range(20):
        opts = record_select.locator("option").evaluate_all(
            "opts => opts.map(o => o.value)"
        )
        if dossier_id in opts:
            break
        page.wait_for_timeout(200)
    record_select.select_option(dossier_id)
    page.wait_for_timeout(200)

    # Open the edit dialog.
    page.locator("#ver-edit").click()
    page.locator("#ver-edit-dialog").wait_for(state="visible", timeout=5_000)

    # The form must be pre-filled with the current record's title.
    title_input = page.locator("#ver-edit-input-title")
    assert title_input.input_value() == "E2E edit v1", (
        f"Expected title pre-fill 'E2E edit v1', got {title_input.input_value()!r}"
    )

    # The status select must be present and show 'draft'.
    status_select = page.locator("#ver-edit-input-status")
    assert status_select.input_value() == "draft", (
        f"Expected status 'draft', got {status_select.input_value()!r}"
    )

    # Change the title and submit.
    title_input.fill("E2E edit v2 (edited)")
    page.locator("#ver-edit-submit").click()

    # The dialog must close on success. Poll for up to 5s.
    for _ in range(25):
        is_open = page.evaluate(
            "() => !!document.getElementById('ver-edit-dialog').open"
        )
        if not is_open:
            break
        page.wait_for_timeout(200)
    assert not is_open, (
        f"Edit dialog did not close after successful submit. "
        f"PUT requests captured: {put_requests}"
    )

    # Verify the new revision via the API.
    result = page.evaluate(
        """async ({baseUrl, dossierId}) => {
            const r = await fetch(
                baseUrl + '/recruitment/dossiers/' + encodeURIComponent(dossierId),
                { cache: 'no-store' }
            );
            const d = await r.json();
            const backupsResp = await fetch(
                baseUrl + '/recruitment/dossiers/' + encodeURIComponent(dossierId) + '/backups',
                { cache: 'no-store' }
            );
            const backupsData = await backupsResp.json();
            return {
                serverRevision: d.record?.server_revision,
                title: d.record?.dossier?.title,
                backupCount: backupsData.count,
                httpStatus: r.status,
                rawDetail: d.detail,
            };
        }""",
        {"baseUrl": live_server_url, "dossierId": dossier_id},
    )

    assert result["serverRevision"] == 2, (
        f"Expected server_revision=2 after edit, got {result['serverRevision']!r}. "
        f"httpStatus={result.get('httpStatus')!r}, "
        f"rawDetail={result.get('rawDetail')!r}. "
        f"PUT requests captured: {put_requests}"
    )
    assert result["title"] == "E2E edit v2 (edited)", (
        f"Expected edited title to persist, got {result['title']!r}"
    )
    assert result["backupCount"] == 1, (
        f"Expected 1 backup after edit, got {result['backupCount']}"
    )


def test_versions_view_edit_dossier_status_transition_to_decided(
    page, live_server_url: str, seeded_dossier_for_edit
) -> None:
    """Edit-dialog status transition: draft → decided (with decision).

    Drives the full UI flow:
    1. Open the edit dialog on a draft dossier.
    2. Change status to 'decided' and decision to 'proceed'.
    3. Submit → must succeed (decision is consistent with status).
    4. Verify the new revision reflects the decided/proceed state.

    Catches regressions where:
    - the client-side decision-consistency check rejects a valid
      draft → decided + proceed transition
    - the server-side validation rejects the same transition
    - the form fails to serialize the status / decision selects
    """
    dossier_id = seeded_dossier_for_edit

    open_loaded_app(page, live_server_url)
    page.locator(".nav-stack .nav-action[data-view='versions']").click()
    page.locator("#view-versions").wait_for(state="visible", timeout=10_000)

    type_select = page.locator("#ver-type-select")
    type_select.wait_for(state="visible", timeout=10_000)
    type_select.select_option("dossier")
    page.wait_for_timeout(200)

    page.locator("#ver-refresh").click()
    page.wait_for_timeout(300)

    record_select = page.locator("#ver-record-select")
    for _ in range(20):
        opts = record_select.locator("option").evaluate_all(
            "opts => opts.map(o => o.value)"
        )
        if dossier_id in opts:
            break
        page.wait_for_timeout(200)
    record_select.select_option(dossier_id)
    page.wait_for_timeout(200)

    page.locator("#ver-edit").click()
    page.locator("#ver-edit-dialog").wait_for(state="visible", timeout=5_000)

    # Move status to 'decided' and decision to 'proceed'.
    page.locator("#ver-edit-input-status").select_option("decided")
    page.locator("#ver-edit-input-decision").select_option("proceed")
    page.locator("#ver-edit-submit").click()

    for _ in range(25):
        is_open = page.evaluate(
            "() => !!document.getElementById('ver-edit-dialog').open"
        )
        if not is_open:
            break
        page.wait_for_timeout(200)
    assert not is_open, (
        "Edit dialog did not close after valid status transition to decided"
    )

    result = page.evaluate(
        """async ({baseUrl, dossierId}) => {
            const r = await fetch(
                baseUrl + '/recruitment/dossiers/' + encodeURIComponent(dossierId)
            );
            const d = await r.json();
            return {
                serverRevision: d.record?.server_revision,
                status: d.record?.dossier?.status,
                decision: d.record?.dossier?.decision,
            };
        }""",
        {"baseUrl": live_server_url, "dossierId": dossier_id},
    )
    assert result["serverRevision"] == 2, (
        f"Expected revision 2 after status transition, got {result['serverRevision']}"
    )
    assert result["status"] == "decided", (
        f"Expected status='decided', got {result['status']!r}"
    )
    assert result["decision"] == "proceed", (
        f"Expected decision='proceed', got {result['decision']!r}"
    )


def test_versions_view_edit_dossier_decided_without_decision_blocks(
    page, live_server_url: str, seeded_dossier_for_edit
) -> None:
    """Client-side guard: status='decided' without a decision must keep
    the dialog open and surface the validation error.

    Catches regressions where the client-side decision-consistency check
    is missing or bypassed, letting an invalid payload reach the server.
    """
    dossier_id = seeded_dossier_for_edit

    open_loaded_app(page, live_server_url)
    page.locator(".nav-stack .nav-action[data-view='versions']").click()
    page.locator("#view-versions").wait_for(state="visible", timeout=10_000)

    type_select = page.locator("#ver-type-select")
    type_select.wait_for(state="visible", timeout=10_000)
    type_select.select_option("dossier")
    page.wait_for_timeout(200)

    page.locator("#ver-refresh").click()
    page.wait_for_timeout(300)

    record_select = page.locator("#ver-record-select")
    for _ in range(20):
        opts = record_select.locator("option").evaluate_all(
            "opts => opts.map(o => o.value)"
        )
        if dossier_id in opts:
            break
        page.wait_for_timeout(200)
    record_select.select_option(dossier_id)
    page.wait_for_timeout(200)

    page.locator("#ver-edit").click()
    page.locator("#ver-edit-dialog").wait_for(state="visible", timeout=5_000)

    # Move status to 'decided' but leave decision empty.
    page.locator("#ver-edit-input-status").select_option("decided")
    page.locator("#ver-edit-input-decision").select_option("")
    page.locator("#ver-edit-submit").click()

    # An alert() should fire; we need to dismiss it before reading state.
    page.on("dialog", lambda d: d.dismiss())
    page.wait_for_timeout(400)

    # The dialog must still be open (validation blocked the submit).
    is_open = page.evaluate(
        "() => !!document.getElementById('ver-edit-dialog').open"
    )
    assert is_open, (
        "Edit dialog should still be open after invalid "
        "status='decided' without decision"
    )

    # Confirm the server-side revision is unchanged.
    result = page.evaluate(
        """async ({baseUrl, dossierId}) => {
            const r = await fetch(
                baseUrl + '/recruitment/dossiers/' + encodeURIComponent(dossierId)
            );
            const d = await r.json();
            return {
                serverRevision: d.record?.server_revision,
                status: d.record?.dossier?.status,
            };
        }""",
        {"baseUrl": live_server_url, "dossierId": dossier_id},
    )
    assert result["serverRevision"] == 1, (
        f"Revision should still be 1 (no commit); got {result['serverRevision']}"
    )
    assert result["status"] == "draft", (
        f"Status should still be 'draft'; got {result['status']!r}"
    )


# ── Versions view: edit dossier conflict recovery ────────────────────


def test_versions_view_edit_dossier_conflict_recovery(
    page, live_server_url: str, seeded_dossier_for_edit
) -> None:
    """Edit-dialog conflict recovery: a stale expected_revision must
    surface a 409 conflict inline and keep the dialog open so the
    maintainer can refresh without losing their input.

    Drives the flow:
    1. Open the edit dialog (loads revision 1).
    2. Out-of-band, push a second revision through the store so the
       on-disk revision becomes 2 while the dialog still thinks 1.
    3. Submit the edit — the server must reject with 409
       ``dossier_revision_conflict``.
    4. The dialog must stay open and the conflict note must be visible.
    5. Closing and re-opening the dialog must load the current revision.
    """
    dossier_id = seeded_dossier_for_edit
    from scoutfootball.api import _dossier_store

    open_loaded_app(page, live_server_url)
    page.locator(".nav-stack .nav-action[data-view='versions']").click()
    page.locator("#view-versions").wait_for(state="visible", timeout=10_000)

    type_select = page.locator("#ver-type-select")
    type_select.wait_for(state="visible", timeout=10_000)
    type_select.select_option("dossier")
    page.wait_for_timeout(200)

    page.locator("#ver-refresh").click()
    page.wait_for_timeout(300)

    record_select = page.locator("#ver-record-select")
    for _ in range(20):
        opts = record_select.locator("option").evaluate_all(
            "opts => opts.map(o => o.value)"
        )
        if dossier_id in opts:
            break
        page.wait_for_timeout(200)
    record_select.select_option(dossier_id)
    page.wait_for_timeout(200)

    # Open the edit dialog — captures expected_revision=1.
    page.locator("#ver-edit").click()
    page.locator("#ver-edit-dialog").wait_for(state="visible", timeout=5_000)

    # Out-of-band: push rev 2 through the store so the dialog's
    # expected_revision=1 is now stale.
    store = _dossier_store()
    store.save(
        dossier_id,
        _valid_dossier_payload(dossier_id, title="Out-of-band v2"),
        expected_revision=1,
    )

    # Fill in a new title and submit. The server must reject with 409.
    page.locator("#ver-edit-input-title").fill("Stale edit attempt")
    # Dismiss any alert() that might fire from a non-conflict path.
    page.on("dialog", lambda d: d.dismiss())
    page.locator("#ver-edit-submit").click()
    page.wait_for_timeout(800)

    # The dialog must still be open and the conflict note visible.
    is_open = page.evaluate(
        "() => !!document.getElementById('ver-edit-dialog').open"
    )
    assert is_open, (
        "Edit dialog should stay open after a 409 revision conflict"
    )
    conflict_el = page.locator("#ver-edit-conflict")
    assert conflict_el.get_attribute("hidden") is None, (
        "Conflict note should be visible after a 409 response"
    )
    conflict_text = conflict_el.inner_text()
    assert conflict_text.strip() != "", (
        "Conflict note text should not be empty"
    )

    # Close + re-open the dialog. The new dialog must load the current
    # (rev 2) record so a fresh edit can succeed.
    page.locator("#ver-edit-cancel").click()
    page.wait_for_timeout(200)
    page.locator("#ver-edit").click()
    page.locator("#ver-edit-dialog").wait_for(state="visible", timeout=5_000)

    # The title input must now reflect the out-of-band rev 2 title.
    title_input = page.locator("#ver-edit-input-title")
    assert title_input.input_value() == "Out-of-band v2", (
        f"Expected re-opened dialog to load rev 2 title 'Out-of-band v2', "
        f"got {title_input.input_value()!r}"
    )

    # Conflict note must be cleared on re-open.
    assert page.locator("#ver-edit-conflict").get_attribute("hidden") is not None, (
        "Conflict note should be hidden after re-opening the edit dialog"
    )


# ── Versions view: edit review round-trip ────────────────────────────


@pytest.fixture()
def seeded_review_for_edit():
    """Seed a single draft review for the edit round-trip tests.

    Yields ``review_id``; cleanup removes the record and any backups.
    """
    from scoutfootball.api import _review_store

    review_id = f"e2e-edit-rev-{uuid.uuid4().hex[:8]}"
    store = _review_store()
    store.save(
        review_id,
        _valid_review_payload(review_id, title="E2E edit review v1"),
        expected_revision=0,
    )

    yield review_id

    try:
        store.delete(review_id, expected_revision=None)
    except Exception:
        pass
    record_path = store.root / f"{review_id}.json"
    record_path.unlink(missing_ok=True)
    backup_dir = getattr(store, "backup_root", None)
    if backup_dir:
        for f in backup_dir.glob(f"{review_id}.*.json"):
            f.unlink(missing_ok=True)


def test_versions_view_edit_review_round_trip(
    page, live_server_url: str, seeded_review_for_edit
) -> None:
    """End-to-end edit flow for a post-match review via the browser.

    Same shape as the dossier edit test but exercises the
    ``/opposition/reviews/{id}`` PUT endpoint and the review form fields
    (which include final_score_home / final_score_away as number inputs).
    """
    review_id = seeded_review_for_edit

    open_loaded_app(page, live_server_url)
    page.locator(".nav-stack .nav-action[data-view='versions']").click()
    page.locator("#view-versions").wait_for(state="visible", timeout=10_000)

    type_select = page.locator("#ver-type-select")
    type_select.wait_for(state="visible", timeout=10_000)
    type_select.select_option("review")
    page.wait_for_timeout(200)

    page.locator("#ver-refresh").click()
    page.wait_for_timeout(300)

    record_select = page.locator("#ver-record-select")
    for _ in range(20):
        opts = record_select.locator("option").evaluate_all(
            "opts => opts.map(o => o.value)"
        )
        if review_id in opts:
            break
        page.wait_for_timeout(200)
    record_select.select_option(review_id)
    page.wait_for_timeout(200)

    page.locator("#ver-edit").click()
    page.locator("#ver-edit-dialog").wait_for(state="visible", timeout=5_000)

    # Form must be pre-filled with the current review values.
    title_input = page.locator("#ver-edit-input-title")
    assert title_input.input_value() == "E2E edit review v1", (
        f"Expected title pre-fill, got {title_input.input_value()!r}"
    )
    home_score_input = page.locator("#ver-edit-input-final_score_home")
    assert home_score_input.input_value() == "2", (
        f"Expected final_score_home=2, got {home_score_input.input_value()!r}"
    )

    # Edit title + final_score_home, then submit.
    title_input.fill("E2E edit review v2 (edited)")
    home_score_input.fill("3")
    page.locator("#ver-edit-submit").click()

    for _ in range(25):
        is_open = page.evaluate(
            "() => !!document.getElementById('ver-edit-dialog').open"
        )
        if not is_open:
            break
        page.wait_for_timeout(200)
    assert not is_open, "Edit dialog did not close after successful submit"

    result = page.evaluate(
        """async ({baseUrl, reviewId}) => {
            const r = await fetch(
                baseUrl + '/opposition/reviews/' + encodeURIComponent(reviewId)
            );
            const d = await r.json();
            return {
                serverRevision: d.record?.server_revision,
                title: d.record?.review?.title,
                finalScoreHome: d.record?.review?.final_score_home,
            };
        }""",
        {"baseUrl": live_server_url, "reviewId": review_id},
    )
    assert result["serverRevision"] == 2, (
        f"Expected server_revision=2 after edit, got {result['serverRevision']}"
    )
    assert result["title"] == "E2E edit review v2 (edited)", (
        f"Expected edited title to persist, got {result['title']!r}"
    )
    assert result["finalScoreHome"] == 3, (
        f"Expected final_score_home=3 after edit, got {result['finalScoreHome']!r}"
    )


def test_versions_view_edit_review_status_transition_to_finalized(
    page, live_server_url: str, seeded_review_for_edit
) -> None:
    """Edit-dialog status transition: draft → finalized (with decision).

    Review uses ``finalized`` as the decision-required status and the
    review-specific decision vocabulary (confirmed / falsified / partial
    / inconclusive). This test catches regressions where the client-side
    check uses the dossier vocabulary or the wrong decision-required
    status.
    """
    review_id = seeded_review_for_edit

    open_loaded_app(page, live_server_url)
    page.locator(".nav-stack .nav-action[data-view='versions']").click()
    page.locator("#view-versions").wait_for(state="visible", timeout=10_000)

    type_select = page.locator("#ver-type-select")
    type_select.wait_for(state="visible", timeout=10_000)
    type_select.select_option("review")
    page.wait_for_timeout(200)

    page.locator("#ver-refresh").click()
    page.wait_for_timeout(300)

    record_select = page.locator("#ver-record-select")
    for _ in range(20):
        opts = record_select.locator("option").evaluate_all(
            "opts => opts.map(o => o.value)"
        )
        if review_id in opts:
            break
        page.wait_for_timeout(200)
    record_select.select_option(review_id)
    page.wait_for_timeout(200)

    page.locator("#ver-edit").click()
    page.locator("#ver-edit-dialog").wait_for(state="visible", timeout=5_000)

    page.locator("#ver-edit-input-status").select_option("finalized")
    page.locator("#ver-edit-input-decision").select_option("confirmed")
    page.locator("#ver-edit-submit").click()

    for _ in range(25):
        is_open = page.evaluate(
            "() => !!document.getElementById('ver-edit-dialog').open"
        )
        if not is_open:
            break
        page.wait_for_timeout(200)
    assert not is_open, (
        "Edit dialog did not close after valid review status transition"
    )

    result = page.evaluate(
        """async ({baseUrl, reviewId}) => {
            const r = await fetch(
                baseUrl + '/opposition/reviews/' + encodeURIComponent(reviewId)
            );
            const d = await r.json();
            return {
                serverRevision: d.record?.server_revision,
                status: d.record?.review?.status,
                decision: d.record?.review?.decision,
            };
        }""",
        {"baseUrl": live_server_url, "reviewId": review_id},
    )
    assert result["serverRevision"] == 2, (
        f"Expected revision 2 after status transition, got {result['serverRevision']}"
    )
    assert result["status"] == "finalized", (
        f"Expected status='finalized', got {result['status']!r}"
    )
    assert result["decision"] == "confirmed", (
        f"Expected decision='confirmed', got {result['decision']!r}"
    )
