"""Tests for match momentum prediction (in-play win probability)."""

from __future__ import annotations

import pytest

from scoutfootball.models import (
    MatchMomentum,
    MomentumPoint,
    compute_momentum,
    update_probability_at_scoreline,
)

# ---------------------------------------------------------------------------
# compute_momentum
# ---------------------------------------------------------------------------


class TestComputeMomentum:
    def test_returns_result(self) -> None:
        m = compute_momentum("TeamA", "TeamB", 1.5, 1.2)
        assert isinstance(m, MatchMomentum)

    def test_timeline_non_empty(self) -> None:
        m = compute_momentum("TeamA", "TeamB", 1.5, 1.2)
        assert len(m.timeline) > 0
        assert all(isinstance(p, MomentumPoint) for p in m.timeline)

    def test_timeline_starts_at_current_minute(self) -> None:
        m = compute_momentum("TeamA", "TeamB", 1.5, 1.2, current_minute=30)
        assert m.timeline[0].minute == 30

    def test_timeline_includes_minute_90(self) -> None:
        m = compute_momentum("TeamA", "TeamB", 1.5, 1.2)
        assert m.timeline[-1].minute == 90

    def test_probabilities_sum_to_one(self) -> None:
        m = compute_momentum("TeamA", "TeamB", 1.5, 1.2)
        for p in m.timeline[:-1]:  # skip last (minute 90, deterministic)
            total = p.home_win + p.draw + p.away_win
            assert total == pytest.approx(1.0, abs=1e-6)

    def test_probabilities_in_valid_range(self) -> None:
        m = compute_momentum("TeamA", "TeamB", 1.5, 1.2)
        for p in m.timeline:
            assert 0.0 <= p.home_win <= 1.0
            assert 0.0 <= p.draw <= 1.0
            assert 0.0 <= p.away_win <= 1.0

    def test_remaining_lambda_decreases_over_time(self) -> None:
        m = compute_momentum("TeamA", "TeamB", 1.5, 1.2)
        for i in range(1, len(m.timeline)):
            assert m.timeline[i].remaining_home_lambda <= m.timeline[i - 1].remaining_home_lambda
            assert m.timeline[i].remaining_away_lambda <= m.timeline[i - 1].remaining_away_lambda

    def test_negative_lambda_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            compute_momentum("A", "B", -1.0, 1.0)

    def test_negative_minute_raises(self) -> None:
        with pytest.raises(ValueError, match="current_minute"):
            compute_momentum("A", "B", 1.0, 1.0, current_minute=-1)

    def test_negative_goals_raises(self) -> None:
        with pytest.raises(ValueError, match="Goals"):
            compute_momentum("A", "B", 1.0, 1.0, current_home_goals=-1)

    def test_invalid_minute_step_raises(self) -> None:
        with pytest.raises(ValueError, match="minute_step"):
            compute_momentum("A", "B", 1.0, 1.0, minute_step=0)

    def test_home_lead_increases_home_win(self) -> None:
        """When home team leads, home_win should be higher than at 0-0."""
        m_level = compute_momentum("A", "B", 1.5, 1.2, current_minute=45)
        m_home_lead = compute_momentum(
            "A", "B", 1.5, 1.2,
            current_home_goals=2, current_away_goals=0, current_minute=45,
        )
        assert m_home_lead.timeline[0].home_win > m_level.timeline[0].home_win

    def test_away_lead_increases_away_win(self) -> None:
        """When away team leads, away_win should be higher than at 0-0."""
        m_level = compute_momentum("A", "B", 1.5, 1.2, current_minute=45)
        m_away_lead = compute_momentum(
            "A", "B", 1.5, 1.2,
            current_home_goals=0, current_away_goals=2, current_minute=45,
        )
        assert m_away_lead.timeline[0].away_win > m_level.timeline[0].away_win

    def test_minute_90_deterministic(self) -> None:
        """At minute 90, outcome is determined by current scoreline."""
        m = compute_momentum(
            "A", "B", 1.5, 1.2,
            current_home_goals=2, current_away_goals=1,
        )
        last = m.timeline[-1]
        assert last.minute == 90
        assert last.home_win == 1.0
        assert last.draw == 0.0
        assert last.away_win == 0.0
        assert last.remaining_home_lambda == 0.0
        assert last.remaining_away_lambda == 0.0

    def test_minute_90_draw(self) -> None:
        m = compute_momentum(
            "A", "B", 1.5, 1.2,
            current_home_goals=1, current_away_goals=1,
        )
        last = m.timeline[-1]
        assert last.draw == 1.0

    def test_minute_90_away_win(self) -> None:
        m = compute_momentum(
            "A", "B", 1.5, 1.2,
            current_home_goals=0, current_away_goals=1,
        )
        last = m.timeline[-1]
        assert last.away_win == 1.0

    def test_custom_minute_step(self) -> None:
        m = compute_momentum("A", "B", 1.5, 1.2, minute_step=10)
        minutes = [p.minute for p in m.timeline]
        assert minutes == list(range(0, 91, 10))

    def test_custom_match_duration(self) -> None:
        m = compute_momentum("A", "B", 1.5, 1.2, match_duration=120, minute_step=30)
        minutes = [p.minute for p in m.timeline]
        assert minutes == [0, 30, 60, 90, 120]

    def test_stores_team_names(self) -> None:
        m = compute_momentum("Arsenal", "Chelsea", 1.5, 1.2)
        assert m.home_team == "Arsenal"
        assert m.away_team == "Chelsea"

    def test_stores_lambdas(self) -> None:
        m = compute_momentum("A", "B", 1.5, 1.2)
        assert m.home_lambda == 1.5
        assert m.away_lambda == 1.2

    def test_stores_current_scoreline(self) -> None:
        m = compute_momentum(
            "A", "B", 1.5, 1.2,
            current_home_goals=2, current_away_goals=1, current_minute=60,
        )
        assert m.current_home_goals == 2
        assert m.current_away_goals == 1
        assert m.current_minute == 60

    def test_zero_lambda_at_full_time(self) -> None:
        m = compute_momentum("A", "B", 1.5, 1.2)
        # At minute 0, remaining lambda = full lambda
        assert m.timeline[0].remaining_home_lambda == pytest.approx(1.5)
        # At minute 90, remaining lambda = 0
        assert m.timeline[-1].remaining_home_lambda == 0.0

    def test_timeline_from_current_minute(self) -> None:
        """When current_minute=60, timeline should start at 60."""
        m = compute_momentum("A", "B", 1.5, 1.2, current_minute=60)
        assert m.timeline[0].minute == 60


