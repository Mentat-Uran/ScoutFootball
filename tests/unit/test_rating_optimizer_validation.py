import importlib.util
import sys
from pathlib import Path

import pandas as pd
import torch


def _load_optimizer_module():
    module_name = "_rating_optimizer_under_test"
    if module_name in sys.modules:
        return sys.modules[module_name]
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "optimize_ratings_gpu.py"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _sample_frames():
    rows = []
    standings = []
    seasons = ["2021-2022", "2022-2023", "2023-2024", "2024-2025"]
    leagues = ["Premier League", "La Liga"]
    for season_idx, season in enumerate(seasons):
        for league_idx, league in enumerate(leagues):
            for team_idx in range(3):
                team = f"{league[:2]}-{team_idx}"
                points = 35 + season_idx * 3 + league_idx * 2 + team_idx * 7
                standings.append(
                    {
                        "team": team,
                        "league": league,
                        "season": season,
                        "total_points": points,
                    },
                )
                for player_idx in range(2):
                    signal = points / 100 + player_idx * 0.02
                    rows.append(
                        {
                            "player": f"{team}-p{player_idx}-{season}",
                            "team": team,
                            "league": league,
                            "season": season,
                            "sub_position": "CM",
                            "pos_idx": player_idx % 2,
                            "matches": 20 + player_idx,
                            "starts": 12 + player_idx,
                            "minutes": 900 + points * 10 + player_idx * 50,
                            "npg_p90": signal,
                            "assists_p90": signal / 2,
                            "g_a_volume": signal * 15,
                            "defense_composite": signal * 3,
                            "possession_composite": signal * 4,
                            "npg_trend": signal / 10,
                            "experience_factor": 0.8,
                        },
                    )
    return pd.DataFrame(rows), pd.DataFrame(standings)


def test_make_season_splits_are_chronological_and_non_overlapping() -> None:
    opt = _load_optimizer_module()
    players, _ = _sample_frames()

    splits = opt.make_season_splits(players, n_splits=2, min_train_seasons=2, test_seasons=1)

    assert len(splits) == 2
    assert splits[-1].test_seasons == ("2024-2025",)
    for split in splits:
        assert set(split.train_seasons).isdisjoint(split.test_seasons)
        assert split.train_seasons[-1] < split.test_seasons[0]


def test_build_feature_tensors_uses_train_reference_for_test_slice() -> None:
    opt = _load_optimizer_module()
    players, _ = _sample_frames()
    train = players[players["season"].isin(["2021-2022", "2022-2023", "2023-2024"])].copy()
    test = players[players["season"] == "2024-2025"].copy()

    feat = opt.build_feature_tensors(test, rank_reference_df=train)

    league = "Premier League"
    expected_median = train.loc[train["league"] == league, "minutes"].median()
    actual = feat["league_med"].numpy()[test["league"].to_numpy() == league]
    assert set(actual.tolist()) == {float(expected_median)}


def test_holdout_evaluation_reports_metrics_calibration_and_league_layers() -> None:
    opt = _load_optimizer_module()
    players, standings = _sample_frames()
    train = players[players["season"].isin(["2021-2022", "2022-2023", "2023-2024"])].copy()
    test = players[players["season"] == "2024-2025"].copy()
    test_standings = standings[standings["season"] == "2024-2025"].copy()

    params = opt._get_default_params_tensor(torch.device("cpu"))
    evaluation = opt.evaluate_params(
        params,
        test,
        test_standings,
        train,
        torch.device("cpu"),
        split_name="test",
        calibration_bins=3,
    )
    by_league = opt.league_metrics(evaluation["matched"], min_n=2, calibration_bins=3)

    assert evaluation["metrics"]["n_team_seasons"] == len(test_standings)
    assert "rank_loss" in evaluation["metrics"]
    assert {"bin", "calibration_gap"}.issubset(evaluation["calibration"].columns)
    assert set(by_league["league"]) == {"La Liga", "Premier League"}
