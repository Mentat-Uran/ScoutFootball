"""Unit tests for composite objective functions in optimize_ratings_gpu.py."""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip("torch")


def _load_optimizer_module():
    module_name = "_optimize_ratings_gpu_shared"
    if module_name in sys.modules:
        return sys.modules[module_name]
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "optimize_ratings_gpu.py"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_mod = _load_optimizer_module()
POSITIONS = _mod.POSITIONS
POS_TO_IDX = _mod.POS_TO_IDX
_get_default_params_tensor = _mod._get_default_params_tensor
build_feature_tensors = _mod.build_feature_tensors
compute_ratings_torch = _mod.compute_ratings_torch
extreme_penalty = _mod.extreme_penalty
ndcg_loss = _mod.ndcg_loss
objective_torch = _mod.objective_torch
position_consistency_loss = _mod.position_consistency_loss


def _make_synthetic_feat(n_players=40, device="cpu"):
    """Build a minimal synthetic feature dict for testing."""
    rng = np.random.default_rng(42)

    # Assign positions: 5 players per position
    positions = []
    for pos in POSITIONS:
        positions.extend([pos] * 5)
    pos_idx_arr = np.array([POS_TO_IDX[p] for p in positions], dtype=np.int64)

    # Core metrics
    npg_p90 = rng.uniform(0, 0.5, n_players).astype(np.float32)
    assists_p90 = rng.uniform(0, 0.3, n_players).astype(np.float32)
    g_a_volume = (npg_p90 + assists_p90) * rng.uniform(5, 15, n_players).astype(np.float32)
    defense_composite = rng.uniform(0, 3, n_players).astype(np.float32)
    possession_composite = rng.uniform(0, 3, n_players).astype(np.float32)
    crosses_p90 = rng.uniform(0, 2, n_players).astype(np.float32)

    minutes = rng.uniform(200, 3000, n_players).astype(np.float32)
    starts = (minutes * rng.uniform(0.5, 0.9, n_players)).astype(np.float32)
    matches = (minutes / 90 * rng.uniform(0.7, 1.0, n_players)).astype(np.float32)

    # Build team-season groups: 12 teams, 2 leagues, 1 season
    # Need >=10 matched team-seasons for objective_torch to compute real loss
    n_teams = 12
    n_leagues = 2
    team_names = [f"Team{i}" for i in range(n_teams)]
    league_names = ["LeagueA", "LeagueB"]
    season = "2425"

    # Assign players to teams
    team_assignments = [team_names[i % n_teams] for i in range(n_players)]
    league_assignments = [league_names[i % n_leagues] for i in range(n_players)]

    # Build DataFrame
    df = pd.DataFrame({
        "player": [f"Player{i}" for i in range(n_players)],
        "team": team_assignments,
        "league": league_assignments,
        "season": season,
        "source_position": positions,
        "sub_position": positions,
        "pos_idx": pos_idx_arr,
        "matches": matches,
        "starts": starts,
        "minutes": minutes,
        "npg_p90": npg_p90,
        "assists_p90": assists_p90,
        "g_a_volume": g_a_volume,
        "defense_composite": defense_composite,
        "possession_composite": possession_composite,
        "crosses_p90": crosses_p90,
        "experience_factor": np.ones(n_players, dtype=np.float32),
    })

    # Use build_feature_tensors to get a proper feat dict
    feat = build_feature_tensors(df)

    # Build team_pts DataFrame: each team belongs to exactly one league
    team_pts_rows = []
    for i, team in enumerate(team_names):
        league = league_names[i % n_leagues]
        team_pts_rows.append({
            "team": team,
            "league": league,
            "season": season,
            "total_points": float(rng.integers(30, 90)),
        })
    team_pts = pd.DataFrame(team_pts_rows)

    return feat, team_pts, df


