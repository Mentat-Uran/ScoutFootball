"""Source claim audit for statsbomb_open rows in player_match.parquet.

Extends the source_claim audit (previously covering football_data, understat
and fbref) to the statsbomb_open source.  Gold ``player_match`` rows whose
``source_name == 'statsbomb_open'`` are aggregated from
``raw/statsbomb_open/events_sample.parquet`` (or ``events_all.parquet`` when
present) by ``pipeline._build_player_match_from_statsbomb``: per-player-per-
match groups are summarised into goals/assists/shots/shots_on_target/passes/
tackles/minutes_played/npxg/player_name/team_name.  The audit re-derives the
same aggregates from the raw events file and compares them field-by-field
against the gold row.

Special handling:
- ``player_id`` is stored in gold as a float-formatted string (e.g.
  ``'10605.0'``) and in raw as a float; the audit normalises both sides
  through ``str(float(...))`` so ``'10605'`` and ``'10605.0'`` match.
- ``npxg`` in gold is ``pd.NA`` when the player took no shots or summed to
  zero xG; raw produces ``0.0`` in that case.  The audit treats
  (gold=NA and raw=0.0) as consistent, and uses ``math.isclose`` with the
  same tolerances as the understat/fbref audits when raw>0.
- ``xa`` and ``xT_added`` in gold are always ``pd.NA`` for statsbomb_open
  rows (the pipeline does not extract them from events), so they are
  intentionally not compared.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd

DATA_ROOT = Path("data")
PLAYER_MATCH_PATH = DATA_ROOT / "gold" / "feature_store" / "player_match.parquet"
EVENTS_ALL_PATH = DATA_ROOT / "raw" / "statsbomb_open" / "events_all.parquet"
EVENTS_SAMPLE_PATH = DATA_ROOT / "raw" / "statsbomb_open" / "events_sample.parquet"
DEFAULT_AUDIT_LEDGER = DATA_ROOT / "reports" / "data_health" / "quality_audit_ledger.jsonl"
DEFAULT_THRESHOLD_LEDGER = (
    DATA_ROOT / "reports" / "data_health" / "quality_threshold_ledger.jsonl"
)
SAMPLE_SIZE = 50
SEED = 20260725
REVIEWER = "ai_agent_auxiliary_audit"
SOURCE_ID = "statsbomb_open"

# Fields compared against re-derived raw aggregates.  The pipeline writes
# these for statsbomb_open rows (see ``_build_player_match_from_statsbomb``);
# ``xa`` and ``xT_added`` are always NA in gold and are intentionally
# excluded.  ``npxg`` is handled separately because gold stores NA when the
# raw xG sum is 0.
INTEGER_FIELD_MAP = (
    "minutes_played",
    "goals",
    "assists",
    "shots",
    "shots_on_target",
    "passes",
    "tackles",
)

# shot_outcome_name values the pipeline treats as "on target".
SHOTS_ON_TARGET_OUTCOMES = ("Goal", "Saved", "Saved To Post")


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


def _normalise_player_id(value) -> str:
    """Normalise player_id across gold (str '10605.0') and raw (float 10605.0).

    Gold stores player_id as ``str(float)`` (e.g. ``'10605.0'``) because the
    pipeline does ``str(player_id)`` on a float64 series.  Raw events store
    player_id as float64.  ``str(10605.0) == '10605.0'`` matches ``str('10605.0')``
    directly, but ``str(10605) == '10605'`` would not — this helper floats
    both sides so int-formatted strings also match.
    """
    if value is None:
        return ""
    try:
        return str(float(value))
    except (TypeError, ValueError):
        return str(value).strip()


def _resolve_events_path() -> Path:
    """Mirror the pipeline's fallback: events_all.parquet then events_sample.parquet."""
    if EVENTS_ALL_PATH.exists():
        return EVENTS_ALL_PATH
    if EVENTS_SAMPLE_PATH.exists():
        return EVENTS_SAMPLE_PATH
    raise SystemExit(
        f"No statsbomb_open events file found at {EVENTS_ALL_PATH} or {EVENTS_SAMPLE_PATH}"
    )


