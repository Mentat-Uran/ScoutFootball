#!/usr/bin/env python3
"""
球员评分权重优化器 — PyTorch GPU 版本
在 Windows + RTX 5070 Ti 上运行，几秒完成一次优化循环。

使用方法 (Windows):
  1. pip install torch pandas numpy scipy pyarrow
  2. 把 data/ 目录复制到 Windows 机器上
  3. python optimize_ratings_gpu.py --data_dir ./data

或在 Mac 上用 CPU 也能跑 (会慢一些但比 scipy 快很多)。
"""

import argparse
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from scipy.stats import pearsonr, spearmanr

# ── 位置映射 ──────────────────────────────────────────────────────────────

POSITIONS = ["ST", "W", "AM", "CM", "DM", "FB", "CB", "GK"]
DIMENSIONS = ["availability", "attack", "defense", "possession", "quality"]
ATTACK_METRICS = ["npxg_p90", "assists_p90", "g_a_volume"]
POS_TO_IDX = {p: i for i, p in enumerate(POSITIONS)}
N_POS = len(POSITIONS)
N_DIM = len(DIMENSIONS)
N_ATK = len(ATTACK_METRICS)
N_PARAMS = (
    N_POS * N_DIM + N_POS * N_ATK + 4 + 4 + 3 + 2
)  # = 77 (added trend_weight, experience_weight)

POSITION_DIMENSION_PRIOR = [
    [0.15, 0.38, 0.08, 0.14, 0.25],  # ST
    [0.12, 0.30, 0.10, 0.25, 0.23],  # W
    [0.12, 0.28, 0.10, 0.28, 0.22],  # AM
    [0.14, 0.16, 0.18, 0.32, 0.20],  # CM
    [0.14, 0.08, 0.30, 0.28, 0.20],  # DM
    [0.15, 0.10, 0.28, 0.27, 0.20],  # FB
    [0.16, 0.05, 0.42, 0.20, 0.17],  # CB
    [0.20, 0.05, 0.35, 0.20, 0.20],  # GK
]
ATTACK_WEIGHT_PRIOR = [
    [0.45, 0.15, 0.40],  # ST
    [0.30, 0.30, 0.40],  # W
    [0.20, 0.40, 0.40],  # AM
    [0.15, 0.35, 0.50],  # CM
    [0.10, 0.25, 0.65],  # DM
    [0.10, 0.45, 0.45],  # FB
    [0.20, 0.20, 0.60],  # CB
    [0.05, 0.05, 0.90],  # GK
]
QUALITY_SUBWEIGHT_PRIOR = [0.35, 0.25, 0.25, 0.15]
POSITION_DIMENSION_CAPS = [
    [0.20, 1.00, 1.00, 1.00, 0.30],  # ST: 出勤是可靠性信号，不能替代进攻输出
    [0.20, 1.00, 1.00, 1.00, 0.28],  # W
    [0.20, 0.35, 1.00, 1.00, 0.30],  # AM
    [0.18, 0.22, 1.00, 1.00, 0.24],  # CM: 防止出勤/进攻/quality 泛化霸榜
    [0.20, 0.12, 1.00, 1.00, 0.24],  # DM
    [0.20, 0.16, 1.00, 1.00, 0.28],  # FB
    [0.18, 0.10, 1.00, 1.00, 0.25],  # CB
    [0.18, 0.06, 1.00, 1.00, 0.28],  # GK
]
TEAM_AGG_MINUTES_CAP = 1500.0
TEAM_AGG_CORE_MINUTES = 450.0
TEAM_AGG_CORE_SCALE = 180.0
TEAM_AGG_CAPPED_MINUTES_BLEND = 0.55


@dataclass(frozen=True)
class SeasonSplit:
    """Chronological split by complete seasons."""

    name: str
    train_seasons: tuple[str, ...]
    test_seasons: tuple[str, ...]


def map_position(pos_str):
    if not isinstance(pos_str, str):
        return "CM"
    s = pos_str.upper()
    if "GK" in s:
        return "GK"
    if "FW" in s and "MF" in s:
        return "W"
    if "MF" in s and "FW" in s:
        return "AM"
    if "DF" in s and "MF" in s:
        return "FB"
    if "MF" in s and "DF" in s:
        return "DM"
    if "FW" in s:
        return "ST"
    if "DF" in s:
        return "CB"
    if "MF" in s:
        return "CM"
    return "CM"


def refine_role_positions(df: pd.DataFrame) -> pd.DataFrame:
    """用历史粗位置和当前输出特征修正明显的角色误分。

    FBref 的 `pos` 在部分赛季会把边锋、前腰和翼卫统一写成 `MF`，
    直接映射会把 Salah、Olise、Dimarco 这类球员挤进 CM 池。这里不做
    球员名单特判，只在有历史 FW/DF 线索且当前输出特征支持时改写角色。
    """
    if "source_position" not in df.columns:
        return df

    refined = df.copy()
    source = refined["source_position"].fillna("").astype(str).str.upper()
    history_by_player = refined.groupby("player")["source_position"].agg(
        lambda values: " ".join(
            sorted({str(value).upper() for value in values if pd.notna(value)})
        ),
    )
    history = refined["player"].map(history_by_player).fillna("")

    has_fw_history = history.str.contains("FW", regex=False)
    has_df_history = history.str.contains("DF", regex=False)
    has_wingback_history = history.str.contains("DF,MF", regex=False) | history.str.contains(
        "MF,DF",
        regex=False,
    )

    npg = pd.to_numeric(refined.get("npg_p90", 0.0), errors="coerce").fillna(0.0)
    assists = pd.to_numeric(refined.get("assists_p90", 0.0), errors="coerce").fillna(0.0)
    volume = pd.to_numeric(refined.get("g_a_volume", 0.0), errors="coerce").fillna(0.0)
    crosses = pd.to_numeric(refined.get("crosses_p90", 0.0), errors="coerce").fillna(0.0)
    defense = pd.to_numeric(refined.get("defense_composite", 0.0), errors="coerce").fillna(0.0)

    current_cm = refined["sub_position"].eq("CM")
    raw_mf = source.eq("MF")
    raw_df = source.eq("DF")

    # 进攻型 MF 只有在历史上出现过 FW 或当前产量非常前场化时才改为 W/AM。
    # 这避免把普通推进型中场仅因助攻波动改成前场。
    forward_like = (
        (has_fw_history & ((npg >= 0.20) | (assists >= 0.20) | (volume >= 8.0)))
        | ((npg >= 0.32) & (volume >= 10.0))
    )
    pure_attacking_mid = (~has_fw_history) & (npg >= 0.24) & (assists >= 0.16)

    # 翼卫/边后卫在 FBref 中经常从 DF,MF 降级成 MF 或 DF。用历史 DF/MF 线索、
    # 传中和防守动作量判断，不把纯进攻边锋误放到后场。
    wingback_like = has_df_history & (
        (raw_df & has_wingback_history)
        | (crosses >= 1.8)
        | ((crosses >= 1.2) & (defense >= 0.8))
    )

    refined.loc[current_cm & raw_mf & wingback_like, "sub_position"] = "FB"
    refined.loc[current_cm & raw_mf & forward_like & ~wingback_like, "sub_position"] = "W"
    refined.loc[current_cm & raw_mf & pure_attacking_mid & ~wingback_like, "sub_position"] = "AM"
    refined.loc[raw_df & wingback_like, "sub_position"] = "FB"
    refined["pos_idx"] = (
        refined["sub_position"].map(POS_TO_IDX).fillna(POS_TO_IDX["CM"]).astype(int)
    )

    return refined


def apply_position_weight_caps(weights: torch.Tensor) -> torch.Tensor:
    """限制明显不符合角色职责的维度权重，并保持每行归一化。"""
    caps = torch.tensor(POSITION_DIMENSION_CAPS, dtype=weights.dtype, device=weights.device)
    capped = torch.minimum(weights, caps)
    missing = torch.clamp(1.0 - capped.sum(dim=1, keepdim=True), min=0.0)
    room = torch.clamp(caps - capped, min=0.0)
    room_sum = room.sum(dim=1, keepdim=True).clamp_min(1e-8)
    adjusted = capped + missing * room / room_sum
    return adjusted / adjusted.sum(dim=1, keepdim=True).clamp_min(1e-8)


