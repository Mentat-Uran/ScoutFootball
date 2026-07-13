"""Tests for snapshot_to_truth_labels bridge in transfermarkt_manual adapter."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pandas as pd
import pytest

from scoutfootball.adapters.transfermarkt_manual import snapshot_to_truth_labels


def _make_snapshot_df() -> pd.DataFrame:
    """Build a minimal snapshot DataFrame that load_snapshot would produce."""
    return pd.DataFrame({
        "player_name": ["Erling Haaland", "Jude Bellingham"],
        "team_name": ["Manchester City", "Real Madrid"],
        "snapshot_date": [pd.Timestamp("2025-06-01").date()] * 2,
        "market_value": [170_000_000.0, 120_000_000.0],
        "contract_end": [pd.NaT.date()] * 2,
        "transfer_fee": [None, None],
        "data_source": ["transfermarkt_manual"] * 2,
        "import_method": ["local_file"] * 2,
    })


class TestSnapshotToTruthLabelsBasic:
    """Test basic output shape and column mapping."""

    @patch("scoutfootball.adapters.transfermarkt_manual.load_snapshot")
    def test_correct_columns(self, mock_load) -> None:
        mock_load.return_value.dataframe = _make_snapshot_df()
        result = snapshot_to_truth_labels("dummy.csv", "2526")

        expected_cols = [
            "player_id", "season", "label_source", "label_confidence",
            "label_value", "as_of_date", "position_scope", "manual_review_flag",
        ]
        assert list(result.columns) == expected_cols

    @patch("scoutfootball.adapters.transfermarkt_manual.load_snapshot")
    def test_label_source(self, mock_load) -> None:
        mock_load.return_value.dataframe = _make_snapshot_df()
        result = snapshot_to_truth_labels("dummy.csv", "2526")

        assert (result["label_source"] == "transfermarkt_value").all()

    @patch("scoutfootball.adapters.transfermarkt_manual.load_snapshot")
    def test_default_confidence(self, mock_load) -> None:
        mock_load.return_value.dataframe = _make_snapshot_df()
        result = snapshot_to_truth_labels("dummy.csv", "2526")

        assert (result["label_confidence"] == "medium").all()

    @patch("scoutfootball.adapters.transfermarkt_manual.load_snapshot")
    def test_player_id_from_player_name(self, mock_load) -> None:
        snapshot = _make_snapshot_df()
        mock_load.return_value.dataframe = snapshot
        result = snapshot_to_truth_labels("dummy.csv", "2526")

        assert list(result["player_id"]) == ["Erling Haaland", "Jude Bellingham"]

    @patch("scoutfootball.adapters.transfermarkt_manual.load_snapshot")
    def test_label_value_from_market_value(self, mock_load) -> None:
        snapshot = _make_snapshot_df()
        mock_load.return_value.dataframe = snapshot
        result = snapshot_to_truth_labels("dummy.csv", "2526")

        assert list(result["label_value"]) == [170_000_000.0, 120_000_000.0]


class TestSnapshotToTruthLabelsCustomConfidence:
    @patch("scoutfootball.adapters.transfermarkt_manual.load_snapshot")
    def test_high_confidence(self, mock_load) -> None:
        mock_load.return_value.dataframe = _make_snapshot_df()
        result = snapshot_to_truth_labels("dummy.csv", "2526", confidence="high")

        assert (result["label_confidence"] == "high").all()


class TestSnapshotToTruthLabelsValidationFailure:
    @patch("scoutfootball.evaluation.truth_labels.validate_truth_labels")
    @patch("scoutfootball.adapters.transfermarkt_manual.load_snapshot")
    def test_raises_on_validation_error(self, mock_load, mock_validate) -> None:
        mock_load.return_value.dataframe = _make_snapshot_df()
        mock_validate.return_value = ["Missing columns: ['player_id']"]

        with pytest.raises(ValueError, match="Truth labels validation failed"):
            snapshot_to_truth_labels("dummy.csv", "2526")


class TestSnapshotToTruthLabelsAsOfDate:
    @patch("scoutfootball.adapters.transfermarkt_manual.load_snapshot")
    def test_preserves_source_snapshot_date(self, mock_load) -> None:
        mock_load.return_value.dataframe = _make_snapshot_df()
        result = snapshot_to_truth_labels("dummy.csv", "2526")

        assert (result["as_of_date"] == "2025-06-01").all()

        # Verify YYYY-MM-DD format
        as_of = result["as_of_date"].iloc[0]
        datetime.strptime(as_of, "%Y-%m-%d")  # raises if format is wrong

    @patch("scoutfootball.adapters.transfermarkt_manual.load_snapshot")
    def test_allows_explicit_iso_date_override(self, mock_load) -> None:
        mock_load.return_value.dataframe = _make_snapshot_df()
        result = snapshot_to_truth_labels("dummy.csv", "2526", as_of_date="2025-05-31")

        assert (result["as_of_date"] == "2025-05-31").all()

    @patch("scoutfootball.adapters.transfermarkt_manual.load_snapshot")
    def test_rejects_non_iso_date_override(self, mock_load) -> None:
        mock_load.return_value.dataframe = _make_snapshot_df()

        with pytest.raises(ValueError, match="ISO YYYY-MM-DD"):
            snapshot_to_truth_labels("dummy.csv", "2526", as_of_date="2025/05/31")
