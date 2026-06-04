#!/usr/bin/env python3
"""
抓取 Capology 五大联赛球员薪资数据
使用 ScraperFC 库，需要 Chrome/Chromium 浏览器
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

from scoutlab.adapters.capology import fetch_player_salaries
from scoutlab.config import PlatformSettings


def main():
    # Check ScraperFC installation
    try:
        from ScraperFC import Capology  # noqa: F401
    except ImportError:
        print("错误: ScraperFC 未安装。请运行: uv pip install ScraperFC")
        print("注意: ScraperFC 需要 Chrome/Chromium 浏览器 (Selenium)")
        return False

    settings = PlatformSettings.from_root()

    # Big 5 leagues (internal names matching adapter LEAGUE_MAPPINGS)
    leagues = [
        "Premier League",
        "La Liga",
        "Bundesliga",
        "Serie A",
        "Ligue 1",
    ]

    # Current and previous season (Capology format: "YYYY-YY")
    seasons = ["2025-26", "2024-25"]

    print("=" * 60)
    print("Capology - 五大联赛球员薪资数据")
    print("=" * 60)

    all_frames = []
    success_count = 0
    fail_count = 0

    for season in seasons:
        print(f"\n--- 赛季 {season} ---")
        for league in leagues:
            try:
                result = fetch_player_salaries(
                    league,
                    season,
                    settings=settings,
                    force_refresh=False,
                )
                df = result.dataframe
                all_frames.append(df)
                success_count += 1
                print(f"  ✓ {league} {season}: {len(df)} 球员")
            except Exception as e:
                fail_count += 1
                print(f"  ✗ {league} {season}: {e}")

    if not all_frames:
        print("\n未获取到任何数据")
        return False

    combined = pd.concat(all_frames, ignore_index=True)

    # Save combined output
    output_path = settings.raw_root / "capology" / "player_salaries.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(output_path, index=False)

    print(f"\n总计: {len(combined)} 条薪资记录")
    print(f"已保存: {output_path}")
    print(f"成功获取: {success_count}/{len(leagues) * len(seasons)} 个数据集")
    print(f"失败: {fail_count}")

    # League distribution
    print("\n联赛分布:")
    for league in sorted(combined["league"].unique()):
        count = len(combined[combined["league"] == league])
        print(f"  {league}: {count} 条")

    # Season distribution
    print("\n赛季分布:")
    for season in sorted(combined["season"].unique()):
        count = len(combined[combined["season"] == season])
        print(f"  {season}: {count} 条")

    # Average salary by league (weekly gross, GBP)
    salary_col = "weekly_gross_salary"
    if salary_col in combined.columns:
        valid = combined[combined[salary_col] > 0]
        if not valid.empty:
            print("\n平均周薪 (Gross, GBP) 按联赛:")
            for league in sorted(valid["league"].unique()):
                avg = valid[valid["league"] == league][salary_col].mean()
                print(f"  {league}: £{avg:,.0f}")

            print("\n平均周薪 (Gross, GBP) 按位置:")
            for pos in sorted(valid["position"].dropna().unique()):
                avg = valid[valid["position"] == pos][salary_col].mean()
                print(f"  {pos}: £{avg:,.0f}")

    return success_count > 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
