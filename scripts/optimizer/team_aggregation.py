"""Torch-free team aggregation helpers for rating evaluation.

This module intentionally contains only pandas/numpy logic so validation of
position caps and team weighting remains available when the optional PyTorch
optimizer runtime is absent or unavailable.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .constants import (
    POSITION_SLOT_CAPS,
    POSITION_SLOT_GROUPS,
    TEAM_AGG_CAPPED_MINUTES_BLEND,
    TEAM_AGG_CORE_MINUTES,
    TEAM_AGG_CORE_SCALE,
    TEAM_AGG_MINUTES_CAP,
)


def build_team_aggregation_weights(df_reset: pd.DataFrame) -> np.ndarray:
    """Build normalized, position-capped weights for each team-season."""
    if df_reset.empty:
        return np.array([], dtype=np.float32)

    minutes = pd.to_numeric(df_reset["minutes"], errors="coerce").fillna(0.0).clip(lower=0.0)
    capped = np.sqrt(np.minimum(minutes.to_numpy(dtype=np.float64), TEAM_AGG_MINUTES_CAP))
    z = np.clip(
        (minutes.to_numpy(dtype=np.float64) - TEAM_AGG_CORE_MINUTES) / TEAM_AGG_CORE_SCALE,
        -50.0,
        50.0,
    )
    core = 1.0 / (1.0 + np.exp(-z))

    work = df_reset.loc[:, ["team", "league", "season"]].copy()
    work["capped"] = capped
    work["core"] = core
    group = work.groupby(["team", "league", "season"], sort=False)
    group_size = group["capped"].transform("size").to_numpy(dtype=np.float64)
    fallback = np.divide(1.0, group_size, out=np.zeros_like(group_size), where=group_size > 0)
    capped_sum = group["capped"].transform("sum").to_numpy(dtype=np.float64)
    core_sum = group["core"].transform("sum").to_numpy(dtype=np.float64)
    capped_share = np.divide(capped, capped_sum, out=fallback, where=capped_sum > 0)
    core_share = np.divide(core, core_sum, out=fallback, where=core_sum > 0)
    weights = (
        TEAM_AGG_CAPPED_MINUTES_BLEND * capped_share
        + (1.0 - TEAM_AGG_CAPPED_MINUTES_BLEND) * core_share
    )

    if "sub_position" in df_reset.columns:
        slot_group = df_reset["sub_position"].map(POSITION_SLOT_GROUPS).fillna("MF")
        work["slot_group"] = slot_group.values
        work["team_season"] = work["team"] + "|" + work["league"] + "|" + work["season"]
        work["weight"] = weights
        slot_totals = work.groupby(["team_season", "slot_group"], sort=False)["weight"].transform(
            "sum"
        )
        slot_caps = slot_group.map(POSITION_SLOT_CAPS).fillna(2.5)
        overcap = slot_totals > slot_caps.values
        if overcap.any():
            weights = weights * np.where(overcap, slot_caps.values / slot_totals, 1.0)

    work["weight"] = weights
    weight_sum = work.groupby(["team", "league", "season"], sort=False)["weight"].transform(
        "sum"
    ).to_numpy(dtype=np.float64)
    return np.divide(weights, weight_sum, out=fallback, where=weight_sum > 0).astype(np.float32)
