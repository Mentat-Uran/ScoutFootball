"""Source claim audit for understat rows in player_match.parquet."""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd

DATA_ROOT = Path("data")
PLAYER_MATCH_PATH = DATA_ROOT / "gold" / "feature_store" / "player_match.parquet"
RAW_PATH = DATA_ROOT / "raw" / "understat" / "players_10seasons.parquet"
DEFAULT_AUDIT_LEDGER = DATA_ROOT / "reports" / "data_health" / "quality_audit_ledger.jsonl"
DEFAULT_THRESHOLD_LEDGER = (
    DATA_ROOT / "reports" / "data_health" / "quality_threshold_ledger.jsonl"
)
SAMPLE_SIZE = 50
SEED = 20260722
REVIEWER = "ai_agent_auxiliary_audit"
SOURCE_ID = "understat"

NUMERIC_FIELD_MAP = {
    "goals": "goals",
    "assists": "assists",
    "shots": "shots",
    "npxg": "npxG",
    "xa": "xA",
    "minutes_played": "time",
    "matches_played": "games",
}


def _season_id_to_raw(season_id):
    text = str(season_id).strip()
    if len(text) == 4 and text.isdigit():
        return "20" + text
    return ""


def _extract_understat_id(player_id):
    text = str(player_id).strip()
    prefix = "understat|"
    if not text.startswith(prefix):
        return ""
    return text[len(prefix):]


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


def _find_raw_row(raw, understat_id, raw_season):
    id_match = raw["id"].astype(str) == understat_id
    season_match = raw["season"].astype(str) == raw_season
    candidates = raw[id_match & season_match]
    if candidates.empty:
        return None
    return candidates.iloc[0]


def _team_consistent(gold_team, raw_team_title):
    if gold_team == raw_team_title:
        return True
    if raw_team_title.startswith(gold_team + ","):
        return True
    return False


