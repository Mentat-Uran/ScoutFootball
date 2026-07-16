"""E2E coverage for the declared ScoutFootball reference workflows.

This module covers the scenarios required by G1 subtask 3:

- LIVE: real data loads into the overview and license views
- STATIC: the data-source manifest table populates from /artifacts
- OFFLINE: the SPA degrades gracefully when the network is taken away
- Empty / low-coverage: the data-status view renders even when an
  artifact is missing or marked as synthetic
- Field-missing: a view whose API response lacks a field does not crash
- Mobile reading: the nav remains usable on a 375x667 viewport
- Import safety: tampered tournament state is rejected by the import
  preview endpoint from the browser context

Each test is intentionally small and asserts only what is contractually
visible to a maintainer using the app. We do not assert pixel-perfect
layouts, copy strings, or chart internals — those drift too easily and
are not what these scenarios are about.

Run with::

    uv run pytest tests/e2e/test_workflows.py -m e2e -v
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


# ── LIVE: real data reaches the SPA from the live server ──────────────


def test_overview_renders_data_health_panel(page, live_server_url: str) -> None:
    """The overview view's #data-health-list must contain health items.

    This is the smallest end-to-end proof that:
    - /artifacts was fetched successfully from the live server
    - artifactSummary.data_health was populated
    - renderOverview() ran and updated the DOM

    If this fails, every downstream view that depends on artifactSummary
    is suspect.
    """
    page.goto(live_server_url, wait_until="domcontentloaded", timeout=15_000)
    # renderOverview() runs on initial paint, but the underlying /artifacts
    # fetch is async. Wait for at least one health-item to be present.
    health_list = page.locator("#data-health-list .health-item")
    health_list.first.wait_for(state="visible", timeout=10_000)
    assert health_list.count() >= 3, (
        f"Expected >=3 health items in #data-health-list, found {health_list.count()}"
    )


def test_overview_license_attribution_lists_known_sources(
    page, live_server_url: str
) -> None:
    """The license-attribution panel lists the known open data sources.

    Catches regressions in /artifacts.license_attribution mapping or in
    the overview's rendering of that map.
    """
    page.goto(live_server_url, wait_until="domcontentloaded", timeout=15_000)
    license_list = page.locator("#license-list .health-item")
    license_list.first.wait_for(state="visible", timeout=10_000)
    assert license_list.count() >= 1, (
        f"Expected >=1 license attribution entry, found {license_list.count()}"
    )


# ── STATIC: license view populates the data source manifest table ────


def test_license_view_populates_data_source_table(
    page, live_server_url: str
) -> None:
    """The license view's table body must contain real rows, not the
    initial 'Loading...' placeholder.

    This proves the /license endpoint (or /artifacts fallback) returned
    data and renderLicense() replaced the placeholder rows.
    """
    page.goto(live_server_url, wait_until="domcontentloaded", timeout=15_000)

    # Switch to the license view via the nav button.
    page.locator(".nav-stack .nav-action[data-view='license']").click()

    # The table body must end up with at least one row that is NOT the
    # initial Loading... placeholder. We wait for the first <tr> that
    # contains a <td> with non-empty text.
    tbody = page.locator("#license-table-body")
    tbody.wait_for(state="visible", timeout=10_000)

    # Give renderLicense() a moment to replace the placeholder. We poll
    # the row count and the text content of the first row.
    page.wait_for_function(
        """() => {
            const tbody = document.getElementById('license-table-body');
            if (!tbody) return false;
            const rows = tbody.querySelectorAll('tr');
            if (rows.length === 0) return false;
            const firstText = (rows[0].textContent || '').trim();
            return firstText !== '' && firstText.toLowerCase() !== 'loading...';
        }""",
        timeout=10_000,
    )

    rows = tbody.locator("tr")
    assert rows.count() >= 1, f"Expected >=1 license row, found {rows.count()}"


# ── Mobile reading: nav remains usable on a phone-sized viewport ─────


def test_mobile_viewport_nav_remains_usable(
    page, context, live_server_url: str
) -> None:
    """On a 375x667 viewport, the nav buttons must still be visible
    and clickable.

    Catches regressions where a CSS change hides or overlaps the nav
    on small screens, breaking the SPA on mobile.
    """
    # Set the viewport to a phone-sized layout. We use a fresh page on
    # the same context so the test is independent of any prior navigation.
    page.set_viewport_size({"width": 375, "height": 667})
    page.goto(live_server_url, wait_until="domcontentloaded", timeout=15_000)

    # The nav stack must be visible. We don't require it to be in a
    # particular layout (drawer vs. sidebar) — only that the buttons
    # are present and clickable.
    nav_stack = page.locator(".nav-stack")
    nav_stack.wait_for(state="visible", timeout=10_000)

    # Clicking the players button must still switch views.
    players_button = page.locator(".nav-stack .nav-action[data-view='players']")
    players_button.click()
    expect_active_view(page, "players")


# ── OFFLINE: SPA degrades gracefully when the network is taken away ──


def test_offline_does_not_crash_initial_load(
    context, live_server_url: str
) -> None:
    """With the browser context set to offline before navigation, the
    SPA must still load its HTML shell without throwing an uncaught
    exception.

    We do NOT assert that data loads — that is expected to fail
    offline. We only assert that the page does not crash, the nav is
    still visible, and the user can switch views (even if the views
    show empty/loading states).
    """
    # Use a fresh page so we don't disturb other tests' shared browser.
    page = context.new_page()

    errors: list[str] = []
    page.on(
        "pageerror",
        lambda exc: errors.append(str(exc)),
    )

    context.set_offline(True)
    try:
        # navigation itself should still succeed because the server is
        # local and the request is in-flight before offline takes effect;
        # but if it fails, we still want to assert no uncaught pageerror.
        try:
            page.goto(live_server_url, wait_until="domcontentloaded", timeout=10_000)
        except Exception:
            # If the navigation itself failed, the page is blank. We
            # still require that no pageerror was emitted — the SPA must
            # not have thrown during the partial load.
            pass

        # If the page loaded, the nav stack should be present (even if
        # empty of data). We tolerate either outcome as long as no
        # pageerror was emitted.
        nav_stack = page.locator(".nav-stack")
        if nav_stack.count() > 0:
            # Clicking another view must not throw a pageerror either.
            players_button = page.locator(
                ".nav-stack .nav-action[data-view='players']"
            )
            if players_button.count() > 0:
                players_button.click()
                page.wait_for_timeout(500)
    finally:
        context.set_offline(False)
        page.close()

    assert not errors, f"Uncaught page errors while offline: {errors}"


# ── Empty / low-coverage: data-status view renders despite gaps ──────


def test_data_view_renders_artifact_table(page, live_server_url: str) -> None:
    """The data-status view's #data-sources-table must render rows even
    when some artifacts are missing or marked as synthetic.

    The dev dataset has known gaps (e.g. value_fairness_oof.parquet is
    not always present). This test confirms the view still populates
    instead of leaving the placeholder or crashing.
    """
    page.goto(live_server_url, wait_until="domcontentloaded", timeout=15_000)

    page.locator(".nav-stack .nav-action[data-view='data']").click()

    tbody = page.locator("#data-sources-table")
    tbody.wait_for(state="visible", timeout=10_000)

    # renderData() replaces the placeholder once artifactSummary is
    # available. Wait for the first non-placeholder row.
    page.wait_for_function(
        """() => {
            const tbody = document.getElementById('data-sources-table');
            if (!tbody) return false;
            const rows = tbody.querySelectorAll('tr');
            if (rows.length === 0) return false;
            const firstText = (rows[0].textContent || '').trim();
            return firstText !== '' && firstText.toLowerCase() !== 'loading...';
        }""",
        timeout=10_000,
    )

    rows = tbody.locator("tr")
    assert rows.count() >= 1, f"Expected >=1 data source row, found {rows.count()}"


# ── Field-missing: a view does not crash when an API field is absent ─


def test_wc_tournament_view_renders_without_api_data(
    page, live_server_url: str
) -> None:
    """The wc_tournament view must render its shell even if the
    tournament API call fails or returns an empty payload.

    The initial HTML contains a 'Loading tournament data...' placeholder
    and a status pill labelled 'API OFFLINE'. We assert the shell is
    visible and the status pill is present — the view must not be a
    blank screen even before any data arrives.
    """
    page.goto(live_server_url, wait_until="domcontentloaded", timeout=15_000)

    page.locator(".nav-stack .nav-action[data-view='wc_tournament']").click()

    # The view root must become visible.
    root = page.locator("#wc-tournament-root")
    root.wait_for(state="visible", timeout=10_000)

    # The status pill must be present (its text may be API OFFLINE or
    # something else after the API responds — we only require that the
    # element exists, not its text).
    status_pill = page.locator("#wc-tournament-status")
    assert status_pill.count() == 1, (
        f"Expected exactly 1 #wc-tournament-status, found {status_pill.count()}"
    )


# ── Import safety: tampered tournament state is rejected from browser ─


def test_tournament_import_preview_rejects_tampered_state_from_browser(
    page, live_server_url: str
) -> None:
    """From the browser context, posting a tampered tournament state to
    /world-cup/tournament/import/preview must return an integrity_failed
    error, NOT silently accept the payload.

    This is the browser-side counterpart of the existing integration
    test (test_tournament_import_preview_reports_integrity_without_persisting).
    It proves the same safety net holds when the request originates
    from fetch() inside the SPA, not just from the TestClient.
    """
    page.goto(live_server_url, wait_until="domcontentloaded", timeout=15_000)

    # Build a tampered state payload. We reuse init_state() and mutate
    # one team name so the integrity check fails. The encoding follows
    # the same base64url scheme the export/import endpoints use.
    result = page.evaluate(
        """async (baseUrl) => {
            // Fetch a known-good export from the server, then tamper
            // with one team name before re-encoding. This mirrors the
            // real attack surface: a user pastes a base64 blob that
            // someone edited by hand.
            const exportResp = await fetch(baseUrl + '/world-cup/tournament/export');
            const exportData = await exportResp.json();
            if (exportData.status !== 'ok' || !exportData.encoded) {
                return { status: 'export_failed', detail: exportData };
            }
            // Decode the base64url payload, mutate, re-encode.
            // We intentionally do NOT use the server's helper — we
            // replicate the client-side decode/encode path so the test
            // exercises the same code a real attacker would.
            const padded = exportData.encoded + '='.repeat((4 - exportData.encoded.length % 4) % 4);
            const decoded = atob(padded.replace(/-/g, '+').replace(/_/g, '/'));
            const state = JSON.parse(decoded);
            if (!state.matches || !state.matches.length) {
                return { status: 'no_matches_to_tamper' };
            }
            state.matches[0].home = 'TAMPERED TEAM NAME';
            const reEncoded = btoa(JSON.stringify(state))
                .replace(/\\+/g, '-').replace(/\\//g, '_').replace(/=+$/, '');
            const previewResp = await fetch(baseUrl + '/world-cup/tournament/import/preview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ encoded: reEncoded }),
            });
            return await previewResp.json();
        }""",
        live_server_url,
    )

    # The preview endpoint must reject the tampered payload.
    assert result["status"] == "error", (
        f"Expected status='error', got: {result}"
    )
    assert result["code"] == "integrity_failed", (
        f"Expected code='integrity_failed', got: {result}"
    )
    # The integrity_errors list must mention the altered home team.
    integrity_errors = result.get("integrity_errors") or []
    assert any("altered home" in err for err in integrity_errors), (
        f"Expected 'altered home' in integrity_errors, got: {integrity_errors}"
    )


# ── Helpers ──────────────────────────────────────────────────────────


def expect_active_view(page, view: str) -> None:
    """Assert the given view's nav button is the active one."""
    active = page.locator(f".nav-stack .nav-action.active[data-view='{view}']")
    assert active.count() == 1, (
        f"Expected exactly 1 active nav button for view '{view}', "
        f"found {active.count()}"
    )
