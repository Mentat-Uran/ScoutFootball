"""Tests for action_value/schema.py — InternalAction, ActionType,
ActionResult, coordinate normalization."""

from __future__ import annotations

import pytest

from scoutfootball.action_value.schema import (
    STATSBOMB_ACTION_MAP,
    ActionResult,
    ActionSequence,
    ActionType,
    InternalAction,
    normalize_coordinates,
    statsbomb_result,
)


class TestActionType:
    def test_action_type_values(self) -> None:
        assert ActionType.PASS == "pass"
        assert ActionType.SHOT == "shot"
        assert ActionType.DRIBBLE == "dribble"
        assert ActionType.TACKLE == "tackle"
        assert ActionType.INTERCEPTION == "interception"
        assert ActionType.CLEARANCE == "clearance"
        assert ActionType.BLOCK == "block"
        assert ActionType.GOALKEEPER == "goalkeeper"
        assert ActionType.RECEIPT == "receipt"
        assert ActionType.CARRY == "carry"
        assert ActionType.FREEZE == "freeze"
        assert ActionType.TAKE_ON == "take_on"
        assert ActionType.UNKNOWN == "unknown"

    def test_action_type_count(self) -> None:
        assert len(ActionType) == 13


class TestActionResult:
    def test_result_values(self) -> None:
        assert ActionResult.SUCCESS == "success"
        assert ActionResult.FAILURE == "failure"
        assert ActionResult.UNKNOWN == "unknown"

    def test_result_count(self) -> None:
        assert len(ActionResult) == 3


class TestInternalAction:
    def test_required_fields(self) -> None:
        action = InternalAction(
            action_id=1,
            provider_action_id="sb-100",
            match_id="M1",
            team_id="T1",
            player_id="P1",
            period=1,
            minute=35,
            second=12,
            action_type=ActionType.PASS,
            result=ActionResult.SUCCESS,
            start_x=50.0,
            start_y=50.0,
            end_x=70.0,
            end_y=30.0,
        )
        assert action.action_id == 1
        assert action.provider_action_id == "sb-100"
        assert action.action_type == ActionType.PASS
        assert action.result == ActionResult.SUCCESS

    def test_default_values(self) -> None:
        action = InternalAction(
            action_id=1,
            provider_action_id="x",
            match_id="M",
            team_id="T",
            player_id="P",
            period=1,
            minute=0,
            second=0,
            action_type=ActionType.UNKNOWN,
            result=ActionResult.UNKNOWN,
            start_x=0.0,
            start_y=0.0,
            end_x=0.0,
            end_y=0.0,
        )
        assert action.body_part == "foot"
        assert action.qualifier == {}
        assert action.source == "unknown"
        assert action.source_coverage == "full"

    def test_frozen(self) -> None:
        action = InternalAction(
            action_id=1,
            provider_action_id="x",
            match_id="M",
            team_id="T",
            player_id="P",
            period=1,
            minute=0,
            second=0,
            action_type=ActionType.PASS,
            result=ActionResult.SUCCESS,
            start_x=0.0,
            start_y=0.0,
            end_x=0.0,
            end_y=0.0,
        )
        with pytest.raises(AttributeError):
            action.action_id = 2  # type: ignore[misc]

    def test_qualifier_custom(self) -> None:
        action = InternalAction(
            action_id=1,
            provider_action_id="x",
            match_id="M",
            team_id="T",
            player_id="P",
            period=1,
            minute=0,
            second=0,
            action_type=ActionType.PASS,
            result=ActionResult.SUCCESS,
            start_x=0.0,
            start_y=0.0,
            end_x=0.0,
            end_y=0.0,
            qualifier={"technique": "through_ball"},
        )
        assert action.qualifier["technique"] == "through_ball"


class TestActionSequence:
    def test_sequence_defaults(self) -> None:
        seq = ActionSequence(match_id="M1", team_id="T1", actions=[])
        assert seq.start_minute == 0
        assert seq.end_minute == 0
        assert seq.outcome == "unknown"

    def test_sequence_with_actions(self) -> None:
        a = InternalAction(
            action_id=1,
            provider_action_id="x",
            match_id="M",
            team_id="T",
            player_id="P",
            period=1,
            minute=10,
            second=0,
            action_type=ActionType.PASS,
            result=ActionResult.SUCCESS,
            start_x=0.0,
            start_y=0.0,
            end_x=0.0,
            end_y=0.0,
        )
        seq = ActionSequence(
            match_id="M",
            team_id="T",
            actions=[a],
            start_minute=10,
            end_minute=10,
            outcome="goal",
        )
        assert len(seq.actions) == 1
        assert seq.outcome == "goal"


class TestStatsbombActionMap:
    def test_core_actions_mapped(self) -> None:
        assert STATSBOMB_ACTION_MAP["Pass"] == ActionType.PASS
        assert STATSBOMB_ACTION_MAP["Shot"] == ActionType.SHOT
        assert STATSBOMB_ACTION_MAP["Carry"] == ActionType.CARRY
        assert STATSBOMB_ACTION_MAP["Dribble"] == ActionType.DRIBBLE
        assert STATSBOMB_ACTION_MAP["Tackle"] == ActionType.TACKLE
        assert STATSBOMB_ACTION_MAP["Interception"] == ActionType.INTERCEPTION

    def test_freeze_actions(self) -> None:
        for key in ("Half Start", "Half End", "Starting XI", "Substitution",
                     "Injury Stoppage", "Referee Ball-Drop", "Bad Behaviour", "Offside"):
            assert STATSBOMB_ACTION_MAP[key] == ActionType.FREEZE, f"{key} should map to FREEZE"

    def test_all_mapped_types_are_valid(self) -> None:
        for key, action_type in STATSBOMB_ACTION_MAP.items():
            assert isinstance(action_type, ActionType), f"{key} maps to non-ActionType"


class TestStatsbombResult:
    def test_success_outcomes(self) -> None:
        for name in ("Complete", "Won", "Success", "Complete To Team"):
            assert statsbomb_result({"name": name}) == ActionResult.SUCCESS

    def test_failure_outcomes(self) -> None:
        for name in ("Incomplete", "Lost", "Out"):
            assert statsbomb_result({"name": name}) == ActionResult.FAILURE

    def test_unknown_outcome(self) -> None:
        assert statsbomb_result({"name": "Something Else"}) == ActionResult.UNKNOWN

    def test_none_outcome(self) -> None:
        assert statsbomb_result(None) == ActionResult.UNKNOWN

    def test_empty_dict(self) -> None:
        assert statsbomb_result({}) == ActionResult.UNKNOWN


class TestNormalizeCoordinates:
    def test_origin(self) -> None:
        x, y = normalize_coordinates(0, 0)
        assert x == pytest.approx(0.0)
        assert y == pytest.approx(0.0)

    def test_full_field(self) -> None:
        x, y = normalize_coordinates(120, 80)
        assert x == pytest.approx(100.0)
        assert y == pytest.approx(100.0)

    def test_center(self) -> None:
        x, y = normalize_coordinates(60, 40)
        assert x == pytest.approx(50.0)
        assert y == pytest.approx(50.0)

    def test_quarter_field(self) -> None:
        x, y = normalize_coordinates(30, 20)
        assert x == pytest.approx(25.0)
        assert y == pytest.approx(25.0)
