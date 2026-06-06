#!/usr/bin/env python3
"""Validate fetched data quality."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

from scoutfootball.config import PlatformSettings


def main():
    settings = PlatformSettings.from_root()

    print("=" * 60)
    print("数据质量验证")
    print("=" * 60)

    # 1. Validate StatsBomb matches
    print("\n[1] StatsBomb 比赛数据")
    matches_path = settings.raw_root / "statsbomb_open" / "matches_all.parquet"
    if matches_path.exists():
        matches = pd.read_parquet(matches_path)
        print(f"  ✓ 文件存在: {matches_path.name}")
        print(f"  ✓ 记录数: {len(matches)}")
        print(f"  ✓ 列: {list(matches.columns[:8])}")
        print(f"  ✓ 日期范围: {matches['match_date'].min()} ~ {matches['match_date'].max()}")
        print(f"  ✓ 主场球队数: {matches['home_team_id'].nunique()}")
    else:
        print("  ✗ 文件不存在")

    # 2. Validate StatsBomb events
    print("\n[2] StatsBomb 事件数据")
    events_path = settings.raw_root / "statsbomb_open" / "events_sample.parquet"
    if events_path.exists():
        events = pd.read_parquet(events_path)
        print(f"  ✓ 文件存在: {events_path.name}")
        print(f"  ✓ 记录数: {len(events)}")
        print(f"  ✓ 比赛数: {events['match_id'].nunique()}")
        print(f"  ✓ 事件类型: {events['event_type'].unique()[:5]}")

        # Check for location data
        if "location_x" in events.columns:
            print("  ✓ 坐标列: location_x, location_y 存在")
    else:
        print("  ✗ 文件不存在")

    # 3. Validate Football-Data
    print("\n[3] Football-Data 比赛结果")
    fd_path = settings.raw_root / "football_data" / "combined_results.parquet"
    if fd_path.exists():
        fd = pd.read_parquet(fd_path)
        print(f"  ✓ 文件存在: {fd_path.name}")
        print(f"  ✓ 记录数: {len(fd)}")
        print(f"  ✓ 联赛: {fd['league'].unique()}")
        print(f"  ✓ 赛季: {fd['season'].unique()}")
        print(f"  ✓ 进球统计: 主场均 {fd['FTHG'].mean():.2f}, 客场均 {fd['FTAG'].mean():.2f}")

        # Check missing values
        missing_pct = fd[["FTHG", "FTAG"]].isnull().mean()
        print(f"  ✓ 缺失值: {missing_pct.to_dict()}")
    else:
        print("  ✗ 文件不存在")

    # 4. Summary
    print("\n" + "=" * 60)
    print("验证总结")
    print("=" * 60)

    total_files = sum(
        1
        for f in [
            settings.raw_root / "statsbomb_open" / "matches_all.parquet",
            settings.raw_root / "statsbomb_open" / "events_sample.parquet",
            settings.raw_root / "football_data" / "combined_results.parquet",
        ]
        if f.exists()
    )

    print(f"\n✓ 成功获取 {total_files}/3 个数据源")
    print(f"\n数据存储位置: {settings.raw_root}")

    return total_files >= 2  # At least 2 sources


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
