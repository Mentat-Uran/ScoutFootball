#!/usr/bin/env python3
"""
扩展 StatsBomb Open Data - 获取所有可用的五大联赛数据
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import json
import pandas as pd
from scoutlab.adapters.common import CachedHttpClient
from scoutlab.config import PlatformSettings

RAW_BASE_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"

# 五大联赛 competition_id
BIG5_COMPETITIONS = {
    9: "1. Bundesliga",
    11: "La Liga",
    7: "Ligue 1",
    2: "Premier League",
    12: "Serie A",
}


def main():
    settings = PlatformSettings.from_root()
    client = CachedHttpClient(settings=settings)

    print("=" * 60)
    print("StatsBomb Open Data - 五大联赛全量数据获取")
    print("=" * 60)

    # Step 1: 获取所有可用联赛和赛季
    print("\n[1] 获取可用联赛列表...")
    competitions_url = f"{RAW_BASE_URL}/competitions.json"
    cache_path = settings.raw_root / "statsbomb_open" / "competitions.json"

    artifact = client.fetch(
        source_name="statsbomb_open",
        source_uri=competitions_url,
        cache_path=cache_path,
        parser_version="statsbomb_open/v0.1.0",
    )

    with open(cache_path) as f:
        competitions = json.load(f)

    # Filter to Big 5
    big5_comps = [c for c in competitions if c["competition_id"] in BIG5_COMPETITIONS]
    print(f"  找到 {len(big5_comps)} 个五大联赛赛事")

    # Step 2: 获取每个联赛的所有赛季
    print("\n[2] 获取赛季列表...")
    all_seasons = []
    for comp in big5_comps:
        comp_id = comp["competition_id"]
        comp_name = BIG5_COMPETITIONS[comp_id]
        season_url = f"{RAW_BASE_URL}/competitions/{comp_id}/seasons.json"
        season_cache = settings.raw_root / "statsbomb_open" / "seasons" / f"{comp_id}.json"
        season_cache.parent.mkdir(parents=True, exist_ok=True)

        try:
            artifact = client.fetch(
                source_name="statsbomb_open",
                source_uri=season_url,
                cache_path=season_cache,
                parser_version="statsbomb_open/v0.1.0",
            )
            with open(season_cache) as f:
                seasons = json.load(f)
            
            for season in seasons:
                all_seasons.append({
                    "competition_id": comp_id,
                    "competition_name": comp_name,
                    "season_id": season["season_id"],
                    "season_name": season["season_name"],
                })
            print(f"  {comp_name}: {len(seasons)} 个赛季")
        except Exception as e:
            print(f"  {comp_name}: FAIL ({e})")

    print(f"\n总计: {len(all_seasons)} 个赛季")

    # Step 3: 获取每个赛季的比赛列表
    print("\n[3] 获取比赛列表...")
    all_matches = []
    for season_info in all_seasons:
        comp_id = season_info["competition_id"]
        season_id = season_info["season_id"]
        comp_name = season_info["competition_name"]
        season_name = season_info["season_name"]

        matches_url = f"{RAW_BASE_URL}/matches/{comp_id}/{season_id}.json"
        matches_cache = settings.raw_root / "statsbomb_open" / "matches" / str(comp_id) / f"{season_id}.json"
        matches_cache.parent.mkdir(parents=True, exist_ok=True)

        try:
            artifact = client.fetch(
                source_name="statsbomb_open",
                source_uri=matches_url,
                cache_path=matches_cache,
                parser_version="statsbomb_open/v0.1.0",
            )
            with open(matches_cache) as f:
                matches = json.load(f)
            
            for match in matches:
                all_matches.append({
                    "competition_id": comp_id,
                    "competition_name": comp_name,
                    "season_id": season_id,
                    "season_name": season_name,
                    "match_id": match["match_id"],
                    "home_team": match.get("home_team", {}).get("home_team_name", ""),
                    "away_team": match.get("away_team", {}).get("away_team_name", ""),
                    "home_score": match.get("home_score", 0),
                    "away_score": match.get("away_score", 0),
                })
            print(f"  {comp_name} {season_name}: {len(matches)} 场比赛")
        except Exception as e:
            print(f"  {comp_name} {season_name}: FAIL ({e})")

    print(f"\n总计: {len(all_matches)} 场比赛")

    # Step 4: 获取比赛事件数据
    print("\n[4] 获取比赛事件数据...")
    events_frames = []
    lineups_frames = []
    
    for i, match_info in enumerate(all_matches):
        match_id = match_info["match_id"]
        comp_name = match_info["competition_name"]
        season_name = match_info["season_name"]
        
        if (i + 1) % 10 == 0 or i == 0:
            print(f"  进度: {i+1}/{len(all_matches)}...", flush=True)

        # Events
        events_url = f"{RAW_BASE_URL}/events/{match_id}.json"
        events_cache = settings.raw_root / "statsbomb_open" / "events" / f"{match_id}.json"
        events_cache.parent.mkdir(parents=True, exist_ok=True)

        try:
            artifact = client.fetch(
                source_name="statsbomb_open",
                source_uri=events_url,
                cache_path=events_cache,
                parser_version="statsbomb_open/v0.1.0",
            )
            with open(events_cache) as f:
                events = json.load(f)
            
            for event in events:
                event["match_id"] = match_id
                event["competition_name"] = comp_name
                event["season_name"] = season_name
            
            events_frames.append(pd.DataFrame(events))
        except Exception as e:
            pass  # Skip failed events

        # Lineups
        lineups_url = f"{RAW_BASE_URL}/lineups/{match_id}.json"
        lineups_cache = settings.raw_root / "statsbomb_open" / "lineups" / f"{match_id}.json"
        lineups_cache.parent.mkdir(parents=True, exist_ok=True)

        try:
            artifact = client.fetch(
                source_name="statsbomb_open",
                source_uri=lineups_url,
                cache_path=lineups_cache,
                parser_version="statsbomb_open/v0.1.0",
            )
            with open(lineups_cache) as f:
                lineups = json.load(f)
            
            for lineup in lineups:
                lineup["match_id"] = match_id
                lineup["competition_name"] = comp_name
                lineup["season_name"] = season_name
            
            lineups_frames.append(pd.DataFrame(lineups))
        except Exception as e:
            pass  # Skip failed lineups

    # Step 5: 保存数据
    print("\n[5] 保存数据...")
    
    if events_frames:
        events_df = pd.concat(events_frames, ignore_index=True)
        events_path = settings.raw_root / "statsbomb_open" / "events_all.parquet"
        events_df.to_parquet(events_path, index=False)
        print(f"  Events: {len(events_df)} 条事件 -> {events_path.name}")
    
    if lineups_frames:
        lineups_df = pd.concat(lineups_frames, ignore_index=True)
        lineups_path = settings.raw_root / "statsbomb_open" / "lineups_all.parquet"
        lineups_df.to_parquet(lineups_path, index=False)
        print(f"  Lineups: {len(lineups_df)} 条阵容 -> {lineups_path.name}")
    
    # Save matches summary
    matches_df = pd.DataFrame(all_matches)
    matches_path = settings.raw_root / "statsbomb_open" / "matches_all.parquet"
    matches_df.to_parquet(matches_path, index=False)
    print(f"  Matches: {len(matches_df)} 场比赛 -> {matches_path.name}")

    # Competition summary
    print("\n[6] 赛事统计:")
    for comp_name in sorted(matches_df["competition_name"].unique()):
        comp_matches = matches_df[matches_df["competition_name"] == comp_name]
        seasons_count = comp_matches["season_name"].nunique()
        print(f"  {comp_name}: {len(comp_matches)} 场比赛, {seasons_count} 个赛季")

    print("\n完成!")


if __name__ == "__main__":
    main()