def team_aggregation_config() -> dict[str, float]:
    """Return the robust team-season aggregation settings for reports."""
    return {
        "minutes_cap": TEAM_AGG_MINUTES_CAP,
        "core_minutes": TEAM_AGG_CORE_MINUTES,
        "core_scale": TEAM_AGG_CORE_SCALE,
        "capped_minutes_blend": TEAM_AGG_CAPPED_MINUTES_BLEND,
        "core_rotation_blend": 1.0 - TEAM_AGG_CAPPED_MINUTES_BLEND,
    }


# ── 数据加载 ──────────────────────────────────────────────────────────────

def load_data(data_dir: Path):
    """加载 FBref 球员数据 (standard + misc + shooting) + Football-Data 球队积分。"""
    fbref = pd.read_parquet(data_dir / "raw" / "fbref" / "player_stats_big5_3seasons.parquet")

    goals = fbref[("Performance", "Gls")].values.astype(np.float32)
    assists_col = fbref[("Performance", "Ast")].values.astype(np.float32)
    pk = fbref[("Performance", "PK")].values.astype(np.float32)
    minutes = fbref[("Playing Time", "Min")].values.astype(np.float32)
    starts = fbref[("Playing Time", "Starts")].values.astype(np.float32)
    matches = fbref[("Playing Time", "MP")].values.astype(np.float32)
    positions = fbref[("pos", "")].values
    leagues_raw = fbref.index.get_level_values("league").astype(str).values
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

    sub_pos = np.array([map_position(p) for p in positions])
    pos_idx = np.array([POS_TO_IDX.get(p, 4) for p in sub_pos])

    # Build base DataFrame
    df = pd.DataFrame({
        "player": players, "team": teams, "league": leagues, "season": seasons,
        "source_position": positions,
        "sub_position": sub_pos, "pos_idx": pos_idx,
        "matches": matches, "starts": starts, "minutes": minutes,
        "npg_p90": npg_p90, "assists_p90": assists_p90, "g_a_volume": g_a_volume,
    })

    # Load and merge misc stats (tackles, interceptions, fouls, crosses)
    misc_path = data_dir / "raw" / "fbref" / "player_misc_3seasons.parquet"
    if misc_path.exists():
        misc = pd.read_parquet(misc_path)
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
    shoot_path = data_dir / "raw" / "fbref" / "player_shooting_3seasons.parquet"
    if shoot_path.exists():
        shooting = pd.read_parquet(shoot_path)
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
    df["shots_p90"] = df["shots"].fillna(0) / safe_min_df * 90
    df["sot_p90"] = df["shots_on_target"].fillna(0) / safe_min_df * 90

    # Defense composite: tackles + interceptions (normalized)
    df["defense_composite"] = df["tackles_p90"] * 0.6 + df["interceptions_p90"] * 0.4
    # Possession composite: crosses + fouls drawn (proxy for ball involvement)
    df["possession_composite"] = df["crosses_p90"] * 0.5 + df["fouls_drawn_p90"] * 0.5

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
    if understat_path.exists():
        print("  加载 Understat 数据...")
        understat = pd.read_parquet(understat_path)
        
        # Normalize league names
        understat_league_map = {
            "EPL": "Premier League",
            "La_Liga": "La Liga",
            "Bundesliga": "Bundesliga",
            "Serie_A": "Serie A",
            "Ligue_1": "Ligue 1",
        }
        understat["league"] = (
            understat["league"].map(understat_league_map).fillna(understat["league"])
        )
        
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
        understat["starts"] = understat["games"].values.astype(np.float32)  # Approximate
        
        # Position mapping
        understat["sub_position"] = understat["position"].apply(map_position)
        understat["pos_idx"] = understat["sub_position"].map(POS_TO_IDX).fillna(4).astype(int)
        
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
            "sub_position", "pos_idx", "matches", "starts", "minutes",
            "npg_p90", "assists_p90", "g_a_volume",
        ]].copy()
        understat_df = understat_df.rename(
            columns={
                "player_name": "player",
                "team_title": "team",
                "position": "source_position",
            },
        )
        
        # Add missing columns with neutral defaults (50th percentile = 0 after centering)
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
            "shots_p90",
            "sot_p90",
            "defense_composite",
            "possession_composite",
        ]:
            understat_df[col] = 0.0  # Will be percentile-ranked as 0, but position-relative
        
        # Find seasons in Understat but not in FBref
        fbref_seasons = set(df["season"].unique())
        understat_only = understat_df[~understat_df["season"].isin(fbref_seasons)]
        print(f"    Understat 独有赛季: {sorted(understat_only['season'].unique())}")
        
        # Combine: FBref takes priority for overlapping seasons
        df = pd.concat([df, understat_only], ignore_index=True, sort=False)
        print(f"    合并后: {len(df)} 行")
        
        # Recompute per-90 and composite metrics for all rows (Understat rows have 0s)
        safe_min_all = np.maximum(df["minutes"].values.astype(np.float32), 1.0)
        df["tackles_p90"] = df["tackles_won"].fillna(0) / safe_min_all * 90
        df["interceptions_p90"] = df["interceptions"].fillna(0) / safe_min_all * 90
        df["crosses_p90"] = df["crosses"].fillna(0) / safe_min_all * 90
        df["fouls_drawn_p90"] = df["fouls_drawn"].fillna(0) / safe_min_all * 90
        df["defense_composite"] = df["tackles_p90"] * 0.6 + df["interceptions_p90"] * 0.4
        df["possession_composite"] = df["crosses_p90"] * 0.5 + df["fouls_drawn_p90"] * 0.5
        
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

    # Team standings
    fd = pd.read_parquet(data_dir / "raw" / "football_data" / "combined_results.parquet")
    standings_rows = []
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
    standings = pd.DataFrame(standings_rows)
    team_pts = standings.groupby(["team", "league", "season"]).agg(
        total_points=("points", "sum"),
    ).reset_index()

    return df, team_pts


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


def build_matched_results(feat, team_pts_df, team_avgs):
    """Match predicted team-season ratings with actual points.

    Teams with NaN or non-finite total_points are excluded from matching.
    """
    # Filter out teams with NaN or non-finite total_points
    valid_pts = team_pts_df.copy()
    valid_pts["total_points"] = pd.to_numeric(valid_pts["total_points"], errors="coerce")
    n_before = len(valid_pts)
    valid_pts = valid_pts[
        valid_pts["total_points"].notna() & np.isfinite(valid_pts["total_points"])
    ]
    n_excluded = n_before - len(valid_pts)

    points_lookup = {
        (str(row["team"]), str(row["league"]), str(row["season"])): float(row["total_points"])
        for _, row in valid_pts.iterrows()
    }
    rows = []
    for i, (team, league, season) in enumerate(
        zip(feat["ts_team_names"], feat["ts_leagues"], feat["ts_seasons"], strict=False)
    ):
        key = (str(team), str(league), str(season))
        if key not in points_lookup:
            continue
        rows.append(
            {
                "team": str(team),
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
    rated = pd.DataFrame(
        {
            "team": [str(team) for team in feat["ts_team_names"]],
            "league": [str(league) for league in feat["ts_leagues"]],
            "season": [str(season) for season in feat["ts_seasons"]],
        },
    ).drop_duplicates()
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
        }
    spearman = _safe_spearman(matched_df["pred_rating"], matched_df["actual_points"])
    pearson = _safe_pearson(matched_df["pred_rating"], matched_df["actual_points"])
    rank_loss = 1.0 - spearman if np.isfinite(spearman) else float("nan")
    return {
        "n_team_seasons": int(len(matched_df)),
        "spearman": spearman,
        "pearson": pearson,
        "rank_loss": rank_loss,
        "z_mse": _standardized_mse(matched_df["pred_rating"], matched_df["actual_points"]),
        "calibration_mae": calibration_mae(matched_df, n_bins=n_bins),
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
):
    """Evaluate params on a slice without letting that slice define train statistics."""
    feat_eval = build_feature_tensors(eval_df, rank_reference_df=rank_reference_df)
    ratings = compute_ratings_torch(feat_eval, params.to(device), device)
    team_avgs = compute_team_avg_ratings(feat_eval, ratings, device)
    matched_df = build_matched_results(feat_eval, team_pts_df, team_avgs)
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


def compute_input_hash(data_dir: Path) -> str:
    """Compute SHA256 hash of key input files for reproducibility."""
    import hashlib

    hasher = hashlib.sha256()
    key_files = [
        "gold/feature_store/rating_feature_matrix.parquet",
        "raw/football_data/combined_results.parquet",
        "gold/feature_store/player_ratings_optimized.parquet",
    ]
    for rel_path in key_files:
        fpath = data_dir / rel_path
        if fpath.exists():
            hasher.update(fpath.read_bytes())
    return hasher.hexdigest()[:16]


def save_model_run(
    params: np.ndarray,
    metrics: dict,
    args: argparse.Namespace | None = None,
    output_dir: Path | None = None,
    feat_hash: str | None = None,
):
    """Save model run with full provenance to data/models/runs/<timestamp>/.

    Saves:
    - optimized_params.npy
    - meta.json with: params summary, seed, input hash, metrics, position metrics,
      error case summary, composite objective weights
    """
    from datetime import UTC, datetime

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = (output_dir or Path("data/models/runs")) / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    # Save params
    np.save(run_dir / "optimized_params.npy", params)

    # Build meta
    meta = {
        "timestamp": timestamp,
        "params_shape": list(params.shape),
        "params_mean": float(params.mean()),
        "params_std": float(params.std()),
        "input_hash": feat_hash,
        "metrics": {
            k: float(v) if isinstance(v, (int, float, np.floating)) else str(v)
            for k, v in metrics.items()
        },
    }

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
            "extreme_penalty_weight": getattr(args, "extreme_penalty_weight", None),
            "prior_weight": getattr(args, "prior_weight", None),
        }

    with open(run_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"  模型运行登记已保存: {run_dir}")
    return run_dir


