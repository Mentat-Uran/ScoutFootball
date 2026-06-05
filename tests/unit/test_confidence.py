"""Unit tests for unified confidence module."""

from __future__ import annotations

import pandas as pd
import pytest

from scoutlab.evaluation.confidence import (
    assess_batch_confidence,
    assess_player_confidence,
)

# ---------------------------------------------------------------------------
# assess_player_confidence — low minutes
# ---------------------------------------------------------------------------


class TestLowMinutes:
    def test_below_threshold_is_low_confidence(self) -> None:
        row = pd.Series({"player_name": "Test", "minutes_played": 200, "position_group": "CM"})
        result = assess_player_confidence(row)
        assert result.is_low_confidence
        assert any("出场时间不足" in r for r in result.reasons)
        assert result.minutes_played == 200.0

    def test_at_threshold_is_high_confidence(self) -> None:
        row = pd.Series({"player_name": "Test", "minutes_played": 450, "position_group": "CM"})
        result = assess_player_confidence(row)
        assert not result.is_low_confidence

    def test_above_threshold_is_high_confidence(self) -> None:
        row = pd.Series({"player_name": "Test", "minutes_played": 2000, "position_group": "CM"})
        result = assess_player_confidence(row)
        assert not result.is_low_confidence

    def test_custom_min_minutes(self) -> None:
        row = pd.Series({"player_name": "Test", "minutes_played": 500, "position_group": "CM"})
        result = assess_player_confidence(row, min_minutes=600)
        assert result.is_low_confidence

    def test_zero_minutes(self) -> None:
        row = pd.Series({"player_name": "Test", "minutes_played": 0, "position_group": "CM"})
        result = assess_player_confidence(row)
        assert result.is_low_confidence


# ---------------------------------------------------------------------------
# assess_player_confidence — missing dimensions
# ---------------------------------------------------------------------------


class TestMissingDimensions:
    def test_missing_defense_flagged(self) -> None:
        row = pd.Series({
            "player_name": "Test",
            "minutes_played": 1000,
            "position_group": "CB",
            "defense_missing": True,
        })
        result = assess_player_confidence(row)
        assert result.is_low_confidence
        assert "defense" in result.missing_dimensions
        assert any("缺失defense数据" in r for r in result.reasons)

    def test_multiple_missing_dimensions(self) -> None:
        row = pd.Series({
            "player_name": "Test",
            "minutes_played": 1000,
            "position_group": "CM",
            "defense_missing": True,
            "possession_missing": True,
        })
        result = assess_player_confidence(row)
        assert "defense" in result.missing_dimensions
        assert "possession" in result.missing_dimensions
        assert len(result.missing_dimensions) == 2

    def test_not_missing_is_high_confidence(self) -> None:
        row = pd.Series({
            "player_name": "Test",
            "minutes_played": 1000,
            "position_group": "CM",
            "defense_missing": False,
        })
        result = assess_player_confidence(row)
        assert not result.is_low_confidence
        assert len(result.missing_dimensions) == 0


# ---------------------------------------------------------------------------
# assess_player_confidence — coarse position
# ---------------------------------------------------------------------------


class TestCoarsePosition:
    def test_df_is_coarse(self) -> None:
        row = pd.Series({"player_name": "Test", "minutes_played": 1000, "position_group": "DF"})
        result = assess_player_confidence(row)
        assert result.position_confidence == "low"
        assert any("位置分组粗略" in r for r in result.reasons)

    def test_mf_is_coarse(self) -> None:
        row = pd.Series({"player_name": "Test", "minutes_played": 1000, "position_group": "MF"})
        result = assess_player_confidence(row)
        assert result.position_confidence == "low"

    def test_fw_is_coarse(self) -> None:
        row = pd.Series({"player_name": "Test", "minutes_played": 1000, "position_group": "FW"})
        result = assess_player_confidence(row)
        assert result.position_confidence == "low"

    def test_cb_is_fine(self) -> None:
        row = pd.Series({"player_name": "Test", "minutes_played": 1000, "position_group": "CB"})
        result = assess_player_confidence(row)
        assert result.position_confidence == "high"
        assert not result.is_low_confidence

    def test_st_is_fine(self) -> None:
        row = pd.Series({"player_name": "Test", "minutes_played": 1000, "position_group": "ST"})
        result = assess_player_confidence(row)
        assert result.position_confidence == "high"
        assert not result.is_low_confidence

    def test_coarse_position_only_is_not_low_confidence(self) -> None:
        """Coarse position alone should not trigger is_low_confidence."""
        row = pd.Series({"player_name": "Test", "minutes_played": 1000, "position_group": "DF"})
        result = assess_player_confidence(row)
        assert not result.is_low_confidence
        assert result.position_confidence == "low"


# ---------------------------------------------------------------------------
# assess_player_confidence — low coverage
# ---------------------------------------------------------------------------


