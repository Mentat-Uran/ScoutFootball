# optimizer/data.py — 数据加载、校准、评估与持久化
# 从 optimize_ratings_gpu.py 提取 (lines 787-1918)

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from scipy.stats import pearsonr, spearmanr

from .constants import (
    POS_TO_IDX,
    SeasonSplit,
    TeamPointsCalibrator,
    map_position_detailed,
    normalize_team_name,
    refine_role_positions,
)

# ── 数据加载 ──────────────────────────────────────────────────────────────


def summarize_optimizer_data_coverage(frame: pd.DataFrame) -> dict:
    """Return source and field-observability coverage for an optimizer input.

    Season aggregates can be useful historical proxies, but they must not be
    represented as having match-level fields that their source does not expose.
    The summary is persisted with each model run so a later score comparison can
    distinguish an FBref-backed run from one that includes Understat history.
    """
    artifact_statuses = list(frame.attrs.get("optimizer_artifact_statuses", []))
    if frame.empty:
        return {
            "rows": 0,
            "seasons": [],
            "sources": [],
            "starts_observed_rows": 0,
            "artifact_statuses": artifact_statuses,
        }

    work = frame.copy()
    if "source_name" not in work.columns:
        work["source_name"] = "unknown"
    if "data_granularity" not in work.columns:
        work["data_granularity"] = "unknown"
    if "starts_observed" not in work.columns:
        work["starts_observed"] = True

    starts_observed = work["starts_observed"].fillna(False).astype(bool)
    sources = (
        work.assign(_starts_observed=starts_observed)
        .groupby(["source_name", "data_granularity"], dropna=False)
        .agg(
            rows=("source_name", "size"),
            seasons=("season", lambda values: sorted({str(value) for value in values})),
            starts_observed_rows=("_starts_observed", "sum"),
        )
        .reset_index()
        .sort_values(["source_name", "data_granularity"])
    )
    return {
        "rows": int(len(work)),
        "seasons": sorted({str(value) for value in work.get("season", pd.Series(dtype=str))}),
        "starts_observed_rows": int(starts_observed.sum()),
        "artifact_statuses": artifact_statuses,
        "sources": [
            {
                "source_name": str(row["source_name"]),
                "data_granularity": str(row["data_granularity"]),
                "rows": int(row["rows"]),
                "seasons": list(row["seasons"]),
                "starts_observed_rows": int(row["starts_observed_rows"]),
            }
            for _, row in sources.iterrows()
        ],
    }


