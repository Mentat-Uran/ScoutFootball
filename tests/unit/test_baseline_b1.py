"""Unit tests for the PRS-2 B1 expert_weighted baseline.

Covers the versioned weight set invariants (sum to 1.0, dimension
coverage, finite floats), the weight-renormalisation helper on missing
dimensions, the vectorised weighted-score path, hand-recomputability
(B1 score == sum(effective_weight * dimension_percentile)), bootstrap
rank intervals, and the public ``compute_b1_baseline`` entry point's
fail-closed and happy-path behaviour.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.baseline_b0 import (
    B0_DIMENSIONS,
    _dimension_percentile,
    _pool_column_arrays,
)
from scoutfootball.evaluation.baseline_b1 import (
    B1_WEIGHTS,
    B1_WEIGHTS_VERSION,
    BASELINE_B1_SCHEMA,
    BASELINE_B1_VERSION,
    B1DimensionScore,
    B1PlayerScore,
    B1RoleSummary,
    _bootstrap_rank_interval,
    _player_score,
    _renormalised_weights,
    _vectorised_dimension_percentiles,
    _vectorised_weighted_scores,
    _vectorised_weighted_scores_for_resample,
    compute_b1_baseline,
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
    """preview_cohort reads player_match.parquet, so cohort tests must
    write it alongside the feature matrix."""
    path = settings.gold_root / "feature_store" / "player_match.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def _make_feature_matrix_df(rows: list[dict] | None = None) -> pd.DataFrame:
    """Build a rating_feature_matrix DataFrame with columns B0/B1 consume."""
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
            # One UNKNOWN position (not scored by B0 or B1)
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
# Weight set invariants
# ---------------------------------------------------------------------------


class TestWeightSetInvariants:
    def test_every_role_has_weight_set(self) -> None:
        """Every RoleFamily in B0_DIMENSIONS (except UNKNOWN) must have
        a corresponding entry in B1_WEIGHTS."""
        for role in B0_DIMENSIONS:
            if role == RoleFamily.UNKNOWN:
                continue
            assert role in B1_WEIGHTS, f"missing weights for {role}"

    def test_weights_cover_exactly_b0_dimensions(self) -> None:
        """The weight set's keys must exactly match B0_DIMENSIONS' keys
        for each role — no missing, no extra."""
        for role, dims in B0_DIMENSIONS.items():
            if role == RoleFamily.UNKNOWN:
                continue
            weights = B1_WEIGHTS[role]
            dim_keys = {d.key for d in dims}
            weight_keys = set(weights.keys())
            assert weight_keys == dim_keys, (
                f"{role}: weight keys {sorted(weight_keys)} "
                f"!= dim keys {sorted(dim_keys)}"
            )

    def test_weights_sum_to_one(self) -> None:
        """Each role's weights must sum to 1.0 within tolerance."""
        for role, weights in B1_WEIGHTS.items():
            total = sum(float(w) for w in weights.values())
            assert abs(total - 1.0) < 1e-9, (
                f"{role}: weights sum to {total!r}, expected 1.0"
            )

    def test_weights_are_in_unit_interval(self) -> None:
        """Every weight must be a finite float in [0, 1]."""
        for role, weights in B1_WEIGHTS.items():
            for k, w in weights.items():
                assert isinstance(w, (int, float)) and not isinstance(w, bool), (
                    f"{role}.{k}: weight is not a number: {w!r}"
                )
                wf = float(w)
                assert math.isfinite(wf), (
                    f"{role}.{k}: weight is not finite: {w!r}"
                )
                assert 0.0 <= wf <= 1.0, (
                    f"{role}.{k}: weight out of [0,1]: {w!r}"
                )

    def test_gk_weight_is_availability_only(self) -> None:
        """GK must have weight 1.0 on availability (the only dimension)
        — so B1 == B0 for GK."""
        gk_weights = B1_WEIGHTS[RoleFamily.GK]
        assert gk_weights == {"availability": 1.0}

    def test_weight_version_is_string(self) -> None:
        """weight_version must be a non-empty string."""
        assert isinstance(B1_WEIGHTS_VERSION, str)
        assert B1_WEIGHTS_VERSION != ""

    def test_st_finishing_is_dominant(self) -> None:
        """ST's finishing weight must be the largest — encodes 'for a
        ST, finishing matters most'."""
        st = B1_WEIGHTS[RoleFamily.ST]
        assert max(st, key=st.get) == "finishing"
        assert st["finishing"] > st["attacking"]
        assert st["finishing"] > st["availability"]

    def test_cb_defending_is_dominant(self) -> None:
        """CB's defending weight must be the largest."""
        cb = B1_WEIGHTS[RoleFamily.CB]
        assert max(cb, key=cb.get) == "defending"
        assert cb["defending"] > cb["possession"]
        assert cb["defending"] > cb["availability"]

    def test_w_attacking_is_dominant(self) -> None:
        """W's attacking weight must be the largest."""
        w = B1_WEIGHTS[RoleFamily.W]
        assert max(w, key=w.get) == "attacking"
        assert w["attacking"] > w["availability"]


# ---------------------------------------------------------------------------
# Dataclass invariants
# ---------------------------------------------------------------------------


