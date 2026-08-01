"""Tests for the World Cup tournament match-predictions batch endpoint.

Covers :func:`scoutfootball.api.get_wc_tournament_match_predictions`,
which returns a compact Poisson-model prediction summary for each
scheduled group-stage match (filtered by group when requested), and
annotates completed matches with a prediction-delta classification.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from scoutfootball import api
from scoutfootball.api import (
    _classify_prediction_delta,
    _most_likely_wc_scoreline,
    get_wc_tournament_match_predictions,
)

# ── helpers ───────────────────────────────────────────────────────────


def _match(
    match_id: str,
    group: str,
    home: str,
    away: str,
    *,
    matchday: int = 1,
    date: str = "2026-06-11",
    venue: str = "Venue",
    city: str = "City",
) -> dict:
    return {
        "match_id": match_id,
        "group": group,
        "matchday": matchday,
        "date": date,
        "time_et": "12:00",
        "home": home,
        "away": away,
        "venue": venue,
        "city": city,
    }


def _state(matches, results=None):
    """Build a minimal tournament state duck-typed object."""
    return SimpleNamespace(matches=list(matches), results=results or {})


def _completed_result(home_goals: int, away_goals: int) -> dict:
    winner = "home" if home_goals > away_goals else (
        "away" if away_goals > home_goals else "draw"
    )
    return {
        "status": "completed",
        "home_goals": home_goals,
        "away_goals": away_goals,
        "winner": winner,
        "decided_by": "regular",
    }


@pytest.fixture
def _mock_env(monkeypatch):
    """Mock tournament state + WC squads for batch prediction tests.

    - "Alpha" and "Beta" are valid WC teams with enriched squads.
    - "Gamma" is a valid WC team (used to test host bonus).
    - "Unknown" is not in enriched_squads (team_not_found path).
    """
    matches = [
        _match("A-1-Alpha-Beta-001", "A", "Alpha", "Beta", matchday=1),
        _match("A-2-Gamma-Alpha-002", "A", "Gamma", "Alpha", matchday=2),
        _match("B-1-Unknown-Alpha-003", "B", "Unknown", "Alpha", matchday=1),
        _match("A-3-Beta-Gamma-004", "A", "Beta", "Gamma", matchday=3),
    ]
    state = _state(matches)

    monkeypatch.setattr(api, "_wc_tournament_state", lambda: state)

    enriched = {"Alpha": [], "Beta": [], "Gamma": []}
    strengths = {"Alpha": 0.8, "Beta": 0.5, "Gamma": 0.6}
    monkeypatch.setattr(
        api, "_get_wc_enriched_squads", lambda: (enriched, strengths)
    )
    monkeypatch.setattr(api, "HOSTS", ["Gamma"])
    return state


# ── status / structure ────────────────────────────────────────────────


def test_ok_status(_mock_env):
    result = get_wc_tournament_match_predictions()
    assert result["status"] == "ok"
    assert result["count"] == 4
    assert result["model"] == "world_cup_strength_poisson"
    assert result["model_version"] == "wc-1.0"
    assert "disclaimer" in result
    assert "source_attribution" in result


def test_group_filter_returns_only_matching(_mock_env):
    result = get_wc_tournament_match_predictions(group="A")
    assert result["status"] == "ok"
    assert result["group"] == "A"
    assert result["count"] == 3
    for entry in result["predictions"]:
        assert entry["group"] == "A"


def test_group_filter_case_insensitive(_mock_env):
    result = get_wc_tournament_match_predictions(group="a")
    assert result["status"] == "ok"
    assert result["group"] == "A"
    assert result["count"] == 3


def test_unknown_group_returns_error(_mock_env):
    result = get_wc_tournament_match_predictions(group="Z")
    assert result["status"] == "error"
    assert result["code"] == "unknown_group"


def test_no_data_when_squads_empty(monkeypatch):
    monkeypatch.setattr(api, "_wc_tournament_state", lambda: _state([]))
    monkeypatch.setattr(
        api, "_get_wc_enriched_squads", lambda: ({}, {})
    )
    result = get_wc_tournament_match_predictions()
    assert result["status"] == "no_data"
    assert result["predictions"] == []
    assert result["count"] == 0


# ── per-match fields ──────────────────────────────────────────────────


def test_prediction_entry_fields(_mock_env):
    result = get_wc_tournament_match_predictions()
    alpha_beta = next(
        e for e in result["predictions"] if e["match_id"] == "A-1-Alpha-Beta-001"
    )
    assert alpha_beta["status"] == "ok"
    assert alpha_beta["home"] == "Alpha"
    assert alpha_beta["away"] == "Beta"
    assert alpha_beta["group"] == "A"
    assert alpha_beta["matchday"] == 1
    assert "home_win_prob" in alpha_beta
    assert "draw_prob" in alpha_beta
    assert "away_win_prob" in alpha_beta
    assert "expected_goals_home" in alpha_beta
    assert "expected_goals_away" in alpha_beta
    assert "home_strength" in alpha_beta
    assert "away_strength" in alpha_beta
    assert "host_bonus" in alpha_beta
    assert "most_likely_scoreline" in alpha_beta
    assert alpha_beta["completed"] is False


def test_probabilities_sum_to_one(_mock_env):
    result = get_wc_tournament_match_predictions()
    for entry in result["predictions"]:
        if entry["status"] != "ok":
            continue
        total = (
            entry["home_win_prob"] + entry["draw_prob"] + entry["away_win_prob"]
        )
        assert abs(total - 1.0) < 0.01


def test_host_bonus_applied(_mock_env):
    """Gamma is a host; when Gamma is home, host_bonus > 0."""
    result = get_wc_tournament_match_predictions()
    gamma_home = next(
        e for e in result["predictions"] if e["home"] == "Gamma"
    )
    assert gamma_home["host_bonus"] > 0
    assert gamma_home["home_is_host"] is True
    assert gamma_home["away_is_host"] is False


def test_host_bonus_negative_when_away_is_host(_mock_env):
    """When the away team is a host, host_bonus should be negative."""
    result = get_wc_tournament_match_predictions()
    gamma_away = next(
        e for e in result["predictions"] if e["away"] == "Gamma"
    )
    assert gamma_away["host_bonus"] < 0
    assert gamma_away["away_is_host"] is True


def test_team_not_found_entry(_mock_env):
    """Unknown (not in enriched_squads) should produce team_not_found status."""
    result = get_wc_tournament_match_predictions()
    unknown_entry = next(
        e for e in result["predictions"] if e["home"] == "Unknown"
    )
    assert unknown_entry["status"] == "team_not_found"
    assert unknown_entry["completed"] is False
    assert "home_win_prob" not in unknown_entry


def test_most_likely_scoreline_structure(_mock_env):
    result = get_wc_tournament_match_predictions()
    entry = result["predictions"][0]
    mls = entry["most_likely_scoreline"]
    assert "home_goals" in mls
    assert "away_goals" in mls
    assert "probability" in mls
    assert 0 <= mls["home_goals"] <= 5
    assert 0 <= mls["away_goals"] <= 5
    assert 0.0 <= mls["probability"] <= 1.0


# ── completed matches + delta classification ──────────────────────────


def test_completed_match_has_result_and_delta(monkeypatch):
    """When a match has a recorded result, the entry includes result + delta."""
    matches = [_match("A-1-Alpha-Beta-001", "A", "Alpha", "Beta")]
    results = {"A-1-Alpha-Beta-001": _completed_result(3, 0)}
    state = _state(matches, results)
    monkeypatch.setattr(api, "_wc_tournament_state", lambda: state)
    monkeypatch.setattr(
        api,
        "_get_wc_enriched_squads",
        lambda: ({"Alpha": [], "Beta": []}, {"Alpha": 0.8, "Beta": 0.4}),
    )
    monkeypatch.setattr(api, "HOSTS", [])

    result = get_wc_tournament_match_predictions()
    entry = result["predictions"][0]
    assert entry["completed"] is True
    assert entry["result"]["home_goals"] == 3
    assert entry["result"]["away_goals"] == 0
    assert entry["result"]["winner"] == "home"
    assert "delta" in entry
    assert entry["delta"]["classification"] in {
        "as_expected", "upset", "hold"
    }
    assert entry["delta"]["actual_outcome"] == "home_win"
    assert "predicted_outcome" in entry["delta"]
    assert "actual_prob" in entry["delta"]


def test_pending_match_has_no_result_or_delta(_mock_env):
    result = get_wc_tournament_match_predictions()
    entry = next(
        e for e in result["predictions"] if e["match_id"] == "A-1-Alpha-Beta-001"
    )
    assert entry["completed"] is False
    assert "result" not in entry
    assert "delta" not in entry


def test_delta_as_expected_when_predicted_outcome_matches_actual():
    """If argmax prediction matches actual result, classification is as_expected."""
    # home_win is the argmax (0.6 > 0.25 > 0.15)
    delta = _classify_prediction_delta(0.60, 0.25, 0.15, 2, 1)
    assert delta["classification"] == "as_expected"
    assert delta["actual_outcome"] == "home_win"
    assert delta["predicted_outcome"] == "home_win"


def test_delta_upset_when_low_prob_outcome_happens():
    """If actual outcome's pre-match prob < 0.30 and not as_expected, upset."""
    # away_win is 0.10 (< 0.30) and actual is away win
    delta = _classify_prediction_delta(0.55, 0.35, 0.10, 0, 1)
    assert delta["classification"] == "upset"
    assert delta["actual_outcome"] == "away_win"
    assert delta["predicted_outcome"] == "home_win"