def _read_optional_parquet(
    path: Path,
    *,
    source: str,
    artifact_statuses: list[dict],
) -> pd.DataFrame | None:
    """Read an optional optimizer source without hiding its failure state."""
    if not path.exists():
        artifact_statuses.append({"source": source, "status": "missing", "path": str(path)})
        return None
    try:
        frame = pd.read_parquet(path)
    except Exception as exc:
        artifact_statuses.append(
            {
                "source": source,
                "status": "unreadable",
                "path": str(path),
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        )
        print(f"  Optional {source} unavailable ({type(exc).__name__}): {exc}")
        return None
    artifact_statuses.append({"source": source, "status": "loaded", "path": str(path)})
    return frame


def load_data(data_dir: Path):
    """加载 FBref 球员数据 (standard + misc + shooting) + Football-Data 球队积分。"""
    artifact_statuses: list[dict] = []
    standard_path = data_dir / "raw" / "fbref" / "player_stats_big5_3seasons.parquet"
    fbref = pd.read_parquet(standard_path)
    artifact_statuses.append(
        {"source": "fbref_standard", "status": "loaded", "path": str(standard_path)},
    )

    goals = fbref[("Performance", "Gls")].values.astype(np.float32)
    assists_col = fbref[("Performance", "Ast")].values.astype(np.float32)
    pk = fbref[("Performance", "PK")].values.astype(np.float32)
    minutes = fbref[("Playing Time", "Min")].values.astype(np.float32)
    starts = fbref[("Playing Time", "Starts")].values.astype(np.float32)
    matches = fbref[("Playing Time", "MP")].values.astype(np.float32)
    positions = fbref[("pos", "")].values
    leagues_raw = fbref.index.get_level_values("league")
    # Bundesliga rows have NaN league in FBref; fill before str conversion
    leagues_raw = leagues_raw.fillna("GER-Bundesliga").astype(str).values
    seasons = fbref.index.get_level_values("season").values
    teams = fbref.index.get_level_values("team").values
    players = fbref.index.get_level_values("player").values

    # Normalize league names
    league_name_map = {
        "ENG-Premier League": "Premier League",
        "ESP-La Liga": "La Liga",
        "FRA-Ligue 1": "Ligue 1",
        "ITA-Serie A": "Serie A",
        "GER-Bundesliga": "Bundesliga",
    }
    leagues = np.array([league_name_map.get(league, league) for league in leagues_raw])

    npg = goals - pk
    safe_min = np.maximum(minutes, 1.0)
    npg_p90 = npg / safe_min * 90
    assists_p90 = assists_col / safe_min * 90
    g_a_volume = npg + assists_col

    pos_details = [map_position_detailed(p) for p in positions]
    sub_pos = np.array([d[0] for d in pos_details])
    pos_idx = np.array([POS_TO_IDX.get(p, 4) for p in sub_pos])
    position_source = [d[1] for d in pos_details]
    position_confidence = [d[2] for d in pos_details]

    # Build base DataFrame
    df = pd.DataFrame({
        "player": players, "team": teams, "league": leagues, "season": seasons,
        "source_position": positions,
        "sub_position": sub_pos, "pos_idx": pos_idx,
        "position_source": position_source, "position_confidence": position_confidence,
        "matches": matches, "starts": starts, "minutes": minutes,
        "npg_p90": npg_p90, "assists_p90": assists_p90, "g_a_volume": g_a_volume,
    })
    df["source_name"] = "fbref"
    df["data_granularity"] = "season_proxy"
    df["starts_observed"] = True

    # Normalize team names to Football-Data canonical form
    df["team"] = df["team"].apply(normalize_team_name)

    # Load and merge misc stats (tackles, interceptions, fouls, crosses)
    misc_path = data_dir / "raw" / "fbref" / "player_misc_5seasons.parquet"
    if not misc_path.exists():
        misc_path = data_dir / "raw" / "fbref" / "player_misc_3seasons.parquet"
    misc = _read_optional_parquet(
        misc_path,
        source="fbref_misc",
        artifact_statuses=artifact_statuses,
    )
    if misc is not None:
        misc_idx = misc.index.to_frame(index=False)
        # Normalize league names in misc index
        misc_league_norm = misc_idx["league"].map(league_name_map).fillna(misc_idx["league"])
        misc_data = pd.DataFrame({
            "merge_key": (
                misc_idx["player"].astype(str) + "|" +
                misc_league_norm.astype(str) + "|" +
                misc_idx["season"].astype(str)
            ),
            "tackles_won": pd.to_numeric(misc[("Performance", "TklW")], errors="coerce").values,
            "interceptions": pd.to_numeric(misc[("Performance", "Int")], errors="coerce").values,
            "fouls": pd.to_numeric(misc[("Performance", "Fls")], errors="coerce").values,
            "fouls_drawn": pd.to_numeric(misc[("Performance", "Fld")], errors="coerce").values,
            "crosses": pd.to_numeric(misc[("Performance", "Crs")], errors="coerce").values,
            "yellow_cards": pd.to_numeric(misc[("Performance", "CrdY")], errors="coerce").values,
        })
        misc_data = misc_data.drop_duplicates(subset=["merge_key"], keep="first")
        df["merge_key"] = (
            df["player"].astype(str)
            + "|"
            + df["league"].astype(str)
            + "|"
            + df["season"].astype(str)
        )
        df = df.merge(misc_data, on="merge_key", how="left")
        df = df.drop(columns=["merge_key"])
        print(
            "  Misc stats merged: "
            f"tackles={df['tackles_won'].notna().sum()}, "
            f"interceptions={df['interceptions'].notna().sum()}"
        )
    else:
        df["tackles_won"] = np.nan
        df["interceptions"] = np.nan
        df["fouls"] = np.nan
        df["fouls_drawn"] = np.nan
        df["crosses"] = np.nan
        df["yellow_cards"] = np.nan

    # Load and merge shooting stats
    shoot_path = data_dir / "raw" / "fbref" / "player_shooting_5seasons.parquet"
    if not shoot_path.exists():
        shoot_path = data_dir / "raw" / "fbref" / "player_shooting_3seasons.parquet"
    shooting = _read_optional_parquet(
        shoot_path,
        source="fbref_shooting",
        artifact_statuses=artifact_statuses,
    )
    if shooting is not None:
        shoot_idx = shooting.index.to_frame(index=False)
        shoot_league_norm = shoot_idx["league"].map(league_name_map).fillna(shoot_idx["league"])
        shoot_data = pd.DataFrame({
            "merge_key": (
                shoot_idx["player"].astype(str) + "|" +
                shoot_league_norm.astype(str) + "|" +
                shoot_idx["season"].astype(str)
            ),
            "shots": pd.to_numeric(shooting[("Standard", "Sh")], errors="coerce").values,
            "shots_on_target": pd.to_numeric(shooting[("Standard", "SoT")], errors="coerce").values,
            "shot_accuracy": pd.to_numeric(shooting[("Standard", "SoT%")], errors="coerce").values,
        })
        shoot_data = shoot_data.drop_duplicates(subset=["merge_key"], keep="first")
        df["merge_key"] = (
            df["player"].astype(str)
            + "|"
            + df["league"].astype(str)
            + "|"
            + df["season"].astype(str)
        )
        df = df.merge(shoot_data, on="merge_key", how="left")
        df = df.drop(columns=["merge_key"])
        print(
            "  Shooting stats merged: "
            f"shots={df['shots'].notna().sum()}, "
            f"sot={df['shots_on_target'].notna().sum()}"
        )
    else:
        df["shots"] = np.nan
        df["shots_on_target"] = np.nan
        df["shot_accuracy"] = np.nan

    # Compute per-90 defensive/possession metrics (after merge, safe_min from df)
    safe_min_df = df["minutes"].values.astype(np.float32)
    safe_min_df = np.maximum(safe_min_df, 1.0)
    df["tackles_p90"] = df["tackles_won"].fillna(0) / safe_min_df * 90
    df["interceptions_p90"] = df["interceptions"].fillna(0) / safe_min_df * 90
    df["crosses_p90"] = df["crosses"].fillna(0) / safe_min_df * 90
    df["fouls_drawn_p90"] = df["fouls_drawn"].fillna(0) / safe_min_df * 90
    df["fouls_p90"] = df["fouls"].fillna(0) / safe_min_df * 90
    df["shots_p90"] = df["shots"].fillna(0) / safe_min_df * 90
    df["sot_p90"] = df["shots_on_target"].fillna(0) / safe_min_df * 90

    # Defense composite (enhanced):
    #   tackles_won_p90 * 0.35  — primary defensive action
    #   interceptions_p90 * 0.30 — reading the game
    #   fouls_p90 * -0.10        — discipline penalty (fewer fouls = better)
    #   fouls_drawn_p90 * 0.10   — physical engagement proxy
    #   crosses_p90 * 0.15       — for FB/FB, defensive work rate includes crossing
    # Only use real data where available; missing tackles/interceptions → NaN
    has_defense_data = df["tackles_won"].notna() & df["interceptions"].notna()
    df["defense_composite"] = np.where(
        has_defense_data,
        (
            df["tackles_p90"] * 0.35
            + df["interceptions_p90"] * 0.30
            - df["fouls_p90"] * 0.10
            + df["fouls_drawn_p90"] * 0.10
            + df["crosses_p90"] * 0.15
        ),
        np.nan,
    )
    # Possession composite: crosses + fouls drawn (proxy for ball involvement)
    df["possession_composite"] = np.where(
        has_defense_data,
        df["crosses_p90"] * 0.5 + df["fouls_drawn_p90"] * 0.5,
        np.nan,
    )

    # Cross-season trend: compute per-player improvement across seasons.
    # The trend feature must be causal for historical rows; using a player's
    # latest season for all rows leaks future performance into old seasons.
    # Sort by player and season for trend computation
    df = df.sort_values(["player", "season"])
    df["season_rank"] = df.groupby("player").cumcount()
    past_avg = (
        df.groupby("player")[["npg_p90", "defense_composite", "possession_composite"]]
        .expanding()
        .mean()
        .groupby(level=0)
        .shift(1)
        .reset_index(level=0, drop=True)
    )
    df["npg_trend"] = (df["npg_p90"] - past_avg["npg_p90"]).fillna(0.0)
    df["def_trend"] = (df["defense_composite"] - past_avg["defense_composite"]).fillna(0.0)
    df["pos_trend"] = (df["possession_composite"] - past_avg["possession_composite"]).fillna(0.0)

    # Experience factor: seasons observed up to this row, not future career length.
    df["experience_factor"] = np.clip((df["season_rank"] + 1) / 3, 0.5, 1.0)

    df = df.sort_values("minutes", ascending=False)
    df = df.drop_duplicates(subset=["player", "season", "league"], keep="first")

    # Load Understat data for additional seasons
    understat_path = data_dir / "raw" / "understat" / "players_10seasons.parquet"
    understat = _read_optional_parquet(
        understat_path,
        source="understat",
        artifact_statuses=artifact_statuses,
    )
    if understat is not None:
        print("  加载 Understat 数据...")
        
        # Normalize league names
        understat_league_map = {
            "EPL": "Premier League",
            "La_Liga": "La Liga",
            "Bundesliga": "Bundesliga",
            "Serie_A": "Serie A",
            "Ligue_1": "Ligue 1",
        }
        understat["league"] = understat["league"].map(understat_league_map)
        understat = understat[understat["league"].notna()].copy()
        
        # Convert numeric columns
        for col in ["games", "time", "goals", "xG", "assists", "xA", "npxG", "shots", "key_passes"]:
            understat[col] = pd.to_numeric(understat[col], errors="coerce")
        
        # Normalize season format: "201617" -> "1617"
        def _normalize_season(s):
            s = str(s)
            if len(s) == 6 and s.startswith("20"):
                return s[2:]  # "201617" -> "1617"
            return s
        
        understat["season"] = understat["season"].apply(_normalize_season)
        
        # Calculate per-90 metrics
        safe_min_us = np.maximum(understat["time"].values.astype(np.float32), 1.0)
        understat["minutes"] = understat["time"].values.astype(np.float32)
        understat["matches"] = understat["games"].values.astype(np.float32)
        # Understat's aggregate snapshot has appearances but no starts field.
        # Preserve an explicit sentinel and make the scorer ignore it rather
        # than pretending every appearance was a start.
        understat["starts"] = 0.0
        understat["starts_observed"] = False
        understat["source_name"] = "understat"
        understat["data_granularity"] = "season_proxy"
        
        # Position mapping
        understat_pos_details = understat["position"].apply(map_position_detailed)
        understat["sub_position"] = understat_pos_details.apply(lambda x: x[0])
        understat["pos_idx"] = understat["sub_position"].map(POS_TO_IDX).fillna(4).astype(int)
        understat["position_source"] = understat_pos_details.apply(lambda x: x[1])
        understat["position_confidence"] = understat_pos_details.apply(lambda x: x[2])
        
        # Per-90 metrics
        understat["npg_p90"] = (
            (understat["goals"].values - understat["goals"].values * 0.1)
            / safe_min_us
            * 90
        )
        understat["assists_p90"] = understat["assists"].values / safe_min_us * 90
        understat["g_a_volume"] = understat["goals"].values + understat["assists"].values
        
        # Select and rename columns
        understat_df = understat[[
            "player_name", "team_title", "league", "season", "position",
            "sub_position", "pos_idx", "position_source", "position_confidence",
            "matches", "starts", "starts_observed", "minutes",
            "source_name", "data_granularity",
            "npg_p90", "assists_p90", "g_a_volume",
        ]].copy()
        understat_df = understat_df.rename(
            columns={
                "player_name": "player",
                "team_title": "team",
                "position": "source_position",
            },
        )

        # Normalize Understat team names to Football-Data canonical form
        understat_df["team"] = understat_df["team"].apply(normalize_team_name)
        
        # Add missing columns with NaN (not 0) for defense/possession stats.
        # NaN rows are excluded from percentile ranking, so they get the
        # position median (50th percentile) instead of being forced to 0.
        for col in [
            "tackles_won",
            "interceptions",
            "fouls",
            "fouls_drawn",
            "crosses",
            "yellow_cards",
            "shots",
            "shots_on_target",
            "shot_accuracy",
            "tackles_p90",
            "interceptions_p90",
            "crosses_p90",
            "fouls_drawn_p90",
            "fouls_p90",
            "shots_p90",
            "sot_p90",
            "defense_composite",
            "possession_composite",
        ]:
            understat_df[col] = np.nan
        
        # Find seasons in Understat but not in FBref
        fbref_seasons = set(df["season"].unique())
        understat_only = understat_df[~understat_df["season"].isin(fbref_seasons)]
        print(f"    Understat 独有赛季: {sorted(understat_only['season'].unique())}")
        
        # Combine: FBref takes priority for overlapping seasons
        df = pd.concat([df, understat_only], ignore_index=True, sort=False)
        print(f"    合并后: {len(df)} 行")
        
        # Recompute per-90 and composite metrics for all rows.
        # Understat rows have NaN defense/possession — keep NaN so percentile
        # ranking assigns them the position median instead of 0.
        safe_min_all = np.maximum(df["minutes"].values.astype(np.float32), 1.0)
        df["tackles_p90"] = df["tackles_won"].fillna(0) / safe_min_all * 90
        df["interceptions_p90"] = df["interceptions"].fillna(0) / safe_min_all * 90
        df["crosses_p90"] = df["crosses"].fillna(0) / safe_min_all * 90
        df["fouls_drawn_p90"] = df["fouls_drawn"].fillna(0) / safe_min_all * 90
        df["fouls_p90"] = df["fouls"].fillna(0) / safe_min_all * 90
        # defense/possession composite: NaN where underlying stats are NaN
        has_defense = df["tackles_won"].notna() & df["interceptions"].notna()
        df["defense_composite"] = np.where(
            has_defense,
            (
                df["tackles_p90"] * 0.35
                + df["interceptions_p90"] * 0.30
                - df["fouls_p90"] * 0.10
                + df["fouls_drawn_p90"] * 0.10
                + df["crosses_p90"] * 0.15
            ),
            np.nan,
        )
        has_possession = df["crosses"].notna() & df["fouls_drawn"].notna()
        df["possession_composite"] = np.where(
            has_possession,
            df["crosses_p90"] * 0.5 + df["fouls_drawn_p90"] * 0.5,
            np.nan,
        )
        
        # Recompute trend and experience for all rows
        df = df.sort_values(["player", "season"])
        df["season_rank"] = df.groupby("player").cumcount()
        df["experience_factor"] = np.clip((df["season_rank"] + 1) / 3, 0.5, 1.0)
        
        # Recompute trends
        past_avg = (
            df.groupby("player")[["npg_p90", "defense_composite", "possession_composite"]]
            .expanding()
            .mean()
            .groupby(level=0)
            .shift(1)
            .reset_index(level=0, drop=True)
        )
        df["npg_trend"] = (df["npg_p90"] - past_avg["npg_p90"]).fillna(0.0)
        df["def_trend"] = (df["defense_composite"] - past_avg["defense_composite"]).fillna(0.0)
        df["pos_trend"] = (
            df["possession_composite"] - past_avg["possession_composite"]
        ).fillna(0.0)

    df = refine_role_positions(df)

    # Team standings + match-level data (for Dixon-Coles)
    results_path = data_dir / "raw" / "football_data" / "combined_results.parquet"
    fd = pd.read_parquet(results_path)
    artifact_statuses.append(
        {"source": "football_data_results", "status": "loaded", "path": str(results_path)},
    )
    standings_rows = []
    match_rows = []
    for _, row in fd.iterrows():
        season = str(row.get("season", ""))
        league = str(row.get("league", ""))
        home, away = str(row["HomeTeam"]), str(row["AwayTeam"])
        hg, ag = float(row["FTHG"]), float(row["FTAG"])
        hp = 3 if hg > ag else (1 if hg == ag else 0)
        ap = 3 - hp if hg != ag else 1
        standings_rows.append({"team": home, "league": league, "season": season,
                               "points": hp, "gf": hg, "ga": ag})
        standings_rows.append({"team": away, "league": league, "season": season,
                               "points": ap, "gf": ag, "ga": hg})
        match_rows.append({
            "home_team": home, "away_team": away,
            "home_goals": hg, "away_goals": ag,
            "season": season, "league": league,
        })
    standings = pd.DataFrame(standings_rows)
    matches_df = pd.DataFrame(match_rows)
    # Normalize Football-Data team names (some CSVs have inconsistent casing)
    standings["team"] = standings["team"].apply(normalize_team_name)
    team_pts = standings.groupby(["team", "league", "season"]).agg(
        total_points=("points", "sum"),
    ).reset_index()

    # Diagnostics: report team name matching rate
    player_teams = set(df["team"].dropna().unique())
    pts_teams = set(team_pts["team"].dropna().unique())
    matched_teams = player_teams & pts_teams
    unmatched_player = player_teams - pts_teams
    if unmatched_player:
        print(
            f"  队名匹配: {len(matched_teams)}/{len(player_teams)} 球员侧球队匹配积分侧, "
            f"未匹配: {sorted(unmatched_player)[:20]}"
        )
    else:
        print(f"  队名匹配: {len(matched_teams)}/{len(player_teams)} 全部匹配")

    # Report NaN stats coverage
    for col in ["defense_composite", "possession_composite"]:
        n_total = len(df)
        n_nan = int(df[col].isna().sum())
        if n_nan > 0:
            print(f"  {col}: {n_nan}/{n_total} 行缺失 ({n_nan/n_total*100:.1f}%)")

    df.attrs["optimizer_artifact_statuses"] = artifact_statuses
    return df, team_pts, matches_df


def _percentile_against_reference(df, reference_df, column):
    """Map values to per-position percentiles from a reference frame."""
    percentiles = np.full(len(df), 50.0, dtype=np.float32)
    if column not in df.columns or column not in reference_df.columns:
        return percentiles

    for pos_idx in sorted(set(df["pos_idx"].dropna().unique())):
        eval_mask = df["pos_idx"].to_numpy() == pos_idx
        ref_mask = reference_df["pos_idx"].to_numpy() == pos_idx
        ref_values = pd.to_numeric(reference_df.loc[ref_mask, column], errors="coerce")
        ref_values = ref_values[np.isfinite(ref_values)].to_numpy(dtype=np.float32)
        if len(ref_values) == 0:
            continue

        sorted_ref = np.sort(ref_values)
        values = pd.to_numeric(df.loc[eval_mask, column], errors="coerce").to_numpy(
            dtype=np.float32,
        )
        finite = np.isfinite(values)
        pct = np.full(len(values), 50.0, dtype=np.float32)
        left = np.searchsorted(sorted_ref, values[finite], side="left")
        right = np.searchsorted(sorted_ref, values[finite], side="right")
        pct[finite] = ((left + right) / 2.0 / len(sorted_ref) * 100.0).astype(np.float32)
        percentiles[eval_mask] = np.clip(pct, 0.0, 100.0)

    return pd.Series(percentiles, index=df.index, dtype=np.float32)


def _season_sort_key(value):
    text = str(value)
    match = re.search(r"\d{4}", text)
    if match:
        return int(match.group()), text
    return 0, text


def _sorted_seasons(df):
    return tuple(sorted({str(season) for season in df["season"].dropna()}, key=_season_sort_key))


def make_season_splits(
    df,
    *,
    n_splits=3,
    test_seasons=1,
    min_train_seasons=2,
    gap_seasons=0,
):
    """Create expanding-window CV splits by complete season."""
    seasons = _sorted_seasons(df)
    if test_seasons < 1:
        raise ValueError("test_seasons must be at least 1")
    if min_train_seasons < 1:
        raise ValueError("min_train_seasons must be at least 1")
    if gap_seasons < 0:
        raise ValueError("gap_seasons must be non-negative")

    starts = []
    last_start = len(seasons) - test_seasons
    for test_start in range(min_train_seasons + gap_seasons, last_start + 1):
        train_end = test_start - gap_seasons
        if train_end >= min_train_seasons:
            starts.append(test_start)

    if not starts:
        raise ValueError(
            "not enough seasons for chronological validation: "
            f"seasons={list(seasons)}, min_train={min_train_seasons}, "
            f"gap={gap_seasons}, test={test_seasons}",
        )

    selected_starts = starts[-n_splits:] if n_splits and n_splits > 0 else starts
    splits = []
    for fold_idx, test_start in enumerate(selected_starts, start=1):
        train_end = test_start - gap_seasons
        split = SeasonSplit(
            name=f"fold_{fold_idx}",
            train_seasons=seasons[:train_end],
            test_seasons=seasons[test_start:test_start + test_seasons],
        )
        _assert_no_split_leakage(split)
        splits.append(split)
    return splits


def make_holdout_split(df, *, test_seasons=1, min_train_seasons=2, gap_seasons=0):
    """Use the latest complete season block as the final holdout."""
    return make_season_splits(
        df,
        n_splits=1,
        test_seasons=test_seasons,
        min_train_seasons=min_train_seasons,
        gap_seasons=gap_seasons,
    )[-1]


def _assert_no_split_leakage(split):
    train_set = set(split.train_seasons)
    test_set = set(split.test_seasons)
    overlap = train_set.intersection(test_set)
    if overlap:
        raise ValueError(f"season leakage detected in {split.name}: {sorted(overlap)}")
    if split.train_seasons and split.test_seasons:
        train_last = _season_sort_key(split.train_seasons[-1])
        test_first = _season_sort_key(split.test_seasons[0])
        if train_last >= test_first:
            raise ValueError(
                f"non-chronological split {split.name}: "
                f"train_last={split.train_seasons[-1]}, test_first={split.test_seasons[0]}",
            )


def _filter_by_seasons(df, seasons):
    seasons_set = {str(season) for season in seasons}
    return df.loc[df["season"].astype(str).isin(seasons_set)].copy()


def _safe_spearman(pred, actual):
    pred_arr = np.asarray(pred, dtype=float)
    actual_arr = np.asarray(actual, dtype=float)
    if len(pred_arr) < 2 or np.nanstd(pred_arr) == 0 or np.nanstd(actual_arr) == 0:
        return float("nan")
    corr, _ = spearmanr(pred_arr, actual_arr)
    return float(corr)


def _safe_pearson(pred, actual):
    pred_arr = np.asarray(pred, dtype=float)
    actual_arr = np.asarray(actual, dtype=float)
    if len(pred_arr) < 2 or np.nanstd(pred_arr) == 0 or np.nanstd(actual_arr) == 0:
        return float("nan")
    corr, _ = pearsonr(pred_arr, actual_arr)
    return float(corr)


def _standardized_mse(pred, actual):
    pred_arr = np.asarray(pred, dtype=float)
    actual_arr = np.asarray(actual, dtype=float)
    if len(pred_arr) == 0:
        return float("nan")
    pred_std = np.nanstd(pred_arr)
    actual_std = np.nanstd(actual_arr)
    if pred_std == 0 or actual_std == 0:
        return float("nan")
    pred_z = (pred_arr - np.nanmean(pred_arr)) / pred_std
    actual_z = (actual_arr - np.nanmean(actual_arr)) / actual_std
    return float(np.nanmean((pred_z - actual_z) ** 2))


def fit_team_points_calibrator(
    matched_df: pd.DataFrame,
    *,
    min_slope: float = 0.05,
    max_slope: float = 8.0,
    use_league_offsets: bool = True,
    league_prior_n: float = 60.0,
    league_offset_cap: float = 8.0,
) -> TeamPointsCalibrator:
    """Fit a leakage-safe monotonic mapping from strength ratings to points.

    The raw team aggregate is a squad-strength score, not a season-points model.
    This z-score affine layer fixes the known range compression while preserving
    the learned ordering. It must be fitted on train seasons and then reused for
    holdout/test seasons.
    """
    if matched_df.empty:
        return TeamPointsCalibrator(
            method="zscore_affine_empty",
            slope=0.0,
            intercept=0.0,
            pred_mean=0.0,
            pred_std=0.0,
            actual_mean=0.0,
            actual_std=0.0,
            min_slope=float(min_slope),
            max_slope=float(max_slope),
        )

    pred = pd.to_numeric(matched_df["pred_rating"], errors="coerce").to_numpy(dtype=float)
    actual = pd.to_numeric(matched_df["actual_points"], errors="coerce").to_numpy(dtype=float)
    valid = np.isfinite(pred) & np.isfinite(actual)
    if valid.sum() < 2:
        actual_mean = float(np.nanmean(actual[valid])) if valid.any() else 0.0
        return TeamPointsCalibrator(
            method="zscore_affine_degenerate",
            slope=0.0,
            intercept=actual_mean,
            pred_mean=float(np.nanmean(pred[valid])) if valid.any() else 0.0,
            pred_std=0.0,
            actual_mean=actual_mean,
            actual_std=0.0,
            min_slope=float(min_slope),
            max_slope=float(max_slope),
        )

    pred = pred[valid]
    actual = actual[valid]
    pred_mean = float(np.mean(pred))
    actual_mean = float(np.mean(actual))
    pred_std = float(np.std(pred))
    actual_std = float(np.std(actual))
    if pred_std < 1e-8 or actual_std < 1e-8:
        slope = 0.0
        intercept = actual_mean
        method = "zscore_affine_constant"
    else:
        slope = float(np.clip(actual_std / pred_std, min_slope, max_slope))
        intercept = actual_mean - slope * pred_mean
        method = "zscore_affine_train_fit"

    league_offsets = None
    league_residual_means = None
    league_counts = None
    if use_league_offsets and "league" in matched_df.columns:
        prepared = matched_df.loc[valid].copy()
        prepared["pred_points_global"] = intercept + slope * pred
        prepared["residual"] = (
            pd.to_numeric(prepared["actual_points"], errors="coerce")
            - prepared["pred_points_global"]
        )
        league_grouped = prepared.groupby("league", observed=True)["residual"].agg(
            ["count", "mean"],
        )
        if not league_grouped.empty:
            league_counts = {
                str(league): int(row["count"])
                for league, row in league_grouped.iterrows()
            }
            league_residual_means = {
                str(league): float(row["mean"])
                for league, row in league_grouped.iterrows()
            }
            prior = max(float(league_prior_n), 0.0)
            cap = max(float(league_offset_cap), 0.0)
            offsets = {}
            for league, row in league_grouped.iterrows():
                shrink = float(row["count"]) / (float(row["count"]) + prior) if prior > 0 else 1.0
                offset = float(row["mean"]) * shrink
                offsets[str(league)] = float(np.clip(offset, -cap, cap))
            league_offsets = offsets

    return TeamPointsCalibrator(
        method=method,
        slope=slope,
        intercept=float(intercept),
        pred_mean=pred_mean,
        pred_std=pred_std,
        actual_mean=actual_mean,
        actual_std=actual_std,
        min_slope=float(min_slope),
        max_slope=float(max_slope),
        league_offsets=league_offsets,
        league_residual_means=league_residual_means,
        league_counts=league_counts,
        league_prior_n=float(league_prior_n),
        league_offset_cap=float(league_offset_cap),
    )


def apply_team_points_calibrator(
    matched_df: pd.DataFrame,
    calibrator: TeamPointsCalibrator | None,
) -> pd.DataFrame:
    """Attach calibrated season-point predictions to a matched result frame."""
    if calibrator is None or matched_df.empty:
        return matched_df
    result = matched_df.copy()
    pred = pd.to_numeric(result["pred_rating"], errors="coerce").to_numpy(dtype=float)
    result["pred_points_global"] = calibrator.intercept + calibrator.slope * pred
    if calibrator.league_offsets:
        offsets = result["league"].astype(str).map(calibrator.league_offsets).fillna(0.0)
        result["pred_points_league_offset"] = offsets.to_numpy(dtype=float)
        result["pred_points_calibrated"] = result["pred_points_global"] + offsets
    else:
        result["pred_points_league_offset"] = 0.0
        result["pred_points_calibrated"] = result["pred_points_global"]
    return result


def build_matched_results(feat, team_pts_df, team_avgs):
    """Match predicted team-season ratings with actual points.

    Teams with NaN or non-finite total_points are excluded from matching.
    Uses normalize_team_name for cross-source team name matching.
    """
    # Filter out teams with NaN or non-finite total_points
    valid_pts = team_pts_df.copy()
    valid_pts["total_points"] = pd.to_numeric(valid_pts["total_points"], errors="coerce")
    n_before = len(valid_pts)
    valid_pts = valid_pts[
        valid_pts["total_points"].notna() & np.isfinite(valid_pts["total_points"])
    ]
    n_excluded = n_before - len(valid_pts)

    # Build lookup with normalized team names
    points_lookup = {
        (normalize_team_name(row["team"]), str(row["league"]), str(row["season"])): float(
            row["total_points"],
        )
        for _, row in valid_pts.iterrows()
    }
    rows = []
    for i, (team, league, season) in enumerate(
        zip(feat["ts_team_names"], feat["ts_leagues"], feat["ts_seasons"], strict=False)
    ):
        # Normalize team name for matching
        normalized_team = normalize_team_name(team)
        key = (normalized_team, str(league), str(season))
        if key not in points_lookup:
            continue
        rows.append(
            {
                "team": str(team),
                "normalized_team": normalized_team,
                "league": str(league),
                "season": str(season),
                "pred_rating": float(team_avgs[i]),
                "actual_points": points_lookup[key],
            },
        )
    result = pd.DataFrame(rows)
    result.attrs["n_excluded_na"] = n_excluded
    return result


def team_coverage_table(feat, team_pts_df):
    """Report team-season coverage before interpreting holdout metrics."""
    actual = team_pts_df.loc[:, ["team", "league", "season"]].copy()
    if actual.empty:
        return pd.DataFrame(
            columns=[
                "league",
                "season",
                "target_teams",
                "rated_teams",
                "matched_teams",
                "coverage",
            ],
        )

    actual = actual.astype(str).drop_duplicates()
    # Normalize team names in actual
    actual["team"] = actual["team"].apply(normalize_team_name)

    rated = pd.DataFrame(
        {
            "team": [normalize_team_name(team) for team in feat["ts_team_names"]],
            "league": [str(league) for league in feat["ts_leagues"]],
            "season": [str(season) for season in feat["ts_seasons"]],
        },
    ).drop_duplicates()
    # Defensive: replace "nan" league with "Bundesliga" (FBref NaN league issue)
    rated["league"] = rated["league"].replace("nan", "Bundesliga")
    matched = actual.merge(rated, on=["team", "league", "season"], how="inner")

    group_cols = ["league", "season"]
    target_counts = actual.groupby(group_cols, observed=True).size().rename("target_teams")
    rated_counts = rated.groupby(group_cols, observed=True).size().rename("rated_teams")
    matched_counts = matched.groupby(group_cols, observed=True).size().rename("matched_teams")
    coverage = (
        pd.concat([target_counts, rated_counts, matched_counts], axis=1)
        .fillna(0)
        .reset_index()
    )
    for column in ["target_teams", "rated_teams", "matched_teams"]:
        coverage[column] = coverage[column].astype(int)
    coverage["coverage"] = coverage["matched_teams"] / coverage["target_teams"].where(
        coverage["target_teams"] > 0,
    )
    coverage = coverage.sort_values(["season", "league"]).reset_index(drop=True)
    return coverage


def rating_calibration_table(matched_df, n_bins=5):
    """Compare predicted rating percentiles with actual point percentiles."""
    if matched_df.empty:
        return pd.DataFrame(
            columns=[
                "bin",
                "n",
                "pred_percentile_mean",
                "actual_percentile_mean",
                "calibration_gap",
            ],
        )

    prepared = matched_df.copy()
    prepared["pred_percentile"] = prepared["pred_rating"].rank(method="average", pct=True) * 100
    prepared["actual_percentile"] = prepared["actual_points"].rank(method="average", pct=True) * 100
    bins = max(1, min(int(n_bins), len(prepared)))
    prepared["bin"] = pd.qcut(
        prepared["pred_percentile"],
        q=bins,
        labels=False,
        duplicates="drop",
    )
    grouped = prepared.groupby("bin", dropna=False, observed=True).agg(
        n=("team", "size"),
        pred_percentile_mean=("pred_percentile", "mean"),
        actual_percentile_mean=("actual_percentile", "mean"),
    )
    grouped = grouped.reset_index()
    grouped["calibration_gap"] = (
        grouped["pred_percentile_mean"] - grouped["actual_percentile_mean"]
    )
    return grouped


def calibration_mae(matched_df, n_bins=5):
    table = rating_calibration_table(matched_df, n_bins=n_bins)
    if table.empty:
        return float("nan")
    weights = table["n"].to_numpy(dtype=float)
    gaps = np.abs(table["calibration_gap"].to_numpy(dtype=float))
    return float(np.average(gaps, weights=weights))


def rating_metrics(matched_df, *, n_bins=5):
    if matched_df.empty:
        return {
            "n_team_seasons": 0,
            "spearman": float("nan"),
            "pearson": float("nan"),
            "rank_loss": float("nan"),
            "z_mse": float("nan"),
            "calibration_mae": float("nan"),
            "raw_pred_range": float("nan"),
            "actual_points_range": float("nan"),
            "raw_spread_ratio": float("nan"),
            "points_mae": float("nan"),
            "points_rmse": float("nan"),
            "points_bias": float("nan"),
            "points_spread_ratio": float("nan"),
        }
    spearman = _safe_spearman(matched_df["pred_rating"], matched_df["actual_points"])
    pearson = _safe_pearson(matched_df["pred_rating"], matched_df["actual_points"])
    rank_loss = 1.0 - spearman if np.isfinite(spearman) else float("nan")
    pred_arr = pd.to_numeric(matched_df["pred_rating"], errors="coerce").to_numpy(dtype=float)
    actual_arr = pd.to_numeric(matched_df["actual_points"], errors="coerce").to_numpy(dtype=float)
    actual_std = np.nanstd(actual_arr)
    pred_std = np.nanstd(pred_arr)
    raw_spread_ratio = (
        float(pred_std / actual_std)
        if np.isfinite(pred_std) and np.isfinite(actual_std) and actual_std > 0
        else float("nan")
    )
    raw_pred_range = (
        float(np.nanmax(pred_arr) - np.nanmin(pred_arr)) if len(pred_arr) else float("nan")
    )
    actual_points_range = (
        float(np.nanmax(actual_arr) - np.nanmin(actual_arr)) if len(actual_arr) else float("nan")
    )
    points_mae = float("nan")
    points_rmse = float("nan")
    points_bias = float("nan")
    points_spread_ratio = float("nan")
    if "pred_points_calibrated" in matched_df.columns:
        points_arr = pd.to_numeric(
            matched_df["pred_points_calibrated"],
            errors="coerce",
        ).to_numpy(dtype=float)
        diff = points_arr - actual_arr
        points_mae = float(np.nanmean(np.abs(diff)))
        points_rmse = float(np.sqrt(np.nanmean(diff ** 2)))
        points_bias = float(np.nanmean(diff))
        points_std = np.nanstd(points_arr)
        points_spread_ratio = (
            float(points_std / actual_std)
            if np.isfinite(points_std) and np.isfinite(actual_std) and actual_std > 0
            else float("nan")
        )
    return {
        "n_team_seasons": int(len(matched_df)),
        "spearman": spearman,
        "pearson": pearson,
        "rank_loss": rank_loss,
        "z_mse": _standardized_mse(matched_df["pred_rating"], matched_df["actual_points"]),
        "calibration_mae": calibration_mae(matched_df, n_bins=n_bins),
        "raw_pred_range": raw_pred_range,
        "actual_points_range": actual_points_range,
        "raw_spread_ratio": raw_spread_ratio,
        "points_mae": points_mae,
        "points_rmse": points_rmse,
        "points_bias": points_bias,
        "points_spread_ratio": points_spread_ratio,
    }


def evaluate_params(
    params,
    eval_df,
    team_pts_df,
    rank_reference_df,
    device,
    *,
    split_name,
    calibration_bins=5,
    points_calibrator: TeamPointsCalibrator | None = None,
):
    """Evaluate params on a slice without letting that slice define train statistics."""
    # Local imports to avoid circular dependency with evaluate module
    from .scoring import build_feature_tensors, compute_ratings_torch, compute_team_avg_ratings

    feat_eval = build_feature_tensors(eval_df, rank_reference_df=rank_reference_df)
    ratings = compute_ratings_torch(feat_eval, params.to(device), device)
    team_avgs = compute_team_avg_ratings(feat_eval, ratings, device)
    matched_df = build_matched_results(feat_eval, team_pts_df, team_avgs)
    matched_df = apply_team_points_calibrator(matched_df, points_calibrator)
    coverage = team_coverage_table(feat_eval, team_pts_df)
    metrics = rating_metrics(matched_df, n_bins=calibration_bins)
    metrics["split"] = split_name
    metrics["n_players"] = int(len(eval_df))
    metrics["target_team_seasons"] = (
        int(coverage["target_teams"].sum()) if not coverage.empty else 0
    )
    metrics["rated_team_seasons"] = int(coverage["rated_teams"].sum()) if not coverage.empty else 0
    metrics["team_coverage"] = (
        float(coverage["matched_teams"].sum() / coverage["target_teams"].sum())
        if not coverage.empty and coverage["target_teams"].sum() > 0
        else float("nan")
    )
    # Report N/A teams excluded from evaluation
    excluded_na = matched_df.attrs.get("n_excluded_na", 0)
    metrics["n_excluded_na_teams"] = excluded_na
    return {
        "features": feat_eval,
        "matched": matched_df,
        "metrics": metrics,
        "calibration": rating_calibration_table(matched_df, n_bins=calibration_bins),
        "coverage": coverage,
    }


def league_metrics(matched_df, *, min_n=5, calibration_bins=5):
    rows = []
    if matched_df.empty:
        return pd.DataFrame(rows)
    for league in sorted(matched_df["league"].dropna().unique()):
        league_frame = matched_df.loc[matched_df["league"] == league].copy()
        if len(league_frame) < min_n:
            continue
        metrics = rating_metrics(league_frame, n_bins=calibration_bins)
        metrics["league"] = league
        rows.append(metrics)
    return pd.DataFrame(rows)


def permutation_feature_importance(
    params,
    eval_df,
    team_pts_df,
    rank_reference_df,
    device,
    *,
    columns=None,
    n_repeats=1,
    seed=42,
    calibration_bins=5,
):
    """Estimate feature importance by Spearman drop after shuffling one feature."""
    if columns is None:
        columns = [
            "minutes",
            "starts",
            "matches",
            "npg_p90",
            "assists_p90",
            "g_a_volume",
            "defense_composite",
            "possession_composite",
            "npg_trend",
        ]
    base_eval = evaluate_params(
        params,
        eval_df,
        team_pts_df,
        rank_reference_df,
        device,
        split_name="importance_base",
        calibration_bins=calibration_bins,
    )
    base_spearman = base_eval["metrics"]["spearman"]
    rng = np.random.default_rng(seed)
    rows = []
    for column in columns:
        if column not in eval_df.columns or eval_df[column].nunique(dropna=True) <= 1:
            continue
        drops = []
        shuffled_scores = []
        for _ in range(max(1, int(n_repeats))):
            shuffled = eval_df.copy()
            values = shuffled[column].to_numpy(copy=True)
            rng.shuffle(values)
            shuffled[column] = values
            shuffled_eval = evaluate_params(
                params,
                shuffled,
                team_pts_df,
                rank_reference_df,
                device,
                split_name=f"shuffle_{column}",
                calibration_bins=calibration_bins,
            )
            shuffled_spearman = shuffled_eval["metrics"]["spearman"]
            if np.isfinite(base_spearman) and np.isfinite(shuffled_spearman):
                drops.append(base_spearman - shuffled_spearman)
            shuffled_scores.append(shuffled_spearman)
        rows.append(
            {
                "feature": column,
                "baseline_spearman": base_spearman,
                "shuffled_spearman_mean": float(np.nanmean(shuffled_scores)),
                "spearman_drop_mean": float(np.nanmean(drops)) if drops else float("nan"),
                "spearman_drop_std": float(np.nanstd(drops)) if drops else float("nan"),
                "n_repeats": int(max(1, int(n_repeats))),
            },
        )
    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values("spearman_drop_mean", ascending=False, na_position="last")
    return result


def optimizer_input_artifacts(data_dir: Path) -> list[str]:
    """List the local artifacts that can influence an optimizer run.

    The active player-rating output is deliberately excluded: the optimizer
    does not read it, so including it would make a candidate's lineage depend
    on the score artifact it may later replace. Optional FBref inputs follow
    the same five-season/three-season fallback that ``load_data`` uses.
    """
    root = Path(data_dir)
    candidates = [
        "raw/fbref/player_stats_big5_3seasons.parquet",
        "raw/football_data/combined_results.parquet",
        "raw/understat/players_10seasons.parquet",
        "gold/feature_store/rating_feature_matrix.parquet",
        "gold/feature_store/player_truth_labels.parquet",
    ]
    for preferred, fallback in (
        (
            "raw/fbref/player_misc_5seasons.parquet",
            "raw/fbref/player_misc_3seasons.parquet",
        ),
        (
            "raw/fbref/player_shooting_5seasons.parquet",
            "raw/fbref/player_shooting_3seasons.parquet",
        ),
    ):
        candidates.append(preferred if (root / preferred).exists() else fallback)
    return [relative for relative in candidates if (root / relative).exists()]


def compute_input_hash(data_dir: Path) -> str:
    """Compute SHA256 hash of artifacts actually read by the optimizer."""
    hasher = hashlib.sha256()
    for rel_path in optimizer_input_artifacts(data_dir):
        fpath = data_dir / rel_path
        hasher.update(fpath.read_bytes())
    return hasher.hexdigest()[:16]


def build_run_lineage(data_dir: Path, *, input_hash: str | None = None) -> dict:
    """Describe the local dataset and feature-manifest snapshot used by a run.

    The rating optimizer's input hash identifies source artifacts actually read
    by the run, never an active player-rating output.
    The adjacent feature-manifest hash identifies the schema and feature build
    metadata separately, so a run can be reproduced or explicitly marked as
    partially recorded when older artifacts lack that manifest.
    """
    root = Path(data_dir)
    manifest_path = root / "gold" / "feature_store" / "rating_feature_matrix_manifest.json"
    manifest: dict = {}
    manifest_hash: str | None = None
    if manifest_path.exists():
        raw = manifest_path.read_bytes()
        manifest_hash = hashlib.sha256(raw).hexdigest()[:16]
        try:
            loaded = json.loads(raw)
            manifest = loaded if isinstance(loaded, dict) else {}
        except (TypeError, ValueError, UnicodeDecodeError):
            manifest = {}

    snapshot_hash = input_hash or compute_input_hash(root)
    return {
        "schema": "scoutfootball.model-run-lineage",
        "version": "1.0.0",
        "status": "recorded" if manifest_hash else "partial",
        "dataset_snapshot": {
            "input_hash": snapshot_hash,
            "input_artifacts": optimizer_input_artifacts(root),
        },
        "feature_manifest": {
            "path": "gold/feature_store/rating_feature_matrix_manifest.json",
            "hash": manifest_hash,
            "schema_version": manifest.get("schema_version") or manifest.get("version"),
            "generated_at": manifest.get("generated_at") or manifest.get("timestamp"),
            "input_hash": manifest.get("input_hash"),
        },
    }


def build_dc_tensors(feat, matches_df, device):
    """Build Dixon-Coles tensors from match data and feature tensors.

    Maps Football-Data match home/away teams to the same team group indices
    used by the rating optimizer, so dc_likelihood loss can be computed.

    Args:
        feat: output of build_feature_tensors (contains ts_team_names, ts_leagues, ts_seasons)
        matches_df: DataFrame with columns [home_team, away_team, home_goals,
            away_goals, season, league]
        device: torch device

    Returns:
        dict with keys: home_group_idx, away_group_idx, home_goals, away_goals, n_matches
        Returns None if no matches can be mapped.
    """
    ts_names = feat["ts_team_names"]
    ts_leagues = feat["ts_leagues"]
    ts_seasons = feat["ts_seasons"]

    # Build lookup: (normalize(team), league, season) -> group_idx
    lookup = {}
    for i, (name, lg, ssn) in enumerate(zip(ts_names, ts_leagues, ts_seasons, strict=False)):
        key = (normalize_team_name(name), str(lg), str(ssn))
        lookup[key] = i

    home_idx, away_idx, hg_list, ag_list = [], [], [], []
    for _, row in matches_df.iterrows():
        home = normalize_team_name(str(row["home_team"]))
        away = normalize_team_name(str(row["away_team"]))
        lg = str(row["league"])
        ssn = str(row["season"])
        hi = lookup.get((home, lg, ssn))
        ai = lookup.get((away, lg, ssn))
        if hi is not None and ai is not None:
            home_idx.append(hi)
            away_idx.append(ai)
            hg_list.append(float(row["home_goals"]))
            ag_list.append(float(row["away_goals"]))

    n = len(home_idx)
    if n == 0:
        return None

    return {
        "home_group_idx": torch.tensor(home_idx, dtype=torch.long, device=device),
        "away_group_idx": torch.tensor(away_idx, dtype=torch.long, device=device),
        "home_goals": torch.tensor(hg_list, dtype=torch.float32, device=device),
        "away_goals": torch.tensor(ag_list, dtype=torch.float32, device=device),
        "n_matches": n,
    }


def save_model_run(
    params: np.ndarray,
    metrics: dict,
    args: argparse.Namespace | None = None,
    output_dir: Path | None = None,
    run_id: str | None = None,
    feat_hash: str | None = None,
    data_dir: Path | None = None,
    data_coverage: dict | None = None,
    error_cases: dict | None = None,
    train_seasons: tuple[str, ...] | list[str] | None = None,
    test_seasons: tuple[str, ...] | list[str] | None = None,
):
    """Save model run with full provenance to data/models/runs/<timestamp>/.

    Saves:
    - optimized_params.npy
    - meta.json with: params summary, seed, input hash, metrics, position metrics,
      error case summary, dependency versions, train/test season split,
      composite objective weights and dataset/feature-manifest lineage
    """
    import platform
    from datetime import UTC, datetime

    timestamp = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    if Path(timestamp).name != timestamp:
        raise ValueError("run_id must be a single directory name")
    run_dir = (output_dir or Path("data/models/runs")) / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    # Save params
    np.save(run_dir / "optimized_params.npy", params)

    # Build meta
    meta: dict = {
        "timestamp": timestamp,
        "run_id": timestamp,
        "params_shape": list(params.shape),
        "params_mean": float(params.mean()),
        "params_std": float(params.std()),
        "input_hash": feat_hash,
        # Metrics contain nested baseline/holdout dictionaries. Preserve that
        # structure so a later promotion review can compare like-for-like
        # evidence; converting nested values to ``str`` makes it impossible to
        # distinguish an evaluated candidate from a legacy opaque record.
        "metrics": _json_ready(metrics),
        "lineage": build_run_lineage(data_dir or Path("data"), input_hash=feat_hash),
        "activation": {
            "status": "not_activated",
            "note": "Candidate artifacts remain local until an explicit promotion workflow exists.",
        },
    }
    if data_coverage is not None:
        meta["data_coverage"] = _json_ready(data_coverage)

    # Dependency versions for reproducibility
    dep_versions: dict[str, str] = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
    }
    try:
        dep_versions["torch"] = torch.__version__
    except Exception:
        pass
    for mod_name in ("sklearn", "scipy", "duckdb"):
        try:
            mod = __import__(mod_name)
            dep_versions[mod_name] = getattr(mod, "__version__", "unknown")
        except Exception:
            pass
    meta["dependency_versions"] = dep_versions

    # Record the actual split selected by ``make_holdout_split``. CLI knobs
    # such as ``--test-seasons 1`` are configuration counts, not a season
    # list, and must never be represented as the holdout itself.
    def _season_list(value: object) -> list[str] | None:
        if value is None:
            return None
        if isinstance(value, str):
            return [value]
        if isinstance(value, (list, tuple)):
            return [str(season) for season in value]
        return None

    recorded_train = _season_list(train_seasons)
    recorded_test = _season_list(test_seasons)
    if recorded_train is None and args is not None:
        recorded_train = _season_list(getattr(args, "train_seasons", None))
    if recorded_test is None and args is not None:
        recorded_test = _season_list(getattr(args, "test_seasons", None))
    if recorded_train:
        meta["train_seasons"] = recorded_train
    if recorded_test:
        meta["test_seasons"] = recorded_test

    # Position-level metrics (if provided in metrics dict)
    for pos_key in ("position_metrics", "position_metrics_by_group"):
        if pos_key in metrics and isinstance(metrics[pos_key], dict):
            meta[pos_key] = _json_ready(metrics[pos_key])
            break

    # Prefer error cases derived from this exact holdout evaluation. The legacy
    # file lookup remains only as a compatibility fallback and must not make a
    # run depend on a stale shared file.
    recorded_error_cases = error_cases or _compute_error_cases(output_dir)
    if recorded_error_cases:
        meta["error_cases"] = _json_ready(recorded_error_cases)

    if args is not None:
        meta["args"] = {
            "pop_size": getattr(args, "pop", None),
            "n_steps": getattr(args, "steps", None),
            "lr": getattr(args, "lr", None),
            "patience": getattr(args, "patience", None),
            "seed": getattr(args, "seed", None),
            "spearman_weight": getattr(args, "spearman_weight", None),
            "ndcg_weight": getattr(args, "ndcg_weight", None),
            "position_consistency_weight": getattr(args, "position_consistency_weight", None),
            "points_regression_weight": getattr(args, "points_regression_weight", None),
            "distribution_weight": getattr(args, "distribution_weight", None),
            "quantile_weight": getattr(args, "quantile_weight", None),
            "range_penalty_weight": getattr(args, "range_penalty_weight", None),
            "tail_calibration_weight": getattr(args, "tail_calibration_weight", None),
            "league_bias_weight": getattr(args, "league_bias_weight", None),
            "extreme_penalty_weight": getattr(args, "extreme_penalty_weight", None),
            "prior_weight": getattr(args, "prior_weight", None),
            "dc_likelihood_weight": getattr(args, "dc_likelihood_weight", None),
            "warmup_steps": getattr(args, "warmup_steps", None),
            "min_lr_ratio": getattr(args, "min_lr_ratio", None),
            "grad_clip": getattr(args, "grad_clip", None),
            "league_calibration_prior_n": getattr(args, "league_calibration_prior_n", None),
            "league_calibration_cap": getattr(args, "league_calibration_cap", None),
            "disable_league_calibration": getattr(args, "disable_league_calibration", None),
        }

    with open(run_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"  模型运行登记已保存: {run_dir}")
    return run_dir


