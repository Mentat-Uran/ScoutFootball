"""Unit tests for the PRS-2 B0 raw_percentile baseline.

Covers dimension definitions for every role, the legacy and vectorised
percentile paths, the cross-check between them, confidence classification
(high/medium/low), missing-data handling, bootstrap rank intervals,
cohort filtering, and the public ``compute_b0_baseline`` entry point's
fail-closed and happy-path behaviour.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.baseline_b0 import (
    B0_DIMENSIONS,
    BASELINE_B0_SCHEMA,
    BASELINE_B0_VERSION,
    B0Dimension,
    B0DimensionScore,
    B0PlayerScore,
    B0RoleSummary,
    _bootstrap_rank_interval,
    _column_percentile,
    _dimension_percentile,
    _dimension_percentile_vectorised,
    _pool_column_arrays,
    _to_float,
    _vectorised_scores,
    _vectorised_scores_for_resample,
    compute_b0_baseline,
)
from scoutfootball.evaluation.cohort import CohortDefinition
from scoutfootball.evaluation.role_system import RoleFamily

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _write_rating_feature_matrix(
    settings: PlatformSettings, df: pd.DataFrame
) -> None:
    path = settings.gold_root / "feature_store" / "rating_feature_matrix.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def _make_feature_matrix_df(rows: list[dict] | None = None) -> pd.DataFrame:
    """Build a rating_feature_matrix DataFrame with columns B0 consumes."""
    if rows is None:
        rows = [
            # Two CBs with full data — distinct scores
            {
                "player_id": "u|1", "player_name": "CB-A", "season_id": "2425",
                "position_group": "CB", "source_name": "understat",
                "minutes_played": 2000, "starts": 22,
                "tackles": 30, "interceptions": 40, "passes": 1500,
                "goals": 1, "assists": 0, "npxg": 0.5, "xa": 0.2,
                "defense_missing": False, "possession_missing": False,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            },
            {
                "player_id": "u|2", "player_name": "CB-B", "season_id": "2425",
                "position_group": "CB", "source_name": "understat",
                "minutes_played": 1500, "starts": 17,
                "tackles": 20, "interceptions": 25, "passes": 1000,
                "goals": 0, "assists": 0, "npxg": 0.0, "xa": 0.0,
                "defense_missing": False, "possession_missing": False,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            },
            # One ST with full data
            {
                "player_id": "u|3", "player_name": "ST-A", "season_id": "2425",
                "position_group": "FW", "source_name": "understat",
                "minutes_played": 1800, "starts": 20,
                "tackles": 5, "interceptions": 5, "passes": 200,
                "goals": 20, "assists": 5, "npxg": 15.0, "xa": 4.0,
                "defense_missing": True, "possession_missing": True,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            },
            # One GK (availability-only)
            {
                "player_id": "u|4", "player_name": "GK-A", "season_id": "2425",
                "position_group": "GK", "source_name": "understat",
                "minutes_played": 2700, "starts": 30,
                "tackles": 0, "interceptions": 0, "passes": 0,
                "goals": 0, "assists": 0, "npxg": 0.0, "xa": 0.0,
                "defense_missing": True, "possession_missing": True,
                "xT_VAEP_missing": True, "goalkeeper_missing": False,
            },
            # One UNKNOWN position
            {
                "player_id": "u|5", "player_name": "UNK-A", "season_id": "2425",
                "position_group": "XYZ", "source_name": "understat",
                "minutes_played": 1000, "starts": 11,
                "tackles": 10, "interceptions": 10, "passes": 500,
                "goals": 0, "assists": 0, "npxg": 0.0, "xa": 0.0,
                "defense_missing": False, "possession_missing": False,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            },
        ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# B0Dimension and B0_DIMENSIONS
# ---------------------------------------------------------------------------


class TestB0DimensionDefinitions:
    def test_all_known_roles_have_dimensions(self) -> None:
        """Every RoleFamily except UNKNOWN must have a B0_DIMENSIONS entry."""
        for role in RoleFamily:
            if role == RoleFamily.UNKNOWN:
                assert role not in B0_DIMENSIONS
                continue
            assert role in B0_DIMENSIONS, f"missing dims for {role}"
            dims = B0_DIMENSIONS[role]
            assert len(dims) > 0, f"empty dims for {role}"

    def test_every_role_has_availability_dimension(self) -> None:
        """availability is the universal core dimension."""
        for role, dims in B0_DIMENSIONS.items():
            avail = [d for d in dims if d.key == "availability"]
            assert len(avail) == 1, f"{role}: expected one availability dim"
            assert avail[0].core is True, f"{role}: availability must be core"
            assert "minutes_played" in avail[0].columns
            assert "starts" in avail[0].columns

    def test_gk_is_availability_only(self) -> None:
        """GK must not consume tackles/interceptions or any outfield metric."""
        gk_dims = B0_DIMENSIONS[RoleFamily.GK]
        assert len(gk_dims) == 1
        assert gk_dims[0].key == "availability"
        for col in gk_dims[0].columns:
            assert col not in {"tackles", "interceptions", "passes",
                               "goals", "assists", "npxg", "xa"}

    def test_core_dimensions_exist_for_each_role(self) -> None:
        """Every role must have at least one core dimension (else every
        player would be confidence=low)."""
        for role, dims in B0_DIMENSIONS.items():
            core = [d for d in dims if d.core]
            assert len(core) >= 1, f"{role}: no core dimensions"

    def test_dimension_columns_are_known_columns(self) -> None:
        """All referenced columns must be in the known column set that
        rating_feature_matrix.parquet carries."""
        known = {
            "minutes_played", "starts",
            "tackles", "interceptions", "passes",
            "goals", "assists", "npxg", "xa",
        }
        for role, dims in B0_DIMENSIONS.items():
            for dim in dims:
                for col in dim.columns:
                    assert col in known, (
                        f"{role}.{dim.key}: unknown column {col!r}"
                    )

    def test_missing_flag_names_are_known(self) -> None:
        """missing_flag values must match the *_missing flag columns
        produced by rating_feature_matrix builders."""
        known_flags = {
            "", "defense_missing", "possession_missing",
            "xT_VAEP_missing", "goalkeeper_missing",
        }
        for role, dims in B0_DIMENSIONS.items():
            for dim in dims:
                assert dim.missing_flag in known_flags, (
                    f"{role}.{dim.key}: unknown missing_flag {dim.missing_flag!r}"
                )

    def test_dimension_is_frozen(self) -> None:
        d = B0Dimension(key="x", label="y", columns=("a",))
        with pytest.raises((AttributeError, TypeError)):
            d.key = "z"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _to_float
# ---------------------------------------------------------------------------


class TestToFloat:
    def test_int(self) -> None:
        assert _to_float(5) == 5.0

    def test_float(self) -> None:
        assert _to_float(3.14) == pytest.approx(3.14)

    def test_none(self) -> None:
        assert _to_float(None) is None

    def test_nan_float(self) -> None:
        assert _to_float(float("nan")) is None

    def test_bool_returns_none(self) -> None:
        """Booleans are not valid metric values."""
        assert _to_float(True) is None
        assert _to_float(False) is None

    def test_numeric_string(self) -> None:
        assert _to_float("12.5") == 12.5

    def test_non_numeric_string(self) -> None:
        assert _to_float("abc") is None

    def test_empty_string(self) -> None:
        assert _to_float("") is None


# ---------------------------------------------------------------------------
# _column_percentile
# ---------------------------------------------------------------------------


class TestColumnPercentile:
    def test_empty_pool_returns_neutral(self) -> None:
        assert _column_percentile(5.0, []) == 50.0

    def test_lowest_value_gets_zero(self) -> None:
        assert _column_percentile(1.0, [1.0, 2.0, 3.0]) == 0.0

    def test_highest_value_gets_100_minus_tie(self) -> None:
        # strict-less-than: 3.0 has 2 values below it → 2/3*100
        assert _column_percentile(3.0, [1.0, 2.0, 3.0]) == pytest.approx(200.0 / 3.0)

    def test_lower_better_inverts(self) -> None:
        # direction='lower_better': smaller is better, so the lowest value
        # has 0 below it but we invert → 100 - 0 = 100
        # Actually: 'lower_better' counts how many values are *greater*.
        # For 1.0 in [1,2,3]: 2 values greater → 2/3*100
        pct = _column_percentile(1.0, [1.0, 2.0, 3.0], "lower_better")
        assert pct == pytest.approx(200.0 / 3.0)

    def test_ties_get_same_percentile(self) -> None:
        pool = [5.0, 5.0, 5.0]
        # All three have 0 values strictly below → all get 0.0
        assert _column_percentile(5.0, pool) == 0.0


# ---------------------------------------------------------------------------
# _dimension_percentile (legacy path) vs _dimension_percentile_vectorised
# ---------------------------------------------------------------------------


class TestDimensionPercentileLegacy:
    def test_player_with_full_data(self) -> None:
        dim = B0Dimension(
            key="defending", label="D",
            columns=("tackles", "interceptions"), core=True,
        )
        player = {"tackles": 30, "interceptions": 40}
        pool = [
            {"tackles": 30, "interceptions": 40},
            {"tackles": 20, "interceptions": 25},
            {"tackles": 10, "interceptions": 15},
        ]
        score = _dimension_percentile(player, pool, dim)
        assert score.is_missing is False
        assert score.is_core is True
        # tackles: 2/3 below → 66.67; interceptions: 2/3 below → 66.67
        # mean = 66.67
        assert score.dimension_percentile == pytest.approx(200.0 / 3.0)
        assert "tackles" in score.column_percentiles
        assert "interceptions" in score.column_percentiles

    def test_player_with_missing_column(self) -> None:
        """If one column is missing for the player, the dimension
        percentile is the mean of available columns."""
        dim = B0Dimension(
            key="defending", label="D",
            columns=("tackles", "interceptions"), core=True,
        )
        player = {"tackles": 30}  # interceptions missing
        pool = [
            {"tackles": 30, "interceptions": 40},
            {"tackles": 20, "interceptions": 25},
        ]
        score = _dimension_percentile(player, pool, dim)
        assert score.is_missing is False
        assert "tackles" in score.columns_present
        assert "interceptions" in score.columns_missing
        # tackles only: 1/2 below → 50.0
        assert score.dimension_percentile == pytest.approx(50.0)

    def test_player_with_all_columns_missing(self) -> None:
        dim = B0Dimension(
            key="defending", label="D",
            columns=("tackles", "interceptions"), core=True,
        )
        player: dict = {}
        pool = [{"tackles": 30, "interceptions": 40}]
        score = _dimension_percentile(player, pool, dim)
        assert score.is_missing is True
        assert score.dimension_percentile == 50.0
        assert len(score.columns_present) == 0

    def test_pool_with_no_data_for_column(self) -> None:
        """If the pool has no values for a column, the column is treated
        as missing for the player even if the player has a value."""
        dim = B0Dimension(
            key="x", label="X", columns=("a",), core=True,
        )
        player = {"a": 5.0}
        pool = [{"a": None}, {"a": None}]
        score = _dimension_percentile(player, pool, dim)
        assert score.is_missing is True


class TestVectorisedMatchesLegacy:
    """Cross-check: the vectorised path produces the same dimension
    percentile as the legacy path."""

    def test_cross_check_on_synthetic_pool(self) -> None:
        dim = B0Dimension(
            key="defending", label="D",
            columns=("tackles", "interceptions"), core=True,
        )
        pool = [
            {"tackles": 30, "interceptions": 40},
            {"tackles": 20, "interceptions": 25},
            {"tackles": 10, "interceptions": 15},
            {"tackles": None, "interceptions": 50},
            {"tackles": 25, "interceptions": None},
        ]
        cols = ("tackles", "interceptions")
        arrays = _pool_column_arrays(pool, cols)
        for i, player_row in enumerate(pool):
            legacy = _dimension_percentile(player_row, pool, dim)
            vec = _dimension_percentile_vectorised(i, arrays, dim)
            assert vec.dimension_percentile == pytest.approx(
                legacy.dimension_percentile, rel=1e-9
            )
            assert vec.is_missing == legacy.is_missing
            assert set(vec.columns_present) == set(legacy.columns_present)


# ---------------------------------------------------------------------------
# _vectorised_scores
# ---------------------------------------------------------------------------


class TestVectorisedScores:
    def test_empty_pool(self) -> None:
        dims = B0_DIMENSIONS[RoleFamily.CB]
        out = _vectorised_scores([], dims)
        assert len(out) == 0

    def test_one_player_gets_neutral(self) -> None:
        """A single player has no one below them → percentiles are 0;
        but B0 score is mean of dimension percentiles."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        pool = [{
            "tackles": 30, "interceptions": 40, "passes": 100,
            "minutes_played": 2000, "starts": 22,
        }]
        out = _vectorised_scores(pool, dims)
        assert len(out) == 1
        # Only one value in pool → strict-less-than count is 0 for every
        # column → every column percentile is 0 → score is 0.
        assert out[0] == pytest.approx(0.0)

    def test_two_players_distinct_scores(self) -> None:
        dims = B0_DIMENSIONS[RoleFamily.CB]
        pool = [
            {"tackles": 30, "interceptions": 40, "passes": 100,
             "minutes_played": 2000, "starts": 22},
            {"tackles": 10, "interceptions": 15, "passes": 50,
             "minutes_played": 1000, "starts": 11},
        ]
        out = _vectorised_scores(pool, dims)
        assert len(out) == 2
        # Player 0 is better in every column → higher score.
        assert out[0] > out[1]

    def test_player_with_all_missing_gets_neutral_50(self) -> None:
        """A player with no available columns should get score 50.0
        (neutral placeholder), not 0.0."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        pool = [
            # Player 0 has all metrics missing
            {"tackles": None, "interceptions": None, "passes": None,
             "minutes_played": None, "starts": None},
            # Player 1 has data
            {"tackles": 30, "interceptions": 40, "passes": 100,
             "minutes_played": 2000, "starts": 22},
        ]
        out = _vectorised_scores(pool, dims)
        assert out[0] == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# _vectorised_scores_for_resample
# ---------------------------------------------------------------------------


class TestVectorisedScoresForResample:
    def test_identity_resample_matches_base(self) -> None:
        """Resampling with the identity permutation (indices 0..n-1)
        must reproduce the base scores."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        pool = [
            {"tackles": 30, "interceptions": 40, "passes": 100,
             "minutes_played": 2000, "starts": 22},
            {"tackles": 20, "interceptions": 25, "passes": 80,
             "minutes_played": 1500, "starts": 17},
            {"tackles": 10, "interceptions": 15, "passes": 50,
             "minutes_played": 1000, "starts": 11},
        ]
        cols = tuple(
            c for d in dims for c in d.columns
        )
        # Deduplicate preserving order
        seen: set[str] = set()
        unique_cols: list[str] = []
        for c in cols:
            if c not in seen:
                seen.add(c)
                unique_cols.append(c)
        base_arrays = _pool_column_arrays(pool, tuple(unique_cols))
        base_scores = _vectorised_scores(pool, dims)
        identity = np.arange(len(pool))
        resample_scores = _vectorised_scores_for_resample(
            base_arrays, dims, identity, len(pool)
        )
        np.testing.assert_allclose(resample_scores, base_scores, rtol=1e-9)


