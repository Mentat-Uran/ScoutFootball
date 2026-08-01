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


class TestValidationFixture:
    """Test that valid schema objects can be created with expected field types."""

    def test_internal_match_field_types(self) -> None:
        m = InternalMatch(
            match_id="m1", provider_match_id="pm1",
            competition="PL", season="2526", match_date="2026-01-01",
            home_team_id="H", away_team_id="A",
        )
        assert isinstance(m.match_id, str)
        assert isinstance(m.home_score, int)
        assert isinstance(m.away_score, int)
        assert isinstance(m.status, MatchStatus)
        assert isinstance(m.source_coverage, str)

    def test_internal_event_field_types(self) -> None:
        e = InternalEvent(
            event_id="e1", provider_event_id="pe1",
            match_id="m1", team_id="T", player_id="P",
            event_type="pass", outcome="success",
            start_x=30.0, start_y=50.0,
        )
        assert isinstance(e.event_id, str)
        assert isinstance(e.player_id, str)
        assert isinstance(e.start_x, float)
        assert isinstance(e.start_y, float)
        assert isinstance(e.period, PeriodType)
        assert isinstance(e.qualifier, dict)
        assert isinstance(e.source_coverage, str)

    def test_tracking_frame_field_types(self) -> None:
        f = TrackingFrame(frame_id=1, match_id="m1")
        assert isinstance(f.frame_id, int)
        assert isinstance(f.ball_x, float)
        assert isinstance(f.ball_y, float)
        assert isinstance(f.ball_z, float)
        assert isinstance(f.home_possession, bool)
        assert isinstance(f.players, tuple)
        assert isinstance(f.source_coverage, str)

    def test_internal_lineup_field_types(self) -> None:
        lineup = InternalLineup(
            match_id="m1", team_id="T",
            formation="4-3-3",
            starting_players=["p1", "p2"],
            substitutes=["p3"],
        )
        assert isinstance(lineup.match_id, str)
        assert isinstance(lineup.formation, str)
        assert isinstance(lineup.starting_players, list)
        assert isinstance(lineup.substitutes, list)


class TestEmptyDataBehavior:
    """Test that objects tolerate empty/missing placeholder values."""

    def test_event_empty_player_id(self) -> None:
        e = InternalEvent(
            event_id="e1", provider_event_id="pe1",
            match_id="m1", team_id="T", player_id="",
            event_type="substitution",
        )
        assert e.player_id == ""

    def test_event_default_coordinates(self) -> None:
        e = InternalEvent(
            event_id="e1", provider_event_id="pe1",
            match_id="m1", team_id="T", player_id="P",
        )
        assert e.start_x == 50.0
        assert e.start_y == 50.0
        assert e.end_x == 50.0
        assert e.end_y == 50.0

    def test_event_missing_qualifier_defaults_empty_dict(self) -> None:
        e = InternalEvent(
            event_id="e1", provider_event_id="pe1",
            match_id="m1", team_id="T", player_id="P",
        )
        assert e.qualifier == {}

    def test_frame_empty_players(self) -> None:
        f = TrackingFrame(frame_id=1, match_id="m1")
        assert f.players == ()

    def test_lineup_empty_formation(self) -> None:
        lineup = InternalLineup(match_id="m1", team_id="T")
        assert lineup.formation == ""
        assert lineup.starting_players == []
        assert lineup.substitutes == []

    def test_match_empty_venue_referee(self) -> None:
        m = InternalMatch(
            match_id="m1", provider_match_id="pm1",
            competition="PL", season="2526", match_date="2026-01-01",
            home_team_id="H", away_team_id="A",
        )
        assert m.venue == ""
        assert m.referee == ""


