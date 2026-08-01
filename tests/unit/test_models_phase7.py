import pandas as pd

from scoutfootball.models import TimeSplitConfig, classify_fairness, fit_regressor


def test_classify_fairness_assigns_three_bands_consistently() -> None:
    predicted = pd.Series([2.0, 2.0, 2.0])
    actual = pd.Series([2.4, 2.05, 1.6])

    labels = classify_fairness(predicted, actual, threshold=0.2)

    assert labels.tolist() == ["expensive", "fair", "cheap"]


def test_fit_regressor_outputs_oof_metrics_and_beats_group_median_baseline() -> None:
    rows = []
    for idx in range(18):
        snapshot_date = pd.Timestamp("2026-01-01") + pd.Timedelta(days=idx * 7)
        age = 20 + (idx % 5)
        npxg = 0.2 + 0.12 * idx
        xa = 0.1 + 0.04 * idx
        minutes = 500 + 20 * idx
        market_value = 4_000_000 + 7_500_000 * npxg + 2_500_000 * xa + 1_500 * minutes
        rows.append(
            {
                "player_id": f"p{idx}",
                "player_name": f"Player {idx}",
                "team_id": f"t{idx % 3}",
                "team_name": f"Team {idx % 3}",
                "snapshot_date": snapshot_date,
                "market_value": market_value,
                "position_group": "fwd",
                "league": "EPL",
                "age": age,
                "npxg_p90_shrunk_5": npxg,
                "xa_p90_shrunk_5": xa,
                "prior_minutes_5": minutes,
                "minutes_share": 0.8,
                "elo_pre_mean_5": 1500 + idx,
            },
        )

    feature_df = pd.DataFrame(rows)

    result = fit_regressor(
        feature_df,
        TimeSplitConfig(n_splits=3, gap=0),
        feature_version="feature-v1",
        data_version="data-v1",
    )

    assert len(result.oof_predictions) == 12
    assert result.metrics["mae_model"] < result.metrics["mae_baseline"]
    assert result.metrics["mae_improvement_vs_baseline"] > 0
    assert result.feature_version == "feature-v1"
    assert result.data_version == "data-v1"
    assert set(result.oof_predictions["fairness_label"].unique()).issubset(
        {"cheap", "fair", "expensive"},
    )


def test_fit_regressor_time_splits_only_train_on_past_rows() -> None:
    feature_df = pd.DataFrame(
        [
            {
                "player_id": f"p{idx}",
                "snapshot_date": pd.Timestamp("2026-01-01") + pd.Timedelta(days=idx),
                "market_value": 1_000_000 + idx * 50_000,
                "position_group": "mid",
                "league": "EPL",
                "age": 22 + idx,
                "npxg_p90_shrunk_5": 0.2 + 0.01 * idx,
            }
            for idx in range(10)
        ],
    )

    result = fit_regressor(feature_df, TimeSplitConfig(n_splits=2, gap=0))

    assert all(result.fold_metrics["train_end"] <= result.fold_metrics["test_start"])
