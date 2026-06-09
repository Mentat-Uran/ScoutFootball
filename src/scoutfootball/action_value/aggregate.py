"""Player-level aggregation of action values.

Aggregates xT values at the player level to produce
player_action_value.parquet.

Current status: P2 skeleton.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from scoutfootball.action_value.schema import InternalAction
from scoutfootball.action_value.xt import action_xt_value, compute_xt

logger = logging.getLogger(__name__)


def aggregate_player_xt(
    actions: list[InternalAction],
    xt_grid=None,
) -> pd.DataFrame:
    """Aggregate xT values per player.

    Returns a DataFrame with columns:
        player_id, team_id, match_id, n_actions, total_xt, mean_xt, max_xt
    """
    if not actions:
        return pd.DataFrame(columns=[
            "player_id", "team_id", "match_id",
            "n_actions", "total_xt", "mean_xt", "max_xt",
        ])

    if xt_grid is None:
        xt_grid = compute_xt(actions)

    records = []
    for action in actions:
        xt_val = action_xt_value(action, xt_grid)
        records.append({
            "player_id": action.player_id,
            "team_id": action.team_id,
            "match_id": action.match_id,
            "action_type": action.action_type.value,
            "xt_value": xt_val,
        })

    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame(columns=[
            "player_id", "team_id", "match_id",
            "n_actions", "total_xt", "mean_xt", "max_xt",
        ])

    agg = df.groupby(["player_id", "team_id", "match_id"]).agg(
        n_actions=("xt_value", "count"),
        total_xt=("xt_value", "sum"),
        mean_xt=("xt_value", "mean"),
        max_xt=("xt_value", "max"),
    ).reset_index()

    return agg.sort_values("total_xt", ascending=False).reset_index(drop=True)


def build_player_action_value(actions: list[InternalAction]) -> pd.DataFrame:
    """Build the player_action_value DataFrame.

    This is the main entry point for producing the action value artifact.
    """
    if not actions:
        logger.warning("No actions provided for player action value aggregation")
        return pd.DataFrame()

    xt_grid = compute_xt(actions)
    df = aggregate_player_xt(actions, xt_grid)

    logger.info("Built player action value: %d players, %d actions", len(df), len(actions))
    return df


def save_player_action_value(df: pd.DataFrame, output_path: Path) -> None:
    """Save player_action_value to Parquet."""
    if df.empty:
        logger.warning("Empty DataFrame, not saving")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    logger.info("Saved player_action_value to %s (%d rows)", output_path, len(df))