class TestSourceCoverage:
    """Test source_coverage field accepts valid values and defaults are correct."""

    @pytest.mark.parametrize("coverage", ["full", "sample", "partial"])
    def test_internal_match_source_coverage_values(self, coverage: str) -> None:
        m = InternalMatch(
            match_id="m1", provider_match_id="pm1",
            competition="PL", season="2526", match_date="2026-01-01",
            home_team_id="H", away_team_id="A",
            source_coverage=coverage,
        )
        assert m.source_coverage == coverage

    @pytest.mark.parametrize("coverage", ["full", "sample", "partial"])
    def test_internal_event_source_coverage_values(self, coverage: str) -> None:
        e = InternalEvent(
            event_id="e1", provider_event_id="pe1",
            match_id="m1", team_id="T", player_id="P",
            source_coverage=coverage,
        )
        assert e.source_coverage == coverage

    @pytest.mark.parametrize("coverage", ["full", "sample", "partial"])
    def test_tracking_frame_source_coverage_values(self, coverage: str) -> None:
        f = TrackingFrame(frame_id=1, match_id="m1", source_coverage=coverage)
        assert f.source_coverage == coverage

    def test_match_default_source_coverage(self) -> None:
        m = InternalMatch(
            match_id="m1", provider_match_id="pm1",
            competition="PL", season="2526", match_date="2026-01-01",
            home_team_id="H", away_team_id="A",
        )
        assert m.source_coverage == "full"

    def test_event_default_source_coverage(self) -> None:
        e = InternalEvent(
            event_id="e1", provider_event_id="pe1",
            match_id="m1", team_id="T", player_id="P",
        )
        assert e.source_coverage == "full"

    def test_frame_default_source_coverage(self) -> None:
        f = TrackingFrame(frame_id=1, match_id="m1")
        assert f.source_coverage == "sample"


class TestCoordinateRange:
    """Test that coordinates accept boundary values 0.0 and 100.0."""

    def test_event_zero_coordinates(self) -> None:
        e = InternalEvent(
            event_id="e1", provider_event_id="pe1",
            match_id="m1", team_id="T", player_id="P",
            start_x=0.0, start_y=0.0, end_x=0.0, end_y=0.0,
        )
        assert e.start_x == 0.0
        assert e.start_y == 0.0
        assert e.end_x == 0.0
        assert e.end_y == 0.0

    def test_event_hundred_coordinates(self) -> None:
        e = InternalEvent(
            event_id="e1", provider_event_id="pe1",
            match_id="m1", team_id="T", player_id="P",
            start_x=100.0, start_y=100.0, end_x=100.0, end_y=100.0,
        )
        assert e.start_x == 100.0
        assert e.start_y == 100.0
        assert e.end_x == 100.0
        assert e.end_y == 100.0

    def test_frame_zero_ball_coordinates(self) -> None:
        f = TrackingFrame(frame_id=1, match_id="m1", ball_x=0.0, ball_y=0.0)
        assert f.ball_x == 0.0
        assert f.ball_y == 0.0

    def test_frame_hundred_ball_coordinates(self) -> None:
        f = TrackingFrame(frame_id=1, match_id="m1", ball_x=100.0, ball_y=100.0)
        assert f.ball_x == 100.0
        assert f.ball_y == 100.0


class TestFrozenDataclass:
    """Verify frozen/non-frozen behavior of schema dataclasses."""

    def test_internal_match_frozen(self) -> None:
        m = InternalMatch(
            match_id="m1", provider_match_id="pm1",
            competition="PL", season="2526", match_date="2026-01-01",
            home_team_id="H", away_team_id="A",
        )
        with pytest.raises(AttributeError):
            m.home_score = 99  # type: ignore[misc]

    def test_internal_event_frozen(self) -> None:
        e = InternalEvent(
            event_id="e1", provider_event_id="pe1",
            match_id="m1", team_id="T", player_id="P",
        )
        with pytest.raises(AttributeError):
            e.event_type = "shot"  # type: ignore[misc]

    def test_tracking_frame_frozen(self) -> None:
        f = TrackingFrame(frame_id=1, match_id="m1")
        with pytest.raises(AttributeError):
            f.ball_x = 99.0  # type: ignore[misc]

    def test_internal_lineup_not_frozen(self) -> None:
        lineup = InternalLineup(match_id="m1", team_id="T", formation="4-4-2")
        lineup.formation = "3-5-2"
        assert lineup.formation == "3-5-2"
        lineup.starting_players.append("p1")
        assert lineup.starting_players == ["p1"]
