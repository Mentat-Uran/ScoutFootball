"""Tests for the league season projection and form analysis module.

Covers ``compute_league_form_table``, ``compute_fixture_difficulty`` and
``compute_season_projection`` in ``scoutfootball.features.season_projection``.
The fixtures use synthetic pandas frames that mirror the
``combined_results.parquet`` schema so the helpers can be exercised without
loading disk artifacts.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scoutfootball.features.season_projection import (
    _DEFAULT_LAST_N,
    _DEFAULT_NUM_SIMULATIONS,
    _DEFAULT_RELEGATION_SLOTS,
    _DEFAULT_TOP_N,
    _MAX_LAST_N,
    _MAX_SIMULATIONS,
    _MAX_UPCOMING_N,
    _MIN_SIMULATIONS,
    compute_fixture_difficulty,
    compute_league_form_table,
    compute_season_projection,
)

# ---------------------------------------------------------------------------
# Synthetic fixtures
# ---------------------------------------------------------------------------


def _build_synthetic_results() -> pd.DataFrame:
    """Build a synthetic 4-team single round-robin results frame.

    Teams: Alpha, Beta, Gamma, Delta
    Season: 2526, League: Test League
    Each pair meets once (6 matches total). Alpha wins all, Delta loses all.
    """
    rows: list[dict] = [
        # Alpha dominant, Delta weak
        {
            "Date": "2025-08-10", "HomeTeam": "Alpha", "AwayTeam": "Beta",
            "FTHG": 3, "FTAG": 0, "league": "Test League", "season": "2526",
        },
        {
            "Date": "2025-08-17", "HomeTeam": "Gamma", "AwayTeam": "Delta",
            "FTHG": 2, "FTAG": 0, "league": "Test League", "season": "2526",
        },
        {
            "Date": "2025-08-24", "HomeTeam": "Alpha", "AwayTeam": "Gamma",
            "FTHG": 2, "FTAG": 1, "league": "Test League", "season": "2526",
        },
        {
            "Date": "2025-08-31", "HomeTeam": "Beta", "AwayTeam": "Delta",
            "FTHG": 1, "FTAG": 0, "league": "Test League", "season": "2526",
        },
        {
            "Date": "2025-09-07", "HomeTeam": "Beta", "AwayTeam": "Gamma",
            "FTHG": 0, "FTAG": 0, "league": "Test League", "season": "2526",
        },
        {
            "Date": "2025-09-14", "HomeTeam": "Alpha", "AwayTeam": "Delta",
            "FTHG": 4, "FTAG": 0, "league": "Test League", "season": "2526",
        },
    ]
    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"])
    return df


def _build_synthetic_results_two_seasons() -> pd.DataFrame:
    """Build a synthetic frame spanning 2 seasons to test season filtering."""
    df = _build_synthetic_results()
    other = df.copy()
    other["season"] = "2425"
    other["Date"] = other["Date"] - pd.Timedelta(days=365)
    return pd.concat([df, other], ignore_index=True)


# ---------------------------------------------------------------------------
# compute_league_form_table
# ---------------------------------------------------------------------------

_FORM_TEAM_KEYS = {
    "team",
    "ppg",
    "form_rating",
    "trend_label",
    "home_ppg",
    "away_ppg",
    "form_string",
    "played",
}


class TestComputeLeagueFormTable:
    """compute_league_form_table builds a last-N form table for a league-season."""

    def test_returns_ok_status_with_synthetic_data(self) -> None:
        df = _build_synthetic_results()
        result = compute_league_form_table(df, league="Test League", season="2526", last_n=6)
        assert result["status"] == "ok"
        assert result["league"] == "Test League"
        assert result["season"] == "2526"
        assert result["last_n"] == 6
        assert isinstance(result["teams"], list)
        assert len(result["teams"]) == 4

    def test_teams_sorted_by_ppg_descending(self) -> None:
        df = _build_synthetic_results()
        result = compute_league_form_table(df, league="Test League", season="2526", last_n=6)
        ppgs = [t["ppg"] for t in result["teams"]]
        assert ppgs == sorted(ppgs, reverse=True)
        # Alpha wins all 3 matches -> 9 points / 3 = 3.0 PPG
        assert result["teams"][0]["team"] == "Alpha"
        assert result["teams"][0]["ppg"] == pytest.approx(3.0, abs=0.01)

    def test_team_dict_has_required_keys(self) -> None:
        df = _build_synthetic_results()
        result = compute_league_form_table(df, league="Test League", season="2526", last_n=6)
        for team in result["teams"]:
            assert _FORM_TEAM_KEYS.issubset(team.keys())
            assert isinstance(team["form_string"], str)
            assert isinstance(team["played"], int)
            assert team["trend_label"] in {
                "rising", "declining", "stable", "insufficient", "no_data"
            }

    def test_empty_dataframe_returns_no_data(self) -> None:
        result = compute_league_form_table(pd.DataFrame(), league="Test League", season="2526")
        assert result["status"] == "no_data"
        assert result["teams"] == []

    def test_none_dataframe_returns_no_data(self) -> None:
        result = compute_league_form_table(None, league="Test League", season="2526")
        assert result["status"] == "no_data"
        assert result["teams"] == []

    def test_wrong_season_returns_no_data(self) -> None:
        df = _build_synthetic_results()
        result = compute_league_form_table(df, league="Test League", season="9999")
        assert result["status"] == "no_data"
        assert result["teams"] == []

    def test_wrong_league_returns_no_data(self) -> None:
        df = _build_synthetic_results()
        result = compute_league_form_table(df, league="Nonexistent League", season="2526")
        assert result["status"] == "no_data"
        assert result["teams"] == []

    def test_season_filter_isolates_correct_season(self) -> None:
        df = _build_synthetic_results_two_seasons()
        result_2526 = compute_league_form_table(df, league="Test League", season="2526", last_n=6)
        result_2425 = compute_league_form_table(df, league="Test League", season="2425", last_n=6)
        assert result_2526["status"] == "ok"
        assert result_2425["status"] == "ok"
        # Both seasons have the same teams
        assert len(result_2526["teams"]) == 4
        assert len(result_2425["teams"]) == 4

    def test_last_n_clamped_to_max(self) -> None:
        df = _build_synthetic_results()
        result = compute_league_form_table(df, league="Test League", season="2526", last_n=999)
        assert result["last_n"] == _MAX_LAST_N

    def test_last_n_clamped_to_min(self) -> None:
        df = _build_synthetic_results()
        result = compute_league_form_table(df, league="Test League", season="2526", last_n=0)
        assert result["last_n"] == 1

    def test_default_last_n_value(self) -> None:
        df = _build_synthetic_results()
        result = compute_league_form_table(df, league="Test League", season="2526")
        assert result["last_n"] == _DEFAULT_LAST_N

    def test_does_not_mutate_input(self) -> None:
        df = _build_synthetic_results()
        df_copy = df.copy(deep=True)
        compute_league_form_table(df, league="Test League", season="2526", last_n=6)
        pd.testing.assert_frame_equal(df, df_copy)

    def test_disclaimer_present(self) -> None:
        df = _build_synthetic_results()
        result = compute_league_form_table(df, league="Test League", season="2526", last_n=6)
        assert "disclaimer" in result
        assert isinstance(result["disclaimer"], str)
        assert len(result["disclaimer"]) > 0


class TestFormMatches:
    """compute_league_form_table exposes per-match details via form_matches."""

    def test_form_matches_present_in_team_dict(self) -> None:
        df = _build_synthetic_results()
        result = compute_league_form_table(df, league="Test League", season="2526", last_n=6)
        for team in result["teams"]:
            assert "form_matches" in team
            assert isinstance(team["form_matches"], list)

    def test_form_matches_length_matches_played(self) -> None:
        df = _build_synthetic_results()
        result = compute_league_form_table(df, league="Test League", season="2526", last_n=6)
        for team in result["teams"]:
            assert len(team["form_matches"]) == team["played"]

    def test_form_matches_entry_has_required_keys(self) -> None:
        df = _build_synthetic_results()
        result = compute_league_form_table(df, league="Test League", season="2526", last_n=6)
        required = {"result", "opponent", "venue", "goals_for", "goals_against", "date", "points"}
        for team in result["teams"]:
            for m in team["form_matches"]:
                assert required.issubset(m.keys())

    def test_form_matches_most_recent_first(self) -> None:
        df = _build_synthetic_results()
        result = compute_league_form_table(df, league="Test League", season="2526", last_n=6)
        alpha = next(t for t in result["teams"] if t["team"] == "Alpha")
        # Alpha's most recent match is 2025-09-14 vs Delta
        assert alpha["form_matches"][0]["opponent"] == "Delta"
        assert alpha["form_matches"][0]["date"] is not None
        assert str(alpha["form_matches"][0]["date"]).startswith("2025-09-14")

    def test_form_matches_result_matches_form_string(self) -> None:
        df = _build_synthetic_results()
        result = compute_league_form_table(df, league="Test League", season="2526", last_n=6)
        for team in result["teams"]:
            joined = "".join(m["result"] for m in team["form_matches"])
            assert joined == team["form_string"]

    def test_form_matches_alpha_all_wins(self) -> None:
        df = _build_synthetic_results()
        result = compute_league_form_table(df, league="Test League", season="2526", last_n=6)
        alpha = next(t for t in result["teams"] if t["team"] == "Alpha")
        assert len(alpha["form_matches"]) == 3
        for m in alpha["form_matches"]:
            assert m["result"] == "W"
            assert m["points"] == 3
        opponents = [m["opponent"] for m in alpha["form_matches"]]
        assert "Beta" in opponents
        assert "Gamma" in opponents
        assert "Delta" in opponents

    def test_form_matches_venue_correct(self) -> None:
        df = _build_synthetic_results()
        result = compute_league_form_table(df, league="Test League", season="2526", last_n=6)
        alpha = next(t for t in result["teams"] if t["team"] == "Alpha")
        # All Alpha's matches in the synthetic data are at home
        for m in alpha["form_matches"]:
            assert m["venue"] == "H"

    def test_form_matches_venue_away_for_away_team(self) -> None:
        df = _build_synthetic_results()
        result = compute_league_form_table(df, league="Test League", season="2526", last_n=6)
        beta = next(t for t in result["teams"] if t["team"] == "Beta")
        # Beta vs Alpha (2025-08-10) was away
        alpha_match = next(m for m in beta["form_matches"] if m["opponent"] == "Alpha")
        assert alpha_match["venue"] == "A"
        assert alpha_match["result"] == "L"
        assert alpha_match["points"] == 0

    def test_form_matches_goals_correct(self) -> None:
        df = _build_synthetic_results()
        result = compute_league_form_table(df, league="Test League", season="2526", last_n=6)
        alpha = next(t for t in result["teams"] if t["team"] == "Alpha")
        # Alpha 3-0 Beta, 2-1 Gamma, 4-0 Delta
        beta_match = next(m for m in alpha["form_matches"] if m["opponent"] == "Beta")
        assert beta_match["goals_for"] == 3
        assert beta_match["goals_against"] == 0
        gamma_match = next(m for m in alpha["form_matches"] if m["opponent"] == "Gamma")
        assert gamma_match["goals_for"] == 2
        assert gamma_match["goals_against"] == 1
        delta_match = next(m for m in alpha["form_matches"] if m["opponent"] == "Delta")
        assert delta_match["goals_for"] == 4
        assert delta_match["goals_against"] == 0

    def test_form_matches_draw_has_correct_points(self) -> None:
        df = _build_synthetic_results()
        result = compute_league_form_table(df, league="Test League", season="2526", last_n=6)
        # Beta 0-0 Gamma was a draw
        beta = next(t for t in result["teams"] if t["team"] == "Beta")
        gamma_match = next(m for m in beta["form_matches"] if m["opponent"] == "Gamma")
        assert gamma_match["result"] == "D"
        assert gamma_match["points"] == 1
        assert gamma_match["goals_for"] == 0
        assert gamma_match["goals_against"] == 0

    def test_form_matches_date_is_string_or_none(self) -> None:
        df = _build_synthetic_results()
        result = compute_league_form_table(df, league="Test League", season="2526", last_n=6)
        for team in result["teams"]:
            for m in team["form_matches"]:
                assert m["date"] is None or isinstance(m["date"], str)

    def test_form_matches_respects_last_n(self) -> None:
        df = _build_synthetic_results()
        result = compute_league_form_table(df, league="Test League", season="2526", last_n=2)
        for team in result["teams"]:
            assert len(team["form_matches"]) <= 2
            assert team["played"] <= 2

    def test_form_matches_no_data_status_empty(self) -> None:
        result = compute_league_form_table(pd.DataFrame(), league="Test League", season="2526")
        assert result["status"] == "no_data"
        assert result["teams"] == []

    def test_form_matches_entry_types(self) -> None:
        df = _build_synthetic_results()
        result = compute_league_form_table(df, league="Test League", season="2526", last_n=6)
        for team in result["teams"]:
            for m in team["form_matches"]:
                assert isinstance(m["result"], str)
                assert isinstance(m["opponent"], str)
                assert isinstance(m["venue"], str)
                assert isinstance(m["goals_for"], int)
                assert isinstance(m["goals_against"], int)
                assert isinstance(m["points"], int)


# ---------------------------------------------------------------------------
# compute_fixture_difficulty
# ---------------------------------------------------------------------------


class TestComputeFixtureDifficulty:
    """compute_fixture_difficulty rates each team's recent N fixtures."""

    def test_returns_ok_status_with_team_filter(self) -> None:
        df = _build_synthetic_results()
        result = compute_fixture_difficulty(
            df, league="Test League", season="2526", team="Alpha", upcoming_n=10
        )
        assert result["status"] == "ok"
        assert result["team"] == "Alpha"
        assert isinstance(result["teams"], list)
        assert len(result["teams"]) == 1

    def test_returns_all_teams_without_team_filter(self) -> None:
        df = _build_synthetic_results()
        result = compute_fixture_difficulty(
            df, league="Test League", season="2526", team=None, upcoming_n=10
        )
        assert result["status"] == "ok"
        assert len(result["teams"]) == 4

    def test_fixture_dict_has_required_keys(self) -> None:
        df = _build_synthetic_results()
        result = compute_fixture_difficulty(
            df, league="Test League", season="2526", team="Alpha", upcoming_n=10
        )
        fixture_keys = {
            "date", "opponent", "venue", "expected_points",
            "difficulty_score", "difficulty_label",
        }
        for team_entry in result["teams"]:
            assert "team" in team_entry
            assert isinstance(team_entry["fixtures"], list)
            for fixture in team_entry["fixtures"]:
                assert fixture_keys.issubset(fixture.keys())
                assert fixture["venue"] in {"H", "A"}
                assert fixture["difficulty_label"] in {
                    "very_hard", "hard", "moderate", "easy", "very_easy"
                }
                assert 0 <= fixture["difficulty_score"] <= 100
                assert 0 <= fixture["expected_points"] <= 3

    def test_empty_dataframe_returns_no_data(self) -> None:
        result = compute_fixture_difficulty(
            pd.DataFrame(), league="Test League", season="2526", team="Alpha"
        )
        assert result["status"] == "no_data"
        assert result["teams"] == []

    def test_none_dataframe_returns_no_data(self) -> None:
        result = compute_fixture_difficulty(None, league="Test League", season="2526", team="Alpha")
        assert result["status"] == "no_data"
        assert result["teams"] == []

    def test_wrong_team_returns_no_data(self) -> None:
        df = _build_synthetic_results()
        result = compute_fixture_difficulty(
            df, league="Test League", season="2526", team="Nonexistent Team"
        )
        # Module distinguishes "no data at all" from "team not found in existing data"
        assert result["status"] in {"no_data", "team_not_found"}

    def test_upcoming_n_clamped_to_max(self) -> None:
        df = _build_synthetic_results()
        result = compute_fixture_difficulty(
            df, league="Test League", season="2526", team="Alpha", upcoming_n=999
        )
        assert result["upcoming_n"] == _MAX_UPCOMING_N

    def test_upcoming_n_clamped_to_min(self) -> None:
        df = _build_synthetic_results()
        result = compute_fixture_difficulty(
            df, league="Test League", season="2526", team="Alpha", upcoming_n=0
        )
        assert result["upcoming_n"] == 1

    def test_does_not_mutate_input(self) -> None:
        df = _build_synthetic_results()
        df_copy = df.copy(deep=True)
        compute_fixture_difficulty(
            df, league="Test League", season="2526", team="Alpha", upcoming_n=10
        )
        pd.testing.assert_frame_equal(df, df_copy)

    def test_custom_team_strengths_used(self) -> None:
        df = _build_synthetic_results()
        # Alpha super strong, Delta super weak
        strengths = {"Alpha": 5.0, "Beta": 1.0, "Gamma": 1.0, "Delta": -5.0}
        result = compute_fixture_difficulty(
            df,
            league="Test League",
            season="2526",
            team="Delta",
            upcoming_n=10,
            team_strengths=strengths,
        )
        assert result["status"] == "ok"
        # Delta's fixtures should be mostly very_hard
        for team_entry in result["teams"]:
            for fixture in team_entry["fixtures"]:
                # Delta is very weak, so all fixtures should be hard
                assert fixture["difficulty_label"] in {"very_hard", "hard", "moderate"}


