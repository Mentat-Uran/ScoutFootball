from __future__ import annotations

from pathlib import Path

import pandas as pd

from scoutfootball.evaluation.truth_labels import create_empty_truth_labels
from scoutfootball.models.player_rating_nn import (
    PlayerRatingNNConfig,
    build_player_rating_nn_dataset,
    train_player_rating_nn,
    write_player_rating_nn_artifacts,
)


def _sample_feature_matrix() -> pd.DataFrame:
    rows = []
    seasons = ["2122", "2223", "2324", "2425"]
    for season_i, season in enumerate(seasons):
        for player_i in range(8):
            position = ["ST", "W", "CM", "CB"][player_i % 4]
            goals = season_i + player_i % 3
            assists = (player_i + season_i) % 4
            minutes = 800 + season_i * 100 + player_i * 45
            rows.append(
                {
                    "player_id": f"p{player_i}",
                    "season_id": season,
                    "player_name": f"Player {player_i}",
                    "team_id": f"t{player_i % 3}",
                    "team_name": f"Team {player_i % 3}",
                    "competition_id": "Premier League" if player_i % 2 else "La Liga",
                    "position_group": position,
                    "goals": goals,
                    "assists": assists,
                    "shots": goals * 4 + 2,
                    "shots_on_target": goals * 2,
                    "minutes_played": minutes,
                    "starts": minutes / 90,
                    "available_flag": 1.0,
                    "tackles": player_i % 5,
                    "passes": 20 + player_i * 3,
                    "finishing_shrunk": goals / 50,
                    "fbref_source_covered": True,
                    "statsbomb_open_source_covered": player_i % 2 == 0,
                },
            )
    return pd.DataFrame(rows)


def _sample_truth_labels(feature_matrix: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in feature_matrix.iterrows():
        label = (
            45.0
            + float(row["goals"]) * 5.0
            + float(row["assists"]) * 3.0
            + float(row["minutes_played"]) / 220.0
        )
        rows.append(
            {
                "player_id": row["player_id"],
                "season": row["season_id"],
                "label_source": "manual_calibration",
                "label_confidence": "high",
                "label_value": label,
                "as_of_date": "2026-06-10",
                "position_scope": row["position_group"],
                "manual_review_flag": False,
            },
        )
    return pd.DataFrame(rows)


def _sample_baseline(feature_matrix: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "player": feature_matrix["player_name"],
            "season": feature_matrix["season_id"],
            "optimized_score": 50.0 + feature_matrix["goals"].astype(float) * 4.0,
            "same_position_score": 55.0 + feature_matrix["assists"].astype(float) * 3.0,
        },
    )


def test_build_dataset_attaches_optimizer_baseline() -> None:
    features = _sample_feature_matrix()
    labels = _sample_truth_labels(features)
    baseline = _sample_baseline(features)

    dataset = build_player_rating_nn_dataset(features, labels, baseline_ratings=baseline)

    assert len(dataset) == len(features)
    assert dataset["baseline_optimized_score"].notna().all()
    assert "label_value" in dataset.columns


def test_train_player_rating_nn_skips_empty_labels() -> None:
    features = _sample_feature_matrix()

    result = train_player_rating_nn(
        features,
        create_empty_truth_labels(),
        config=PlayerRatingNNConfig(min_labels=10, max_iter=20),
    )

    assert result.trained is False
    assert result.status.startswith("skipped:")


def test_train_player_rating_nn_with_synthetic_labels_writes_artifacts(tmp_path: Path) -> None:
    features = _sample_feature_matrix()
    labels = _sample_truth_labels(features)
    baseline = _sample_baseline(features)

    result = train_player_rating_nn(
        features,
        labels,
        baseline_ratings=baseline,
        config=PlayerRatingNNConfig(min_labels=20, max_iter=80, early_stopping=False),
    )
    write_player_rating_nn_artifacts(
        result,
        tmp_path,
        config=PlayerRatingNNConfig(min_labels=20, max_iter=80, early_stopping=False),
    )

    assert result.trained is True
    assert result.metrics["test"]["n"] > 0
    assert "optimizer_baseline_test" in result.metrics
    assert set(result.predictions["split"]) == {"train", "test"}
    assert (tmp_path / "metrics.json").exists()
    assert (tmp_path / "predictions.parquet").exists()
    assert (tmp_path / "model.pkl").exists()
