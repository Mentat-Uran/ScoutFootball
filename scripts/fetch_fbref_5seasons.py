#!/usr/bin/env python3
"""
抓取 5 赛季 FBref 数据 (standard + misc + shooting)，含德甲回退。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
from scoutlab.adapters.fbref_soccerdata import (
    read_player_season_stats_with_bundesliga_fallback,
)
from scoutlab.config import PlatformSettings


def main():
    settings = PlatformSettings.from_root()
    seasons = ["2021-2022", "2022-2023", "2023-2024", "2024-2025", "2025-2026"]

    print("=" * 70)
    print("抓取 5 赛季 FBref 数据 (含德甲回退)")
    print("=" * 70)

    for stat_type in ["standard", "misc", "shooting"]:
        print(f"\n=== {stat_type} ===")
        all_frames = []
        for season in seasons:
            print(f"  {season}...", end=" ", flush=True)
            try:
                df = read_player_season_stats_with_bundesliga_fallback(
                    season, stat_type=stat_type,
                )
                if not df.empty:
                    df["season"] = season
                    all_frames.append(df)
                    leagues = df.index.get_level_values("league").dropna().unique()
                    print(f"OK ({len(df)} rows, {len(leagues)} leagues)")
                else:
                    print("empty")
            except Exception as e:
                print(f"FAIL: {e}")

        if all_frames:
            combined = pd.concat(all_frames, axis=0)
            # Deduplicate
            if combined.index.has_duplicates:
                combined = combined[~combined.index.duplicated(keep="first")]

            # Save as 5-season
            output_5s = settings.raw_root / "fbref" / f"player_{stat_type}_5seasons.parquet"
            combined.to_parquet(output_5s, index=True)
            print(f"  Saved: {output_5s.name} ({len(combined)} rows)")

            # Also save as _3seasons for backward compatibility (pipeline reads this)
            if stat_type == "standard":
                output_3s = settings.raw_root / "fbref" / "player_stats_big5_3seasons.parquet"
            else:
                output_3s = settings.raw_root / "fbref" / f"player_{stat_type}_3seasons.parquet"
            combined.to_parquet(output_3s, index=True)
            print(f"  Saved: {output_3s.name} ({len(combined)} rows)")

            # Summary
            leagues = sorted(str(l) for l in combined.index.get_level_values("league").dropna().unique())
            print(f"  Leagues: {leagues}")

    print("\n完成!")


if __name__ == "__main__":
    main()
