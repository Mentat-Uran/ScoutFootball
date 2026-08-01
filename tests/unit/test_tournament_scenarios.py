"""Unit tests for compute_knockout_scenarios and simulate_group_stage."""

from __future__ import annotations

import pytest

from scoutfootball.worldcup.data import (
    GROUPS,
    compute_knockout_scenarios,
    simulate_group_stage,
)
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
    teams = [t for ts in GROUPS.values() for t in ts]
    return {t: 0.5 for t in teams}


@pytest.fixture
def varied_strengths():
    """Varied team strengths — first team in each group is stronger."""
    strengths = {}
    for _letter, teams in GROUPS.items():
        for i, t in enumerate(teams):
            strengths[t] = 0.8 - i * 0.15
    return strengths


# ── compute_knockout_scenarios tests ──────────────────────────────


class TestComputeKnockoutScenarios:
    def test_no_bracket_returns_error(self, fresh_state, team_strengths):
        overview = get_knockout_overview(fresh_state)
        result = compute_knockout_scenarios(overview, team_strengths, "Argentina")
        assert result["status"] == "error"

    def test_team_not_in_bracket_returns_error(
        self, state_with_bracket, team_strengths
    ):
        overview = get_knockout_overview(state_with_bracket)
        result = compute_knockout_scenarios(
            overview, team_strengths, "NonExistentTeam"
        )
        assert result["status"] == "error"

    def test_team_in_bracket_returns_scenarios(
        self, state_with_bracket, team_strengths
    ):
        overview = get_knockout_overview(state_with_bracket)
        # Get a team from the R32 matches
        r32 = overview.get("rounds", {}).get("r32", {})
        matches = r32.get("matches", [])
        assert len(matches) > 0
        team = matches[0]["home"]
        result = compute_knockout_scenarios(
            overview, team_strengths, team, num_simulations=200
        )
        assert result["status"] == "ok"
        assert result["team"] == team
        assert "current_championship_probability" in result
        assert "next_match" in result
        assert "scenarios" in result
        assert "disclaimer" in result

    def test_next_match_has_opponent_and_win_prob(
        self, state_with_bracket, team_strengths
    ):
        overview = get_knockout_overview(state_with_bracket)
        r32 = overview.get("rounds", {}).get("r32", {})
        team = r32["matches"][0]["home"]
        result = compute_knockout_scenarios(
            overview, team_strengths, team, num_simulations=200
        )
        nm = result["next_match"]
        assert nm is not None
        assert nm["opponent"] is not None
        assert nm["win_probability"] is not None
        assert 0.0 <= nm["win_probability"] <= 1.0

    def test_equal_strengths_give_50_50_next_match(
        self, state_with_bracket, team_strengths
    ):
        overview = get_knockout_overview(state_with_bracket)
        r32 = overview.get("rounds", {}).get("r32", {})
        team = r32["matches"][0]["home"]
        result = compute_knockout_scenarios(
            overview, team_strengths, team, num_simulations=200
        )
        nm = result["next_match"]
        assert abs(nm["win_probability"] - 0.5) < 0.01

    def test_championship_if_win_greater_than_baseline(
        self, state_with_bracket, team_strengths
    ):
        overview = get_knockout_overview(state_with_bracket)
        r32 = overview.get("rounds", {}).get("r32", {})
        team = r32["matches"][0]["home"]
        result = compute_knockout_scenarios(
            overview, team_strengths, team, num_simulations=500
        )
        baseline = result["current_championship_probability"]
        scenarios = result["scenarios"]
        assert len(scenarios) > 0
        champ_if_win = scenarios[0]["championship_if_win"]
        # If team wins their next match, championship prob should be >= baseline
        # (could be equal in edge cases but generally higher)
        assert champ_if_win >= baseline - 0.001

    def test_championship_if_lose_is_zero(
        self, state_with_bracket, team_strengths
    ):
        overview = get_knockout_overview(state_with_bracket)
        r32 = overview.get("rounds", {}).get("r32", {})
        team = r32["matches"][0]["home"]
        result = compute_knockout_scenarios(
            overview, team_strengths, team, num_simulations=200
        )
        for s in result["scenarios"]:
            if "championship_if_lose" in s:
                assert s["championship_if_lose"] == 0.0

    def test_reproducible_with_seed(self, state_with_bracket, team_strengths):
        overview = get_knockout_overview(state_with_bracket)
        r32 = overview.get("rounds", {}).get("r32", {})
        team = r32["matches"][0]["home"]
        result1 = compute_knockout_scenarios(
            overview, team_strengths, team, num_simulations=200, seed=42
        )
        result2 = compute_knockout_scenarios(
            overview, team_strengths, team, num_simulations=200, seed=42
        )
        assert (
            result1["current_championship_probability"]
            == result2["current_championship_probability"]
        )

    def test_disclaimer_present(self, state_with_bracket, team_strengths):
        overview = get_knockout_overview(state_with_bracket)
        r32 = overview.get("rounds", {}).get("r32", {})
        team = r32["matches"][0]["home"]
        result = compute_knockout_scenarios(
            overview, team_strengths, team, num_simulations=100
        )
        assert "disclaimer" in result
        assert len(result["disclaimer"]) > 10

    def test_scenarios_have_required_fields(
        self, state_with_bracket, team_strengths
    ):
        overview = get_knockout_overview(state_with_bracket)
        r32 = overview.get("rounds", {}).get("r32", {})
        team = r32["matches"][0]["home"]
        result = compute_knockout_scenarios(
            overview, team_strengths, team, num_simulations=100
        )
        for s in result["scenarios"]:
            assert "round" in s
            assert "match_id" in s

    def test_eliminated_team_returns_zero_prob(
        self, state_with_bracket, team_strengths
    ):
        """Test that a team that lost a match shows 0 championship probability."""
        overview = get_knockout_overview(state_with_bracket)
        r32 = overview.get("rounds", {}).get("r32", {})
        first_match = r32["matches"][0]
        home_team = first_match["home"]

        # Apply a result where home team loses (modifies state in-place)
        apply_knockout_result(
            state_with_bracket,
            first_match["match_id"],
            home_goals=0,
            away_goals=1,
        )
        overview = get_knockout_overview(state_with_bracket)
        result = compute_knockout_scenarios(
            overview, team_strengths, home_team, num_simulations=100
        )
        assert result["status"] == "ok"
        assert result["current_championship_probability"] == 0.0
        assert result["next_match"] is None
        assert result["scenarios"] == []


