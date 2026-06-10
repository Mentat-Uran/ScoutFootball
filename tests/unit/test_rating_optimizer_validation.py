import sys
from pathlib import Path

import pandas as pd
import torch


def _load_optimizer_module():
    """Import optimizer package modules directly."""
    repo_root = Path(__file__).resolve().parents[2]
    scripts_dir = str(repo_root / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import types

    import optimizer.constants as _c
    import optimizer.data as _d
    import optimizer.optimization as _o
    import optimizer.scoring as _s
    mod = types.SimpleNamespace()
    # constants
    mod.POSITIONS = _c.POSITIONS
    mod.POS_TO_IDX = _c.POS_TO_IDX
    mod.N_POS = _c.N_POS
    mod.N_DIM = _c.N_DIM
    mod.N_PARAMS = _c.N_PARAMS
    mod.DIMENSIONS = _c.DIMENSIONS
    mod.POSITION_DIMENSION_PRIOR = _c.POSITION_DIMENSION_PRIOR
    mod.ATTACK_WEIGHT_PRIOR = _c.ATTACK_WEIGHT_PRIOR
    mod.QUALITY_SUBWEIGHT_PRIOR = _c.QUALITY_SUBWEIGHT_PRIOR
    mod.TEAM_AGG_MINUTES_CAP = _c.TEAM_AGG_MINUTES_CAP
    mod.TEAM_AGG_CORE_MINUTES = _c.TEAM_AGG_CORE_MINUTES
    mod.TEAM_AGG_CORE_SCALE = _c.TEAM_AGG_CORE_SCALE
    mod.TEAM_AGG_CAPPED_MINUTES_BLEND = _c.TEAM_AGG_CAPPED_MINUTES_BLEND
    mod.POSITION_SLOT_CAPS = _c.POSITION_SLOT_CAPS
    mod.POSITION_SLOT_GROUPS = _c.POSITION_SLOT_GROUPS
    mod.POSITION_DIMENSION_CAPS = _c.POSITION_DIMENSION_CAPS
    mod.map_position_detailed = _c.map_position_detailed
    mod.normalize_team_name = _c.normalize_team_name
    mod.refine_role_positions = _c.refine_role_positions
    mod.apply_position_weight_caps = _c.apply_position_weight_caps
    mod.SeasonSplit = _c.SeasonSplit
    mod.TeamPointsCalibrator = _c.TeamPointsCalibrator
    # scoring
    mod.build_feature_tensors = _s.build_feature_tensors
    mod.compute_ratings_torch = _s.compute_ratings_torch
    mod.compute_team_avg_ratings = _s.compute_team_avg_ratings
    mod.compute_team_avg_ratings_torch = _s.compute_team_avg_ratings_torch
    mod.build_team_target_tensors = _s.build_team_target_tensors
    mod._build_team_aggregation_weights = _s._build_team_aggregation_weights
    # data
    mod.make_season_splits = _d.make_season_splits
    mod.compute_input_hash = _d.compute_input_hash
    mod.save_model_run = _d.save_model_run
    mod.build_dc_tensors = _d.build_dc_tensors
    mod.evaluate_params = _d.evaluate_params
    mod.fit_team_points_calibrator = _d.fit_team_points_calibrator
    mod.apply_team_points_calibrator = _d.apply_team_points_calibrator
    mod.league_metrics = _d.league_metrics
    mod.rating_metrics = _d.rating_metrics
    # losses
    import optimizer.losses as _l
    mod.objective_torch = _l.objective_torch
    # optimization
    mod._get_default_params_tensor = _o._get_default_params_tensor
    mod.cosine_lr_scale = _o.cosine_lr_scale
    return mod


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


def test_team_aggregation_weights_reduce_raw_minutes_dominance() -> None:
    opt = _load_optimizer_module()
    frame = pd.DataFrame(
        [
            {
                "player": "High Minute Average",
                "team": "Example FC",
                "league": "Premier League",
                "season": "2024-2025",
                "sub_position": "CM",
                "pos_idx": opt.POS_TO_IDX["CM"],
                "matches": 38,
                "starts": 38,
                "minutes": 3000,
                "npg_p90": 0.05,
                "assists_p90": 0.05,
                "g_a_volume": 2.0,
                "defense_composite": 1.0,
                "possession_composite": 1.0,
                "npg_trend": 0.0,
                "experience_factor": 1.0,
            },
            {
                "player": "Rotated Core",
                "team": "Example FC",
                "league": "Premier League",
                "season": "2024-2025",
                "sub_position": "CM",
                "pos_idx": opt.POS_TO_IDX["CM"],
                "matches": 24,
                "starts": 14,
                "minutes": 1200,
                "npg_p90": 0.20,
                "assists_p90": 0.20,
                "g_a_volume": 8.0,
                "defense_composite": 1.2,
                "possession_composite": 1.4,
                "npg_trend": 0.0,
                "experience_factor": 1.0,
            },
            {
                "player": "Low Minute Reserve",
                "team": "Example FC",
                "league": "Premier League",
                "season": "2024-2025",
                "sub_position": "CM",
                "pos_idx": opt.POS_TO_IDX["CM"],
                "matches": 8,
                "starts": 2,
                "minutes": 300,
                "npg_p90": 0.10,
                "assists_p90": 0.08,
                "g_a_volume": 1.0,
                "defense_composite": 0.8,
                "possession_composite": 0.9,
                "npg_trend": 0.0,
                "experience_factor": 0.5,
            },
        ],
    )

    feat = opt.build_feature_tensors(frame)
    weights = feat["team_agg_weight"].numpy()
    raw_minutes = frame["minutes"].to_numpy(dtype=float)
    raw_share = raw_minutes / raw_minutes.sum()

    assert abs(float(weights.sum()) - 1.0) < 1e-6
    assert weights[0] < raw_share[0]
    assert weights[1] > raw_share[1]

    ratings = torch.tensor([50.0, 70.0, 55.0])
    robust_avg = opt.compute_team_avg_ratings(feat, ratings, torch.device("cpu"))[0]
    raw_avg = float((ratings.numpy() * raw_share).sum())
    assert robust_avg > raw_avg


def test_refine_role_positions_uses_history_and_profile_signals() -> None:
    opt = _load_optimizer_module()
    frame = pd.DataFrame(
        [
            {
                "player": "Wide Creator",
                "source_position": "FW,MF",
                "sub_position": "W",
                "pos_idx": opt.POS_TO_IDX["W"],
                "npg_p90": 0.10,
                "assists_p90": 0.10,
                "g_a_volume": 3.0,
                "crosses_p90": 0.5,
                "defense_composite": 0.2,
            },
            {
                "player": "Wide Creator",
                "source_position": "MF",
                "sub_position": "CM",
                "pos_idx": opt.POS_TO_IDX["CM"],
                "npg_p90": 0.24,
                "assists_p90": 0.23,
                "g_a_volume": 9.0,
                "crosses_p90": 0.6,
                "defense_composite": 0.2,
            },
            {
                "player": "Wing Back",
                "source_position": "DF,MF",
                "sub_position": "FB",
                "pos_idx": opt.POS_TO_IDX["FB"],
                "npg_p90": 0.02,
                "assists_p90": 0.05,
                "g_a_volume": 1.0,
                "crosses_p90": 1.2,
                "defense_composite": 1.0,
            },
            {
                "player": "Wing Back",
                "source_position": "MF",
                "sub_position": "CM",
                "pos_idx": opt.POS_TO_IDX["CM"],
                "npg_p90": 0.08,
                "assists_p90": 0.17,
                "g_a_volume": 4.0,
                "crosses_p90": 2.8,
                "defense_composite": 1.1,
            },
            {
                "player": "Central Mid",
                "source_position": "MF",
                "sub_position": "CM",
                "pos_idx": opt.POS_TO_IDX["CM"],
                "npg_p90": 0.10,
                "assists_p90": 0.24,
                "g_a_volume": 5.0,
                "crosses_p90": 0.4,
                "defense_composite": 0.6,
            },
        ],
    )

    refined = opt.refine_role_positions(frame)

    latest = refined.drop_duplicates("player", keep="last").set_index("player")
    assert latest.loc["Wide Creator", "sub_position"] == "W"
    assert latest.loc["Wing Back", "sub_position"] == "FB"
    assert latest.loc["Central Mid", "sub_position"] == "CM"
    assert latest.loc["Wide Creator", "pos_idx"] == opt.POS_TO_IDX["W"]
    assert latest.loc["Wing Back", "pos_idx"] == opt.POS_TO_IDX["FB"]


def test_league_strength_curve_separates_identical_big5_profiles() -> None:
    opt = _load_optimizer_module()
    params = opt._get_default_params_tensor(torch.device("cpu"))
    feat = {
        "pos_idx": torch.tensor([opt.POS_TO_IDX["ST"], opt.POS_TO_IDX["ST"]], dtype=torch.long),
        "npg_pct": torch.tensor([80.0, 80.0]),
        "ast_pct": torch.tensor([70.0, 70.0]),
        "vol_pct": torch.tensor([85.0, 85.0]),
        "def_pct": torch.tensor([50.0, 50.0]),
        "pos_pct": torch.tensor([55.0, 55.0]),
        "trend_pct": torch.tensor([50.0, 50.0]),
        "experience": torch.tensor([1.0, 1.0]),
        "minutes": torch.tensor([2400.0, 2400.0]),
        "starts": torch.tensor([28.0, 28.0]),
        "matches": torch.tensor([32.0, 32.0]),
        "league_med": torch.tensor([1800.0, 1800.0]),
        "league_idx": torch.tensor([0, 1], dtype=torch.long),
        "league_names": ["Ligue 1", "Premier League"],
    }

    ratings = opt.compute_ratings_torch(feat, params, torch.device("cpu"))

    assert ratings[1] > ratings[0]
    assert float(ratings[1] - ratings[0]) > 5.0


def test_position_weight_caps_limit_cm_shortcuts() -> None:
    opt = _load_optimizer_module()
    weights = torch.full((opt.N_POS, opt.N_DIM), 1.0 / opt.N_DIM)
    cm_idx = opt.POS_TO_IDX["CM"]
    weights[cm_idx] = torch.tensor([0.40, 0.35, 0.05, 0.05, 0.15])

    capped = opt.apply_position_weight_caps(weights)

    assert torch.allclose(capped.sum(dim=1), torch.ones(opt.N_POS))
    assert capped[cm_idx, opt.DIMENSIONS.index("availability")] <= 0.18 + 1e-6
    assert capped[cm_idx, opt.DIMENSIONS.index("attack")] <= 0.22 + 1e-6
    assert capped[cm_idx, opt.DIMENSIONS.index("quality")] <= 0.24 + 1e-6

    availability_idx = opt.DIMENSIONS.index("availability")
    shortcut_weights = torch.zeros((opt.N_POS, opt.N_DIM))
    shortcut_weights[:, availability_idx] = 0.90
    shortcut_weights[:, opt.DIMENSIONS.index("attack")] = 0.10
    shortcut_capped = opt.apply_position_weight_caps(shortcut_weights)
    expected_caps = torch.tensor([row[availability_idx] for row in opt.POSITION_DIMENSION_CAPS])
    assert torch.all(shortcut_capped[:, availability_idx] <= expected_caps + 1e-6)


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
    assert evaluation["metrics"]["target_team_seasons"] == len(test_standings)
    assert evaluation["metrics"]["team_coverage"] == 1.0
    assert "rank_loss" in evaluation["metrics"]
    assert {"bin", "calibration_gap"}.issubset(evaluation["calibration"].columns)
    assert {"target_teams", "rated_teams", "matched_teams", "coverage"}.issubset(
        evaluation["coverage"].columns,
    )
    assert set(by_league["league"]) == {"La Liga", "Premier League"}


def test_team_points_calibrator_expands_compressed_strength_scale() -> None:
    opt = _load_optimizer_module()
    matched = pd.DataFrame(
        {
            "team": [f"t{i}" for i in range(5)],
            "league": ["Premier League"] * 5,
            "season": ["2024-2025"] * 5,
            "pred_rating": [42.0, 45.0, 48.0, 51.0, 54.0],
            "actual_points": [18.0, 34.0, 52.0, 73.0, 92.0],
        },
    )

    calibrator = opt.fit_team_points_calibrator(matched)
    calibrated = opt.apply_team_points_calibrator(matched, calibrator)
    metrics = opt.rating_metrics(calibrated)

    assert calibrator.slope > 3.0
    assert metrics["raw_spread_ratio"] < 0.35
    assert 0.95 <= metrics["points_spread_ratio"] <= 1.05
    assert "pred_points_calibrated" in calibrated.columns


def test_team_points_calibrator_applies_shrunken_league_offsets() -> None:
    opt = _load_optimizer_module()
    matched = pd.DataFrame(
        {
            "team": [f"a{i}" for i in range(6)] + [f"b{i}" for i in range(6)],
            "league": ["League A"] * 6 + ["League B"] * 6,
            "season": ["2024-2025"] * 12,
            "pred_rating": [40, 42, 44, 46, 48, 50, 40, 42, 44, 46, 48, 50],
            "actual_points": [42, 45, 48, 51, 54, 57, 22, 25, 28, 31, 34, 37],
        },
    )

    global_only = opt.apply_team_points_calibrator(
        matched,
        opt.fit_team_points_calibrator(matched, use_league_offsets=False),
    )
    league_calibrated = opt.apply_team_points_calibrator(
        matched,
        opt.fit_team_points_calibrator(
            matched,
            league_prior_n=1,
            league_offset_cap=20,
        ),
    )
    global_mae = (global_only["pred_points_calibrated"] - global_only["actual_points"]).abs().mean()
    league_mae = (
        league_calibrated["pred_points_calibrated"] - league_calibrated["actual_points"]
    ).abs().mean()

    assert league_mae < global_mae
    assert league_calibrated["pred_points_league_offset"].abs().max() > 0


def test_composite_objective_includes_points_distribution_and_tail_losses() -> None:
    opt = _load_optimizer_module()
    players, standings = _sample_frames()
    feat = opt.build_feature_tensors(players)
    params = opt._get_default_params_tensor(torch.device("cpu")).clone().requires_grad_(True)

    loss, components = opt.objective_torch(
        feat,
        standings,
        params,
        torch.device("cpu"),
        return_components=True,
    )
    loss.backward()

    assert {"points_loss", "distribution", "tail", "league_bias"}.issubset(components)
    assert params.grad is not None
    assert torch.isfinite(params.grad).all()


def test_cosine_lr_scale_warmup_and_decay_shape() -> None:
    opt = _load_optimizer_module()

    first = opt.cosine_lr_scale(0, total_steps=100, warmup_steps=10, min_lr_ratio=0.08)
    warm = opt.cosine_lr_scale(9, total_steps=100, warmup_steps=10, min_lr_ratio=0.08)
    final = opt.cosine_lr_scale(100, total_steps=100, warmup_steps=10, min_lr_ratio=0.08)

    assert first < warm
    assert warm == 1.0
    assert 0.079 <= final <= 0.081
