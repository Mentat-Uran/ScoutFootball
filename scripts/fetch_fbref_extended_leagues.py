#!/usr/bin/env python3
"""
抓取 5 个非 Big5 联赛的 FBref 数据 (10 赛季, 10 stat types)
这些联赛不在 Big 5 Combined 视图中，需要单独抓取

联赛: POR-Primeira Liga, NED-Eredivisie, TUR-Süper Lig,
      SCO-Scottish Premiership, BEL-First Division A
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

from scoutfootball.adapters.fbref_soccerdata import (
    EXTENDED_LEAGUES,
    read_player_season_stats_extended,
)
from scoutfootball.config import PlatformSettings

STAT_TYPES = [
    "standard",
    "misc",
    "shooting",
    "passing",
    "defense",
    "possession",
    "gca",
    "playing_time",
    "keeper",
    "keeper_adv",
]

SEASONS = [
    "2025-2026", "2024-2025", "2023-2024", "2022-2023", "2021-2022",
    "2020-2021", "2019-2020", "2018-2019", "2017-2018", "2016-2017",
]


def main():
    settings = PlatformSettings.from_root()
    output_dir = settings.raw_root / "fbref" / "extended_leagues"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(f"FBref Extended Leagues - {len(EXTENDED_LEAGUES)} leagues, "
          f"{len(STAT_TYPES)} stat types, {len(SEASONS)} seasons")
    print("=" * 70)

    for stat_type in STAT_TYPES:
        print(f"\n=== {stat_type} ===")
        all_frames = []

        for season in SEASONS:
            print(f"  {season}...", end=" ", flush=True)
            try:
                df = read_player_season_stats_extended(
                    season,
                    stat_type=stat_type,
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
            if combined.index.has_duplicates:
                combined = combined[~combined.index.duplicated(keep="first")]

            output = output_dir / f"player_{stat_type}_extended_10seasons.parquet"
            combined.to_parquet(output, index=True)
            print(f"\n  已保存: {output.name} ({len(combined)} rows)")

            leagues = sorted(
                str(lg) for lg in combined.index.get_level_values("league").dropna().unique()
            )
            seasons_found = sorted(
                str(s) for s in combined.index.get_level_values("season").unique()
            )
            print(f"  Leagues: {leagues}")
            print(f"  Seasons: {seasons_found}")
        else:
            print(f"  {stat_type}: 无数据，跳过")

    print("\n完成!")


if __name__ == "__main__":
    main()
