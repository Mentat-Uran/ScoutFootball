"""Unit tests for project_knockout_probabilities."""

from __future__ import annotations

import pytest

from scoutfootball.worldcup.data import project_knockout_probabilities
from scoutfootball.worldcup.tournament import (
    apply_knockout_result,
    generate_knockout_bracket,
    get_knockout_overview,
    init_state,
)


@pytest.fixture
def fresh_state():
    return init_state()


@pytest.fixture
def state_with_bracket(fresh_state):
    fresh_state.knockout = generate_knockout_bracket(fresh_state)
    return fresh_state


@pytest.fixture
def team_strengths():
    """Minimal team strengths for the 48 WC teams — all equal by default."""
    from scoutfootball.worldcup.data import GROUPS

    teams = [t for ts in GROUPS.values() for t in ts]
    return {t: 0.5 for t in teams}


@pytest.fixture
def varied_strengths():
    """Varied team strengths — first team in each group is stronger."""
    from scoutfootball.worldcup.data import GROUPS

    strengths = {}
    for _letter, teams in GROUPS.items():
        for i, t in enumerate(teams):
            strengths[t] = 0.8 - i * 0.15
    return strengths


class TestProjectKnockoutProbabilities:
    def test_no_bracket_returns_empty(self, team_strengths):
        overview = {"generated": False, "matches": []}
        result = project_knockout_probabilities(overview, team_strengths)
        assert result["status"] == "ok"
        assert result["match_probabilities"] == []
        assert result["tournament_win_probability"] == []

    def test_per_match_probabilities_for_ready_matches(
        self, state_with_bracket, team_strengths
    ):
        overview = get_knockout_overview(state_with_bracket)
        result = project_knockout_probabilities(overview, team_strengths)
        match_probs = result["match_probabilities"]
        # 31 matches total
        assert len(match_probs) == 31
        # R32 matches should have probabilities (both teams filled)
        r32_probs = [p for p in match_probs if p["round"] == "r32"]
        assert len(r32_probs) == 16
        for p in r32_probs:
            assert p["home_win_probability"] is not None
            assert p["away_win_probability"] is not None
            assert (
                abs(p["home_win_probability"] + p["away_win_probability"] - 1.0) < 0.01
            )

    def test_equal_strengths_give_50_50(self, state_with_bracket, team_strengths):
        overview = get_knockout_overview(state_with_bracket)
        result = project_knockout_probabilities(overview, team_strengths)
        r32_probs = [p for p in result["match_probabilities"] if p["round"] == "r32"]
        for p in r32_probs:
            assert abs(p["home_win_probability"] - 0.5) < 0.01
            assert abs(p["away_win_probability"] - 0.5) < 0.01

    def test_varied_strengths_favor_stronger_team(
        self, state_with_bracket, varied_strengths
    ):
        overview = get_knockout_overview(state_with_bracket)
        result = project_knockout_probabilities(overview, varied_strengths)
        r32_probs = [p for p in result["match_probabilities"] if p["round"] == "r32"]
        for p in r32_probs:
            home_str = varied_strengths.get(p["home"], 0.2)
            away_str = varied_strengths.get(p["away"], 0.2)
            if home_str > away_str:
                assert p["home_win_probability"] > 0.5
            elif away_str > home_str:
                assert p["away_win_probability"] > 0.5

    def test_tbd_matches_have_null_probabilities(self, state_with_bracket, team_strengths):
        overview = get_knockout_overview(state_with_bracket)
        result = project_knockout_probabilities(overview, team_strengths)
        # R16 and later should have null probabilities (teams TBD)
        r16_probs = [p for p in result["match_probabilities"] if p["round"] == "r16"]
        for p in r16_probs:
            assert p["home_win_probability"] is None
            assert p["away_win_probability"] is None

    def test_completed_match_has_known_winner(self, state_with_bracket, team_strengths):
        state = state_with_bracket
        m = state.knockout_match_by_id("r32-01")
        home = m["home"]
        apply_knockout_result(state, "r32-01", 2, 0)
        overview = get_knockout_overview(state)
        result = project_knockout_probabilities(overview, team_strengths)
        match_prob = next(
            p for p in result["match_probabilities"] if p["match_id"] == "r32-01"
        )
        assert match_prob["status"] == "completed"
        assert match_prob["winner"] == home
        assert match_prob["home_win_probability"] == 1.0
        assert match_prob["away_win_probability"] == 0.0

    def test_tournament_win_probability_when_r32_ready(
        self, state_with_bracket, team_strengths
    ):
        overview = get_knockout_overview(state_with_bracket)
        result = project_knockout_probabilities(
            overview, team_strengths, num_simulations=100
        )
        assert result["num_simulations"] == 100
        odds = result["tournament_win_probability"]
        assert len(odds) > 0
        assert len(odds) <= 16
        # Probabilities should be positive and sorted descending
        for t in odds:
            assert t["win_probability"] > 0
        for i in range(len(odds) - 1):
            assert odds[i]["win_probability"] >= odds[i + 1]["win_probability"]

    def test_tournament_win_probability_respects_completed_matches(
        self, state_with_bracket, varied_strengths
    ):
        state = state_with_bracket
        # Complete all R32 matches — stronger team always wins (1-0)
        for i in range(1, 17):
            mid = f"r32-{i:02d}"
            apply_knockout_result(state, mid, 1, 0)
        overview = get_knockout_overview(state)
        result = project_knockout_probabilities(
            overview, varied_strengths, num_simulations=200
        )
        odds = result["tournament_win_probability"]
        assert len(odds) > 0
        # Only R32 winners should appear in tournament odds
        r32_winners = set()
        for i in range(1, 17):
            m = state.knockout_match_by_id(f"r32-{i:02d}")
            r32_winners.add(m["winner"])
        odds_teams = {t["team"] for t in odds}
        assert odds_teams.issubset(r32_winners)

    def test_reproducible_with_seed(self, state_with_bracket, team_strengths):
        overview = get_knockout_overview(state_with_bracket)
        r1 = project_knockout_probabilities(overview, team_strengths, seed=42, num_simulations=100)
        r2 = project_knockout_probabilities(overview, team_strengths, seed=42, num_simulations=100)
        assert r1["tournament_win_probability"] == r2["tournament_win_probability"]

    def test_disclaimer_present(self, state_with_bracket, team_strengths):
        overview = get_knockout_overview(state_with_bracket)
        result = project_knockout_probabilities(overview, team_strengths)
        assert "disclaimer" in result
        assert len(result["disclaimer"]) > 0

    def test_match_probabilities_have_required_fields(
        self, state_with_bracket, team_strengths
    ):
        overview = get_knockout_overview(state_with_bracket)
        result = project_knockout_probabilities(overview, team_strengths)
        for p in result["match_probabilities"]:
            assert "match_id" in p
            assert "round" in p
            assert "home" in p
            assert "away" in p
            assert "status" in p
            assert "home_win_probability" in p
            assert "away_win_probability" in p

    def test_no_tournament_odds_when_r32_not_ready(self, fresh_state, team_strengths):
        """When no bracket is generated, there should be no tournament odds."""
        overview = get_knockout_overview(fresh_state)
        result = project_knockout_probabilities(overview, team_strengths)
        assert result["tournament_win_probability"] == []
        assert result["num_simulations"] == 0
