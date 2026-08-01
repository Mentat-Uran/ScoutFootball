#!/usr/bin/env bash
# Download StatsBomb Open Data using curl (more reliable than Python urllib)
set -euo pipefail

BASE="https://raw.githubusercontent.com/statsbomb/open-data/master/data"
OUT="data/raw/statsbomb_open"
mkdir -p "$OUT/matches" "$OUT/events" "$OUT/lineups"

# Step 1: Download matches for all target competition-seasons
echo "=== Downloading matches ==="
ALL_MIDS=()

# Competition/season pairs from the JSON we already fetched
PAIRS=(
  "9/281" "9/27"
  "16/4" "16/1" "16/2" "16/27" "16/26" "16/25" "16/24" "16/23" "16/22" "16/21" "16/41" "16/39" "16/37" "16/44" "16/76" "16/277" "16/71" "16/276"
  "11/90" "11/42" "11/4" "11/1" "11/2" "11/27" "11/26" "11/25" "11/24" "11/23" "11/22" "11/21" "11/41" "11/40" "11/39" "11/38" "11/37" "11/278"
  "7/235" "7/108" "7/27"
  "2/27" "2/44"
  "12/27" "12/86"
)

for pair in "${PAIRS[@]}"; do
  cid="${pair%%/*}"
  sid="${pair##*/}"
  echo -n "  $cid/$sid... "
  
  mkdir -p "$OUT/matches/$cid"
  outfile="$OUT/matches/$cid/$sid.json"
  
  if [ -f "$outfile" ] && [ -s "$outfile" ]; then
    echo "cached"
  else
    curl -sL --connect-timeout 10 --max-time 30 \
      -H "User-Agent: ScoutFootball/1.0" \
      "$BASE/matches/$cid/$sid.json" -o "$outfile"
    sleep 0.5
  fi
  
  # Extract match_ids
  mids=$(python3 -c "
import json
with open('$outfile') as f:
    data = json.load(f)
for m in data:
    print(m.get('match_id',''))
" 2>/dev/null || true)
  
  while IFS= read -r mid; do
    [ -n "$mid" ] && ALL_MIDS+=("$mid")
  done <<< "$mids"
done

echo ""
echo "Total matches to fetch events: ${#ALL_MIDS[@]}"

# Save match_ids
printf '%s\n' "${ALL_MIDS[@]}" > /tmp/sb_all_mids.txt

# Step 2: Download events for each match
echo ""
echo "=== Downloading events ==="
total=${#ALL_MIDS[@]}
fetched=0
skipped=0
failed=0

for mid in "${ALL_MIDS[@]}"; do
  outfile="$OUT/events/${mid}.json"
  
  if [ -f "$outfile" ] && [ -s "$outfile" ]; then
    skipped=$((skipped + 1))
    continue
  fi
  
  if curl -sL --connect-timeout 10 --max-time 60 \
    -H "User-Agent: ScoutFootball/1.0" \
    "$BASE/events/$mid.json" -o "$outfile" 2>/dev/null; then
    if [ -s "$outfile" ]; then
      fetched=$((fetched + 1))
    else
      rm -f "$outfile"
      failed=$((failed + 1))
    fi
  else
    failed=$((failed + 1))
  fi
  
  sleep 0.3
  
  if [ $((fetched % 100)) -eq 0 ] && [ $fetched -gt 0 ]; then
    echo "  $fetched fetched, $skipped skipped, $failed failed / $total total"
  fi
done

echo ""
echo "Events done: $fetched fetched, $skipped skipped, $failed failed"

# Step 3: Consolidate events into parquet
echo ""
echo "=== Consolidating events to parquet ==="
uv run python -c "
import json, pandas as pd
from pathlib import Path

out = Path('$OUT')
events_dir = out / 'events'
files = sorted(events_dir.glob('*.json'))
print(f'Found {len(files)} event JSON files')

all_events = []
for f in files:
    try:
        with open(f) as fh:
            data = json.load(fh)
        if not data:
            continue
        df = pd.json_normalize(data, sep='_')
        mid = int(f.stem)
        df.insert(0, 'match_id', mid)
        # Keep only essential columns to save space
        keep = ['match_id','event_id','index','period','timestamp','minute','second',
                'possession','duration','event_type','player_name','player_id',
                'team_name','team_id','location','pass_end_location',
                'shot_statsbomb_xg','shot_end_location','pass_shot_assist',
                'under_pressure','counterpress','possession_team_name']
        cols = [c for c in keep if c in df.columns]
        all_events.append(df[cols])
    except:
        pass

if all_events:
    combined = pd.concat(all_events, ignore_index=True)
    combined.to_parquet(out / 'events_all.parquet', index=False)
    print(f'Saved {len(combined)} events from {combined.match_id.nunique()} matches')
else:
    print('No events found')
"

echo ""
echo "=== DONE ==="
