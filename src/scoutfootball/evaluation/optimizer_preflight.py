"""Read-only runtime and source checks for the optional rating optimizer."""

from __future__ import annotations

from importlib import metadata
from pathlib import Path
from typing import Any

import pandas as pd

REQUIRED_ARTIFACTS = {
    "fbref_standard": Path("raw/fbref/player_stats_big5_3seasons.parquet"),
    "football_data_results": Path("raw/football_data/combined_results.parquet"),
}
OPTIONAL_ARTIFACTS = {
    "fbref_misc": Path("raw/fbref/player_misc_5seasons.parquet"),
    "fbref_shooting": Path("raw/fbref/player_shooting_5seasons.parquet"),
    "understat": Path("raw/understat/players_10seasons.parquet"),
}


def optimizer_preflight(data_dir: Path) -> dict[str, Any]:
    """Inspect optimizer prerequisites without training or changing artifacts."""
    checks: list[dict[str, Any]] = []
    for required, artifacts in ((True, REQUIRED_ARTIFACTS), (False, OPTIONAL_ARTIFACTS)):
        for source, relative_path in artifacts.items():
            path = data_dir / relative_path
            check: dict[str, Any] = {"source": source, "required": required, "path": str(path)}
            if not path.exists():
                check["status"] = "missing"
            else:
                try:
                    check["rows"] = int(len(pd.read_parquet(path)))
                    check["status"] = "readable"
                except Exception as exc:
                    check.update(status="unreadable", error_type=type(exc).__name__, error=str(exc))
            checks.append(check)

    try:
        import torch

        torch_check = {
            "status": "available",
            "version": torch.__version__,
            "cuda": bool(torch.cuda.is_available()),
        }
    except Exception as exc:
        torch_check = {"status": "unavailable", "error_type": type(exc).__name__, "error": str(exc)}

    required_ready = all(check["status"] == "readable" for check in checks if check["required"])
    return {
        "schema": "scoutfootball.optimizer-preflight",
        "version": "1.0.0",
        "data_dir": str(data_dir),
        "runtime": {
            "pandas": pd.__version__,
            "pyarrow": metadata.version("pyarrow"),
            "torch": torch_check,
        },
        "artifacts": checks,
        "ready": bool(required_ready and torch_check["status"] == "available"),
        "install_hint": "uv sync --extra optimizer",
    }
