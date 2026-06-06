#!/usr/bin/env python3
"""Fetch API-Football data (injuries, coaches) for Big 5 leagues.

Requires API_FOOTBALL_KEY environment variable.
Free tier: 100 requests/day.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

from scoutfootball.adapters.api_football import (
    DailyLimitExceededError,
    _DailyRequestCounter,
    fetch_coaches,
    fetch_injuries,
)
from scoutfootball.adapters.common import CachedHttpClient
from scoutfootball.config import PlatformSettings


def main():
    # Check for API key first
    api_key = os.environ.get("API_FOOTBALL_KEY")
    if not api_key:
        print("=" * 60)
        print("API-Football: 缺少 API Key")
        print("=" * 60)
        print()
        print("请设置环境变量 API_FOOTBALL_KEY:")
        print()
        print("  export API_FOOTBALL_KEY='your-key-here'")
        print()
        print("获取 API Key:")
        print("  1. 注册 https://www.api-football.com/")
        print("  2. 在 Dashboard 获取免费 API Key")
        print("  3. 免费版限额: 100 requests/day")
        print()
        return False

    settings = PlatformSettings.from_root()
    client = CachedHttpClient(settings=settings)
    counter = _DailyRequestCounter(settings.log_root / "api_football" / "daily_counter")

    current_season = 2025  # 2025/26 season

    # Big 5 + extended leagues
    leagues = {
        "EPL": 39,
        "La_Liga": 140,
        "Bundesliga": 78,
        "Serie_A": 135,
        "Ligue_1": 61,
    }

    print("=" * 60)
    print("API-Football - 伤病 & 教练数据获取")
    print("=" * 60)
    print(f"API Key: ...{api_key[-4:]}")
    print(f"今日已用请求: {counter.count()}/100")
    print(f"剩余请求: {counter.remaining()}")
    print()

    # --- Injuries ---
    print("--- 伤病数据 ---")
    injury_frames = []
    for league_name, league_id in leagues.items():
        try:
            result = fetch_injuries(
                league_id,
                current_season,
                api_key=api_key,
                client=client,
                settings=settings,
                force_refresh=False,
            )
            df = result.dataframe
            df["league"] = league_name
            df["season"] = current_season
            injury_frames.append(df)
            print(f"  ✓ {league_name} {current_season}: {len(df)} 条伤病记录")
        except DailyLimitExceededError as e:
            print(f"  ✗ 每日请求限额已用完: {e}")
            break
        except Exception as e:
            print(f"  ✗ {league_name} {current_season}: {e}")

    if injury_frames:
        combined_injuries = pd.concat(injury_frames, ignore_index=True)
        output_path = settings.raw_root / "api_football" / "injuries" / "big5_injuries.parquet"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        combined_injuries.to_parquet(output_path, index=False)
        print(f"\n伤病总计: {len(combined_injuries)} 条")
        print(f"已保存: {output_path}")

    print(f"\n今日已用请求: {counter.count()}/100")

    # --- Coaches ---
    print("\n--- 教练数据 ---")
    coach_frames = []
    for league_name, league_id in leagues.items():
        try:
            result = fetch_coaches(
                league_id,
                current_season,
                api_key=api_key,
                client=client,
                settings=settings,
                force_refresh=False,
            )
            df = result.dataframe
            df["league"] = league_name
            df["season"] = current_season
            coach_frames.append(df)
            print(f"  ✓ {league_name} {current_season}: {len(df)} 条教练记录")
        except DailyLimitExceededError as e:
            print(f"  ✗ 每日请求限额已用完: {e}")
            break
        except Exception as e:
            print(f"  ✗ {league_name} {current_season}: {e}")

    if coach_frames:
        combined_coaches = pd.concat(coach_frames, ignore_index=True)
        output_path = settings.raw_root / "api_football" / "coaches" / "big5_coaches.parquet"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        combined_coaches.to_parquet(output_path, index=False)
        print(f"\n教练总计: {len(combined_coaches)} 条")
        print(f"已保存: {output_path}")

    print(f"\n今日已用请求: {counter.count()}/100")
    print(f"剩余请求: {counter.remaining()}")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
