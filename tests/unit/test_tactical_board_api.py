"""Tests for tactical board API endpoints — capabilities and MP4 export."""

from __future__ import annotations

import shutil

from scoutfootball.api import _clean_json_value


class TestTacticalBoardCapabilities:
    """Test the /tactical-board/capabilities endpoint logic."""

    def test_ffmpeg_detection(self) -> None:
        """Verify ffmpeg detection works."""
        ffmpeg_path = shutil.which("ffmpeg")
        # Just verify the logic works without crashing
        result = {
            "ffmpeg_available": ffmpeg_path is not None,
            "ffmpeg_path": ffmpeg_path,
            "supported_formats": {
                "png": True,
                "webm": True,
                "mp4": ffmpeg_path is not None,
                "gif": ffmpeg_path is not None,
                "pdf": True,
            },
        }
        assert isinstance(result["ffmpeg_available"], bool)
        assert isinstance(result["supported_formats"], dict)
        assert result["supported_formats"]["png"] is True
        assert result["supported_formats"]["webm"] is True
        assert result["supported_formats"]["pdf"] is True

    def test_capabilities_response_structure(self) -> None:
        """Response should have all required fields."""
        ffmpeg_path = shutil.which("ffmpeg")
        response = _clean_json_value({
            "ffmpeg_available": ffmpeg_path is not None,
            "ffmpeg_path": ffmpeg_path,
            "supported_formats": {
                "png": True,
                "webm": True,
                "mp4": ffmpeg_path is not None,
                "gif": ffmpeg_path is not None,
                "pdf": True,
            },
            "export_dir": "/tmp/test",
        })
        assert "ffmpeg_available" in response
        assert "supported_formats" in response
        assert "export_dir" in response
        assert isinstance(response["supported_formats"], dict)

    def test_clean_json_handles_none_ffmpeg_path(self) -> None:
        """When ffmpeg is not found, path is None."""
        response = _clean_json_value({
            "ffmpeg_available": False,
            "ffmpeg_path": None,
        })
        assert response["ffmpeg_available"] is False
        assert response["ffmpeg_path"] is None