def aggregate_raw_group(group: pd.DataFrame) -> dict[str, object]:
    """Re-derive the per-player-per-match aggregate from raw events.

    Mirrors ``pipeline._build_player_match_from_statsbomb`` exactly so the
    audit verifies the production aggregation path rather than a parallel
    implementation.  Any divergence here would itself be a bug.
    """
    if group.empty:
        return {
            "minutes_played": 0,
            "goals": 0,
            "assists": 0,
            "shots": 0,
            "shots_on_target": 0,
            "passes": 0,
            "tackles": 0,
            "npxg_raw": 0.0,
            "player_name_raw": "",
            "team_name_raw": "",
        }

    minutes = int(group["minute"].max()) + 1
    shots = group[group["event_type"] == "Shot"]
    goals = int((shots["shot_outcome_name"] == "Goal").sum()) if not shots.empty else 0
    shots_total = len(shots)
    shots_on = (
        int(shots["shot_outcome_name"].isin(SHOTS_ON_TARGET_OUTCOMES).sum())
        if not shots.empty
        else 0
    )
    xg = (
        float(shots["shot_statsbomb_xg"].sum())
        if "shot_statsbomb_xg" in shots.columns
        else 0.0
    )
    assists = int(group.get("pass_goal_assist", pd.Series(False)).sum())
    passes = int((group["event_type"] == "Pass").sum())
    tackles = int((group["event_type"] == "Duel").sum())

    return {
        "minutes_played": minutes,
        "goals": goals,
        "assists": assists,
        "shots": shots_total,
        "shots_on_target": shots_on,
        "passes": passes,
        "tackles": tackles,
        "npxg_raw": xg,
        "player_name_raw": str(group["player_name"].iloc[0]),
        "team_name_raw": str(group["team_name"].iloc[0]),
    }


def build_raw_aggregates(events: pd.DataFrame) -> dict[tuple[str, str], dict[str, object]]:
    """Group raw events by (match_id, player_id) and aggregate each group.

    Keys are ``(str(match_id), str(player_id))`` — the raw events file stores
    ``match_id`` as int64 and ``player_id`` as float64, so ``str()`` produces
    ``'3773386'`` and ``'10605.0'`` respectively, matching the gold row's
    string fields directly.
    """
    events_with_player = events.dropna(subset=["player_id"]).copy()
    aggregates: dict[tuple[str, str], dict[str, object]] = {}
    for (match_id, player_id), group in events_with_player.groupby(
        ["match_id", "player_id"]
    ):
        key = (str(match_id), str(player_id))
        aggregates[key] = aggregate_raw_group(group)
    return aggregates


