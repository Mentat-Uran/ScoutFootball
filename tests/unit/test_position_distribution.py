"""Tests for position distribution and same_position_score logic.

Covers:
1. map_position_detailed() — Understat and FBref position string parsing
2. same_position_score percentile calculation with small-group fallback
3. Top N position distribution alert
4. Position slot caps in team aggregation weights
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


# Import from optimizer package
def _load_optimizer_module():
    """Import optimizer package modules directly."""
    repo_root = Path(__file__).resolve().parents[2]
    scripts_dir = str(repo_root / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import types

    import optimizer.constants as _c
    from optimizer.team_aggregation import build_team_aggregation_weights
    mod = types.SimpleNamespace()
    mod.POSITION_SLOT_CAPS = _c.POSITION_SLOT_CAPS
    mod.POSITION_SLOT_GROUPS = _c.POSITION_SLOT_GROUPS
    mod._build_team_aggregation_weights = build_team_aggregation_weights
    mod.map_position_detailed = _c.map_position_detailed
    return mod

_mod = _load_optimizer_module()
POSITION_SLOT_CAPS = _mod.POSITION_SLOT_CAPS
POSITION_SLOT_GROUPS = _mod.POSITION_SLOT_GROUPS
_build_team_aggregation_weights = _mod._build_team_aggregation_weights
map_position_detailed = _mod.map_position_detailed

# ---------------------------------------------------------------------------
# 1. map_position_detailed
# ---------------------------------------------------------------------------


class TestMapPositionDetailedUnderstat:
    """Understat uses single letters: D, M, F, S and combinations."""

    @pytest.mark.parametrize(
        "input_str, expected_pos, expected_conf",
        [
            ("D", "CB", "low"),
            ("D M", "FB", "medium"),
            ("D M S", "FB", "medium"),
            ("F M S", "W", "medium"),
            ("F M", "W", "medium"),
            ("M", "CM", "low"),
            ("F", "ST", "low"),
            ("S", "CM", "low"),
            ("D S", "CB", "low"),
        ],
    )
    def test_understat_mappings(self, input_str, expected_pos, expected_conf):
        pos, source, confidence = map_position_detailed(input_str)
        assert pos == expected_pos
        assert confidence == expected_conf
        assert source == input_str


class TestMapPositionDetailedFBref:
    """FBref uses 2-letter codes: GK, DF, MF, FW and comma-separated combos."""

    @pytest.mark.parametrize(
        "input_str, expected_pos, expected_conf",
        [
            ("GK", "GK", "high"),
            ("DF,MF", "FB", "high"),
            ("MF,FW", "AM", "high"),
            ("FW,MF", "W", "high"),
            ("DF", "CB", "medium"),
            ("MF", "CM", "medium"),
            ("FW", "ST", "medium"),
        ],
    )
    def test_fbref_mappings(self, input_str, expected_pos, expected_conf):
        pos, source, confidence = map_position_detailed(input_str)
        assert pos == expected_pos
        assert confidence == expected_conf
        assert source == input_str


class TestMapPositionDetailedEdgeCases:
    """Edge cases: None, empty string, GK."""

    def test_none_input(self):
        pos, source, confidence = map_position_detailed(None)
        assert pos == "CM"
        assert source == "None"
        assert confidence == "low"

    def test_empty_string(self):
        pos, source, confidence = map_position_detailed("")
        assert pos == "CM"
        assert source == ""
        assert confidence == "low"

    def test_gk_string(self):
        pos, source, confidence = map_position_detailed("GK")
        assert pos == "GK"
        assert source == "GK"
        assert confidence == "high"


# ---------------------------------------------------------------------------
# 2. same_position_score calculation
# ---------------------------------------------------------------------------

MIN_POSITION_GROUP_SIZE = 5


def _compute_same_position_score(df: pd.DataFrame) -> pd.Series:
    """Replicate the same_position_score logic from optimize_ratings_gpu.main()."""

    def _position_percentile(group):
        if len(group) < MIN_POSITION_GROUP_SIZE:
            return pd.Series(np.nan, index=group.index)
        return group.rank(pct=True) * 100

    result = (
        df.groupby(["season", "sub_position"])["optimized_score"]
        .transform(_position_percentile)
    )

    needs_fallback = result.isna()
    if needs_fallback.any():
        global_pct = (
            df.loc[needs_fallback]
            .groupby("sub_position")["optimized_score"]
            .transform(
                lambda g: g.rank(pct=True) * 100
                if len(g) >= MIN_POSITION_GROUP_SIZE
                else pd.Series(np.nan, index=g.index),
            )
        )
        result.loc[needs_fallback] = global_pct

    return result


class TestSamePositionScore:
    def test_percentile_ranks_within_group(self):
        """Within a season+position group with >=5 members, percentiles are correct."""
        df = pd.DataFrame(
            {
                "season": ["2425"] * 8,
                "sub_position": ["CB"] * 8,
                "optimized_score": [80, 70, 60, 50, 40, 30, 20, 10],
            },
        )
        result = _compute_same_position_score(df)
        # Highest score should get highest percentile
        assert result.iloc[0] > result.iloc[-1]
        # All values should be in (0, 100]
        assert (result > 0).all() and (result <= 100).all()

    def test_small_group_falls_back_to_global(self):
        """Groups with <5 members fall back to global percentile within that position.

        The fallback groups only the NaN rows by sub_position, so the fallback
        group must itself have >=5 members to produce non-NaN percentiles.
        """
        # 3 CBs in season A (too small for season+position), 3 CBs in season B
        # (also too small). Together the fallback set has 6 CBs >= 5.
        df = pd.DataFrame(
            {
                "season": ["2324"] * 3 + ["2425"] * 3,
                "sub_position": ["CB"] * 6,
                "optimized_score": [90, 80, 70, 60, 50, 40],
            },
        )
        result = _compute_same_position_score(df)
        # Both season groups are <5, so all fall into the fallback.
        # The fallback set has 6 CBs >= 5, so all should get global percentiles.
        assert result.notna().all()

    def test_very_small_global_group_gets_nan(self):
        """If even the global position group has <5 members, result is NaN."""
        df = pd.DataFrame(
            {
                "season": ["2324"] * 2 + ["2425"] * 2,
                "sub_position": ["GK"] * 4,
                "optimized_score": [90, 80, 70, 60],
            },
        )
        result = _compute_same_position_score(df)
        # Total 4 GKs < 5, so all should be NaN
        assert result.isna().all()


# ---------------------------------------------------------------------------
# 3. Top N position distribution alert
# ---------------------------------------------------------------------------

POSITION_DOMINATION_THRESHOLD = 0.40


def _check_position_domination(df: pd.DataFrame, top_n: int = 100) -> dict:
    """Check if any single position exceeds the threshold in the Top N."""
    top = df.nlargest(top_n, "optimized_score")
    counts = top["sub_position"].value_counts()
    total = len(top)
    alerts = {}
    for pos, count in counts.items():
        fraction = count / total
        if fraction > POSITION_DOMINATION_THRESHOLD:
            alerts[pos] = fraction
    return alerts


class TestTopNPositionDistribution:
    def test_alert_triggers_when_position_dominates(self):
        """When CB > 40% of Top 100, alert should trigger."""
        n = 120
        positions = (
            ["CB"] * 50 + ["ST"] * 20 + ["CM"] * 20 + ["W"] * 15
            + ["GK"] * 5 + ["FB"] * 5 + ["AM"] * 3 + ["DM"] * 2
        )
        positions = positions[:n]
        scores = list(range(n, 0, -1))  # descending
        df = pd.DataFrame(
            {
                "sub_position": positions,
                "optimized_score": scores,
            },
        )
        alerts = _check_position_domination(df, top_n=100)
        assert "CB" in alerts
        assert alerts["CB"] > POSITION_DOMINATION_THRESHOLD

    def test_no_alert_when_balanced(self):
        """When no position exceeds 40%, no alert should trigger."""
        n = 120
        positions = (
            ["CB"] * 18 + ["ST"] * 18 + ["CM"] * 18 + ["W"] * 18
            + ["FB"] * 16 + ["AM"] * 14 + ["DM"] * 10 + ["GK"] * 8
        )
        positions = positions[:n]
        scores = list(range(n, 0, -1))
        df = pd.DataFrame(
            {
                "sub_position": positions,
                "optimized_score": scores,
            },
        )
        alerts = _check_position_domination(df, top_n=100)
        assert len(alerts) == 0


# ---------------------------------------------------------------------------
# 4. Position slot caps
# ---------------------------------------------------------------------------


class TestPositionSlotCaps:
    def test_slot_group_mapping(self):
        """POSITION_SLOT_GROUPS maps each position to the correct slot."""
        assert POSITION_SLOT_GROUPS["GK"] == "GK"
        assert POSITION_SLOT_GROUPS["CB"] == "CB"
        assert POSITION_SLOT_GROUPS["FB"] == "FB"
        assert POSITION_SLOT_GROUPS["DM"] == "MF"
        assert POSITION_SLOT_GROUPS["CM"] == "MF"
        assert POSITION_SLOT_GROUPS["AM"] == "ATT"
        assert POSITION_SLOT_GROUPS["W"] == "ATT"
        assert POSITION_SLOT_GROUPS["ST"] == "ATT"

    def test_slot_caps_defined(self):
        """All slot groups have caps defined."""
        for slot_group in POSITION_SLOT_GROUPS.values():
            assert slot_group in POSITION_SLOT_CAPS

    def test_slot_cap_scaling_logic(self):
        """Verify the slot cap scaling logic: when a slot's total weight exceeds
        its cap, weights in that slot are scaled down proportionally.

        The current weight scheme produces shares that sum to ~1.0 per team-season,
        so slot totals rarely exceed the caps (which are in the 1.0–2.5 range).
        This test verifies the scaling math directly rather than relying on the
        full pipeline to trigger the cap.
        """
        # Simulate a scenario where slot totals exceed caps
        # 5 CBs each with weight 0.6 → slot total = 3.0, cap = 2.5
        # 2 STs each with weight 0.5 → slot total = 1.0, cap = 2.5
        cb_weights = np.array([0.6] * 5, dtype=np.float64)
        st_weights = np.array([0.5] * 2, dtype=np.float64)
        raw_weights = np.concatenate([cb_weights, st_weights])

        slot_groups = ["CB"] * 5 + ["ATT"] * 2
        slot_caps = np.array([POSITION_SLOT_CAPS[g] for g in slot_groups], dtype=np.float64)

        # Compute slot totals
        slot_totals = np.zeros_like(raw_weights)
        for sg in set(slot_groups):
            mask = np.array([g == sg for g in slot_groups])
            total = raw_weights[mask].sum()
            slot_totals[mask] = total

        # Apply scaling where overcap
        overcap = slot_totals > slot_caps
        scale_factor = np.where(overcap, slot_caps / slot_totals, 1.0)
        scaled_weights = raw_weights * scale_factor

        # CB slot was overcap (3.0 > 2.5), so each CB weight should be scaled
        cb_scaled_total = scaled_weights[:5].sum()
        assert cb_scaled_total <= POSITION_SLOT_CAPS["CB"] + 1e-10, (
            f"CB slot total after scaling ({cb_scaled_total:.4f}) "
            f"should be <= cap ({POSITION_SLOT_CAPS['CB']})"
        )
        # ST slot was not overcap (1.0 < 2.5), so weights unchanged
        np.testing.assert_array_equal(scaled_weights[5:], st_weights)

        # CB weights should be reduced
        assert scaled_weights[:5].mean() < cb_weights.mean()

    def test_weights_sum_to_one_within_team_season(self):
        """Weights still sum to 1 within each team-season after slot cap adjustment."""
        df = pd.DataFrame(
            {
                "team": ["TeamA"] * 10 + ["TeamB"] * 8,
                "league": ["Premier League"] * 18,
                "season": ["2425"] * 18,
                "sub_position": (
                    ["CB"] * 4 + ["ST"] * 2 + ["CM"] * 2 + ["GK"] * 1 + ["FB"] * 1
                    + ["CB"] * 3 + ["CM"] * 2 + ["ST"] * 2 + ["GK"] * 1
                ),
                "minutes": [2000] * 18,
            },
        )
        weights = _build_team_aggregation_weights(df)

        # Check sum within each team-season
        for team in ["TeamA", "TeamB"]:
            mask = df["team"] == team
            team_weights = weights[mask.values]
            assert abs(team_weights.sum() - 1.0) < 1e-5, (
                f"Weights for {team} sum to {team_weights.sum():.6f}, expected 1.0"
            )
