#!/usr/bin/env python3
"""Fetch Club Elo ratings."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

from scoutlab.adapters.clubelo import fetch_elo_by_date
from scoutlab.adapters.common import CachedHttpClient
from scoutlab.config import PlatformSettings


def main():
    settings = PlatformSettings.from_root()
    client = CachedHttpClient(settings=settings)

    print("=" * 60)
    print("Club Elo - 真实数据获取")
    print("=" * 60)

    # Fetch a few dates to get recent Elo ratings
    dates = ["2026-01-01", "2025-01-01", "2024-01-01"]
    all_data = []

    for date in dates:
        try:
            result = fetch_elo_by_date(
                date,
                client=client,
                settings=settings,
                force_refresh=False,
            )
            df = result.dataframe
            df["snapshot_date"] = date
            all_data.append(df)
            print(f"  ✓ {date}: {len(df)} 支球队")
        except Exception as e:
            print(f"  ✗ {date}: {e}")

    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        output_path = settings.raw_root / "clubelo" / "team_elo_ratings.parquet"
        combined.to_parquet(output_path, index=False)

        print(f"\n总计: {len(combined)} 条记录")
        print(f"已保存: {output_path}")

        # Show top teams
        latest = combined[combined["snapshot_date"] == "2026-01-01"].nlargest(10, "Elo")
        print("\n2026-01-01 Elo 排名前 10:")
        for _, row in latest.iterrows():
            print(f"  {row['Rank']}. {row['Club']}: {row['Elo']:.0f}")

    return len(all_data) > 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
