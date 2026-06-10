"""Player-level aggregation of action values.

Aggregates xT values at the player level to produce
player_value_metrics.parquet.

Current status: P2. Uses StatsBomb Open Data sample only.
Output must NOT be treated as full league action value data.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from scoutfootball.action_value.schema import InternalAction
from scoutfootball.action_value.xt import action_xt_value, compute_xt

logger = logging.getLogger(__name__)

SOURCE_ATTRIBUTION = "StatsBomb Open Data"
COVERAGE_NOTE = "Sample: StatsBomb Open Data only. NOT full league coverage."


def aggregate_player_xt(
    actions: list[InternalAction],
    xt_grid: np.ndarray | None = None,
) -> pd.DataFrame:
    """Aggregate xT values per player-match.

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
        if not action.player_id:
            continue
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


def _aggregate_action_counts(actions: list[InternalAction]) -> pd.DataFrame:
    """Count action types per player for per-90 computation."""
    if not actions:
        return pd.DataFrame()

    records = []
    for action in actions:
        if not action.player_id:
            continue
        records.append({
            "player_id": action.player_id,
            "team_id": action.team_id,
            "match_id": action.match_id,
            "action_type": action.action_type.value,
            "result": action.result.value,
        })

    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame()

    # Count by action type per player
    type_counts = df.groupby(["player_id", "team_id", "match_id", "action_type"]).size().unstack(fill_value=0)
    type_counts.columns = [f"n_{c}" for c in type_counts.columns]
    type_counts = type_counts.reset_index()

    # Success rates
    df["is_success"] = (df["result"] == "success").astype(int)
    df["is_failure"] = (df["result"] == "failure").astype(int)

    success_agg = df.groupby(["player_id", "team_id", "match_id"]).agg(
        n_total=("action_type", "count"),
        n_success=("is_success", "sum"),
        n_failure=("is_failure", "sum"),
    ).reset_index()

    return type_counts.merge(success_agg, on=["player_id", "team_id", "match_id"], how="outer")


