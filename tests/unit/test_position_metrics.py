"""Unit tests for position_metrics module."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scoutfootball.evaluation.position_metrics import (
    POSITION_DIMENSIONS,
    POSITION_GROUP_MAP,
    PlayerPositionMetrics,
    PositionDimensionScore,
    compute_cross_position_ranking,
    compute_dimension_percentile,
    compute_player_position_metrics,
    compute_position_rankings,
    generate_explanation,
)

# ---------------------------------------------------------------------------
# POSITION_DIMENSIONS structure
# ---------------------------------------------------------------------------

class TestPositionDimensions:
    """Tests for the POSITION_DIMENSIONS constant."""

    EXPECTED_POSITIONS = {"GK", "CB", "FB", "DM", "CM", "AM", "W", "ST"}

    def test_all_eight_positions_defined(self) -> None:
        assert set(POSITION_DIMENSIONS.keys()) == self.EXPECTED_POSITIONS

    @pytest.mark.parametrize("position", list(EXPECTED_POSITIONS))
    def test_each_position_has_3_to_6_dimensions(self, position: str) -> None:
        dims = POSITION_DIMENSIONS[position]
        assert 3 <= len(dims) <= 6

    @pytest.mark.parametrize("position", list(EXPECTED_POSITIONS))
    def test_each_dimension_has_required_keys(self, position: str) -> None:
        for dim_key, dim_cfg in POSITION_DIMENSIONS[position].items():
            assert "label" in dim_cfg, f"{position}.{dim_key} missing 'label'"
            assert "columns" in dim_cfg, f"{position}.{dim_key} missing 'columns'"
            assert "direction" in dim_cfg, f"{position}.{dim_key} missing 'direction'"
            assert isinstance(dim_cfg["columns"], list)
            assert len(dim_cfg["columns"]) >= 1

    @pytest.mark.parametrize("position", list(EXPECTED_POSITIONS))
    def test_each_position_has_availability(self, position: str) -> None:
        dims = POSITION_DIMENSIONS[position]
        assert "availability" in dims, f"{position} missing 'availability' dimension"


class TestPositionGroupMap:
    """Tests for the POSITION_GROUP_MAP constant."""

    def test_coarse_groups_map(self) -> None:
        assert POSITION_GROUP_MAP["DF"] == "CB"
        assert POSITION_GROUP_MAP["MF"] == "CM"
        assert POSITION_GROUP_MAP["FW"] == "ST"

    def test_fine_groups_identity(self) -> None:
        for pos in ("GK", "CB", "FB", "DM", "CM", "AM", "W", "ST"):
            assert POSITION_GROUP_MAP[pos] == pos


# ---------------------------------------------------------------------------
# compute_dimension_percentile
# ---------------------------------------------------------------------------

class TestComputeDimensionPercentile:

    @pytest.fixture()
    def sample_pool(self) -> pd.DataFrame:
        rng = np.random.default_rng(42)
        return pd.DataFrame({
            "goals": rng.uniform(0, 20, 100),
            "npxg": rng.uniform(0, 15, 100),
            "minutes_played": rng.uniform(100, 3000, 100),
            "league_strength": rng.uniform(0.3, 1.0, 100),
        })

    def test_returns_value_in_0_100_range(self, sample_pool: pd.DataFrame) -> None:
        player = pd.Series({"goals": 10.0, "npxg": 8.0})
        dim_cfg = {"columns": ["goals", "npxg"], "direction": "higher_better"}
        pct = compute_dimension_percentile(sample_pool, dim_cfg, player)
        assert 0.0 <= pct <= 100.0

    def test_top_player_high_percentile(self, sample_pool: pd.DataFrame) -> None:
        player = pd.Series({"goals": 100.0, "npxg": 100.0})
        dim_cfg = {"columns": ["goals", "npxg"], "direction": "higher_better"}
        pct = compute_dimension_percentile(sample_pool, dim_cfg, player)
        assert pct >= 90.0

    def test_bottom_player_low_percentile(self, sample_pool: pd.DataFrame) -> None:
        player = pd.Series({"goals": -1.0, "npxg": -1.0})
        dim_cfg = {"columns": ["goals", "npxg"], "direction": "higher_better"}
        pct = compute_dimension_percentile(sample_pool, dim_cfg, player)
        assert pct <= 10.0

    def test_missing_columns_return_50(self, sample_pool: pd.DataFrame) -> None:
        player = pd.Series({"goals": 10.0})
        dim_cfg = {"columns": ["nonexistent_col"], "direction": "higher_better"}
        pct = compute_dimension_percentile(sample_pool, dim_cfg, player)
        assert pct == 50.0

    def test_nan_player_value_skipped(self, sample_pool: pd.DataFrame) -> None:
        player = pd.Series({"goals": float("nan"), "npxg": 8.0})
        dim_cfg = {"columns": ["goals", "npxg"], "direction": "higher_better"}
        pct = compute_dimension_percentile(sample_pool, dim_cfg, player)
        # Should only use npxg, still in range
        assert 0.0 <= pct <= 100.0

    def test_empty_pool_returns_50(self) -> None:
        empty_pool = pd.DataFrame({"goals": pd.Series(dtype=float)})
        player = pd.Series({"goals": 10.0})
        dim_cfg = {"columns": ["goals"], "direction": "higher_better"}
        pct = compute_dimension_percentile(empty_pool, dim_cfg, player)
        assert pct == 50.0


# ---------------------------------------------------------------------------
# compute_player_position_metrics
# ---------------------------------------------------------------------------

class TestComputePlayerPositionMetrics:

    @pytest.fixture()
    def st_pool(self) -> pd.DataFrame:
        rng = np.random.default_rng(123)
        n = 50
        return pd.DataFrame({
            "player_name": [f"ST-{i}" for i in range(n)],
            "position_group": ["ST"] * n,
            "goals": rng.uniform(0, 25, n),
            "npxg": rng.uniform(0, 18, n),
            "finishing_shrunk": rng.uniform(0, 1, n),
            "progressive_carries": rng.uniform(0, 50, n),
            "dribbles_completed": rng.uniform(0, 30, n),
            "minutes_played": rng.uniform(100, 3000, n),
            "matches_played": rng.uniform(5, 38, n),
            "league_strength": rng.uniform(0.3, 1.0, n),
        })

    def test_returns_correct_structure(self, st_pool: pd.DataFrame) -> None:
        player = st_pool.iloc[0]
        result = compute_player_position_metrics(player, st_pool)
        assert isinstance(result, PlayerPositionMetrics)
        assert isinstance(result.dimensions, tuple)
        assert all(isinstance(d, PositionDimensionScore) for d in result.dimensions)
        assert isinstance(result.overall_percentile, float)
        assert isinstance(result.explanation, str)

    def test_position_resolved(self, st_pool: pd.DataFrame) -> None:
        player = st_pool.iloc[0]
        result = compute_player_position_metrics(player, st_pool)
        assert result.position == "ST"

    def test_position_override(self, st_pool: pd.DataFrame) -> None:
        player = st_pool.iloc[0].copy()
        result = compute_player_position_metrics(player, st_pool, position="CM")
        assert result.position == "CM"

    def test_coarse_position_mapped(self) -> None:
        pool = pd.DataFrame({
            "player_name": ["A", "B"],
            "position_group": ["FW", "FW"],
            "goals": [5.0, 10.0],
            "npxg": [3.0, 7.0],
            "finishing_shrunk": [0.3, 0.6],
            "progressive_carries": [10.0, 20.0],
            "dribbles_completed": [5.0, 15.0],
            "minutes_played": [1000.0, 2000.0],
            "matches_played": [20.0, 30.0],
            "league_strength": [0.5, 0.8],
        })
        player = pool.iloc[0]
        result = compute_player_position_metrics(player, pool)
        # FW maps to ST
        assert result.position == "ST"

    def test_overall_percentile_in_range(self, st_pool: pd.DataFrame) -> None:
        player = st_pool.iloc[0]
        result = compute_player_position_metrics(player, st_pool)
        assert 0.0 <= result.overall_percentile <= 100.0

    def test_dimension_percentiles_in_range(self, st_pool: pd.DataFrame) -> None:
        player = st_pool.iloc[0]
        result = compute_player_position_metrics(player, st_pool)
        for dim in result.dimensions:
            assert 0.0 <= dim.percentile <= 100.0

    def test_unknown_position_falls_back(self) -> None:
        pool = pd.DataFrame({
            "player_name": ["X"],
            "position_group": ["UNKNOWN"],
            "goals": [5.0],
        })
        player = pool.iloc[0]
        result = compute_player_position_metrics(player, pool)
        # Unknown position has no dimension definitions
        assert result.position == "UNKNOWN"
        assert len(result.dimensions) == 0
        assert result.overall_percentile == 50.0


# ---------------------------------------------------------------------------
# generate_explanation
# ---------------------------------------------------------------------------

class TestGenerateExplanation:

    def test_produces_chinese_text(self) -> None:
        scores = (
            PositionDimensionScore("finishing", "终结", 92.0, 0.8, False),
            PositionDimensionScore("availability", "出勤", 45.0, 1200.0, False),
        )
        text = generate_explanation("Test Player", "ST", scores)
        # Should contain Chinese characters
        assert any("\u4e00" <= c <= "\u9fff" for c in text)

    def test_includes_percentile_tier(self) -> None:
        scores = (
            PositionDimensionScore("finishing", "终结", 92.0, 0.8, False),
            PositionDimensionScore("availability", "出勤", 45.0, 1200.0, False),
        )
        text = generate_explanation("Test Player", "ST", scores)
        assert "前 10%" in text
        assert "前 75%" in text

    def test_empty_scores(self) -> None:
        text = generate_explanation("Nobody", "GK", ())
        assert "无可用" in text

    def test_missing_dimension_labeled(self) -> None:
        scores = (
            PositionDimensionScore("xT", "威胁", 50.0, None, True),
        )
        text = generate_explanation("Player", "CM", scores)
        assert "缺失" in text

    def test_all_high_percentiles(self) -> None:
        scores = (
            PositionDimensionScore("finishing", "终结", 95.0, 0.9, False),
            PositionDimensionScore("creation", "创造", 88.0, 0.7, False),
        )
        text = generate_explanation("Star", "AM", scores)
        assert "强项" in text

    def test_all_low_percentiles(self) -> None:
        scores = (
            PositionDimensionScore("defending", "防守", 10.0, 0.1, False),
            PositionDimensionScore("availability", "出勤", 20.0, 500.0, False),
        )
        text = generate_explanation("Bench", "CB", scores)
        assert "不足" in text


# ---------------------------------------------------------------------------
# compute_position_rankings
# ---------------------------------------------------------------------------

class TestComputePositionRankings:

    @pytest.fixture()
    def feature_matrix(self) -> pd.DataFrame:
        rng = np.random.default_rng(99)
        n = 30
        return pd.DataFrame({
            "player_name": [f"P{i}" for i in range(n)],
            "team_name": [f"T{i % 5}" for i in range(n)],
            "position_group": (["ST"] * 10 + ["CB"] * 10 + ["CM"] * 10),
            "goals": rng.uniform(0, 15, n),
        })

    def test_groups_by_position(self, feature_matrix: pd.DataFrame) -> None:
        ratings = pd.Series(np.random.default_rng(7).uniform(50, 100, 30))
        result = compute_position_rankings(feature_matrix, ratings)
        assert "ST" in result
        assert "CB" in result
        assert "CM" in result

    def test_each_group_has_correct_count(self, feature_matrix: pd.DataFrame) -> None:
        ratings = pd.Series(np.random.default_rng(7).uniform(50, 100, 30))
        result = compute_position_rankings(feature_matrix, ratings)
        assert len(result["ST"]) == 10
        assert len(result["CB"]) == 10
        assert len(result["CM"]) == 10

    def test_position_percentile_in_range(self, feature_matrix: pd.DataFrame) -> None:
        ratings = pd.Series(np.random.default_rng(7).uniform(50, 100, 30))
        result = compute_position_rankings(feature_matrix, ratings)
        for _pos, df in result.items():
            assert (df["position_percentile"] >= 0).all()
            assert (df["position_percentile"] <= 100).all()

    def test_empty_input(self) -> None:
        result = compute_position_rankings(pd.DataFrame(), pd.Series(dtype=float))
        assert result == {}

    def test_coarse_position_mapped(self) -> None:
        fm = pd.DataFrame({
            "player_name": ["A", "B", "C"],
            "team_name": ["T1", "T1", "T1"],
            "position_group": ["FW", "DF", "MF"],
            "rating": [80.0, 70.0, 60.0],
        })
        ratings = pd.Series([80.0, 70.0, 60.0])
        result = compute_position_rankings(fm, ratings)
        # FW -> ST, DF -> CB, MF -> CM
        assert "ST" in result
        assert "CB" in result
        assert "CM" in result


# ---------------------------------------------------------------------------
# compute_cross_position_ranking
# ---------------------------------------------------------------------------

class TestComputeCrossPositionRanking:

    @pytest.fixture()
    def feature_matrix(self) -> pd.DataFrame:
        rng = np.random.default_rng(55)
        n = 20
        return pd.DataFrame({
            "player_name": [f"P{i}" for i in range(n)],
            "team_name": [f"T{i % 4}" for i in range(n)],
            "position_group": (["ST"] * 10 + ["CB"] * 10),
            "rating": rng.uniform(50, 100, n),
        })

    def test_includes_all_players(self, feature_matrix: pd.DataFrame) -> None:
        ratings = feature_matrix["rating"]
        result = compute_cross_position_ranking(feature_matrix, ratings)
        assert len(result) == 20

    def test_has_required_columns(self, feature_matrix: pd.DataFrame) -> None:
        ratings = feature_matrix["rating"]
        result = compute_cross_position_ranking(feature_matrix, ratings)
        for col in ("player_name", "position_group", "rating", "overall_rank"):
            assert col in result.columns

    def test_sorted_by_rank(self, feature_matrix: pd.DataFrame) -> None:
        ratings = feature_matrix["rating"]
        result = compute_cross_position_ranking(feature_matrix, ratings)
        ranks = result["overall_rank"].tolist()
        assert ranks == sorted(ranks)

    def test_empty_input(self) -> None:
        result = compute_cross_position_ranking(pd.DataFrame(), pd.Series(dtype=float))
        assert result.empty

    def test_includes_position_labels(self, feature_matrix: pd.DataFrame) -> None:
        ratings = feature_matrix["rating"]
        result = compute_cross_position_ranking(feature_matrix, ratings)
        positions = set(result["position_group"].unique())
        assert "ST" in positions
        assert "CB" in positions


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_all_nan_columns_in_pool(self) -> None:
        pool = pd.DataFrame({
            "goals": [float("nan")] * 10,
            "npxg": [float("nan")] * 10,
            "player_name": [f"P{i}" for i in range(10)],
            "position_group": ["ST"] * 10,
            "minutes_played": [1000.0] * 10,
            "matches_played": [20.0] * 10,
        })
        player = pool.iloc[0]
        result = compute_player_position_metrics(player, pool)
        # Dimensions with all-NaN columns should get 50.0 percentile
        for dim in result.dimensions:
            if dim.is_missing:
                assert dim.percentile == 50.0

    def test_single_player_pool(self) -> None:
        pool = pd.DataFrame({
            "player_name": ["Only"],
            "position_group": ["CM"],
            "goals": [5.0],
            "assists": [3.0],
            "xa": [2.0],
            "key_passes": [10.0],
            "progressive_passes": [20.0],
            "progressive_carries": [15.0],
            "passes_completed_pct": [85.0],
            "touches": [1000.0],
            "minutes_played": [2000.0],
            "matches_played": [30.0],
        })
        player = pool.iloc[0]
        result = compute_player_position_metrics(player, pool)
        # With only 1 player, (col < val).mean() = 0.0 for all
        assert result.overall_percentile == 0.0

    def test_position_with_no_matching_dimensions(self) -> None:
        pool = pd.DataFrame({
            "player_name": ["X"],
            "position_group": ["GK"],
            "goals": [0.0],
        })
        player = pool.iloc[0]
        result = compute_player_position_metrics(player, pool)
        # GK dimensions reference saves, psxg_minus_ga etc. which don't exist
        assert all(d.is_missing for d in result.dimensions)
