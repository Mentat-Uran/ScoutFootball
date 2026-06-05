"""Unit tests for coverage_confidence module."""

from __future__ import annotations

import pandas as pd
import pytest

from scoutlab.evaluation.coverage_confidence import (
    ConfidenceLevel,
    add_confidence_to_ratings,
    assess_coverage_batch,
    assess_league_season,
    classify_confidence,
)

# ---------------------------------------------------------------------------
# classify_confidence
# ---------------------------------------------------------------------------


class TestClassifyConfidence:
    def test_high_at_threshold(self) -> None:
        assert classify_confidence(0.90) == ConfidenceLevel.HIGH

    def test_high_above_threshold(self) -> None:
        assert classify_confidence(1.00) == ConfidenceLevel.HIGH

    def test_medium_at_lower_threshold(self) -> None:
        assert classify_confidence(0.70) == ConfidenceLevel.MEDIUM

    def test_medium_just_below_high(self) -> None:
        assert classify_confidence(0.89) == ConfidenceLevel.MEDIUM

    def test_low_just_below_medium(self) -> None:
        assert classify_confidence(0.69) == ConfidenceLevel.LOW

    def test_low_zero(self) -> None:
        assert classify_confidence(0.0) == ConfidenceLevel.LOW

    def test_medium_midrange(self) -> None:
        assert classify_confidence(0.80) == ConfidenceLevel.MEDIUM


# ---------------------------------------------------------------------------
# assess_league_season
# ---------------------------------------------------------------------------


class TestAssessLeagueSeason:
    def test_full_coverage(self) -> None:
        result = assess_league_season("Premier League", "2024-2025", 20, 20, 20)
        assert result.coverage == 1.0
        assert result.confidence_level == ConfidenceLevel.HIGH
        assert result.allowed_output == "full"

    def test_medium_coverage(self) -> None:
        result = assess_league_season("Eredivisie", "2024-2025", 18, 14, 14)
        assert abs(result.coverage - 14 / 18) < 1e-9
        assert result.confidence_level == ConfidenceLevel.MEDIUM
        assert result.allowed_output == "reference_only"

    def test_low_coverage(self) -> None:
        result = assess_league_season("Süper Lig", "2024-2025", 20, 10, 10)
        assert result.coverage == 0.5
        assert result.confidence_level == ConfidenceLevel.LOW
        assert result.allowed_output == "diagnostic_only"

    def test_zero_target_teams(self) -> None:
        result = assess_league_season("Unknown", "2024-2025", 0, 5, 0)
        assert result.coverage == 0.0
        assert result.confidence_level == ConfidenceLevel.LOW

    def test_frozen_dataclass(self) -> None:
        result = assess_league_season("La Liga", "2024-2025", 20, 20, 20)
        with pytest.raises(AttributeError):
            result.coverage = 0.5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# assess_coverage_batch
# ---------------------------------------------------------------------------


class TestAssessCoverageBatch:
    def _make_ratings(self) -> pd.DataFrame:
        rows = [
            {"league": "Premier League", "season": "2024-2025", "team_name": "Arsenal"},
            {"league": "Premier League", "season": "2024-2025", "team_name": "Chelsea"},
            {"league": "Premier League", "season": "2024-2025", "team_name": "Liverpool"},
            {"league": "La Liga", "season": "2024-2025", "team_name": "Barcelona"},
            {"league": "La Liga", "season": "2024-2025", "team_name": "Real Madrid"},
            {"league": "Eredivisie", "season": "2024-2025", "team_name": "Ajax"},
        ]
        return pd.DataFrame(rows)

    def test_empty_dataframe(self) -> None:
        df = pd.DataFrame(columns=["league", "season", "team_name"])
        result = assess_coverage_batch(df)
        assert result.empty
        assert list(result.columns) == [
            "league",
            "season",
            "target_teams",
            "rated_teams",
            "matched_teams",
            "coverage",
            "confidence_level",
            "allowed_output",
        ]

    def test_missing_columns_raises(self) -> None:
        df = pd.DataFrame({"league": ["A"], "season": ["2024"]})
        with pytest.raises(ValueError, match="missing required columns"):
            assess_coverage_batch(df)

    def test_without_target_teams_defaults_full_coverage(self) -> None:
        df = self._make_ratings()
        result = assess_coverage_batch(df)
        pl = result[result["league"] == "Premier League"].iloc[0]
        assert pl["rated_teams"] == 3
        assert pl["target_teams"] == 3
        assert pl["coverage"] == 1.0
        assert pl["confidence_level"] == "high"

    def test_with_target_teams(self) -> None:
        df = self._make_ratings()
        targets = {"Premier League": 20, "La Liga": 20, "Eredivisie": 18}
        result = assess_coverage_batch(df, target_teams_per_league=targets)
        pl = result[result["league"] == "Premier League"].iloc[0]
        assert pl["target_teams"] == 20
        assert pl["matched_teams"] == 3
        assert abs(pl["coverage"] - 3 / 20) < 1e-9
        assert pl["confidence_level"] == "low"

    def test_unknown_league_in_targets_uses_rated_as_fallback(self) -> None:
        df = self._make_ratings()
        targets = {"Premier League": 20}
        result = assess_coverage_batch(df, target_teams_per_league=targets)
        eredivisie = result[result["league"] == "Eredivisie"].iloc[0]
        assert eredivisie["target_teams"] == 1  # rated_teams as fallback
        assert eredivisie["coverage"] == 1.0

    def test_output_columns(self) -> None:
        df = self._make_ratings()
        result = assess_coverage_batch(df)
        expected = {
            "league",
            "season",
            "target_teams",
            "rated_teams",
            "matched_teams",
            "coverage",
            "confidence_level",
            "allowed_output",
        }
        assert expected == set(result.columns)


