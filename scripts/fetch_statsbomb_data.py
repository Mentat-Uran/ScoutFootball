#!/usr/bin/env python3
"""Fetch real StatsBomb Open Data and write to Parquet."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

from scoutfootball.adapters.common import CachedHttpClient
from scoutfootball.adapters.statsbomb_open import load_events, load_lineups, load_matches
from scoutfootball.config import PlatformSettings

# StatsBomb Open Data competitions (Big 5 leagues + UCL/UEL)
COMPETITIONS = [
    (11, "La Liga"),
    (2, "Premier League"),
]

# Recent seasons
SEASONS = [90, 42]


def main():
    settings = PlatformSettings.from_root()
    client = CachedHttpClient(settings=settings)

    all_matches = []

    print("=" * 60)
    print("StatsBomb Open Data - 真实数据获取测试")
    print("=" * 60)

    # Step 1: Fetch matches for each competition/season
    print("\n[1/3] 获取比赛列表...")
    for comp_id, comp_name in COMPETITIONS:
        for season_id in SEASONS:
            try:
                result = load_matches(
                    comp_id,
                    season_id,
                    client=client,
                    settings=settings,
                    force_refresh=False,
                )
                df = result.dataframe
                if not df.empty:
                    df["source_competition"] = comp_name
                    all_matches.append(df)
                    print(f"  ✓ {comp_name} season {season_id}: {len(df)} 场比赛")
            except Exception:
                # Not all competitions have all seasons
                pass

    if not all_matches:
        print("  ✗ 未获取到任何比赛数据")
        return False

    matches_df = pd.concat(all_matches, ignore_index=True)
    print(f"\n  总计: {len(matches_df)} 场比赛")

    # Save matches to Parquet
    matches_path = settings.raw_root / "statsbomb_open" / "matches_all.parquet"
    matches_df.to_parquet(matches_path, index=False)
    print(f"  已保存: {matches_path}")

    # Step 2: Fetch events for a sample match
    print("\n[2/3] 获取事件数据 (样本比赛)...")
    sample_match_ids = matches_df["match_id"].head(3).tolist()
    all_events = []

    for match_id in sample_match_ids:
        try:
            result = load_events(
                match_id,
                client=client,
                settings=settings,
                force_refresh=False,
            )
            df = result.dataframe
            all_events.append(df)
            print(f"  ✓ Match {match_id}: {len(df)} 个事件")
        except Exception as e:
            print(f"  ✗ Match {match_id}: {e}")

    if all_events:
        events_df = pd.concat(all_events, ignore_index=True)
        events_path = settings.raw_root / "statsbomb_open" / "events_sample.parquet"
        events_df.to_parquet(events_path, index=False)
        print(f"\n  总计: {len(events_df)} 个事件")
        print(f"  已保存: {events_path}")

    # Step 3: Fetch lineups for a sample match
    print("\n[3/3] 获取阵容数据 (样本比赛)...")
    sample_match_id = matches_df["match_id"].iloc[0]

    try:
        result = load_lineups(
            sample_match_id,
            client=client,
            settings=settings,
            force_refresh=False,
        )
        lineups_df = result.dataframe
        lineups_path = settings.raw_root / "statsbomb_open" / "lineups_sample.parquet"
        lineups_df.to_parquet(lineups_path, index=False)
        print(f"  ✓ Match {sample_match_id}: {len(lineups_df)} 条阵容记录")
        print(f"  已保存: {lineups_path}")
    except Exception as e:
        print(f"  ✗ 获取阵容失败: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("数据获取完成!")
    print("=" * 60)
    print(f"\n数据目录: {settings.raw_root / 'statsbomb_open'}")
    print("\n文件列表:")
    for f in sorted((settings.raw_root / "statsbomb_open").glob("*.parquet")):
        size_mb = f.stat().st_size / 1024 / 1024
        print(f"  - {f.name}: {size_mb:.2f} MB")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
