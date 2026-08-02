"""Named entry point for the Set Transformer team-points candidate."""

from __future__ import annotations

import sys

from train_team_points_mlp import main

if __name__ == "__main__":
    if "--architecture" not in sys.argv:
        sys.argv[1:1] = ["--architecture", "set_transformer"]
    raise SystemExit(main())