class TestDataclassInvariants:
    def test_b1_dimension_score_contribution_property(self) -> None:
        """contribution = effective_weight * dimension_percentile."""
        ds = B1DimensionScore(
            dimension="defending", label="D",
            columns_present=("tackles",), columns_missing=(),
            column_percentiles={"tackles": 70.0},
            dimension_percentile=70.0,
            is_missing=False, is_core=True, missing_flag="",
            weight=0.5, effective_weight=0.625,
        )
        assert ds.contribution == pytest.approx(0.625 * 70.0)

    def test_b1_dimension_score_to_dict_json_serializable(self) -> None:
        ds = B1DimensionScore(
            dimension="defending", label="D",
            columns_present=("tackles",), columns_missing=("interceptions",),
            column_percentiles={"tackles": 70.0},
            dimension_percentile=70.0,
            is_missing=False, is_core=True, missing_flag="defense_missing",
            weight=0.5, effective_weight=0.5,
        )
        d = ds.to_dict()
        json.dumps(d, ensure_ascii=False)
        assert d["dimension"] == "defending"
        assert d["weight"] == 0.5
        assert d["effective_weight"] == 0.5
        assert d["contribution"] == pytest.approx(35.0)
        assert d["columns_present"] == ["tackles"]
        assert d["columns_missing"] == ["interceptions"]

    def test_b1_player_score_is_frozen(self) -> None:
        ps = B1PlayerScore(
            canonical_player_id="x", player_name="n", season_id="s",
            role_family="CB", score=50.0,
            rank_in_role=1, role_pool_size=2,
            rank_p5=1, rank_p50=1, rank_p95=2,
            confidence="high", missing_reason="",
            core_dimensions_used=2, core_dimensions_total=2,
            dimensions=(), weight_version="1.0",
            cross_position_comparable=False,
        )
        with pytest.raises(AttributeError):
            ps.score = 99.0  # type: ignore[misc]

    def test_b1_player_score_to_dict_json_serializable(self) -> None:
        ps = B1PlayerScore(
            canonical_player_id="x", player_name="n", season_id="s",
            role_family="CB", score=55.0,
            rank_in_role=1, role_pool_size=2,
            rank_p5=1, rank_p50=1, rank_p95=2,
            confidence="high", missing_reason="",
            core_dimensions_used=2, core_dimensions_total=2,
            dimensions=(), weight_version="1.0",
            cross_position_comparable=False,
        )
        d = ps.to_dict()
        json.dumps(d, ensure_ascii=False)
        assert d["score"] == 55.0
        assert d["rank_interval"] == {"p5": 1, "p50": 1, "p95": 2}
        assert d["weight_version"] == "1.0"
        assert d["cross_position_comparable"] is False

    def test_b1_player_score_to_dict_rank_interval_none(self) -> None:
        """When rank_p5 is None, rank_interval must be None."""
        ps = B1PlayerScore(
            canonical_player_id="x", player_name="n", season_id="s",
            role_family="CB", score=55.0,
            rank_in_role=None, role_pool_size=0,
            rank_p5=None, rank_p50=None, rank_p95=None,
            confidence="low", missing_reason="reason",
            core_dimensions_used=0, core_dimensions_total=2,
            dimensions=(), weight_version="1.0",
            cross_position_comparable=False,
        )
        d = ps.to_dict()
        assert d["rank_interval"] is None
        assert d["rank_in_role"] is None

    def test_b1_role_summary_to_dict_json_serializable(self) -> None:
        rs = B1RoleSummary(
            role_family="CB", member_count=10,
            high_confidence_count=8, medium_confidence_count=2,
            low_confidence_count=0,
            score_min=20.0, score_median=45.0, score_max=80.0,
            dimensions_available=("defending", "possession", "availability"),
            weight_version="1.0",
            weights={"defending": 0.5, "possession": 0.2, "availability": 0.3},
        )
        d = rs.to_dict()
        json.dumps(d, ensure_ascii=False)
        assert d["role_family"] == "CB"
        assert d["member_count"] == 10
        assert d["confidence_counts"] == {"high": 8, "medium": 2, "low": 0}
        assert d["weight_version"] == "1.0"
        assert d["weights"]["defending"] == 0.5


# ---------------------------------------------------------------------------
# _renormalised_weights
# ---------------------------------------------------------------------------


