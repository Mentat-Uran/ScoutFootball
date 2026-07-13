"""Tests for expected-callup World Cup squad balance diagnostics."""

from __future__ import annotations

from scoutfootball.api import (
    get_wc_squad,
    get_wc_team_outlook,
    get_world_cup_match_briefing,
)
from scoutfootball.worldcup.data import SquadPlayer, compute_squad_balance


def test_balance_marks_thin_roles_without_claiming_a_confirmed_roster() -> None:
    squad = [
        SquadPlayer("Keeper", "GK", "Club", "Premier League"),
        SquadPlayer("Centre Back", "CB", "Club", "Premier League"),
        SquadPlayer("Forward", "ST", "Club", "Premier League"),
    ]

    result = compute_squad_balance(squad)

    assert result["status"] == "ok"
    assert result["scope"] == "expected_callup_snapshot"
    assert result["roles"]["GK"]["depth_status"] == "thin"
    assert result["roles"]["FB"]["depth_status"] == "missing"
    assert {flag["role"] for flag in result["planning_flags"]} >= {"GK", "FB"}
    assert "not a confirmed" in result["disclaimer"]


def test_balance_reports_rated_coverage_by_role_and_unit() -> None:
    keeper = SquadPlayer("Keeper", "GK", "Club", "Premier League")
    keeper.has_rating = True
    keeper.rating = 71.0
    result = compute_squad_balance([keeper])

    assert result["roles"]["GK"]["rated_players"] == 1
    assert result["roles"]["GK"]["rating_coverage"] == 1.0
    assert result["units"]["goalkeepers"]["avg_rating"] == 71.0


def test_squad_outlook_and_briefing_expose_same_balance_contract() -> None:
    squad = get_wc_squad("Argentina")
    outlook = get_wc_team_outlook("Argentina")
    briefing = get_world_cup_match_briefing("Argentina", "France")

    assert squad["squad_balance"]["schema"] == "scoutfootball.world-cup-squad-balance"
    assert outlook["squad_balance"]["scope"] == "expected_callup_snapshot"
    assert briefing["teams"]["home"]["squad"]["balance"]["version"] == "1.0.0"
