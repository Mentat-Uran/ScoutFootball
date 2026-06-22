"""Contract checks for the restored scouting and action-value workbenches."""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = PROJECT_ROOT / "frontend"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_scouting_and_action_navigation_are_visible() -> None:
    html = _read(FRONTEND / "index.html")

    for view in ("scouting", "actions"):
        marker = f'data-view="{view}"'
        start = html.index(marker)
        button = html[html.rfind("<button", 0, start) : html.index("</button>", start)]
        assert "display:none" not in button.replace(" ", "")


def test_scouting_adapter_preserves_queue_contract_fields() -> None:
    app_js = _read(FRONTEND / "app.js")

    for field in (
        "player_name",
        "reason_code",
        "review_status",
        "reviewer_note",
        "as_of_date",
        "rating_snapshot_id",
    ):
        assert f"p.{field}" in app_js

    review_data = json.loads(_read(FRONTEND / "data" / "review_queue.json"))
    first = review_data["players"][0]
    assert first["player_name"]
    assert first["reason_code"]


def test_action_value_renderer_supports_current_xt_and_vaep_contracts() -> None:
    app_js = _read(FRONTEND / "app.js")
    action_data = json.loads(_read(FRONTEND / "data" / "action_values.json"))

    assert "actionData" not in app_js
    assert 'metricKey = mode === "vaep" ? "vaep_per_90" : "xt_per_90"' in app_js
    assert action_data["xt_players"][0]["xt_per_90"] is not None
    assert action_data["vaep_players"][0]["vaep_per_90"] is not None
    assert action_data["metrics"]["xt_rows"] > 0
    assert action_data["metrics"]["vaep_rows"] > 0


def test_restored_workbenches_expose_filters_and_boundaries() -> None:
    html = _read(FRONTEND / "index.html")

    for element_id in (
        "scout-search",
        "scout-status-filter",
        "scout-save-snapshot",
        "scout-export-csv",
        "action-search",
        "action-competition-filter",
        "action-minutes-filter",
    ):
        assert f'id="{element_id}"' in html

    assert "StatsBomb Open Data" in html
    assert "450" in html


def test_static_server_404_continues_to_mapped_json_fallback() -> None:
    app_js = _read(FRONTEND / "app.js")

    assert "_staticUrlFor(apiPath) === null" in app_js
    assert '"/review-queue": "/data/review_queue.json"' in app_js
    assert '"/action-values": "/data/action_values.json"' in app_js


def test_league_coverage_counts_rated_teams_not_player_rows() -> None:
    app_js = _read(FRONTEND / "app.js")

    assert "ratedTeams: new Set()" in app_js
    assert "ratedTeams.add(p.team)" in app_js
    assert "entry.ratedTeams.size" in app_js
