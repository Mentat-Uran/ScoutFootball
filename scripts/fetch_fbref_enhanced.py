#!/usr/bin/env python3
"""
增强 FBref 数据: 抓取 misc + shooting 统计。
分别保存，在优化器中合并。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

from scoutfootball.adapters.fbref_soccerdata import read_player_season_stats_with_bundesliga_fallback
from scoutfootball.config import PlatformSettings


def main():
    settings = PlatformSettings.from_root()
    seasons = ["2022-2023", "2023-2024", "2024-2025"]

    print("=" * 70)
    print("增强 FBref 数据")
    print("=" * 70)

    for stat_type in ["misc", "shooting"]:
        print(f"\n[{stat_type}]")
        all_frames = []
        for season in seasons:
            print(f"  {season}...", end=" ", flush=True)
            try:
                df = read_player_season_stats_with_bundesliga_fallback(
                    season,
                    stat_type=stat_type,
                )
                if not df.empty:
                    df["season"] = season
                    all_frames.append(df)
                    print(f"OK ({len(df)} rows)")
                else:
                    print("empty")
            except Exception as e:
                print(f"FAIL: {e}")

        if all_frames:
            combined = pd.concat(all_frames, axis=0)
            output_path = settings.raw_root / "fbref" / f"player_{stat_type}_3seasons.parquet"
            combined.to_parquet(output_path, index=True)
            print(f"  保存: {output_path} ({len(combined)} rows)")

            # Show useful columns
            useful = [
                c
                for c in combined.columns
                if c[0] not in ("nation", "pos", "age", "born", "90s", "season")
            ]
            print(f"  统计列: {[c[1] for c in useful]}")

    print("\n完成! 现在可以在优化器中使用防守/射门数据。")


if __name__ == "__main__":
    main()
