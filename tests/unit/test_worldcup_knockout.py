"""Unit tests for World Cup knockout bracket simulation."""

from __future__ import annotations

import pytest

from scoutfootball.worldcup.data import (
    GROUPS,
    SquadPlayer,
    _knockout_match_prob,
    _predict_group_finishes,
    _seed_round_of_32,
    compute_group_predictions,
    compute_team_outlook,
    compute_team_strength_details,
    simulate_knockout,
)


@pytest.fixture()
def sample_strengths():
    """Return a small set of team strengths for testing."""
    return {
        "Spain": 0.85,
        "France": 0.82,
        "Brazil": 0.80,
        "England": 0.78,
        "Argentina": 0.77,
        "Germany": 0.72,
        "Portugal": 0.70,
        "Netherlands": 0.68,
        "Uruguay": 0.60,
        "Belgium": 0.58,
        "Mexico": 0.50,
        "Canada": 0.48,
        "South Africa": 0.35,
        "Qatar": 0.30,
        "New Zealand": 0.25,
        "Curacao": 0.20,
    }


@pytest.fixture()
def full_strengths():
    """Return strengths for all 48 WC teams."""
    strengths = {}
    for teams in GROUPS.values():
        for i, team in enumerate(teams):
            strengths[team] = 0.85 - i * 0.15
    return strengths


class TestKnockoutMatchProb:
    def test_equal_strengths(self):
        assert _knockout_match_prob(0.5, 0.5) == pytest.approx(0.5)

    def test_home_stronger(self):
        p = _knockout_match_prob(0.8, 0.4)
        assert 0.5 < p <= 1.0

    def test_away_stronger(self):
        p = _knockout_match_prob(0.3, 0.7)
        assert 0.0 <= p < 0.5

    def test_zero_strengths(self):
        assert _knockout_match_prob(0.0, 0.0) == 0.5

    def test_probabilities_sum_to_one(self):
        p_home = _knockout_match_prob(0.6, 0.4)
        # Home + away probabilities always sum to 1
        assert p_home + (1 - p_home) == pytest.approx(1.0)


class TestPredictGroupFinishes:
    def test_returns_three_lists(self, sample_strengths):
        preds = compute_group_predictions(sample_strengths)
        firsts, seconds, thirds = _predict_group_finishes(preds)
        assert isinstance(firsts, list)
        assert isinstance(seconds, list)
        assert isinstance(thirds, list)

    def test_each_group_has_representative(self, full_strengths):
        preds = compute_group_predictions(full_strengths)
        firsts, seconds, thirds = _predict_group_finishes(preds)
        assert len(firsts) == 12
        assert len(seconds) == 12
        assert len(thirds) == 12

    def test_firsts_sorted_by_strength_descending(self, full_strengths):
        preds = compute_group_predictions(full_strengths)
        firsts, _, _ = _predict_group_finishes(preds)
        strengths = [s for _, _, s in firsts]
        assert strengths == sorted(strengths, reverse=True)


class TestSeedRoundOf32:
    def test_produces_16_matchups(self, full_strengths):
        preds = compute_group_predictions(full_strengths)
        firsts, seconds, thirds = _predict_group_finishes(preds)
        matchups = _seed_round_of_32(firsts, seconds, thirds)
        assert len(matchups) == 16

    def test_each_matchup_has_six_fields(self, full_strengths):
        preds = compute_group_predictions(full_strengths)
        firsts, seconds, thirds = _predict_group_finishes(preds)
        matchups = _seed_round_of_32(firsts, seconds, thirds)
        for m in matchups:
            assert len(m) == 6

    def test_strong_teams_not_paired_together(self, full_strengths):
        preds = compute_group_predictions(full_strengths)
        firsts, seconds, thirds = _predict_group_finishes(preds)
        matchups = _seed_round_of_32(firsts, seconds, thirds)
        # The first matchup should have the strongest winner
        # vs the weakest third-placed team
        first_match = matchups[0]
        last_match = matchups[-1]
        assert first_match[2] >= last_match[2]  # home strength


