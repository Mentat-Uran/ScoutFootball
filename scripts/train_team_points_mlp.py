"""Run the candidate-only team-points MLP on local optimizer inputs.

This is an experiment runner, not a promotion command.  It writes only to a
new local run directory and never changes the active rating artifact.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from optimizer.data import load_data  # noqa: E402

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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train a candidate player MLP against team-season points proxy"
    )
    parser.add_argument("--data-dir", type=Path, default=REPO_ROOT / "data")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--epochs", type=int, default=180)
    parser.add_argument("--hidden", type=_parse_hidden, default=(96, 48))
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--weight-decay", type=float, default=0.0001)
    parser.add_argument("--patience", type=int, default=25)
    parser.add_argument("--min-team-players", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    data_dir = args.data_dir.resolve()
    loaded = load_data(data_dir)
    frame, team_points = loaded[:2]
    config = TeamPointsMLPConfig(
        hidden_layer_sizes=args.hidden,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        patience=args.patience,
        min_team_players=args.min_team_players,
        seed=args.seed,
    )
    result = train_team_points_mlp(frame, team_points, config=config)
    run_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-team-points-mlp"
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir is not None
        else data_dir / "models" / "runs" / run_id
    )
    write_team_points_mlp_artifacts(result, output_dir, config=config, input_frame=frame)
    print(result.status)
    print(f"candidate_run={output_dir}")
    print(json.dumps(result.metrics, indent=2, ensure_ascii=False))
    return 0 if result.trained else 1


if __name__ == "__main__":
    raise SystemExit(main())