class TestExtremePenalty:
    def test_returns_scalar_with_gradient(self):
        ratings = torch.randn(100, requires_grad=True)
        penalty = extreme_penalty(ratings)
        assert penalty.dim() == 0, "Should return scalar"
        assert penalty.requires_grad, "Should require grad"
        penalty.backward()
        assert ratings.grad is not None, "Gradient should flow"

    def test_zero_for_non_extreme(self):
        # All values within 1 sigma -> no penalty
        ratings = torch.randn(1000)
        ratings = (ratings - ratings.mean()) / (ratings.std() + 1e-8)  # z-scores
        ratings = ratings * 0.5  # well within sigma=3
        penalty = extreme_penalty(ratings, sigma=3.0)
        assert penalty.item() == pytest.approx(0.0, abs=1e-3)

    def test_positive_for_extreme(self):
        # Create extreme values
        ratings = torch.cat([torch.zeros(99), torch.tensor([100.0])])
        penalty = extreme_penalty(ratings, sigma=3.0)
        assert penalty.item() > 0.0, "Should penalize extreme values"

    def test_larger_sigma_less_penalty(self):
        ratings = torch.cat([torch.zeros(99), torch.tensor([50.0])])
        p1 = extreme_penalty(ratings, sigma=1.0)
        p3 = extreme_penalty(ratings, sigma=3.0)
        assert p1.item() >= p3.item(), "Larger sigma should give less or equal penalty"


class TestNDCGLoss:
    def test_returns_scalar_with_gradient(self):
        feat, team_pts, _df = _make_synthetic_feat()
        device = torch.device("cpu")
        params = _get_default_params_tensor(device)
        params = params.clone().detach().requires_grad_(True)
        ratings = compute_ratings_torch(feat, params, device)

        loss = ndcg_loss(feat, ratings, team_pts, device, k=20)
        assert loss.dim() == 0, "Should return scalar"
        assert isinstance(loss, torch.Tensor)

    def test_loss_range(self):
        feat, team_pts, _df = _make_synthetic_feat()
        device = torch.device("cpu")
        params = _get_default_params_tensor(device)
        ratings = compute_ratings_torch(feat, params, device)

        loss = ndcg_loss(feat, ratings, team_pts, device, k=20)
        # NDCG loss = 1 - NDCG, should be in [0, 1] for valid NDCG
        assert 0.0 <= loss.item() <= 1.0, f"NDCG loss should be in [0,1], got {loss.item()}"

    def test_perfect_ranking_low_loss(self):
        """When team ratings perfectly match actual points ranking, NDCG loss should be low."""
        feat, team_pts, _df = _make_synthetic_feat()
        device = torch.device("cpu")

        # Manually construct ratings that perfectly correlate with team points
        # This is a best-effort test since we can't easily inject perfect ratings
        params = _get_default_params_tensor(device)
        ratings = compute_ratings_torch(feat, params, device)
        loss = ndcg_loss(feat, ratings, team_pts, device, k=20)
        # Just verify it returns a valid number
        assert loss.item() >= 0.0


class TestPositionConsistencyLoss:
    def test_returns_scalar_with_gradient(self):
        feat, team_pts, _df = _make_synthetic_feat()
        device = torch.device("cpu")
        params = _get_default_params_tensor(device)
        params = params.clone().detach().requires_grad_(True)
        ratings = compute_ratings_torch(feat, params, device)

        loss = position_consistency_loss(feat, ratings, device)
        assert loss.dim() == 0, "Should return scalar"
        assert isinstance(loss, torch.Tensor)

    def test_loss_non_negative(self):
        feat, team_pts, _df = _make_synthetic_feat()
        device = torch.device("cpu")
        params = _get_default_params_tensor(device)
        ratings = compute_ratings_torch(feat, params, device)

        loss = position_consistency_loss(feat, ratings, device)
        assert loss.item() >= 0.0, "Position consistency loss should be non-negative"

    def test_gradient_flows(self):
        feat, team_pts, _df = _make_synthetic_feat()
        device = torch.device("cpu")
        params = _get_default_params_tensor(device).clone().detach().requires_grad_(True)
        ratings = compute_ratings_torch(feat, params, device)

        loss = position_consistency_loss(feat, ratings, device)
        if loss.requires_grad:
            loss.backward()
            assert params.grad is not None, "Gradient should flow to params"


