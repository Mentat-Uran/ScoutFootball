#!/usr/bin/env python3
"""Download StatsBomb Open Data with robust error handling and incremental saves."""
from __future__ import annotations

import json
import ssl
import time
import urllib.request
from pathlib import Path

import pandas as pd

RAW_BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "statsbomb_open"
TARGET_COMPETITIONS = {2, 7, 9, 11, 12, 16}
DELAY = 0.5  # seconds between requests


def fetch_json(url: str, retries: int = 3):
    ctx = ssl.create_default_context()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ScoutFootball/1.0"})
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            if attempt < retries - 1:
                time.sleep(2 ** (attempt + 1))
            else:
                return None
    return None


def download_all():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Get competition list
    print("Fetching competitions list...")
    competitions = fetch_json(f"{RAW_BASE}/competitions.json")
    if not competitions:
        print("ERROR: Could not fetch competitions list")
        return

    seen = set()
    target_seasons = []
    for comp in competitions:
        cid, sid = comp["competition_id"], comp["season_id"]
        if cid in TARGET_COMPETITIONS and (cid, sid) not in seen:
            seen.add((cid, sid))
            target_seasons.append((cid, sid, comp["season_name"], comp["competition_name"]))
    print(f"Found {len(target_seasons)} competition-seasons\n")

    # Step 2: Download matches
    all_matches = []
    for cid, sid, sname, cname in target_seasons:
        print(f"[matches] {cname} {sname}...", end=" ")
        url = f"{RAW_BASE}/matches/{cid}/{sid}.json"
        records = fetch_json(url)
        if not records:
            print("no data")
            continue
        df = pd.json_normalize(records, sep="_")
        keep = ["match_id", "match_date", "kick_off", "home_score", "away_score", "match_week"]
        nested_rename = {
            "competition_competition_id": "competition_id",
            "competition_competition_name": "competition_name",
            "season_season_id": "season_id",
            "season_season_name": "season_name",
            "home_team_home_team_id": "home_team_id",
            "home_team_home_team_name": "home_team_name",
            "away_team_away_team_id": "away_team_id",
            "away_team_away_team_name": "away_team_name",
        }
        cols = [c for c in keep if c in df.columns] + list(nested_rename.keys())
        df = df[[c for c in cols if c in df.columns]].rename(columns=nested_rename)
        all_matches.append(df)
        print(f"{len(df)} matches")
        time.sleep(DELAY)

    if not all_matches:
        print("No matches downloaded!")
        return

    combined = pd.concat(all_matches, ignore_index=True).drop_duplicates(subset=["match_id"])
    combined.to_parquet(OUT_DIR / "matches_all.parquet", index=False)
    match_ids = combined["match_id"].dropna().astype(int).tolist()
    print(f"\nTotal matches: {len(match_ids)}")

    # Step 3: Download events (incremental)
    events_path = OUT_DIR / "events_all.parquet"
    existing_match_ids = set()
    if events_path.exists():
        ex = pd.read_parquet(events_path)
        if "match_id" in ex.columns and len(ex) > 0:
            existing_match_ids = set(ex["match_id"].unique())
    to_fetch = [m for m in match_ids if m not in existing_match_ids]
    print(f"\nDownloading events: {len(to_fetch)} to fetch, {len(existing_match_ids)} already done")

    new_events = []
    failed = 0
    for i, mid in enumerate(to_fetch):
        url = f"{RAW_BASE}/events/{mid}.json"
        records = fetch_json(url)
        if not records:
            failed += 1
            continue
        df = pd.json_normalize(records, sep="_")
        df = df.rename(columns={"id": "event_id", "type_name": "event_type"})
        df.insert(0, "match_id", mid)
        new_events.append(df)
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(to_fetch)} fetched, {failed} failed")
        time.sleep(DELAY)

    if new_events:
        new_df = pd.concat(new_events, ignore_index=True)
        if existing_match_ids and events_path.exists():
            old = pd.read_parquet(events_path)
            combined_e = pd.concat([old, new_df], ignore_index=True)
        else:
            combined_e = new_df
        combined_e.to_parquet(events_path, index=False)
        print(f"Events saved: {len(combined_e)} rows, {combined_e.match_id.nunique()} matches")
    print(f"Failed: {failed}")

    # Step 4: Download lineups (incremental)
    lu_path = OUT_DIR / "lineups_all.parquet"
    existing_lu_ids = set()
    if lu_path.exists():
        ex_lu = pd.read_parquet(lu_path)
        if "match_id" in ex_lu.columns and len(ex_lu) > 0:
            existing_lu_ids = set(ex_lu["match_id"].unique())
    to_fetch_lu = [m for m in match_ids if m not in existing_lu_ids]
    print(f"\nDownloading lineups: {len(to_fetch_lu)} to fetch")

    new_lineups = []
    for i, mid in enumerate(to_fetch_lu):
        url = f"{RAW_BASE}/lineups/{mid}.json"
        records = fetch_json(url)
        if not records:
            continue
        for team in records:
            for player in team.get("lineup", []):
                player["team_id"] = team.get("team_id")
                player["team_name"] = team.get("team_name")
                player["match_id"] = mid
                new_lineups.append(player)
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(to_fetch_lu)} done")
        time.sleep(DELAY)

    if new_lineups:
        new_lu = pd.DataFrame(new_lineups)
        if existing_lu_ids and lu_path.exists():
            old_lu = pd.read_parquet(lu_path)
            combined_lu = pd.concat([old_lu, new_lu], ignore_index=True)
        else:
            combined_lu = new_lu
        combined_lu.to_parquet(lu_path, index=False)
        print(f"Lineups saved: {len(combined_lu)} rows, {combined_lu.match_id.nunique()} matches")

    print("\n=== DONE ===")


if __name__ == "__main__":
    download_all()