def _aggregate_shot_stats(events_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate shot/xG stats from raw events per player."""
    shots = events_df[events_df["event_type"] == "Shot"].copy()
    if shots.empty:
        return pd.DataFrame(columns=[
            "player_id", "shots", "xG_total", "goals",
        ])

    shots["player_id_str"] = shots["player_id"].apply(
        lambda x: str(int(float(x))) if pd.notna(x) else ""
    )
    shots["is_goal"] = (shots["shot_outcome_name"] == "Goal").astype(int)
    shots["xg"] = shots["shot_statsbomb_xg"].fillna(0.0)

    agg = shots.groupby("player_id_str").agg(
        shots=("event_id", "count"),
        xG_total=("xg", "sum"),
        goals=("is_goal", "sum"),
    ).reset_index().rename(columns={"player_id_str": "player_id"})

    return agg


def _estimate_minutes(actions: list[InternalAction]) -> pd.DataFrame:
    """Estimate minutes played per player from action timestamps.

    Uses max minute per match as a rough proxy (not exact).
    """
    if not actions:
        return pd.DataFrame(columns=["player_id", "match_id", "estimated_minutes"])

    records = []
    for action in actions:
        if not action.player_id:
            continue
        records.append({
            "player_id": action.player_id,
            "team_id": action.team_id,
            "match_id": action.match_id,
            "minute": action.minute,
        })

    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame(columns=["player_id", "match_id", "estimated_minutes"])

    # Max minute per player-match as rough proxy
    minutes = df.groupby(["player_id", "team_id", "match_id"]).agg(
        max_minute=("minute", "max"),
        min_minute=("minute", "min"),
    ).reset_index()
    minutes["estimated_minutes"] = (minutes["max_minute"] - minutes["min_minute"]).clip(lower=1)
    # Add a base of 45 minutes if player has any actions (they played at least a half)
    minutes["estimated_minutes"] = minutes["estimated_minutes"].clip(lower=45)

    return minutes[["player_id", "team_id", "match_id", "estimated_minutes"]]


def build_player_action_value(
    actions: list[InternalAction],
    events_df: pd.DataFrame | None = None,
    player_names: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Build the player_value_metrics DataFrame.

    This is the main entry point for producing the action value artifact.
    Combines xT aggregation with shot/xG stats and per-90 normalization.

    Args:
        actions: List of InternalAction objects.
        events_df: Raw StatsBomb events DataFrame (for xG/shot stats).
        player_names: Optional mapping of player_id -> player_name.
    """
    if not actions:
        logger.warning("No actions provided for player action value aggregation")
        return pd.DataFrame()

    # 1. Compute xT grid and aggregate
    xt_grid = compute_xt(actions)
    xt_agg = aggregate_player_xt(actions, xt_grid)

    if xt_agg.empty:
        logger.warning("No player xT values computed")
        return pd.DataFrame()

    # 2. Aggregate action counts
    action_counts = _aggregate_action_counts(actions)

    # 3. Estimate minutes
    minutes_df = _estimate_minutes(actions)

    # 4. Merge xT + action counts + minutes
    merged = xt_agg.merge(action_counts, on=["player_id", "team_id", "match_id"], how="left")
    merged = merged.merge(minutes_df, on=["player_id", "team_id", "match_id"], how="left")

    # 5. Add shot/xG stats if events_df provided
    if events_df is not None and not events_df.empty:
        shot_stats = _aggregate_shot_stats(events_df)
        merged = merged.merge(shot_stats, on="player_id", how="left")
    else:
        merged["shots"] = 0
        merged["xG_total"] = 0.0
        merged["goals"] = 0

    # 6. Fill NaN for count columns
    count_cols = [c for c in merged.columns if c.startswith("n_")]
    for c in count_cols:
        merged[c] = merged[c].fillna(0).astype(int)
    for c in ["shots", "goals"]:
        if c in merged.columns:
            merged[c] = merged[c].fillna(0).astype(int)
    merged["xG_total"] = merged["xG_total"].fillna(0.0)

    # 7. Compute per-90 stats
    merged["minutes_90"] = merged["estimated_minutes"] / 90.0
    merged["minutes_90"] = merged["minutes_90"].clip(lower=0.1)  # avoid div by zero

    # xT per 90
    merged["xT_per_90"] = merged["total_xt"] / merged["minutes_90"]

    # Shots/xG per 90
    merged["shots_per_90"] = merged["shots"] / merged["minutes_90"]
    merged["xG_per_90"] = merged["xG_total"] / merged["minutes_90"]
    merged["goals_per_90"] = merged["goals"] / merged["minutes_90"]

    # Finishing delta = goals - xG
    merged["finishing_delta"] = merged["goals"] - merged["xG_total"]

    # Pass stats per 90
    if "n_pass" in merged.columns:
        merged["passes_per_90"] = merged["n_pass"] / merged["minutes_90"]
    else:
        merged["passes_per_90"] = 0.0

    # Pass completion rate
    if "n_pass" in merged.columns and "n_success" in merged.columns:
        # Approximate: count successful passes from pass actions
        pass_success = merged.get("n_pass", 0) - merged.get("n_failure", 0).clip(upper=merged.get("n_pass", 0))
        merged["pass_completion_rate"] = np.where(
            merged["n_pass"] > 0,
            (merged["n_pass"] - merged["n_failure"].clip(upper=merged["n_pass"])) / merged["n_pass"],
            0.0,
        )
    else:
        merged["pass_completion_rate"] = 0.0

    # Defensive stats per 90
    for action_col, per90_col in [
        ("n_tackle", "tackles_per_90"),
        ("n_interception", "interceptions_per_90"),
        ("n_block", "blocks_per_90"),
    ]:
        if action_col in merged.columns:
            merged[per90_col] = merged[action_col] / merged["minutes_90"]
        else:
            merged[per90_col] = 0.0

    # Duel win rate (tackle + dribble as proxy)
    n_duel = merged.get("n_tackle", 0) + merged.get("n_dribble", 0)
    n_duel_success = merged.get("n_success", 0)
    merged["duel_win_rate"] = np.where(n_duel > 0, n_duel_success / merged["n_total"], 0.0)
    merged["duels_per_90"] = n_duel / merged["minutes_90"]

    # Carry/dribble per 90
    if "n_carry" in merged.columns:
        merged["progressive_carries_per_90"] = merged["n_carry"] / merged["minutes_90"]
    else:
        merged["progressive_carries_per_90"] = 0.0

    # Touches per 90 (all actions as proxy)
    merged["touches_per_90"] = merged["n_total"] / merged["minutes_90"]

    # Final third touches (actions starting in x > 66.7)
    final_third_actions = [
        a for a in actions if a.player_id and a.start_x > 66.7
    ]
    ft_records = [{"player_id": a.player_id, "match_id": a.match_id} for a in final_third_actions]
    if ft_records:
        ft_df = pd.DataFrame(ft_records)
        ft_counts = ft_df.groupby(["player_id", "match_id"]).size().reset_index(name="final_third_touches")
        merged = merged.merge(ft_counts, on=["player_id", "match_id"], how="left")
        merged["final_third_touches"] = merged["final_third_touches"].fillna(0)
    else:
        merged["final_third_touches"] = 0
    merged["final_third_touches_per_90"] = merged["final_third_touches"] / merged["minutes_90"]

    # Penalty area touches (actions starting in x > 83.3)
    pa_actions = [
        a for a in actions if a.player_id and a.start_x > 83.3
    ]
    pa_records = [{"player_id": a.player_id, "match_id": a.match_id} for a in pa_actions]
    if pa_records:
        pa_df = pd.DataFrame(pa_records)
        pa_counts = pa_df.groupby(["player_id", "match_id"]).size().reset_index(name="penalty_area_touches")
        merged = merged.merge(pa_counts, on=["player_id", "match_id"], how="left")
        merged["penalty_area_touches"] = merged["penalty_area_touches"].fillna(0)
    else:
        merged["penalty_area_touches"] = 0
    merged["penalty_area_touches_per_90"] = merged["penalty_area_touches"] / merged["minutes_90"]

    # Forward pass rate (passes ending in higher x than start)
    forward_passes = [
        a for a in actions
        if a.player_id and a.action_type.value == "pass" and a.end_x > a.start_x
    ]
    fp_records = [{"player_id": a.player_id, "match_id": a.match_id} for a in forward_passes]
    if fp_records:
        fp_df = pd.DataFrame(fp_records)
        fp_counts = fp_df.groupby(["player_id", "match_id"]).size().reset_index(name="forward_passes")
        merged = merged.merge(fp_counts, on=["player_id", "match_id"], how="left")
        merged["forward_passes"] = merged["forward_passes"].fillna(0)
    else:
        merged["forward_passes"] = 0
    merged["forward_pass_rate"] = np.where(
        merged.get("n_pass", 0) > 0,
        merged["forward_passes"] / merged["n_pass"],
        0.0,
    )

    # 8. Add player names
    if player_names:
        merged["player_name"] = merged["player_id"].map(player_names).fillna("")
    else:
        merged["player_name"] = ""

    # 9. Composite score (weighted sum of normalized metrics)
    # Simple version: weighted xT + xG + goals
    if merged["total_xt"].std() > 0:
        xt_norm = (merged["total_xt"] - merged["total_xt"].mean()) / merged["total_xt"].std()
    else:
        xt_norm = pd.Series(0.0, index=merged.index)
    if merged["xG_total"].std() > 0:
        xg_norm = (merged["xG_total"] - merged["xG_total"].mean()) / merged["xG_total"].std()
    else:
        xg_norm = pd.Series(0.0, index=merged.index)
    if merged["goals"].std() > 0:
        goals_norm = (merged["goals"] - merged["goals"].mean()) / merged["goals"].std()
    else:
        goals_norm = pd.Series(0.0, index=merged.index)

    merged["composite_score"] = (
        0.4 * xt_norm + 0.3 * xg_norm + 0.3 * goals_norm
    )
    # Scale to 0-100 range
    if merged["composite_score"].std() > 0:
        merged["composite_score"] = (
            (merged["composite_score"] - merged["composite_score"].min())
            / (merged["composite_score"].max() - merged["composite_score"].min())
            * 100
        )

    # 10. Add metadata columns
    merged["source"] = SOURCE_ATTRIBUTION
    merged["source_attribution"] = SOURCE_ATTRIBUTION
    merged["coverage_note"] = COVERAGE_NOTE
    merged["n_matches"] = 1  # each row is per player-match

    # 11. Select final columns matching existing schema
    output_cols = [
        "player_id", "player_name", "team_id", "match_id",
        "estimated_minutes",
        "shots", "shots_per_90", "xG_total", "xG_per_90",
        "goals", "goals_per_90", "finishing_delta",
        "passes_per_90", "pass_completion_rate", "forward_pass_rate",
        "total_xt", "xT_per_90",
        "tackles_per_90", "interceptions_per_90", "blocks_per_90",
        "duel_win_rate", "duels_per_90",
        "touches_per_90", "progressive_carries_per_90",
        "final_third_touches_per_90", "penalty_area_touches_per_90",
        "composite_score",
        "source", "source_attribution", "coverage_note", "n_matches",
    ]
    # Only include columns that exist
    final_cols = [c for c in output_cols if c in merged.columns]
    result = merged[final_cols].copy()

    # Aggregate across matches for player-level summary
    player_agg = _aggregate_to_player_level(result)

    logger.info("Built player action value: %d player-matches, %d unique players", len(result), len(player_agg))
    return player_agg


def _aggregate_to_player_level(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate player-match rows to player-level summary."""
    if df.empty:
        return df

    agg_dict = {
        "estimated_minutes": "sum",
        "shots": "sum",
        "xG_total": "sum",
        "goals": "sum",
        "total_xt": "sum",
        "n_matches": "sum",
    }

    # Per-90 columns: recompute from totals
    player = df.groupby(["player_id", "player_name", "team_id"]).agg(agg_dict).reset_index()

    minutes_90 = (player["estimated_minutes"] / 90.0).clip(lower=0.1)
    player["shots_per_90"] = player["shots"] / minutes_90
    player["xG_per_90"] = player["xG_total"] / minutes_90
    player["goals_per_90"] = player["goals"] / minutes_90
    player["finishing_delta"] = player["goals"] - player["xG_total"]
    player["xT_per_90"] = player["total_xt"] / minutes_90

    # Average per-90 stats across matches (weighted by minutes)
    per90_cols = [
        "passes_per_90", "pass_completion_rate", "forward_pass_rate",
        "tackles_per_90", "interceptions_per_90", "blocks_per_90",
        "duel_win_rate", "duels_per_90",
        "touches_per_90", "progressive_carries_per_90",
        "final_third_touches_per_90", "penalty_area_touches_per_90",
    ]
    for col in per90_cols:
        if col in df.columns:
            # Weighted average by estimated_minutes
            weights = df["estimated_minutes"].fillna(0)
            values = df[col].fillna(0)
            total_weight = df.groupby(["player_id", "team_id"])["estimated_minutes"].transform("sum")
            df["_weighted"] = values * weights
            weighted_sum = df.groupby(["player_id", "team_id"])["_weighted"].sum().reset_index()
            total_w = df.groupby(["player_id", "team_id"])["estimated_minutes"].sum().reset_index()
            merged = weighted_sum.merge(total_w, on=["player_id", "team_id"])
            merged[col] = np.where(merged["estimated_minutes"] > 0, merged["_weighted"] / merged["estimated_minutes"], 0.0)
            player = player.merge(merged[["player_id", "team_id", col]], on=["player_id", "team_id"], how="left")
            df.drop(columns=["_weighted"], inplace=True, errors="ignore")

    # Recompute composite score at player level
    if player["total_xt"].std() > 0:
        xt_norm = (player["total_xt"] - player["total_xt"].mean()) / player["total_xt"].std()
    else:
        xt_norm = pd.Series(0.0, index=player.index)
    if player["xG_total"].std() > 0:
        xg_norm = (player["xG_total"] - player["xG_total"].mean()) / player["xG_total"].std()
    else:
        xg_norm = pd.Series(0.0, index=player.index)
    if player["goals"].std() > 0:
        goals_norm = (player["goals"] - player["goals"].mean()) / player["goals"].std()
    else:
        goals_norm = pd.Series(0.0, index=player.index)

    player["composite_score"] = 0.4 * xt_norm + 0.3 * xg_norm + 0.3 * goals_norm
    if player["composite_score"].std() > 0:
        player["composite_score"] = (
            (player["composite_score"] - player["composite_score"].min())
            / (player["composite_score"].max() - player["composite_score"].min())
            * 100
        )

    player["source"] = SOURCE_ATTRIBUTION
    player["source_attribution"] = SOURCE_ATTRIBUTION
    player["coverage_note"] = COVERAGE_NOTE

    # Select final output columns
    output_cols = [
        "player_id", "player_name", "team_id",
        "estimated_minutes", "n_matches",
        "shots", "shots_per_90", "xG_total", "xG_per_90",
        "goals", "goals_per_90", "finishing_delta",
        "passes_per_90", "pass_completion_rate", "forward_pass_rate",
        "total_xt", "xT_per_90",
        "tackles_per_90", "interceptions_per_90", "blocks_per_90",
        "duel_win_rate", "duels_per_90",
        "touches_per_90", "progressive_carries_per_90",
        "final_third_touches_per_90", "penalty_area_touches_per_90",
        "composite_score", "source", "source_attribution", "coverage_note",
    ]
    final_cols = [c for c in output_cols if c in player.columns]
    result = player[final_cols].sort_values("composite_score", ascending=False).reset_index(drop=True)

    return result


def save_player_action_value(df: pd.DataFrame, output_path: Path) -> None:
    """Save player_value_metrics to Parquet."""
    if df.empty:
        logger.warning("Empty DataFrame, not saving")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    logger.info("Saved player_value_metrics to %s (%d rows)", output_path, len(df))