def compute_error_cases(matched_df: pd.DataFrame) -> dict | None:
    """Summarize the largest team-level residuals for one holdout evaluation."""
    if matched_df.empty or "team" not in matched_df.columns:
        return None

    prepared = matched_df.copy()
    residual_col = "residual"
    prediction_columns = ("pred_points_calibrated", "pred_points_global", "pred_rating")
    prediction_column = next(
        (column for column in prediction_columns if column in prepared),
        None,
    )
    if prediction_column is not None and "actual_points" in prepared.columns:
        prepared[residual_col] = (
            pd.to_numeric(prepared[prediction_column], errors="coerce")
            - pd.to_numeric(prepared["actual_points"], errors="coerce")
        )
        residual_definition = "prediction_minus_actual"
    elif residual_col in prepared.columns:
        # A historical fallback file may have an undocumented residual sign.
        # Preserve it for inspection instead of mislabelling the direction.
        residual_definition = "legacy_residual_column_direction_not_recorded"
    else:
        return None

    prepared[residual_col] = pd.to_numeric(prepared[residual_col], errors="coerce")
    prepared = prepared.dropna(subset=["team", residual_col])
    if prepared.empty:
        return None

    aggregated = prepared.groupby("team", observed=True)[residual_col].mean().sort_values()
    return {
        "residual_definition": residual_definition,
        "over_estimated": [
            {"team": str(team), "residual": round(float(value), 1)}
            for team, value in aggregated.tail(5).items()
        ],
        "under_estimated": [
            {"team": str(team), "residual": round(float(value), 1)}
            for team, value in aggregated.head(5).items()
        ],
    }


