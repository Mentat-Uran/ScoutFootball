"""Integration tests for ScoutFootball FastAPI endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def client():
    """Create a TestClient for the FastAPI app (module-scoped for speed)."""
    from scoutfootball.api_server import create_app

    app = create_app()
    return TestClient(app)


def test_artifacts_endpoint(client: TestClient):
    """/artifacts should return 200 with artifact summary."""
    response = client.get("/artifacts")
    assert response.status_code == 200
    data = response.json()
    assert "artifacts" in data or "data_source_label" in data


def test_ratings_snapshots_endpoint(client: TestClient):
    """/ratings/snapshots should return 200."""
    response = client.get("/ratings/snapshots")
    assert response.status_code == 200


def test_predictions_meta_endpoint(client: TestClient):
    """/predictions/meta should return 200."""
    response = client.get("/predictions/meta")
    assert response.status_code == 200


def test_action_values_endpoint(client: TestClient):
    """/action-values should return 200."""
    response = client.get("/action-values")
    assert response.status_code == 200


def test_action_value_rating_links_endpoint_is_explicit_about_candidate_status(client: TestClient):
    response = client.get("/action-values/players/8945/rating-links")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "scoutfootball.action-value-rating-links"
    assert payload["status"] in {
        "candidate_available", "no_strict_candidate", "not_found", "rating_artifact_unavailable",
    }
    assert isinstance(payload["rating_candidates"], list)
    assert any("human verification" in item for item in payload["limitations"])
    if payload["status"] == "candidate_available":
        assert payload["rating_candidates"][0]["match_basis"] == "normalized_name_team_season"


def test_player_match_action_values_endpoint_is_explicit_before_generation(client: TestClient):
    response = client.get("/action-values/matches")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "not_generated", "no_data"}
    assert "rows" in payload
    if payload["status"] == "not_generated":
        assert payload["coverage_scope"] == "sample"
        assert "action-value-matches" in payload["build_command"]


def test_health_endpoint(client: TestClient):
    """/health should return 200."""
    response = client.get("/health")
    assert response.status_code == 200


def test_teams_strength_endpoint(client: TestClient):
    """/teams/strength should return 200 with team strength data."""
    response = client.get("/teams/strength")
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "teams" in data
    assert isinstance(data["teams"], list)
    if data["teams"]:
        team = data["teams"][0]
        assert "team" in team
        assert "overall_rating" in team
        assert "squad_size" in team
        assert "position_groups" in team
        assert "top_players" in team


def test_teams_strength_with_limit(client: TestClient):
    """/teams/strength should respect limit parameter."""
    response = client.get("/teams/strength?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] <= 5


def test_players_compare_endpoint(client: TestClient):
    """/players/compare should return comparison data."""
    response = client.get("/players/compare?a=Lionel Messi&b=Cristiano Ronaldo")
    assert response.status_code == 200
    data = response.json()
    # Should have either comparison data or error
    if "error" not in data:
        assert "player_a" in data
        assert "player_b" in data
        assert "radar_labels" in data
        assert "radar_a" in data
        assert "radar_b" in data
        assert "stats_comparison" in data


def test_teams_compare_endpoint(client: TestClient):
    """/teams/compare should return team comparison data."""
    response = client.get("/teams/compare?a=Arsenal&b=Barcelona")
    assert response.status_code == 200
    data = response.json()
    if "error" not in data:
        assert "team_a" in data
        assert "team_b" in data
        assert "position_group_comparison" in data
        assert "radar_labels" in data


def test_world_cup_match_briefing_endpoint(client: TestClient):
    """World Cup briefing exposes a model result with explicit limitations."""
    response = client.get("/world-cup/match-briefings/Argentina/France")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["schema"] == "scoutfootball.world-cup-match-briefing"
    assert data["prediction"]["model_type"] == "world_cup_strength_poisson"
    assert data["teams"]["home"]["squad"]["balance"]["scope"] == "expected_callup_snapshot"
    assert "limitations" in data


def test_world_cup_knockout_briefing_endpoint_keeps_unresolved_state_explicit(client: TestClient):
    response = client.get("/world-cup/tournament/knockout/R32-01/briefing")

    assert response.status_code == 200
    data = response.json()
    assert data["schema"] == "scoutfootball.world-cup-knockout-match-briefing"
    assert data["status"] in {
        "not_generated", "not_ready", "not_found", "ok", "briefing_unavailable",
    }


def test_world_cup_knockout_review_endpoint_never_backfills_a_prediction(client: TestClient):
    response = client.get("/world-cup/tournament/knockout/R32-01/review")

    assert response.status_code == 200
    data = response.json()
    assert data["schema"] == "scoutfootball.world-cup-knockout-result-review"
    assert data["status"] in {
        "not_generated", "not_found", "not_completed", "snapshot_not_recorded", "ok",
    }
    assert data["recording_scope"] == "browser-local tournament bracket state"


def test_world_cup_squad_balance_comparison_endpoint(client: TestClient):
    response = client.get("/world-cup/squad-balance-comparison/Argentina/France")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["roles"][0]["role"] == "GK"
