"""Pytest fixtures for real-browser E2E tests.

This fixture layer starts a real FastAPI server on a free localhost port
(not FastAPI's in-process TestClient) so that Playwright drives the same
HTTP path a real browser would. The browser is launched against the
system-installed Chrome channel via Playwright's ``channel="chrome"``
option, which avoids downloading a separate Chromium binary and keeps
the dev-only footprint small.

E2E tests are marked with ``@pytest.mark.e2e`` and are NOT run by the
default pytest invocation. Run them explicitly:

    uv run pytest tests/e2e/ -m e2e

or

    uv run pytest -m e2e
"""

from __future__ import annotations

import socket
import threading
import time
import urllib.request
from collections.abc import Generator, Iterator

import pytest

# uvicorn is a runtime dependency of scoutfootball (serve command).
from uvicorn import Config, Server

from scoutfootball.api_server import create_app


def _free_port() -> int:
    """Reserve an ephemeral localhost port to avoid collisions in CI/dev."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_server(url: str, timeout_s: float = 120.0) -> None:
    """Poll /health until the server responds or timeout expires.

    The default 120s timeout accommodates the WC squad cache warmup that
    runs during FastAPI lifespan startup on the first request. In practice
    warmup completes in ~30-60s on a cold dev machine; we leave headroom
    so the fixture does not flake on slower hosts.
    """
    deadline = time.monotonic() + timeout_s
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=1.0) as resp:
                if resp.status == 200:
                    return
        except Exception as err:  # noqa: BLE001 - intentional broad wait
            last_err = err
            time.sleep(0.5)
    raise RuntimeError(
        f"FastAPI server at {url} did not become healthy within {timeout_s}s: {last_err}"
    )


@pytest.fixture(scope="session")
def live_server_url() -> Iterator[str]:
    """Start a real uvicorn server on a free port and yield its base URL.

    The server runs in a daemon thread; the fixture asks it to exit on
    teardown. Thread-scoped FastAPI state is acceptable for E2E because
    we never run E2E tests in parallel within one process.
    """
    port = _free_port()
    app = create_app()
    config = Config(
        app=app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = Server(config=config)

    thread = threading.Thread(target=server.run, daemon=True, name="e2e-uvicorn")
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    _wait_for_server(base_url)

    yield base_url

    server.should_exit = True
    thread.join(timeout=5.0)


@pytest.fixture(scope="session")
def browser() -> Generator:
    """Launch a headless Chrome browser using the system-installed channel.

    Requires Google Chrome to be installed on the host. We deliberately
    use ``channel="chrome"`` instead of downloading a Playwright-managed
    Chromium binary to keep the dev-tooling footprint small and to test
    against the browser the maintainer actually uses.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        try:
            yield browser
        finally:
            browser.close()


@pytest.fixture
def context(browser):
    """A fresh browser context per test (isolated localStorage, cookies)."""
    ctx = browser.new_context()
    try:
        yield ctx
    finally:
        ctx.close()


@pytest.fixture
def page(context):
    """A fresh page per test."""
    pg = context.new_page()
    try:
        yield pg
    finally:
        pg.close()
