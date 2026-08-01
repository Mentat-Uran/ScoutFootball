#!/usr/bin/env python3
"""Consolidate StatsBomb event JSON files into a single Parquet.

Processes JSON directly (not via pd.json_normalize) for speed.
Only extracts the columns needed for xT/action-value computation.
"""
import gc
import json
from pathlib import Path

import pandas as pd

EVENTS_DIR = Path("data/raw/statsbomb_open/events")
OUT_PATH = Path("data/raw/statsbomb_open/events_all.parquet")

# Columns to extract (flattened from nested JSON)
NESTED_MAP = {
    "type_name": "event_type",
    "player_id": "player_id",
    "player_name": "player_name",
    "team_id": "team_id",
    "team_name": "team_name",
    "shot_statsbomb_xg": "shot_statsbomb_xg",
    "shot_outcome_name": "shot_outcome_name",
    "pass_outcome_name": "pass_outcome_name",
    "pass_end_location": "pass_end_location",
    "shot_end_location": "shot_end_location",
}


def extract_event(ev: dict, match_id: int) -> dict | None:
    """Extract relevant fields from a raw StatsBomb event dict."""
    etype = ev.get("type", {})
    if isinstance(etype, dict):
        etype_name = etype.get("name", "")
    else:
        etype_name = str(etype)

    # Skip non-actionable events
    if etype_name in ("Half Start", "Half End", "Starting XI", "Substitution",
                      "Injury Stoppage", "Referee Ball-Drop", "Bad Behaviour",
                      "Offside", "Tactical Shift", "Error"):
        return None

    player = ev.get("player", {})
    team = ev.get("team", {})
    shot = ev.get("shot", {})
    pas = ev.get("pass", {})

    row = {
        "match_id": match_id,
        "event_id": ev.get("id", ""),
        "index": ev.get("index", 0),
        "period": ev.get("period", 1),
        "minute": ev.get("minute", 0),
        "second": ev.get("second", 0),
        "possession": ev.get("possession", 0),
        "duration": ev.get("duration", 0.0),
        "event_type": etype_name,
        "player_id": player.get("id", 0) if isinstance(player, dict) else 0,
        "player_name": player.get("name", "") if isinstance(player, dict) else "",
        "team_id": team.get("id", 0) if isinstance(team, dict) else 0,
        "team_name": team.get("name", "") if isinstance(team, dict) else "",
        "location": ev.get("location"),
        "pass_end_location": pas.get("end_location") if isinstance(pas, dict) else None,
        "shot_end_location": shot.get("end_location") if isinstance(shot, dict) else None,
        "shot_statsbomb_xg": shot.get("statsbomb_xg") if isinstance(shot, dict) else None,
        "shot_outcome_name": (
            shot.get("outcome", {}).get("name") if isinstance(shot, dict) else None
        ),
        "pass_outcome_name": pas.get("outcome", {}).get("name") if isinstance(pas, dict) else None,
    }
    return row


def main():
    files = sorted(EVENTS_DIR.glob("*.json"))
    print(f"Processing {len(files)} event files...")

    chunk_size = 300
    chunks = []

    for i in range(0, len(files), chunk_size):
        chunk_files = files[i:i + chunk_size]
        rows = []
        for f in chunk_files:
            try:
                with open(f) as fh:
                    data = json.load(fh)
                if not data:
                    continue
                mid = int(f.stem)
                for ev in data:
                    row = extract_event(ev, mid)
                    if row is not None:
                        rows.append(row)
            except Exception:
                pass

        if rows:
            df = pd.DataFrame(rows)
            # Expand location lists into x, y columns
            for col in ["location", "pass_end_location", "shot_end_location"]:
                if col in df.columns:
                    df[f"{col}_x"] = df[col].apply(
                        lambda v: v[0] if isinstance(v, list) and len(v) >= 2 else None
                    )
                    df[f"{col}_y"] = df[col].apply(
                        lambda v: v[1] if isinstance(v, list) and len(v) >= 2 else None
                    )
                    df = df.drop(columns=[col])
            chunks.append(df)
            print(f"  chunk {i // chunk_size + 1}: {len(rows)} actions")
            del rows, df
            gc.collect()

    print(f"Concatenating {len(chunks)} chunks...")
    combined = pd.concat(chunks, ignore_index=True)
    combined.to_parquet(OUT_PATH, index=False)
    print(f"Saved {len(combined)} events, {combined.match_id.nunique()} matches")
    print(f"Columns: {sorted(combined.columns.tolist())}")
    shots = combined[combined.event_type == "Shot"]
    print(f"Shots: {len(shots)}, goals: {(shots.shot_outcome_name == 'Goal').sum()}")


if __name__ == "__main__":
    main()
