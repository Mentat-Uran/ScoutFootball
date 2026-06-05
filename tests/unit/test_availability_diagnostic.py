"""Unit tests for availability_diagnostic module."""

from __future__ import annotations

import numpy as np
import pandas as pd

from scoutlab.evaluation.availability_diagnostic import (
    AvailabilityDiagnosticReport,
    compute_permutation_importance,
    compute_position_availability_weights,
    compute_team_aggregation_weights,
    generate_availability_diagnostic,
    identify_availability_driven_players,
    save_availability_diagnostic,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_feature_matrix(n: int = 100, seed: int = 42) -> pd.DataFrame:
    """Create a synthetic feature matrix with availability and performance features."""
    rng = np.random.default_rng(seed)
    positions = rng.choice(["GK", "DF", "MF", "FW"], size=n)
    return pd.DataFrame(
        {
            "minutes_played": rng.uniform(100, 3000, size=n),
            "started": rng.integers(5, 35, size=n),
            "matches_played": rng.integers(10, 38, size=n),
            "goals": rng.integers(0, 20, size=n),
            "assists": rng.integers(0, 15, size=n),
            "shots": rng.integers(0, 80, size=n),
            "passes": rng.integers(100, 2000, size=n),
            "tackles": rng.integers(10, 100, size=n),
            "position_group": positions,
            "player_name": [f"Player_{i}" for i in range(n)],
            "team_name": rng.choice(["Team_A", "Team_B", "Team_C", "Team_D"], size=n),
        },
    )


def _make_ratings(n: int = 100, seed: int = 42) -> pd.Series:
    """Create synthetic ratings that are partially driven by availability."""
    rng = np.random.default_rng(seed)
    # Make ratings strongly correlated with minutes (simulating the shortcut)
    minutes = rng.uniform(100, 3000, size=n)
    noise = rng.normal(0, 5, size=n)
    ratings = 50 + 0.01 * minutes + noise
    return pd.Series(ratings, name="rating")


# ---------------------------------------------------------------------------
# compute_permutation_importance
# ---------------------------------------------------------------------------


class TestComputePermutationImportance:
    def test_returns_correct_structure(self) -> None:
        fm = _make_feature_matrix()
        ratings = _make_ratings()
        numeric_cols = ["minutes_played", "started", "matches_played", "goals", "assists", "shots"]
        result = compute_permutation_importance(fm[numeric_cols], ratings)

        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ["feature", "importance", "is_availability"]
        assert len(result) == len(numeric_cols)

    def test_availability_features_flagged(self) -> None:
        fm = _make_feature_matrix()
        ratings = _make_ratings()
        numeric_cols = ["minutes_played", "started", "matches_played", "goals", "assists"]
        result = compute_permutation_importance(fm[numeric_cols], ratings)

        avail_features = result[result["is_availability"]]
        non_avail_features = result[~result["is_availability"]]
        assert len(avail_features) == 3
        assert len(non_avail_features) == 2

    def test_empty_dataframe_returns_empty(self) -> None:
        result = compute_permutation_importance(
            pd.DataFrame(), pd.Series(dtype=float),
        )
        assert result.empty
        assert list(result.columns) == ["feature", "importance", "is_availability"]

    def test_importance_sorted_descending(self) -> None:
        fm = _make_feature_matrix()
        ratings = _make_ratings()
        numeric_cols = ["minutes_played", "started", "matches_played", "goals", "assists"]
        result = compute_permutation_importance(fm[numeric_cols], ratings)

        importances = result["importance"].values
        assert all(importances[i] >= importances[i + 1] for i in range(len(importances) - 1))

    def test_all_zero_ratings(self) -> None:
        fm = _make_feature_matrix()
        ratings = pd.Series(0.0, index=fm.index)
        numeric_cols = ["minutes_played", "goals"]
        result = compute_permutation_importance(fm[numeric_cols], ratings)
        # Should return a DataFrame even with zero ratings
        assert isinstance(result, pd.DataFrame)


# ---------------------------------------------------------------------------
# compute_position_availability_weights
# ---------------------------------------------------------------------------


class TestComputePositionAvailabilityWeights:
    def test_groups_by_position_correctly(self) -> None:
        fm = _make_feature_matrix()
        ratings = _make_ratings()
        result = compute_position_availability_weights(fm, ratings)

        assert isinstance(result, pd.DataFrame)
        assert "position" in result.columns
        assert "availability_correlation" in result.columns
        assert "non_availability_correlation" in result.columns
        # Should have at least some positions
        assert len(result) > 0

    def test_missing_position_column_returns_empty(self) -> None:
        fm = _make_feature_matrix().drop(columns=["position_group"])
        ratings = _make_ratings()
        result = compute_position_availability_weights(fm, ratings)
        assert result.empty

    def test_empty_dataframe_returns_empty(self) -> None:
        result = compute_position_availability_weights(
            pd.DataFrame(), pd.Series(dtype=float),
        )
        assert result.empty

    def test_correlations_are_non_negative(self) -> None:
        fm = _make_feature_matrix()
        ratings = _make_ratings()
        result = compute_position_availability_weights(fm, ratings)

        if not result.empty:
            assert (result["availability_correlation"] >= 0).all()
            assert (result["non_availability_correlation"] >= 0).all()


# ---------------------------------------------------------------------------
# compute_team_aggregation_weights
# ---------------------------------------------------------------------------


class TestComputeTeamAggregationWeights:
    def test_basic_team_aggregation(self) -> None:
        data = pd.DataFrame(
            {
                "team_name": ["A", "A", "B", "B", "B"],
                "rating": [80.0, 75.0, 70.0, 65.0, 60.0],
                "minutes_played": [2000, 1500, 1800, 1200, 600],
            },
        )
        result = compute_team_aggregation_weights(data)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert "team" in result.columns
        assert "top_player_minute_share" in result.columns
        assert "rating_std" in result.columns
        assert "n_players" in result.columns

    def test_single_player_team(self) -> None:
        data = pd.DataFrame(
            {
                "team_name": ["A"],
                "rating": [80.0],
                "minutes_played": [2000],
            },
        )
        result = compute_team_aggregation_weights(data)
        assert len(result) == 1
        assert result.iloc[0]["top_player_minute_share"] == 1.0
        assert result.iloc[0]["rating_std"] == 0.0
        assert result.iloc[0]["n_players"] == 1

    def test_missing_columns_returns_empty(self) -> None:
        data = pd.DataFrame({"team_name": ["A"], "rating": [80.0]})
        result = compute_team_aggregation_weights(data)
        assert result.empty

    def test_empty_dataframe_returns_empty(self) -> None:
        result = compute_team_aggregation_weights(
            pd.DataFrame(columns=["team_name", "rating", "minutes_played"]),
        )
        assert result.empty

    def test_top_player_share_calculation(self) -> None:
        data = pd.DataFrame(
            {
                "team_name": ["A", "A"],
                "rating": [80.0, 70.0],
                "minutes_played": [1800, 600],
            },
        )
        result = compute_team_aggregation_weights(data)
        team_a = result[result["team"] == "A"].iloc[0]
        expected_share = 1800 / 2400
        assert abs(team_a["top_player_minute_share"] - expected_share) < 1e-9


# ---------------------------------------------------------------------------
# identify_availability_driven_players
# ---------------------------------------------------------------------------


class TestIdentifyAvailabilityDrivenPlayers:
    def test_identifies_high_availability_players(self) -> None:
        fm = _make_feature_matrix()
        # Create ratings strongly driven by minutes
        ratings = 50 + 0.02 * fm["minutes_played"] + np.random.default_rng(42).normal(0, 2, len(fm))
        ratings = pd.Series(ratings.values, index=fm.index, name="rating")

        result = identify_availability_driven_players(fm, ratings, threshold=0.30)

        assert isinstance(result, pd.DataFrame)
        if not result.empty:
            assert "player_name" in result.columns
            assert "team_name" in result.columns
            assert "position_group" in result.columns
            assert "rating" in result.columns
            assert "availability_contribution_ratio" in result.columns

    def test_empty_feature_matrix_returns_empty(self) -> None:
        result = identify_availability_driven_players(
            pd.DataFrame(), pd.Series(dtype=float),
        )
        assert result.empty

    def test_threshold_filters_players(self) -> None:
        fm = _make_feature_matrix()
        ratings = _make_ratings()

        result_low = identify_availability_driven_players(fm, ratings, threshold=0.01)
        result_high = identify_availability_driven_players(fm, ratings, threshold=0.99)

        # Lower threshold should find at least as many as higher threshold
        assert len(result_low) >= len(result_high)

    def test_top_n_limits_results(self) -> None:
        fm = _make_feature_matrix()
        ratings = _make_ratings()

        result = identify_availability_driven_players(fm, ratings, threshold=0.0, top_n=5)
        assert len(result) <= 5


# ---------------------------------------------------------------------------
# generate_availability_diagnostic
# ---------------------------------------------------------------------------


class TestGenerateAvailabilityDiagnostic:
    def test_handles_missing_files_gracefully(self, tmp_path) -> None:
        """Test with non-existent file paths."""
        from scoutlab.config import PlatformSettings

        settings = PlatformSettings.from_root(tmp_path)
        report = generate_availability_diagnostic(settings=settings)

        assert isinstance(report, AvailabilityDiagnosticReport)
        assert report.permutation_importance.empty
        assert report.position_availability_weights.empty
        assert report.team_aggregation_weights.empty
        assert report.availability_driven_players.empty
        assert "reason" in report.summary

    def test_with_feature_matrix_only(self, tmp_path) -> None:
        """Test when only the feature matrix file exists."""
        from scoutlab.config import PlatformSettings

        settings = PlatformSettings.from_root(tmp_path)

        # Create a feature matrix file
        fm = _make_feature_matrix()
        fm_dir = settings.gold_root / "feature_store"
        fm_dir.mkdir(parents=True, exist_ok=True)
        fm["rating"] = _make_ratings().values
        fm.to_parquet(fm_dir / "rating_feature_matrix.parquet", index=False)

        report = generate_availability_diagnostic(settings=settings)
        assert isinstance(report, AvailabilityDiagnosticReport)
        # Should have some permutation importance results
        assert isinstance(report.permutation_importance, pd.DataFrame)


# ---------------------------------------------------------------------------
# save_availability_diagnostic
# ---------------------------------------------------------------------------


class TestSaveAvailabilityDiagnostic:
    def test_saves_all_components(self, tmp_path) -> None:
        report = AvailabilityDiagnosticReport(
            permutation_importance=pd.DataFrame(
                {
                    "feature": ["minutes_played"],
                    "importance": [0.5],
                    "is_availability": [True],
                },
            ),
            position_availability_weights=pd.DataFrame(
                {
                    "position": ["FW"],
                    "availability_correlation": [0.6],
                    "non_availability_correlation": [0.3],
                },
            ),
            team_aggregation_weights=pd.DataFrame(
                {
                    "team": ["A"],
                    "top_player_minute_share": [0.4],
                    "rating_std": [5.0],
                    "n_players": [11],
                },
            ),
            availability_driven_players=pd.DataFrame(
                {
                    "player_name": ["Player X"],
                    "team_name": ["Team A"],
                    "position_group": ["FW"],
                    "rating": [85.0],
                    "availability_contribution_ratio": [0.7],
                },
            ),
            summary={"availability_importance_share": 0.5},
        )

        result = save_availability_diagnostic(report, str(tmp_path / "diagnostic"))

        assert "ok" in result
        assert (tmp_path / "diagnostic" / "permutation_importance.parquet").exists()
        assert (tmp_path / "diagnostic" / "position_availability_weights.parquet").exists()
        assert (tmp_path / "diagnostic" / "team_aggregation_weights.parquet").exists()
        assert (tmp_path / "diagnostic" / "availability_driven_players.parquet").exists()
        assert (tmp_path / "diagnostic" / "summary.json").exists()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_nan_ratings_handled(self) -> None:
        fm = _make_feature_matrix()
        ratings = pd.Series([np.nan] * len(fm), index=fm.index)
        numeric_cols = ["minutes_played", "goals"]
        result = compute_permutation_importance(fm[numeric_cols], ratings)
        # Should not crash, may return empty
        assert isinstance(result, pd.DataFrame)

    def test_constant_feature_column_dropped(self) -> None:
        fm = pd.DataFrame(
            {
                "minutes_played": np.random.default_rng(42).uniform(100, 3000, size=50),
                "constant_col": 1.0,
                "goals": np.random.default_rng(42).integers(0, 10, size=50),
            },
        )
        ratings = 50 + 0.01 * fm["minutes_played"]
        result = compute_permutation_importance(fm, ratings)
        # constant_col should be excluded
        assert "constant_col" not in result["feature"].values

    def test_misaligned_indices(self) -> None:
        fm = _make_feature_matrix()
        ratings = _make_ratings()
        # Shift ratings index
        ratings.index = range(50, 50 + len(ratings))
        numeric_cols = ["minutes_played", "goals"]
        result = compute_permutation_importance(fm[numeric_cols], ratings)
        # Should handle gracefully (empty intersection)
        assert isinstance(result, pd.DataFrame)
