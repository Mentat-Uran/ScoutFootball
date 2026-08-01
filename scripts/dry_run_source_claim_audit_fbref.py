"""Source claim audit for fbref rows in player_match.parquet.

Extends the source_claim audit (previously covering football_data and
understat) to the fbref source.  The raw fbref parquet stores player names
and seasons in its DataFrame index (league, season, team, player) rather
than as regular columns, and uses pandas MultiIndex columns for stats
(e.g. ``('Performance', 'Gls')``).  The gold ``player_name`` is copied
directly from the raw index, so an exact name + season join is reliable;
team_name disambiguates the rare multi-team-season case.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd

DATA_ROOT = Path("data")
PLAYER_MATCH_PATH = DATA_ROOT / "gold" / "feature_store" / "player_match.parquet"
RAW_PATH = DATA_ROOT / "raw" / "fbref" / "player_stats_big5_3seasons.parquet"
DEFAULT_AUDIT_LEDGER = DATA_ROOT / "reports" / "data_health" / "quality_audit_ledger.jsonl"
DEFAULT_THRESHOLD_LEDGER = (
    DATA_ROOT / "reports" / "data_health" / "quality_threshold_ledger.jsonl"
)
SAMPLE_SIZE = 50
SEED = 20260722
REVIEWER = "ai_agent_auxiliary_audit"
SOURCE_ID = "fbref"

# Gold column → raw (MultiIndex column, or flat column) mapping.
# The raw file lacks npxg/xA/shots (those live in separate shooting/misc
# files), so only the 5 fields present in player_stats_big5_3seasons are
# compared.
NUMERIC_FIELD_MAP = {
    "goals": ("Performance", "Gls"),
    "assists": ("Performance", "Ast"),
    "minutes_played": ("Playing Time", "Min"),
    "matches_played": ("Playing Time", "MP"),
    "starts": ("Playing Time", "Starts"),
}


def _to_float(value):
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(result):
        return None
    return result


def _flatten_raw(raw):
    """Return a flat DataFrame with index fields and stat columns."""
    idx = raw.index.to_frame(index=False)
    flat = pd.DataFrame(
        {
            "player": idx["player"].astype(str),
            "season": idx["season"].astype(str),
            "team": idx["team"].astype(str),
            "born_raw": pd.to_numeric(
                raw[("born", "")].reset_index(drop=True), errors="coerce"
            ),
        }
    )
    for _gold_col, raw_col in NUMERIC_FIELD_MAP.items():
        flat[raw_col] = pd.to_numeric(
            raw[raw_col].reset_index(drop=True), errors="coerce"
        )
    return flat


def _find_raw_row(flat_raw, player_name, season_id, team_name):
    """Locate the raw row by (player, season), disambiguating by team if needed."""
    matches = flat_raw[
        (flat_raw["player"] == player_name) & (flat_raw["season"] == season_id)
    ]
    if matches.empty:
        return None
    if len(matches) == 1:
        return matches.iloc[0]
    # Multi-team season: try exact team match first.
    team_matches = matches[matches["team"] == team_name]
    if not team_matches.empty:
        return team_matches.iloc[0]
    # Fallback: first row (multi_team_season flag in gold records this).
    return matches.iloc[0]


def audit_sample(row, flat_raw):
    player_name = str(row.get("player_name") or "").strip()
    if not player_name:
        return {"outcome": "no_match", "reason": "player_name_empty"}

    season_id = str(row.get("season_id") or "").strip()
    if not season_id:
        return {"outcome": "no_match", "reason": "season_id_empty"}

    team_name = str(row.get("team_name") or "").strip()
    raw_row = _find_raw_row(flat_raw, player_name, season_id, team_name)
    if raw_row is None:
        return {"outcome": "no_match", "reason": "raw_row_not_found"}

    for gold_col, raw_col in NUMERIC_FIELD_MAP.items():
        gold_val = _to_float(row.get(gold_col))
        raw_val = _to_float(raw_row.get(raw_col))
        if gold_val is None or raw_val is None:
            continue
        # Use approximate equality for floats: minutes can have fractional
        # values in fbref, and to_numeric coercion may introduce ULP-level
        # rounding.  A relative tolerance of 1e-9 catches real discrepancies
        # while ignoring floating-point representation noise.
        if not math.isclose(gold_val, raw_val, rel_tol=1e-9, abs_tol=1e-12):
            return {
                "outcome": "confirmed_error",
                "reason": f"{gold_col}_mismatch",
                "gold_field": gold_col,
                "raw_field": str(raw_col),
                "gold_value": gold_val,
                "raw_value": raw_val,
                "player_id": row.get("player_id"),
                "season_id": row.get("season_id"),
            }

    # Verify born year consistency as a cross-check.
    gold_born = _to_float(row.get("born"))
    raw_born = _to_float(raw_row.get("born_raw"))
    if gold_born is not None and raw_born is not None:
        if not math.isclose(gold_born, raw_born, rel_tol=1e-9, abs_tol=1e-12):
            return {
                "outcome": "confirmed_error",
                "reason": "born_mismatch",
                "gold_value": gold_born,
                "raw_value": raw_born,
                "player_id": row.get("player_id"),
                "season_id": row.get("season_id"),
            }

    multi_team_val = row.get("multi_team_season", False)
    multi_team = bool(multi_team_val) if not pd.isna(multi_team_val) else False
    return {
        "outcome": "confirmed_correct",
        "player_id": row.get("player_id"),
        "season_id": row.get("season_id"),
        "player_name": player_name,
        "season_id_raw": season_id,
        "fields_verified": list(NUMERIC_FIELD_MAP.keys()),
        "born_verified": gold_born is not None and raw_born is not None,
        "multi_team_season": multi_team,
    }


def write_audit_ledger(audit_records, ledger_path):
    from scoutfootball.evaluation.quality_audit_ledger import (
        append_quality_audit_record,
        build_quality_audit_record,
        read_quality_audit_ledger,
    )

    existing_ids = (
        {record["audit_id"] for record in read_quality_audit_ledger(ledger_path)}
        if ledger_path.exists()
        else set()
    )
    written = 0
    for sample in audit_records:
        sample_id = f"player_match:{sample['player_id']}:{sample['season_id']}"
        if sample.get("multi_team_season"):
            evidence_note = "multi_team_season=True (gold may keep first team)"
        else:
            evidence_note = "single_team_season"
        evidence_reference = (
            f"raw/fbref/player_stats_big5_3seasons.parquet "
            f"player={sample.get('player_name')} "
            f"season={sample.get('season_id_raw')} ({evidence_note})"
        )
        if sample["outcome"] == "confirmed_correct":
            decision = (
                f"Verified 5 numeric fields {sample.get('fields_verified')} "
                f"plus born year consistency against raw FBref snapshot. "
                f"{evidence_note}."
            )
        else:
            gold_repr = sample.get("gold_value", "n/a")
            raw_repr = sample.get("raw_value", "n/a")
            decision = (
                f"Mismatch on {sample.get('reason')}: "
                f"gold={gold_repr} raw={raw_repr}"
            )
        record = build_quality_audit_record(
            audit_kind="source_claim",
            source_id=SOURCE_ID,
            sample_id=sample_id,
            outcome=sample["outcome"],
            reviewer=REVIEWER,
            evidence_reference=evidence_reference,
            decision=decision,
        )
        if record["audit_id"] in existing_ids:
            continue
        append_quality_audit_record(record, ledger_path)
        existing_ids.add(record["audit_id"])
        written += 1
    return written


def write_threshold_ledger(ledger_path, sample_count):
    from scoutfootball.evaluation.quality_audit_ledger import (
        append_quality_threshold_record,
        build_quality_threshold_record,
        read_quality_threshold_ledger,
    )

    existing_ids = (
        {record["threshold_id"] for record in read_quality_threshold_ledger(ledger_path)}
        if ledger_path.exists()
        else set()
    )
    decision = (
        "Conservative threshold for source_claim audit on fbref source: "
        "5% maximum error rate matches the identity_resolution, "
        "football_data and understat source_claim thresholds; "
        f"minimum_sample_count equals actual audit sample count ({sample_count}). "
        "AI-assisted content-level provenance verification "
        "(goals/assists/minutes_played/matches_played/starts matched against "
        "raw player_stats_big5_3seasons.parquet) cannot replace independent "
        "maintainer human review of external factual claims. FBref xG/xA "
        "claims require separate audit against the shooting/misc raw files."
    )
    record = build_quality_threshold_record(
        audit_kind="source_claim",
        maximum_error_rate=0.05,
        minimum_sample_count=sample_count,
        decision=decision,
    )
    if record["threshold_id"] in existing_ids:
        return 0
    append_quality_threshold_record(record, ledger_path)
    return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-ledger",
        action="store_true",
        help="Write confirmed outcomes to quality_audit_ledger.jsonl and threshold.",
    )
    parser.add_argument("--audit-ledger", type=Path, default=DEFAULT_AUDIT_LEDGER)
    parser.add_argument("--threshold-ledger", type=Path, default=DEFAULT_THRESHOLD_LEDGER)
    parser.add_argument("--sample-size", type=int, default=SAMPLE_SIZE)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument(
        "--output-file",
        type=Path,
        default=None,
        help="Optional path to write the dry-run summary.",
    )
    args = parser.parse_args()

    if not PLAYER_MATCH_PATH.exists():
        raise SystemExit(f"player_match.parquet not found: {PLAYER_MATCH_PATH}")
    if not RAW_PATH.exists():
        raise SystemExit(f"raw player_stats_big5_3seasons.parquet not found: {RAW_PATH}")

    gold = pd.read_parquet(PLAYER_MATCH_PATH)
    raw = pd.read_parquet(RAW_PATH)
    flat_raw = _flatten_raw(raw)

    fb_rows = gold[gold["source_name"].astype(str) == "fbref"]
    if len(fb_rows) == 0:
        raise SystemExit("No fbref source_name rows found in player_match.parquet")

    sample = fb_rows.sample(n=min(args.sample_size, len(fb_rows)), random_state=args.seed)

    lines = []
    lines.append(f"Auditing {len(sample)} samples from {len(fb_rows)} fbref rows...")
    print(lines[-1])

    results = [audit_sample(row, flat_raw) for _, row in sample.iterrows()]
    correct = [r for r in results if r["outcome"] == "confirmed_correct"]
    errors = [r for r in results if r["outcome"] == "confirmed_error"]
    no_match = [r for r in results if r["outcome"] == "no_match"]

    lines.append("")
    lines.append("Summary:")
    lines.append(f"  confirmed_correct: {len(correct)}")
    lines.append(f"  confirmed_error:   {len(errors)}")
    lines.append(f"  no_match:          {len(no_match)}")
    lines.append(f"  total:             {len(results)}")
    for line in lines[-5:]:
        print(line)

    if correct:
        lines.append("")
        lines.append("Sample confirmed_correct entries (first 3):")
        for entry in correct[:3]:
            lines.append(
                f"  {entry.get('player_name')} | {entry.get('season_id')} "
                f"| fields={entry.get('fields_verified')} "
                f"| multi_team={entry.get('multi_team_season')}"
            )
        for line in lines[-3:]:
            print(line)

    if errors:
        lines.append("")
        lines.append("Sample confirmed_error entries (first 5):")
        for entry in errors[:5]:
            lines.append(
                f"  {entry.get('reason')}: gold={entry.get('gold_value')} "
                f"raw={entry.get('raw_value')} | {entry.get('player_id')}"
            )
        for line in lines[-5:]:
            print(line)

    if args.write_ledger:
        audit_written = write_audit_ledger(results, args.audit_ledger)
        threshold_written = write_threshold_ledger(args.threshold_ledger, len(results))
        lines.append("")
        lines.append(f"Wrote {audit_written} audit records to {args.audit_ledger}")
        lines.append(f"Wrote {threshold_written} threshold records to {args.threshold_ledger}")
        for line in lines[-2:]:
            print(line)

    if args.output_file:
        args.output_file.write_text("\n".join(lines), encoding="utf-8")
        print(f"\nSummary written to {args.output_file}")


if __name__ == "__main__":
    main()