# ---------------------------------------------------------------------------
# add_confidence_to_ratings
# ---------------------------------------------------------------------------


class TestAddConfidenceToRatings:
    def test_merge_adds_columns(self) -> None:
        ratings = pd.DataFrame(
            {
                "league": ["Premier League", "Premier League", "La Liga"],
                "season": ["2024-2025", "2024-2025", "2024-2025"],
                "player": ["Player A", "Player B", "Player C"],
                "rating": [80.0, 75.0, 70.0],
            },
        )
        assessments = pd.DataFrame(
            {
                "league": ["Premier League", "La Liga"],
                "season": ["2024-2025", "2024-2025"],
                "coverage": [0.95, 0.60],
                "confidence_level": ["high", "low"],
                "allowed_output": ["full", "diagnostic_only"],
            },
        )
        result = add_confidence_to_ratings(ratings, assessments)
        assert "coverage" in result.columns
        assert "confidence_level" in result.columns
        assert "allowed_output" in result.columns
        la_liga = result.loc[result["league"] == "La Liga", "confidence_level"].iloc[0]
        assert la_liga == "low"
        pl = result.loc[result["league"] == "Premier League", "confidence_level"].iloc[0]
        assert pl == "high"

    def test_empty_assessments_adds_na_columns(self) -> None:
        ratings = pd.DataFrame(
            {
                "league": ["Premier League"],
                "season": ["2024-2025"],
                "player": ["Player A"],
            },
        )
        assessments = pd.DataFrame(
            columns=["league", "season", "coverage", "confidence_level", "allowed_output"],
        )
        result = add_confidence_to_ratings(ratings, assessments)
        assert pd.isna(result["coverage"].iloc[0])
        assert pd.isna(result["confidence_level"].iloc[0])

    def test_does_not_mutate_original(self) -> None:
        ratings = pd.DataFrame(
            {
                "league": ["Premier League"],
                "season": ["2024-2025"],
                "player": ["Player A"],
            },
        )
        assessments = pd.DataFrame(
            {
                "league": ["Premier League"],
                "season": ["2024-2025"],
                "coverage": [0.95],
                "confidence_level": ["high"],
                "allowed_output": ["full"],
            },
        )
        result = add_confidence_to_ratings(ratings, assessments)
        assert "coverage" not in ratings.columns
        assert "coverage" in result.columns

    def test_unmatched_league_gets_na(self) -> None:
        ratings = pd.DataFrame(
            {
                "league": ["Süper Lig"],
                "season": ["2024-2025"],
                "player": ["Player X"],
            },
        )
        assessments = pd.DataFrame(
            {
                "league": ["Premier League"],
                "season": ["2024-2025"],
                "coverage": [0.95],
                "confidence_level": ["high"],
                "allowed_output": ["full"],
            },
        )
        result = add_confidence_to_ratings(ratings, assessments)
        assert pd.isna(result["coverage"].iloc[0])