# ---------------------------------------------------------------------------
# update_probability_at_scoreline
# ---------------------------------------------------------------------------


class TestUpdateProbabilityAtScoreline:
    def test_returns_tuple_of_three(self) -> None:
        result = update_probability_at_scoreline(1.5, 1.2, 0, 0, 45)
        assert len(result) == 3

    def test_probabilities_sum_to_one(self) -> None:
        hw, dw, aw = update_probability_at_scoreline(1.5, 1.2, 0, 0, 45)
        assert hw + dw + aw == pytest.approx(1.0, abs=1e-6)

    def test_minute_0_matches_full_match(self) -> None:
        """At minute 0, probabilities should be close to pre-match."""
        hw, dw, aw = update_probability_at_scoreline(1.5, 1.2, 0, 0, 0)
        # Home team has higher lambda, so home_win should be > away_win
        assert hw > aw

    def test_minute_90_determined_by_scoreline(self) -> None:
        hw, dw, aw = update_probability_at_scoreline(1.5, 1.2, 2, 0, 90)
        assert hw == 1.0
        assert dw == 0.0
        assert aw == 0.0

    def test_home_lead_favors_home(self) -> None:
        hw_level, _, _ = update_probability_at_scoreline(1.5, 1.2, 0, 0, 45)
        hw_lead, _, _ = update_probability_at_scoreline(1.5, 1.2, 2, 0, 45)
        assert hw_lead > hw_level

    def test_away_lead_favors_away(self) -> None:
        _, _, aw_level = update_probability_at_scoreline(1.5, 1.2, 0, 0, 45)
        _, _, aw_lead = update_probability_at_scoreline(1.5, 1.2, 0, 2, 45)
        assert aw_lead > aw_level

    def test_probabilities_in_valid_range(self) -> None:
        hw, dw, aw = update_probability_at_scoreline(1.5, 1.2, 1, 1, 60)
        assert 0.0 <= hw <= 1.0
        assert 0.0 <= dw <= 1.0
        assert 0.0 <= aw <= 1.0

    def test_custom_match_duration(self) -> None:
        hw, dw, aw = update_probability_at_scoreline(
            1.5, 1.2, 0, 0, 60, match_duration=120,
        )
        # At minute 60 of 120, half the match remains
        assert hw + dw + aw == pytest.approx(1.0, abs=1e-6)