def test_delta_hold_when_middle_prob_outcome_happens():
    """If actual is neither argmax nor < 0.30, classification is hold."""
    # draw is 0.35 (>= 0.30, not argmax)
    delta = _classify_prediction_delta(0.50, 0.35, 0.15, 1, 1)
    assert delta["classification"] == "hold"
    assert delta["actual_outcome"] == "draw"
    assert delta["predicted_outcome"] == "home_win"


def test_delta_as_expected_takes_priority_over_upset():
    """If actual == argmax but prob < 0.30, as_expected wins over upset."""
    # home_win is argmax at 0.40 (still argmax, < 0.50 but > others)
    delta = _classify_prediction_delta(0.40, 0.35, 0.25, 1, 0)
    assert delta["classification"] == "as_expected"
    assert delta["actual_outcome"] == "home_win"


# ── _most_likely_wc_scoreline ─────────────────────────────────────────


def test_most_likely_scoreline_finds_max():
    matrix = [
        [0.05, 0.10, 0.02],
        [0.20, 0.40, 0.05],
        [0.03, 0.08, 0.07],
    ]
    result = _most_likely_wc_scoreline(matrix)
    assert result["home_goals"] == 1
    assert result["away_goals"] == 1
    assert result["probability"] == 0.40


def test_most_likely_scoreline_handles_ties():
    """When multiple cells tie, the first (lowest h, then lowest a) wins."""
    matrix = [
        [0.50, 0.10],
        [0.10, 0.50],
    ]
    result = _most_likely_wc_scoreline(matrix)
    # First maximum encountered (i=0, j=0) wins
    assert result["home_goals"] == 0
    assert result["away_goals"] == 0


def test_most_likely_scoreline_returns_rounded_prob():
    matrix = [[0.333333, 0.666666]]
    result = _most_likely_wc_scoreline(matrix)
    assert result["probability"] == 0.6667