# ── simulate_group_stage tests ────────────────────────────────────


class TestSimulateGroupStage:
    def test_no_remaining_matches(self, fresh_state, team_strengths):
        """When all group matches are completed, returns deterministic results."""
        # Complete all group matches with 1-0 home wins
        from scoutfootball.worldcup.tournament import apply_result

        state = fresh_state
        for m in state.matches:
            g = m.get("group", "")
            if g and g not in ("r32", "r16", "qf", "sf", "final"):
                apply_result(state, m["match_id"], 1, 0)

        result = simulate_group_stage(state, team_strengths, num_simulations=10)
        assert result["status"] == "ok"
        assert result["remaining_matches"] == 0
        assert result["num_simulations"] == 1

    def test_random_mode_basic(self, fresh_state):
        """Random mode should produce valid output with unplayed matches."""
        result = simulate_group_stage(
            fresh_state, None, num_simulations=50, mode="random"
        )
        assert result["status"] == "ok"
        assert result["mode"] == "random"
        assert result["num_simulations"] == 50
        assert result["remaining_matches"] > 0
        assert len(result["advancement_probability"]) > 0
        assert len(result["most_likely_group_winners"]) > 0

    def test_strength_mode_basic(self, fresh_state, team_strengths):
        """Strength mode should produce valid output."""
        result = simulate_group_stage(
            fresh_state, team_strengths, num_simulations=50, mode="strength"
        )
        assert result["status"] == "ok"
        assert result["mode"] == "strength"

    def test_advancement_probabilities_in_range(self, fresh_state):
        result = simulate_group_stage(
            fresh_state, None, num_simulations=50, mode="random"
        )
        for t in result["advancement_probability"]:
            assert 0.0 <= t["advance_prob"] <= 1.0
            assert 0.0 <= t["win_group_prob"] <= 1.0
            assert t["group"] in GROUPS

    def test_most_likely_winners_cover_all_groups(self, fresh_state):
        result = simulate_group_stage(
            fresh_state, None, num_simulations=50, mode="random"
        )
        groups_covered = {w["group"] for w in result["most_likely_group_winners"]}
        assert groups_covered == set(GROUPS.keys())

    def test_reproducible_with_seed(self, fresh_state, team_strengths):
        result1 = simulate_group_stage(
            fresh_state, team_strengths, num_simulations=100, seed=42
        )
        result2 = simulate_group_stage(
            fresh_state, team_strengths, num_simulations=100, seed=42
        )
        # Same seed should produce same advancement probabilities
        assert result1["advancement_probability"] == result2["advancement_probability"]

    def test_disclaimer_present(self, fresh_state):
        result = simulate_group_stage(
            fresh_state, None, num_simulations=10, mode="random"
        )
        assert "disclaimer" in result
        assert len(result["disclaimer"]) > 10

    def test_strength_mode_favors_stronger_teams(
        self, fresh_state, varied_strengths
    ):
        """With varied strengths, stronger teams should have higher advancement prob."""
        result = simulate_group_stage(
            fresh_state, varied_strengths, num_simulations=300, mode="strength"
        )
        adv_map = {t["team"]: t["advance_prob"] for t in result["advancement_probability"]}
        # Check that for each group, the first team (strongest) has higher prob
        # than the last team (weakest)
        for _letter, teams in GROUPS.items():
            strongest = teams[0]
            weakest = teams[-1]
            if strongest in adv_map and weakest in adv_map:
                # With enough simulations, stronger should generally be higher
                # (allow some tolerance for randomness)
                assert adv_map[strongest] >= adv_map[weakest] - 0.15

    def test_all_48_teams_in_advancement_list(self, fresh_state):
        result = simulate_group_stage(
            fresh_state, None, num_simulations=50, mode="random"
        )
        all_teams = {t for ts in GROUPS.values() for t in ts}
        result_teams = {t["team"] for t in result["advancement_probability"]}
        assert all_teams == result_teams

    def test_winner_probability_correlates_with_frequency(self, fresh_state):
        result = simulate_group_stage(
            fresh_state, None, num_simulations=100, mode="random"
        )
        for w in result["most_likely_group_winners"]:
            assert w["frequency"] > 0
            expected_prob = w["frequency"] / result["num_simulations"]
            assert abs(w["probability"] - round(expected_prob, 4)) < 0.01