def _json_ready(value):
    """Convert numpy/pandas scalars and NaN values to JSON-safe objects."""
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


# ── 向量化评分 (PyTorch) ──────────────────────────────────────────────────

def build_feature_tensors(df, rank_reference_df=None):
    """预计算所有特征张量，包括防守和控球维度。

    rank_reference_df 用于把验证/测试集映射到训练集分布，避免用测试集整体分布
    计算百分位或联赛分钟中位数。
    """
    n_rows = len(df)
    reference_df = df if rank_reference_df is None else rank_reference_df

    # Per-position percentile ranks for all dimensions. For validation/test
    # slices, percentile thresholds come only from the train reference frame.
    rank_cols = {
        "npg_p90": "npg_pct",
        "assists_p90": "ast_pct",
        "g_a_volume": "vol_pct",
        "defense_composite": "def_pct",
        "possession_composite": "pos_pct",
    }
    if "npg_trend" in df.columns:
        rank_cols["npg_trend"] = "trend_pct"

    pct_df = pd.DataFrame(index=df.index)
    for src_col, out_col in rank_cols.items():
        pct_df[out_col] = _percentile_against_reference(
            df,
            reference_df,
            src_col,
        )

    npg_pct = pct_df["npg_pct"].to_numpy(dtype=np.float32)
    ast_pct = pct_df["ast_pct"].to_numpy(dtype=np.float32)
    vol_pct = pct_df["vol_pct"].to_numpy(dtype=np.float32)
    def_pct = pct_df["def_pct"].to_numpy(dtype=np.float32)
    pos_pct = pct_df["pos_pct"].to_numpy(dtype=np.float32)
    trend_pct = pct_df.get(
        "trend_pct",
        pd.Series(np.full(n_rows, 50.0, dtype=np.float32), index=df.index),
    ).to_numpy(dtype=np.float32)

    # League encoding
    league_names = sorted(df["league"].unique())
    league_to_idx = {league: i for i, league in enumerate(league_names)}
    league_idx = np.array([league_to_idx.get(league, 0) for league in df["league"].values])

    # League median minutes
    league_med = reference_df.groupby("league")["minutes"].median()
    global_minutes_median = float(pd.to_numeric(reference_df["minutes"], errors="coerce").median())
    if not np.isfinite(global_minutes_median):
        global_minutes_median = 1800.0
    league_med_arr = np.array(
        [league_med.get(league, global_minutes_median) for league in df["league"].values],
        dtype=np.float32,
    )

    # Team-season grouping (use reset index positions)
    df_reset = df.reset_index(drop=True)
    team_agg_weight = _build_team_aggregation_weights(df_reset)
    team_season_groups = df_reset.groupby(["team", "league", "season"]).groups
    ts_indices = []
    ts_team_names = []
    ts_leagues = []
    ts_seasons = []
    team_group_idx = np.empty(n_rows, dtype=np.int64)
    for (team, league, season), indices in team_season_groups.items():
        group_i = len(ts_indices)
        idx_arr = np.array(
            indices.values if hasattr(indices, "values") else list(indices),
            dtype=np.int64,
        )
        team_group_idx[idx_arr] = group_i
        ts_indices.append(idx_arr)
        ts_team_names.append(team)
        ts_leagues.append(league)
        ts_seasons.append(season)

    return {
        "N": n_rows,
        "n_team_groups": len(ts_indices),
        "team_group_idx": torch.tensor(team_group_idx, dtype=torch.long),
        "team_agg_weight": torch.tensor(team_agg_weight, dtype=torch.float32),
        "pos_idx": torch.tensor(df["pos_idx"].values, dtype=torch.long),
        "npg_pct": torch.tensor(npg_pct, dtype=torch.float32),
        "ast_pct": torch.tensor(ast_pct, dtype=torch.float32),
        "vol_pct": torch.tensor(vol_pct, dtype=torch.float32),
        "def_pct": torch.tensor(def_pct, dtype=torch.float32),
        "pos_pct": torch.tensor(pos_pct, dtype=torch.float32),
        "trend_pct": torch.tensor(trend_pct, dtype=torch.float32),
        "experience": torch.tensor(
            np.clip(
                df["experience_factor"].values
                if "experience_factor" in df.columns
                else np.ones(n_rows),
                0.5,
                1.0,
            ),
            dtype=torch.float32,
        ),
        "minutes": torch.tensor(df["minutes"].values, dtype=torch.float32),
        "starts": torch.tensor(df["starts"].values, dtype=torch.float32),
        "matches": torch.tensor(df["matches"].values, dtype=torch.float32),
        "league_med": torch.tensor(league_med_arr, dtype=torch.float32),
        "league_idx": torch.tensor(league_idx, dtype=torch.long),
        "n_leagues": len(league_names),
        "league_names": league_names,
        "ts_indices": ts_indices,
        "ts_team_names": ts_team_names,
        "ts_leagues": ts_leagues,
        "ts_seasons": ts_seasons,
        "df": df,
    }


def _build_team_aggregation_weights(df_reset: pd.DataFrame) -> np.ndarray:
    """Build robust team-season weights that do not reward raw minutes twice.

    Player ratings already include availability/reliability. For team strength,
    pure minutes weighting lets high-minute average CM/CB/GK profiles drag a
    squad above stronger but more rotated sides. This uses a capped-minutes share
    blended with a core-rotation share, approximating a squad median without
    dropping the first-team signal.
    """
    if df_reset.empty:
        return np.array([], dtype=np.float32)

    minutes = pd.to_numeric(df_reset["minutes"], errors="coerce").fillna(0.0).clip(lower=0.0)
    capped = np.sqrt(np.minimum(minutes.to_numpy(dtype=np.float64), TEAM_AGG_MINUTES_CAP))
    z = np.clip(
        (minutes.to_numpy(dtype=np.float64) - TEAM_AGG_CORE_MINUTES) / TEAM_AGG_CORE_SCALE,
        -50.0,
        50.0,
    )
    core = 1.0 / (1.0 + np.exp(-z))

    work = df_reset.loc[:, ["team", "league", "season"]].copy()
    work["capped"] = capped
    work["core"] = core
    group = work.groupby(["team", "league", "season"], sort=False)
    group_size = group["capped"].transform("size").to_numpy(dtype=np.float64)

    capped_sum = group["capped"].transform("sum").to_numpy(dtype=np.float64)
    core_sum = group["core"].transform("sum").to_numpy(dtype=np.float64)
    capped_share = np.divide(
        capped,
        capped_sum,
        out=np.divide(1.0, group_size, out=np.zeros_like(group_size), where=group_size > 0),
        where=capped_sum > 0,
    )
    core_share = np.divide(
        core,
        core_sum,
        out=np.divide(1.0, group_size, out=np.zeros_like(group_size), where=group_size > 0),
        where=core_sum > 0,
    )

    weights = (
        TEAM_AGG_CAPPED_MINUTES_BLEND * capped_share
        + (1.0 - TEAM_AGG_CAPPED_MINUTES_BLEND) * core_share
    )
    work["weight"] = weights
    weight_sum = work.groupby(["team", "league", "season"], sort=False)["weight"].transform(
        "sum",
    ).to_numpy(dtype=np.float64)
    normalized = np.divide(
        weights,
        weight_sum,
        out=np.divide(1.0, group_size, out=np.zeros_like(group_size), where=group_size > 0),
        where=weight_sum > 0,
    )
    return normalized.astype(np.float32)