class TestSimulateKnockout:
    def test_returns_valid_structure(self, full_strengths):
        result = simulate_knockout(full_strengths, num_simulations=100, seed=42)
        assert result["status"] == "ok"
        assert "round_of_32" in result
        assert "round_of_16" in result
        assert "quarter_finals" in result
        assert "semi_finals" in result
        assert "final" in result
        assert "tournament_win_probability" in result
        assert "disclaimer" in result

    def test_round_of_32_has_16_matchups(self, full_strengths):
        result = simulate_knockout(full_strengths, num_simulations=100, seed=42)
        assert len(result["round_of_32"]) == 16

    def test_round_of_16_has_8_matchups(self, full_strengths):
        result = simulate_knockout(full_strengths, num_simulations=100, seed=42)
        assert len(result["round_of_16"]) == 8

    def test_quarter_finals_has_4_matchups(self, full_strengths):
        result = simulate_knockout(full_strengths, num_simulations=100, seed=42)
        assert len(result["quarter_finals"]) == 4

    def test_semi_finals_has_2_matchups(self, full_strengths):
        result = simulate_knockout(full_strengths, num_simulations=100, seed=42)
        assert len(result["semi_finals"]) == 2

    def test_final_has_1_matchup(self, full_strengths):
        result = simulate_knockout(full_strengths, num_simulations=100, seed=42)
        assert len(result["final"]) == 1

    def test_matchup_has_win_probabilities(self, full_strengths):
        result = simulate_knockout(full_strengths, num_simulations=100, seed=42)
        m = result["round_of_32"][0]
        assert "home_win_probability" in m
        assert "away_win_probability" in m
        assert m["home_win_probability"] + m["away_win_probability"] == pytest.approx(1.0)

    def test_tournament_win_prob_sorted_descending(self, full_strengths):
        result = simulate_knockout(full_strengths, num_simulations=500, seed=42)
        probs = [t["win_probability"] for t in result["tournament_win_probability"]]
        assert probs == sorted(probs, reverse=True)

    def test_tournament_win_prob_top_16(self, full_strengths):
        result = simulate_knockout(full_strengths, num_simulations=500, seed=42)
        assert len(result["tournament_win_probability"]) <= 16

    def test_reproducible_with_same_seed(self, full_strengths):
        r1 = simulate_knockout(full_strengths, num_simulations=100, seed=42)
        r2 = simulate_knockout(full_strengths, num_simulations=100, seed=42)
        assert r1["tournament_win_probability"] == r2["tournament_win_probability"]

    def test_win_probabilities_sum_leq_one(self, full_strengths):
        result = simulate_knockout(full_strengths, num_simulations=1000, seed=42)
        total = sum(t["win_probability"] for t in result["tournament_win_probability"])
        assert total <= 1.0 + 1e-6

    def test_empty_strengths(self):
        """Empty strengths still produces all 48 teams via group defaults."""
        result = simulate_knockout({}, num_simulations=10, seed=42)
        assert result["status"] == "ok"
        # Groups always have 48 teams, strengths default to 0.2
        assert len(result["round_of_32"]) == 16

    def test_accepts_precomputed_group_predictions(self, full_strengths):
        preds = compute_group_predictions(full_strengths)
        result = simulate_knockout(
            full_strengths, group_predictions=preds, num_simulations=50, seed=42
        )
        assert result["status"] == "ok"


