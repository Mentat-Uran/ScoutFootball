#!/usr/bin/env python3
"""
获取 StatsBomb Open Data 完整数据
包括所有可用联赛和赛季
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import json

import pandas as pd

from scoutlab.adapters.common import CachedHttpClient
from scoutlab.config import PlatformSettings

RAW_BASE_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"

# 五大联赛 competition_id
BIG5_COMPETITIONS = {
    9: "1. Bundesliga",  # 德甲
    11: "La Liga",  # 西甲
    7: "Ligue 1",  # 法甲
    2: "Premier League",  # 英超
    12: "Serie A",  # 意甲
}


def main():
    settings = PlatformSettings.from_root()
    client = CachedHttpClient(settings=settings)

    print("=" * 60)
    print("StatsBomb Open Data - 五大联赛全量数据获取")
    print("=" * 60)

    # Step 1: 获取所有可用联赛和赛季
    print("\n[1] 获取可用联赛列表...")
    competitions_url = f"{RAW_BASE_URL}/competitions.json"
    cache_path = settings.raw_root / "statsbomb_open" / "competitions.json"

    artifact = client.fetch(
        source_name="statsbomb_open",
        source_uri=competitions_url,
        cache_path=cache_path,
        parser_version="statsbomb_open/v0.1.0",
    )

    competitions = json.loads(artifact.payload.decode("utf-8"))
    print(f"  ✓ 可用联赛+赛季组合数: {len(competitions)}")

    # 筛选五大联赛近三个赛季
    print("\n[2] 筛选五大联赛数据...")
    print("-" * 60)

    target_seasons = []
    for comp in competitions:
        comp_id = comp["competition_id"]
        season_name = comp["season_name"]

        # 只处理五大联赛
        if comp_id not in BIG5_COMPETITIONS:
            continue

        # 只处理近三个赛季 (2022/2023, 2023/2024, 2024/2025)
        if any(year in season_name for year in ["2022", "2023", "2024"]):
            target_seasons.append(comp)
            print(
                f"  ✓ {comp['competition_name']} - {season_name} "
                f"(ID: {comp_id}/{comp['season_id']})"
            )

    print(f"\n  目标数据集: {len(target_seasons)} 个")

    # Step 3: 获取所有比赛
    print("\n[3] 获取比赛数据...")
    print("-" * 60)

    all_matches = []

    for comp in target_seasons:
        comp_id = comp["competition_id"]
        season_id = comp["season_id"]
        comp_name = comp["competition_name"]
        season_name = comp["season_name"]

        print(f"\n  获取: {comp_name} {season_name}...")

        try:
            matches_url = f"{RAW_BASE_URL}/matches/{comp_id}/{season_id}.json"
            cache_path = (
                settings.raw_root
                / "statsbomb_open"
                / "matches"
                / str(comp_id)
                / f"{season_id}.json"
            )

            artifact = client.fetch(
                source_name="statsbomb_open",
                source_uri=matches_url,
                cache_path=cache_path,
                parser_version="statsbomb_open/v0.1.0",
            )

            matches_data = json.loads(artifact.payload.decode("utf-8"))

            for match in matches_data:
                all_matches.append(
                    {
                        "match_id": match["match_id"],
                        "competition_id": comp_id,
                        "competition_name": comp_name,
                        "season_id": season_id,
                        "season_name": season_name,
                        "match_date": match["match_date"],
                        "home_team_id": match["home_team"]["home_team_id"],
                        "home_team_name": match["home_team"]["home_team_name"],
                        "away_team_id": match["away_team"]["away_team_id"],
                        "away_team_name": match["away_team"]["away_team_name"],
                        "home_score": match.get("home_score", 0),
                        "away_score": match.get("away_score", 0),
                    }
                )

            print(f"    ✓ {len(matches_data)} 场比赛")

        except Exception as e:
            print(f"    ✗ 失败: {e}")

    # 保存所有比赛
    if all_matches:
        matches_df = pd.DataFrame(all_matches)
        output_path = settings.raw_root / "statsbomb_open" / "big5_matches.parquet"
        matches_df.to_parquet(output_path, index=False)

        print("\n[4] 数据汇总:")
        print("-" * 60)
        print(f"  总比赛数: {len(matches_df)}")
        print("  联赛分布:")
        for comp, count in matches_df["competition_name"].value_counts().items():
            print(f"    {comp}: {count} 场")
        print(f"\n  保存位置: {output_path}")

        # 统计独特球队数
        teams = pd.concat(
            [
                matches_df[["home_team_id", "home_team_name"]].rename(
                    columns={"home_team_id": "team_id", "home_team_name": "team_name"}
                ),
                matches_df[["away_team_id", "away_team_name"]].rename(
                    columns={"away_team_id": "team_id", "away_team_name": "team_name"}
                ),
            ]
        ).drop_duplicates()
        print(f"  球队数: {len(teams)}")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
