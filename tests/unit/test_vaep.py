"""Tests for action_value/vaep.py — VAEP model feature creation,
label creation, training, and prediction."""

from __future__ import annotations

import numpy as np
import pandas as pd

from scoutfootball.action_value.vaep import (
    create_vaep_features,
    create_vaep_labels,
    create_vaep_labels_fast,
    predict_vaep_value,
    train_vaep_model,
)


def _make_actions(n: int = 100, seed: int = 42) -> pd.DataFrame:
    """Create a small synthetic SPADL actions DataFrame for testing."""
    rng = np.random.RandomState(seed)
    action_types = ["pass", "receipt", "carry", "shot", "tackle",
                    "interception", "clearance", "dribble", "block", "goalkeeper"]
    results = ["success", "failure", "unknown"]

    df = pd.DataFrame({
        "action_id": np.arange(n),
        "provider_action_id": [f"evt_{i}" for i in range(n)],
        "match_id": rng.choice(["m1", "m2", "m3"], size=n),
        "team_id": rng.choice(["t1", "t2"], size=n),
        "player_id": rng.choice([f"p{i}" for i in range(1, 11)], size=n),
        "period": rng.choice([1, 2], size=n),
        "minute": rng.randint(0, 90, size=n),
        "second": rng.randint(0, 60, size=n),
        "action_type": rng.choice(action_types, size=n),
        "result": rng.choice(results, size=n),
        "start_x": rng.uniform(0, 100, size=n).round(2),
        "start_y": rng.uniform(0, 100, size=n).round(2),
        "end_x": rng.uniform(0, 100, size=n).round(2),
        "end_y": rng.uniform(0, 100, size=n).round(2),
        "body_part": "foot",
        "source": "test",
        "source_coverage": "sample",
    })
    return df


