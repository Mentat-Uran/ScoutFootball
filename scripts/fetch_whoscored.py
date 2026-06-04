#!/usr/bin/env python3
"""
Fetch WhoScored player match ratings and match events for Big 5 leagues.

WhoScored provides player ratings (1-10 scale) based on Opta event data,
which can serve as ground truth for the player rating model.

Requirements:
  - soccerdata: uv pip install soccerdata
  - Selenium + Chrome: uv pip install selenium && ensure Chrome is installed
  - In some regions, a proxy may be needed to access whoscored.com

Usage:
  uv run python scripts/fetch_whoscored.py
  uv run python scripts/fetch_whoscored.py --seasons 2023-2024 2024-2025
  uv run python scripts/fetch_whoscored.py --force-refresh
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

from scoutlab.adapters.whoscored import (
    fetch_match_events,
    fetch_player_match_ratings,
)
from scoutlab.config import PlatformSettings

# Big 5 leagues in soccerdata WhoScored format
BIG5_LEAGUES = [
    "ENG-Premier League",
    "ESP-La Liga",
    "GER-Bundesliga",
    "ITA-Serie A",
    "FRA-Ligue 1",
]

# WhoScored has limited historical data; focus on recent seasons
DEFAULT_SEASONS = ["2022-2023", "2023-2024", "2024-2025"]


def main():
    parser = argparse.ArgumentParser(description="Fetch WhoScored data for Big 5 leagues")
    parser.add_argument(
        "--seasons",
        nargs="+",
        default=DEFAULT_SEASONS,
        help="Seasons to fetch (default: 2022-2025)",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force refresh (bypass soccerdata cache)",
    )
    parser.add_argument(
        "--skip-events",
        action="store_true",
        help="Skip match events fetch (ratings only)",
    )
    args = parser.parse_args()

    settings = PlatformSettings.from_root()
    output_dir = settings.raw_root / "whoscored"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("WhoScored - Big 5 League Player Ratings & Events")
    print("=" * 60)

    # --- Player Match Ratings ---
    all_ratings: list[pd.DataFrame] = []
    ratings_success = 0
    ratings_fail = 0

    for season in args.seasons:
        season_frames: list[pd.DataFrame] = []
        for league in BIG5_LEAGUES:
            try:
                result = fetch_player_match_ratings(
                    league,
                    season,
                    settings=settings,
                    force_refresh=args.force_refresh,
                )
                df = result.dataframe
                season_frames.append(df)
                ratings_success += 1
                print(f"  ✓ {league} {season}: {len(df)} 条评分记录")
            except Exception as e:
                ratings_fail += 1
                print(f"  ✗ {league} {season}: {e}")

        if season_frames:
            combined = pd.concat(season_frames, ignore_index=True)
            out_path = output_dir / f"player_ratings_{season}.parquet"
            combined.to_parquet(out_path, index=False)
            all_ratings.append(combined)
            print(f"  → 已保存: {out_path} ({len(combined)} 条)")

    # Summary for ratings
    if all_ratings:
        all_df = pd.concat(all_ratings, ignore_index=True)
        print(f"\n{'=' * 60}")
        print(f"评分总计: {len(all_df)} 条")
        print(f"成功: {ratings_success}, 失败: {ratings_fail}")

        # Average ratings by position
        if "position" in all_df.columns and "rating" in all_df.columns:
            valid = all_df.dropna(subset=["rating"])
            if not valid.empty and valid["position"].notna().any():
                pos_avg = valid.groupby("position")["rating"].agg(["mean", "count"])
                pos_avg = pos_avg.sort_values("count", ascending=False)
                print("\n各位置平均评分:")
                for pos, row in pos_avg.head(15).iterrows():
                    if pos:
                        print(f"  {pos}: {row['mean']:.2f} (n={int(row['count'])})")

        # Average ratings by league
        if "league" in all_df.columns and "rating" in all_df.columns:
            valid = all_df.dropna(subset=["rating"])
            if not valid.empty:
                league_avg = valid.groupby("league")["rating"].agg(["mean", "count"])
                print("\n各联赛平均评分:")
                for lg, row in league_avg.iterrows():
                    print(f"  {lg}: {row['mean']:.2f} (n={int(row['count'])})")

    # --- Match Events (latest season only) ---
    if not args.skip_events:
        latest_season = args.seasons[-1]
        print(f"\n{'=' * 60}")
        print(f"比赛事件 - {latest_season}")
        print("=" * 60)

        all_events: list[pd.DataFrame] = []
        events_success = 0
        events_fail = 0

        for league in BIG5_LEAGUES:
            try:
                result = fetch_match_events(
                    league,
                    latest_season,
                    settings=settings,
                    force_refresh=args.force_refresh,
                )
                df = result.dataframe
                all_events.append(df)
                events_success += 1
                print(f"  ✓ {league} {latest_season}: {len(df)} 条事件")
            except Exception as e:
                events_fail += 1
                print(f"  ✗ {league} {latest_season}: {e}")

        if all_events:
            combined_events = pd.concat(all_events, ignore_index=True)
            out_path = output_dir / f"match_events_{latest_season}.parquet"
            combined_events.to_parquet(out_path, index=False)
            print(f"  → 已保存: {out_path} ({len(combined_events)} 条)")

            # Event type distribution
            if "event_type" in combined_events.columns:
                type_counts = combined_events["event_type"].value_counts().head(10)
                print("\n事件类型分布 (Top 10):")
                for etype, count in type_counts.items():
                    print(f"  {etype}: {count}")

        print(f"\n事件: 成功 {events_success}, 失败 {events_fail}")

    return ratings_success > 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