def compute_ratings_torch(feat, params, device):
    """向量化评分，无循环。"""
    # Unpack parameters
    idx = 0
    # Position weights: 8×5
    pw_raw = params[idx:idx + N_POS * N_DIM].reshape(N_POS, N_DIM)
    pw = torch.softmax(pw_raw, dim=1)  # [8, 5]
    # 77 个参数仍然参与训练，但位置维度不能完全自由漂移。只用球队积分做监督时，
    # 优化器很容易把 CM/GK 的出勤或 quality 当成通用捷径；这里只封顶明显
    # 不符合角色职责的维度，超出部分回流到该位置仍可使用的其他维度。
    pw = apply_position_weight_caps(pw)
    idx += N_POS * N_DIM

    # Attack weights: 8×3
    aw_raw = params[idx:idx + N_POS * N_ATK].reshape(N_POS, N_ATK)
    aw = torch.softmax(aw_raw, dim=1)  # [8, 3]
    idx += N_POS * N_ATK

    # Availability sub-weights: 4
    avail_sw = torch.softmax(params[idx:idx + 4], dim=0)
    idx += 4

    # Quality sub-weights: 4
    qual_sw = torch.softmax(params[idx:idx + 4], dim=0)
    idx += 4

    # Scalar params
    league_log_scale = params[idx]  # raw, retained as the league-curve shape control
    idx += 1
    _rel_min_scale = torch.sigmoid(params[idx])  # retained for 77-param compatibility
    rel_starts_scale = torch.sigmoid(params[idx + 1])  # [0, 1] -> maps to [0.3, 0.7]
    idx += 2
    # Trend weight: how much to boost players who are improving
    trend_weight = torch.sigmoid(params[idx]) * 10  # [0, 10] points bonus
    idx += 1
    # Experience weight: how much to boost multi-season players
    exp_weight = torch.sigmoid(params[idx]) * 5  # [0, 5] points bonus

    # Gather position weights for each player
    pos_idx = feat["pos_idx"].to(device)
    player_pw = pw[pos_idx]  # [N, 5]
    player_aw = aw[pos_idx]  # [N, 3]

    minutes = feat["minutes"].to(device)
    starts_t = feat["starts"].to(device)
    matches_t = feat["matches"].to(device)
    league_med = feat["league_med"].to(device)

    # ── Availability ──
    min_share = torch.clamp(minutes / league_med, max=1.0) * 100
    start_rate_score = starts_t / torch.clamp(matches_t, min=1) * 100
    avail_pct = torch.clamp(matches_t / 38, max=1.0) * 100
    role_stab = torch.full_like(minutes, 50.0)

    availability = (min_share * avail_sw[0] + start_rate_score * avail_sw[1]
                    + avail_pct * avail_sw[2] + role_stab * avail_sw[3])

    # ── Attack (percentile-based, pre-computed) ──
    npg_pct = feat["npg_pct"].to(device)
    ast_pct = feat["ast_pct"].to(device)
    vol_pct = feat["vol_pct"].to(device)

    # 前场球员的进攻百分位已经在位置内排序，优化器又可能给 ST/W 很高的 attack
    # 维度权重。如果最后再按位置整体打折，会同时惩罚出勤、防守和控球，解释性较差；
    # 这里只压缩进攻维度本身，让高产前锋仍然靠真实进攻输出拿分，但避免进球/助攻
    # 单一维度把 Top 排名挤满。AM 只做轻微压缩，供未来位置映射修正后使用。
    attack_scale = torch.ones(N_POS, device=device)
    w_idx = POS_TO_IDX.get("W", 1)
    am_idx = POS_TO_IDX.get("AM", 2)
    # ST 不压缩 attack：前锋本应由进攻主导，quality cap 已防止 quality 绕路霸榜
    attack_scale[w_idx] = 0.96
    attack_scale[am_idx] = 0.97
    cm_idx = POS_TO_IDX.get("CM", 3)
    dm_idx = POS_TO_IDX.get("DM", 4)
    # FBref 粗位置会把部分边锋/前腰写成 MF。位置重判已处理明显样本；
    # 剩余 CM 的进攻输出仍应作为中场附加价值，而不是等同前场核心产量。
    attack_scale[cm_idx] = 0.92
    attack_scale[dm_idx] = 0.82

    attack = (
        npg_pct * player_aw[:, 0]
        + ast_pct * player_aw[:, 1]
        + vol_pct * player_aw[:, 2]
    ) * attack_scale[pos_idx]

    # ── Defense (percentile-based, real data) ──
    def_pct = feat["def_pct"].to(device)
    defense = def_pct  # Already percentile-ranked within position group

    # ── Possession (percentile-based, real data) ──
    pos_pct = feat["pos_pct"].to(device)
    possession = pos_pct  # Already percentile-ranked within position group

    # ── Quality ──
    quality = (npg_pct * qual_sw[0] + ast_pct * qual_sw[1]
               + def_pct * qual_sw[2] + pos_pct * qual_sw[3])
    # quality 是跨维度效率项，不应让中场通过"进攻百分位 + 出勤"获得前锋级
    # 影响力。ST 的 quality 已被 cap 限制在 0.30，不需要额外下调；
    # CM/DM 下调，避免优化器把中场 quality 当作低风险的统一捷径。
    quality_scale = torch.ones(N_POS, dtype=quality.dtype, device=device)
    quality_scale[cm_idx] = 0.88
    quality_scale[dm_idx] = 0.94
    quality = quality * quality_scale[pos_idx]

    # ── Base score ──
    base = (availability * player_pw[:, 0] + attack * player_pw[:, 1]
            + defense * player_pw[:, 2] + possession * player_pw[:, 3]
            + quality * player_pw[:, 4])

    # ── Reliability (出场时间惩罚) ──
    # 低分钟数样本仍然不可靠，但旧曲线把 500 分钟球员压到 0.3，容易把
    # 半季主力、冬窗转会和伤愈回归球员惩罚过重。这里改成更温和的线性爬坡：
    # <400 分钟保留 0.42 底分，400-1200 分钟快速恢复，>=1200 分钟视为满可信。
    min_threshold = 400.0
    min_ceiling = 1200.0
    min_floor = 0.42
    min_progress = torch.clamp(
        (minutes - min_threshold) / (min_ceiling - min_threshold),
        min=0.0,
        max=1.0,
    )
    min_rel = min_floor + (1.0 - min_floor) * min_progress

    # 首发率惩罚 (保持原有逻辑)
    sr = starts_t / torch.clamp(matches_t, min=1)
    rel_starts_ref = 0.3 + rel_starts_scale * 0.4
    start_rel = 0.85 + 0.15 * torch.clamp(sr / rel_starts_ref, max=1.0)
    reliability = min_rel * start_rel

    # ── League coefficient ──
    # 外部联赛强度只能作为温和校准，而不是硬排名：当前特征已经是跨联赛球员
    # 原始表现百分位，英超球员本身会因数据分布拿到较高基础分。如果再用线性
    # UEFA 比值，会把 Top 30 推成英超名单；如果完全不用强度先验，又会低估
    # 联赛竞争环境。这里保留 Big 5 强度先验，但用 0.14-0.20 的窄幂曲线压缩
    # 差距。上一版 0.14-0.20 的指数过窄，Ligue 1/Serie A 的高百分位球员
    # 容易被推到接近英超同档。这里改成 0.28-0.42 的中等幂曲线：弱一档
    # 联赛会被明确折扣，但不会把 La Liga/Bundesliga 顶级球员整体压扁。
    league_name_to_coeff = {
        "Premier League": 119.52,
        "La Liga": 93.00,
        "Bundesliga": 92.90,
        "Ligue 1": 83.50,
        "Serie A": 81.93,
    }
    league_names_sorted = feat["league_names"]
    coeff_values = [league_name_to_coeff.get(league, 80.0) for league in league_names_sorted]
    league_coeffs = torch.tensor(coeff_values, dtype=torch.float32, device=device)
    league_ratio = league_coeffs / torch.max(league_coeffs)
    league_curve_exponent = 0.28 + 0.14 * torch.sigmoid(league_log_scale)
    league_strength = torch.pow(league_ratio, league_curve_exponent)

    league_idx = feat["league_idx"].to(device)
    player_league_coeff = league_strength[league_idx]

    # ── Trend bonus ──
    trend_pct = feat["trend_pct"].to(device)
    trend_bonus = (trend_pct - 50) / 50 * trend_weight  # centered at 0, range [-tw, +tw]

    # ── Experience bonus ──
    experience = feat["experience"].to(device)
    exp_bonus = (experience - 0.5) / 0.5 * exp_weight  # centered at 0, range [0, ew]

    # ── Final score ──
    overall = base * reliability * player_league_coeff + trend_bonus + exp_bonus

    return overall