# ---------------------------------------------------------------------------
# _bootstrap_rank_interval
# ---------------------------------------------------------------------------


class TestBootstrapRankInterval:
    def test_small_pool_returns_none(self) -> None:
        """Pools below _MIN_BOOTSTRAP_POOL must return None for every
        player — small samples should not be reported as robust ranks."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        pool = [
            {"tackles": 30, "interceptions": 40, "passes": 100,
             "minutes_played": 2000, "starts": 22},
            {"tackles": 20, "interceptions": 25, "passes": 80,
             "minutes_played": 1500, "starts": 17},
        ]
        scores = _vectorised_scores(pool, dims).tolist()
        intervals = _bootstrap_rank_interval(
            pool, scores, dims, n_bootstrap=10, seed=42
        )
        assert intervals == [None, None]

    def test_zero_bootstrap_returns_none(self) -> None:
        dims = B0_DIMENSIONS[RoleFamily.CB]
        pool = [
            {"tackles": 30, "interceptions": 40, "passes": 100,
             "minutes_played": 2000, "starts": 22},
        ] * 15
        scores = _vectorised_scores(pool, dims).tolist()
        intervals = _bootstrap_rank_interval(
            pool, scores, dims, n_bootstrap=0, seed=42
        )
        assert all(i is None for i in intervals)

    def test_large_pool_returns_intervals(self) -> None:
        """A pool of 15 players with n_bootstrap=5 returns a
        (p5, p50, p95) tuple per player."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        # Build 15 distinct players
        pool = [
            {
                "tackles": 10 + i, "interceptions": 15 + i, "passes": 100 + i * 5,
                "minutes_played": 1000 + i * 100, "starts": 11 + i,
            }
            for i in range(15)
        ]
        scores = _vectorised_scores(pool, dims).tolist()
        intervals = _bootstrap_rank_interval(
            pool, scores, dims, n_bootstrap=5, seed=42
        )
        assert len(intervals) == 15
        for iv in intervals:
            assert iv is not None
            p5, p50, p95 = iv
            assert 1 <= p5 <= 15
            assert 1 <= p50 <= 15
            assert 1 <= p95 <= 15
            assert p5 <= p50 <= p95

    def test_seed_reproducibility(self) -> None:
        """Same seed → same intervals."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        pool = [
            {
                "tackles": 10 + i, "interceptions": 15 + i, "passes": 100 + i * 5,
                "minutes_played": 1000 + i * 100, "starts": 11 + i,
            }
            for i in range(15)
        ]
        scores = _vectorised_scores(pool, dims).tolist()
        iv1 = _bootstrap_rank_interval(pool, scores, dims, n_bootstrap=5, seed=99)
        iv2 = _bootstrap_rank_interval(pool, scores, dims, n_bootstrap=5, seed=99)
        assert iv1 == iv2


# ---------------------------------------------------------------------------
# B0PlayerScore and B0DimensionScore dataclasses
# ---------------------------------------------------------------------------


class TestB0DimensionScoreToDict:
    def test_to_dict_is_json_serializable(self) -> None:
        d = B0DimensionScore(
            dimension="defending", label="防守",
            columns_present=("tackles",), columns_missing=("interceptions",),
            column_percentiles={"tackles": 75.0},
            dimension_percentile=75.0,
            is_missing=False, is_core=True, missing_flag="defense_missing",
        )
        out = d.to_dict()
        json.dumps(out)  # must not raise
        assert out["dimension"] == "defending"
        assert out["dimension_percentile"] == 75.0
        assert out["columns_present"] == ["tackles"]


class TestB0PlayerScoreToDict:
    def test_to_dict_with_rank_interval(self) -> None:
        ps = B0PlayerScore(
            canonical_player_id="cid-1", player_name="P1", season_id="2425",
            role_family="CB", score=72.5, rank_in_role=3, role_pool_size=20,
            rank_p5=2, rank_p50=3, rank_p95=5,
            confidence="high", missing_reason="",
            core_dimensions_used=2, core_dimensions_total=2,
            dimensions=(), cross_position_comparable=False,
        )
        out = ps.to_dict()
        json.dumps(out)
        assert out["score"] == 72.5
        assert out["rank_interval"] == {"p5": 2, "p50": 3, "p95": 5}
        assert out["cross_position_comparable"] is False

    def test_to_dict_without_rank_interval(self) -> None:
        ps = B0PlayerScore(
            canonical_player_id="cid-1", player_name="P1", season_id="2425",
            role_family="CB", score=50.0, rank_in_role=None, role_pool_size=5,
            rank_p5=None, rank_p50=None, rank_p95=None,
            confidence="low", missing_reason="all missing",
            core_dimensions_used=0, core_dimensions_total=2,
            dimensions=(), cross_position_comparable=False,
        )
        out = ps.to_dict()
        assert out["rank_interval"] is None
        assert out["confidence"] == "low"


class TestB0RoleSummaryToDict:
    def test_to_dict(self) -> None:
        rs = B0RoleSummary(
            role_family="CB", member_count=20,
            high_confidence_count=18, medium_confidence_count=2,
            low_confidence_count=0,
            score_min=10.0, score_median=50.0, score_max=90.0,
            dimensions_available=("defending", "possession", "availability"),
        )
        out = rs.to_dict()
        json.dumps(out)
        assert out["confidence_counts"] == {"high": 18, "medium": 2, "low": 0}
        assert out["dimensions_available"] == [
            "defending", "possession", "availability"
        ]


# ---------------------------------------------------------------------------
# compute_b0_baseline — fail-closed behaviour
# ---------------------------------------------------------------------------


class TestComputeB0BaselineFailClosed:
    def test_missing_feature_matrix_returns_unavailable(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_b0_baseline(settings=settings)
        assert rep["schema"] == BASELINE_B0_SCHEMA
        assert rep["schema_version"] == BASELINE_B0_VERSION
        assert rep["status"] == "unavailable"
        assert "rating_feature_matrix" in rep["evidence"]["reason"]
        assert len(rep["limitations"]) > 0

    def test_empty_feature_matrix_returns_unavailable(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, pd.DataFrame({"player_id": []}))
        rep = compute_b0_baseline(settings=settings)
        assert rep["status"] == "unavailable"
        assert "empty" in rep["evidence"]["reason"]


# ---------------------------------------------------------------------------
# compute_b0_baseline — happy path
# ---------------------------------------------------------------------------


class TestComputeB0BaselineHappyPath:
    def test_status_ok(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b0_baseline(settings=settings, n_bootstrap=5)
        assert rep["status"] == "ok"
        assert rep["schema"] == BASELINE_B0_SCHEMA
        assert rep["schema_version"] == BASELINE_B0_VERSION
        assert "generated_at" in rep

    def test_total_players_scored(self, tmp_path: Path) -> None:
        """UNKNOWN rows are not scored but counted in by_role_family."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b0_baseline(settings=settings, n_bootstrap=5)
        # 5 rows total: 2 CB + 1 ST + 1 GK + 1 UNKNOWN
        # Scored = 4 (UNKNOWN excluded)
        assert rep["evidence"]["total_players_scored"] == 4
        assert rep["evidence"]["by_role_family"].get("UNKNOWN") == 1

    def test_role_summaries_present(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b0_baseline(settings=settings, n_bootstrap=5)
        summaries = rep["evidence"]["role_summaries"]
        roles = {s["role_family"] for s in summaries}
        assert "CB" in roles
        assert "ST" in roles
        assert "GK" in roles
        # UNKNOWN should not have a summary (not scored)
        assert "UNKNOWN" not in roles

    def test_cross_position_comparable_false_for_all(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b0_baseline(settings=settings, n_bootstrap=5)
        for p in rep["evidence"]["players"]:
            assert p["cross_position_comparable"] is False

    def test_high_confidence_for_full_data_player(self, tmp_path: Path) -> None:
        """A CB with full data should have confidence='high'."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b0_baseline(settings=settings, n_bootstrap=5)
        cb_players = [p for p in rep["evidence"]["players"]
                      if p["role_family"] == "CB"]
        assert len(cb_players) == 2
        for p in cb_players:
            assert p["confidence"] == "high"
            assert p["missing_reason"] == ""

    def test_rank_in_role_indices_correct(self, tmp_path: Path) -> None:
        """Rank 1 is the highest score in the role."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b0_baseline(settings=settings, n_bootstrap=5)
        cb_players = sorted(
            [p for p in rep["evidence"]["players"] if p["role_family"] == "CB"],
            key=lambda p: p["rank_in_role"],
        )
        assert cb_players[0]["rank_in_role"] == 1
        assert cb_players[0]["score"] >= cb_players[1]["score"]
        # Pool size = 2
        assert cb_players[0]["role_pool_size"] == 2

    def test_small_pool_no_rank_interval(self, tmp_path: Path) -> None:
        """Pool size 2 < _MIN_BOOTSTRAP_POOL (10) → rank_interval is None."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b0_baseline(settings=settings, n_bootstrap=5)
        for p in rep["evidence"]["players"]:
            assert p["rank_interval"] is None

    def test_gk_role_is_availability_only(self, tmp_path: Path) -> None:
        """GK's B0 must only have an availability dimension."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b0_baseline(settings=settings, n_bootstrap=5)
        gk_players = [p for p in rep["evidence"]["players"]
                      if p["role_family"] == "GK"]
        assert len(gk_players) == 1
        dims = gk_players[0]["dimensions"]
        assert len(dims) == 1
        assert dims[0]["dimension"] == "availability"

    def test_canonical_player_id_fallback(self, tmp_path: Path) -> None:
        """When canonical_player_id column is missing, B0 falls back to
        unresolved:<source>:<player_id> per the PRS-1 contract."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b0_baseline(settings=settings, n_bootstrap=5)
        for p in rep["evidence"]["players"]:
            assert p["canonical_player_id"].startswith("unresolved:")

    def test_json_serializable(self, tmp_path: Path) -> None:
        """The full report must be JSON-serialisable for CLI output."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b0_baseline(settings=settings, n_bootstrap=5)
        json.dumps(rep, ensure_ascii=False)  # must not raise

    def test_limitations_non_empty(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b0_baseline(settings=settings, n_bootstrap=5)
        assert len(rep["limitations"]) >= 5

    def test_parameters_recorded(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b0_baseline(
            settings=settings, n_bootstrap=42, seed=12345
        )
        assert rep["parameters"]["n_bootstrap"] == 42
        assert rep["parameters"]["seed"] == 12345


# ---------------------------------------------------------------------------
# compute_b0_baseline — cohort filtering
# ---------------------------------------------------------------------------


def _write_player_match(settings: PlatformSettings, df: pd.DataFrame) -> None:
    path = settings.gold_root / "feature_store" / "player_match.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


class TestComputeB0BaselineCohort:
    def test_cohort_filter_restricts_membership(self, tmp_path: Path) -> None:
        """A cohort definition that requires resolved identity (with no
        registry configured) excludes all rows → scored=0."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        # preview_cohort reads player_match.parquet, so write that too.
        _write_player_match(settings, _make_feature_matrix_df())
        definition = CohortDefinition(
            name="empty", require_resolved_identity=True
        )
        rep = compute_b0_baseline(
            settings=settings, cohort_definition=definition, n_bootstrap=5
        )
        # All rows unresolved → cohort membership is empty → scored=0
        assert rep["status"] == "ok"
        assert rep["evidence"]["total_players_scored"] == 0


# ---------------------------------------------------------------------------
# compute_b0_baseline — missing-data scenarios
# ---------------------------------------------------------------------------


class TestComputeB0BaselineMissingData:
    def test_player_with_all_core_missing_gets_low_confidence(
        self, tmp_path: Path
    ) -> None:
        """A CB with defense_missing=True and no tackles/interceptions
        AND no minutes/starts should be confidence='low' with score 50."""
        settings = PlatformSettings.from_root(tmp_path)
        rows = [
            # CB with full data
            {
                "player_id": "u|1", "player_name": "CB-full", "season_id": "2425",
                "position_group": "CB", "source_name": "understat",
                "minutes_played": 2000, "starts": 22,
                "tackles": 30, "interceptions": 40, "passes": 1500,
                "goals": 1, "assists": 0, "npxg": 0.5, "xa": 0.2,
                "defense_missing": False, "possession_missing": False,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            },
            # CB with all metrics missing (all core dims missing)
            {
                "player_id": "u|2", "player_name": "CB-empty", "season_id": "2425",
                "position_group": "CB", "source_name": "understat",
                "minutes_played": None, "starts": None,
                "tackles": None, "interceptions": None, "passes": None,
                "goals": None, "assists": None, "npxg": None, "xa": None,
                "defense_missing": True, "possession_missing": True,
                "xT_VAEP_missing": True, "goalkeeper_missing": True,
            },
        ]
        _write_rating_feature_matrix(settings, pd.DataFrame(rows))
        rep = compute_b0_baseline(settings=settings, n_bootstrap=5)
        cb_players = [p for p in rep["evidence"]["players"]
                      if p["role_family"] == "CB"]
        # Find the empty player
        empty = [p for p in cb_players if p["player_name"] == "CB-empty"][0]
        assert empty["confidence"] == "low"
        assert empty["score"] == 50.0
        assert "全部核心维度缺失" in empty["missing_reason"]

    def test_player_with_one_core_missing_gets_medium_confidence(
        self, tmp_path: Path
    ) -> None:
        """A CM where possession is missing (core for CM) but availability
        is present should be confidence='medium'."""
        settings = PlatformSettings.from_root(tmp_path)
        rows = [
            # CM with possession missing (core for CM)
            {
                "player_id": "u|1", "player_name": "CM-mid", "season_id": "2425",
                "position_group": "MF", "source_name": "understat",
                "minutes_played": 2000, "starts": 22,
                "tackles": 30, "interceptions": 40,
                "passes": None,  # possession missing for CM
                "goals": 1, "assists": 0, "npxg": 0.5, "xa": 0.2,
                "defense_missing": False, "possession_missing": True,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            },
            # CM with full data
            {
                "player_id": "u|2", "player_name": "CM-full", "season_id": "2425",
                "position_group": "MF", "source_name": "understat",
                "minutes_played": 1500, "starts": 17,
                "tackles": 20, "interceptions": 25, "passes": 800,
                "goals": 0, "assists": 1, "npxg": 0.0, "xa": 1.5,
                "defense_missing": False, "possession_missing": False,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            },
        ]
        _write_rating_feature_matrix(settings, pd.DataFrame(rows))
        rep = compute_b0_baseline(settings=settings, n_bootstrap=5)
        cm_players = [p for p in rep["evidence"]["players"]
                      if p["role_family"] == "CM"]
        mid = [p for p in cm_players if p["player_name"] == "CM-mid"][0]
        assert mid["confidence"] == "medium"
        assert "控球" in mid["missing_reason"] or "possession" in mid["missing_reason"]


# ---------------------------------------------------------------------------
# compute_b0_baseline — feature_matrix parameter
# ---------------------------------------------------------------------------


class TestComputeB0BaselineFeatureMatrixParam:
    def test_accepts_preloaded_dataframe(self, tmp_path: Path) -> None:
        """feature_matrix parameter bypasses parquet loading."""
        settings = PlatformSettings.from_root(tmp_path)
        # Do not write the parquet — pass the DataFrame directly.
        df = _make_feature_matrix_df()
        rep = compute_b0_baseline(
            settings=settings, feature_matrix=df, n_bootstrap=5
        )
        assert rep["status"] == "ok"
        assert rep["evidence"]["total_players_scored"] == 4

    def test_canonical_player_id_column_used(self, tmp_path: Path) -> None:
        """If the feature matrix already has canonical_player_id, B0
        uses it instead of the unresolved fallback."""
        settings = PlatformSettings.from_root(tmp_path)
        df = _make_feature_matrix_df()
        df["canonical_player_id"] = df["player_id"].map(
            lambda pid: f"canonical:{pid}"
        )
        rep = compute_b0_baseline(
            settings=settings, feature_matrix=df, n_bootstrap=5
        )
        for p in rep["evidence"]["players"]:
            assert p["canonical_player_id"].startswith("canonical:")
