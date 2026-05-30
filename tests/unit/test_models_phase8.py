import math

import pandas as pd

from scoutlab.evaluation import run_poisson_backtest
from scoutlab.models import (
    TimeSplitConfig,
    fit_dixon_coles_placeholder,
    fit_independent_poisson,
    predict_match,
)


def test_predict_match_returns_normalized_score_matrix_and_market_summaries() -> None:
    team_match = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "match_date": "2026-01-01",
                "team_id": "t1",
                "is_home": True,
                "goals_for": 2,
                "goals_against": 0,
            },
            {
                "match_id": "m1",
                "match_date": "2026-01-01",
                "team_id": "t2",
                "is_home": False,
                "goals_for": 0,
                "goals_against": 2,
            },
            {
                "match_id": "m2",
                "match_date": "2026-01-08",
                "team_id": "t1",
                "is_home": False,
                "goals_for": 1,
                "goals_against": 1,
            },
            {
                "match_id": "m2",
                "match_date": "2026-01-08",
                "team_id": "t2",
                "is_home": True,
                "goals_for": 1,
                "goals_against": 1,
            },
            {
                "match_id": "m3",
                "match_date": "2026-01-15",
                "team_id": "t1",
                "is_home": True,
                "goals_for": 3,
                "goals_against": 1,
            },
            {
                "match_id": "m3",
                "match_date": "2026-01-15",
                "team_id": "t3",
                "is_home": False,
                "goals_for": 1,
                "goals_against": 3,
            },
        ],
    )

    model = fit_independent_poisson(team_match)
    prediction = predict_match(model, "t1", "t2", max_goals=6)

    assert math.isclose(float(prediction.score_matrix.to_numpy().sum()), 1.0, rel_tol=1e-9)
    assert prediction.home_lambda > prediction.away_lambda
    assert math.isclose(
        prediction.summary.home_win + prediction.summary.draw + prediction.summary.away_win,
        1.0,
        rel_tol=1e-9,
    )
    assert math.isclose(
        prediction.summary.over_2_5 + prediction.summary.under_2_5,
        1.0,
        rel_tol=1e-9,
    )
    assert math.isclose(
        prediction.summary.btts_yes + prediction.summary.btts_no,
        1.0,
        rel_tol=1e-9,
    )


def test_run_poisson_backtest_only_trains_on_past_matches_and_outputs_metrics() -> None:
    team_match = pd.DataFrame(
        [
            {
                "match_id": f"m{idx}",
                "match_date": pd.Timestamp("2026-01-01") + pd.Timedelta(days=7 * idx),
                "team_id": home_team,
                "is_home": True,
                "goals_for": home_goals,
                "goals_against": away_goals,
            }
            for idx, (home_team, away_team, home_goals, away_goals) in enumerate(
                [
                    ("t1", "t2", 2, 1),
                    ("t2", "t3", 1, 0),
                    ("t3", "t1", 0, 2),
                    ("t1", "t2", 1, 1),
                    ("t2", "t3", 2, 2),
                    ("t3", "t1", 0, 1),
                ],
                start=1,
            )
        ]
        + [
            {
                "match_id": f"m{idx}",
                "match_date": pd.Timestamp("2026-01-01") + pd.Timedelta(days=7 * idx),
                "team_id": away_team,
                "is_home": False,
                "goals_for": away_goals,
                "goals_against": home_goals,
            }
            for idx, (home_team, away_team, home_goals, away_goals) in enumerate(
                [
                    ("t1", "t2", 2, 1),
                    ("t2", "t3", 1, 0),
                    ("t3", "t1", 0, 2),
                    ("t1", "t2", 1, 1),
                    ("t2", "t3", 2, 2),
                    ("t3", "t1", 0, 1),
                ],
                start=1,
            )
        ],
    )

    result = run_poisson_backtest(team_match, TimeSplitConfig(n_splits=2, gap=0), max_goals=6)

    assert len(result.predictions) == 4
    assert all(result.fold_metrics["train_end"] <= result.fold_metrics["test_start"])
    assert set(result.metrics) == {"log_loss_exact", "brier_1x2", "rps_1x2"}
    assert (result.predictions["exact_score_probability"] > 0).all()


def test_fit_dixon_coles_placeholder_is_explicit() -> None:
    try:
        fit_dixon_coles_placeholder()
    except NotImplementedError as error:
        assert "not implemented" in str(error).lower()
    else:
        raise AssertionError("Expected NotImplementedError from Dixon-Coles placeholder")