def compute_team_avg_ratings_torch(feat, ratings, device):
    """计算每队每赛季稳健平均评分，保持 Torch 计算图用于反向传播。"""
    group_idx = feat["team_group_idx"].to(device)
    if "team_agg_weight" in feat:
        weights = feat["team_agg_weight"].to(device)
    else:
        minutes = feat["minutes"].to(device)
        weights = torch.clamp(minutes, min=1)
    n_groups = int(feat["n_team_groups"])

    weighted_sum = torch.zeros(n_groups, dtype=ratings.dtype, device=device)
    weight_sum = torch.zeros(n_groups, dtype=ratings.dtype, device=device)
    weighted_sum = weighted_sum.index_add(0, group_idx, ratings * weights)
    weight_sum = weight_sum.index_add(0, group_idx, weights)
    return weighted_sum / torch.clamp(weight_sum, min=1e-8)


def compute_team_avg_ratings(feat, ratings, device):
    """计算每队每赛季稳健平均评分，返回 NumPy 供报告使用。"""
    return compute_team_avg_ratings_torch(feat, ratings, device).detach().cpu().numpy()


def build_team_target_tensors(feat, team_pts_df, device):
    """把可匹配的球队赛季积分预编译成张量索引，避免训练步内 pandas 查询。

    Teams with NaN or non-finite total_points are excluded.
    """
    # Filter out teams with NaN or non-finite total_points
    valid_pts = team_pts_df.copy()
    valid_pts["total_points"] = pd.to_numeric(valid_pts["total_points"], errors="coerce")
    valid_pts = valid_pts[
        valid_pts["total_points"].notna() & np.isfinite(valid_pts["total_points"])
    ]

    points_lookup = {
        (str(row["team"]), str(row["league"]), str(row["season"])): float(row["total_points"])
        for _, row in valid_pts.iterrows()
    }
    matched_group_idx = []
    actual_points = []
    for i, (team, league, season) in enumerate(
        zip(feat["ts_team_names"], feat["ts_leagues"], feat["ts_seasons"], strict=False)
    ):
        key = (str(team), str(league), str(season))
        if key in points_lookup:
            matched_group_idx.append(i)
            actual_points.append(points_lookup[key])

    return (
        torch.tensor(matched_group_idx, dtype=torch.long, device=device),
        torch.tensor(actual_points, dtype=torch.float32, device=device),
    )


def _corrcoef_torch(x, y, eps=1e-8):
    """Pearson correlation with numerical guards."""
    x = x - x.mean()
    y = y - y.mean()
    denom = torch.sqrt(torch.sum(x * x) * torch.sum(y * y)).clamp_min(eps)
    return torch.sum(x * y) / denom


def soft_rank_torch(values, temperature=4.0):
    """Dependency-free smooth ascending ranks for Spearman-style optimization."""
    temp = max(float(temperature), 1e-6)
    x = values.reshape(-1)
    pairwise = (x[:, None] - x[None, :]) / temp
    return torch.sigmoid(pairwise).sum(dim=1)


def differentiable_rank_loss(pred, actual, spearman_weight=0.7, temperature=4.0):
    """Blend soft Spearman and Pearson into a single differentiable objective."""
    pred_rank = soft_rank_torch(pred, temperature=temperature)
    actual_rank = soft_rank_torch(actual.detach(), temperature=temperature)
    soft_spearman = _corrcoef_torch(pred_rank, actual_rank)
    pearson_corr = _corrcoef_torch(pred, actual)
    w = float(np.clip(spearman_weight, 0.0, 1.0))
    objective = w * soft_spearman + (1.0 - w) * pearson_corr
    return -objective, soft_spearman, pearson_corr


def objective_torch(feat, team_pts_df, params, device, verbose=False):
    """负 soft-Spearman/Pearson 混合相关性 (最小化)。"""
    ratings = compute_ratings_torch(feat, params, device)
    team_avgs = compute_team_avg_ratings_torch(feat, ratings, device)
    matched_group_idx, actual_t = build_team_target_tensors(feat, team_pts_df, device)

    if len(matched_group_idx) < 10:
        return torch.tensor(1.0, device=device, requires_grad=True)

    pred_t = team_avgs.index_select(0, matched_group_idx)
    loss, soft_sp, pr = differentiable_rank_loss(pred_t, actual_t)

    if verbose:
        print(f"  soft-Spearman={soft_sp.item():.4f}  Pearson={pr.item():.4f}  N={len(pred_t)}")

    return loss


# ── 优化循环 ──────────────────────────────────────────────────────────────

def optimize(
    feat,
    team_pts,
    device,
    n_steps=500,
    lr=0.05,
    pop_size=32,
    spearman_weight=0.7,
    soft_rank_temperature=4.0,
    prior_strength=0.01,
    init_scale=0.35,
    patience=80,
    seed=None,
):
    """
    多起点并行优化。
    对 pop_size 组随机初始化的参数同时优化，取最优。
    """
    print(f"  设备: {device}")
    print(f"  种群: {pop_size}, 步数: {n_steps}, 学习率: {lr}")
    print(
        "  目标: "
        f"{spearman_weight:.2f}*soft-Spearman + {1-spearman_weight:.2f}*Pearson, "
        f"soft-rank温度={soft_rank_temperature}, prior={prior_strength}"
    )

    if seed is not None:
        np.random.seed(int(seed))
        torch.manual_seed(int(seed))
        if device.type == "cuda":
            torch.cuda.manual_seed_all(int(seed))

    matched_group_idx, actual_t = build_team_target_tensors(feat, team_pts, device)
    if len(matched_group_idx) < 10:
        raise ValueError("可匹配的球队赛季少于 10 个，无法稳定优化")

    prior_params = _get_default_params_tensor(device)

    # 初始化参数种群
    all_params = []
    all_losses = []
    all_final_corrs = []

    for pop_i in range(pop_size):
        # Warm-start from the explainable v3 prior, then explore around it.
        if pop_i == 0:
            params = prior_params.clone()
        else:
            params = prior_params + torch.randn(N_PARAMS, device=device) * init_scale

        # Adam optimizer
        params_t = params.clone().detach().requires_grad_(True)
        optimizer = torch.optim.AdamW([params_t], lr=lr)

        best_loss = float("inf")
        best_params = params_t.clone().detach()
        patience_counter = 0

        for _step in range(n_steps):
            optimizer.zero_grad()

            # Forward: compute ratings
            ratings = compute_ratings_torch(feat, params_t, device)
            team_avgs = compute_team_avg_ratings_torch(feat, ratings, device)
            pred_t = team_avgs.index_select(0, matched_group_idx)
            loss, soft_sp, pearson_corr = differentiable_rank_loss(
                pred_t,
                actual_t,
                spearman_weight=spearman_weight,
                temperature=soft_rank_temperature,
            )

            # Regularization: keep learned weights close to the explainable v3 prior.
            reg = prior_strength * ((params_t - prior_params) ** 2).mean()
            total_loss = loss + reg

            total_loss.backward()
            optimizer.step()

            current_loss = float(loss.detach().cpu())
            if current_loss < best_loss:
                best_loss = current_loss
                best_params = params_t.clone().detach()
                patience_counter = 0
            else:
                patience_counter += 1

            if patience_counter > patience:
                break

        # Final evaluation with Spearman (non-differentiable but correct metric)
        final_ratings = compute_ratings_torch(feat, best_params, device)
        final_team_avgs = compute_team_avg_ratings(feat, final_ratings, device)

        idx_np = matched_group_idx.detach().cpu().numpy()
        pred_arr = final_team_avgs[idx_np]
        actual_arr = actual_t.detach().cpu().numpy()
        sp, _ = spearmanr(pred_arr, actual_arr)
        pr, _ = pearsonr(pred_arr, actual_arr)

        all_params.append(best_params.cpu())
        all_losses.append(-sp)
        all_final_corrs.append((sp, pr))

        if (pop_i + 1) % 5 == 0 or pop_i == 0:
            print(f"  [{pop_i+1}/{pop_size}] best Spearman={sp:.4f}  Pearson={pr:.4f}")

    # Pick best
    best_idx = int(np.argmin(all_losses))
    best_sp, best_pr = all_final_corrs[best_idx]
    print(f"\n  最优: Spearman={best_sp:.4f}  Pearson={best_pr:.4f}  (第 {best_idx+1} 组)")

    return all_params[best_idx].to(device)