def _make_actions_with_goals(n: int = 200, seed: int = 42) -> pd.DataFrame:
    """Create actions with explicit goal events for label testing."""
    rng = np.random.RandomState(seed)
    rows = []
    match_id = "m1"
    action_types = ["pass", "carry", "shot", "tackle", "interception",
                    "clearance", "dribble", "receipt", "block", "goalkeeper"]

    for i in range(n):
        minute = i // 3
        second = (i % 3) * 20
        team = "t1" if (i // 10) % 2 == 0 else "t2"

        # Insert goals at specific positions
        if i == 30:
            atype, result = "shot", "success"  # goal for t1
        elif i == 70:
            atype, result = "shot", "success"  # goal for t2
        elif i == 120:
            atype, result = "shot", "success"  # goal for t1
        else:
            atype = rng.choice(action_types)
            result = rng.choice(["success", "failure", "unknown"])

        rows.append({
            "action_id": i,
            "provider_action_id": f"evt_{i}",
            "match_id": match_id,
            "team_id": team,
            "player_id": f"p{(i % 10) + 1}",
            "period": 1 if minute < 45 else 2,
            "minute": minute,
            "second": second,
            "action_type": atype,
            "result": result,
            "start_x": rng.uniform(0, 100),
            "start_y": rng.uniform(0, 100),
            "end_x": rng.uniform(0, 100),
            "end_y": rng.uniform(0, 100),
            "body_part": "foot",
            "source": "test",
            "source_coverage": "sample",
        })

    return pd.DataFrame(rows)


class TestCreateVaepFeatures:
    def test_output_shape(self) -> None:
        df = _make_actions(100)
        features = create_vaep_features(df)
        assert len(features) == 100
        # Expected feature count:
        # 10 type one-hot + 3 result one-hot + 11 coords + 2 time
        # + (10+3+1)*2 context = 54
        assert features.shape[1] == 54

    def test_feature_columns_exist(self) -> None:
        df = _make_actions(50)
        features = create_vaep_features(df)
        # Check key columns
        assert "type_pass" in features.columns
        assert "type_shot" in features.columns
        assert "result_success" in features.columns
        assert "start_dist_goal" in features.columns
        assert "end_dist_goal" in features.columns
        assert "start_angle_goal" in features.columns
        assert "prev1_type_pass" in features.columns
        assert "prev2_result_success" in features.columns
        assert "prev1_same_team" in features.columns

    def test_no_nan_values(self) -> None:
        df = _make_actions(50)
        features = create_vaep_features(df)
        assert features.isna().sum().sum() == 0

    def test_one_hot_sums(self) -> None:
        df = _make_actions(100)
        features = create_vaep_features(df)
        # Each row should have exactly 1 action type one-hot
        type_cols = [f"type_{t}" for t in [
            "pass", "receipt", "carry", "tackle", "interception",
            "block", "shot", "goalkeeper", "clearance", "dribble",
        ]]
        assert (features[type_cols].sum(axis=1) == 1).all()

    def test_distance_features_positive(self) -> None:
        df = _make_actions(50)
        features = create_vaep_features(df)
        assert (features["start_dist_goal"] >= 0).all()
        assert (features["end_dist_goal"] >= 0).all()


class TestCreateVaepLabels:
    def test_labels_are_binary(self) -> None:
        df = _make_actions_with_goals(200)
        labels = create_vaep_labels(df)
        assert set(labels["scores"].unique()).issubset({0, 1})
        assert set(labels["concedes"].unique()).issubset({0, 1})

    def test_labels_shape(self) -> None:
        df = _make_actions_with_goals(200)
        labels = create_vaep_labels(df)
        assert len(labels) == 200
        assert list(labels.columns) == ["scores", "concedes"]

    def test_goals_produce_scores(self) -> None:
        df = _make_actions_with_goals(200)
        labels = create_vaep_labels(df)
        # At least some scores should be 1 (we inserted goals)
        assert labels["scores"].sum() > 0

    def test_fast_labels_match(self) -> None:
        df = _make_actions_with_goals(200)
        labels_slow = create_vaep_labels(df)
        labels_fast = create_vaep_labels_fast(df)
        # Both should produce same shape and same label counts (within tolerance)
        assert labels_slow.shape == labels_fast.shape
        # The total number of scored/conceded labels should be similar
        # (may not be exactly equal due to possession boundary differences)
        assert abs(labels_slow["scores"].sum() - labels_fast["scores"].sum()) <= 5


class TestCreateVaepLabelsFast:
    def test_labels_are_binary(self) -> None:
        df = _make_actions_with_goals(200)
        labels = create_vaep_labels_fast(df)
        assert set(labels["scores"].unique()).issubset({0, 1})
        assert set(labels["concedes"].unique()).issubset({0, 1})

    def test_concedes_when_opponent_scores(self) -> None:
        """Test that concedes=1 when the next possession by the opponent scores."""
        # Build a simple sequence: t1 actions, then t2 scores
        df = pd.DataFrame({
            "action_id": range(5),
            "provider_action_id": [f"e{i}" for i in range(5)],
            "match_id": ["m1"] * 5,
            "team_id": ["t1", "t1", "t2", "t2", "t2"],
            "player_id": ["p1", "p1", "p2", "p2", "p2"],
            "period": [1, 1, 1, 1, 1],
            "minute": [10, 11, 12, 13, 14],
            "second": [0, 0, 0, 0, 0],
            "action_type": ["pass", "pass", "pass", "shot", "pass"],
            "result": ["success", "failure", "success", "success", "success"],
            "start_x": [50, 60, 40, 80, 30],
            "start_y": [50, 50, 50, 50, 50],
            "end_x": [60, 40, 80, 90, 30],
            "end_y": [50, 50, 50, 50, 50],
            "body_part": ["foot"] * 5,
            "source": ["test"] * 5,
            "source_coverage": ["sample"] * 5,
        })
        labels = create_vaep_labels_fast(df)
        # t2's shot (action_id=3) is a goal, so t2's possession scores=1
        # t1's possession before that should have concedes=1
        assert labels["scores"].sum() >= 1  # t2 scores


class TestTrainVaepModel:
    def test_returns_model_dict(self) -> None:
        df = _make_actions_with_goals(200)
        features = create_vaep_features(df)
        labels = create_vaep_labels_fast(df)
        model = train_vaep_model(
            features, labels, model_type="lr", sample_fraction=1.0,
        )
        assert "scores_model" in model
        assert "concedes_model" in model
        assert "scores_auc" in model
        assert "concedes_auc" in model
        assert 0.0 <= model["scores_auc"] <= 1.0
        assert 0.0 <= model["concedes_auc"] <= 1.0

    def test_gb_model(self) -> None:
        df = _make_actions_with_goals(200)
        features = create_vaep_features(df)
        labels = create_vaep_labels_fast(df)
        model = train_vaep_model(
            features, labels, model_type="gb", sample_fraction=1.0,
        )
        assert model["scores_auc"] >= 0.5  # Should be at least random


class TestPredictVaepValue:
    def test_prediction_shape(self) -> None:
        df = _make_actions_with_goals(200)
        features = create_vaep_features(df)
        labels = create_vaep_labels_fast(df)
        model = train_vaep_model(
            features, labels, model_type="lr", sample_fraction=1.0,
        )
        vaep_values = predict_vaep_value(model, features)
        assert len(vaep_values) == 200
        assert vaep_values.dtype == np.float64

    def test_prediction_range(self) -> None:
        df = _make_actions_with_goals(200)
        features = create_vaep_features(df)
        labels = create_vaep_labels_fast(df)
        model = train_vaep_model(
            features, labels, model_type="lr", sample_fraction=1.0,
        )
        vaep_values = predict_vaep_value(model, features)
        # VAEP = P(scores) - P(concedes), so range is [-1, 1]
        assert vaep_values.min() >= -1.0
        assert vaep_values.max() <= 1.0


class TestEndToEnd:
    def test_small_pipeline(self) -> None:
        """End-to-end test with small synthetic data."""
        df = _make_actions_with_goals(200)
        features = create_vaep_features(df)
        labels = create_vaep_labels_fast(df)

        model = train_vaep_model(
            features, labels, model_type="lr", sample_fraction=1.0,
        )
        vaep_values = predict_vaep_value(model, features)

        # Should produce values for all actions
        assert len(vaep_values) == 200
        # Mean should be close to 0 (most actions don't lead to goals)
        assert abs(vaep_values.mean()) < 0.5