# ---------------------------------------------------------------------------
# compute_season_projection
# ---------------------------------------------------------------------------


_PROJECTION_TEAM_KEYS = {
    "team",
    "avg_final_points",
    "avg_position",
    "title_probability",
    "top_n_probability",
    "relegation_probability",
    "position_distribution",
}


class TestComputeSeasonProjection:
    """compute_season_projection runs Monte Carlo on remaining fixtures."""

    def test_returns_ok_status_with_synthetic_data(self) -> None:
        df = _build_synthetic_results()
        result = compute_season_projection(
            df,
            league="Test League",
            season="2526",
            num_simulations=200,
            random_seed=42,
        )
        assert result["status"] == "ok"
        assert result["league"] == "Test League"
        assert result["season"] == "2526"
        assert isinstance(result["teams"], list)
        assert len(result["teams"]) == 4

    def test_teams_sorted_by_avg_position_ascending(self) -> None:
        df = _build_synthetic_results()
        result = compute_season_projection(
            df, league="Test League", season="2526", num_simulations=200, random_seed=42
        )
        # Teams are sorted by (avg_position, avg_final_points, team) ascending
        positions = [t["avg_position"] for t in result["teams"]]
        assert positions == sorted(positions)
        # Alpha should be #1 (won all 3 in first half) → best avg_position
        assert result["teams"][0]["team"] == "Alpha"

    def test_team_dict_has_required_keys(self) -> None:
        df = _build_synthetic_results()
        result = compute_season_projection(
            df, league="Test League", season="2526", num_simulations=200, random_seed=42
        )
        for team in result["teams"]:
            assert _PROJECTION_TEAM_KEYS.issubset(team.keys())
            assert 0.0 <= team["title_probability"] <= 1.0
            assert 0.0 <= team["top_n_probability"] <= 1.0
            assert 0.0 <= team["relegation_probability"] <= 1.0
            assert isinstance(team["position_distribution"], list)
            assert len(team["position_distribution"]) >= 1
            # Each distribution entry has position, count, probability
            for entry in team["position_distribution"]:
                assert "position" in entry
                assert "count" in entry
                assert "probability" in entry
                assert 0.0 <= entry["probability"] <= 1.0

    def test_probabilities_sum_to_one_across_teams(self) -> None:
        df = _build_synthetic_results()
        result = compute_season_projection(
            df, league="Test League", season="2526", num_simulations=500, random_seed=42
        )
        total_title = sum(t["title_probability"] for t in result["teams"])
        assert total_title == pytest.approx(1.0, abs=0.01)

    def test_deterministic_with_same_seed(self) -> None:
        df = _build_synthetic_results()
        result1 = compute_season_projection(
            df, league="Test League", season="2526", num_simulations=200, random_seed=42
        )
        result2 = compute_season_projection(
            df, league="Test League", season="2526", num_simulations=200, random_seed=42
        )
        # Same seed -> same avg points
        for t1, t2 in zip(result1["teams"], result2["teams"], strict=True):
            assert t1["team"] == t2["team"]
            assert t1["avg_final_points"] == pytest.approx(t2["avg_final_points"], abs=0.001)
            assert t1["title_probability"] == pytest.approx(t2["title_probability"], abs=0.001)

    def test_different_seed_may_produce_different_results(self) -> None:
        df = _build_synthetic_results()
        result1 = compute_season_projection(
            df, league="Test League", season="2526", num_simulations=200, random_seed=1
        )
        result2 = compute_season_projection(
            df, league="Test League", season="2526", num_simulations=200, random_seed=999
        )
        # Different seeds should produce somewhat different results (not guaranteed
        # but very likely with only 4 teams and 200 sims)
        points1 = [t["avg_final_points"] for t in result1["teams"]]
        points2 = [t["avg_final_points"] for t in result2["teams"]]
        # At least one value should differ
        assert any(abs(p1 - p2) > 0.01 for p1, p2 in zip(points1, points2, strict=True))

    def test_empty_dataframe_returns_no_data(self) -> None:
        result = compute_season_projection(
            pd.DataFrame(), league="Test League", season="2526", num_simulations=200
        )
        assert result["status"] == "no_data"
        assert result["teams"] == []

    def test_none_dataframe_returns_no_data(self) -> None:
        result = compute_season_projection(
            None, league="Test League", season="2526", num_simulations=200
        )
        assert result["status"] == "no_data"
        assert result["teams"] == []

    def test_wrong_season_returns_no_data(self) -> None:
        df = _build_synthetic_results()
        result = compute_season_projection(
            df, league="Test League", season="9999", num_simulations=200
        )
        assert result["status"] == "no_data"

    def test_num_simulations_clamped_to_min(self) -> None:
        df = _build_synthetic_results()
        result = compute_season_projection(
            df, league="Test League", season="2526", num_simulations=1
        )
        # Should be clamped up to _MIN_SIMULATIONS
        assert result["num_simulations"] == _MIN_SIMULATIONS

    def test_num_simulations_clamped_to_max(self) -> None:
        df = _build_synthetic_results()
        result = compute_season_projection(
            df, league="Test League", season="2526", num_simulations=999999
        )
        assert result["num_simulations"] == _MAX_SIMULATIONS

    def test_default_num_simulations_value(self) -> None:
        df = _build_synthetic_results()
        result = compute_season_projection(df, league="Test League", season="2526")
        assert result["num_simulations"] == _DEFAULT_NUM_SIMULATIONS

    def test_default_top_n_and_relegation_slots(self) -> None:
        df = _build_synthetic_results()
        result = compute_season_projection(
            df, league="Test League", season="2526", num_simulations=200
        )
        assert result["top_n"] == _DEFAULT_TOP_N
        assert result["relegation_slots"] == _DEFAULT_RELEGATION_SLOTS

    def test_custom_top_n(self) -> None:
        df = _build_synthetic_results()
        result = compute_season_projection(
            df, league="Test League", season="2526", num_simulations=200, top_n=2
        )
        assert result["top_n"] == 2

    def test_custom_relegation_slots(self) -> None:
        df = _build_synthetic_results()
        result = compute_season_projection(
            df, league="Test League", season="2526", num_simulations=200, relegation_slots=1
        )
        assert result["relegation_slots"] == 1

    def test_does_not_mutate_input(self) -> None:
        df = _build_synthetic_results()
        df_copy = df.copy(deep=True)
        compute_season_projection(
            df, league="Test League", season="2526", num_simulations=100, random_seed=42
        )
        pd.testing.assert_frame_equal(df, df_copy)

    def test_disclaimer_present(self) -> None:
        df = _build_synthetic_results()
        result = compute_season_projection(
            df, league="Test League", season="2526", num_simulations=100
        )
        assert "disclaimer" in result
        assert isinstance(result["disclaimer"], str)
        assert len(result["disclaimer"]) > 0

    def test_relegation_slots_zero_allowed(self) -> None:
        df = _build_synthetic_results()
        result = compute_season_projection(
            df, league="Test League", season="2526", num_simulations=100, relegation_slots=0
        )
        assert result["status"] == "ok"
        # With 0 relegation slots, all teams should have 0 relegation probability
        for team in result["teams"]:
            assert team["relegation_probability"] == 0.0

    def test_custom_team_strengths_produce_valid_result(self) -> None:
        df = _build_synthetic_results()
        strengths = {"Alpha": 3.0, "Beta": 0.5, "Gamma": 0.5, "Delta": -3.0}
        result = compute_season_projection(
            df,
            league="Test League",
            season="2526",
            num_simulations=200,
            random_seed=42,
            team_strengths=strengths,
        )
        assert result["status"] == "ok"
        # Alpha should still win the title most often
        assert result["teams"][0]["team"] == "Alpha"
        assert result["teams"][0]["title_probability"] > 0.5


# ---------------------------------------------------------------------------
# Missing required columns
# ---------------------------------------------------------------------------


class TestMissingColumns:
    """All three functions should handle missing required columns gracefully."""

    def _df_missing_columns(self) -> pd.DataFrame:
        """Return a frame missing FTHG/FTAG columns."""
        return pd.DataFrame({
            "Date": ["2025-08-10"],
            "HomeTeam": ["Alpha"],
            "AwayTeam": ["Beta"],
            "league": ["Test League"],
            "season": ["2526"],
        })

    def test_form_table_missing_columns_returns_no_data(self) -> None:
        result = compute_league_form_table(
            self._df_missing_columns(), league="Test League", season="2526"
        )
        assert result["status"] == "no_data"

    def test_fixture_difficulty_missing_columns_returns_no_data(self) -> None:
        result = compute_fixture_difficulty(
            self._df_missing_columns(), league="Test League", season="2526", team="Alpha"
        )
        assert result["status"] == "no_data"

    def test_season_projection_missing_columns_returns_no_data(self) -> None:
        result = compute_season_projection(
            self._df_missing_columns(), league="Test League", season="2526", num_simulations=100
        )
        assert result["status"] == "no_data"
