"""Tests for Dixon-Coles decay parameter tuning and prediction calibration."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from scoutfootball.evaluation.backtests import (
    DEFAULT_DECAY_CANDIDATES,
    DecayTuningResult,
    tune_dixon_coles_decay,
)
from scoutfootball.models import TimeSplitConfig


def _make_team_match_df(n_teams: int = 6, n_seasons: int = 3) -> pd.DataFrame:
    """Create synthetic team-match data spanning multiple seasons for backtesting."""
    rng = np.random.default_rng(42)
    teams = [f"team_{i}" for i in range(n_teams)]
    rows: list[dict] = []
    match_id = 0
    for season in range(n_seasons):
        season_year = 2022 + season
        for round_num in range(4):
            for i in range(0, n_teams, 2):
                home, away = teams[i], teams[i + 1]
                hg = rng.poisson(1.5)
                ag = rng.poisson(1.1)
                match_date = f"{season_year}-{1 + round_num:02d}-{15 + i:02d}"
                rows.append({
                    "match_id": str(match_id),
                    "match_date": match_date,
                    "team_id": home,
                    "is_home": True,
                    "goals_for": hg,
                    "goals_against": ag,
                })
                rows.append({
                    "match_id": str(match_id),
                    "match_date": match_date,
                    "team_id": away,
                    "is_home": False,
                    "goals_for": ag,
                    "goals_against": hg,
                })
                match_id += 1
    return pd.DataFrame(rows)


class TestTuneDixonColesDecay:
    """Tests for the tune_dixon_coles_decay grid search function."""

    def test_basic_tuning_returns_result(self) -> None:
        """Tuning should return a DecayTuningResult with expected fields."""
        df = _make_team_match_df()
        result = tune_dixon_coles_decay(df, decay_candidates=[0.0, 0.005])
        assert isinstance(result, DecayTuningResult)
        assert result.best_decay in (0.0, 0.005)
        assert result.selection_metric == "rps_1x2"
        assert result.n_folds == 3  # default TimeSplitConfig
        assert result.n_matches > 0

    def test_comparison_table_has_all_candidates(self) -> None:
        """Comparison table should have one row per candidate."""
        df = _make_team_match_df()
        candidates = [0.0, 0.005, 0.01]
        result = tune_dixon_coles_decay(df, decay_candidates=candidates)
        assert len(result.comparison_table) == 3
        assert set(result.comparison_table["decay"]) == set(candidates)

    def test_comparison_table_columns(self) -> None:
        """Comparison table should have decay, half_life_days, and metric columns."""
        df = _make_team_match_df()
        result = tune_dixon_coles_decay(df, decay_candidates=[0.0, 0.005])
        cols = set(result.comparison_table.columns)
        assert "decay" in cols
        assert "half_life_days" in cols
        assert "log_loss_exact" in cols
        assert "brier_1x2" in cols
        assert "rps_1x2" in cols

    def test_half_life_inf_for_zero_decay(self) -> None:
        """Zero decay should have infinite half-life."""
        df = _make_team_match_df()
        result = tune_dixon_coles_decay(df, decay_candidates=[0.0, 0.005])
        row = result.comparison_table[result.comparison_table["decay"] == 0.0].iloc[0]
        assert row["half_life_days"] == float("inf")

    def test_half_life_finite_for_nonzero_decay(self) -> None:
        """Non-zero decay should have finite half-life = ln(2)/decay."""
        df = _make_team_match_df()
        result = tune_dixon_coles_decay(df, decay_candidates=[0.005])
        row = result.comparison_table[result.comparison_table["decay"] == 0.005].iloc[0]
        expected_hl = np.log(2) / 0.005
        assert abs(row["half_life_days"] - round(expected_hl, 1)) < 0.1

    def test_best_decay_minimises_selection_metric(self) -> None:
        """Best decay should be the one with lowest selection metric value."""
        df = _make_team_match_df()
        result = tune_dixon_coles_decay(
            df, decay_candidates=[0.0, 0.005, 0.01], selection_metric="brier_1x2",
        )
        # The best decay should have the minimum brier_1x2 among candidates
        metrics = result.candidate_metrics
        min_brier = min(metrics[d]["brier_1x2"] for d in [0.0, 0.005, 0.01])
        assert metrics[result.best_decay]["brier_1x2"] == min_brier
        assert result.selection_metric == "brier_1x2"

    def test_selection_metric_log_loss(self) -> None:
        """Should be able to select by log_loss_exact."""
        df = _make_team_match_df()
        result = tune_dixon_coles_decay(
            df, decay_candidates=[0.0, 0.005], selection_metric="log_loss_exact",
        )
        assert result.selection_metric == "log_loss_exact"
        metrics = result.candidate_metrics
        min_ll = min(metrics[d]["log_loss_exact"] for d in [0.0, 0.005])
        assert metrics[result.best_decay]["log_loss_exact"] == min_ll

    def test_invalid_selection_metric_raises(self) -> None:
        """Invalid selection metric should raise ValueError."""
        df = _make_team_match_df()
        with pytest.raises(ValueError, match="selection_metric"):
            tune_dixon_coles_decay(df, decay_candidates=[0.0], selection_metric="invalid")

    def test_empty_candidates_raises(self) -> None:
        """Empty candidates list should raise ValueError."""
        df = _make_team_match_df()
        with pytest.raises(ValueError, match="decay_candidates"):
            tune_dixon_coles_decay(df, decay_candidates=[])

    def test_candidate_metrics_has_all_candidates(self) -> None:
        """candidate_metrics dict should have an entry for each candidate."""
        df = _make_team_match_df()
        candidates = [0.0, 0.005, 0.01, 0.02]
        result = tune_dixon_coles_decay(df, decay_candidates=candidates)
        assert set(result.candidate_metrics.keys()) == set(candidates)
        for d in candidates:
            m = result.candidate_metrics[d]
            assert "log_loss_exact" in m
            assert "brier_1x2" in m
            assert "rps_1x2" in m

    def test_default_candidates_used_when_none(self) -> None:
        """When decay_candidates is None, should use DEFAULT_DECAY_CANDIDATES."""
        df = _make_team_match_df()
        result = tune_dixon_coles_decay(df)
        assert len(result.comparison_table) == len(DEFAULT_DECAY_CANDIDATES)

    def test_custom_split_config(self) -> None:
        """Should accept a custom TimeSplitConfig."""
        df = _make_team_match_df()
        cfg = TimeSplitConfig(n_splits=2, gap=0)
        result = tune_dixon_coles_decay(
            df, decay_candidates=[0.0, 0.005], split_cfg=cfg,
        )
        assert result.n_folds == 2


class TestGetDecayTuningAPI:
    """Tests for the get_decay_tuning API function."""

    def test_not_available_when_no_file(self, monkeypatch, tmp_path) -> None:
        """Should return not_available status when tuning file doesn't exist."""
        from scoutfootball.api import get_decay_tuning

        class MockSettings:
            report_root = tmp_path

        monkeypatch.setattr("scoutfootball.api._settings", lambda: MockSettings())
        # Clear cache
        import scoutfootball.api as api_mod
        api_mod._BACKTEST_CACHE["tuning_data"] = None

        result = get_decay_tuning(force_refresh=True)
        assert result["status"] == "not_available"
        assert "instructions" in result

    def test_ok_when_file_exists(self, monkeypatch, tmp_path) -> None:
        """Should return ok status with tuning data when file exists."""
        from scoutfootball.api import get_decay_tuning

        bt_dir = tmp_path / "calibration_backtest"
        bt_dir.mkdir()
        tuning_data = {
            "best_decay": 0.005,
            "selection_metric": "rps_1x2",
            "n_folds": 3,
            "n_matches": 1000,
            "candidates": [
                {
                    "decay": 0.0,
                    "half_life_days": float("inf"),
                    "log_loss_exact": 2.5,
                    "brier_1x2": 0.65,
                    "rps_1x2": 0.22,
                },
                {
                    "decay": 0.005,
                    "half_life_days": 138.6,
                    "log_loss_exact": 2.4,
                    "brier_1x2": 0.63,
                    "rps_1x2": 0.21,
                },
            ],
        }
        with open(bt_dir / "decay_tuning_results.json", "w") as f:
            json.dump(tuning_data, f)

        class MockSettings:
            report_root = tmp_path

        monkeypatch.setattr("scoutfootball.api._settings", lambda: MockSettings())
        import scoutfootball.api as api_mod
        api_mod._BACKTEST_CACHE["tuning_data"] = None

        result = get_decay_tuning(force_refresh=True)
        assert result["status"] == "ok"
        assert result["best_decay"] == 0.005
        assert result["selection_metric"] == "rps_1x2"
        assert len(result["candidates"]) == 2


