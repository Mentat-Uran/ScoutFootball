"""Static analysis tests for scripts/demo.sh.

Verifies that the demo script uses same-origin FastAPI hosting (no separate
frontend server), the correct default port, and includes a smoke test.
"""

from pathlib import Path

DEMO_SH = Path(__file__).resolve().parents[2] / "scripts" / "demo.sh"


def _read_demo() -> str:
    return DEMO_SH.read_text(encoding="utf-8")


def test_demo_script_exists():
    assert DEMO_SH.exists(), f"demo.sh not found at {DEMO_SH}"


def test_uses_same_origin_fastapi_hosting():
    """The frontend must be served by FastAPI, not a separate http.server."""
    content = _read_demo()
    assert "scoutfootball serve" in content
    # The old pattern started a separate python3 -m http.server for the frontend.
    # This must not appear anywhere in the script.
    assert "http.server" not in content, (
        "demo.sh must not start a separate http.server — FastAPI serves the "
        "frontend via StaticFiles on the same origin"
    )


def test_no_old_port_references():
    """Ports 8600 and 8601 were the old split-origin ports; must not appear."""
    content = _read_demo()
    assert "8600" not in content, "demo.sh must not reference old API port 8600"
    assert "8601" not in content, "demo.sh must not reference old frontend port 8601"


def test_default_port_is_8000():
    """The default port must be 8000, matching `scoutfootball serve` default."""
    content = _read_demo()
    assert 'PORT="${SCOUTFOOTBALL_PORT:-8000}"' in content


def test_passes_host_and_port_to_serve():
    """The serve command must receive --host and --port explicitly."""
    content = _read_demo()
    assert "--host" in content
    assert "--port" in content
    assert 'scoutfootball serve --host "$HOST" --port "$PORT"' in content


def test_has_smoke_test_flag():
    """The --smoke flag must exist for quick health verification."""
    content = _read_demo()
    assert "--smoke" in content
    assert "SMOKE_ONLY" in content


def test_smoke_test_checks_health_endpoint():
    """The smoke test must verify /health responds."""
    content = _read_demo()
    assert "/health" in content


def test_smoke_test_checks_frontend_served():
    """The smoke test must verify the frontend (/) returns HTTP 200."""
    content = _read_demo()
    assert "HTTP 200" in content or "200" in content


def test_same_origin_documented():
    """The script must document that API and frontend are same-origin."""
    content = _read_demo()
    assert "same-origin" in content.lower() or "same origin" in content.lower()
