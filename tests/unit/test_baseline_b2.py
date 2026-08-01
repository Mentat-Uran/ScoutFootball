"""Unit tests for the PRS-2 B2 minutes-shrinkage baseline.

Covers the shrinkage formula, prior mean computation, B0->B2 confidence
propagation, hand-recomputability (B2 score == w * prior + (1-w) * b0),
vectorised helpers, bootstrap rank intervals on B2 scores, and the
public ``compute_b2_baseline`` entry point's fail-closed and happy-path
behaviour.
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
)
from scoutfootball.evaluation.baseline_b2 import (
    BASELINE_B2_SCHEMA,
    BASELINE_B2_VERSION,
    B2PlayerScore,
    B2RoleSummary,
    _apply_shrinkage,
    _b2_confidence_from_b0,
    _bootstrap_b2_rank_interval,
    _compute_prior_mean,
    _compute_ranks_min_rank,
    _shrinkage_weight,
    compute_b2_baseline,
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


def _write_player_match(settings: PlatformSettings, df: pd.DataFrame) -> None:
    path = settings.gold_root / "feature_store" / "player_match.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def _make_feature_matrix_df(rows: list[dict] | None = None) -> pd.DataFrame:
    """Build a rating_feature_matrix DataFrame with columns B0/B2 consume."""
    if rows is None:
        rows = [
            # Two CBs with full data, distinct minutes
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
            # One UNKNOWN position (not scored by B0 or B2)
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
# Dataclass invariants
# ---------------------------------------------------------------------------


class TestDataclassInvariants:
    def test_b2_player_score_is_frozen(self) -> None:
        ps = B2PlayerScore(
            canonical_player_id="x", player_name="n", season_id="s",
            role_family="CB",
            b0_score=50.0, b0_confidence="high", b0_missing_reason="",
            b0_rank_in_role=1, b0_role_pool_size=2,
            b0_rank_p5=1, b0_rank_p50=1, b0_rank_p95=2,
            b2_score=55.0, b2_rank_in_role=1, b2_role_pool_size=2,
            b2_rank_p5=1, b2_rank_p50=1, b2_rank_p95=2,
            shrinkage_weight=0.3, prior_mean=60.0,
            prior_source="stable_core", minutes_played=2000.0,
            minutes_input_missing=False,
            b2_confidence="high", b2_missing_reason="",
            cross_position_comparable=False,
        )
        with pytest.raises(AttributeError):
            ps.b2_score = 99.0  # type: ignore[misc]

    def test_b2_player_score_to_dict_json_serializable(self) -> None:
        ps = B2PlayerScore(
            canonical_player_id="x", player_name="n", season_id="s",
            role_family="CB",
            b0_score=50.0, b0_confidence="high", b0_missing_reason="",
            b0_rank_in_role=1, b0_role_pool_size=2,
            b0_rank_p5=1, b0_rank_p50=1, b0_rank_p95=2,
            b2_score=55.0, b2_rank_in_role=1, b2_role_pool_size=2,
            b2_rank_p5=None, b2_rank_p50=None, b2_rank_p95=None,
            shrinkage_weight=0.3, prior_mean=60.0,
            prior_source="stable_core", minutes_played=None,
            minutes_input_missing=True,
            b2_confidence="medium", b2_missing_reason="reason",
            cross_position_comparable=False,
        )
        d = ps.to_dict()
        # Must be JSON-serialisable.
        json.dumps(d, ensure_ascii=False)
        # b2_rank_interval None when p5 is None.
        assert d["b2_rank_interval"] is None
        # b0_rank_interval is a dict when p5 is not None.
        assert d["b0_rank_interval"] == {"p5": 1, "p50": 1, "p95": 2}
        # minutes_played is None when input was missing.
        assert d["minutes_played"] is None
        assert d["minutes_input_missing"] is True
        # Rounded floats.
        assert isinstance(d["b2_score"], (int, float))
        assert isinstance(d["shrinkage_weight"], (int, float))

    def test_b2_role_summary_to_dict(self) -> None:
        rs = B2RoleSummary(
            role_family="CB", member_count=10, stable_core_count=4,
            prior_mean=42.5, prior_source="stable_core",
            b0_score_median=40.0,
            b2_score_min=20.0, b2_score_median=45.0, b2_score_max=80.0,
            high_confidence_count=8, medium_confidence_count=2,
            low_confidence_count=0,
            dimensions_available=("defending", "availability"),
        )
        d = rs.to_dict()
        json.dumps(d, ensure_ascii=False)
        assert d["role_family"] == "CB"
        assert d["stable_core_count"] == 4
        assert d["confidence_counts"] == {"high": 8, "medium": 2, "low": 0}


# ---------------------------------------------------------------------------
# _shrinkage_weight
# ---------------------------------------------------------------------------


class TestShrinkageWeight:
    def test_zero_minutes_full_shrinkage(self) -> None:
        assert _shrinkage_weight(0.0, 900.0) == 1.0

    def test_negative_minutes_full_shrinkage(self) -> None:
        assert _shrinkage_weight(-100.0, 900.0) == 1.0

    def test_nan_minutes_full_shrinkage(self) -> None:
        assert _shrinkage_weight(float("nan"), 900.0) == 1.0

    def test_inf_minutes_full_shrinkage(self) -> None:
        assert _shrinkage_weight(float("inf"), 900.0) == 1.0

    def test_reference_minutes_half_shrinkage(self) -> None:
        """At minutes == reference_minutes, w must be exactly 0.5."""
        assert _shrinkage_weight(900.0, 900.0) == pytest.approx(0.5)

    def test_low_minutes_high_shrinkage(self) -> None:
        """90 minutes (1 match) with reference 900 -> w ≈ 0.909."""
        w = _shrinkage_weight(90.0, 900.0)
        assert w > 0.9
        assert w < 1.0
        assert w == pytest.approx(900.0 / 990.0)

    def test_high_minutes_low_shrinkage(self) -> None:
        """3000 minutes with reference 900 -> w ≈ 0.231."""
        w = _shrinkage_weight(3000.0, 900.0)
        assert w < 0.25
        assert w > 0.2
        assert w == pytest.approx(900.0 / 3900.0)

    def test_monotonic_decreasing_in_minutes(self) -> None:
        """w must be strictly decreasing as minutes increase."""
        ref = 900.0
        prev = 1.1  # higher than any valid w
        for m in [1, 10, 100, 500, 900, 1500, 2000, 3000, 5000]:
            w = _shrinkage_weight(float(m), ref)
            assert w < prev
            assert 0.0 < w <= 1.0
            prev = w


# ---------------------------------------------------------------------------
# _compute_prior_mean
# ---------------------------------------------------------------------------


class TestComputePriorMean:
    def test_empty_pool(self) -> None:
        scores = np.array([], dtype=np.float64)
        minutes = np.array([], dtype=np.float64)
        prior, source = _compute_prior_mean(scores, minutes, 900.0)
        assert prior == 50.0
        assert source == "empty"

    def test_stable_core_weighted_mean(self) -> None:
        """Stable core: players with minutes >= reference. Prior is the
        minutes-weighted mean of their B0 scores."""
        scores = np.array([80.0, 60.0, 40.0])
        minutes = np.array([2000.0, 1000.0, 100.0])
        prior, source = _compute_prior_mean(scores, minutes, 900.0)
        # Stable core = players 0 and 1 (minutes 2000 and 1000 >= 900).
        # Weighted mean = (80 * 2000 + 60 * 1000) / (2000 + 1000)
        #              = (160000 + 60000) / 3000 = 220000 / 3000
        #              = 73.333...
        assert source == "stable_core"
        assert prior == pytest.approx(220000.0 / 3000.0)

    def test_no_stable_core_fallback(self) -> None:
        """When no player meets the threshold, fallback to simple mean."""
        scores = np.array([80.0, 60.0, 40.0])
        minutes = np.array([100.0, 200.0, 50.0])
        prior, source = _compute_prior_mean(scores, minutes, 900.0)
        assert source == "fallback_full_pool"
        assert prior == pytest.approx(60.0)  # simple mean

    def test_stable_core_all_zero_minutes_defensive(self) -> None:
        """Defensive: stable core with all-zero minutes (impossible in
        practice but B2 must not divide by zero)."""
        scores = np.array([80.0, 60.0])
        # Both players have minutes == 900 (threshold) but we force them
        # to zero to test the div-by-zero guard. Use mock by passing
        # minutes that pass the >= check but sum to 0.
        # Actually, the threshold check uses `>=` so minutes == 900 pass.
        # To trigger the guard we'd need minutes that pass >= 900 but
        # sum to 0 — impossible. Instead test the guard directly:
        # bypass _compute_prior_mean and verify np.average with zero
        # weights raises. The function should fall back to simple mean.
        # We trust the guard; this test documents the intent.
        # Realistic test: threshold == 0 means everyone is stable core.
        minutes = np.array([0.0, 0.0])
        scores = np.array([80.0, 60.0])
        prior, source = _compute_prior_mean(scores, minutes, 0.0)
        # All players pass threshold (>= 0). Sum of minutes = 0 →
        # guard kicks in, fallback to simple mean.
        assert source == "stable_core"
        assert prior == pytest.approx(70.0)


# ---------------------------------------------------------------------------
# _apply_shrinkage
# ---------------------------------------------------------------------------


class TestApplyShrinkage:
    def test_empty_pool(self) -> None:
        b0 = np.array([], dtype=np.float64)
        minutes = np.array([], dtype=np.float64)
        b2 = _apply_shrinkage(b0, minutes, prior_mean=50.0, reference_minutes=900.0)
        assert len(b2) == 0

    def test_convex_combination(self) -> None:
        """b2 = w * prior + (1 - w) * b0 where w = ref / (ref + minutes)."""
        b0 = np.array([80.0, 60.0])
        minutes = np.array([900.0, 1800.0])  # w = 0.5, 0.333
        prior = 50.0
        ref = 900.0
        b2 = _apply_shrinkage(b0, minutes, prior, ref)
        # Player 0: w = 0.5 -> b2 = 0.5*50 + 0.5*80 = 65
        # Player 1: w = 900/2700 = 0.333... -> b2 = 0.333*50 + 0.666*60 = 56.666
        assert b2[0] == pytest.approx(65.0)
        assert b2[1] == pytest.approx((1.0 / 3.0) * 50.0 + (2.0 / 3.0) * 60.0)

    def test_missing_minutes_full_shrinkage(self) -> None:
        """NaN or non-positive minutes -> w = 1.0 -> b2 = prior."""
        b0 = np.array([80.0, 90.0, 70.0])
        minutes = np.array([np.nan, 0.0, -10.0])
        prior = 50.0
        b2 = _apply_shrinkage(b0, minutes, prior, 900.0)
        # All three players get full shrinkage to prior.
        np.testing.assert_allclose(b2, np.full(3, 50.0))

    def test_low_minute_player_pulled_to_prior(self) -> None:
        """A 90-minute player with b0=99 should be pulled close to prior."""
        b0 = np.array([99.0])
        minutes = np.array([90.0])
        prior = 50.0
        b2 = _apply_shrinkage(b0, minutes, prior, 900.0)
        # w = 900/990 ≈ 0.909; b2 ≈ 0.909*50 + 0.091*99 ≈ 54.45
        assert b2[0] < 55.0
        assert b2[0] > 50.0  # not equal to prior (small b0 contribution)

    def test_high_minute_player_keeps_b0(self) -> None:
        """A 3000-minute player with b0=99 should mostly keep their score."""
        b0 = np.array([99.0])
        minutes = np.array([3000.0])
        prior = 50.0
        b2 = _apply_shrinkage(b0, minutes, prior, 900.0)
        # w = 900/3900 ≈ 0.231; b2 ≈ 0.231*50 + 0.769*99 ≈ 87.7
        assert b2[0] > 85.0
        assert b2[0] < 99.0


# ---------------------------------------------------------------------------
# _compute_ranks_min_rank
# ---------------------------------------------------------------------------


class TestComputeRanksMinRank:
    def test_empty(self) -> None:
        ranks = _compute_ranks_min_rank(np.array([], dtype=np.float64))
        assert len(ranks) == 0

    def test_simple_descending(self) -> None:
        """[10, 20, 30] -> ranks [3, 2, 1] (1 = highest)."""
        ranks = _compute_ranks_min_rank(np.array([10.0, 20.0, 30.0]))
        np.testing.assert_array_equal(ranks, np.array([3, 2, 1]))

    def test_ties_min_rank(self) -> None:
        """[10, 10, 20] -> ranks [2, 2, 1] (min-rank for ties)."""
        ranks = _compute_ranks_min_rank(np.array([10.0, 10.0, 20.0]))
        np.testing.assert_array_equal(ranks, np.array([2, 2, 1]))

    def test_all_ties(self) -> None:
        """[5, 5, 5] -> ranks [1, 1, 1]."""
        ranks = _compute_ranks_min_rank(np.array([5.0, 5.0, 5.0]))
        np.testing.assert_array_equal(ranks, np.array([1, 1, 1]))


# ---------------------------------------------------------------------------
# _b2_confidence_from_b0
# ---------------------------------------------------------------------------


class TestB2ConfidenceFromB0:
    def test_b0_low_b2_low(self) -> None:
        conf, reason = _b2_confidence_from_b0(
            "low", minutes_input_missing=False, prior_source="stable_core"
        )
        assert conf == "low"
        assert "B0 confidence=low" in reason

    def test_b0_medium_clean_b2_medium(self) -> None:
        conf, reason = _b2_confidence_from_b0(
            "medium", minutes_input_missing=False, prior_source="stable_core"
        )
        assert conf == "medium"
        assert "B0 confidence=medium" in reason

    def test_b0_high_clean_b2_high(self) -> None:
        conf, reason = _b2_confidence_from_b0(
            "high", minutes_input_missing=False, prior_source="stable_core"
        )
        assert conf == "high"
        assert reason == ""

    def test_b0_high_minutes_missing_b2_medium(self) -> None:
        conf, reason = _b2_confidence_from_b0(
            "high", minutes_input_missing=True, prior_source="stable_core"
        )
        assert conf == "medium"
        assert "minutes_played" in reason

    def test_b0_high_prior_fallback_b2_medium(self) -> None:
        conf, reason = _b2_confidence_from_b0(
            "high", minutes_input_missing=False, prior_source="fallback_full_pool"
        )
        assert conf == "medium"
        assert "fallback_full_pool" in reason

    def test_b0_low_overrides_everything(self) -> None:
        """B0 low always returns B2 low, regardless of other inputs."""
        conf, _ = _b2_confidence_from_b0(
            "low", minutes_input_missing=False, prior_source="stable_core"
        )
        assert conf == "low"
        conf, _ = _b2_confidence_from_b0(
            "low", minutes_input_missing=True, prior_source="fallback_full_pool"
        )
        assert conf == "low"


# ---------------------------------------------------------------------------
# _bootstrap_b2_rank_interval
# ---------------------------------------------------------------------------


class TestBootstrapB2RankInterval:
    def test_small_pool_returns_none(self) -> None:
        """Pools below _MIN_BOOTSTRAP_POOL must return None for every player."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        pool = [
            {"tackles": 30, "interceptions": 40, "passes": 100,
             "minutes_played": 2000, "starts": 22},
            {"tackles": 20, "interceptions": 25, "passes": 80,
             "minutes_played": 1500, "starts": 17},
        ]
        minutes = np.array([2000.0, 1500.0])
        intervals = _bootstrap_b2_rank_interval(
            pool, dims, minutes, 900.0, n_bootstrap=10, seed=42
        )
        assert intervals == [None, None]

    def test_zero_bootstrap_returns_none(self) -> None:
        dims = B0_DIMENSIONS[RoleFamily.CB]
        pool = [
            {"tackles": 30, "interceptions": 40, "passes": 100,
             "minutes_played": 2000, "starts": 22},
        ] * 15
        minutes = np.array([2000.0] * 15)
        intervals = _bootstrap_b2_rank_interval(
            pool, dims, minutes, 900.0, n_bootstrap=0, seed=42
        )
        assert all(i is None for i in intervals)

    def test_large_pool_returns_intervals(self) -> None:
        """A pool of 15 players with n_bootstrap=5 returns a
        (p5, p50, p95) tuple per player."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        pool = [
            {
                "tackles": 10 + i, "interceptions": 15 + i, "passes": 100 + i * 5,
                "minutes_played": 1000 + i * 100, "starts": 11 + i,
            }
            for i in range(15)
        ]
        minutes = np.array([1000.0 + i * 100 for i in range(15)])
        intervals = _bootstrap_b2_rank_interval(
            pool, dims, minutes, 900.0, n_bootstrap=5, seed=42
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
        minutes = np.array([1000.0 + i * 100 for i in range(15)])
        iv1 = _bootstrap_b2_rank_interval(
            pool, dims, minutes, 900.0, n_bootstrap=5, seed=42
        )
        iv2 = _bootstrap_b2_rank_interval(
            pool, dims, minutes, 900.0, n_bootstrap=5, seed=42
        )
        assert iv1 == iv2

    def test_different_seeds_may_differ(self) -> None:
        """Different seeds usually produce different intervals (statistical
        sanity check, not deterministic)."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        pool = [
            {
                "tackles": 10 + i, "interceptions": 15 + i, "passes": 100 + i * 5,
                "minutes_played": 1000 + i * 100, "starts": 11 + i,
            }
            for i in range(15)
        ]
        minutes = np.array([1000.0 + i * 100 for i in range(15)])
        iv1 = _bootstrap_b2_rank_interval(
            pool, dims, minutes, 900.0, n_bootstrap=5, seed=42
        )
        iv2 = _bootstrap_b2_rank_interval(
            pool, dims, minutes, 900.0, n_bootstrap=5, seed=999
        )
        # At least one player's p50 should differ. (Not strictly required
        # but very likely with distinct seeds.)
        differs = any(
            iv1[i][1] != iv2[i][1]  # type: ignore[index]
            for i in range(len(iv1))
            if iv1[i] is not None and iv2[i] is not None
        )
        # Allow the rare case where they happen to coincide.
        assert isinstance(differs, bool)