class TestLowCoverage:
    def test_below_90_is_low_confidence(self) -> None:
        row = pd.Series({
            "player_name": "Test",
            "minutes_played": 1000,
            "position_group": "CM",
            "coverage": 0.75,
        })
        result = assess_player_confidence(row)
        assert result.is_low_confidence
        assert result.league_coverage == 0.75
        assert any("联赛覆盖不足" in r for r in result.reasons)

    def test_at_90_is_high_confidence(self) -> None:
        row = pd.Series({
            "player_name": "Test",
            "minutes_played": 1000,
            "position_group": "CM",
            "coverage": 0.90,
        })
        result = assess_player_confidence(row)
        assert not result.is_low_confidence

    def test_above_90_is_high_confidence(self) -> None:
        row = pd.Series({
            "player_name": "Test",
            "minutes_played": 1000,
            "position_group": "CM",
            "coverage": 1.00,
        })
        result = assess_player_confidence(row)
        assert not result.is_low_confidence


# ---------------------------------------------------------------------------
# assess_player_confidence — complete data = high confidence
# ---------------------------------------------------------------------------


class TestHighConfidenceCompleteData:
    def test_complete_data_is_high_confidence(self) -> None:
        row = pd.Series({
            "player_name": "Complete Player",
            "minutes_played": 2500,
            "position_group": "CM",
            "coverage": 0.95,
        })
        result = assess_player_confidence(row)
        assert not result.is_low_confidence
        assert result.position_confidence == "high"
        assert len(result.reasons) == 0
        assert len(result.missing_dimensions) == 0


# ---------------------------------------------------------------------------
# assess_batch_confidence
# ---------------------------------------------------------------------------


class TestAssessBatchConfidence:
    def test_adds_columns(self) -> None:
        df = pd.DataFrame([
            {"player_name": "A", "minutes_played": 100, "position_group": "CM"},
            {"player_name": "B", "minutes_played": 2000, "position_group": "ST"},
        ])
        result = assess_batch_confidence(df)
        assert "is_low_confidence" in result.columns
        assert "confidence_reasons" in result.columns
        assert "missing_dimensions" in result.columns
        assert result.iloc[0]["is_low_confidence"] == True  # noqa: E712
        assert result.iloc[1]["is_low_confidence"] == False  # noqa: E712

    def test_empty_dataframe(self) -> None:
        df = pd.DataFrame(columns=["player_name", "minutes_played", "position_group"])
        result = assess_batch_confidence(df)
        assert result.empty
        assert "is_low_confidence" in result.columns
        assert "confidence_reasons" in result.columns
        assert "missing_dimensions" in result.columns

    def test_does_not_mutate_original(self) -> None:
        df = pd.DataFrame([
            {"player_name": "A", "minutes_played": 100, "position_group": "CM"},
        ])
        original_cols = set(df.columns)
        _ = assess_batch_confidence(df)
        assert set(df.columns) == original_cols


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_missing_minutes_column(self) -> None:
        row = pd.Series({"player_name": "Test", "position_group": "CM"})
        result = assess_player_confidence(row)
        assert result.minutes_played is None
        # No minutes column means no low-minutes reason
        assert not any("出场时间不足" in r for r in result.reasons)

    def test_missing_position_column(self) -> None:
        row = pd.Series({"player_name": "Test", "minutes_played": 1000})
        result = assess_player_confidence(row)
        assert result.position_confidence == "high"

    def test_nan_minutes(self) -> None:
        row = pd.Series({
            "player_name": "Test",
            "minutes_played": float("nan"),
            "position_group": "CM",
        })
        result = assess_player_confidence(row)
        assert result.minutes_played is None
        assert not any("出场时间不足" in r for r in result.reasons)

    def test_nan_coverage(self) -> None:
        row = pd.Series({
            "player_name": "Test",
            "minutes_played": 1000,
            "position_group": "CM",
            "coverage": float("nan"),
        })
        result = assess_player_confidence(row)
        assert result.league_coverage is None
        assert not any("联赛覆盖不足" in r for r in result.reasons)

    def test_non_numeric_minutes(self) -> None:
        row = pd.Series({"player_name": "Test", "minutes_played": "N/A", "position_group": "CM"})
        result = assess_player_confidence(row)
        assert result.minutes_played is None

    def test_frozen_dataclass(self) -> None:
        row = pd.Series({"player_name": "Test", "minutes_played": 1000, "position_group": "CM"})
        result = assess_player_confidence(row)
        with pytest.raises(AttributeError):
            result.is_low_confidence = False  # type: ignore[misc]

    def test_coarse_position_with_other_issue_is_low(self) -> None:
        """Coarse position + low minutes = low confidence."""
        row = pd.Series({"player_name": "Test", "minutes_played": 100, "position_group": "DF"})
        result = assess_player_confidence(row)
        assert result.is_low_confidence
        assert result.position_confidence == "low"

    def test_missing_suffix_custom(self) -> None:
        row = pd.Series({
            "player_name": "Test",
            "minutes_played": 1000,
            "position_group": "CM",
            "defense_flag": True,
        })
        result = assess_player_confidence(row, missing_suffix="_flag")
        assert "defense" in result.missing_dimensions

    def test_coverage_col_custom(self) -> None:
        row = pd.Series({
            "player_name": "Test",
            "minutes_played": 1000,
            "position_group": "CM",
            "league_cov": 0.50,
        })
        result = assess_player_confidence(row, coverage_col="league_cov")
        assert result.league_coverage == 0.50
        assert result.is_low_confidence