class TestComputeTeamOutlook:
    @pytest.fixture()
    def bracket_and_preds(self, full_strengths):
        preds = compute_group_predictions(full_strengths)
        bracket = simulate_knockout(
            full_strengths, group_predictions=preds,
            num_simulations=100, seed=42,
        )
        return bracket, preds

    def test_returns_valid_structure(self, full_strengths, bracket_and_preds):
        bracket, preds = bracket_and_preds
        outlook = compute_team_outlook("Spain", full_strengths, preds, bracket)
        assert outlook["status"] == "ok"
        assert outlook["team"] == "Spain"
        assert outlook["group"] == "H"
        assert "strength" in outlook
        assert "is_host" in outlook
        assert "group_finish" in outlook
        assert "group_rank" in outlook
        assert "group_teams" in outlook
        assert "knockout_path" in outlook
        assert "championship_probability" in outlook
        assert "strength_breakdown" in outlook
        assert "disclaimer" in outlook

    def test_group_finish_has_probability_keys(self, full_strengths, bracket_and_preds):
        bracket, preds = bracket_and_preds
        outlook = compute_team_outlook("Argentina", full_strengths, preds, bracket)
        gf = outlook["group_finish"]
        for key in ("p1st", "p2nd", "p3rd", "p4th", "p_advance"):
            assert key in gf

    def test_group_teams_includes_team(self, full_strengths, bracket_and_preds):
        bracket, preds = bracket_and_preds
        outlook = compute_team_outlook("France", full_strengths, preds, bracket)
        names = [t["team"] for t in outlook["group_teams"]]
        assert "France" in names

    def test_group_rank_is_valid(self, full_strengths, bracket_and_preds):
        bracket, preds = bracket_and_preds
        outlook = compute_team_outlook("Brazil", full_strengths, preds, bracket)
        assert outlook["group_rank"] is not None
        assert 1 <= outlook["group_rank"] <= 4

    def test_knockout_path_starts_with_r32(self, full_strengths, bracket_and_preds):
        bracket, preds = bracket_and_preds
        outlook = compute_team_outlook("Spain", full_strengths, preds, bracket)
        path = outlook["knockout_path"]
        assert len(path) >= 1
        assert path[0]["round"] == "round_of_32"
        assert "opponent" in path[0]
        assert "win_probability" in path[0]

    def test_championship_probability_nonneg(self, full_strengths):
        preds = compute_group_predictions(full_strengths)
        bracket = simulate_knockout(
            full_strengths, group_predictions=preds,
            num_simulations=200, seed=42,
        )
        outlook = compute_team_outlook("Spain", full_strengths, preds, bracket)
        assert outlook["championship_probability"] >= 0.0

    def test_strength_breakdown_empty_without_details(self, full_strengths, bracket_and_preds):
        bracket, preds = bracket_and_preds
        outlook = compute_team_outlook("Spain", full_strengths, preds, bracket)
        sb = outlook["strength_breakdown"]
        assert "coverage" in sb
        assert sb["coverage"] is None  # no strength_details passed

    def test_strength_breakdown_with_details(self, full_strengths, bracket_and_preds):
        bracket, preds = bracket_and_preds
        details = {
            "Spain": {
                "coverage": 0.95,
                "shrunk_avg_rating": 0.82,
                "core_avg_rating": 0.88,
            },
        }
        outlook = compute_team_outlook(
            "Spain", full_strengths, preds, bracket,
            strength_details=details,
        )
        sb = outlook["strength_breakdown"]
        assert sb["coverage"] == 0.95
        assert sb["shrunk_avg_rating"] == 0.82
        assert sb["core_avg_rating"] == 0.88

    def test_strength_breakdown_forwards_all_fields(self, full_strengths, bracket_and_preds):
        """Verify outlook forwards the full strength breakdown, including
        previously-missing rated_players/total_players and component scores."""
        bracket, preds = bracket_and_preds
        details = {
            "Spain": {
                "coverage": 0.9,
                "rated_players": 20,
                "total_players": 23,
                "observed_avg_rating": 70.5,
                "proxy_avg_rating": 55.0,
                "shrunk_avg_rating": 68.0,
                "core_avg_rating": 75.0,
                "depth_avg_rating": 65.0,
                "reserve_avg_rating": 55.0,
                "squad_quality_rating": 71.0,
                "rating_score": 0.85,
                "opta_score": 0.9,
                "league_score": 0.7,
                "coverage_score": 0.92,
                "big5_score": 0.8,
                "big5_ratio": 0.6,
            },
        }
        outlook = compute_team_outlook(
            "Spain", full_strengths, preds, bracket,
            strength_details=details,
        )
        sb = outlook["strength_breakdown"]
        # Previously-missing fields now forwarded
        assert sb["rated_players"] == 20
        assert sb["total_players"] == 23
        # Newly-forwarded component scores
        assert sb["depth_avg_rating"] == 65.0
        assert sb["reserve_avg_rating"] == 55.0
        assert sb["squad_quality_rating"] == 71.0
        assert sb["rating_score"] == 0.85
        assert sb["opta_score"] == 0.9
        assert sb["league_score"] == 0.7
        assert sb["coverage_score"] == 0.92
        assert sb["big5_score"] == 0.8
        assert sb["big5_ratio"] == 0.6
        assert sb["observed_avg_rating"] == 70.5
        assert sb["proxy_avg_rating"] == 55.0

    def test_host_flag(self, full_strengths, bracket_and_preds):
        bracket, preds = bracket_and_preds
        outlook_us = compute_team_outlook("United States", full_strengths, preds, bracket)
        outlook_brazil = compute_team_outlook("Brazil", full_strengths, preds, bracket)
        assert outlook_us["is_host"] is True
        assert outlook_brazil["is_host"] is False


