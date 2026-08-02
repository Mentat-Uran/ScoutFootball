"""Integration tests for ScoutFootball FastAPI endpoints."""

from __future__ import annotations

import base64
import json
from urllib.parse import quote

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
    assert "player_match_coverage" in data["data_health"]


def test_truth_label_supervision_endpoint_exposes_source_policy(client: TestClient):
    response = client.get("/reports/truth-labels")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "scoutfootball.truth-label-supervision"
    assert payload["status"] in {"eligible_labels_available", "no_eligible_labels", "no_data"}
    assert "eligible_rows" in payload["report"]
    assert "caveat" in payload["report"]


def test_transfermarkt_identity_report_endpoint_preserves_no_data_boundary(client: TestClient):
    response = client.get("/reports/transfermarkt-identities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "scoutfootball.transfermarkt-identity-report"
    assert payload["status"] in {"available", "no_data", "unavailable"}
    assert "report" in payload


def test_ratings_snapshots_endpoint(client: TestClient):
    """/ratings/snapshots should return 200."""
    response = client.get("/ratings/snapshots")
    assert response.status_code == 200


def test_ratings_endpoint_exposes_canonical_identity_boundary(client: TestClient):
    response = client.get("/ratings?limit=5")
    assert response.status_code == 200
    payload = response.json()
    assert payload["canonical_resolution"] in {"ok", "unavailable"}
    for player in payload["players"]:
        assert "canonical_player_id" in player
        assert "canonical_match_ambiguous" in player
        if str(player["canonical_player_id"]).startswith("unresolved:"):
            assert player["canonical_match_ambiguous"] in {True, False}


def test_player_detail_accepts_canonical_identity_selector(client: TestClient):
    ratings = client.get("/ratings?limit=1").json().get("players", [])
    if not ratings:
        pytest.skip("ratings artifact unavailable")

    row = ratings[0]
    query = f"canonical_player_id={quote(str(row['canonical_player_id']), safe='')}"
    if row.get("season"):
        query += f"&season={quote(str(row['season']), safe='')}"
    response = client.get(f"/players/{quote(str(row['player']), safe='')}?{query}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["found"] is True
    assert payload["canonical_player_id"] == row["canonical_player_id"]


def test_ratings_meta_exposes_proxy_source_lineage(client: TestClient):
    response = client.get("/ratings/meta")
    assert response.status_code == 200
    source = response.json()["rating_source"]
    assert source["kind"] == "optimizer_proxy_objective"
    assert source["latest_run_id"]
    assert source["training_objective"]
    assert "current_manifest_hash" in source
    assert "/health/research" in source["research_health_endpoint"]


def test_model_training_endpoint_exposes_active_neural_diagnostics(client: TestClient):
    response = client.get("/reports/model-training")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "no_data"}
    if payload["status"] == "ok":
        assert payload["model_type"] in {"team_points_mlp", "team_points_set_transformer"}
        assert payload["history"]
        assert payload["training_device"] in {"cuda", "cpu"}


def test_market_value_endpoint_preserves_source_boundary(client: TestClient):
    response = client.get("/market-value/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "no_data"}
    assert "source" in payload
    assert "license_boundary" in payload["source"]
    if payload["status"] == "ok":
        assert payload["latest_snapshot_date"]
        assert all("player_name" in row for row in payload["top_players"])


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
    assert data["recording_scope"] == "local application tournament state"


def test_world_cup_knockout_review_ledger_endpoint_is_local_only(client: TestClient):
    response = client.get("/world-cup/tournament/knockout/reviews")

    assert response.status_code == 200
    data = response.json()
    assert data["schema"] == "scoutfootball.world-cup-knockout-review-ledger"
    assert data["recording_scope"] == "local application tournament state"
    assert data["status"] in {"not_generated", "ok"}


def test_tournament_import_preview_reports_integrity_without_persisting(client: TestClient):
    from scoutfootball.worldcup.tournament import init_state, state_to_dict

    incoming = state_to_dict(init_state())
    incoming["matches"][0]["home"] = "Altered Team"
    encoded = base64.urlsafe_b64encode(json.dumps(incoming).encode("utf-8")).decode("ascii")

    response = client.post("/world-cup/tournament/import/preview", json={"encoded": encoded})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert data["code"] == "integrity_failed"
    assert any("altered home" in issue for issue in data["integrity_errors"])


def test_tournament_qualification_impact_endpoint_is_local_and_provisional(client: TestClient):
    response = client.get("/world-cup/tournament/qualification-impact?group=A")

    assert response.status_code == 200
    data = response.json()
    assert data["schema"] == "scoutfootball.world-cup-qualification-impact"
    assert data["group"] == "A"
    assert data["third_place"]["cutoff_rank"] == 8
    assert "locally recorded group results" in data["limitations"][0]


def test_tournament_tiebreak_diagnostics_endpoint_exposes_local_boundary(client: TestClient):
    response = client.get("/world-cup/tournament/tiebreak-diagnostics?group=A")

    assert response.status_code == 200
    data = response.json()
    assert data["schema"] == "scoutfootball.world-cup-group-tiebreak-diagnostics"
    assert data["group"] == "A"
    assert "not an official ranking decision" in data["limitations"][-1]


def test_world_cup_squad_balance_comparison_endpoint(client: TestClient):
    response = client.get("/world-cup/squad-balance-comparison/Argentina/France")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["roles"][0]["role"] == "GK"