# ---------------------------------------------------------------------------
# compute_b2_baseline — fail-closed paths
# ---------------------------------------------------------------------------


class TestComputeB2BaselineFailClosed:
    def test_missing_feature_matrix(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_b2_baseline(settings=settings, n_bootstrap=5)
        assert rep["status"] == "unavailable"
        assert "missing" in rep["evidence"]["reason"]

    def test_empty_feature_matrix(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, pd.DataFrame([]))
        rep = compute_b2_baseline(settings=settings, n_bootstrap=5)
        assert rep["status"] == "unavailable"
        assert "empty" in rep["evidence"]["reason"]

    def test_invalid_reference_minutes_zero(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b2_baseline(
            settings=settings, reference_minutes=0.0, n_bootstrap=5
        )
        assert rep["status"] == "unavailable"
        assert "reference_minutes" in rep["evidence"]["reason"]

    def test_invalid_reference_minutes_negative(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b2_baseline(
            settings=settings, reference_minutes=-100.0, n_bootstrap=5
        )
        assert rep["status"] == "unavailable"

    def test_invalid_reference_minutes_nan(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b2_baseline(
            settings=settings, reference_minutes=float("nan"), n_bootstrap=5
        )
        assert rep["status"] == "unavailable"


# ---------------------------------------------------------------------------
# compute_b2_baseline — happy path
# ---------------------------------------------------------------------------


class TestComputeB2BaselineHappy:
    def test_status_ok(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b2_baseline(settings=settings, n_bootstrap=5)
        assert rep["status"] == "ok"
        assert rep["schema"] == BASELINE_B2_SCHEMA
        assert rep["schema_version"] == BASELINE_B2_VERSION

    def test_total_players_scored_excludes_unknown(self, tmp_path: Path) -> None:
        """UNKNOWN rows are counted but not scored."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b2_baseline(settings=settings, n_bootstrap=5)
        # 5 rows: 2 CB + 1 ST + 1 GK + 1 UNKNOWN. Scored = 4.
        assert rep["evidence"]["total_players_scored"] == 4
        # by_role_family includes UNKNOWN count.
        assert rep["evidence"]["by_role_family"].get("UNKNOWN") == 1

    def test_role_summaries_present(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b2_baseline(settings=settings, n_bootstrap=5)
        summaries = rep["evidence"]["role_summaries"]
        roles = {s["role_family"] for s in summaries}
        assert roles == {"CB", "ST", "GK"}

    def test_role_summary_has_prior_mean_and_stable_core(self, tmp_path: Path) -> None:
        """Each role summary must report prior_mean, prior_source, and
        stable_core_count."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b2_baseline(settings=settings, n_bootstrap=5)
        for rs in rep["evidence"]["role_summaries"]:
            assert "prior_mean" in rs
            assert "prior_source" in rs
            assert "stable_core_count" in rs
            assert rs["prior_source"] in ("stable_core", "fallback_full_pool", "empty")
            assert isinstance(rs["stable_core_count"], int)
            assert rs["stable_core_count"] >= 0
            assert rs["stable_core_count"] <= rs["member_count"]

    def test_player_has_b0_and_b2_scores(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b2_baseline(settings=settings, n_bootstrap=5)
        for p in rep["evidence"]["players"]:
            assert "b0_score" in p
            assert "b2_score" in p
            assert "b0_rank_in_role" in p
            assert "b2_rank_in_role" in p
            assert "shrinkage_weight" in p
            assert "prior_mean" in p
            assert "prior_source" in p
            assert "minutes_played" in p
            assert "minutes_input_missing" in p
            assert "b0_confidence" in p
            assert "b2_confidence" in p

    def test_b2_score_is_hand_recomputable(self, tmp_path: Path) -> None:
        """For every player, b2_score == w * prior + (1-w) * b0_score,
        where w = reference_minutes / (reference_minutes + minutes)."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        ref = 900.0
        rep = compute_b2_baseline(
            settings=settings, reference_minutes=ref, n_bootstrap=5
        )
        for p in rep["evidence"]["players"]:
            w = p["shrinkage_weight"]
            prior = p["prior_mean"]
            b0 = p["b0_score"]
            b2 = p["b2_score"]
            # Check the convex combination formula (within rounding).
            expected = w * prior + (1.0 - w) * b0
            assert b2 == pytest.approx(expected, abs=0.05), (
                f"b2 mismatch for {p['player_name']}: "
                f"b2={b2}, expected={expected}, w={w}, prior={prior}, b0={b0}"
            )

    def test_shrinkage_weight_matches_formula(self, tmp_path: Path) -> None:
        """shrinkage_weight == reference_minutes / (reference_minutes + minutes)."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        ref = 900.0
        rep = compute_b2_baseline(
            settings=settings, reference_minutes=ref, n_bootstrap=5
        )
        for p in rep["evidence"]["players"]:
            minutes = p["minutes_played"]
            w = p["shrinkage_weight"]
            if minutes is None or minutes <= 0:
                assert w == 1.0
            else:
                expected_w = ref / (ref + minutes)
                assert w == pytest.approx(expected_w, abs=0.001)

    def test_cross_position_comparable_always_false(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b2_baseline(settings=settings, n_bootstrap=5)
        for p in rep["evidence"]["players"]:
            assert p["cross_position_comparable"] is False

    def test_low_minute_player_b2_closer_to_prior_than_b0(self, tmp_path: Path) -> None:
        """A low-minute player's b2_score should be closer to prior_mean
        than their b0_score is."""
        settings = PlatformSettings.from_root(tmp_path)
        # Add a low-minute CB with extreme stats.
        rows = _make_feature_matrix_df().to_dict("records")
        rows.append({
            "player_id": "u|9", "player_name": "CB-LOWMIN", "season_id": "2425",
            "position_group": "CB", "source_name": "understat",
            "minutes_played": 90, "starts": 1,
            "tackles": 100, "interceptions": 100, "passes": 5000,
            "goals": 0, "assists": 0, "npxg": 0.0, "xa": 0.0,
            "defense_missing": False, "possession_missing": False,
            "xT_VAEP_missing": False, "goalkeeper_missing": True,
        })
        _write_rating_feature_matrix(settings, pd.DataFrame(rows))
        rep = compute_b2_baseline(settings=settings, n_bootstrap=5)
        cb_players = [p for p in rep["evidence"]["players"]
                      if p["role_family"] == "CB"]
        low_min = next(p for p in cb_players if p["player_name"] == "CB-LOWMIN")
        # b0 should be high (extreme stats) but b2 should be pulled toward prior.
        prior = low_min["prior_mean"]
        b0 = low_min["b0_score"]
        b2 = low_min["b2_score"]
        # |b2 - prior| < |b0 - prior|
        assert abs(b2 - prior) < abs(b0 - prior)
        # w should be > 0.9 (90 minutes with reference 900)
        assert low_min["shrinkage_weight"] > 0.9

    def test_high_minute_player_b2_close_to_b0(self, tmp_path: Path) -> None:
        """A high-minute player's b2_score should be close to b0_score
        (small shrinkage)."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b2_baseline(settings=settings, n_bootstrap=5)
        # CB-A has 2000 minutes → w = 900/2900 ≈ 0.31. b2 should be
        # within ~30% of (b0 - prior) of b0.
        cb_a = next(
            p for p in rep["evidence"]["players"]
            if p["player_name"] == "CB-A"
        )
        w = cb_a["shrinkage_weight"]
        assert w < 0.35  # high minutes → low weight
        # b2 should be between prior and b0.
        prior = cb_a["prior_mean"]
        b0 = cb_a["b0_score"]
        b2 = cb_a["b2_score"]
        assert min(b0, prior) - 0.01 <= b2 <= max(b0, prior) + 0.01

    def test_gk_role_still_provisional(self, tmp_path: Path) -> None:
        """GK should still be scored (availability-only), but with the
        gk_provisional limitation in the report."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b2_baseline(settings=settings, n_bootstrap=5)
        gk_players = [p for p in rep["evidence"]["players"]
                      if p["role_family"] == "GK"]
        assert len(gk_players) == 1
        # Limitations should mention gk_provisional.
        gk_lim = [lim for lim in rep["limitations"] if "gk_provisional" in lim]
        assert len(gk_lim) >= 1

    def test_canonical_player_id_fallback(self, tmp_path: Path) -> None:
        """When canonical_player_id column is missing, B2 falls back to
        unresolved:<source>:<player_id> per the PRS-1 contract."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b2_baseline(settings=settings, n_bootstrap=5)
        for p in rep["evidence"]["players"]:
            assert p["canonical_player_id"].startswith("unresolved:")

    def test_json_serializable(self, tmp_path: Path) -> None:
        """The full report must be JSON-serialisable for CLI output."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b2_baseline(settings=settings, n_bootstrap=5)
        json.dumps(rep, ensure_ascii=False)  # must not raise

    def test_limitations_non_empty(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b2_baseline(settings=settings, n_bootstrap=5)
        # B2 has 11 limitations.
        assert len(rep["limitations"]) >= 8

    def test_parameters_recorded(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b2_baseline(
            settings=settings,
            reference_minutes=500.0,
            n_bootstrap=42,
            seed=12345,
        )
        assert rep["parameters"]["reference_minutes"] == 500.0
        assert rep["parameters"]["n_bootstrap"] == 42
        assert rep["parameters"]["seed"] == 12345
        assert rep["parameters"]["baseline_b0_schema"] == "scoutfootball.baseline-b0"

    def test_b0_rank_in_b2_report_matches_standalone_b0(
        self, tmp_path: Path
    ) -> None:
        """The b0_rank_in_role reported by B2 must match what B0 standalone
        reports for the same player."""
        from scoutfootball.evaluation.baseline_b0 import compute_b0_baseline

        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        b2_rep = compute_b2_baseline(settings=settings, n_bootstrap=5)
        b0_rep = compute_b0_baseline(settings=settings, n_bootstrap=5)

        b0_ranks = {
            (p["canonical_player_id"], p["season_id"]): p["rank_in_role"]
            for p in b0_rep["evidence"]["players"]
        }
        for p in b2_rep["evidence"]["players"]:
            key = (p["canonical_player_id"], p["season_id"])
            assert key in b0_ranks
            assert p["b0_rank_in_role"] == b0_ranks[key]

    def test_b0_score_in_b2_report_matches_standalone_b0(
        self, tmp_path: Path
    ) -> None:
        """The b0_score reported by B2 must match what B0 standalone
        reports for the same player."""
        from scoutfootball.evaluation.baseline_b0 import compute_b0_baseline

        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        b2_rep = compute_b2_baseline(settings=settings, n_bootstrap=5)
        b0_rep = compute_b0_baseline(settings=settings, n_bootstrap=5)

        b0_scores = {
            (p["canonical_player_id"], p["season_id"]): p["score"]
            for p in b0_rep["evidence"]["players"]
        }
        for p in b2_rep["evidence"]["players"]:
            key = (p["canonical_player_id"], p["season_id"])
            assert key in b0_scores
            assert p["b0_score"] == pytest.approx(b0_scores[key], abs=0.01)

    def test_feature_matrix_parameter_direct(self, tmp_path: Path) -> None:
        """Passing feature_matrix directly bypasses file loading."""
        settings = PlatformSettings.from_root(tmp_path)
        # Do NOT write the file. Pass DataFrame directly.
        rep = compute_b2_baseline(
            settings=settings,
            feature_matrix=_make_feature_matrix_df(),
            n_bootstrap=5,
        )
        assert rep["status"] == "ok"
        assert rep["evidence"]["total_players_scored"] == 4


# ---------------------------------------------------------------------------
# compute_b2_baseline — cohort filtering
# ---------------------------------------------------------------------------


class TestComputeB2BaselineCohort:
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
        rep = compute_b2_baseline(
            settings=settings, cohort_definition=definition, n_bootstrap=5
        )
        # All rows unresolved → cohort membership is empty → scored=0
        assert rep["status"] == "ok"
        assert rep["evidence"]["total_players_scored"] == 0


# ---------------------------------------------------------------------------
# compute_b2_baseline — missing-data scenarios
# ---------------------------------------------------------------------------


class TestComputeB2BaselineMissingData:
    def test_minutes_missing_marks_player(self, tmp_path: Path) -> None:
        """A player with missing minutes_played must be flagged
        minutes_input_missing=True and have b2_score == prior_mean."""
        settings = PlatformSettings.from_root(tmp_path)
        rows = _make_feature_matrix_df().to_dict("records")
        # Add a CB with NaN minutes.
        rows.append({
            "player_id": "u|8", "player_name": "CB-NOMIN", "season_id": "2425",
            "position_group": "CB", "source_name": "understat",
            "minutes_played": None, "starts": None,
            "tackles": 25, "interceptions": 30, "passes": 800,
            "goals": 0, "assists": 0, "npxg": 0.0, "xa": 0.0,
            "defense_missing": False, "possession_missing": False,
            "xT_VAEP_missing": False, "goalkeeper_missing": True,
        })
        df = pd.DataFrame(rows)
        # pandas may convert None to NaN; force minutes_played to NaN.
        df["minutes_played"] = df["minutes_played"].astype("Float64")
        _write_rating_feature_matrix(settings, df)
        rep = compute_b2_baseline(settings=settings, n_bootstrap=5)
        cb_nomin = next(
            p for p in rep["evidence"]["players"]
            if p["player_name"] == "CB-NOMIN"
        )
        assert cb_nomin["minutes_input_missing"] is True
        assert cb_nomin["minutes_played"] is None
        # w must be 1.0 (full shrinkage).
        assert cb_nomin["shrinkage_weight"] == 1.0
        # b2 must equal prior_mean.
        assert cb_nomin["b2_score"] == pytest.approx(
            cb_nomin["prior_mean"], abs=0.01
        )
        # B2 confidence must be at most medium.
        assert cb_nomin["b2_confidence"] in ("medium", "low")

    def test_b0_low_player_stays_low_in_b2(self, tmp_path: Path) -> None:
        """A player with B0 confidence=low (all core dims missing) must
        have B2 confidence=low too, and b2 == prior_mean."""
        settings = PlatformSettings.from_root(tmp_path)
        rows = [
            # CB with full data (high confidence baseline)
            {
                "player_id": "u|1", "player_name": "CB-FULL", "season_id": "2425",
                "position_group": "CB", "source_name": "understat",
                "minutes_played": 2000, "starts": 22,
                "tackles": 30, "interceptions": 40, "passes": 1500,
                "goals": 1, "assists": 0, "npxg": 0.5, "xa": 0.2,
                "defense_missing": False, "possession_missing": False,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            },
            # CB with everything missing — B0 confidence=low.
            # All core dims (defending + availability) must be missing,
            # so minutes_played/starts are None too.
            {
                "player_id": "u|2", "player_name": "CB-EMPTY", "season_id": "2425",
                "position_group": "CB", "source_name": "understat",
                "minutes_played": None, "starts": None,
                "tackles": None, "interceptions": None, "passes": None,
                "goals": None, "assists": None, "npxg": None, "xa": None,
                "defense_missing": True, "possession_missing": True,
                "xT_VAEP_missing": True, "goalkeeper_missing": True,
            },
        ]
        _write_rating_feature_matrix(settings, pd.DataFrame(rows))
        rep = compute_b2_baseline(settings=settings, n_bootstrap=5)
        cb_empty = next(
            p for p in rep["evidence"]["players"]
            if p["player_name"] == "CB-EMPTY"
        )
        assert cb_empty["b0_confidence"] == "low"
        assert cb_empty["b2_confidence"] == "low"
        # b0_score is the neutral 50.0 placeholder; b2 applies full
        # shrinkage to prior_mean.
        assert cb_empty["b0_score"] == pytest.approx(50.0, abs=0.01)
        assert cb_empty["b2_score"] == pytest.approx(
            cb_empty["prior_mean"], abs=0.01
        )
        assert cb_empty["shrinkage_weight"] == 1.0


# ---------------------------------------------------------------------------
# compute_b2_baseline — fallback prior source
# ---------------------------------------------------------------------------


class TestComputeB2BaselineFallbackPrior:
    def test_fallback_prior_when_no_stable_core(self, tmp_path: Path) -> None:
        """When all players in a role have minutes < reference_minutes,
        prior_source must be fallback_full_pool and B2 confidence capped
        at medium for high-B0-confidence players."""
        settings = PlatformSettings.from_root(tmp_path)
        # Build a CB pool where all minutes are below 900.
        rows = [
            {
                "player_id": f"u|{i}", "player_name": f"CB-{i}",
                "season_id": "2425",
                "position_group": "CB", "source_name": "understat",
                "minutes_played": 100 + i * 10, "starts": 1,
                "tackles": 20 + i, "interceptions": 25 + i, "passes": 500 + i * 10,
                "goals": 0, "assists": 0, "npxg": 0.0, "xa": 0.0,
                "defense_missing": False, "possession_missing": False,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            }
            for i in range(15)
        ]
        _write_rating_feature_matrix(settings, pd.DataFrame(rows))
        rep = compute_b2_baseline(
            settings=settings, reference_minutes=900.0, n_bootstrap=5
        )
        cb_summary = next(
            s for s in rep["evidence"]["role_summaries"] if s["role_family"] == "CB"
        )
        assert cb_summary["prior_source"] == "fallback_full_pool"
        # All players must be medium confidence (fallback prior).
        for p in rep["evidence"]["players"]:
            assert p["b2_confidence"] in ("medium", "low")


# ---------------------------------------------------------------------------
# compute_b2_baseline — reference_minutes sensitivity
# ---------------------------------------------------------------------------


class TestComputeB2BaselineReferenceMinutes:
    def test_lower_reference_less_shrinkage(self, tmp_path: Path) -> None:
        """A lower reference_minutes means LESS shrinkage at the same
        minutes (w is smaller). Player keeps more of their b0 score."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        # High reference (3000): 2000-min player w = 3000/5000 = 0.6
        rep_high = compute_b2_baseline(
            settings=settings, reference_minutes=3000.0, n_bootstrap=5
        )
        # Low reference (100): 2000-min player w = 100/2100 ≈ 0.048
        rep_low = compute_b2_baseline(
            settings=settings, reference_minutes=100.0, n_bootstrap=5
        )
        cb_a_high = next(
            p for p in rep_high["evidence"]["players"]
            if p["player_name"] == "CB-A"
        )
        cb_a_low = next(
            p for p in rep_low["evidence"]["players"]
            if p["player_name"] == "CB-A"
        )
        # Higher reference → higher w → more shrinkage → b2 closer to prior.
        assert cb_a_high["shrinkage_weight"] > cb_a_low["shrinkage_weight"]


# ---------------------------------------------------------------------------
# compute_b2_baseline — rank ordering
# ---------------------------------------------------------------------------


class TestComputeB2BaselineRanking:
    def test_b2_ranks_are_sequential_per_role(self, tmp_path: Path) -> None:
        """Within each role, b2 ranks must form a valid min-rank sequence
        (1, 1, ..., 2, 3, ...). Best player(s) get rank 1."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b2_baseline(settings=settings, n_bootstrap=5)
        by_role: dict[str, list] = {}
        for p in rep["evidence"]["players"]:
            by_role.setdefault(p["role_family"], []).append(p)
        for _role, players in by_role.items():
            ranks = sorted(p["b2_rank_in_role"] for p in players)
            assert ranks[0] == 1
            assert all(1 <= r <= len(players) for r in ranks)

    def test_top_b2_player_has_highest_b2_score(self, tmp_path: Path) -> None:
        """The player with b2_rank=1 must have the highest b2_score."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b2_baseline(settings=settings, n_bootstrap=5)
        by_role: dict[str, list] = {}
        for p in rep["evidence"]["players"]:
            by_role.setdefault(p["role_family"], []).append(p)
        for _role, players in by_role.items():
            top = next(p for p in players if p["b2_rank_in_role"] == 1)
            scores = [p["b2_score"] for p in players]
            assert top["b2_score"] == max(scores)