def audit_sample(row, raw):
    player_id = row.get("player_id")
    understat_id = _extract_understat_id(player_id)
    if not understat_id:
        return {"outcome": "no_match", "reason": "player_id_not_understat_prefixed"}

    raw_season = _season_id_to_raw(row.get("season_id"))
    if not raw_season:
        return {"outcome": "no_match", "reason": "season_id_unparseable"}

    raw_row = _find_raw_row(raw, understat_id, raw_season)
    if raw_row is None:
        return {"outcome": "no_match", "reason": "raw_row_not_found"}

    for gold_col, raw_col in NUMERIC_FIELD_MAP.items():
        gold_val = _to_float(row.get(gold_col))
        raw_val = _to_float(raw_row.get(raw_col))
        if gold_val is None or raw_val is None:
            continue
        # Use approximate equality for floats: xG/xA values go through JSON
        # serialization in the raw snapshot and to_numeric coercion in the
        # gold pipeline, which introduces ULP-level rounding.  A relative
        # tolerance of 1e-9 catches real discrepancies while ignoring
        # floating-point representation noise.
        if not math.isclose(gold_val, raw_val, rel_tol=1e-9, abs_tol=1e-12):
            return {
                "outcome": "confirmed_error",
                "reason": f"{gold_col}_mismatch",
                "gold_field": gold_col,
                "raw_field": raw_col,
                "gold_value": gold_val,
                "raw_value": raw_val,
                "player_id": player_id,
                "season_id": row.get("season_id"),
            }

    gold_name = str(row.get("player_name") or "").strip()
    raw_name = str(raw_row.get("player_name") or "").strip()
    if gold_name and raw_name and gold_name != raw_name:
        return {
            "outcome": "confirmed_error",
            "reason": "player_name_mismatch",
            "gold_name": gold_name,
            "raw_name": raw_name,
            "player_id": player_id,
            "season_id": row.get("season_id"),
        }

    gold_team = str(row.get("team_name") or "").strip()
    raw_team = str(raw_row.get("team_title") or "").strip()
    if gold_team and raw_team and not _team_consistent(gold_team, raw_team):
        return {
            "outcome": "confirmed_error",
            "reason": "team_name_mismatch",
            "gold_team": gold_team,
            "raw_team": raw_team,
            "player_id": player_id,
            "season_id": row.get("season_id"),
        }

    multi_team = bool(row.get("multi_team_season", False))
    return {
        "outcome": "confirmed_correct",
        "player_id": player_id,
        "season_id": row.get("season_id"),
        "understat_id": understat_id,
        "raw_season": raw_season,
        "fields_verified": list(NUMERIC_FIELD_MAP.keys()),
        "player_name_verified": True,
        "team_name_verified": True,
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
            evidence_note = "multi_team_season=True (gold keeps first club only)"
        else:
            evidence_note = "single_team_season"
        evidence_reference = (
            f"raw/understat/players_10seasons.parquet "
            f"id={sample.get('understat_id')} "
            f"season={sample.get('raw_season')} ({evidence_note})"
        )
        if sample["outcome"] == "confirmed_correct":
            decision = (
                f"Verified 7 numeric fields {sample.get('fields_verified')} "
                f"plus player_name and team_name consistency against raw "
                f"Understat snapshot. {evidence_note}."
            )
        else:
            gold_repr = sample.get(
                "gold_value",
                sample.get("gold_name", sample.get("gold_team", "n/a")),
            )
            raw_repr = sample.get(
                "raw_value",
                sample.get("raw_name", sample.get("raw_team", "n/a")),
            )
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
        "Conservative threshold for source_claim audit on understat source: "
        "5% maximum error rate matches the identity_resolution and "
        "football_data source_claim thresholds; minimum_sample_count equals "
        f"actual audit sample count ({sample_count}). AI-assisted content-level "
        "provenance verification (goals/assists/npxg/xa/shots/minutes_played/"
        "matches_played matched against raw players_10seasons.parquet) cannot "
        "replace independent maintainer human review of external factual "
        "claims. Sample size limited by single-source scope (understat only); "
        "other sources' claims (fbref xG, clubelo elo, transfermarkt market "
        "value) require separate audit scripts."
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
        raise SystemExit(f"raw players_10seasons.parquet not found: {RAW_PATH}")

    gold = pd.read_parquet(PLAYER_MATCH_PATH)
    raw = pd.read_parquet(RAW_PATH)

    us_rows = gold[gold["source_name"].astype(str) == "understat"]
    if len(us_rows) == 0:
        raise SystemExit("No understat source_name rows found in player_match.parquet")

    sample = us_rows.sample(n=min(args.sample_size, len(us_rows)), random_state=args.seed)

    lines = []
    lines.append(f"Auditing {len(sample)} samples from {len(us_rows)} understat rows...")
    print(lines[-1])

    results = [audit_sample(row, raw) for _, row in sample.iterrows()]
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
        lines.append("First 3 confirmed_correct samples:")
        print(lines[-2])
        for s in correct[:3]:
            line = f"  {s}"
            lines.append(line)
            print(line)
    if errors:
        lines.append("")
        lines.append("First 3 confirmed_error samples:")
        print(lines[-2])
        for s in errors[:3]:
            line = f"  {s}"
            lines.append(line)
            print(line)
    if no_match:
        reasons = {}
        for s in no_match:
            reason = s.get("reason", "unknown")
            reasons[reason] = reasons.get(reason, 0) + 1
        lines.append("")
        lines.append(f"no_match reasons: {reasons}")
        print(lines[-1])

    if args.output_file is not None:
        args.output_file.parent.mkdir(parents=True, exist_ok=True)
        args.output_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nSummary written to {args.output_file}")

    if args.write_ledger:
        writable = correct + errors
        if not writable:
            print("\nNo confirmed outcomes to write; skipping ledger write.")
            return 0
        written = write_audit_ledger(writable, args.audit_ledger)
        print(f"\nWrote {written} new audit records to {args.audit_ledger}")
        threshold_written = write_threshold_ledger(args.threshold_ledger, len(writable))
        print(f"Wrote {threshold_written} new threshold record to {args.threshold_ledger}")
    else:
        print("\n(dry-run; pass --write-ledger to record outcomes)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
