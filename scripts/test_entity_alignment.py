#!/usr/bin/env python3
"""End-to-end pipeline: entity alignment -> features -> model training."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

from scoutlab.config import PlatformSettings
from scoutlab.entities.normalize import normalize_team_name


def main():
    settings = PlatformSettings.from_root()

    print("=" * 60)
    print("Phase 5: 实体对齐 - 真实数据测试")
    print("=" * 60)

    # Load data
    print("\n[1] 加载数据源...")
    sb_matches = pd.read_parquet(settings.raw_root / "statsbomb_open" / "matches_all.parquet")
    fd_matches = pd.read_parquet(settings.raw_root / "football_data" / "combined_results.parquet")
    print(f"  ✓ StatsBomb: {len(sb_matches)} 场比赛")
    print(f"  ✓ Football-Data: {len(fd_matches)} 场比赛")

    # Extract unique teams from each source
    print("\n[2] 提取球队列表...")

    # StatsBomb teams
    sb_teams = pd.DataFrame(
        {
            "team_id": pd.concat([sb_matches["home_team_id"], sb_matches["away_team_id"]]).unique(),
            "team_name": pd.concat(
                [sb_matches["home_team_name"], sb_matches["away_team_name"]]
            ).unique(),
        }
    )

    # Football-Data teams
    fd_teams_home = fd_matches[["HomeTeam"]].rename(columns={"HomeTeam": "team_name"})
    fd_teams_away = fd_matches[["AwayTeam"]].rename(columns={"AwayTeam": "team_name"})
    fd_teams = pd.concat([fd_teams_home, fd_teams_away]).drop_duplicates().reset_index(drop=True)
    fd_teams["team_id"] = fd_teams.index.astype(str)

    print(f"  ✓ StatsBomb 球队数: {len(sb_teams)}")
    print(f"  ✓ Football-Data 球队数: {len(fd_teams)}")

    # Perform entity alignment
    print("\n[3] 执行实体对齐...")

    # Add normalized names
    sb_teams["normalized_name"] = sb_teams["team_name"].apply(normalize_team_name)
    fd_teams["normalized_name"] = fd_teams["team_name"].apply(normalize_team_name)

    # Simple matching for demonstration
    bridges = []
    for _, fd_row in fd_teams.iterrows():
        matches = sb_teams[sb_teams["normalized_name"] == fd_row["normalized_name"]]
        if len(matches) == 1:
            bridges.append(
                {
                    "source_name": "football_data",
                    "source_team_id": fd_row["team_id"],
                    "team_id": matches.iloc[0]["team_id"],
                    "fd_team_name": fd_row["team_name"],
                    "sb_team_name": matches.iloc[0]["team_name"],
                    "method": "exact_normalized",
                    "score": 1.0,
                }
            )
        elif len(matches) > 1:
            bridges.append(
                {
                    "source_name": "football_data",
                    "source_team_id": fd_row["team_id"],
                    "team_id": matches.iloc[0]["team_id"],
                    "fd_team_name": fd_row["team_name"],
                    "sb_team_name": matches.iloc[0]["team_name"],
                    "method": "ambiguous",
                    "score": 0.5,
                }
            )

    bridge_df = pd.DataFrame(bridges)

    print(f"  ✓ 匹配成功: {len(bridge_df[bridge_df['method'] == 'exact_normalized'])} 支球队")
    print(f"  ✓ 需要审核: {len(bridge_df[bridge_df['method'] == 'ambiguous'])} 支球队")

    # Show some matches
    if not bridge_df.empty:
        print("\n  匹配示例:")
        for _, row in bridge_df.head(5).iterrows():
            print(f"    {row['fd_team_name']} → {row['sb_team_name']} (score: {row['score']})")

    # Save bridge table
    bridge_path = settings.silver_root / "bridge" / "team_bridge.parquet"
    bridge_df.to_parquet(bridge_path, index=False)
    print(f"\n  ✓ 已保存: {bridge_path}")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
