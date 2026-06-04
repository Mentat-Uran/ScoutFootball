#!/usr/bin/env python3
"""
球员评分权重优化器 — PyTorch GPU 版本 (v2)
支持 FBref + Understat 双数据源，覆盖 10 赛季

在 Windows + RTX 5070 Ti 上运行，几秒完成一次优化循环。

使用方法 (Windows):
  1. pip install torch pandas numpy scipy pyarrow
  2. 把 data/ 目录复制到 Windows 机器上
  3. python optimize_ratings_gpu_v2.py --data_dir ./data

或在 Mac 上用 CPU 也能跑 (会慢一些但比 scipy 快很多)。
"""

from __future__ import annotations

import argparse
import time
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
N_PARAMS = N_POS * N_DIM + N_POS * N_ATK + 4 + 4 + 3 + 2  # = 77


def map_position(pos_str):
    """Map position string to sub-position."""
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


def map_understat_position(pos_str):
    """Map Understat position to sub-position."""
    if not isinstance(pos_str, str):
        return "CM"
    s = pos_str.upper()
    if "GK" in s:
        return "GK"
    if "F" in s and "M" in s:
        return "W"
    if "M" in s and "F" in s:
        return "AM"
    if "D" in s and "M" in s:
        return "FB"
    if "M" in s and "D" in s:
        return "DM"
    if "F" in s:
        return "ST"
    if "D" in s:
        return "CB"
    if "M" in s:
        return "CM"
    return "CM"


# ── 数据加载 ──────────────────────────────────────────────────────────────


