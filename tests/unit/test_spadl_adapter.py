"""Contract tests for the flat StatsBomb-to-internal-action conversion."""

from __future__ import annotations

import pandas as pd
import pytest

from scoutfootball.action_value.spadl_adapter import (
    EventConversionError,
    convert_events,
)


def _event_frame() -> pd.DataFrame:
    """Small redistributable fixture with two matches and one skipped event."""
    return pd.DataFrame(
        [
            {
                "event_id": "start-m1",
                "match_id": "m1",
                "event_type": "Starting XI",
                "period": 1,
                "minute": 0,
                "second": 0,
                "location_x": None,
                "location_y": None,
            },
            {
                "event_id": "pass-m1",
                "match_id": "m1",
                "event_type": "Pass",
                "period": 1,
                "minute": 4,
                "second": 12,
                "location_x": 60.0,
                "location_y": 40.0,
                "pass_end_location_x": 90.0,
                "pass_end_location_y": 60.0,
                "pass_outcome_name": None,
            },
            {
                "event_id": "shot-m1",
                "match_id": "m1",
                "event_type": "Shot",
                "period": 1,
                "minute": 5,
                "second": 3,
                "location_x": 96.0,
                "location_y": 24.0,
                "shot_end_location_x": 120.0,
                "shot_end_location_y": 40.0,
                "shot_outcome_name": "Goal",
            },
            {
                "event_id": "pass-m2",
                "match_id": "m2",
                "event_type": "Pass",
                "period": 1,
                "minute": 1,
                "second": 0,
                "location_x": 12.0,
                "location_y": 16.0,
                "pass_end_location_x": 24.0,
                "pass_end_location_y": 32.0,
                "pass_outcome_name": "Incomplete",
            },
        ]
    )


class TestConvertEvents:
    def test_preserves_provider_identity_and_generates_match_local_ids(self) -> None:
        actions = convert_events(_event_frame())

        assert actions["provider_action_id"].tolist() == [
            "pass-m1",
            "shot-m1",
            "pass-m2",
        ]
        assert actions["action_id"].tolist() == [0, 1, 0]
        assert actions["match_id"].tolist() == ["m1", "m1", "m2"]
        assert not actions.duplicated(["match_id", "action_id"]).any()

    def test_normalizes_coordinates_without_claiming_direction_reorientation(self) -> None:
        actions = convert_events(_event_frame())

        first = actions.iloc[0]
        assert (first.start_x, first.start_y) == (50.0, 50.0)
        assert (first.end_x, first.end_y) == (75.0, 75.0)
        assert actions["action_type"].tolist() == ["pass", "shot", "pass"]
        assert actions["result"].tolist() == ["success", "success", "failure"]

    def test_skipped_events_may_lack_coordinates(self) -> None:
        actions = convert_events(_event_frame())

        assert len(actions) == 3

    @pytest.mark.parametrize(
        ("column", "value", "message"),
        [
            ("event_id", "", "blank event_id"),
            ("match_id", "", "blank match_id"),
            ("period", 0, "invalid period"),
            ("minute", 4.5, "invalid minute"),
            ("second", 60, "invalid second"),
        ],
    )
    def test_rejects_invalid_identity_or_timing(
        self, column: str, value: object, message: str
    ) -> None:
        events = _event_frame()
        if column in {"period", "minute", "second"}:
            events[column] = events[column].astype(float)
        events.loc[1, column] = value

        with pytest.raises(EventConversionError, match=message):
            convert_events(events)

    def test_rejects_duplicate_provider_event_identity(self) -> None:
        events = _event_frame()
        events.loc[2, "event_id"] = "pass-m1"

        with pytest.raises(EventConversionError, match="duplicate event_id"):
            convert_events(events)

    def test_rejects_invalid_coordinate_on_convertible_event(self) -> None:
        events = _event_frame()
        events.loc[1, "location_x"] = 121.0

        with pytest.raises(EventConversionError, match="invalid location_x"):
            convert_events(events)

    def test_partial_end_coordinate_pair_falls_back_to_start(self) -> None:
        events = _event_frame().drop(columns=["pass_end_location_y"])

        actions = convert_events(events)

        first = actions.iloc[0]
        assert (first.end_x, first.end_y) == (first.start_x, first.start_y)