class TestRenormalisedWeights:
    def test_all_present_returns_raw_weights(self) -> None:
        """When every dimension is present, effective weights equal raw
        weights (no renormalisation needed since they already sum to 1)."""
        dims = B0_DIMENSIONS[RoleFamily.CB]  # defending/possession/availability
        raw = B1_WEIGHTS[RoleFamily.CB]
        # All dimensions present (is_missing=False).
        dim_flags = [(d, False) for d in dims]
        eff = _renormalised_weights(dim_flags, raw)
        for d in dims:
            assert eff[d.key] == pytest.approx(raw[d.key])

    def test_missing_supporting_dimension_renormalises(self) -> None:
        """When a supporting dimension is missing, the remaining weights
        must renormalise to sum to 1.0."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        raw = B1_WEIGHTS[RoleFamily.CB]
        # CB: defending=0.5, possession=0.2, availability=0.3
        # Mark possession as missing → remaining weights 0.5/0.3 must
        # renormalise to 0.5/0.8 and 0.3/0.8.
        dim_flags = [
            (dims[0], False),  # defending present
            (dims[1], True),   # possession missing
            (dims[2], False),  # availability present
        ]
        eff = _renormalised_weights(dim_flags, raw)
        assert eff["defending"] == pytest.approx(0.5 / 0.8)
        assert eff["possession"] == 0.0
        assert eff["availability"] == pytest.approx(0.3 / 0.8)
        # Sum of present weights must be 1.0.
        total = eff["defending"] + eff["availability"]
        assert total == pytest.approx(1.0)

    def test_missing_core_dimension_renormalises(self) -> None:
        """When a core dimension is missing, the remaining weights still
        renormalise (B1 does not veto the score on a single missing
        core dim — it downgrades confidence instead)."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        raw = B1_WEIGHTS[RoleFamily.CB]
        # Mark defending (core) as missing → remaining 0.2/0.3 must
        # renormalise to 0.2/0.5 and 0.3/0.5.
        dim_flags = [
            (dims[0], True),   # defending missing
            (dims[1], False),  # possession present
            (dims[2], False),  # availability present
        ]
        eff = _renormalised_weights(dim_flags, raw)
        assert eff["defending"] == 0.0
        assert eff["possession"] == pytest.approx(0.2 / 0.5)
        assert eff["availability"] == pytest.approx(0.3 / 0.5)
        total = eff["possession"] + eff["availability"]
        assert total == pytest.approx(1.0)

    def test_all_missing_returns_zeros(self) -> None:
        """When every dimension is missing, every effective weight is 0
        (caller must handle the empty-score case)."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        raw = B1_WEIGHTS[RoleFamily.CB]
        dim_flags = [(d, True) for d in dims]
        eff = _renormalised_weights(dim_flags, raw)
        for d in dims:
            assert eff[d.key] == 0.0

    def test_all_present_zero_weights_fallback_to_equal(self) -> None:
        """Defensive guard: if all present dimensions have raw weight 0
        (impossible in v1.0 but possible in a future revision), the
        function falls back to equal weights among present dims."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        # All-zero raw weights (violates v1.0 invariant but tests the
        # defensive guard).
        raw = {"defending": 0.0, "possession": 0.0, "availability": 0.0}
        dim_flags = [(d, False) for d in dims]
        eff = _renormalised_weights(dim_flags, raw)
        # All present → equal weights 1/3 each.
        for d in dims:
            assert eff[d.key] == pytest.approx(1.0 / 3.0)

    def test_single_dimension_role_no_renormalisation_needed(self) -> None:
        """GK has a single dimension (availability=1.0). Renormalisation
        is a no-op when the only dimension is present."""
        dims = B0_DIMENSIONS[RoleFamily.GK]
        raw = B1_WEIGHTS[RoleFamily.GK]
        dim_flags = [(d, False) for d in dims]
        eff = _renormalised_weights(dim_flags, raw)
        assert eff["availability"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# _vectorised_dimension_percentiles
# ---------------------------------------------------------------------------


class TestVectorisedDimensionPercentiles:
    def test_matches_legacy_dimension_percentile(self) -> None:
        """The vectorised dimension-percentile path must match the
        legacy per-player path."""
        dim = B0_DIMENSIONS[RoleFamily.CB][0]  # defending
        pool = [
            {"tackles": 30, "interceptions": 40},
            {"tackles": 20, "interceptions": 25},
            {"tackles": 10, "interceptions": 15},
            {"tackles": None, "interceptions": 50},
            {"tackles": 25, "interceptions": None},
        ]
        cols = ("tackles", "interceptions")
        arrays = _pool_column_arrays(pool, cols)
        dim_pct_arrays = _vectorised_dimension_percentiles(
            arrays, (dim,), len(pool)
        )
        assert len(dim_pct_arrays) == 1
        vec_arr = dim_pct_arrays[0]
        for i, player_row in enumerate(pool):
            legacy = _dimension_percentile(player_row, pool, dim)
            vec_val = vec_arr[i]
            if legacy.is_missing:
                assert np.isnan(vec_val)
            else:
                assert vec_val == pytest.approx(
                    legacy.dimension_percentile, rel=1e-9
                )


# ---------------------------------------------------------------------------
# _vectorised_weighted_scores
# ---------------------------------------------------------------------------


class TestVectorisedWeightedScores:
    def test_empty_pool(self) -> None:
        dims = B0_DIMENSIONS[RoleFamily.CB]
        raw = B1_WEIGHTS[RoleFamily.CB]
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
        arrays = _pool_column_arrays([], tuple(unique_cols))
        out = _vectorised_weighted_scores(arrays, dims, raw, 0)
        assert len(out) == 0

    def test_single_player_all_present(self) -> None:
        """A single player has no one below them → percentiles are 0;
        B1 score = sum(eff_weight * 0) = 0."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        raw = B1_WEIGHTS[RoleFamily.CB]
        pool = [{
            "tackles": 30, "interceptions": 40, "passes": 100,
            "minutes_played": 2000, "starts": 22,
        }]
        cols = tuple(
            c for d in dims for c in d.columns
        )
        seen: set[str] = set()
        unique_cols: list[str] = []
        for c in cols:
            if c not in seen:
                seen.add(c)
                unique_cols.append(c)
        arrays = _pool_column_arrays(pool, tuple(unique_cols))
        out = _vectorised_weighted_scores(arrays, dims, raw, 1)
        assert len(out) == 1
        # All column percentiles are 0 (no one below) → score = 0.
        assert out[0] == pytest.approx(0.0)

    def test_two_players_distinct_scores(self) -> None:
        """Player 0 (better in every column) must score higher than
        Player 1 under any weight set."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        raw = B1_WEIGHTS[RoleFamily.CB]
        pool = [
            {"tackles": 30, "interceptions": 40, "passes": 100,
             "minutes_played": 2000, "starts": 22},
            {"tackles": 10, "interceptions": 15, "passes": 50,
             "minutes_played": 1000, "starts": 11},
        ]
        cols = tuple(
            c for d in dims for c in d.columns
        )
        seen: set[str] = set()
        unique_cols: list[str] = []
        for c in cols:
            if c not in seen:
                seen.add(c)
                unique_cols.append(c)
        arrays = _pool_column_arrays(pool, tuple(unique_cols))
        out = _vectorised_weighted_scores(arrays, dims, raw, 2)
        assert out[0] > out[1]

    def test_all_missing_gets_neutral_50(self) -> None:
        """A player with all columns missing must get score 50.0
        (neutral placeholder, matching B0's convention)."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        raw = B1_WEIGHTS[RoleFamily.CB]
        pool = [
            {"tackles": None, "interceptions": None, "passes": None,
             "minutes_played": None, "starts": None},
            {"tackles": 30, "interceptions": 40, "passes": 100,
             "minutes_played": 2000, "starts": 22},
        ]
        cols = tuple(
            c for d in dims for c in d.columns
        )
        seen: set[str] = set()
        unique_cols: list[str] = []
        for c in cols:
            if c not in seen:
                seen.add(c)
                unique_cols.append(c)
        arrays = _pool_column_arrays(pool, tuple(unique_cols))
        out = _vectorised_weighted_scores(arrays, dims, raw, 2)
        assert out[0] == pytest.approx(50.0)

    def test_score_is_hand_recomputable(self) -> None:
        """B1 score == sum(effective_weight * dimension_percentile) for
        every player, where effective_weight is renormalised over
        present dimensions."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        raw = B1_WEIGHTS[RoleFamily.CB]
        pool = [
            {"tackles": 30, "interceptions": 40, "passes": 100,
             "minutes_played": 2000, "starts": 22},
            {"tackles": 20, "interceptions": 25, "passes": 80,
             "minutes_played": 1500, "starts": 17},
            {"tackles": 10, "interceptions": 15, "passes": 50,
             "minutes_played": 1000, "starts": 11},
            # Player 3 missing possession (supporting)
            {"tackles": 25, "interceptions": 30, "passes": None,
             "minutes_played": 1800, "starts": 20},
        ]
        cols = tuple(
            c for d in dims for c in d.columns
        )
        seen: set[str] = set()
        unique_cols: list[str] = []
        for c in cols:
            if c not in seen:
                seen.add(c)
                unique_cols.append(c)
        arrays = _pool_column_arrays(pool, tuple(unique_cols))
        scores = _vectorised_weighted_scores(arrays, dims, raw, 4)

        # Cross-check each player against the per-dimension percentile
        # path + renormalisation.
        dim_pct_arrays = _vectorised_dimension_percentiles(
            arrays, dims, 4
        )
        for i, player_row in enumerate(pool):
            # Determine which dimensions are present for this player.
            present_keys: set[str] = set()
            for dim in dims:
                b0_ds = _dimension_percentile(player_row, pool, dim)
                if not b0_ds.is_missing:
                    present_keys.add(dim.key)
            if not present_keys:
                assert scores[i] == pytest.approx(50.0)
                continue
            raw_sum = sum(raw[k] for k in present_keys)
            expected = 0.0
            for dim_idx, dim in enumerate(dims):
                if dim.key not in present_keys:
                    continue
                eff_w = raw[dim.key] / raw_sum
                dim_pct = dim_pct_arrays[dim_idx][i]
                assert not np.isnan(dim_pct)
                expected += eff_w * dim_pct
            assert scores[i] == pytest.approx(expected, rel=1e-9), (
                f"player {i} ({player_row}): expected {expected}, "
                f"got {scores[i]}"
            )

    def test_gk_score_equals_b0_score(self) -> None:
        """GK has weight availability=1.0 (only dimension), so B1 score
        must equal B0 score for GK."""
        from scoutfootball.evaluation.baseline_b0 import _vectorised_scores

        dims = B0_DIMENSIONS[RoleFamily.GK]
        raw = B1_WEIGHTS[RoleFamily.GK]
        pool = [
            {"minutes_played": 2700, "starts": 30},
            {"minutes_played": 1800, "starts": 20},
            {"minutes_played": 900, "starts": 10},
        ]
        cols = tuple(
            c for d in dims for c in d.columns
        )
        seen: set[str] = set()
        unique_cols: list[str] = []
        for c in cols:
            if c not in seen:
                seen.add(c)
                unique_cols.append(c)
        arrays = _pool_column_arrays(pool, tuple(unique_cols))
        b1_scores = _vectorised_weighted_scores(arrays, dims, raw, 3)
        b0_scores = _vectorised_scores(pool, dims, column_arrays=arrays)
        np.testing.assert_allclose(b1_scores, b0_scores, rtol=1e-9)


# ---------------------------------------------------------------------------
# _vectorised_weighted_scores_for_resample
# ---------------------------------------------------------------------------


class TestVectorisedWeightedScoresForResample:
    def test_identity_resample_matches_base(self) -> None:
        """Resampling with the identity permutation (indices 0..n-1)
        must reproduce the base B1 scores."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        raw = B1_WEIGHTS[RoleFamily.CB]
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
        seen: set[str] = set()
        unique_cols: list[str] = []
        for c in cols:
            if c not in seen:
                seen.add(c)
                unique_cols.append(c)
        base_arrays = _pool_column_arrays(pool, tuple(unique_cols))
        base_scores = _vectorised_weighted_scores(
            base_arrays, dims, raw, len(pool)
        )
        identity = np.arange(len(pool))
        resample_scores = _vectorised_weighted_scores_for_resample(
            base_arrays, dims, raw, identity, len(pool)
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
        raw = B1_WEIGHTS[RoleFamily.CB]
        pool = [
            {"tackles": 30, "interceptions": 40, "passes": 100,
             "minutes_played": 2000, "starts": 22},
            {"tackles": 20, "interceptions": 25, "passes": 80,
             "minutes_played": 1500, "starts": 17},
        ]
        intervals = _bootstrap_rank_interval(
            pool, dims, raw, n_bootstrap=10, seed=42
        )
        assert intervals == [None, None]

    def test_zero_bootstrap_returns_none(self) -> None:
        dims = B0_DIMENSIONS[RoleFamily.CB]
        raw = B1_WEIGHTS[RoleFamily.CB]
        pool = [
            {"tackles": 30, "interceptions": 40, "passes": 100,
             "minutes_played": 2000, "starts": 22},
        ] * 15
        intervals = _bootstrap_rank_interval(
            pool, dims, raw, n_bootstrap=0, seed=42
        )
        assert all(i is None for i in intervals)

    def test_large_pool_returns_intervals(self) -> None:
        """A pool of 15 players with n_bootstrap=5 returns a
        (p5, p50, p95) tuple per player."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        raw = B1_WEIGHTS[RoleFamily.CB]
        pool = [
            {
                "tackles": 10 + i, "interceptions": 15 + i, "passes": 100 + i * 5,
                "minutes_played": 1000 + i * 100, "starts": 11 + i,
            }
            for i in range(15)
        ]
        intervals = _bootstrap_rank_interval(
            pool, dims, raw, n_bootstrap=5, seed=42
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
        raw = B1_WEIGHTS[RoleFamily.CB]
        pool = [
            {
                "tackles": 10 + i, "interceptions": 15 + i, "passes": 100 + i * 5,
                "minutes_played": 1000 + i * 100, "starts": 11 + i,
            }
            for i in range(15)
        ]
        intervals_a = _bootstrap_rank_interval(
            pool, dims, raw, n_bootstrap=5, seed=42
        )
        intervals_b = _bootstrap_rank_interval(
            pool, dims, raw, n_bootstrap=5, seed=42
        )
        assert intervals_a == intervals_b

    def test_different_seeds_may_differ(self) -> None:
        """Different seeds should generally produce different intervals
        (sanity check that the seed actually drives the RNG)."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        raw = B1_WEIGHTS[RoleFamily.CB]
        pool = [
            {
                "tackles": 10 + i, "interceptions": 15 + i, "passes": 100 + i * 5,
                "minutes_played": 1000 + i * 100, "starts": 11 + i,
            }
            for i in range(15)
        ]
        intervals_a = _bootstrap_rank_interval(
            pool, dims, raw, n_bootstrap=20, seed=42
        )
        intervals_b = _bootstrap_rank_interval(
            pool, dims, raw, n_bootstrap=20, seed=99
        )
        # At least one player's interval must differ between seeds.
        diffs = [a != b for a, b in zip(intervals_a, intervals_b, strict=True)]
        assert any(diffs), "Different seeds produced identical intervals"


# ---------------------------------------------------------------------------
# _player_score (single-player full-B1 result)
# ---------------------------------------------------------------------------


class TestPlayerScore:
    def test_high_confidence_when_all_core_present(self) -> None:
        """All core dimensions present → confidence=high."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        raw = B1_WEIGHTS[RoleFamily.CB]
        pool = [
            {"tackles": 30, "interceptions": 40, "passes": 1500,
             "minutes_played": 2000, "starts": 22},
            {"tackles": 20, "interceptions": 25, "passes": 1000,
             "minutes_played": 1500, "starts": 17},
            {"tackles": 10, "interceptions": 15, "passes": 500,
             "minutes_played": 1000, "starts": 11},
        ]
        cols = tuple(
            c for d in dims for c in d.columns
        )
        seen: set[str] = set()
        unique_cols: list[str] = []
        for c in cols:
            if c not in seen:
                seen.add(c)
                unique_cols.append(c)
        arrays = _pool_column_arrays(pool, tuple(unique_cols))
        ps = _player_score(
            player_row=pool[0], pool_rows=pool, dimensions=dims,
            raw_weights=raw, role_family=RoleFamily.CB,
            rank_in_role=1, role_pool_size=3,
            rank_interval=(1, 1, 2),
            player_idx=0, column_arrays=arrays,
        )
        assert ps.confidence == "high"
        assert ps.missing_reason == ""
        assert ps.core_dimensions_used == ps.core_dimensions_total
        assert ps.weight_version == B1_WEIGHTS_VERSION
        assert ps.cross_position_comparable is False

    def test_medium_confidence_when_core_missing_but_score_still_computed(self) -> None:
        """When a core dimension is missing but at least one core dim
        is present, confidence=medium and missing_reason names the
        missing core dimension."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        raw = B1_WEIGHTS[RoleFamily.CB]
        # Player 0 missing defending (core) but has possession/availability.
        pool = [
            {"tackles": None, "interceptions": None, "passes": 1500,
             "minutes_played": 2000, "starts": 22},
            {"tackles": 20, "interceptions": 25, "passes": 1000,
             "minutes_played": 1500, "starts": 17},
            {"tackles": 10, "interceptions": 15, "passes": 500,
             "minutes_played": 1000, "starts": 11},
        ]
        cols = tuple(
            c for d in dims for c in d.columns
        )
        seen: set[str] = set()
        unique_cols: list[str] = []
        for c in cols:
            if c not in seen:
                seen.add(c)
                unique_cols.append(c)
        arrays = _pool_column_arrays(pool, tuple(unique_cols))
        ps = _player_score(
            player_row=pool[0], pool_rows=pool, dimensions=dims,
            raw_weights=raw, role_family=RoleFamily.CB,
            rank_in_role=1, role_pool_size=3,
            rank_interval=None,
            player_idx=0, column_arrays=arrays,
        )
        assert ps.confidence == "medium"
        assert "防守" in ps.missing_reason or "defending" in ps.missing_reason
        assert ps.core_dimensions_used < ps.core_dimensions_total

    def test_low_confidence_when_all_core_missing(self) -> None:
        """All core dimensions missing AND no supporting dims available
        → confidence=low, score=50.0 (neutral placeholder)."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        raw = B1_WEIGHTS[RoleFamily.CB]
        # Player 0 missing defending (core), availability (core), AND
        # possession (supporting) — so ALL dims are missing.
        pool = [
            {"tackles": None, "interceptions": None, "passes": None,
             "minutes_played": None, "starts": None},
            {"tackles": 20, "interceptions": 25, "passes": 1000,
             "minutes_played": 1500, "starts": 17},
            {"tackles": 10, "interceptions": 15, "passes": 500,
             "minutes_played": 1000, "starts": 11},
        ]
        cols = tuple(
            c for d in dims for c in d.columns
        )
        seen: set[str] = set()
        unique_cols: list[str] = []
        for c in cols:
            if c not in seen:
                seen.add(c)
                unique_cols.append(c)
        arrays = _pool_column_arrays(pool, tuple(unique_cols))
        ps = _player_score(
            player_row=pool[0], pool_rows=pool, dimensions=dims,
            raw_weights=raw, role_family=RoleFamily.CB,
            rank_in_role=1, role_pool_size=3,
            rank_interval=None,
            player_idx=0, column_arrays=arrays,
        )
        assert ps.confidence == "low"
        assert ps.score == pytest.approx(50.0)
        assert "全部核心维度缺失" in ps.missing_reason

    def test_score_is_hand_recomputable(self) -> None:
        """B1 score == sum(effective_weight * dimension_percentile)
        over present dimensions."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        raw = B1_WEIGHTS[RoleFamily.CB]
        pool = [
            {"tackles": 30, "interceptions": 40, "passes": 1500,
             "minutes_played": 2000, "starts": 22},
            {"tackles": 20, "interceptions": 25, "passes": 1000,
             "minutes_played": 1500, "starts": 17},
            {"tackles": 10, "interceptions": 15, "passes": 500,
             "minutes_played": 1000, "starts": 11},
        ]
        cols = tuple(
            c for d in dims for c in d.columns
        )
        seen: set[str] = set()
        unique_cols: list[str] = []
        for c in cols:
            if c not in seen:
                seen.add(c)
                unique_cols.append(c)
        arrays = _pool_column_arrays(pool, tuple(unique_cols))
        ps = _player_score(
            player_row=pool[0], pool_rows=pool, dimensions=dims,
            raw_weights=raw, role_family=RoleFamily.CB,
            rank_in_role=1, role_pool_size=3,
            rank_interval=None,
            player_idx=0, column_arrays=arrays,
        )
        # Hand-recompute from the dimensions list.
        expected = sum(d.contribution for d in ps.dimensions if not d.is_missing)
        assert ps.score == pytest.approx(expected, rel=1e-9)

    def test_dimension_records_carry_weights(self) -> None:
        """Each B1DimensionScore must carry the raw weight (from the
        versioned table) and the effective weight (renormalised)."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        raw = B1_WEIGHTS[RoleFamily.CB]
        pool = [
            {"tackles": 30, "interceptions": 40, "passes": 1500,
             "minutes_played": 2000, "starts": 22},
            {"tackles": 20, "interceptions": 25, "passes": 1000,
             "minutes_played": 1500, "starts": 17},
        ]
        cols = tuple(
            c for d in dims for c in d.columns
        )
        seen: set[str] = set()
        unique_cols: list[str] = []
        for c in cols:
            if c not in seen:
                seen.add(c)
                unique_cols.append(c)
        arrays = _pool_column_arrays(pool, tuple(unique_cols))
        ps = _player_score(
            player_row=pool[0], pool_rows=pool, dimensions=dims,
            raw_weights=raw, role_family=RoleFamily.CB,
            rank_in_role=1, role_pool_size=2,
            rank_interval=None,
            player_idx=0, column_arrays=arrays,
        )
        for d in ps.dimensions:
            assert d.weight == pytest.approx(raw[d.dimension])
            # All dims present → effective == raw.
            assert d.effective_weight == pytest.approx(raw[d.dimension])

    def test_rank_interval_propagated(self) -> None:
        """The rank_interval tuple must propagate into rank_p5/p50/p95."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        raw = B1_WEIGHTS[RoleFamily.CB]
        pool = [
            {"tackles": 30, "interceptions": 40, "passes": 1500,
             "minutes_played": 2000, "starts": 22},
            {"tackles": 20, "interceptions": 25, "passes": 1000,
             "minutes_played": 1500, "starts": 17},
        ]
        cols = tuple(
            c for d in dims for c in d.columns
        )
        seen: set[str] = set()
        unique_cols: list[str] = []
        for c in cols:
            if c not in seen:
                seen.add(c)
                unique_cols.append(c)
        arrays = _pool_column_arrays(pool, tuple(unique_cols))
        ps = _player_score(
            player_row=pool[0], pool_rows=pool, dimensions=dims,
            raw_weights=raw, role_family=RoleFamily.CB,
            rank_in_role=1, role_pool_size=2,
            rank_interval=(1, 2, 3),
            player_idx=0, column_arrays=arrays,
        )
        assert ps.rank_p5 == 1
        assert ps.rank_p50 == 2
        assert ps.rank_p95 == 3

    def test_role_family_value_used(self) -> None:
        """ps.role_family must be the RoleFamily's string value, not
        the enum object."""
        dims = B0_DIMENSIONS[RoleFamily.CB]
        raw = B1_WEIGHTS[RoleFamily.CB]
        pool = [
            {"tackles": 30, "interceptions": 40, "passes": 1500,
             "minutes_played": 2000, "starts": 22},
        ]
        cols = tuple(
            c for d in dims for c in d.columns
        )
        seen: set[str] = set()
        unique_cols: list[str] = []
        for c in cols:
            if c not in seen:
                seen.add(c)
                unique_cols.append(c)
        arrays = _pool_column_arrays(pool, tuple(unique_cols))
        ps = _player_score(
            player_row=pool[0], pool_rows=pool, dimensions=dims,
            raw_weights=raw, role_family=RoleFamily.CB,
            rank_in_role=1, role_pool_size=1,
            rank_interval=None,
            player_idx=0, column_arrays=arrays,
        )
        assert ps.role_family == "CB"
        assert isinstance(ps.role_family, str)


# ---------------------------------------------------------------------------
# compute_b1_baseline — fail-closed paths
# ---------------------------------------------------------------------------


class TestComputeB1BaselineFailClosed:
    def test_missing_feature_matrix(self, tmp_path: Path) -> None:
        """When rating_feature_matrix.parquet is absent, status=unavailable."""
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_b1_baseline(settings=settings, n_bootstrap=5)
        assert rep["status"] == "unavailable"
        assert rep["schema"] == BASELINE_B1_SCHEMA
        assert rep["schema_version"] == BASELINE_B1_VERSION
        assert "reason" in rep["evidence"]
        assert "rating_feature_matrix.parquet missing" in rep["evidence"]["reason"]

    def test_empty_feature_matrix(self, tmp_path: Path) -> None:
        """When the feature matrix has 0 rows, status=unavailable."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, pd.DataFrame())
        rep = compute_b1_baseline(settings=settings, n_bootstrap=5)
        assert rep["status"] == "unavailable"
        assert "empty" in rep["evidence"]["reason"]

    def test_limitations_present_even_on_failure(self, tmp_path: Path) -> None:
        """Limitations must be present even when status=unavailable."""
        settings = PlatformSettings.from_root(tmp_path)
        rep = compute_b1_baseline(settings=settings, n_bootstrap=5)
        assert "limitations" in rep
        assert isinstance(rep["limitations"], list)
        assert len(rep["limitations"]) > 0


# ---------------------------------------------------------------------------
# compute_b1_baseline — happy path
# ---------------------------------------------------------------------------


class TestComputeB1BaselineHappy:
    def test_status_ok(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b1_baseline(settings=settings, n_bootstrap=5)
        assert rep["status"] == "ok"
        assert rep["schema"] == BASELINE_B1_SCHEMA
        assert rep["schema_version"] == BASELINE_B1_VERSION

    def test_weight_version_emitted(self, tmp_path: Path) -> None:
        """The report must carry the weight version at the top level."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b1_baseline(settings=settings, n_bootstrap=5)
        assert rep["weight_version"] == B1_WEIGHTS_VERSION

    def test_total_players_scored_excludes_unknown(self, tmp_path: Path) -> None:
        """UNKNOWN rows are counted in by_role_family but not scored."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b1_baseline(settings=settings, n_bootstrap=5)
        # 5 rows: 2 CB + 1 ST + 1 GK + 1 UNKNOWN. Scored = 4.
        assert rep["evidence"]["total_players_scored"] == 4
        # by_role_family includes UNKNOWN count.
        assert rep["evidence"]["by_role_family"].get("UNKNOWN") == 1

    def test_role_summaries_present(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b1_baseline(settings=settings, n_bootstrap=5)
        summaries = rep["evidence"]["role_summaries"]
        roles = {s["role_family"] for s in summaries}
        assert roles == {"CB", "ST", "GK"}

    def test_role_summary_has_weights_and_version(self, tmp_path: Path) -> None:
        """Each role summary must report the weight version and the raw
        weight set for that role."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b1_baseline(settings=settings, n_bootstrap=5)
        for rs in rep["evidence"]["role_summaries"]:
            assert rs["weight_version"] == B1_WEIGHTS_VERSION
            assert isinstance(rs["weights"], dict)
            assert len(rs["weights"]) > 0
            # Weights must sum to ~1.0.
            total = sum(float(w) for w in rs["weights"].values())
            assert abs(total - 1.0) < 1e-9

    def test_player_records_have_required_fields(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b1_baseline(settings=settings, n_bootstrap=5)
        for p in rep["evidence"]["players"]:
            assert "score" in p
            assert "rank_in_role" in p
            assert "role_pool_size" in p
            assert "confidence" in p
            assert "missing_reason" in p
            assert "core_dimensions_used" in p
            assert "core_dimensions_total" in p
            assert "dimensions" in p
            assert "weight_version" in p
            assert "cross_position_comparable" in p
            assert p["weight_version"] == B1_WEIGHTS_VERSION

    def test_player_dimensions_have_weights(self, tmp_path: Path) -> None:
        """Each player's per-dimension records must carry weight and
        effective_weight fields."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b1_baseline(settings=settings, n_bootstrap=5)
        for p in rep["evidence"]["players"]:
            for d in p["dimensions"]:
                assert "weight" in d
                assert "effective_weight" in d
                assert "contribution" in d
                assert isinstance(d["weight"], (int, float))
                assert isinstance(d["effective_weight"], (int, float))

    def test_score_is_hand_recomputable_from_dimensions(self, tmp_path: Path) -> None:
        """For every player, score == sum(d.contribution for d in
        dimensions if not d.is_missing), within rounding tolerance."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b1_baseline(settings=settings, n_bootstrap=5)
        for p in rep["evidence"]["players"]:
            if p["confidence"] == "low":
                # All core missing → score is the neutral 50.0 placeholder.
                assert p["score"] == pytest.approx(50.0, abs=0.01)
                continue
            expected = sum(
                d["contribution"] for d in p["dimensions"]
                if not d["is_missing"]
            )
            assert p["score"] == pytest.approx(expected, abs=0.05), (
                f"{p['player_name']}: score={p['score']}, "
                f"expected={expected}"
            )

    def test_cross_position_comparable_always_false(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b1_baseline(settings=settings, n_bootstrap=5)
        for p in rep["evidence"]["players"]:
            assert p["cross_position_comparable"] is False

    def test_gk_score_equals_b0_score(self, tmp_path: Path) -> None:
        """GK has weight availability=1.0 (single dimension), so B1
        score must equal B0 score for GK."""
        from scoutfootball.evaluation.baseline_b0 import compute_b0_baseline

        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep_b1 = compute_b1_baseline(settings=settings, n_bootstrap=5)
        rep_b0 = compute_b0_baseline(settings=settings, n_bootstrap=5)
        gk_b1 = {
            p["player_name"]: p["score"]
            for p in rep_b1["evidence"]["players"]
            if p["role_family"] == "GK"
        }
        gk_b0 = {
            p["player_name"]: p["score"]
            for p in rep_b0["evidence"]["players"]
            if p["role_family"] == "GK"
        }
        assert set(gk_b1.keys()) == set(gk_b0.keys())
        for name in gk_b1:
            assert gk_b1[name] == pytest.approx(gk_b0[name], rel=1e-9)

    def test_gk_role_still_provisional(self, tmp_path: Path) -> None:
        """GK should still be scored (availability-only), but the
        limitations must mention gk_provisional."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b1_baseline(settings=settings, n_bootstrap=5)
        gk_players = [p for p in rep["evidence"]["players"]
                      if p["role_family"] == "GK"]
        assert len(gk_players) == 1
        gk_lim = [lim for lim in rep["limitations"] if "gk_provisional" in lim]
        assert len(gk_lim) >= 1

    def test_canonical_player_id_fallback(self, tmp_path: Path) -> None:
        """When canonical_player_id column is missing, B1 falls back to
        unresolved:<source>:<player_id> per the PRS-1 contract."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b1_baseline(settings=settings, n_bootstrap=5)
        for p in rep["evidence"]["players"]:
            assert p["canonical_player_id"].startswith("unresolved:")

    def test_parameters_recorded(self, tmp_path: Path) -> None:
        """The report must record n_bootstrap, seed, min_bootstrap_pool,
        and weight_version under 'parameters'."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b1_baseline(settings=settings, n_bootstrap=7, seed=123)
        params = rep["parameters"]
        assert params["n_bootstrap"] == 7
        assert params["seed"] == 123
        assert "min_bootstrap_pool" in params
        assert params["weight_version"] == B1_WEIGHTS_VERSION

    def test_players_sorted_by_role_then_rank(self, tmp_path: Path) -> None:
        """Players must be sorted by role_family, then by rank_in_role."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b1_baseline(settings=settings, n_bootstrap=5)
        players = rep["evidence"]["players"]
        keys = [(p["role_family"], p["rank_in_role"]) for p in players]
        assert keys == sorted(keys)

    def test_json_serializable_full_report(self, tmp_path: Path) -> None:
        """The full report must be JSON-serialisable."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b1_baseline(settings=settings, n_bootstrap=5)
        json.dumps(rep, ensure_ascii=False)

    def test_rank_interval_none_for_small_pool(self, tmp_path: Path) -> None:
        """When a role pool is below _MIN_BOOTSTRAP_POOL, every player's
        rank_interval in that role must be None."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b1_baseline(settings=settings, n_bootstrap=5)
        # In the default fixture, every role has < 10 members.
        for p in rep["evidence"]["players"]:
            assert p["rank_interval"] is None

    def test_rank_interval_present_for_large_pool(self, tmp_path: Path) -> None:
        """When a role pool >= 10, every player gets a rank_interval."""
        settings = PlatformSettings.from_root(tmp_path)
        rows = [
            {
                "player_id": f"u|{i}", "player_name": f"CB-{i}",
                "season_id": "2425", "position_group": "CB",
                "source_name": "understat",
                "minutes_played": 1000 + i * 100, "starts": 11 + i,
                "tackles": 10 + i, "interceptions": 15 + i,
                "passes": 100 + i * 5,
                "goals": 0, "assists": 0, "npxg": 0.0, "xa": 0.0,
                "defense_missing": False, "possession_missing": False,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            }
            for i in range(15)
        ]
        _write_rating_feature_matrix(settings, pd.DataFrame(rows))
        rep = compute_b1_baseline(settings=settings, n_bootstrap=5)
        cb_players = [p for p in rep["evidence"]["players"]
                      if p["role_family"] == "CB"]
        assert len(cb_players) == 15
        for p in cb_players:
            assert p["rank_interval"] is not None
            ri = p["rank_interval"]
            assert 1 <= ri["p5"] <= 15
            assert 1 <= ri["p50"] <= 15
            assert 1 <= ri["p95"] <= 15
            assert ri["p5"] <= ri["p50"] <= ri["p95"]

    def test_seed_reproducibility(self, tmp_path: Path) -> None:
        """Same seed → identical rank intervals."""
        settings = PlatformSettings.from_root(tmp_path)
        rows = [
            {
                "player_id": f"u|{i}", "player_name": f"CB-{i}",
                "season_id": "2425", "position_group": "CB",
                "source_name": "understat",
                "minutes_played": 1000 + i * 100, "starts": 11 + i,
                "tackles": 10 + i, "interceptions": 15 + i,
                "passes": 100 + i * 5,
                "goals": 0, "assists": 0, "npxg": 0.0, "xa": 0.0,
                "defense_missing": False, "possession_missing": False,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            }
            for i in range(15)
        ]
        _write_rating_feature_matrix(settings, pd.DataFrame(rows))
        rep_a = compute_b1_baseline(settings=settings, n_bootstrap=5, seed=42)
        rep_b = compute_b1_baseline(settings=settings, n_bootstrap=5, seed=42)
        for a, b in zip(
            rep_a["evidence"]["players"], rep_b["evidence"]["players"], strict=True
        ):
            assert a["rank_interval"] == b["rank_interval"]


# ---------------------------------------------------------------------------
# Cohort filtering
# ---------------------------------------------------------------------------


class TestCohortFiltering:
    def test_cohort_restricts_membership_by_role(self, tmp_path: Path) -> None:
        """When a cohort_definition restricts role_families, only
        members of those roles are scored."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        # preview_cohort reads player_match.parquet, so write that too.
        _write_player_match(settings, _make_feature_matrix_df())
        # Restrict to CB only. The fixture has 2 CBs.
        cohort = CohortDefinition(
            name="cb-only",
            season_ids=frozenset({"2425"}),
            role_families=frozenset({RoleFamily.CB}),
        )
        rep = compute_b1_baseline(
            settings=settings, cohort_definition=cohort, n_bootstrap=5
        )
        assert rep["status"] == "ok"
        # 2 CBs in the fixture.
        assert rep["evidence"]["total_players_scored"] == 2
        players = rep["evidence"]["players"]
        assert len(players) == 2
        # Every scored player must be a CB.
        for p in players:
            assert p["role_family"] == "CB"

    def test_cohort_hash_propagated(self, tmp_path: Path) -> None:
        """When a cohort is provided, cohort_hash and membership_hash
        are surfaced in the report."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        _write_player_match(settings, _make_feature_matrix_df())
        cohort = CohortDefinition(
            name="cb-only",
            season_ids=frozenset({"2425"}),
            role_families=frozenset({RoleFamily.CB}),
        )
        rep = compute_b1_baseline(
            settings=settings, cohort_definition=cohort, n_bootstrap=5
        )
        assert rep["status"] == "ok"
        assert rep.get("cohort_hash") is not None
        assert rep.get("membership_hash") is not None

    def test_empty_cohort_returns_zero_scored(self, tmp_path: Path) -> None:
        """A cohort that matches no players returns status=ok with 0
        scored players. The fixture has no canonical_player_id column,
        so require_resolved_identity=True excludes every row."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        _write_player_match(settings, _make_feature_matrix_df())
        cohort = CohortDefinition(
            name="empty",
            require_resolved_identity=True,
        )
        rep = compute_b1_baseline(
            settings=settings, cohort_definition=cohort, n_bootstrap=5
        )
        assert rep["status"] == "ok"
        assert rep["evidence"]["total_players_scored"] == 0
        assert rep["evidence"]["players"] == []


# ---------------------------------------------------------------------------
# B1 vs B0 divergence (the whole point of B1)
# ---------------------------------------------------------------------------


class TestB1VsB0Divergence:
    def test_b1_diverges_from_b0_when_weights_unequal(self, tmp_path: Path) -> None:
        """For roles where B1 weights are NOT all-equal (i.e. any role
        except GK), B1 and B0 scores must diverge for at least one
        player when dimension percentiles differ across dimensions."""
        from scoutfootball.evaluation.baseline_b0 import compute_b0_baseline

        settings = PlatformSettings.from_root(tmp_path)
        # Build a CB pool where defending/possession/availability
        # percentiles are NOT perfectly correlated across players —
        # so weighting matters. If all columns were perfectly
        # correlated, every dimension percentile would be the same and
        # weighting would be a no-op.
        rows = [
            {
                "player_id": f"u|{i}", "player_name": f"CB-{i}",
                "season_id": "2425", "position_group": "CB",
                "source_name": "understat",
                # Availability: increases with i
                "minutes_played": 1000 + i * 100, "starts": 11 + i,
                # Defending: DEcreases with i (inverse correlation)
                "tackles": 100 - i * 3, "interceptions": 120 - i * 4,
                # Possession: increases with i but at a different rate
                "passes": 200 + i * 50,
                "goals": 0, "assists": 0, "npxg": 0.0, "xa": 0.0,
                "defense_missing": False, "possession_missing": False,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            }
            for i in range(15)
        ]
        _write_rating_feature_matrix(settings, pd.DataFrame(rows))
        rep_b1 = compute_b1_baseline(settings=settings, n_bootstrap=5)
        rep_b0 = compute_b0_baseline(settings=settings, n_bootstrap=5)
        b1_scores = {p["player_name"]: p["score"]
                     for p in rep_b1["evidence"]["players"]}
        b0_scores = {p["player_name"]: p["score"]
                     for p in rep_b0["evidence"]["players"]}
        assert set(b1_scores.keys()) == set(b0_scores.keys())
        # At least one player must have a different B1 vs B0 score
        # (because CB's defending=0.5/possession=0.2/availability=0.3
        # weights are not all 1/3, and the dimensions are not
        # perfectly correlated).
        diffs = [
            name for name in b1_scores
            if abs(b1_scores[name] - b0_scores[name]) > 1e-6
        ]
        assert len(diffs) > 0, "B1 and B0 produced identical scores for every CB"

    def test_b1_ranks_can_differ_from_b0(self, tmp_path: Path) -> None:
        """When weights matter, B1 ranks can differ from B0 ranks."""
        from scoutfootball.evaluation.baseline_b0 import compute_b0_baseline

        settings = PlatformSettings.from_root(tmp_path)
        # Build a CB pool where one player is strong in defending (high
        # B1 weight) but weak in possession (low B1 weight). B0 ranks
        # them by equal-weight average; B1 should rank them higher
        # because defending is weighted 0.5 vs possession 0.2.
        rows = [
            # CB-DEF: strong defending, weak possession, avg availability
            {
                "player_id": "u|1", "player_name": "CB-DEF",
                "season_id": "2425", "position_group": "CB",
                "source_name": "understat",
                "minutes_played": 2000, "starts": 22,
                "tackles": 100, "interceptions": 100, "passes": 50,
                "goals": 0, "assists": 0, "npxg": 0.0, "xa": 0.0,
                "defense_missing": False, "possession_missing": False,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            },
            # CB-POS: weak defending, strong possession, avg availability
            {
                "player_id": "u|2", "player_name": "CB-POS",
                "season_id": "2425", "position_group": "CB",
                "source_name": "understat",
                "minutes_played": 2000, "starts": 22,
                "tackles": 10, "interceptions": 10, "passes": 5000,
                "goals": 0, "assists": 0, "npxg": 0.0, "xa": 0.0,
                "defense_missing": False, "possession_missing": False,
                "xT_VAEP_missing": False, "goalkeeper_missing": True,
            },
        ]
        _write_rating_feature_matrix(settings, pd.DataFrame(rows))
        rep_b1 = compute_b1_baseline(settings=settings, n_bootstrap=5)
        rep_b0 = compute_b0_baseline(settings=settings, n_bootstrap=5)
        b1_ranks = {p["player_name"]: p["rank_in_role"]
                    for p in rep_b1["evidence"]["players"]}
        b0_ranks = {p["player_name"]: p["rank_in_role"]
                    for p in rep_b0["evidence"]["players"]}
        # CB-DEF has strong defending (weight 0.5 in B1). B1 should
        # rank CB-DEF higher (rank 1) than B0 (which weights defending
        # and possession equally at 1/3 each, plus availability 1/3).
        # Note: with only 2 players the percentile math is coarse, but
        # B1's heavier defending weight should favour CB-DEF.
        assert b1_ranks["CB-DEF"] <= b0_ranks["CB-DEF"], (
            f"B1 did not favour CB-DEF: b1={b1_ranks}, b0={b0_ranks}"
        )


# ---------------------------------------------------------------------------
# Limitations
# ---------------------------------------------------------------------------


class TestLimitations:
    def test_limitations_mention_weight_version(self, tmp_path: Path) -> None:
        """At least one limitation must mention the weight versioning
        contract."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b1_baseline(settings=settings, n_bootstrap=5)
        joined = " ".join(rep["limitations"])
        assert "B1_WEIGHTS_VERSION" in joined or "weight_version" in joined

    def test_limitations_mention_renormalisation(self, tmp_path: Path) -> None:
        """At least one limitation must mention weight renormalisation
        on missing dimensions."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b1_baseline(settings=settings, n_bootstrap=5)
        joined = " ".join(rep["limitations"])
        assert "再归一化" in joined or "renormal" in joined.lower()

    def test_limitations_mention_gk_provisional(self, tmp_path: Path) -> None:
        """At least one limitation must mention GK provisional status."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b1_baseline(settings=settings, n_bootstrap=5)
        joined = " ".join(rep["limitations"])
        assert "gk_provisional" in joined

    def test_limitations_mention_b0_reuse(self, tmp_path: Path) -> None:
        """At least one limitation must mention B1 reuses B0_DIMENSIONS."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b1_baseline(settings=settings, n_bootstrap=5)
        joined = " ".join(rep["limitations"])
        assert "B0_DIMENSIONS" in joined or "B0" in joined

    def test_limitations_mention_bootstrap(self, tmp_path: Path) -> None:
        """At least one limitation must mention the bootstrap rank
        interval."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_rating_feature_matrix(settings, _make_feature_matrix_df())
        rep = compute_b1_baseline(settings=settings, n_bootstrap=5)
        joined = " ".join(rep["limitations"])
        assert "bootstrap" in joined.lower() or "Bootstrap" in joined
