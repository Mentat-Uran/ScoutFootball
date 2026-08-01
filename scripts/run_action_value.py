"""Run the action value pipeline: StatsBomb events -> InternalActions -> xT -> player metrics.

Usage:
    python scripts/run_action_value.py
    python scripts/run_action_value.py --events-path data/raw/statsbomb_open/events_all.parquet
    python scripts/run_action_value.py \
        --output-path data/gold/feature_store/player_value_metrics.parquet

This pipeline is idempotent: running it multiple times produces the same output
given the same input data.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))

from scoutfootball.action_value.aggregate import (  # noqa: E402
    build_player_action_value,
    save_player_action_value,
)
from scoutfootball.action_value.spadl_adapter import convert_all_events  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_EVENTS_PATH = project_root / "data" / "raw" / "statsbomb_open" / "events_all.parquet"
DEFAULT_OUTPUT_PATH = (
    project_root / "data" / "gold" / "feature_store"
    / "player_value_metrics.parquet"
)


def run_action_value_pipeline(
    events_path: Path = DEFAULT_EVENTS_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> pd.DataFrame:
    """Run the full action value pipeline.

    Steps:
        1. Load StatsBomb events from Parquet
        2. Convert to InternalActions using SPADL adapter
        3. Compute xT grid from the actions
        4. Aggregate player-level xT values + shot/xG stats
        5. Save to player_value_metrics.parquet

    Returns:
        The player_value_metrics DataFrame.
    """
    logger.info("=== Action Value Pipeline ===")
    logger.info("Events path: %s", events_path)
    logger.info("Output path: %s", output_path)

    # Step 1: Load events
    if not events_path.exists():
        logger.error("Events file not found: %s", events_path)
        sys.exit(1)

    events_df = pd.read_parquet(events_path)
    logger.info("Loaded %d events from %s", len(events_df), events_path)

    # Step 2: Convert to InternalActions
    actions = convert_all_events(events_path)
    logger.info("Converted to %d internal actions", len(actions))

    if not actions:
        logger.error("No actions converted from events. Check event_type mapping.")
        sys.exit(1)

    # Step 2b: Build player name mapping from events
    player_names = {}
    if "player_id" in events_df.columns and "player_name" in events_df.columns:
        name_map = (
            events_df
            .dropna(subset=["player_id", "player_name"])
            .drop_duplicates("player_id")
        )
        for _, row in name_map.iterrows():
            pid = str(int(float(row["player_id"])))
            player_names[pid] = row["player_name"]
    logger.info("Built player name mapping: %d players", len(player_names))

    # Step 3-4: Compute xT and aggregate
    result = build_player_action_value(
        actions=actions,
        events_df=events_df,
        player_names=player_names,
    )

    if result.empty:
        logger.error("No player action values computed")
        sys.exit(1)

    # Step 5: Save
    save_player_action_value(result, output_path)

    # Summary
    logger.info("=== Pipeline Complete ===")
    logger.info("Output: %d players, %d columns", len(result), len(result.columns))
    logger.info("Top 5 players by composite score:")
    for _, row in result.head(5).iterrows():
        name = row.get("player_name", row.get("player_id", "?"))
        score = row.get("composite_score", 0)
        xt = row.get("total_xt", 0)
        logger.info("  %s: composite=%.1f, total_xT=%.4f", name, score, xt)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run action value pipeline")
    parser.add_argument(
        "--events-path",
        type=Path,
        default=DEFAULT_EVENTS_PATH,
        help="Path to StatsBomb events Parquet file",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path to output player_value_metrics Parquet file",
    )
    args = parser.parse_args()
    run_action_value_pipeline(args.events_path, args.output_path)


if __name__ == "__main__":
    main()