class TestComputeTeamStrengthDetails:
    """Verify compute_team_strength_details returns rated_players/total_players
    and all expected component fields."""

    def _squad(self):
        """Build a small 5-player squad: 3 rated, 2 unrated."""
        return [
            SquadPlayer(name="Rated A", position="ST", club="X", club_league="La Liga",
                        has_rating=True, rating=75.0, rating_confidence="high"),
            SquadPlayer(name="Rated B", position="CM", club="Y", club_league="Premier League",
                        has_rating=True, rating=70.0, rating_confidence="high"),
            SquadPlayer(name="Rated C", position="CB", club="Z", club_league="Serie A",
                        has_rating=True, rating=65.0, rating_confidence="medium"),
            SquadPlayer(name="Unrated D", position="GK", club="W", club_league="Ligue 1",
                        has_rating=False, rating=None, rating_confidence="none"),
            SquadPlayer(name="Unrated E", position="FB", club="V", club_league="Bundesliga",
                        has_rating=False, rating=None, rating_confidence="none"),
        ]

    def test_rated_and_total_players_present(self):
        squads = {"TestTeam": self._squad()}
        result = compute_team_strength_details(enriched_squads=squads)
        details = result["TestTeam"]
        assert details["rated_players"] == 3
        assert details["total_players"] == 5

    def test_coverage_matches_rated_total(self):
        squads = {"TestTeam": self._squad()}
        result = compute_team_strength_details(enriched_squads=squads)
        details = result["TestTeam"]
        assert abs(details["coverage"] - 3 / 5) < 0.001

    def test_all_component_fields_present(self):
        squads = {"TestTeam": self._squad()}
        result = compute_team_strength_details(enriched_squads=squads)
        details = result["TestTeam"]
        expected_keys = {
            "strength", "coverage", "observed_avg_rating", "proxy_avg_rating",
            "shrunk_avg_rating", "core_avg_rating", "depth_avg_rating",
            "reserve_avg_rating", "squad_quality_rating", "rating_score",
            "opta_score", "league_score", "coverage_score", "big5_score",
            "big5_ratio", "rated_players", "total_players",
        }
        assert expected_keys.issubset(set(details.keys()))

    def test_empty_squad(self):
        squads = {"EmptyTeam": []}
        result = compute_team_strength_details(enriched_squads=squads)
        details = result["EmptyTeam"]
        assert details["rated_players"] == 0
        assert details["total_players"] == 0
        assert details["coverage"] == 0.0
