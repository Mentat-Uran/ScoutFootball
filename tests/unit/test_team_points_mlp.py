"""Tests for the candidate-only team-points MLP."""

from __future__ import annotations

import numpy as np
import pandas as pd

from scoutfootball.models.team_points_mlp import (
    TeamPointsMLPConfig,
    train_team_points_mlp,
    write_team_points_mlp_artifacts,
)


def _synthetic_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(7)
    player_rows: list[dict[str, object]] = []
    points_rows: list[dict[str, object]] = []
    seasons = ["2021", "2122", "2223", "2324", "2425"]
    teams = ["Alpha", "Bravo", "Charlie", "Delta"]
    for season_index, season in enumerate(seasons):
        for team_index, team in enumerate(teams):
            team_signal = 45.0 + team_index * 8.0 + season_index
            points_rows.append(
                {
                    "team": team,
                    "league": "Example League",
                    "season": season,
                    "total_points": team_signal * 1.5,
                },
            )
            for player_index in range(6):
                goals = team_signal / 10.0 + player_index * 0.1
                player_rows.append(
                    {
                        "player": f"{team}-{season}-{player_index}",
                        "team": team,
                        "league": "Example League",
                        "season": season,
                        "minutes": 1600 + player_index * 30,
                        "goals": goals + rng.normal(0.0, 0.01),
                        "assists": goals * 0.3,
                        "sub_position": "ST" if player_index < 3 else "CM",
                        "optimized_score": 99.0,
                    },
                )
    return pd.DataFrame(player_rows), pd.DataFrame(points_rows)


def test_team_points_mlp_uses_chronological_proxy_holdout() -> None:
    features, targets = _synthetic_inputs()
    result = train_team_points_mlp(
        features,
        targets,
        config=TeamPointsMLPConfig(
            hidden_layer_sizes=(12, 6),
            epochs=25,
            patience=6,
            min_team_players=3,
        ),
    )

    assert result.trained is True
    assert result.metrics["test_seasons"] == ["2425"]
    assert result.metrics["validation_seasons"] == ["2324"]
    assert set(result.team_predictions["split"]) == {"train", "test"}
    assert set(result.metrics["fit_seasons"]).isdisjoint(result.metrics["test_seasons"])
    assert "optimized_score" not in result.feature_columns
    assert result.metrics["architecture"] == "set_transformer"
    assert result.metrics["target_semantics"].startswith("team-season points proxy")
    assert result.metrics["team_coverage"]["test"]["coverage_rate"] == 1.0
    assert result.metrics["team_coverage"]["test"]["scope"] == "leagues_with_player_features"


def test_team_points_mlp_rejects_missing_team_points_schema() -> None:
    features, targets = _synthetic_inputs()
    result = train_team_points_mlp(features, targets.drop(columns="total_points"))

    assert result.trained is False
    assert result.status.startswith("skipped: missing team-points")


def test_team_points_mlp_writer_emits_read_only_model_registry_metadata(tmp_path) -> None:
    features, targets = _synthetic_inputs()
    config = TeamPointsMLPConfig(
        hidden_layer_sizes=(8,),
        epochs=5,
        patience=2,
        min_team_players=3,
    )
    result = train_team_points_mlp(features, targets, config=config)
    output_dir = tmp_path / "data" / "models" / "runs" / "candidate-mlp"

    write_team_points_mlp_artifacts(result, output_dir, config=config, input_frame=features)

    metadata = (output_dir / "meta.json").read_text(encoding="utf-8")
    assert '"model_type": "team_points_set_transformer"' in metadata
    assert '"architecture": "set_transformer"' in metadata
    assert '"status": "not_activated"' in metadata
    assert (
        '"target_semantics": "team-season points proxy; '
        'not independent player-ability truth"'
    ) in metadata


def test_team_points_mlp_architecture_remains_available_as_comparison_baseline() -> None:
    features, targets = _synthetic_inputs()
    result = train_team_points_mlp(
        features,
        targets,
        config=TeamPointsMLPConfig(
            architecture="mlp",
            hidden_layer_sizes=(8,),
            epochs=5,
            patience=2,
            min_team_players=3,
        ),
    )

    assert result.trained is True
    assert result.metrics["architecture"] == "mlp"
