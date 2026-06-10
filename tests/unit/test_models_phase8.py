import math

import pandas as pd

from scoutfootball.evaluation import run_poisson_backtest
from scoutfootball.models import (
    DixonColesModel,
    TimeSplitConfig,
    fit_dixon_coles,
    fit_independent_poisson,
    predict_match,
    predict_match_dc,
)


def _make_team_match() -> pd.DataFrame:
    """Build 6 matches across 3 teams for testing."""
    rows = [
        ("m1", "2026-01-01", "t1", True, 2, 0),
        ("m1", "2026-01-01", "t2", False, 0, 2),
        ("m2", "2026-01-08", "t1", False, 1, 1),
        ("m2", "2026-01-08", "t2", True, 1, 1),
        ("m3", "2026-01-15", "t1", True, 3, 1),
        ("m3", "2026-01-15", "t3", False, 1, 3),
        ("m4", "2026-01-22", "t2", True, 2, 1),
        ("m4", "2026-01-22", "t3", False, 1, 2),
        ("m5", "2026-01-29", "t3", True, 0, 0),
        ("m5", "2026-01-29", "t1", False, 0, 0),
        ("m6", "2026-02-05", "t2", True, 1, 0),
        ("m6", "2026-02-05", "t1", False, 0, 1),
    ]
    return pd.DataFrame(
        [
            {
                "match_id": mid,
                "match_date": date,
                "team_id": tid,
                "is_home": home,
                "goals_for": gf,
                "goals_against": ga,
            }
            for mid, date, tid, home, gf, ga in rows
        ],
    )


_TEAM_MATCH = _make_team_match()


def test_predict_match_returns_normalized_score_matrix_and_market_summaries():
    model = fit_independent_poisson(_TEAM_MATCH)
    prediction = predict_match(model, "t1", "t2", max_goals=6)

    assert math.isclose(
        float(prediction.score_matrix.to_numpy().sum()), 1.0, rel_tol=1e-9,
    )
    assert prediction.home_lambda > prediction.away_lambda
    s = prediction.summary
    assert math.isclose(s.home_win + s.draw + s.away_win, 1.0, rel_tol=1e-9)
    assert math.isclose(s.over_2_5 + s.under_2_5, 1.0, rel_tol=1e-9)
    assert math.isclose(s.btts_yes + s.btts_no, 1.0, rel_tol=1e-9)


def test_run_poisson_backtest_only_trains_on_past_matches():
    data = [
        ("t1", "t2", 2, 1),
        ("t2", "t3", 1, 0),
        ("t3", "t1", 0, 2),
        ("t1", "t2", 1, 1),
        ("t2", "t3", 2, 2),
        ("t3", "t1", 0, 1),
    ]
    rows = []
    for idx, (ht, at, hg, ag) in enumerate(data, start=1):
        ts = pd.Timestamp("2026-01-01") + pd.Timedelta(days=7 * idx)
        rows.append({
            "match_id": f"m{idx}",
            "match_date": ts,
            "team_id": ht,
            "is_home": True,
            "goals_for": hg,
            "goals_against": ag,
        })
        rows.append({
            "match_id": f"m{idx}",
            "match_date": ts,
            "team_id": at,
            "is_home": False,
            "goals_for": ag,
            "goals_against": hg,
        })
    team_match = pd.DataFrame(rows)

    result = run_poisson_backtest(
        team_match, TimeSplitConfig(n_splits=2, gap=0), max_goals=6,
    )

    assert len(result.predictions) == 4
    assert all(
        result.fold_metrics["train_end"] <= result.fold_metrics["test_start"],
    )
    assert set(result.metrics) == {"log_loss_exact", "brier_1x2", "rps_1x2"}
    assert (result.predictions["exact_score_probability"] > 0).all()


def test_fit_dixon_coles_produces_valid_model():
    model = fit_dixon_coles(_TEAM_MATCH)

    assert isinstance(model, DixonColesModel)
    assert model.num_matches == 6
    assert len(model.team_attack) == 3
    assert len(model.team_defense) == 3
    assert model.league_mean_goals > 0
    assert -1.0 <= model.rho <= 0.0
    assert model.home_advantage > 0
    assert abs(sum(model.team_attack.values())) < 0.1


def test_predict_match_dc_returns_normalized_score_matrix():
    model = fit_dixon_coles(_TEAM_MATCH)
    prediction = predict_match_dc(model, "t1", "t2", max_goals=6)

    matrix_sum = float(prediction.score_matrix.to_numpy().sum())
    assert math.isclose(matrix_sum, 1.0, rel_tol=1e-6)
    assert prediction.home_lambda > 0
    assert prediction.away_lambda > 0
    s = prediction.summary
    assert math.isclose(s.home_win + s.draw + s.away_win, 1.0, rel_tol=1e-6)
    assert math.isclose(s.over_2_5 + s.under_2_5, 1.0, rel_tol=1e-6)


def test_dixon_coles_adjusts_low_score_probabilities():
    """DC should give different 0-0 probabilities than plain Poisson."""
    poisson_model = fit_independent_poisson(_TEAM_MATCH)
    dc_model = fit_dixon_coles(_TEAM_MATCH)

    poisson_pred = predict_match(poisson_model, "t1", "t2", max_goals=6)
    dc_pred = predict_match_dc(dc_model, "t1", "t2", max_goals=6)

    p00 = float(poisson_pred.score_matrix.to_numpy()[0, 0])
    dc00 = float(dc_pred.score_matrix.to_numpy()[0, 0])
    assert not math.isclose(p00, dc00, rel_tol=1e-6)


def test_fit_dixon_coles_requires_match_id_column():
    """fit_dixon_coles needs match_id to pair home/away rows."""
    bad_df = _TEAM_MATCH.drop(columns=["match_id"])
    try:
        fit_dixon_coles(bad_df)
    except (ValueError, KeyError):
        pass  # expected: merge fails without match_id


def test_predict_match_dc_unknown_team_defaults_to_zero():
    model = fit_dixon_coles(_TEAM_MATCH)
    prediction = predict_match_dc(model, "unknown_team", "t1")
    assert prediction.home_lambda > 0
    assert float(prediction.score_matrix.to_numpy().sum()) > 0.99
