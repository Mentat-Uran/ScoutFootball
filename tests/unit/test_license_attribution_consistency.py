"""Tests for license attribution key consistency across API, frontend, and desktop.

The API returns license_attribution as a dict keyed by source name
(e.g. "statsbomb", "clubelo"). The frontend (frontend/app.js) and desktop
(desktop/app.js) define LICENSE_SOURCES arrays with a "key" field that
must match the API dict keys so the dynamic attribution text can be
looked up correctly.

A mismatch (e.g. API uses "clubelo" but frontend uses "club_elo") causes
the frontend to silently fall back to the static attribution string,
losing the API-provided dynamic text.
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# The 6 sources registered in architecture.py planned_components.
# These are the canonical keys that must appear everywhere.
EXPECTED_KEYS = {"statsbomb", "fbref", "football_data", "understat", "clubelo", "transfermarkt"}

# Regex to extract the key from a LICENSE_SOURCES entry like:
#   { key: "clubelo", name: "Club Elo", ... }
_KEY_RE = re.compile(r'key:\s*"([^"]+)"')


def _extract_license_keys(js_path: Path) -> set[str]:
    """Extract LICENSE_SOURCES keys from a JS file."""
    content = js_path.read_text(encoding="utf-8")
    # Find the LICENSE_SOURCES array block
    start = content.find("const LICENSE_SOURCES = [")
    if start == -1:
        return set()
    end = content.find("];", start)
    if end == -1:
        return set()
    block = content[start:end]
    return set(_KEY_RE.findall(block))


def test_frontend_app_js_license_keys_match_api():
    """frontend/app.js LICENSE_SOURCES keys must match API license_attribution keys."""
    js_keys = _extract_license_keys(PROJECT_ROOT / "frontend" / "app.js")
    assert js_keys == EXPECTED_KEYS, (
        f"frontend/app.js LICENSE_SOURCES keys mismatch.\n"
        f"  Expected: {sorted(EXPECTED_KEYS)}\n"
        f"  Got:      {sorted(js_keys)}\n"
        f"  Missing:  {sorted(EXPECTED_KEYS - js_keys)}\n"
        f"  Extra:    {sorted(js_keys - EXPECTED_KEYS)}"
    )


def test_desktop_app_js_license_keys_match_api():
    """desktop/app.js LICENSE_SOURCES keys must match API license_attribution keys."""
    js_keys = _extract_license_keys(PROJECT_ROOT / "desktop" / "app.js")
    assert js_keys == EXPECTED_KEYS, (
        f"desktop/app.js LICENSE_SOURCES keys mismatch.\n"
        f"  Expected: {sorted(EXPECTED_KEYS)}\n"
        f"  Got:      {sorted(js_keys)}\n"
        f"  Missing:  {sorted(EXPECTED_KEYS - js_keys)}\n"
        f"  Extra:    {sorted(js_keys - EXPECTED_KEYS)}"
    )


def test_no_club_elo_underscore_key():
    """The old 'club_elo' key (with underscore) must not appear — it breaks API lookup."""
    for js_file in ["frontend/app.js", "desktop/app.js"]:
        content = (PROJECT_ROOT / js_file).read_text(encoding="utf-8")
        # Look for key: "club_elo" specifically
        assert 'key: "club_elo"' not in content, (
            f"{js_file} still uses 'club_elo' key — must be 'clubelo' to match API"
        )