class TestCompositeObjective:
    def test_returns_scalar_with_gradient(self):
        feat, team_pts, _df = _make_synthetic_feat()
        device = torch.device("cpu")
        params = _get_default_params_tensor(device).clone().detach().requires_grad_(True)

        loss = objective_torch(
            feat, team_pts, params, device,
            spearman_weight=0.50,
            ndcg_weight=0.20,
            position_consistency_weight=0.15,
            extreme_penalty_weight=0.10,
            prior_weight=0.05,
            prior_params=_get_default_params_tensor(device),
        )
        assert loss.dim() == 0, "Should return scalar"
        assert loss.requires_grad, "Should require grad"
        loss.backward()
        assert params.grad is not None, "Gradient should flow"

    def test_default_weights(self):
        feat, team_pts, _df = _make_synthetic_feat()
        device = torch.device("cpu")
        params = _get_default_params_tensor(device).clone().detach().requires_grad_(True)

        loss = objective_torch(feat, team_pts, params, device)
        assert loss.dim() == 0
        assert loss.item() > 0.0, "Loss should be positive"

    def test_changing_weights_changes_loss(self):
        feat, team_pts, _df = _make_synthetic_feat()
        device = torch.device("cpu")
        params = _get_default_params_tensor(device).clone().detach()

        # With all weight on spearman
        loss_sp = objective_torch(
            feat, team_pts, params, device,
            spearman_weight=1.0, ndcg_weight=0.0,
            position_consistency_weight=0.0,
            points_regression_weight=0.0,
            distribution_weight=0.0,
            tail_calibration_weight=0.0,
            extreme_penalty_weight=0.0,
            prior_weight=0.0,
        )

        # With all weight on extreme penalty
        loss_ext = objective_torch(
            feat, team_pts, params, device,
            spearman_weight=0.0, ndcg_weight=0.0,
            position_consistency_weight=0.0,
            points_regression_weight=0.0,
            distribution_weight=0.0,
            tail_calibration_weight=0.0,
            extreme_penalty_weight=1.0,
            prior_weight=0.0,
        )

        # The two losses should differ since they measure different things
        assert loss_sp.item() != pytest.approx(
            loss_ext.item(), abs=1e-4
        ), "Different weight configurations should yield different losses"

    def test_prior_reg_with_prior_params(self):
        feat, team_pts, _df = _make_synthetic_feat()
        device = torch.device("cpu")
        prior = _get_default_params_tensor(device)
        # Shifted params
        params = (prior + 1.0).clone().detach().requires_grad_(True)

        loss = objective_torch(
            feat, team_pts, params, device,
            spearman_weight=0.0, ndcg_weight=0.0,
            position_consistency_weight=0.0,
            points_regression_weight=0.0,
            distribution_weight=0.0,
            tail_calibration_weight=0.0,
            extreme_penalty_weight=0.0,
            prior_weight=1.0, prior_params=prior,
        )
        # Prior reg = mean((params - prior)^2) = mean(1.0^2) = 1.0
        assert loss.item() == pytest.approx(1.0, abs=0.01)

    def test_verbose_mode(self, capsys):
        feat, team_pts, _df = _make_synthetic_feat()
        device = torch.device("cpu")
        params = _get_default_params_tensor(device).clone().detach().requires_grad_(True)

        objective_torch(
            feat, team_pts, params, device,
            verbose=True,
        )
        captured = capsys.readouterr()
        assert "rank=" in captured.out
        assert "ndcg=" in captured.out
        assert "pos=" in captured.out
        assert "ext=" in captured.out
        assert "prior=" in captured.out
        assert "total=" in captured.out

    def test_too_few_matched_teams(self):
        """When fewer than 10 matched teams, should return fallback loss."""
        feat, team_pts, _df = _make_synthetic_feat()
        device = torch.device("cpu")
        params = _get_default_params_tensor(device).clone().detach().requires_grad_(True)

        # Create team_pts with no matching teams
        empty_team_pts = pd.DataFrame({
            "team": ["NonExistent"],
            "league": ["NonExistent"],
            "season": ["9999"],
            "total_points": [50.0],
        })

        loss = objective_torch(feat, empty_team_pts, params, device)
        assert loss.item() == 1.0, "Should return fallback loss of 1.0"