def _inv_softmax(probs):
    """Approximate inverse softmax."""
    p = np.array(probs, dtype=np.float32)
    p = np.clip(p, 1e-10, 1.0)
    return np.log(p) - np.log(p).mean()


def _get_default_params_tensor(device):
    """Default v3 weights converted to parameter tensor."""
    params = []
    for row in POSITION_DIMENSION_PRIOR:
        params.extend(_inv_softmax(row))
    for row in ATTACK_WEIGHT_PRIOR:
        params.extend(_inv_softmax(row))
    params.extend(_inv_softmax([0.45, 0.25, 0.20, 0.10]))
    params.extend(_inv_softmax(QUALITY_SUBWEIGHT_PRIOR))
    params.extend([1.0, 0.0, 0.0])  # league_log_scale, rel_min, rel_starts
    # trend_weight (sigmoid=0.5 -> 5), experience_weight (sigmoid=0.5 -> 2.5)
    params.extend([0.0, 0.0])
    return torch.tensor(params, dtype=torch.float32, device=device)


def run_cross_validation(
    df,
    team_pts,
    device,
    *,
    n_splits=3,
    test_seasons=1,
    min_train_seasons=2,
    gap_seasons=0,
    n_steps=150,
    lr=0.05,
    pop_size=8,
    spearman_weight=0.7,
    soft_rank_temperature=4.0,
    prior_strength=0.01,
    init_scale=0.35,
    patience=40,
    seed=42,
    calibration_bins=5,
):
    """Run expanding-window CV; each fold optimizes only on its train seasons."""
    splits = make_season_splits(
        df,
        n_splits=n_splits,
        test_seasons=test_seasons,
        min_train_seasons=min_train_seasons,
        gap_seasons=gap_seasons,
    )
    default_params = _get_default_params_tensor(device)
    rows = []
    for fold_idx, split in enumerate(splits, start=1):
        print(
            f"\n  CV {split.name}: train={list(split.train_seasons)} "
            f"test={list(split.test_seasons)}"
        )
        train_df = _filter_by_seasons(df, split.train_seasons)
        test_df = _filter_by_seasons(df, split.test_seasons)
        train_team_pts = _filter_by_seasons(team_pts, split.train_seasons)
        test_team_pts = _filter_by_seasons(team_pts, split.test_seasons)
        train_feat = build_feature_tensors(train_df)
        fold_params = optimize(
            train_feat,
            train_team_pts,
            device,
            n_steps=n_steps,
            lr=lr,
            pop_size=pop_size,
            spearman_weight=spearman_weight,
            soft_rank_temperature=soft_rank_temperature,
            prior_strength=prior_strength,
            init_scale=init_scale,
            patience=patience,
            seed=seed + fold_idx,
        )
        for model_name, params in [("baseline_v3", default_params), ("optimized", fold_params)]:
            for split_name, eval_df, eval_team_pts in [
                ("train", train_df, train_team_pts),
                ("test", test_df, test_team_pts),
            ]:
                evaluation = evaluate_params(
                    params,
                    eval_df,
                    eval_team_pts,
                    train_df,
                    device,
                    split_name=split_name,
                    calibration_bins=calibration_bins,
                )
                row = {
                    "fold": fold_idx,
                    "fold_name": split.name,
                    "model": model_name,
                    "split": split_name,
                    "train_seasons": ",".join(split.train_seasons),
                    "test_seasons": ",".join(split.test_seasons),
                }
                row.update(evaluation["metrics"])
                rows.append(row)
    return pd.DataFrame(rows)


def run_parameter_stability(
    train_df,
    test_df,
    train_team_pts,
    test_team_pts,
    device,
    *,
    n_runs=3,
    n_steps=150,
    lr=0.05,
    pop_size=8,
    spearman_weight=0.7,
    soft_rank_temperature=4.0,
    prior_strength=0.01,
    init_scale=0.35,
    patience=40,
    seed=42,
    calibration_bins=5,
):
    """Repeat optimization across seeds and summarize metric/parameter variance."""
    if n_runs <= 1:
        return pd.DataFrame(), {}

    train_feat = build_feature_tensors(train_df)
    rows = []
    params_rows = []
    for run_idx in range(n_runs):
        run_seed = seed + run_idx * 101
        print(f"\n  稳定性 run {run_idx + 1}/{n_runs}: seed={run_seed}")
        params = optimize(
            train_feat,
            train_team_pts,
            device,
            n_steps=n_steps,
            lr=lr,
            pop_size=pop_size,
            spearman_weight=spearman_weight,
            soft_rank_temperature=soft_rank_temperature,
            prior_strength=prior_strength,
            init_scale=init_scale,
            patience=patience,
            seed=run_seed,
        )
        train_eval = evaluate_params(
            params,
            train_df,
            train_team_pts,
            train_df,
            device,
            split_name="train",
            calibration_bins=calibration_bins,
        )
        test_eval = evaluate_params(
            params,
            test_df,
            test_team_pts,
            train_df,
            device,
            split_name="test",
            calibration_bins=calibration_bins,
        )
        rows.append(
            {
                "run": run_idx + 1,
                "seed": run_seed,
                "train_spearman": train_eval["metrics"]["spearman"],
                "test_spearman": test_eval["metrics"]["spearman"],
                "train_rank_loss": train_eval["metrics"]["rank_loss"],
                "test_rank_loss": test_eval["metrics"]["rank_loss"],
                "overfit_rank_loss_gap": (
                    test_eval["metrics"]["rank_loss"] - train_eval["metrics"]["rank_loss"]
                ),
            },
        )
        params_rows.append(params.detach().cpu().numpy())

    stability_df = pd.DataFrame(rows)
    params_matrix = np.vstack(params_rows)
    param_std = np.std(params_matrix, axis=0)
    summary = {
        "runs": int(n_runs),
        "test_spearman_mean": float(stability_df["test_spearman"].mean()),
        "test_spearman_std": float(stability_df["test_spearman"].std(ddof=0)),
        "test_spearman_min": float(stability_df["test_spearman"].min()),
        "test_spearman_max": float(stability_df["test_spearman"].max()),
        "param_std_mean": float(np.mean(param_std)),
        "param_std_max": float(np.max(param_std)),
    }
    return stability_df, summary


def _print_metric_block(title, baseline_eval, optimized_eval):
    base = baseline_eval["metrics"]
    opt = optimized_eval["metrics"]
    print(f"\n{title}")
    print("-" * 80)
    print(
        "  baseline_v3: "
        f"Spearman={base['spearman']:.4f}  Pearson={base['pearson']:.4f}  "
        f"rank_loss={base['rank_loss']:.4f}  calib_MAE={base['calibration_mae']:.2f}  "
        f"N={base['n_team_seasons']}"
    )
    print(
        "  optimized:   "
        f"Spearman={opt['spearman']:.4f}  Pearson={opt['pearson']:.4f}  "
        f"rank_loss={opt['rank_loss']:.4f}  calib_MAE={opt['calibration_mae']:.2f}  "
        f"N={opt['n_team_seasons']}"
    )
    print(
        "  improvement: "
        f"Spearman {opt['spearman'] - base['spearman']:+.4f}  "
        f"rank_loss {opt['rank_loss'] - base['rank_loss']:+.4f}"
    )


