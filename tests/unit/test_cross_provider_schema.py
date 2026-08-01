"""Tests for cross-provider schema validation — InternalAction
against StatsBomb and SPADL mappings."""

from __future__ import annotations

import pytest

from scoutfootball.action_value.schema import (
    STATSBOMB_ACTION_MAP,
    ActionResult,
    ActionType,
    InternalAction,
    normalize_coordinates,
    statsbomb_result,
)
from scoutfootball.schemas.storage import build_core_table_definitions


class TestInternalActionSchemaValidation:
    """Validate that InternalAction conforms to the cross-provider contract."""

    def test_all_action_types_covered_in_schema(self) -> None:
        """Every ActionType should be representable as an InternalAction."""
        for action_type in ActionType:
            action = InternalAction(
                action_id=1,
                provider_action_id="test",
                match_id="M",
                team_id="T",
                player_id="P",
                period=1,
                minute=0,
                second=0,
                action_type=action_type,
                result=ActionResult.UNKNOWN,
                start_x=50.0,
                start_y=50.0,
                end_x=50.0,
                end_y=50.0,
            )
            assert action.action_type == action_type

    def test_all_action_results_representable(self) -> None:
        for result in ActionResult:
            action = InternalAction(
                action_id=1,
                provider_action_id="test",
                match_id="M",
                team_id="T",
                player_id="P",
                period=1,
                minute=0,
                second=0,
                action_type=ActionType.PASS,
                result=result,
                start_x=0.0,
                start_y=0.0,
                end_x=0.0,
                end_y=0.0,
            )
            assert action.result == result

    def test_coordinate_range_0_100(self) -> None:
        """Coordinates must be in 0-100 normalized range."""
        for x in (0.0, 25.0, 50.0, 75.0, 100.0):
            for y in (0.0, 25.0, 50.0, 75.0, 100.0):
                action = InternalAction(
                    action_id=1, provider_action_id="t", match_id="M",
                    team_id="T", player_id="P", period=1, minute=0, second=0,
                    action_type=ActionType.PASS, result=ActionResult.SUCCESS,
                    start_x=x, start_y=y, end_x=x, end_y=y,
                )
                assert 0.0 <= action.start_x <= 100.0
                assert 0.0 <= action.start_y <= 100.0

    def test_period_values(self) -> None:
        """Period should support at least 1st half, 2nd half, extra time."""
        for period in (1, 2, 3, 4, 5):
            action = InternalAction(
                action_id=1, provider_action_id="t", match_id="M",
                team_id="T", player_id="P", period=period, minute=0, second=0,
                action_type=ActionType.FREEZE, result=ActionResult.UNKNOWN,
                start_x=0.0, start_y=0.0, end_x=0.0, end_y=0.0,
            )
            assert action.period == period

    def test_source_coverage_values(self) -> None:
        """source_coverage must be one of full/partial/sample."""
        for coverage in ("full", "partial", "sample"):
            action = InternalAction(
                action_id=1, provider_action_id="t", match_id="M",
                team_id="T", player_id="P", period=1, minute=0, second=0,
                action_type=ActionType.PASS, result=ActionResult.SUCCESS,
                start_x=0.0, start_y=0.0, end_x=0.0, end_y=0.0,
                source_coverage=coverage,
            )
            assert action.source_coverage == coverage


class TestStatsBombMappingCompleteness:
    """Validate that the StatsBomb -> InternalAction mapping is complete for known event types."""

    def test_all_mapped_types_are_action_type_enum(self) -> None:
        for sb_type, action_type in STATSBOMB_ACTION_MAP.items():
            assert isinstance(action_type, ActionType), f"{sb_type} maps to non-ActionType"

    def test_core_event_types_mapped(self) -> None:
        """Core StatsBomb event types must have mappings."""
        required = {"Pass", "Shot", "Carry", "Dribble", "Tackle",
                     "Interception", "Clearance", "Block", "Goal Keeper"}
        for event_type in required:
            assert event_type in STATSBOMB_ACTION_MAP, f"Missing mapping for {event_type}"

    def test_statsbomb_result_handles_all_outcomes(self) -> None:
        """statsbomb_result should handle all known outcome patterns."""
        assert statsbomb_result({"name": "Complete"}) == ActionResult.SUCCESS
        assert statsbomb_result({"name": "Incomplete"}) == ActionResult.FAILURE
        assert statsbomb_result({"name": "Won"}) == ActionResult.SUCCESS
        assert statsbomb_result({"name": "Lost"}) == ActionResult.FAILURE
        assert statsbomb_result(None) == ActionResult.UNKNOWN
        assert statsbomb_result({}) == ActionResult.UNKNOWN


class TestCoordinateNormalization:
    """Validate StatsBomb (120x80) -> normalized (100x100) coordinate mapping."""

    def test_corners(self) -> None:
        assert normalize_coordinates(0, 0) == (0.0, 0.0)
        assert normalize_coordinates(120, 80) == (100.0, 100.0)

    def test_midfield_spots(self) -> None:
        x, y = normalize_coordinates(60, 40)
        assert x == pytest.approx(50.0)
        assert y == pytest.approx(50.0)

    def test_penalty_area(self) -> None:
        """StatsBomb penalty area: x~102-120, y~18-62 -> normalized x~85-100, y~22.5-77.5"""
        x1, y1 = normalize_coordinates(102, 18)
        x2, y2 = normalize_coordinates(120, 62)
        assert x1 == pytest.approx(85.0)
        assert y1 == pytest.approx(22.5)
        assert x2 == pytest.approx(100.0)
        assert y2 == pytest.approx(77.5)

    def test_proportionality(self) -> None:
        """Coordinates should maintain relative positions."""
        x1, y1 = normalize_coordinates(30, 20)
        x2, y2 = normalize_coordinates(60, 40)
        assert x2 == pytest.approx(x1 * 2)
        assert y2 == pytest.approx(y1 * 2)


class TestStorageSchemaValidation:
    """Validate that storage schemas are consistent."""

    def test_core_tables_exist(self) -> None:
        tables = build_core_table_definitions()
        table_names = {t.name for t in tables}
        required = {"competition", "team", "player", "match", "team_match", "player_match"}
        assert required.issubset(table_names), f"Missing tables: {required - table_names}"

    def test_team_match_has_match_prediction_columns(self) -> None:
        """team_match must have columns needed by match prediction models."""
        tables = build_core_table_definitions()
        tm = next(t for t in tables if t.name == "team_match")
        col_names = {c.name for c in tm.columns}
        required = {"team_id", "is_home", "goals_for", "goals_against"}
        assert required.issubset(col_names), f"Missing cols: {required - col_names}"
