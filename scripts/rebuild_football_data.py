#!/usr/bin/env python3
"""Rebuild Football-Data combined_results.parquet from all cached CSVs.

Usage:
    PYTHONPATH=src uv run python scripts/rebuild_football_data.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from scoutlab.adapters.football_data import rebuild_combined_results
from scoutlab.config import PlatformSettings


def main() -> int:
    settings = PlatformSettings.from_root()
    data_dir = settings.raw_root / "football_data"

    if not data_dir.exists():
        print(f"Error: Football-Data directory not found: {data_dir}")
        return 1

    print("Rebuilding combined_results.parquet from all cached CSVs...")
    print(f"Data directory: {data_dir}")

    metadata = rebuild_combined_results(data_dir)

    print("\nRebuild complete:")
    print(f"  Raw CSV total rows:  {metadata['total_rows']}")
    print(f"  Parquet rows:        {metadata['parquet_rows']}")
    print(f"  League-seasons:      {len(metadata['league_seasons'])}")
    print(f"  Input hash:          {metadata['input_hash'][:16]}...")
    print(f"  Rebuild time:        {metadata['rebuild_time']}")

    league_seasons = metadata["league_seasons"]
    if league_seasons:
        print(f"\nLeague-season coverage ({len(league_seasons)}):")
        for ls in league_seasons:
            print(f"  {ls}")

    # Save metadata alongside the parquet
    meta_path = data_dir / "combined_results_rebuild_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"\nMetadata saved to: {meta_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
