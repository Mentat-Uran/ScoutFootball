#!/usr/bin/env python3
"""
扩展 Football-Data.co.uk 数据到 10 赛季 (2016-2026)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

from scoutfootball.adapters.common import CachedHttpClient
from scoutfootball.adapters.football_data import download_csv
from scoutfootball.config import PlatformSettings

# Football-Data.co.uk 联赛代码
# 注意：部分联赛赛季覆盖有限，例如 SC2/SC3 可能只有近几个赛季的数据。
# adapter 已能优雅处理缺失 CSV（不会报错，只是缓存目录中找不到）。
LEAGUES = {
    # Big 5
    "E0": "Premier League",
    "SP1": "La Liga",
    "D1": "Bundesliga",
    "F1": "Ligue 1",
    "I1": "Serie A",
    # English lower leagues
    "E1": "Championship",
    "E2": "League One",
    "E3": "League Two",
    # Spanish/German/French/Italian lower leagues
    "SP2": "Segunda División",
    "D2": "2. Bundesliga",
    "F2": "Ligue 2",
    "I2": "Serie B",
    # Other European leagues
    "N1": "Eredivisie",
    "P1": "Primeira Liga",
    "T1": "Süper Lig",
    "B1": "First Division A",
    # Scottish leagues
    "SC0": "Scottish Premiership",
    "SC1": "Scottish Championship",
    "SC2": "Scottish League One",
    "SC3": "Scottish League Two",
}

# 10 seasons: 2016/17 to 2025/26
SEASONS = [
    "2526", "2425", "2324", "2223", "2122",
    "2021", "1920", "1819", "1718", "1617",
]


def main():
    settings = PlatformSettings.from_root()
    client = CachedHttpClient(settings=settings)

    print("=" * 60)
    print("Football-Data.co.uk - 扩展到 10 赛季")
    print("=" * 60)

    all_data = []
    success_count = 0
    fail_count = 0

    for league_code, league_name in LEAGUES.items():
        for season in SEASONS:
            try:
                result = download_csv(
                    league_code,
                    season,
                    client=client,
                    settings=settings,
                    force_refresh=False,
                )
                df = result.dataframe
                df["league"] = league_name
                df["season"] = season
                all_data.append(df)
                success_count += 1
                print(f"  ✓ {league_name} {season}: {len(df)} 场比赛")
            except Exception as e:
                fail_count += 1
                print(f"  ✗ {league_name} {season}: {e}")

    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        # 修复混合类型列（赔率列可能混合 str/float）
        for col in combined.columns:
            if combined[col].dtype == object:
                combined[col] = combined[col].astype(str)
        output_path = settings.raw_root / "football_data" / "combined_results.parquet"
        combined.to_parquet(output_path, index=False)

        print(f"\n总计: {len(combined)} 场比赛")
        print(f"已保存: {output_path}")
        print(f"成功获取: {success_count}/{len(LEAGUES) * len(SEASONS)} 个数据集")
        print(f"失败: {fail_count}")

        # Show season distribution
        print("\n赛季分布:")
        for season in sorted(combined["season"].unique()):
            count = len(combined[combined["season"] == season])
            print(f"  {season}: {count} 场")

    return success_count > 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