def load_fbref_data(data_dir: Path) -> pd.DataFrame:
    """加载 FBref 球员数据 (standard + misc + shooting)。"""
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
    leagues = np.array([league_name_map.get(l, l) for l in leagues_raw])

    npg = goals - pk
    safe_min = np.maximum(minutes, 1.0)
    npg_p90 = npg / safe_min * 90
    assists_p90 = assists_col / safe_min * 90
    g_a_volume = npg + assists_col

    sub_pos = np.array([map_position(p) for p in positions])
    pos_idx = np.array([POS_TO_IDX.get(p, 4) for p in sub_pos])

    # Build base DataFrame
    df = pd.DataFrame({
        "player": players,
        "team": teams,
        "league": leagues,
        "season": seasons,
        "sub_position": sub_pos,
        "pos_idx": pos_idx,
        "matches": matches,
        "starts": starts,
        "minutes": minutes,
        "npg_p90": npg_p90,
        "assists_p90": assists_p90,
        "g_a_volume": g_a_volume,
        "source": "fbref",
    })

    # Load and merge misc stats
    misc_path = data_dir / "raw" / "fbref" / "player_misc_3seasons.parquet"
    if misc_path.exists():
        misc = pd.read_parquet(misc_path)
        misc_idx = misc.index.to_frame(index=False)
        misc_league_norm = misc_idx["league"].map(league_name_map).fillna(misc_idx["league"])
        misc_data = pd.DataFrame({
            "merge_key": (
                misc_idx["player"].astype(str)
                + "|"
                + misc_league_norm.astype(str)
                + "|"
                + misc_idx["season"].astype(str)
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
            df["player"].astype(str) + "|" + df["league"].astype(str) + "|" + df["season"].astype(str)
        )
        df = df.merge(misc_data, on="merge_key", how="left")
        df = df.drop(columns=["merge_key"])
    else:
        for col in ["tackles_won", "interceptions", "fouls", "fouls_drawn", "crosses", "yellow_cards"]:
            df[col] = np.nan

    # Load and merge shooting stats
    shoot_path = data_dir / "raw" / "fbref" / "player_shooting_3seasons.parquet"
    if shoot_path.exists():
        shooting = pd.read_parquet(shoot_path)
        shoot_idx = shooting.index.to_frame(index=False)
        shoot_league_norm = shoot_idx["league"].map(league_name_map).fillna(shoot_idx["league"])
        shoot_data = pd.DataFrame({
            "merge_key": (
                shoot_idx["player"].astype(str)
                + "|"
                + shoot_league_norm.astype(str)
                + "|"
                + shoot_idx["season"].astype(str)
            ),
            "shots": pd.to_numeric(shooting[("Standard", "Sh")], errors="coerce").values,
            "shots_on_target": pd.to_numeric(shooting[("Standard", "SoT")], errors="coerce").values,
            "shot_accuracy": pd.to_numeric(shooting[("Standard", "SoT%")], errors="coerce").values,
        })
        shoot_data = shoot_data.drop_duplicates(subset=["merge_key"], keep="first")
        df["merge_key"] = (
            df["player"].astype(str) + "|" + df["league"].astype(str) + "|" + df["season"].astype(str)
        )
        df = df.merge(shoot_data, on="merge_key", how="left")
        df = df.drop(columns=["merge_key"])
    else:
        for col in ["shots", "shots_on_target", "shot_accuracy"]:
            df[col] = np.nan

    return df


def load_understat_data(data_dir: Path) -> pd.DataFrame:
    """加载 Understat 球员数据 (10赛季)。"""
    understat_path = data_dir / "raw" / "understat" / "players_10seasons.parquet"
    if not understat_path.exists():
        print("  警告: Understat 数据不存在，跳过")
        return pd.DataFrame()

    df = pd.read_parquet(understat_path)

    # Normalize league names
    league_name_map = {
        "EPL": "Premier League",
        "La_Liga": "La Liga",
        "Bundesliga": "Bundesliga",
        "Serie_A": "Serie A",
        "Ligue_1": "Ligue 1",
    }
    df["league"] = df["league"].map(league_name_map).fillna(df["league"])

    # Convert numeric columns
    for col in ["games", "time", "goals", "xG", "assists", "xA", "npxG", "shots", "key_passes", "xGChain", "xGBuildup"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Calculate per-90 metrics
    safe_min = np.maximum(df["time"].values.astype(np.float32), 1.0)
    df["minutes"] = df["time"].values.astype(np.float32)
    df["matches"] = df["games"].values.astype(np.float32)
    df["starts"] = df["games"].values.astype(np.float32)  # Approximate

    # Position mapping
    df["sub_position"] = df["position"].apply(map_understat_position)
    df["pos_idx"] = df["sub_position"].map(POS_TO_IDX).fillna(4).astype(int)

    # Per-90 metrics
    df["npg_p90"] = (df["goals"].values - df["goals"].values * 0.1) / safe_min * 90  # Approximate non-penalty goals
    df["assists_p90"] = df["assists"].values / safe_min * 90
    df["g_a_volume"] = df["goals"].values + df["assists"].values

    # xG metrics (unique to Understat)
    df["xg_p90"] = df["xG"].values / safe_min * 90
    df["xa_p90"] = df["xA"].values / safe_min * 90
    df["npxg_p90"] = df["npxG"].values / safe_min * 90
    df["xgchain_p90"] = df["xGChain"].values / safe_min * 90
    df["xgbuildup_p90"] = df["xGBuildup"].values / safe_min * 90

    # Select and rename columns
    result = df[[
        "player_name", "team_title", "league", "season",
        "sub_position", "pos_idx", "matches", "starts", "minutes",
        "npg_p90", "assists_p90", "g_a_volume",
        "xg_p90", "xa_p90", "npxg_p90", "xgchain_p90", "xgbuildup_p90",
    ]].copy()
    result = result.rename(columns={"player_name": "player", "team_title": "team"})
    result["source"] = "understat"

    # Add missing columns with NaN
    for col in ["tackles_won", "interceptions", "fouls", "fouls_drawn", "crosses", "yellow_cards", "shots", "shots_on_target", "shot_accuracy"]:
        result[col] = np.nan

    return result


def load_data(data_dir: Path):
    """加载 FBref + Understat 数据 + Football-Data 球队积分。"""
    print("  加载 FBref 数据...")
    fbref_df = load_fbref_data(data_dir)
    print(f"    FBref: {len(fbref_df)} 行")

    print("  加载 Understat 数据...")
    understat_df = load_understat_data(data_dir)
    print(f"    Understat: {len(understat_df)} 行")

    # Merge datasets
    if not understat_df.empty:
        # Find seasons in Understat but not in FBref
        fbref_seasons = set(fbref_df["season"].unique())
        understat_only = understat_df[~understat_df["season"].isin(fbref_seasons)]
        print(f"    Understat 独有赛季: {sorted(understat_only['season'].unique())}")

        # Combine: FBref takes priority for overlapping seasons
        df = pd.concat([fbref_df, understat_only], ignore_index=True, sort=False)
    else:
        df = fbref_df

    print(f"  合并后: {len(df)} 行")

    # Compute per-90 defensive/possession metrics
    safe_min_df = df["minutes"].values.astype(np.float32)
    safe_min_df = np.maximum(safe_min_df, 1.0)
    df["tackles_p90"] = df["tackles_won"].fillna(0) / safe_min_df * 90
    df["interceptions_p90"] = df["interceptions"].fillna(0) / safe_min_df * 90
    df["crosses_p90"] = df["crosses"].fillna(0) / safe_min_df * 90
    df["fouls_drawn_p90"] = df["fouls_drawn"].fillna(0) / safe_min_df * 90
    df["shots_p90"] = df["shots"].fillna(0) / safe_min_df * 90
    df["sot_p90"] = df["shots_on_target"].fillna(0) / safe_min_df * 90

    # Defense composite
    df["defense_composite"] = df["tackles_p90"] * 0.6 + df["interceptions_p90"] * 0.4
    # Possession composite
    df["possession_composite"] = df["crosses_p90"] * 0.5 + df["fouls_drawn_p90"] * 0.5

    # Cross-season trend
    df = df.sort_values(["player", "season"])
    df["season_rank"] = df.groupby("player").cumcount()
    df["total_seasons"] = df.groupby("player")["season"].transform("count")

    # Per-player stats across seasons
    player_agg = df.groupby("player").agg(
        avg_npg_p90=("npg_p90", "mean"),
        avg_defense=("defense_composite", "mean"),
        avg_possession=("possession_composite", "mean"),
    ).reset_index()
    player_agg.columns = ["player", "career_avg_npg", "career_avg_def", "career_avg_pos"]

    # Latest season stats
    latest = df.sort_values("season", ascending=False).drop_duplicates(subset=["player"], keep="first")
    latest_stats = latest[["player", "npg_p90", "defense_composite", "possession_composite"]].copy()
    latest_stats.columns = ["player", "latest_npg", "latest_def", "latest_pos"]

    # Merge trend features
    df = df.merge(player_agg, on="player", how="left")
    df = df.merge(latest_stats, on="player", how="left")

    # Trend = latest - career_avg (positive = improving)
    df["npg_trend"] = df["latest_npg"] - df["career_avg_npg"]
    df["def_trend"] = df["latest_def"] - df["career_avg_def"]
    df["pos_trend"] = df["latest_pos"] - df["career_avg_pos"]

    # Experience factor
    df["experience_factor"] = np.clip(df["total_seasons"] / 3, 0.5, 1.0)

    df = df.sort_values("minutes", ascending=False)
    df = df.drop_duplicates(subset=["player", "season", "league"], keep="first")

    # Team standings from Football-Data
    print("  加载 Football-Data 球队积分...")
    fd = pd.read_parquet(data_dir / "raw" / "football_data" / "combined_results.parquet")
    standings_rows = []
    for _, row in fd.iterrows():
        season = str(row.get("season", ""))
        league = str(row.get("league", ""))
        home, away = str(row["HomeTeam"]), str(row["AwayTeam"])
        hg, ag = float(row["FTHG"]), float(row["FTAG"])
        hp = 3 if hg > ag else (1 if hg == ag else 0)
        ap = 3 - hp if hg != ag else 1
        standings_rows.append({"team": home, "league": league, "season": season, "points": hp, "gf": hg, "ga": ag})
        standings_rows.append({"team": away, "league": league, "season": season, "points": ap, "gf": ag, "ga": hg})
    standings = pd.DataFrame(standings_rows)
    team_pts = standings.groupby(["team", "league", "season"]).agg(
        total_points=("points", "sum"),
    ).reset_index()
    print(f"    球队赛季: {len(team_pts)} 个")

    return df, team_pts


def make_holdout_split(
    df: pd.DataFrame,
    test_seasons: list[str] | int | None = None,
    min_train_seasons: int = 3,
    gap_seasons: int = 0,
):
    """Create train/test split by season."""
    all_seasons = sorted(df["season"].unique())
    
    if test_seasons is None:
        # Default: use last season as test
        test_seasons_list = [all_seasons[-1]]
    elif isinstance(test_seasons, int):
        # If integer, take last N seasons as test
        test_seasons_list = all_seasons[-test_seasons:]
    else:
        test_seasons_list = test_seasons
    
    train_seasons = [s for s in all_seasons if s not in test_seasons_list]
    
    # Return a simple object with attributes for easy access
    class SplitResult:
        def __init__(self, train, test, all_s):
            self.train_seasons = train
            self.test_seasons = test
            self.all_seasons = all_s
    
    return SplitResult(train_seasons, test_seasons_list, all_seasons)


def _filter_by_seasons(df: pd.DataFrame, seasons: list[str]) -> pd.DataFrame:
    """Filter DataFrame to specific seasons."""
    return df[df["season"].isin(seasons)].copy()


def evaluate_params(
    params,
    df: pd.DataFrame,
    team_pts: pd.DataFrame,
    reference_df: pd.DataFrame,
    device,
    split_name: str = "train",
) -> dict:
    """Evaluate parameters on a dataset."""
    feat = build_feature_tensors(df)
    ratings = compute_ratings_torch(feat, params, device)
    team_avgs = compute_team_avg_ratings(feat, ratings, device)
    
    # Match with standings
    matched_records = []
    for i in range(len(feat["ts_team_names"])):
        mask = (
            (team_pts["team"] == feat["ts_team_names"][i])
            & (team_pts["league"] == feat["ts_leagues"][i])
            & (team_pts["season"] == feat["ts_seasons"][i])
        )
        matched = team_pts.loc[mask, "total_points"]
        if len(matched) > 0:
            matched_records.append({
                "team": feat["ts_team_names"][i],
                "league": feat["ts_leagues"][i],
                "season": feat["ts_seasons"][i],
                "pred_rating": float(team_avgs[i]),
                "actual_points": float(matched.values[0]),
            })
    
    matched_df = pd.DataFrame(matched_records)
    
    if len(matched_df) < 5:
        return {
            "split": split_name,
            "metrics": {"spearman": 0.0, "pearson": 0.0, "n": 0},
            "matched": matched_df,
        }
    
    sp, _ = spearmanr(matched_df["pred_rating"], matched_df["actual_points"])
    pr, _ = pearsonr(matched_df["pred_rating"], matched_df["actual_points"])
    
    return {
        "split": split_name,
        "metrics": {"spearman": float(sp), "pearson": float(pr), "n": len(matched_df)},
        "matched": matched_df,
    }


def league_metrics(matched_df: pd.DataFrame, min_n: int = 5) -> pd.DataFrame:
    """Compute per-league metrics."""
    results = []
    for league in sorted(matched_df["league"].unique()):
        lm = matched_df[matched_df["league"] == league]
        if len(lm) >= min_n:
            sp, _ = spearmanr(lm["pred_rating"], lm["actual_points"])
            pr, _ = pearsonr(lm["pred_rating"], lm["actual_points"])
            results.append({
                "league": league,
                "spearman": float(sp),
                "pearson": float(pr),
                "n": len(lm),
            })
    return pd.DataFrame(results)

# ── 向量化评分 (PyTorch) ──────────────────────────────────────────────────


def build_feature_tensors(df):
    """预计算所有特征张量，包括防守和控球维度。"""
    N = len(df)

    # Per-position percentile ranks for all dimensions
    pos_groups = {}
    for pos_name, pos_i in POS_TO_IDX.items():
        mask = df["pos_idx"].values == pos_i
        if mask.sum() == 0:
            continue
        pos_groups[pos_i] = {
            "mask": mask,
            "npg_p90": df["npg_p90"].values[mask],
            "assists_p90": df["assists_p90"].values[mask],
            "g_a_volume": df["g_a_volume"].values[mask],
            "defense_composite": df["defense_composite"].values[mask],
            "possession_composite": df["possession_composite"].values[mask],
        }

    # Compute percentiles within position group
    npg_pct = np.full(N, 50.0, dtype=np.float32)
    ast_pct = np.full(N, 50.0, dtype=np.float32)
    vol_pct = np.full(N, 50.0, dtype=np.float32)
    def_pct = np.full(N, 50.0, dtype=np.float32)
    pos_pct = np.full(N, 50.0, dtype=np.float32)
    trend_pct = np.full(N, 50.0, dtype=np.float32)

    for pos_i, pg in pos_groups.items():
        mask = pg["mask"]
        n = mask.sum()
        if n == 0:
            continue
        pg["npg_trend"] = df["npg_trend"].values[mask] if "npg_trend" in df.columns else np.zeros(n)
        for j, idx in enumerate(np.where(mask)[0]):
            npg_pct[idx] = (pg["npg_p90"] < pg["npg_p90"][j]).sum() / n * 100
            ast_pct[idx] = (pg["assists_p90"] < pg["assists_p90"][j]).sum() / n * 100
            vol_pct[idx] = (pg["g_a_volume"] < pg["g_a_volume"][j]).sum() / n * 100
            def_pct[idx] = (pg["defense_composite"] < pg["defense_composite"][j]).sum() / n * 100
            pos_pct[idx] = (pg["possession_composite"] < pg["possession_composite"][j]).sum() / n * 100
            trend_pct[idx] = (pg["npg_trend"] < pg["npg_trend"][j]).sum() / n * 100

    # League encoding
    league_names = sorted(df["league"].unique())
    league_to_idx = {l: i for i, l in enumerate(league_names)}
    league_idx = np.array([league_to_idx.get(l, 0) for l in df["league"].values])

    # League median minutes
    league_med = df.groupby("league")["minutes"].median()
    league_med_arr = np.array([league_med.get(l, 1800) for l in df["league"].values], dtype=np.float32)

    # Team-season grouping
    df_reset = df.reset_index(drop=True)
    team_season_groups = df_reset.groupby(["team", "league", "season"]).groups
    ts_indices = []
    ts_team_names = []
    ts_leagues = []
    ts_seasons = []
    for (team, league, season), indices in team_season_groups.items():
        ts_indices.append(indices.values if hasattr(indices, "values") else list(indices))
        ts_team_names.append(team)
        ts_leagues.append(league)
        ts_seasons.append(season)

    return {
        "N": N,
        "pos_idx": torch.tensor(df["pos_idx"].values, dtype=torch.long),
        "npg_pct": torch.tensor(npg_pct, dtype=torch.float32),
        "ast_pct": torch.tensor(ast_pct, dtype=torch.float32),
        "vol_pct": torch.tensor(vol_pct, dtype=torch.float32),
        "def_pct": torch.tensor(def_pct, dtype=torch.float32),
        "pos_pct": torch.tensor(pos_pct, dtype=torch.float32),
        "trend_pct": torch.tensor(trend_pct, dtype=torch.float32),
        "experience": torch.tensor(
            np.clip(df["experience_factor"].values if "experience_factor" in df.columns else np.ones(N), 0.5, 1.0),
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


def compute_ratings_torch(feat, params, device):
    """向量化评分，无循环。"""
    # Unpack parameters
    idx = 0
    # Position weights: 8×5
    pw_raw = params[idx : idx + N_POS * N_DIM].reshape(N_POS, N_DIM)
    pw = torch.softmax(pw_raw, dim=1)  # [8, 5]
    idx += N_POS * N_DIM

    # Attack weights: 8×3
    aw_raw = params[idx : idx + N_POS * N_ATK].reshape(N_POS, N_ATK)
    aw = torch.softmax(aw_raw, dim=1)  # [8, 3]
    idx += N_POS * N_ATK

    # Availability sub-weights: 4
    avail_sw = torch.softmax(params[idx : idx + 4], dim=0)
    idx += 4

    # Quality sub-weights: 4
    qual_sw = torch.softmax(params[idx : idx + 4], dim=0)
    idx += 4

    # Scalar params
    league_log_scale = params[idx]  # raw, will be used as exponent
    idx += 1
    rel_min_scale = torch.sigmoid(params[idx])  # [0, 1] -> maps to [900, 2700]
    rel_starts_scale = torch.sigmoid(params[idx + 1])  # [0, 1] -> maps to [0.3, 0.7]
    idx += 2
    # Trend weight
    trend_weight = torch.sigmoid(params[idx]) * 10  # [0, 10] points bonus
    idx += 1
    # Experience weight
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

    availability = (
        min_share * avail_sw[0]
        + start_rate_score * avail_sw[1]
        + avail_pct * avail_sw[2]
        + role_stab * avail_sw[3]
    )

    # ── Attack (percentile-based, pre-computed) ──
    npg_pct = feat["npg_pct"].to(device)
    ast_pct = feat["ast_pct"].to(device)
    vol_pct = feat["vol_pct"].to(device)

    attack = npg_pct * player_aw[:, 0] + ast_pct * player_aw[:, 1] + vol_pct * player_aw[:, 2]

    # ── Defense (percentile-based, real data) ──
    def_pct = feat["def_pct"].to(device)
    defense = def_pct

    # ── Possession (percentile-based, real data) ──
    pos_pct = feat["pos_pct"].to(device)
    possession = pos_pct

    # ── Quality ──
    quality = npg_pct * qual_sw[0] + ast_pct * qual_sw[1] + def_pct * qual_sw[2] + pos_pct * qual_sw[3]

    # ── Base score ──
    base = (
        availability * player_pw[:, 0]
        + attack * player_pw[:, 1]
        + defense * player_pw[:, 2]
        + possession * player_pw[:, 3]
        + quality * player_pw[:, 4]
    )

    # ── Reliability ──
    rel_min_ref = 900 + rel_min_scale * 1800
    rel_starts_ref = 0.3 + rel_starts_scale * 0.4

    min_rel = 0.5 + 0.5 * torch.clamp(minutes / rel_min_ref, max=1.0)
    sr = starts_t / torch.clamp(matches_t, min=1)
    start_rel = 0.85 + 0.15 * torch.clamp(sr / rel_starts_ref, max=1.0)
    reliability = min_rel * start_rel

    # ── League coefficient ──
    league_name_to_coeff = {
        "Premier League": 119.52,
        "La Liga": 93.00,
        "Bundesliga": 92.90,
        "Serie A": 81.93,
        "Ligue 1": 83.50,
    }
    league_names_sorted = feat["league_names"]
    coeff_values = [league_name_to_coeff.get(l, 80.0) for l in league_names_sorted]
    league_coeffs = torch.tensor(coeff_values, dtype=torch.float32, device=device)
    eng_log = torch.log(league_coeffs[0])
    league_strength = (torch.log(league_coeffs) / eng_log) ** torch.clamp(league_log_scale, 0.1, 3.0)

    league_idx = feat["league_idx"].to(device)
    player_league_coeff = league_strength[league_idx]

    # ── Trend bonus ──
    trend_pct = feat["trend_pct"].to(device)
    trend_bonus = (trend_pct - 50) / 50 * trend_weight

    # ── Experience bonus ──
    experience = feat["experience"].to(device)
    exp_bonus = (experience - 0.5) / 0.5 * exp_weight

    # ── Final score ──
    overall = base * reliability * player_league_coeff + trend_bonus + exp_bonus
    return overall


def compute_team_avg_ratings(feat, ratings, device):
    """计算每队每赛季平均评分 (按出场分钟加权)。"""
    ts_indices = feat["ts_indices"]
    minutes = feat["minutes"].to(device)

    team_avgs = []
    for indices in ts_indices:
        idx_t = torch.tensor(indices, dtype=torch.long, device=device)
        r = ratings[idx_t]
        m = torch.clamp(minutes[idx_t], min=1)
        avg = (r * m).sum() / m.sum()
        team_avgs.append(avg.item())
    return np.array(team_avgs)


def objective_torch(feat, team_pts_df, params, device, verbose=False):
    """负 Spearman 相关性 (最小化)。"""
    ratings = compute_ratings_torch(feat, params, device)
    team_avgs = compute_team_avg_ratings(feat, ratings, device)

    # Match with actual standings
    ts_team = feat["ts_team_names"]
    ts_league = feat["ts_leagues"]
    ts_season = feat["ts_seasons"]

    pred_pts = []
    actual_pts = []
    for i in range(len(ts_team)):
        mask = (
            (team_pts_df["team"] == ts_team[i])
            & (team_pts_df["league"] == ts_league[i])
            & (team_pts_df["season"] == ts_season[i])
        )
        matched = team_pts_df.loc[mask, "total_points"]
        if len(matched) > 0:
            pred_pts.append(team_avgs[i])
            actual_pts.append(matched.values[0])

    pred_pts = np.array(pred_pts)
    actual_pts = np.array(actual_pts)

    if len(pred_pts) < 10:
        return torch.tensor(1.0, device=device, requires_grad=True)

    sp, _ = spearmanr(pred_pts, actual_pts)
    pr, _ = pearsonr(pred_pts, actual_pts)

    if verbose:
        print(f"  Spearman={sp:.4f}  Pearson={pr:.4f}  N={len(pred_pts)}")

    return torch.tensor(-sp, device=device, requires_grad=True)


# ── 优化循环 ──────────────────────────────────────────────────────────────


def optimize(feat, team_pts, device, n_steps=500, lr=0.05, pop_size=32, seed=42):
    """
    多起点并行优化。
    对 pop_size 组随机初始化的参数同时优化，取最优。
    """
    # Set seed for reproducibility
    torch.manual_seed(seed)
    np.random.seed(seed)
    
    print(f"  设备: {device}")
    print(f"  种群: {pop_size}, 步数: {n_steps}, 学习率: {lr}, 种子: {seed}")

    # 初始化参数种群
    all_params = []
    all_losses = []
    all_final_corrs = []

    for pop_i in range(pop_size):
        # Random init with bias toward reasonable values
        params = torch.randn(N_PARAMS, device=device) * 0.5

        # Adam optimizer
        params_t = params.clone().detach().requires_grad_(True)
        optimizer = torch.optim.Adam([params_t], lr=lr)

        best_loss = float("inf")
        best_params = params_t.clone().detach()
        patience_counter = 0

        for step in range(n_steps):
            optimizer.zero_grad()

            # Forward: compute ratings
            ratings = compute_ratings_torch(feat, params_t, device)
            team_avgs = compute_team_avg_ratings(feat, ratings, device)

            # Match standings
            pred_list = []
            actual_list = []
            for i in range(len(feat["ts_team_names"])):
                mask = (
                    (team_pts["team"] == feat["ts_team_names"][i])
                    & (team_pts["league"] == feat["ts_leagues"][i])
                    & (team_pts["season"] == feat["ts_seasons"][i])
                )
                matched = team_pts.loc[mask, "total_points"]
                if len(matched) > 0:
                    pred_list.append(team_avgs[i])
                    actual_list.append(matched.values[0])

            if len(pred_list) < 10:
                continue

            pred_t = torch.tensor(pred_list, device=device, dtype=torch.float32)
            actual_t = torch.tensor(actual_list, device=device, dtype=torch.float32)

            # Differentiable loss: negative Pearson
            pred_mean = pred_t.mean()
            actual_mean = actual_t.mean()
            pred_centered = pred_t - pred_mean
            actual_centered = actual_t - actual_mean
            pearson_corr = (pred_centered * actual_centered).sum() / (
                torch.sqrt((pred_centered**2).sum() * (actual_centered**2).sum()) + 1e-8
            )
            loss = -pearson_corr

            # Regularization
            reg = 0.001 * (params_t**2).mean()
            total_loss = loss + reg

            total_loss.backward()
            optimizer.step()

            current_loss = loss.item()
            if current_loss < best_loss:
                best_loss = current_loss
                best_params = params_t.clone().detach()
                patience_counter = 0
            else:
                patience_counter += 1

            if patience_counter > 50:
                break

        # Final evaluation with Spearman
        final_ratings = compute_ratings_torch(feat, best_params, device)
        final_team_avgs = compute_team_avg_ratings(feat, final_ratings, device)

        pred_arr = []
        actual_arr = []
        for i in range(len(feat["ts_team_names"])):
            mask = (
                (team_pts["team"] == feat["ts_team_names"][i])
                & (team_pts["league"] == feat["ts_leagues"][i])
                & (team_pts["season"] == feat["ts_seasons"][i])
            )
            matched = team_pts.loc[mask, "total_points"]
            if len(matched) > 0:
                pred_arr.append(final_team_avgs[i])
                actual_arr.append(matched.values[0])

        if len(pred_arr) >= 10:
            sp, _ = spearmanr(pred_arr, actual_arr)
            pr, _ = pearsonr(pred_arr, actual_arr)
        else:
            sp, pr = -1.0, -1.0

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
    default_pw = [
        [0.15, 0.38, 0.08, 0.14, 0.25],  # ST
        [0.12, 0.30, 0.10, 0.25, 0.23],  # W
        [0.12, 0.28, 0.10, 0.28, 0.22],  # AM
        [0.14, 0.16, 0.18, 0.32, 0.20],  # CM
        [0.14, 0.08, 0.30, 0.28, 0.20],  # DM
        [0.15, 0.10, 0.28, 0.27, 0.20],  # FB
        [0.16, 0.05, 0.42, 0.20, 0.17],  # CB
        [0.20, 0.05, 0.35, 0.20, 0.20],  # GK
    ]
    default_aw = [
        [0.45, 0.15, 0.40],  # ST
        [0.30, 0.30, 0.40],  # W
        [0.20, 0.40, 0.40],  # AM
        [0.15, 0.35, 0.50],  # CM
        [0.10, 0.25, 0.65],  # DM
        [0.10, 0.45, 0.45],  # FB
        [0.20, 0.20, 0.60],  # CB
        [0.05, 0.05, 0.90],  # GK
    ]
    params = []
    for row in default_pw:
        params.extend(_inv_softmax(row))
    for row in default_aw:
        params.extend(_inv_softmax(row))
    params.extend(_inv_softmax([0.45, 0.25, 0.20, 0.10]))
    params.extend(_inv_softmax([0.35, 0.25, 0.25, 0.15]))
    params.extend([1.0, 0.0, 0.0])  # league_log_scale, rel_min, rel_starts
    params.extend([0.0, 0.0])  # trend_weight, experience_weight
    return torch.tensor(params, dtype=torch.float32, device=device)


# ── 主流程 ────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="球员评分权重优化器 (GPU) - v2 with Understat")
    parser.add_argument("--data_dir", type=str, default="./data", help="数据目录路径")
    parser.add_argument("--steps", type=int, default=500, help="每组优化步数")
    parser.add_argument("--lr", type=float, default=0.05, help="学习率")
    parser.add_argument("--pop", type=int, default=32, help="种群大小")
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    print("=" * 80)
    print("球员评分权重优化器 (PyTorch GPU) - v2 with Understat")
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
    print(f"  赛季: {sorted(df['season'].unique())}")
    print(f"  数据源: {df['source'].value_counts().to_dict()}")
    print(f"  耗时: {time.time()-t0:.1f}s")

    # Build feature tensors
    print("\n[2] 预计算特征...")
    t0 = time.time()
    feat = build_feature_tensors(df)
    print(f"  耗时: {time.time()-t0:.1f}s")

    # Baseline
    print("\n[3] 基线 (v3 默认权重)...")
    default_params = _get_default_params_tensor(device)
    baseline_ratings = compute_ratings_torch(feat, default_params, device)
    baseline_team_avgs = compute_team_avg_ratings(feat, baseline_ratings, device)

    pred_b, actual_b = [], []
    for i in range(len(feat["ts_team_names"])):
        mask = (
            (team_pts["team"] == feat["ts_team_names"][i])
            & (team_pts["league"] == feat["ts_leagues"][i])
            & (team_pts["season"] == feat["ts_seasons"][i])
        )
        matched = team_pts.loc[mask, "total_points"]
        if len(matched) > 0:
            pred_b.append(baseline_team_avgs[i])
            actual_b.append(matched.values[0])
    sp_b, pr_b = spearmanr(pred_b, actual_b)
    print(f"  基线 Spearman: {sp_b:.4f}  Pearson: {pr_b:.4f}")

    # Optimize
    print(f"\n[4] 优化 (pop={args.pop}, steps={args.steps}, lr={args.lr})...")
    t0 = time.time()
    best_params = optimize(feat, team_pts, device, n_steps=args.steps, lr=args.lr, pop_size=args.pop)
    print(f"  总耗时: {time.time()-t0:.1f}s")

    # Results
    print("\n[5] 优化后权重:")
    print("-" * 80)
    pw_raw = best_params[: N_POS * N_DIM].reshape(N_POS, N_DIM)
    pw = torch.softmax(pw_raw, dim=1).cpu().numpy()
    print(f"{'位置':<5} {'出勤':>7} {'进攻':>7} {'防守':>7} {'控球':>7} {'质量':>7}")
    print("-" * 80)
    for i, pos in enumerate(POSITIONS):
        print(f"{pos:<5} {pw[i,0]:>7.4f} {pw[i,1]:>7.4f} {pw[i,2]:>7.4f} {pw[i,3]:>7.4f} {pw[i,4]:>7.4f}")

    # Attack weights
    aw_raw = best_params[N_POS * N_DIM : N_POS * N_DIM + N_POS * N_ATK].reshape(N_POS, N_ATK)
    aw = torch.softmax(aw_raw, dim=1).cpu().numpy()
    print(f"\n{'位置':<5} {'npxG_p90':>9} {'ast_p90':>9} {'G+A_vol':>9}")
    print("-" * 40)
    for i, pos in enumerate(POSITIONS):
        print(f"{pos:<5} {aw[i,0]:>9.4f} {aw[i,1]:>9.4f} {aw[i,2]:>9.4f}")

    # Per-league correlation
    print("\n[6] 各联赛相关性 (优化后):")
    opt_ratings = compute_ratings_torch(feat, best_params, device)
    opt_team_avgs = compute_team_avg_ratings(feat, opt_ratings, device)

    matched_records = []
    for i in range(len(feat["ts_team_names"])):
        mask = (
            (team_pts["team"] == feat["ts_team_names"][i])
            & (team_pts["league"] == feat["ts_leagues"][i])
            & (team_pts["season"] == feat["ts_seasons"][i])
        )
        matched = team_pts.loc[mask, "total_points"]
        if len(matched) > 0:
            matched_records.append({
                "team": feat["ts_team_names"][i],
                "league": feat["ts_leagues"][i],
                "season": feat["ts_seasons"][i],
                "pred_rating": opt_team_avgs[i],
                "actual_points": matched.values[0],
            })

    matched_df = pd.DataFrame(matched_records)
    pred_opt = matched_df["pred_rating"].values
    actual_opt = matched_df["actual_points"].values

    sp_opt, pr_opt = spearmanr(pred_opt, actual_opt)
    print(f"\n  总体: Spearman={sp_opt:.4f}  Pearson={pr_opt:.4f}")
    print(f"  提升: Spearman {sp_opt - sp_b:+.4f}  Pearson {pr_opt - pr_b:+.4f}")

    # Per league
    for league in sorted(matched_df["league"].unique()):
        lm = matched_df[matched_df["league"] == league]
        if len(lm) >= 5:
            s, _ = spearmanr(lm["pred_rating"], lm["actual_points"])
            pr_l, _ = pearsonr(lm["pred_rating"], lm["actual_points"])
            print(f"    {league:<22} Spearman={s:.3f}  Pearson={pr_l:.3f}  N={len(lm)}")

    # Save
    output = data_dir / "gold" / "feature_store"
    output.mkdir(parents=True, exist_ok=True)
    np.save(output / "optimized_params_v2.npy", best_params.cpu().numpy())
    print(f"\n[7] 参数已保存: {output / 'optimized_params_v2.npy'}")

    # Save re-rated players
    df["optimized_score"] = opt_ratings.cpu().numpy()
    df = df.sort_values("optimized_score", ascending=False)
    df.to_parquet(output / "player_ratings_optimized_v2.parquet", index=False)
    print(f"  球员评分已保存: {output / 'player_ratings_optimized_v2.parquet'}")

    print("\n  Top 20 (优化后):")
    print("-" * 80)
    for i, (_, row) in enumerate(df.head(20).iterrows(), 1):
        print(
            f"  {i:>3}  {row['player']:<28} {row['team']:<22} "
            f"{row['sub_position']:<3} {row['optimized_score']:>6.1f}  [{row['source']}]"
        )


if __name__ == "__main__":
    main()
