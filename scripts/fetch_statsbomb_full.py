#!/usr/bin/env python3
"""
StatsBomb Open Data 全量获取脚本

功能:
1. 获取 competitions.json 发现五大联赛所有可用赛季
2. 每个赛季获取 matches JSON 得到 match_id 列表
3. 每场比赛获取 events JSON 和 lineups JSON，缓存到本地
4. 合并所有 events/lineups 为 parquet 文件

用法:
  python scripts/fetch_statsbomb_full.py              # 完整流程
  python scripts/fetch_statsbomb_full.py --consolidate-only  # 仅合并已有缓存
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

from scoutlab.adapters.common import CachedHttpClient, SourceFetchError
from scoutlab.config import PlatformSettings

RAW_BASE_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"

# 五大联赛 competition_id
BIG5_COMPETITIONS = {
    2: "Premier League",
    9: "1. Bundesliga",
    7: "Ligue 1",
    11: "La Liga",
    12: "Serie A",
}


def fetch_competitions(
    client: CachedHttpClient,
    sb_root: Path,
) -> list[dict]:
    """获取 competitions.json，返回五大联赛赛季列表。"""
    url = f"{RAW_BASE_URL}/competitions.json"
    cache_path = sb_root / "competitions.json"
    artifact = client.fetch(
        source_name="statsbomb_open",
        source_uri=url,
        cache_path=cache_path,
        parser_version="statsbomb_open/v0.1.0",
    )
    all_comps = json.loads(artifact.payload.decode("utf-8"))
    big5 = [c for c in all_comps if c["competition_id"] in BIG5_COMPETITIONS]
    return big5


def fetch_match_list(
    client: CachedHttpClient,
    sb_root: Path,
    comp_id: int,
    season_id: int,
) -> list[int]:
    """获取某个赛季的比赛列表，返回 match_id 列表。"""
    url = f"{RAW_BASE_URL}/matches/{comp_id}/{season_id}.json"
    cache_path = sb_root / "matches" / str(comp_id) / f"{season_id}.json"
    artifact = client.fetch(
        source_name="statsbomb_open",
        source_uri=url,
        cache_path=cache_path,
        parser_version="statsbomb_open/v0.1.0",
    )
    matches = json.loads(artifact.payload.decode("utf-8"))
    return [m["match_id"] for m in matches]


def fetch_match_events(
    client: CachedHttpClient,
    sb_root: Path,
    match_id: int,
) -> bool:
    """获取单场比赛 events JSON，缓存到 events/{match_id}.json。"""
    cache_path = sb_root / "events" / f"{match_id}.json"
    if cache_path.exists():
        return True  # 幂等：已缓存则跳过
    url = f"{RAW_BASE_URL}/events/{match_id}.json"
    try:
        client.fetch(
            source_name="statsbomb_open",
            source_uri=url,
            cache_path=cache_path,
            parser_version="statsbomb_open/v0.1.0",
        )
        return True
    except SourceFetchError as e:
        print(f"    ✗ events/{match_id}.json 失败: {e}")
        return False


def fetch_match_lineups(
    client: CachedHttpClient,
    sb_root: Path,
    match_id: int,
) -> bool:
    """获取单场比赛 lineups JSON，缓存到 lineups/{match_id}.json。"""
    cache_path = sb_root / "lineups" / f"{match_id}.json"
    if cache_path.exists():
        return True
    url = f"{RAW_BASE_URL}/lineups/{match_id}.json"
    try:
        client.fetch(
            source_name="statsbomb_open",
            source_uri=url,
            cache_path=cache_path,
            parser_version="statsbomb_open/v0.1.0",
        )
        return True
    except SourceFetchError as e:
        print(f"    ✗ lineups/{match_id}.json 失败: {e}")
        return False


def consolidate_events(sb_root: Path) -> None:
    """将所有缓存的 events JSON 合并为 events_all.parquet。"""
    events_dir = sb_root / "events"
    json_files = sorted(events_dir.glob("*.json"))
    if not json_files:
        print("  没有找到 events JSON 文件，跳过合并")
        return

    print(f"  合并 {len(json_files)} 个 events 文件...")
    frames: list[pd.DataFrame] = []
    for f in json_files:
        match_id = int(f.stem)
        try:
            records = json.loads(f.read_text("utf-8"))
            if not records:
                continue
            df = pd.json_normalize(records, sep="_")
            df.insert(0, "match_id", match_id)
            if "id" in df.columns:
                df = df.rename(columns={"id": "event_id"})
            if "type_name" in df.columns:
                df = df.rename(columns={"type_name": "event_type"})
            frames.append(df)
        except Exception as e:
            print(f"    ✗ 解析 events/{f.name} 失败: {e}")

    if not frames:
        print("  没有可合并的 events 数据")
        return

    combined = pd.concat(frames, ignore_index=True, sort=False)
    output_path = sb_root / "events_all.parquet"
    combined.to_parquet(output_path, index=False)
    print(f"  ✓ events_all.parquet: {len(combined)} 行 -> {output_path}")


def consolidate_lineups(sb_root: Path) -> None:
    """将所有缓存的 lineups JSON 合并为 lineups_all.parquet。"""
    lineups_dir = sb_root / "lineups"
    json_files = sorted(lineups_dir.glob("*.json"))
    if not json_files:
        print("  没有找到 lineups JSON 文件，跳过合并")
        return

    print(f"  合并 {len(json_files)} 个 lineups 文件...")
    frames: list[pd.DataFrame] = []
    for f in json_files:
        match_id = int(f.stem)
        try:
            records = json.loads(f.read_text("utf-8"))
            if not records:
                continue
            # lineups 是 [team1, team2]，每队有 lineup 数组
            df = pd.json_normalize(
                records,
                record_path="lineup",
                meta=["team_id", "team_name"],
                sep="_",
            )
            df.insert(0, "match_id", match_id)
            frames.append(df)
        except Exception as e:
            print(f"    ✗ 解析 lineups/{f.name} 失败: {e}")

    if not frames:
        print("  没有可合并的 lineups 数据")
        return

    combined = pd.concat(frames, ignore_index=True, sort=False)
    output_path = sb_root / "lineups_all.parquet"
    combined.to_parquet(output_path, index=False)
    print(f"  ✓ lineups_all.parquet: {len(combined)} 行 -> {output_path}")


def consolidate_matches(sb_root: Path) -> None:
    """将所有缓存的 matches JSON 合并为 big5_matches.parquet。"""
    matches_dir = sb_root / "matches"
    if not matches_dir.exists():
        print("  没有找到 matches 目录，跳过合并")
        return

    json_files = sorted(matches_dir.glob("*/*.json"))
    if not json_files:
        print("  没有找到 matches JSON 文件，跳过合并")
        return

    print(f"  合并 {len(json_files)} 个 matches 文件...")
    all_matches: list[dict] = []
    for f in json_files:
        comp_id = int(f.parent.name)
        season_id = int(f.stem)
        try:
            records = json.loads(f.read_text("utf-8"))
            for m in records:
                all_matches.append({
                    "match_id": m["match_id"],
                    "competition_id": comp_id,
                    "competition_name": m.get("competition", {}).get("competition_name", ""),
                    "season_id": season_id,
                    "season_name": m.get("season", {}).get("season_name", ""),
                    "match_date": m.get("match_date", ""),
                    "home_team_id": m.get("home_team", {}).get("home_team_id"),
                    "home_team_name": m.get("home_team", {}).get("home_team_name"),
                    "away_team_id": m.get("away_team", {}).get("away_team_id"),
                    "away_team_name": m.get("away_team", {}).get("away_team_name"),
                    "home_score": m.get("home_score"),
                    "away_score": m.get("away_score"),
                })
        except Exception as e:
            print(f"    ✗ 解析 matches/{f.parent.name}/{f.name} 失败: {e}")

    if not all_matches:
        print("  没有可合并的 matches 数据")
        return

    df = pd.DataFrame(all_matches)
    output_path = sb_root / "big5_matches.parquet"
    df.to_parquet(output_path, index=False)
    print(f"  ✓ big5_matches.parquet: {len(df)} 行 -> {output_path}")


def run_download(settings: PlatformSettings) -> None:
    """执行完整的下载流程。"""
    client = CachedHttpClient(settings=settings)
    sb_root = settings.raw_root / "statsbomb_open"

    print("=" * 60)
    print("StatsBomb Open Data - 五大联赛全量数据获取")
    print("=" * 60)

    # Step 1: 获取联赛列表
    print("\n[1] 获取可用联赛列表...")
    big5_seasons = fetch_competitions(client, sb_root)
    print(f"  ✓ 五大联赛赛季组合数: {len(big5_seasons)}")

    # Step 2: 收集所有 match_id
    print("\n[2] 获取比赛列表...")
    print("-" * 60)
    all_match_ids: list[tuple[int, int, int]] = []  # (match_id, comp_id, season_id)

    for comp in sorted(big5_seasons, key=lambda c: (c["competition_id"], c["season_id"])):
        comp_id = comp["competition_id"]
        season_id = comp["season_id"]
        comp_name = BIG5_COMPETITIONS.get(comp_id, comp.get("competition_name", "?"))
        season_name = comp["season_name"]

        try:
            match_ids = fetch_match_list(client, sb_root, comp_id, season_id)
            for mid in match_ids:
                all_match_ids.append((mid, comp_id, season_id))
            print(f"  ✓ {comp_name} {season_name}: {len(match_ids)} 场")
        except SourceFetchError as e:
            print(f"  ✗ {comp_name} {season_name}: {e}")

    print(f"\n  总比赛数: {len(all_match_ids)}")

    if not all_match_ids:
        print("没有比赛可下载，退出")
        return

    # Step 3: 逐场下载 events 和 lineups
    print("\n[3] 下载 events 和 lineups...")
    print("-" * 60)

    events_ok = 0
    events_skip = 0
    lineups_ok = 0
    lineups_skip = 0
    events_fail = 0
    lineups_fail = 0
    total = len(all_match_ids)
    start_time = time.monotonic()

    for i, (match_id, comp_id, season_id) in enumerate(all_match_ids, 1):
        # events
        events_cache = sb_root / "events" / f"{match_id}.json"
        if events_cache.exists():
            events_skip += 1
        elif fetch_match_events(client, sb_root, match_id):
            events_ok += 1
        else:
            events_fail += 1

        # lineups
        lineups_cache = sb_root / "lineups" / f"{match_id}.json"
        if lineups_cache.exists():
            lineups_skip += 1
        elif fetch_match_lineups(client, sb_root, match_id):
            lineups_ok += 1
        else:
            lineups_fail += 1

        # 进度输出
        if i % 50 == 0 or i == total:
            elapsed = time.monotonic() - start_time
            rate = i / elapsed if elapsed > 0 else 0
            eta = (total - i) / rate if rate > 0 else 0
            print(
                f"  进度: {i}/{total} "
                f"(events: {events_ok}新+{events_skip}缓存+{events_fail}失败, "
                f"lineups: {lineups_ok}新+{lineups_skip}缓存+{lineups_fail}失败) "
                f"ETA: {eta:.0f}s"
            )

    elapsed_total = time.monotonic() - start_time
    print(f"\n  下载完成，耗时 {elapsed_total:.1f}s")
    print(f"  events: {events_ok} 新下载, {events_skip} 已缓存, {events_fail} 失败")
    print(f"  lineups: {lineups_ok} 新下载, {lineups_skip} 已缓存, {lineups_fail} 失败")


def run_consolidate(settings: PlatformSettings) -> None:
    """执行合并流程（不下载）。"""
    sb_root = settings.raw_root / "statsbomb_open"

    print("=" * 60)
    print("StatsBomb Open Data - 合并缓存数据")
    print("=" * 60)

    print("\n[1] 合并 matches...")
    consolidate_matches(sb_root)

    print("\n[2] 合并 events...")
    consolidate_events(sb_root)

    print("\n[3] 合并 lineups...")
    consolidate_lineups(sb_root)

    print("\n完成!")


def main() -> bool:
    parser = argparse.ArgumentParser(description="StatsBomb Open Data 全量获取")
    parser.add_argument(
        "--consolidate-only",
        action="store_true",
        help="仅合并已有缓存，不下载新数据",
    )
    args = parser.parse_args()

    settings = PlatformSettings.from_root()

    if args.consolidate_only:
        run_consolidate(settings)
    else:
        run_download(settings)
        print("\n[4] 合并数据...")
        run_consolidate(settings)

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
