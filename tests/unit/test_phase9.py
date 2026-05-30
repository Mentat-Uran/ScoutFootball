"""Tests for Phase 9 viz and app modules."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scoutlab.app.demo_data import (
    generate_oof_predictions,
    generate_player_match,
    generate_score_matrix,
    generate_team_match,
)
from scoutlab.viz.percentiles import plot_percentile_bars
from scoutlab.viz.radar import plot_player_radar
from scoutlab.viz.scatter import plot_value_scatter
from scoutlab.viz.score_matrix import plot_score_matrix
from scoutlab.viz.trends import plot_trend


def _build_player_rolling(n_rows: int = 200) -> pd.DataFrame:
    raw = generate_player_match(n_rows)
    from scoutlab.features.player_match import build_player_match_features
    from scoutlab.features.player_rolling import build_player_rolling_features

    pm = build_player_match_features(raw)
    return build_player_rolling_features(pm, windows=[10])


@pytest.fixture()
def player_rolling_df():
    return _build_player_rolling(200)


@pytest.fixture()
def oof_df():
    return generate_oof_predictions(100)


def test_radar_returns_figure(player_rolling_df):
    row_a = player_rolling_df.iloc[0]
    row_b = player_rolling_df.iloc[1]
    fig = plot_player_radar(row_a, row_b, player_rolling_df)
    assert fig.layout.title.text == "Position-Relative Radar"
    assert len(fig.data) == 2


def test_radar_no_overlapping_metrics():
    row_a = pd.Series({"goals_p90_shrunk_10": 0.5, "player_name": "A"})
    row_b = pd.Series({"assists_p90_shrunk_10": 0.3, "player_name": "B"})
    pool = pd.DataFrame({"goals_p90_shrunk_10": [0.1, 0.2, 0.5]})
    fig = plot_player_radar(row_a, row_b, pool)
    assert "No overlapping" in fig.layout.title.text


def test_percentile_bars_returns_figure(player_rolling_df):
    row = player_rolling_df.iloc[0]
    fig = plot_percentile_bars(row, player_rolling_df)
    assert "Position Percentiles" in fig.layout.title.text
    assert len(fig.data) == 1


def test_trend_returns_figure(player_rolling_df):
    player_id = player_rolling_df["player_id"].iloc[0]
    player_df = player_rolling_df.loc[player_rolling_df["player_id"] == player_id]
    fig = plot_trend(player_df, "goals_p90_shrunk_10", entity_name="Test")
    assert "Trend" in fig.layout.title.text


def test_trend_missing_metric(player_rolling_df):
    fig = plot_trend(player_rolling_df, "nonexistent_metric")
    assert "not found" in fig.layout.title.text


def test_value_scatter_returns_figure(oof_df):
    fig = plot_value_scatter(oof_df)
    assert fig.layout.title.text == "Market Value vs Predicted Value"
    assert len(fig.data) == 1


def test_value_scatter_missing_column():
    df = pd.DataFrame({"a": [1, 2, 3]})
    fig = plot_value_scatter(df)
    assert "not found" in fig.layout.title.text


def test_score_matrix_returns_figure():
    prediction = generate_score_matrix()
    fig = plot_score_matrix(prediction.score_matrix)
    assert "Score Matrix" in fig.layout.title.text


def test_score_matrix_with_summary():
    prediction = generate_score_matrix()
    summary = {
        "home_win": prediction.summary.home_win,
        "draw": prediction.summary.draw,
        "away_win": prediction.summary.away_win,
        "over_2_5": prediction.summary.over_2_5,
        "btts_yes": prediction.summary.btts_yes,
    }
    fig = plot_score_matrix(prediction.score_matrix, summary=summary)
    assert "1X2" in fig.layout.title.text


def test_demo_data_player_match_schema():
    df = generate_player_match(50)
    required = {"match_id", "player_id", "team_id", "minutes_played", "goals", "assists"}
    assert required.issubset(df.columns)
    assert len(df) == 50


def test_demo_data_team_match_schema():
    df = generate_team_match(50)
    required = {"match_id", "team_id", "is_home", "goals_for", "goals_against"}
    assert required.issubset(df.columns)
    assert len(df) == 50


def test_demo_data_oof_schema():
    df = generate_oof_predictions(50)
    required = {
        "player_id",
        "actual_market_value_log",
        "predicted_market_value_log",
        "fairness_label",
    }
    assert required.issubset(df.columns)
    assert set(df["fairness_label"].unique()).issubset({"cheap", "fair", "expensive"})
