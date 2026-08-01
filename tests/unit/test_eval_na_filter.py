"""Tests for N/A team filtering in evaluation."""
import numpy as np
import pandas as pd


class TestBuildMatchedResultsNAFilter:
    """Test that teams with NaN points are excluded from matched results."""

    def test_nan_points_excluded(self):
        """Teams with NaN total_points should be excluded."""
        team_pts_df = pd.DataFrame({
            "team": ["TeamA", "TeamB", "TeamC"],
            "league": ["League1", "League1", "League1"],
            "season": ["2526", "2526", "2526"],
            "total_points": [80.0, np.nan, 60.0],
        })
        valid_pts = team_pts_df.copy()
        valid_pts["total_points"] = pd.to_numeric(
            valid_pts["total_points"], errors="coerce"
        )
        n_before = len(valid_pts)
        valid_pts = valid_pts[
            valid_pts["total_points"].notna()
            & np.isfinite(valid_pts["total_points"])
        ]
        n_excluded = n_before - len(valid_pts)

        assert len(valid_pts) == 2
        assert n_excluded == 1
        assert "TeamA" in valid_pts["team"].values
        assert "TeamC" in valid_pts["team"].values
        assert "TeamB" not in valid_pts["team"].values

    def test_all_valid_points_pass(self):
        """All teams with valid points should be included."""
        team_pts_df = pd.DataFrame({
            "team": ["TeamA", "TeamB"],
            "league": ["League1", "League1"],
            "season": ["2526", "2526"],
            "total_points": [80.0, 60.0],
        })
        valid_pts = team_pts_df.copy()
        valid_pts["total_points"] = pd.to_numeric(
            valid_pts["total_points"], errors="coerce"
        )
        valid_pts = valid_pts[
            valid_pts["total_points"].notna()
            & np.isfinite(valid_pts["total_points"])
        ]

        assert len(valid_pts) == 2

    def test_string_na_excluded(self):
        """Teams with string 'N/A' points should be excluded."""
        team_pts_df = pd.DataFrame({
            "team": ["TeamA", "TeamB"],
            "league": ["League1", "League1"],
            "season": ["2526", "2526"],
            "total_points": [80.0, "N/A"],
        })
        valid_pts = team_pts_df.copy()
        valid_pts["total_points"] = pd.to_numeric(
            valid_pts["total_points"], errors="coerce"
        )
        n_before = len(valid_pts)
        valid_pts = valid_pts[
            valid_pts["total_points"].notna()
            & np.isfinite(valid_pts["total_points"])
        ]
        n_excluded = n_before - len(valid_pts)

        assert len(valid_pts) == 1
        assert n_excluded == 1

    def test_empty_after_filter(self):
        """If all teams have NaN points, result should be empty."""
        team_pts_df = pd.DataFrame({
            "team": ["TeamA", "TeamB"],
            "league": ["League1", "League1"],
            "season": ["2526", "2526"],
            "total_points": [np.nan, np.nan],
        })
        valid_pts = team_pts_df.copy()
        valid_pts["total_points"] = pd.to_numeric(
            valid_pts["total_points"], errors="coerce"
        )
        valid_pts = valid_pts[
            valid_pts["total_points"].notna()
            & np.isfinite(valid_pts["total_points"])
        ]

        assert len(valid_pts) == 0

    def test_infinite_points_excluded(self):
        """Teams with inf total_points should be excluded."""
        team_pts_df = pd.DataFrame({
            "team": ["TeamA", "TeamB"],
            "league": ["League1", "League1"],
            "season": ["2526", "2526"],
            "total_points": [80.0, np.inf],
        })
        valid_pts = team_pts_df.copy()
        valid_pts["total_points"] = pd.to_numeric(
            valid_pts["total_points"], errors="coerce"
        )
        valid_pts = valid_pts[
            valid_pts["total_points"].notna()
            & np.isfinite(valid_pts["total_points"])
        ]

        assert len(valid_pts) == 1
