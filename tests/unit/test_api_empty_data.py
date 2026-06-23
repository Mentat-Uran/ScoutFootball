"""Tests for API/data_loader graceful handling of empty or missing data.

Verifies that:
- _safe_read_parquet returns None for missing/corrupt files
- API helper functions return valid JSON-serializable dicts when data is empty
- _normalize_ratings_frame handles empty DataFrames
- _clean_json_value handles DataFrames with NaN columns

All tests use mock/monkeypatch or tiny temporary files — no real data dependencies.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from scoutfootball.api import _clean_json_value
from scoutfootball.app.data_loader import _normalize_ratings_frame

# ---------------------------------------------------------------------------
# 1. _safe_read_parquet from data_loader
# ---------------------------------------------------------------------------


class TestSafeReadParquet:
    """Test _safe_read_parquet with missing/corrupt files."""

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        from scoutfootball.app.data_loader import _safe_read_parquet

        missing = tmp_path / "nonexistent.parquet"
        with patch(
            "scoutfootball.app.data_loader._parquet_path",
            return_value=missing,
        ):
            with patch(
                "scoutfootball.app.data_loader._parquet_exists",
                return_value=False,
            ):
                result = _safe_read_parquet(
                    "gold/feature_store/nonexistent.parquet"
                )
        assert result is None

    def test_corrupt_parquet_returns_none(self, tmp_path: Path) -> None:
        from scoutfootball.app.data_loader import _safe_read_parquet

        corrupt_file = tmp_path / "corrupt.parquet"
        corrupt_file.write_bytes(b"not a parquet file")
        with patch(
            "scoutfootball.app.data_loader._parquet_path",
            return_value=corrupt_file,
        ):
            with patch(
                "scoutfootball.app.data_loader._parquet_exists",
                return_value=True,
            ):
                result = _safe_read_parquet(
                    "gold/feature_store/corrupt.parquet"
                )
        assert result is None


# ---------------------------------------------------------------------------
# 2. _normalize_ratings_frame with empty data
# ---------------------------------------------------------------------------


class TestNormalizeRatingsFrameEmpty:
    def test_empty_dataframe_returns_empty(self) -> None:
        df = pd.DataFrame()
        result = _normalize_ratings_frame(df)
        assert result.empty

    def test_empty_with_columns_returns_empty(self) -> None:
        df = pd.DataFrame(columns=["player", "team", "optimized_score"])
        result = _normalize_ratings_frame(df)
        assert result.empty
        assert "player" in result.columns

    def test_adds_player_name_from_player(self) -> None:
        df = pd.DataFrame({"player": ["Test"], "team": ["FC"], "optimized_score": [50.0]})
        result = _normalize_ratings_frame(df)
        assert "player_name" in result.columns
        assert result.iloc[0]["player_name"] == "Test"

    def test_adds_team_name_from_team(self) -> None:
        df = pd.DataFrame({"player": ["Test"], "team": ["FC"], "optimized_score": [50.0]})
        result = _normalize_ratings_frame(df)
        assert "team_name" in result.columns
        assert result.iloc[0]["team_name"] == "FC"

    def test_adds_confidence_level_from_minutes(self) -> None:
        df = pd.DataFrame({"player": ["A", "B", "C"], "minutes": [1000, 500, 100]})
        result = _normalize_ratings_frame(df)
        assert "confidence_level" in result.columns
        assert result.iloc[0]["confidence_level"] == "HIGH"
        assert result.iloc[1]["confidence_level"] == "MEDIUM"
        assert result.iloc[2]["confidence_level"] == "LOW"

    def test_no_minutes_gets_low_confidence(self) -> None:
        df = pd.DataFrame({"player": ["A"], "optimized_score": [50.0]})
        result = _normalize_ratings_frame(df)
        assert "confidence_level" in result.columns
        assert result.iloc[0]["confidence_level"] == "LOW"

    def test_sub_position_renamed_to_position_group(self) -> None:
        df = pd.DataFrame({"player": ["A"], "sub_position": ["ST"], "optimized_score": [50.0]})
        result = _normalize_ratings_frame(df)
        assert "position_group" in result.columns
        assert result.iloc[0]["position_group"] == "ST"


# ---------------------------------------------------------------------------
# 3. API helper functions with empty data
# ---------------------------------------------------------------------------


class TestApiEmptyDataResponses:
    """Test that API functions return valid JSON when data is empty."""

    def test_get_value_summary_empty(self) -> None:
        from scoutfootball.api import get_value_summary

        with patch("scoutfootball.api.load_oof_predictions", return_value=pd.DataFrame()):
            result = get_value_summary()
        assert isinstance(result, dict)
        assert result["status"] == "no_data"
        assert result["players"] == []
        # Must be JSON-serializable
        json.dumps(result)

    def test_get_player_ratings_empty(self) -> None:
        from scoutfootball.api import get_player_ratings

        with patch("scoutfootball.api.load_player_ratings", return_value=pd.DataFrame()):
            result = get_player_ratings()
        assert isinstance(result, dict)
        assert result["count"] == 0
        assert result["players"] == []
        json.dumps(result)

    def test_get_ratings_meta_empty(self) -> None:
        from scoutfootball.api import get_ratings_meta

        with patch("scoutfootball.api.load_model_meta", return_value=pd.DataFrame()):
            with patch("scoutfootball.api.load_league_metrics", return_value=pd.DataFrame()):
                result = get_ratings_meta()
        assert isinstance(result, dict)
        json.dumps(result)

    def test_get_review_queue_empty(self) -> None:
        from scoutfootball.api import get_review_queue

        with patch("scoutfootball.api.load_player_ratings", return_value=pd.DataFrame()):
            result = get_review_queue()
        assert isinstance(result, dict)
        assert result["count"] == 0
        assert result["players"] == []
        json.dumps(result)

    def test_get_watchlist_empty(self) -> None:
        from scoutfootball.api import get_watchlist

        with patch("scoutfootball.api.load_player_ratings", return_value=pd.DataFrame()):
            result = get_watchlist()
        assert isinstance(result, dict)
        assert result["count"] == 0
        assert result["players"] == []
        json.dumps(result)

    def test_get_shortlist_empty(self) -> None:
        from scoutfootball.api import get_shortlist

        with patch("scoutfootball.api.load_player_ratings", return_value=pd.DataFrame()):
            result = get_shortlist()
        assert isinstance(result, dict)
        assert result["count"] == 0
        assert result["players"] == []
        json.dumps(result)

    def test_get_prediction_summary_no_data(self) -> None:
        from scoutfootball.api import get_prediction_summary

        with patch("scoutfootball.api.load_score_prediction", return_value=pd.DataFrame()):
            with patch("scoutfootball.api.load_score_prediction_dc", return_value=pd.DataFrame()):
                result = get_prediction_summary()
        assert isinstance(result, dict)
        json.dumps(result)


# ---------------------------------------------------------------------------
# 4. DataFrame with NaN values cleaned by _clean_json_value
# ---------------------------------------------------------------------------


class TestCleanJsonWithNanDataFrame:
    """Verify _clean_json_value handles dict from DataFrame row with NaN."""

    def test_row_with_nan_values(self) -> None:
        df = pd.DataFrame({
            "name": ["Alice"],
            "score": [float("nan")],
            "value": [np.float64("nan")],
            "count": [np.int64(42)],
            "flag": [np.bool_(True)],
        })
        row_dict = df.iloc[0].to_dict()
        result = _clean_json_value(row_dict)
        assert result["name"] == "Alice"
        assert result["score"] is None
        assert result["value"] is None
        assert result["count"] == 42
        assert result["flag"] is True
        # Must be JSON-serializable
        json.dumps(result)

    def test_row_with_inf_values(self) -> None:
        df = pd.DataFrame({
            "name": ["Bob"],
            "ratio": [float("inf")],
        })
        row_dict = df.iloc[0].to_dict()
        result = _clean_json_value(row_dict)
        assert result["ratio"] is None
        json.dumps(result)

    def test_row_with_pd_na(self) -> None:
        df = pd.DataFrame({
            "name": ["Carol"],
            "optional": [pd.NA],
        })
        row_dict = df.iloc[0].to_dict()
        result = _clean_json_value(row_dict)
        assert result["optional"] is None
        json.dumps(result)

    def test_empty_dataframe_to_records(self) -> None:
        df = pd.DataFrame(columns=["player", "team", "score"])
        records = df.to_dict(orient="records")
        result = _clean_json_value(records)
        assert result == []
        json.dumps(result)