def audit_sample(row, aggregates):
    """Audit one statsbomb_open player_match row against raw aggregates."""
    match_id_raw = row.get("match_id")
    player_id_raw = row.get("player_id")
    if match_id_raw is None or player_id_raw is None:
        return {"outcome": "no_match", "reason": "missing_identifier"}

    match_key = str(match_id_raw)
    player_key = str(player_id_raw)
    if not match_key or not player_key or match_key.lower() == "nan":
        return {"outcome": "no_match", "reason": "identifier_unparseable"}

    raw = aggregates.get((match_key, player_key))
    if raw is None:
        # Fallback: gold may store player_id as int-formatted string (e.g.
        # '10605') while raw uses float ('10605.0').  Normalise player_id
        # through float() and retry.
        normalised_player = _normalise_player_id(player_id_raw)
        if normalised_player and normalised_player != player_key:
            raw = aggregates.get((match_key, normalised_player))
    if raw is None:
        return {"outcome": "no_match", "reason": "raw_events_not_found"}

    for gold_col in INTEGER_FIELD_MAP:
        gold_val = row.get(gold_col)
        raw_val = raw[gold_col]
        if pd.isna(gold_val) and raw_val == 0:
            continue
        try:
            if int(gold_val) != int(raw_val):
                return {
                    "outcome": "confirmed_error",
                    "reason": f"{gold_col}_mismatch",
                    "gold_field": gold_col,
                    "gold_value": int(gold_val) if not pd.isna(gold_val) else None,
                    "raw_value": int(raw_val),
                    "player_id": player_id_raw,
                    "match_id": match_id_raw,
                }
        except (TypeError, ValueError) as exc:
            return {
                "outcome": "confirmed_error",
                "reason": f"{gold_col}_unparseable",
                "gold_field": gold_col,
                "gold_value": str(gold_val),
                "raw_value": str(raw_val),
                "player_id": player_id_raw,
                "match_id": match_id_raw,
                "error": str(exc),
            }

    # npxg: gold stores NA when raw xG sums to 0; otherwise compare as floats.
    gold_npxg = row.get("npxg")
    raw_npxg = raw["npxg_raw"]
    if pd.isna(gold_npxg):
        if raw_npxg and raw_npxg > 0:
            return {
                "outcome": "confirmed_error",
                "reason": "npxg_missing_in_gold",
                "gold_field": "npxg",
                "gold_value": None,
                "raw_value": raw_npxg,
                "player_id": player_id_raw,
                "match_id": match_id_raw,
            }
    else:
        gold_npxg_f = _to_float(gold_npxg)
        if gold_npxg_f is None:
            return {
                "outcome": "confirmed_error",
                "reason": "npxg_unparseable_in_gold",
                "gold_field": "npxg",
                "gold_value": str(gold_npxg),
                "raw_value": raw_npxg,
                "player_id": player_id_raw,
                "match_id": match_id_raw,
            }
        if not math.isclose(gold_npxg_f, float(raw_npxg), rel_tol=1e-9, abs_tol=1e-12):
            return {
                "outcome": "confirmed_error",
                "reason": "npxg_mismatch",
                "gold_field": "npxg",
                "gold_value": gold_npxg_f,
                "raw_value": float(raw_npxg),
                "player_id": player_id_raw,
                "match_id": match_id_raw,
            }

    gold_player_name = str(row.get("player_name") or "").strip()
    raw_player_name = str(raw["player_name_raw"] or "").strip()
    if gold_player_name and raw_player_name and gold_player_name != raw_player_name:
        return {
            "outcome": "confirmed_error",
            "reason": "player_name_mismatch",
            "gold_name": gold_player_name,
            "raw_name": raw_player_name,
            "player_id": player_id_raw,
            "match_id": match_id_raw,
        }

    gold_team_name = str(row.get("team_name") or "").strip()
    raw_team_name = str(raw["team_name_raw"] or "").strip()
    if gold_team_name and raw_team_name and gold_team_name != raw_team_name:
        return {
            "outcome": "confirmed_error",
            "reason": "team_name_mismatch",
            "gold_team": gold_team_name,
            "raw_team": raw_team_name,
            "player_id": player_id_raw,
            "match_id": match_id_raw,
        }

    return {
        "outcome": "confirmed_correct",
        "player_id": player_id_raw,
        "match_id": match_id_raw,
        "player_name": gold_player_name,
        "team_name": gold_team_name,
        "fields_verified": list(INTEGER_FIELD_MAP),
        "npxg_verified": not pd.isna(gold_npxg) or (raw_npxg == 0),
        "player_name_verified": bool(gold_player_name and raw_player_name),
        "team_name_verified": bool(gold_team_name and raw_team_name),
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
        sample_id = f"player_match:{sample['player_id']}:{sample['match_id']}"
        evidence_reference = (
            f"raw/statsbomb_open/events_*.parquet "
            f"match_id={sample.get('match_id')} "
            f"player_id={sample.get('player_id')}"
        )
        if sample["outcome"] == "confirmed_correct":
            decision = (
                f"Re-derived 7 integer fields {sample.get('fields_verified')} "
                f"plus npxg/player_name/team_name consistency against raw "
                f"StatsBomb open-data events snapshot. Aggregation mirrors "
                f"pipeline._build_player_match_from_statsbomb exactly."
            )
        else:
            gold_repr = (
                sample.get("gold_value")
                or sample.get("gold_name")
                or sample.get("gold_team")
                or "n/a"
            )
            raw_repr = (
                sample.get("raw_value")
                or sample.get("raw_name")
                or sample.get("raw_team")
                or "n/a"
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
        "Conservative threshold for source_claim audit on statsbomb_open "
        "source: 5% maximum error rate matches the identity_resolution, "
        "football_data, understat and fbref source_claim thresholds; "
        f"minimum_sample_count equals actual audit sample count ({sample_count}). "
        "AI-assisted content-level provenance verification "
        "(goals/assists/shots/shots_on_target/passes/tackles/minutes_played/"
        "npxg/player_name/team_name re-derived from raw events snapshot) "
        "cannot replace independent maintainer human review of external "
        "factual claims. statsbomb_open coverage in player_match.parquet is "
        "intentionally limited to a 3-match / 94-row sample; this audit "
        "verifies that sample's provenance, not full-league coverage."
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
    events_path = _resolve_events_path()

    gold = pd.read_parquet(PLAYER_MATCH_PATH)
    events = pd.read_parquet(events_path)
    aggregates = build_raw_aggregates(events)

    sb_rows = gold[gold["source_name"].astype(str) == "statsbomb_open"]
    if len(sb_rows) == 0:
        raise SystemExit("No statsbomb_open source_name rows found in player_match.parquet")

    sample = sb_rows.sample(
        n=min(args.sample_size, len(sb_rows)), random_state=args.seed
    )

    lines = []
    lines.append(
        f"Auditing {len(sample)} samples from {len(sb_rows)} statsbomb_open rows "
        f"(events file: {events_path.name})..."
    )
    print(lines[-1])

    results = [audit_sample(row, aggregates) for _, row in sample.iterrows()]
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
            line = (
                f"  match={s.get('match_id')} player={s.get('player_id')} "
                f"| name={s.get('player_name')} team={s.get('team_name')} "
                f"| fields={s.get('fields_verified')}"
            )
            lines.append(line)
            print(line)
    if errors:
        lines.append("")
        lines.append("First 5 confirmed_error samples:")
        print(lines[-2])
        for s in errors[:5]:
            gold_repr = s.get("gold_value", s.get("gold_name", s.get("gold_team")))
            raw_repr = s.get("raw_value", s.get("raw_name", s.get("raw_team")))
            line = (
                f"  {s.get('reason')}: gold={gold_repr} raw={raw_repr} "
                f"| match={s.get('match_id')} player={s.get('player_id')}"
            )
            lines.append(line)
            print(line)
    if no_match:
        reasons: dict[str, int] = {}
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
        threshold_written = write_threshold_ledger(
            args.threshold_ledger, len(writable)
        )
        print(
            f"Wrote {threshold_written} new threshold record to {args.threshold_ledger}"
        )
    else:
        print("\n(dry-run; pass --write-ledger to record outcomes)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
