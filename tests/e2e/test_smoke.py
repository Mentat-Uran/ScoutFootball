"""E2E smoke test: verify the live server + browser + page fixture chain works.

This is the smallest test that exercises every layer of the E2E stack:

- ``live_server_url`` starts a real uvicorn server on a free port
- ``browser`` launches headless Chrome via the system-installed channel
- ``page`` gives a fresh browser context for the test

If this test fails, every other E2E test in ``tests/e2e/`` is suspect, so
we keep it deliberately small and explicit about what each assertion is
checking.

Run with::

    uv run pytest tests/e2e/test_smoke.py -m e2e -v
"""

from __future__ import annotations

import urllib.request

import pytest

pytestmark = pytest.mark.e2e

# The 22 navigation buttons rendered in frontend/index.html. We hard-code the
# list (instead of scraping) so a missing/renamed button fails loudly here
# rather than silently in a downstream workflow test.
EXPECTED_NAV_VIEWS = [
    "overview",
    "players",
    "compare",
    "value",
    "matches",
    "teams",
    "league",
    "scouting",
    "actions",
    "reports",
    "tactical",
    "wc_schedule",
    "wc_squads",
    "wc_compare",
    "wc_probability",
    "wc_knockout",
    "wc_tournament",
    "license",
    "data",
    "calibration",
    "backtest",
    "help",
]

INITIAL_LOAD_TIMEOUT_MS = 30_000


def open_loaded_app(page, live_server_url: str):
    """Navigate through the real initial load without relying on network-idle.

    The SPA deliberately keeps a periodic health poll alive, so Playwright's
    ``networkidle`` is not a stable definition of readiness. The application
    instead exposes a state only after its initial local API/static payloads
    and World Cup bootstrap have settled.
    """
    response = page.goto(
        live_server_url,
        wait_until="domcontentloaded",
        timeout=INITIAL_LOAD_TIMEOUT_MS,
    )
    page.locator("html[data-scoutfootball-initial-load='ready']").wait_for(
        state="attached",
        timeout=INITIAL_LOAD_TIMEOUT_MS,
    )
    return response


def test_health_endpoint_reachable(live_server_url: str) -> None:
    """Sanity check: the FastAPI server is up and /health returns 200."""
    with urllib.request.urlopen(f"{live_server_url}/health", timeout=2) as resp:
        assert resp.status == 200


def test_index_page_loads_with_all_nav_buttons(page, live_server_url: str) -> None:
    """The SPA shell loads and all 22 nav-action buttons are present.

    This catches regressions where:
    - frontend static files are not mounted on the FastAPI app
    - index.html is missing buttons (e.g. a view was removed without cleanup)
    - the page failed to load entirely (blank screen)

    The selector ``.nav-stack .nav-action[...]`` deliberately excludes the
    brand-lockup button at the top of the side nav, which also carries the
    ``nav-action`` class and ``data-view='overview'`` but is not part of
    the 22-button nav stack.
    """
    response = open_loaded_app(page, live_server_url)
    assert response is not None
    assert response.status == 200

    # Body must be present (rules out a totally blank page).
    body = page.locator("body")
    expect_visible(body)

    # Every expected nav-action button must be present in the DOM.
    for view in EXPECTED_NAV_VIEWS:
        button = page.locator(f".nav-stack .nav-action[data-view='{view}']")
        expect_visible(button)

    # The brand lockup at the top should also navigate to overview.
    brand = page.locator(".brand-lockup.nav-action[data-view='overview']")
    expect_visible(brand)


def test_initial_view_is_overview(page, live_server_url: str) -> None:
    """On first load, the overview nav button is marked active."""
    open_loaded_app(page, live_server_url)

    active_button = page.locator(".nav-stack .nav-action.active[data-view='overview']")
    expect_visible(active_button)
    assert active_button.get_attribute("aria-current") == "page"


def test_switching_to_players_view_updates_active_state(page, live_server_url: str) -> None:
    """Clicking the players nav button toggles the active state correctly.

    This exercises the setView() click handler wired up in app.js and
    catches regressions in event binding (e.g. nav buttons rendered after
    the listener was attached).
    """
    open_loaded_app(page, live_server_url)

    players_button = page.locator(".nav-stack .nav-action[data-view='players']")
    expect_visible(players_button)
    players_button.click()

    # After click, players button must be active and have aria-current.
    expect_visible(page.locator(".nav-stack .nav-action.active[data-view='players']"))
    assert (
        page.locator(".nav-stack .nav-action[data-view='players']").get_attribute("aria-current")
        == "page"
    )

    # Overview button must lose active state and aria-current.
    overview_button = page.locator(".nav-stack .nav-action[data-view='overview']")
    assert "active" not in (overview_button.get_attribute("class") or "")
    assert overview_button.get_attribute("aria-current") is None


def test_no_uncaught_console_errors_on_initial_load(page, live_server_url: str) -> None:
    """The initial page load should not emit console error messages.

    We collect console messages during navigation and assert none of them
    are errors. Warnings and info messages are tolerated — many come from
    browser extensions or benign deprecation notices and are not
    actionable for the maintainer.
    """
    errors: list[str] = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

    open_loaded_app(page, live_server_url)

    assert not errors, f"Console errors during initial load: {errors}"


def expect_visible(locator) -> None:
    """Assert a Playwright locator resolves to exactly one visible element.

    Wrapped in a helper so the failure message is readable and consistent
    across smoke tests.
    """
    expect_count = locator.count()
    assert expect_count == 1, f"Expected exactly 1 match for {locator}, found {expect_count}"
    assert locator.first.is_visible(), f"Expected visible: {locator}"
