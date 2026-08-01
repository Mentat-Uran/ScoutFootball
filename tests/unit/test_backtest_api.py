"""Tests for the backtest comparison API endpoint."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from scoutfootball.api import _match_model_comparison, get_backtest_comparison


class TestMatchModelComparison:
    """Verify _match_model_comparison returns None when artifacts missing."""

    @patch("scoutfootball.api.load_score_prediction")
    @patch("scoutfootball.api.load_score_prediction_dc")
    def test_returns_none_when_both_fail(self, mock_dc: MagicMock, mock_poisson: MagicMock) -> None:
        mock_poisson.side_effect = FileNotFoundError("no artifact")
        mock_dc.side_effect = FileNotFoundError("no artifact")
        result = _match_model_comparison("TeamA", "TeamB")
        assert result is None

    @patch("scoutfootball.api.load_score_prediction")
    @patch("scoutfootball.api.load_score_prediction_dc")
    def test_returns_none_when_only_one_available(
        self, mock_dc: MagicMock, mock_poisson: MagicMock,
    ) -> None:
        mock_poisson.side_effect = FileNotFoundError("no artifact")
        # DC returns a dict (fallback case)
        mock_dc.return_value = {"home_win": 0.5}
        result = _match_model_comparison("TeamA", "TeamB")
        assert result is None


class TestGetBacktestComparison:
    """Verify get_backtest_comparison handles available and missing artifacts."""

    @patch("scoutfootball.api._settings")
    def test_returns_not_available_when_no_artifacts(
        self, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        mock_settings.return_value.report_root = tmp_path
        result = get_backtest_comparison(force_refresh=True)
        assert result["status"] == "not_available"
        assert "instructions" in result
        assert result["models"] == []
        assert result["metric_comparison"] == []

    @patch("scoutfootball.api._settings")
    def test_returns_ok_when_metrics_exist(self, mock_settings: MagicMock, tmp_path: Path) -> None:
        bt_dir = tmp_path / "calibration_backtest"
        bt_dir.mkdir(parents=True)
        poisson_metrics = {
            "model": "independent_poisson",
            "n_splits": 3,
            "total_predictions": 900,
            "overall": {"log_loss_exact": 2.85, "brier_1x2": 0.62, "rps_1x2": 0.21},
            "folds": [
                {"fold": 1, "train_start": "2022-01-01", "train_end": "2023-01-01",
                 "test_start": "2023-01-01", "test_end": "2023-06-01",
                 "train_matches": 200, "test_matches": 300,
                 "log_loss_exact": 2.80, "brier_1x2": 0.60, "rps_1x2": 0.20},
            ],
        }
        dc_metrics = {
            "model": "dixon_coles", "decay": None, "n_splits": 3,
            "total_predictions": 900,
            "overall": {"log_loss_exact": 2.78, "brier_1x2": 0.60, "rps_1x2": 0.20},
            "folds": [
                {"fold": 1, "train_start": "2022-01-01", "train_end": "2023-01-01",
                 "test_start": "2023-01-01", "test_end": "2023-06-01",
                 "train_matches": 200, "test_matches": 300,
                 "log_loss_exact": 2.75, "brier_1x2": 0.58, "rps_1x2": 0.19},
            ],
        }
        (bt_dir / "poisson_backtest_metrics.json").write_text(json.dumps(poisson_metrics))
        (bt_dir / "dixon_coles_backtest_metrics.json").write_text(json.dumps(dc_metrics))

        mock_settings.return_value.report_root = tmp_path
        result = get_backtest_comparison(force_refresh=True)
        assert result["status"] == "ok"
        assert len(result["models"]) == 2
        model_keys = [m["model"] for m in result["models"]]
        assert "independent_poisson" in model_keys
        assert "dixon_coles" in model_keys

    @patch("scoutfootball.api._settings")
    def test_metric_comparison_picks_winner(self, mock_settings: MagicMock, tmp_path: Path) -> None:
        bt_dir = tmp_path / "calibration_backtest"
        bt_dir.mkdir(parents=True)
        poisson_metrics = {
            "model": "independent_poisson", "n_splits": 3, "total_predictions": 900,
            "overall": {"log_loss_exact": 2.85, "brier_1x2": 0.62, "rps_1x2": 0.21},
            "folds": [],
        }
        dc_metrics = {
            "model": "dixon_coles", "decay": None, "n_splits": 3, "total_predictions": 900,
            "overall": {"log_loss_exact": 2.78, "brier_1x2": 0.60, "rps_1x2": 0.20},
            "folds": [],
        }
        (bt_dir / "poisson_backtest_metrics.json").write_text(json.dumps(poisson_metrics))
        (bt_dir / "dixon_coles_backtest_metrics.json").write_text(json.dumps(dc_metrics))

        mock_settings.return_value.report_root = tmp_path
        result = get_backtest_comparison(force_refresh=True)
        mc = result["metric_comparison"]
        assert len(mc) == 3
        # Lower is better — DC should win all three metrics
        for row in mc:
            assert row["winner"] == "dixon_coles"

    @patch("scoutfootball.api._settings")
    def test_calibration_report_included(self, mock_settings: MagicMock, tmp_path: Path) -> None:
        bt_dir = tmp_path / "calibration_backtest"
        bt_dir.mkdir(parents=True)
        cal_report = {
            "method": "isotonic", "decay": 0.005,
            "brier_before": 0.62, "brier_after": 0.58,
            "rps_before": 0.21, "rps_after": 0.19,
            "n_matches": 900,
        }
        (bt_dir / "dc_calibration_report.json").write_text(json.dumps(cal_report))

        mock_settings.return_value.report_root = tmp_path
        result = get_backtest_comparison(force_refresh=True)
        assert result["status"] == "not_available"  # no model metrics
        assert result["calibration"]["status"] == "ok"
        assert result["calibration"]["brier_before"] == 0.62
        assert result["calibration"]["brier_after"] == 0.58

    @patch("scoutfootball.api._settings")
    def test_caches_result(self, mock_settings: MagicMock, tmp_path: Path) -> None:
        mock_settings.return_value.report_root = tmp_path
        r1 = get_backtest_comparison(force_refresh=True)
        r2 = get_backtest_comparison()  # should use cache
        assert r1 == r2
