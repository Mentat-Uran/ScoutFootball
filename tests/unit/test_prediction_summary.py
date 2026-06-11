"""Tests for API prediction summary — top-level field aliases."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from scoutfootball.api import get_prediction_summary


class TestGetPredictionSummary:
    """Verify get_prediction_summary returns top-level aliases."""

    @patch("scoutfootball.api._settings")
    def test_returns_top_level_status(self, mock_settings: MagicMock) -> None:
        """Response should have a top-level 'status' field."""
        mock_settings.return_value.data_root = MagicMock()
        # When no artifacts exist, status should be 'no_data'
        with patch("scoutfootball.api.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            result = get_prediction_summary()
        assert "status" in result
        assert "poisson" in result
        assert "dixon_coles" in result
        assert "available_models" in result

    @patch("scoutfootball.api._settings")
    def test_no_data_returns_no_data_status(self, mock_settings: MagicMock) -> None:
        """When no artifacts exist, status should be 'no_data'."""
        mock_root = MagicMock()
        mock_root.__truediv__ = lambda self, other: MagicMock(exists=lambda: False)
        mock_settings.return_value.data_root = mock_root
        result = get_prediction_summary()
        assert result["status"] == "no_data"

    @patch("scoutfootball.api._settings")
    def test_has_model_type_field(self, mock_settings: MagicMock) -> None:
        """Response should have a top-level 'model_type' field."""
        mock_root = MagicMock()
        mock_root.__truediv__ = lambda self, other: MagicMock(exists=lambda: False)
        mock_settings.return_value.data_root = mock_root
        result = get_prediction_summary()
        assert "model_type" in result

    @patch("scoutfootball.api._settings")
    def test_has_available_models(self, mock_settings: MagicMock) -> None:
        """Response should list available models."""
        mock_root = MagicMock()
        mock_root.__truediv__ = lambda self, other: MagicMock(exists=lambda: False)
        mock_settings.return_value.data_root = mock_root
        result = get_prediction_summary()
        assert isinstance(result["available_models"], list)
        assert "poisson" in result["available_models"]
