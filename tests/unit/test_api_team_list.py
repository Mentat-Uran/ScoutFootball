"""Prediction-team API contract tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from scoutfootball.api import list_teams


def test_list_teams_prefers_prediction_artifact_ids(tmp_path) -> None:
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    pd.DataFrame({"team_id": ["Chelsea", "Arsenal", "Chelsea"]}).to_parquet(
        artifact_dir / "dc_team_strengths.parquet",
        index=False,
    )

    settings = SimpleNamespace(model_root=tmp_path)
    ratings = pd.DataFrame({"team": ["Arsenal,Chelsea", "Liverpool"]})
    with patch("scoutfootball.api._settings", return_value=settings):
        with patch("scoutfootball.api.load_player_ratings", return_value=ratings):
            assert list_teams() == ["Arsenal", "Chelsea"]


def test_list_teams_filters_joined_club_histories_in_fallback(tmp_path) -> None:
    settings = SimpleNamespace(model_root=tmp_path)
    ratings = pd.DataFrame(
        {"team": ["Arsenal,Chelsea", "Liverpool", " Arsenal ", None]},
    )
    with patch("scoutfootball.api._settings", return_value=settings):
        with patch("scoutfootball.api.load_player_ratings", return_value=ratings):
            assert list_teams() == ["Arsenal", "Liverpool"]
