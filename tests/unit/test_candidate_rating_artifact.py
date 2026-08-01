"""Candidate rating artifacts must preserve the active score contract without activation."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest
import torch

SCRIPTS_ROOT = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _score(frame: pd.DataFrame) -> pd.DataFrame:
    from optimizer.optimization import _get_default_params_tensor
    from optimizer.scoring import score_player_ratings_frame

    device = torch.device("cpu")
    return score_player_ratings_frame(frame, _get_default_params_tensor(device), device)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "player": ["A", "B", "C", "D"],
            "team": ["Team A", "Team B", "Team C", "Team D"],
            "league": ["Premier League"] * 4,
            "season": ["2526"] * 4,
            "sub_position": ["ST"] * 4,
            "pos_idx": [0] * 4,
            "npg_p90": [0.1, 0.2, 0.3, 0.4],
            "assists_p90": [0.05, 0.10, 0.15, 0.20],
            "g_a_volume": [3.0, 6.0, 9.0, 12.0],
            "defense_composite": [30.0, 40.0, 50.0, 60.0],
            "possession_composite": [30.0, 40.0, 50.0, 60.0],
            "minutes": [900.0, 1300.0, 1800.0, 2500.0],
            "starts": [10.0, 15.0, 20.0, 28.0],
            "matches": [12.0, 18.0, 25.0, 32.0],
            "experience_factor": [0.6, 0.7, 0.8, 1.0],
        }
    )


def test_candidate_scores_keep_active_position_percentile_contract() -> None:
    result = _score(_frame())

    assert {"optimized_score", "same_position_score"}.issubset(result.columns)
    expected = result.groupby(["sub_position", "season"])["optimized_score"].rank(pct=True) * 100
    pd.testing.assert_series_equal(
        result["same_position_score"], expected, check_names=False, check_dtype=False
    )
    assert result["optimized_score"].notna().all()


def test_candidate_scores_reject_missing_position_contract_column() -> None:
    from optimizer.optimization import _get_default_params_tensor
    from optimizer.scoring import score_player_ratings_frame

    device = torch.device("cpu")
    with pytest.raises(ValueError, match="sub_position"):
        score_player_ratings_frame(
            _frame().drop(columns=["sub_position"]),
            _get_default_params_tensor(device),
            device,
        )