class TestResolveDcDecay:
    """Tests for the pipeline._resolve_dc_decay helper."""

    def test_fallback_to_default_when_no_file(self, tmp_path) -> None:
        """Should return 0.005 when tuning file doesn't exist."""
        from scoutfootball.pipeline import _resolve_dc_decay

        result = _resolve_dc_decay(tmp_path)
        assert result == 0.005

    def test_reads_best_decay_from_file(self, tmp_path) -> None:
        """Should read best_decay from tuning results file."""
        from scoutfootball.pipeline import _resolve_dc_decay

        bt_dir = tmp_path / "data" / "reports" / "calibration_backtest"
        bt_dir.mkdir(parents=True)
        tuning_data = {"best_decay": 0.008, "selection_metric": "rps_1x2"}
        with open(bt_dir / "decay_tuning_results.json", "w") as f:
            json.dump(tuning_data, f)

        result = _resolve_dc_decay(tmp_path)
        assert result == 0.008

    def test_fallback_on_invalid_json(self, tmp_path) -> None:
        """Should fall back to 0.005 when JSON is invalid."""
        from scoutfootball.pipeline import _resolve_dc_decay

        bt_dir = tmp_path / "data" / "reports" / "calibration_backtest"
        bt_dir.mkdir(parents=True)
        with open(bt_dir / "decay_tuning_results.json", "w") as f:
            f.write("invalid json {{{")

        result = _resolve_dc_decay(tmp_path)
        assert result == 0.005

    def test_fallback_on_negative_decay(self, tmp_path) -> None:
        """Should fall back to 0.005 when best_decay is negative."""
        from scoutfootball.pipeline import _resolve_dc_decay

        bt_dir = tmp_path / "data" / "reports" / "calibration_backtest"
        bt_dir.mkdir(parents=True)
        tuning_data = {"best_decay": -0.01, "selection_metric": "rps_1x2"}
        with open(bt_dir / "decay_tuning_results.json", "w") as f:
            json.dump(tuning_data, f)

        result = _resolve_dc_decay(tmp_path)
        assert result == 0.005