# ── 主流程 ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="球员评分权重优化器 (GPU)")
    parser.add_argument("--data_dir", type=str, default="./data",
                        help="数据目录路径 (包含 raw/ 和 gold/)")
    parser.add_argument("--steps", type=int, default=500, help="每组优化步数")
    parser.add_argument("--lr", type=float, default=0.05, help="学习率")
    parser.add_argument("--pop", type=int, default=32, help="种群大小 (并行起点数)")
    parser.add_argument("--spearman-weight", type=float, default=0.7,
                        help="soft-Spearman 在训练目标中的权重 [0,1]")
    parser.add_argument("--soft-rank-temperature", type=float, default=4.0,
                        help="soft-rank 温度；越小越接近硬排名但梯度更容易饱和")
    parser.add_argument("--prior-strength", type=float, default=0.01,
                        help="锚定 v3 默认权重的正则强度")
    parser.add_argument("--init-scale", type=float, default=0.35,
                        help="多起点围绕 v3 默认参数的随机扰动标准差")
    parser.add_argument("--patience", type=int, default=80, help="单个起点的 early-stop 耐心步数")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--test-seasons", type=int, default=1, help="最终 holdout 使用最近几个赛季")
    parser.add_argument(
        "--min-train-seasons",
        type=int,
        default=2,
        help="每个时间切分最少训练赛季数",
    )
    parser.add_argument("--gap-seasons", type=int, default=0, help="训练和测试之间跳过的赛季数")
    parser.add_argument(
        "--cv-folds",
        type=int,
        default=3,
        help="时间序列交叉验证 fold 数；0 表示跳过",
    )
    parser.add_argument("--cv-steps", type=int, default=None, help="CV 每 fold 优化步数")
    parser.add_argument("--cv-pop", type=int, default=None, help="CV 每 fold 起点数")
    parser.add_argument("--stability-runs", type=int, default=3, help="不同 seed 稳定性运行次数")
    parser.add_argument("--stability-steps", type=int, default=None, help="稳定性运行每次优化步数")
    parser.add_argument("--stability-pop", type=int, default=None, help="稳定性运行每次起点数")
    parser.add_argument("--importance-repeats", type=int, default=1, help="特征置换重要性重复次数")
    parser.add_argument("--calibration-bins", type=int, default=5, help="校准检查分箱数")
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    print("=" * 80)
    print("球员评分权重优化器 (PyTorch GPU)")
    print("=" * 80)

    # Device
    if torch.cuda.is_available():
        device = torch.device("cuda")
        print(f"\nGPU: {torch.cuda.get_device_name(0)}")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
        print("\nApple MPS (Metal)")
    else:
        device = torch.device("cpu")
        print("\nCPU (没有 GPU 加速)")

    # Load data
    print("\n[1] 加载数据...")
    t0 = time.time()
    df, team_pts = load_data(data_dir)
    print(f"  球员: {len(df)}, 球队赛季: {len(team_pts)}")
    print(f"  耗时: {time.time()-t0:.1f}s")

    # Compute input hash for reproducibility
    feat_hash = compute_input_hash(data_dir)
    print(f"  输入哈希: {feat_hash}")

    print("\n[2] 时间切分...")
    holdout = make_holdout_split(
        df,
        test_seasons=args.test_seasons,
        min_train_seasons=args.min_train_seasons,
        gap_seasons=args.gap_seasons,
    )
    train_df = _filter_by_seasons(df, holdout.train_seasons)
    test_df = _filter_by_seasons(df, holdout.test_seasons)
    train_team_pts = _filter_by_seasons(team_pts, holdout.train_seasons)
    test_team_pts = _filter_by_seasons(team_pts, holdout.test_seasons)
    print(f"  train seasons: {list(holdout.train_seasons)}")
    print(f"  test seasons:  {list(holdout.test_seasons)}")
    print(f"  train players={len(train_df)}, test players={len(test_df)}")

    print("\n[3] 基线 (v3 默认权重, 不训练)...")
    default_params = _get_default_params_tensor(device)
    baseline_train_eval = evaluate_params(
        default_params,
        train_df,
        train_team_pts,
        train_df,
        device,
        split_name="train",
        calibration_bins=args.calibration_bins,
    )
    baseline_test_eval = evaluate_params(
        default_params,
        test_df,
        test_team_pts,
        train_df,
        device,
        split_name="test",
        calibration_bins=args.calibration_bins,
    )
    print(
        f"  train Spearman={baseline_train_eval['metrics']['spearman']:.4f}  "
        f"test Spearman={baseline_test_eval['metrics']['spearman']:.4f}"
    )

    print(f"\n[4] 只在训练赛季优化 (pop={args.pop}, steps={args.steps}, lr={args.lr})...")
    t0 = time.time()
    train_feat = build_feature_tensors(train_df)
    best_params = optimize(
        train_feat,
        train_team_pts,
        device,
        n_steps=args.steps,
        lr=args.lr,
        pop_size=args.pop,
        spearman_weight=args.spearman_weight,
        soft_rank_temperature=args.soft_rank_temperature,
        prior_strength=args.prior_strength,
        init_scale=args.init_scale,
        patience=args.patience,
        seed=args.seed,
    )
    print(f"  总耗时: {time.time()-t0:.1f}s")

    optimized_train_eval = evaluate_params(
        best_params,
        train_df,
        train_team_pts,
        train_df,
        device,
        split_name="train",
        calibration_bins=args.calibration_bins,
    )
    optimized_test_eval = evaluate_params(
        best_params,
        test_df,
        test_team_pts,
        train_df,
        device,
        split_name="test",
        calibration_bins=args.calibration_bins,
    )

    print("\n[5] Train/Test 对比:")
    _print_metric_block("  训练集", baseline_train_eval, optimized_train_eval)
    _print_metric_block("  Holdout 测试集", baseline_test_eval, optimized_test_eval)
    overfit_gap = (
        optimized_test_eval["metrics"]["rank_loss"] - optimized_train_eval["metrics"]["rank_loss"]
    )
    print(f"\n  过拟合检查: test_rank_loss - train_rank_loss = {overfit_gap:+.4f}")

    print("\n[6] 优化后权重:")
    print("-" * 80)
    best_params_cpu = best_params.detach().cpu()
    pw_raw = best_params_cpu[:N_POS * N_DIM].reshape(N_POS, N_DIM)
    pw = apply_position_weight_caps(torch.softmax(pw_raw, dim=1)).cpu().numpy()
    print(f"{'位置':<5} {'出勤':>7} {'进攻':>7} {'防守':>7} {'控球':>7} {'质量':>7}")
    print("-" * 80)
    for i, pos in enumerate(POSITIONS):
        print(
            f"{pos:<5} {pw[i,0]:>7.4f} {pw[i,1]:>7.4f} "
            f"{pw[i,2]:>7.4f} {pw[i,3]:>7.4f} {pw[i,4]:>7.4f}"
        )

    # Attack weights
    aw_raw = best_params_cpu[N_POS * N_DIM:N_POS * N_DIM + N_POS * N_ATK].reshape(
        N_POS,
        N_ATK,
    )
    aw = torch.softmax(aw_raw, dim=1).cpu().numpy()
    print(f"\n{'位置':<5} {'npxG_p90':>9} {'ast_p90':>9} {'G+A_vol':>9}")
    print("-" * 40)
    for i, pos in enumerate(POSITIONS):
        print(f"{pos:<5} {aw[i,0]:>9.4f} {aw[i,1]:>9.4f} {aw[i,2]:>9.4f}")

    print("\n[7] Holdout 球队覆盖率:")
    holdout_coverage = optimized_test_eval["coverage"]
    if holdout_coverage.empty:
        print("  没有可报告的球队覆盖率")
    else:
        for _, row in holdout_coverage.iterrows():
            print(
                f"  {row['league']:<22} {row['season']:<8} "
                f"matched={int(row['matched_teams']):>2}/"
                f"{int(row['target_teams']):<2} "
                f"rated={int(row['rated_teams']):>2} "
                f"coverage={row['coverage']:.2f}"
            )

    print("\n[8] Holdout 联赛分层评估:")
    holdout_league_metrics = league_metrics(
        optimized_test_eval["matched"],
        min_n=5,
        calibration_bins=args.calibration_bins,
    )
    if holdout_league_metrics.empty:
        print("  样本不足，未生成联赛分层指标")
    else:
        for _, row in holdout_league_metrics.iterrows():
            print(
                f"  {row['league']:<22} Spearman={row['spearman']:.3f}  "
                f"Pearson={row['pearson']:.3f}  calib_MAE={row['calibration_mae']:.2f}  "
                f"N={int(row['n_team_seasons'])}"
            )

    print("\n[9] Holdout 校准检查:")
    calibration_test = optimized_test_eval["calibration"]
    for _, row in calibration_test.iterrows():
        print(
            f"  bin={int(row['bin']) if pd.notna(row['bin']) else -1} "
            f"N={int(row['n'])} "
            f"pred_pct={row['pred_percentile_mean']:.1f} "
            f"actual_pct={row['actual_percentile_mean']:.1f} "
            f"gap={row['calibration_gap']:+.1f}"
        )

    cv_metrics = pd.DataFrame()
    cv_error = None
    if args.cv_folds > 0:
        print("\n[10] 时间序列交叉验证:")
        try:
            cv_metrics = run_cross_validation(
                df,
                team_pts,
                device,
                n_splits=args.cv_folds,
                test_seasons=args.test_seasons,
                min_train_seasons=args.min_train_seasons,
                gap_seasons=args.gap_seasons,
                n_steps=args.cv_steps or max(50, args.steps // 3),
                lr=args.lr,
                pop_size=args.cv_pop or max(2, args.pop // 4),
                spearman_weight=args.spearman_weight,
                soft_rank_temperature=args.soft_rank_temperature,
                prior_strength=args.prior_strength,
                init_scale=args.init_scale,
                patience=min(args.patience, 40),
                seed=args.seed,
                calibration_bins=args.calibration_bins,
            )
            cv_test = cv_metrics.loc[
                (cv_metrics["model"] == "optimized") & (cv_metrics["split"] == "test")
            ]
            base_test = cv_metrics.loc[
                (cv_metrics["model"] == "baseline_v3") & (cv_metrics["split"] == "test")
            ]
            print(
                "  optimized test Spearman: "
                f"mean={cv_test['spearman'].mean():.4f}, "
                f"std={cv_test['spearman'].std(ddof=0):.4f}"
            )
            print(
                "  baseline_v3 test Spearman: "
                f"mean={base_test['spearman'].mean():.4f}, "
                f"std={base_test['spearman'].std(ddof=0):.4f}"
            )
        except ValueError as error:
            cv_error = str(error)
            print(f"  跳过 CV: {cv_error}")

    stability_df = pd.DataFrame()
    stability_summary = {}
    if args.stability_runs > 1:
        print("\n[11] 参数稳定性:")
        stability_df, stability_summary = run_parameter_stability(
            train_df,
            test_df,
            train_team_pts,
            test_team_pts,
            device,
            n_runs=args.stability_runs,
            n_steps=args.stability_steps or max(50, args.steps // 3),
            lr=args.lr,
            pop_size=args.stability_pop or max(2, args.pop // 4),
            spearman_weight=args.spearman_weight,
            soft_rank_temperature=args.soft_rank_temperature,
            prior_strength=args.prior_strength,
            init_scale=args.init_scale,
            patience=min(args.patience, 40),
            seed=args.seed,
            calibration_bins=args.calibration_bins,
        )
        print(
            "  test Spearman: "
            f"mean={stability_summary['test_spearman_mean']:.4f}, "
            f"std={stability_summary['test_spearman_std']:.4f}, "
            f"min={stability_summary['test_spearman_min']:.4f}, "
            f"max={stability_summary['test_spearman_max']:.4f}"
        )
        print(
            "  param std: "
            f"mean={stability_summary['param_std_mean']:.4f}, "
            f"max={stability_summary['param_std_max']:.4f}"
        )

    feature_importance = pd.DataFrame()
    if args.importance_repeats > 0:
        print("\n[12] 特征置换重要性 (Holdout):")
        feature_importance = permutation_feature_importance(
            best_params,
            test_df,
            test_team_pts,
            train_df,
            device,
            n_repeats=args.importance_repeats,
            seed=args.seed,
            calibration_bins=args.calibration_bins,
        )
        if feature_importance.empty:
            print("  样本不足，未生成特征重要性")
        else:
            for _, row in feature_importance.head(10).iterrows():
                print(
                    f"  {row['feature']:<24} "
                    f"Spearman drop={row['spearman_drop_mean']:+.4f}"
                )

    # Save
    output = data_dir / "gold" / "feature_store"
    output.mkdir(parents=True, exist_ok=True)
    np.save(output / "optimized_params.npy", best_params.detach().cpu().numpy())
    print(f"\n[13] 参数已保存: {output / 'optimized_params.npy'}")

    # Save model run registry
    try:
        save_model_run(
            params=best_params.cpu().numpy(),
            metrics=optimized_test_eval["metrics"],
            args=args,
            output_dir=data_dir / "models" / "runs",
            feat_hash=feat_hash,
        )
    except Exception as exc:
        print(f"  模型运行登记保存失败: {exc}")

    holdout_predictions = optimized_test_eval["matched"].rename(
        columns={"pred_rating": "optimized_rating"},
    )
    baseline_holdout = baseline_test_eval["matched"].loc[
        :,
        ["team", "league", "season", "pred_rating"],
    ].rename(columns={"pred_rating": "baseline_v3_rating"})
    holdout_predictions = holdout_predictions.merge(
        baseline_holdout,
        on=["team", "league", "season"],
        how="left",
    )
    holdout_predictions.to_parquet(output / "rating_holdout_predictions.parquet", index=False)
    if not cv_metrics.empty:
        cv_metrics.to_parquet(output / "rating_cv_metrics.parquet", index=False)
    if not stability_df.empty:
        stability_df.to_parquet(output / "rating_parameter_stability.parquet", index=False)
    if not feature_importance.empty:
        feature_importance.to_parquet(output / "rating_feature_importance.parquet", index=False)
    if not holdout_league_metrics.empty:
        holdout_league_metrics.to_parquet(output / "rating_league_metrics.parquet", index=False)
    if not holdout_coverage.empty:
        holdout_coverage.to_parquet(output / "rating_team_coverage.parquet", index=False)
    calibration_test.to_parquet(output / "rating_calibration_test.parquet", index=False)

    meta = {
        "optimizer": "adamw_soft_spearman",
        "metric_scope": "holdout_test",
        "n_params": N_PARAMS,
        "device": str(device),
        "seed": args.seed,
        "pop": args.pop,
        "steps": args.steps,
        "lr": args.lr,
        "spearman_weight": args.spearman_weight,
        "soft_rank_temperature": args.soft_rank_temperature,
        "prior_strength": args.prior_strength,
        "init_scale": args.init_scale,
        "patience": args.patience,
        "holdout": {
            "train_seasons": list(holdout.train_seasons),
            "test_seasons": list(holdout.test_seasons),
            "baseline_train": baseline_train_eval["metrics"],
            "baseline_test": baseline_test_eval["metrics"],
            "optimized_train": optimized_train_eval["metrics"],
            "optimized_test": optimized_test_eval["metrics"],
            "overfit_rank_loss_gap": overfit_gap,
        },
        "team_aggregation": team_aggregation_config(),
        "baseline_spearman": baseline_test_eval["metrics"]["spearman"],
        "baseline_pearson": baseline_test_eval["metrics"]["pearson"],
        "optimized_spearman": optimized_test_eval["metrics"]["spearman"],
        "optimized_pearson": optimized_test_eval["metrics"]["pearson"],
        "cv": {
            "folds": args.cv_folds,
            "error": cv_error,
            "metrics": cv_metrics,
        },
        "stability": {
            "runs": args.stability_runs,
            "summary": stability_summary,
            "runs_detail": stability_df,
        },
        "feature_importance": feature_importance,
        "league_metrics": holdout_league_metrics,
        "team_coverage": holdout_coverage,
        "calibration_test": calibration_test,
        "n_players": int(len(df)),
        "n_train_players": int(len(train_df)),
        "n_test_players": int(len(test_df)),
        "n_team_seasons": int(optimized_test_eval["metrics"]["n_team_seasons"]),
    }
    (output / "optimized_params_meta.json").write_text(
        json.dumps(_json_ready(meta), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  参数元数据已保存: {output / 'optimized_params_meta.json'}")

    # Save re-rated players
    all_feat = build_feature_tensors(df, rank_reference_df=train_df)
    all_ratings = compute_ratings_torch(all_feat, best_params, device)
    scored_df = df.copy()
    scored_df["optimized_score"] = all_ratings.detach().cpu().numpy()
    scored_df = scored_df.sort_values("optimized_score", ascending=False)
    scored_df.to_parquet(output / "player_ratings_optimized.parquet", index=False)
    print(f"  球员评分已保存: {output / 'player_ratings_optimized.parquet'}")

    print("\n  Top 20 (优化后):")
    print("-" * 80)
    for i, (_, row) in enumerate(scored_df.head(20).iterrows(), 1):
        print(f"  {i:>3}  {row['player']:<28} {row['team']:<22} "
              f"{row['sub_position']:<3} {row['optimized_score']:>6.1f}")


if __name__ == "__main__":
    main()
