#!/usr/bin/env python3
"""
扩展 FBref 数据到 10 赛季 (2016-2026)
包含 standard, misc, shooting 三类统计
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
    
    # 10 seasons: 2016/17 to 2025/26
    seasons = [
        "2025-2026", "2024-2025", "2023-2024", "2022-2023", "2021-2022",
        "2020-2021", "2019-2020", "2018-2019", "2017-2018", "2016-2017",
    ]

    print("=" * 70)
    print("FBref - 扩展到 10 赛季 (standard + misc + shooting)")
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

            # Save with appropriate filename
            if stat_type == "standard":
                output = settings.raw_root / "fbref" / "player_stats_big5_10seasons.parquet"
            else:
                output = settings.raw_root / "fbref" / f"player_{stat_type}_10seasons.parquet"
            
            combined.to_parquet(output, index=True)
            print(f"\n  已保存: {output.name} ({len(combined)} rows)")
            
            # Also save as _5seasons for backward compatibility
            if stat_type == "standard":
                output_5s = settings.raw_root / "fbref" / "player_stats_big5_5seasons.parquet"
            else:
                output_5s = settings.raw_root / "fbref" / f"player_{stat_type}_5seasons.parquet"
            combined.to_parquet(output_5s, index=True)
            print(f"  已保存: {output_5s.name} (backward compat)")

            # Also save as _3seasons for pipeline compatibility
            if stat_type == "standard":
                output_3s = settings.raw_root / "fbref" / "player_stats_big5_3seasons.parquet"
            else:
                output_3s = settings.raw_root / "fbref" / f"player_{stat_type}_3seasons.parquet"
            combined.to_parquet(output_3s, index=True)
            print(f"  已保存: {output_3s.name} (pipeline compat)")

            # Summary
            leagues = sorted(str(l) for l in combined.index.get_level_values("league").dropna().unique())
            seasons_found = sorted(str(s) for s in combined.index.get_level_values("season").unique())
            print(f"  Leagues: {leagues}")
            print(f"  Seasons: {seasons_found}")

    print("\n完成!")


if __name__ == "__main__":
    main()
