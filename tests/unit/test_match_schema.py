"""Tests for internal match/event/tracking schema validation."""

from __future__ import annotations

import pytest

from scoutfootball.schemas.match import (
    InternalEvent,
    InternalLineup,
    InternalMatch,
    MatchStatus,
    PeriodType,
    TrackingFrame,
)


class TestInternalMatchSchema:
    """Validate InternalMatch schema."""

    def test_create_minimal_match(self) -> None:
        m = InternalMatch(
            match_id="m1", provider_match_id="pm1",
            competition="PL", season="2526", match_date="2026-01-01",
            home_team_id="H", away_team_id="A",
        )
        assert m.match_id == "m1"
        assert m.status == MatchStatus.SCHEDULED
        assert m.source == "unknown"

    def test_match_status_values(self) -> None:
        assert MatchStatus.COMPLETED == "completed"
        assert MatchStatus.LIVE == "live"

    def test_match_frozen(self) -> None:
        m = InternalMatch(
            match_id="m1", provider_match_id="pm1",
            competition="PL", season="2526", match_date="2026-01-01",
            home_team_id="H", away_team_id="A",
        )
        with pytest.raises(AttributeError):
            m.home_score = 99  # type: ignore[misc]


class TestInternalEventSchema:
    """Validate InternalEvent schema."""

    def test_create_event(self) -> None:
        e = InternalEvent(
            event_id="e1", provider_event_id="pe1",
            match_id="m1", team_id="T", player_id="P",
            event_type="pass", outcome="success",
            start_x=30.0, start_y=50.0,
        )
        assert e.event_type == "pass"
        assert e.period == PeriodType.FIRST_HALF

    def test_event_coordinates_normalized(self) -> None:
        e = InternalEvent(
            event_id="e1", provider_event_id="pe1",
            match_id="m1", team_id="T", player_id="P",
            start_x=100.0, start_y=0.0, end_x=50.0, end_y=50.0,
        )
        assert 0.0 <= e.start_x <= 100.0
        assert 0.0 <= e.end_y <= 100.0


class TestTrackingFrameSchema:
    """Validate TrackingFrame schema."""

    def test_create_frame(self) -> None:
        f = TrackingFrame(frame_id=1, match_id="m1")
        assert f.ball_z == 0.0
        assert f.source_coverage == "sample"

    def test_frame_with_players(self) -> None:
        players = (
            {"player_id": "p1", "x": 30.0, "y": 50.0, "team": "home"},
            {"player_id": "p2", "x": 70.0, "y": 50.0, "team": "away"},
        )
        f = TrackingFrame(frame_id=1, match_id="m1", players=players)
        assert len(f.players) == 2


class TestInternalLineupSchema:
    """Validate InternalLineup schema."""

    def test_create_lineup(self) -> None:
        lineup = InternalLineup(
            match_id="m1", team_id="T",
            formation="4-3-3",
            starting_players=["p1", "p2"],
            substitutes=["p3"],
        )
        assert lineup.formation == "4-3-3"
        assert len(lineup.starting_players) == 2

    def test_lineup_default_empty(self) -> None:
        lineup = InternalLineup(match_id="m1", team_id="T")
        assert lineup.starting_players == []
        assert lineup.substitutes == []
