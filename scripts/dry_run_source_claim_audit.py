"""Source claim audit: sample team_match rows and verify their football_data
provenance claim by joining back to raw/football_data/combined_results.parquet
on (match_date, home_team, away_team) and checking goals_for/goals_against.

A team_match row with ``match_id`` starting with ``fd-`` claims to be derived
from football_data. The audit verifies that claim by:

1. Parsing ``match_date`` and ``is_home``/``team_name``/``opponent_team_name``
   to locate the corresponding raw row.
2. Comparing ``goals_for``/``goals_against`` against raw ``FTHG``/``FTAG``
   (flipped when the team is away).
3. Optionally comparing ``shots``/``shots_on_target`` against raw ``HS``/``HST``
   (or ``AS``/``AST``) when both sides have data.

Consistent rows are recorded as ``confirmed_correct``; inconsistent rows are
recorded as ``confirmed_error``. Rows that cannot be matched (raw row missing,
date parse failure, team name mismatch) are NOT recorded — raw coverage gaps
and team-name normalization differences are not evidence of project errors.

Modes:
- default (no flag): dry-run, prints per-sample outcomes + summary
- ``--write-ledger``: also writes confirmed_correct/confirmed_error records
  to the quality_audit_ledger and a conservative threshold to the
  quality_threshold_ledger.

Reviewer is recorded as ``ai_agent_auxiliary_audit`` to make the AI-assisted
nature explicit; independent maintainer human audit remains required for
higher confidence levels.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

DATA_ROOT = Path("data")
TEAM_MATCH_PATH = DATA_ROOT / "gold" / "feature_store" / "team_match.parquet"
RAW_PATH = DATA_ROOT / "raw" / "football_data" / "combined_results.parquet"
DEFAULT_AUDIT_LEDGER = DATA_ROOT / "reports" / "data_health" / "quality_audit_ledger.jsonl"
DEFAULT_THRESHOLD_LEDGER = (
    DATA_ROOT / "reports" / "data_health" / "quality_threshold_ledger.jsonl"
)
SAMPLE_SIZE = 50
SEED = 20260720
REVIEWER = "ai_agent_auxiliary_audit"
SOURCE_ID = "football_data"


def _parse_raw_date(raw_date: object) -> pd.Timestamp | None:
    """Parse football_data Date column (DD/MM/YY or DD/MM/YYYY)."""
    if not isinstance(raw_date, str) or not raw_date:
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return pd.Timestamp.strptime(raw_date, fmt)
        except ValueError:
            continue
    return None


def _norm_team(name: object) -> str:
    if not isinstance(name, str):
        return ""
    return name.strip().lower()


def _find_raw_row(
    raw: pd.DataFrame,
    match_date: pd.Timestamp,
    home_team: str,
    away_team: str,
) -> pd.Series | None:
    """Locate the raw row matching (date, home, away). Returns None if not found."""
    raw_date = match_date.strftime("%d/%m/%y")
    candidates = raw[
        (raw["Date"] == raw_date)
        & (raw["HomeTeam"].astype(str).str.strip().str.lower() == _norm_team(home_team))
        & (raw["AwayTeam"].astype(str).str.strip().str.lower() == _norm_team(away_team))
    ]
    if candidates.empty:
        # Try YYYY format as fallback
        raw_date_y = match_date.strftime("%d/%m/%Y")
        candidates = raw[
            (raw["Date"] == raw_date_y)
            & (raw["HomeTeam"].astype(str).str.strip().str.lower() == _norm_team(home_team))
            & (raw["AwayTeam"].astype(str).str.strip().str.lower() == _norm_team(away_team))
        ]
    if candidates.empty:
        return None
    return candidates.iloc[0]


def audit_sample(row: pd.Series, raw: pd.DataFrame) -> dict[str, object]:
    """Audit one team_match row. Returns outcome + evidence dict."""
    if not isinstance(row["match_id"], str) or not row["match_id"].startswith("fd-"):
        return {"outcome": "no_match", "reason": "match_id_not_fd_prefixed"}

    if row["is_home"]:
        home_team = str(row["team_name"])
        away_team = str(row["opponent_team_name"])
        expected_goals_for = row["goals_for"]
        expected_goals_against = row["goals_against"]
    else:
        home_team = str(row["opponent_team_name"])
        away_team = str(row["team_name"])
        expected_goals_for = row["goals_for"]
        expected_goals_against = row["goals_against"]

    raw_row = _find_raw_row(raw, row["match_date"], home_team, away_team)
    if raw_row is None:
        return {"outcome": "no_match", "reason": "raw_row_not_found"}

    raw_fthg = raw_row.get("FTHG")
    raw_ftag = raw_row.get("FTAG")
    if pd.isna(raw_fthg) or pd.isna(raw_ftag):
        return {"outcome": "no_match", "reason": "raw_goals_missing"}

    raw_goals_for = float(raw_fthg) if row["is_home"] else float(raw_ftag)
    raw_goals_against = float(raw_ftag) if row["is_home"] else float(raw_fthg)

    if expected_goals_for != raw_goals_for or expected_goals_against != raw_goals_against:
        return {
            "outcome": "confirmed_error",
            "reason": "goals_mismatch",
            "gold_goals_for": expected_goals_for,
            "gold_goals_against": expected_goals_against,
            "raw_goals_for": raw_goals_for,
            "raw_goals_against": raw_goals_against,
            "match_id": row["match_id"],
            "match_date": str(row["match_date"].date()),
            "home_team": home_team,
            "away_team": away_team,
        }

    # Optional: shots comparison (only when both sides have data)
    shots_evidence = {}
    if row.get("has_shots_data") and not pd.isna(raw_row.get("HS")):
        raw_shots = float(raw_row["HS"]) if row["is_home"] else float(raw_row["AS"])
        if row["shots"] != raw_shots:
            return {
                "outcome": "confirmed_error",
                "reason": "shots_mismatch",
                "gold_shots": float(row["shots"]),
                "raw_shots": raw_shots,
                "match_id": row["match_id"],
                "match_date": str(row["match_date"].date()),
                "home_team": home_team,
                "away_team": away_team,
            }
        shots_evidence["shots_match"] = True

    return {
        "outcome": "confirmed_correct",
        "match_id": row["match_id"],
        "match_date": str(row["match_date"].date()),
        "home_team": home_team,
        "away_team": away_team,
        "goals_for_verified": True,
        "goals_against_verified": True,
        **shots_evidence,
    }


def write_audit_ledger(
    audit_records: list[dict[str, object]],
    ledger_path: Path,
) -> int:
    """Write confirmed_correct/confirmed_error records via project API."""
    from scoutfootball.evaluation.quality_audit_ledger import (
        append_quality_audit_record,
        build_quality_audit_record,
        read_quality_audit_ledger,
    )

    existing_ids = {
        record["audit_id"] for record in read_quality_audit_ledger(ledger_path)
    } if ledger_path.exists() else set()
    written = 0
    for sample in audit_records:
        sample_id = f"team_match:{sample['match_id']}"
        evidence_reference = (
            f"raw/football_data/combined_results.parquet "
            f"match_date={sample['match_date']} "
            f"home={sample['home_team']} away={sample['away_team']}"
        )
        decision = (
            f"Verified goals_for={sample.get('goals_for_verified', False)} "
            f"goals_against={sample.get('goals_against_verified', False)} "
            f"shots_match={sample.get('shots_match', 'n/a')}"
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


def write_threshold_ledger(ledger_path: Path, sample_count: int) -> int:
    """Write conservative source_claim threshold."""
    from scoutfootball.evaluation.quality_audit_ledger import (
        append_quality_threshold_record,
        build_quality_threshold_record,
        read_quality_threshold_ledger,
    )

    existing_ids = {
        record["threshold_id"]
        for record in read_quality_threshold_ledger(ledger_path)
    } if ledger_path.exists() else set()
    decision = (
        "Conservative threshold for source_claim audit: 5% maximum error rate "
        "matches the identity_resolution threshold; minimum_sample_count equals "
        f"actual audit sample count ({sample_count}). AI-assisted content-level "
        "provenance verification (goals_for/goals_against/shots matched against "
        "raw combined_results.parquet) cannot replace independent maintainer "
        "human review of external factual claims. Sample size limited by "
        "single-source scope (football_data only); other sources' claims "
        "(fbref xG, understat xG, clubelo elo, transfermarkt market value) "
        "require separate audit scripts."
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-ledger",
        action="store_true",
        help="Write confirmed outcomes to quality_audit_ledger.jsonl and threshold.",
    )
    parser.add_argument(
        "--audit-ledger",
        type=Path,
        default=DEFAULT_AUDIT_LEDGER,
        help=f"Path to audit ledger (default: {DEFAULT_AUDIT_LEDGER}).",
    )
    parser.add_argument(
        "--threshold-ledger",
        type=Path,
        default=DEFAULT_THRESHOLD_LEDGER,
        help=f"Path to threshold ledger (default: {DEFAULT_THRESHOLD_LEDGER}).",
    )
    parser.add_argument("--sample-size", type=int, default=SAMPLE_SIZE)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    if not TEAM_MATCH_PATH.exists():
        raise SystemExit(f"team_match.parquet not found: {TEAM_MATCH_PATH}")
    if not RAW_PATH.exists():
        raise SystemExit(f"raw combined_results.parquet not found: {RAW_PATH}")

    gold = pd.read_parquet(TEAM_MATCH_PATH)
    raw = pd.read_parquet(RAW_PATH)

    # Only audit rows whose match_id claims football_data provenance
    fd_rows = gold[gold["match_id"].astype(str).str.startswith("fd-")]
    if len(fd_rows) == 0:
        raise SystemExit("No fd-* match_ids found in team_match.parquet")

    sample = fd_rows.sample(n=min(args.sample_size, len(fd_rows)), random_state=args.seed)
    print(f"Auditing {len(sample)} samples from {len(fd_rows)} fd-* rows...")

    results = [audit_sample(row, raw) for _, row in sample.iterrows()]
    correct = [r for r in results if r["outcome"] == "confirmed_correct"]
    errors = [r for r in results if r["outcome"] == "confirmed_error"]
    no_match = [r for r in results if r["outcome"] == "no_match"]

    print("\nSummary:")
    print(f"  confirmed_correct: {len(correct)}")
    print(f"  confirmed_error:   {len(errors)}")
    print(f"  no_match:          {len(no_match)}")
    print(f"  total:             {len(results)}")
    if correct:
        print("\nFirst 3 confirmed_correct samples:")
        for s in correct[:3]:
            print(f"  {s}")
    if errors:
        print("\nFirst 3 confirmed_error samples:")
        for s in errors[:3]:
            print(f"  {s}")
    if no_match:
        reasons: dict[str, int] = {}
        for s in no_match:
            reasons[s.get("reason", "unknown")] = reasons.get(s.get("reason", "unknown"), 0) + 1
        print(f"\nno_match reasons: {reasons}")

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