def _compute_error_cases(output_dir: Path | None) -> dict | None:
    """Load holdout predictions and compute top over/under-estimated teams.

    Returns ``{"over_estimated": [...], "under_estimated": [...]}`` or ``None``
    if the holdout predictions file is not available.
    """
    # The holdout predictions parquet is saved alongside optimized_params
    # in data/gold/feature_store/rating_holdout_predictions.parquet
    search_dirs: list[Path] = []
    if output_dir is not None:
        search_dirs.append(output_dir.parent)  # gold/feature_store/
        search_dirs.append(output_dir.parent.parent)  # gold/
    search_dirs.append(Path("data/gold/feature_store"))
    search_dirs.append(Path("data/models"))

    holdout_path: Path | None = None
    for d in search_dirs:
        candidate = d / "rating_holdout_predictions.parquet"
        if candidate.exists():
            holdout_path = candidate
            break

    if holdout_path is None:
        return None

    try:
        df = pd.read_parquet(holdout_path)
    except Exception:
        return None

    # Identify team and residual columns (names vary across optimizer versions)
    team_col = None
    for c in ("team", "team_name", "squad"):
        if c in df.columns:
            team_col = c
            break
    if team_col is None:
        return None

    residual_col = None
    for c in ("residual", "points_residual", "error", "points_error"):
        if c in df.columns:
            residual_col = c
            break
    if residual_col is None:
        # Try to compute residual from predicted vs actual
        pred_candidates = ("predicted_points", "pred_points", "calibrated_points")
        actual_candidates = ("actual_points", "true_points", "points")
        pred_col = next(
            (c for c in pred_candidates if c in df.columns), None,
        )
        actual_col = next(
            (c for c in actual_candidates if c in df.columns), None,
        )
        if pred_col and actual_col:
            df = df.copy()
            df["__residual"] = df[pred_col] - df[actual_col]
            residual_col = "__residual"
        else:
            return None

    prepared = df.rename(columns={team_col: "team", residual_col: "residual"})
    return compute_error_cases(prepared)


def _json_ready(value):
    """Convert numpy/pandas scalars and NaN values to JSON-safe objects."""
    if hasattr(value, "__dataclass_fields__"):
        return _json_ready(asdict(value))
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_json_ready(v) for v in value]
    if isinstance(value, pd.DataFrame):
        return [_json_ready(row) for row in value.to_dict(orient="records")]
    if isinstance(value, pd.Series):
        return _json_ready(value.to_dict())
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value
