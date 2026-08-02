"""Run candidate-only team-points neural models on local optimizer inputs.

This is an experiment runner, not a promotion command.  It writes only to a
new local run directory and never changes the active rating artifact.  Use
``--compare`` to train the MLP and Set Transformer on the same chronological
split and write a ranked comparison alongside both candidate runs.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from optimizer.data import load_data  # noqa: E402
from optimizer.optimization import _get_default_params_tensor  # noqa: E402
from optimizer.scoring import build_feature_tensors, compute_ratings_torch  # noqa: E402

from scoutfootball.models.team_points_mlp import (  # noqa: E402
    TeamPointsMLPConfig,
    train_team_points_mlp,
    write_team_points_mlp_artifacts,
)


def _parse_hidden(value: str) -> tuple[int, ...]:
    widths = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not widths or any(width < 1 for width in widths):
        raise argparse.ArgumentTypeError("hidden sizes must be positive, e.g. 96,48")
    return widths


def _find_optimizer_prior(
    data_dir: Path, explicit: Path | None
) -> tuple[pd.DataFrame | None, str | None]:
    candidates = (
        [explicit.resolve()]
        if explicit is not None
        else sorted(
            (path for path in (data_dir / "models" / "runs").glob("*") if path.is_dir()),
            reverse=True,
        )
    )
    for run_dir in candidates:
        ratings_path = run_dir / "player_ratings_candidate.parquet"
        if not ratings_path.is_file():
            continue
        try:
            meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
            if meta.get("model_type") in {
                "team_points_mlp",
                "team_points_set_transformer",
            }:
                continue
            ratings = pd.read_parquet(ratings_path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        required = {"player", "team", "league", "season", "optimized_score"}
        if required.issubset(ratings.columns):
            return ratings, str(ratings_path.relative_to(data_dir))
    return None, None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train candidate neural player ratings against team-season points proxy"
    )
    parser.add_argument("--data-dir", type=Path, default=REPO_ROOT / "data")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--epochs",
        type=int,
        default=400,
        help="maximum epochs; early stopping still selects the best validation checkpoint",
    )
    parser.add_argument("--hidden", type=_parse_hidden, default=(96, 48))
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--weight-decay", type=float, default=0.0001)
    parser.add_argument(
        "--patience",
        type=int,
        default=50,
        help="validation epochs without improvement before early stopping",
    )
    parser.add_argument("--min-team-players", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--truth-label-weight", type=float, default=0.08)
    parser.add_argument("--optimizer-run", type=Path, default=None)
    parser.add_argument("--attention-dim", type=int, default=48)
    parser.add_argument("--attention-heads", type=int, default=4)
    parser.add_argument("--attention-layers", type=int, default=1)
    parser.add_argument("--attention-dropout", type=float, default=0.05)
    parser.add_argument(
        "--architecture",
        choices=("mlp", "set_transformer"),
        default="set_transformer",
        help="single architecture to train when --compare is not used",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="train both MLP and Set Transformer on the identical split",
    )
    args = parser.parse_args()

    data_dir = args.data_dir.resolve()
    loaded = load_data(data_dir)
    frame, team_points = loaded[:2]
    optimizer_features = build_feature_tensors(frame)
    prior_params = _get_default_params_tensor(torch.device("cpu"))
    frame = frame.copy()
    frame["optimizer_prior_score"] = (
        compute_ratings_torch(optimizer_features, prior_params, torch.device("cpu"))
        .detach()
        .cpu()
        .numpy()
    )
    optimizer_prior, optimizer_prior_path = _find_optimizer_prior(data_dir, args.optimizer_run)
    if optimizer_prior is not None:
        keys = ["player", "team", "league", "season"]
        optimizer_prior = optimizer_prior[keys + ["optimized_score"]].copy()
        optimizer_prior["season"] = optimizer_prior["season"].astype(str)
        optimizer_prior = optimizer_prior.rename(
            columns={"optimized_score": "optimizer_prior_score_fitted"}
        )
        frame["season"] = frame["season"].astype(str)
        frame = frame.merge(
            optimizer_prior,
            on=keys,
            how="left",
            validate="one_to_one",
        )
        frame["optimizer_prior_score"] = frame["optimizer_prior_score_fitted"].fillna(
            frame["optimizer_prior_score"]
        )
        frame = frame.drop(columns=["optimizer_prior_score_fitted"])
        frame.attrs["optimizer_prior_artifact"] = optimizer_prior_path
    truth_path = data_dir / "gold" / "feature_store" / "player_truth_labels.parquet"
    truth_labels = None
    if truth_path.is_file():
        truth_labels = pd.read_parquet(truth_path)
    architectures = ("mlp", "set_transformer") if args.compare else (args.architecture,)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    if args.output_dir is not None:
        output_root = args.output_dir.resolve()
    else:
        suffix = "comparison" if args.compare else args.architecture.replace("_", "-")
        output_root = data_dir / "models" / "runs" / f"{timestamp}-team-points-{suffix}"

    results: dict[str, dict[str, object]] = {}
    exit_code = 0
    for architecture in architectures:
        config = TeamPointsMLPConfig(
            architecture=architecture,
            hidden_layer_sizes=args.hidden,
            attention_dim=args.attention_dim,
            attention_heads=args.attention_heads,
            attention_layers=args.attention_layers,
            attention_dropout=args.attention_dropout,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
            weight_decay=args.weight_decay,
            patience=args.patience,
            min_team_players=args.min_team_players,
            seed=args.seed,
            truth_label_weight=args.truth_label_weight,
        )
        result = train_team_points_mlp(
            frame,
            team_points,
            config=config,
            truth_labels=truth_labels,
        )
        output_dir = output_root / architecture.replace("_", "-") if args.compare else output_root
        write_team_points_mlp_artifacts(result, output_dir, config=config, input_frame=frame)
        print(f"architecture={architecture} status={result.status}")
        print(f"candidate_run={output_dir}")
        print(json.dumps(result.metrics, indent=2, ensure_ascii=False))
        test_metrics = result.metrics.get("test", {}) if isinstance(result.metrics, dict) else {}
        results[architecture] = {
            "run": str(output_dir),
            "trained": result.trained,
            "test": test_metrics,
        }
        if not result.trained:
            exit_code = 1

    if args.compare:
        comparison_rows: list[dict[str, object]] = []
        for architecture, item in results.items():
            test = item.get("test", {})
            if isinstance(test, dict):
                comparison_rows.append(
                    {
                        "method": architecture,
                        "run": item["run"],
                        "spearman": test.get("spearman"),
                        "mae": test.get("mae"),
                        "rmse": test.get("rmse"),
                        "r2": test.get("r2"),
                        "bias": test.get("bias"),
                    }
                )
        optimizer_metrics = None
        if optimizer_prior_path:
            optimizer_meta_path = data_dir / optimizer_prior_path
            optimizer_meta_path = optimizer_meta_path.parent / "meta.json"
            try:
                optimizer_meta = json.loads(optimizer_meta_path.read_text(encoding="utf-8"))
                optimizer_test = optimizer_meta.get("metrics", {}).get("optimized_test", {})
                if isinstance(optimizer_test, dict):
                    optimizer_metrics = {
                        "method": "optimizer",
                        "run": str(optimizer_meta_path.parent),
                        "spearman": optimizer_test.get("spearman"),
                        "mae": optimizer_test.get("points_mae"),
                        "rmse": optimizer_test.get("points_rmse"),
                        "r2": None,
                        "bias": optimizer_test.get("points_bias"),
                    }
                    comparison_rows.append(optimizer_metrics)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                optimizer_metrics = None
        comparable = [
            row
            for row in comparison_rows
            if isinstance(row.get("spearman"), (float, int))
            and isinstance(row.get("mae"), (float, int))
        ]
        ranked = sorted(
            comparable,
            key=lambda row: (
                -float(row["spearman"]),
                float(row["mae"]),
                -float(row["r2"]) if isinstance(row.get("r2"), (float, int)) else 0.0,
            ),
        )
        comparison = {
            "selection_rule": "highest holdout Spearman, then lowest MAE, then highest R2",
            "same_chronological_split": True,
            "methods": comparison_rows,
            "ranked_methods": [row["method"] for row in ranked],
            "selected_method": ranked[0]["method"] if ranked else None,
        }
        output_root.mkdir(parents=True, exist_ok=True)
        (output_root / "comparison.json").write_text(
            json.dumps(comparison, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(json.dumps(comparison, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
