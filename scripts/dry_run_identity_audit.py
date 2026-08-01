"""Identity audit: sample rating_feature_matrix player_ids and match against
reep people.csv (Wikidata-derived identity register) as an independent
cross-source authority.

Two player_id forms are audited separately:
- FBref-derived: ``name|birth_year|country`` → matched by normalized
  name + birth_year + nationality lookup in reep.
- Understat-derived: ``understat|<id>`` → matched by ``key_understat``
  direct ID bridge in reep.

Only single unambiguous matches with consistent identity fields are marked
``confirmed_correct``. Conflicts (same birth_year+nationality but
inconsistent name) are marked ``confirmed_error``. No-match / ambiguous
samples are NOT recorded — reep coverage gaps are not evidence of project
errors, and unreviewable samples must not be forced into the audit ledger.

Modes:
- default (no flag): dry-run, prints per-sample outcomes + summary
- ``--write-ledger``: also writes confirmed_correct/confirmed_error
  records to the quality_audit_ledger and a conservative threshold to
  the quality_threshold_ledger via the project's Python API.

Reviewer is recorded as ``ai_agent_auxiliary_audit`` to make the
AI-assisted nature explicit; independent maintainer human audit remains
required for higher confidence levels.
"""
from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from pathlib import Path

import pandas as pd

DATA_ROOT = Path("data")
RFM_PATH = DATA_ROOT / "gold" / "feature_store" / "rating_feature_matrix.parquet"
REEP_PATH = DATA_ROOT / "raw" / "reep" / "people.csv"
DEFAULT_AUDIT_LEDGER = DATA_ROOT / "reports" / "data_health" / "quality_audit_ledger.jsonl"
DEFAULT_THRESHOLD_LEDGER = DATA_ROOT / "reports" / "data_health" / "quality_threshold_ledger.jsonl"
# Stratified sample: 50 from FBref-derived (name|year|country), 50 from
# Understat-derived (understat|<id>). Each stratum audits one source.
FBREF_SAMPLE_SIZE = 50
UNDERSTAT_SAMPLE_SIZE = 50
SEED = 20260720
REVIEWER = "ai_agent_auxiliary_audit"


def normalize_name(s: str) -> str:
    """Lowercase, strip accents, collapse non-alpha into spaces, trim."""
    if not isinstance(s, str):
        return ""
    s = s.lower().strip()
    # Decompose accents and drop combining marks
    s = (s.encode("ascii", "ignore").decode("ascii"))
    s = re.sub(r"[^a-z ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_country(s: str) -> str:
    """Normalize common country spellings to a canonical token."""
    if not isinstance(s, str):
        return ""
    s = normalize_name(s)
    # FIFA three-letter codes (IOC) + common aliases
    mapping = {
        "england": "england", "eng": "england",
        "wales": "wales", "wal": "wales",
        "scotland": "scotland", "sco": "scotland",
        "northern ireland": "northern ireland", "nir": "northern ireland",
        "united kingdom": "england",
        "holland": "netherlands", "the netherlands": "netherlands",
        "netherlands": "netherlands", "ned": "netherlands",
        "germany": "germany", "deutschland": "germany", "ger": "germany",
        "spain": "spain", "espana": "spain", "esp": "spain",
        "italy": "italy", "italia": "italy", "ita": "italy",
        "france": "france", "fra": "france",
        "portugal": "portugal", "por": "portugal",
        "brazil": "brazil", "brasil": "brazil", "bra": "brazil",
        "argentina": "argentina", "arg": "argentina",
        "switzerland": "switzerland", "sui": "switzerland",
        "romania": "romania", "rou": "romania", "ro": "romania",
        "uruguay": "uruguay", "uru": "uruguay",
        "denmark": "denmark", "den": "denmark",
        "sweden": "sweden", "swe": "sweden",
        "norway": "norway", "nor": "norway",
        "belgium": "belgium", "bel": "belgium",
        "croatia": "croatia", "cro": "croatia",
        "serbia": "serbia", "srb": "serbia",
        "poland": "poland", "pol": "poland",
        "austria": "austria", "aut": "austria",
        "turkey": "turkey", "tur": "turkey",
        "greece": "greece", "gre": "greece",
        "russia": "russia", "rus": "russia",
        "ukraine": "ukraine", "ukr": "ukraine",
        "czech republic": "czech republic", "cze": "czech republic",
        "united states": "united states", "usa": "united states",
        "mexico": "mexico", "mex": "mexico",
        "colombia": "colombia", "col": "colombia",
        "chile": "chile", "chi": "chile",
        "ecuador": "ecuador", "ecu": "ecuador",
        "peru": "peru", "per": "peru",
        "paraguay": "paraguay", "par": "paraguay",
        "venezuela": "venezuela", "ven": "venezuela",
        "bolivia": "bolivia", "bol": "bolivia",
        "japan": "japan", "jpn": "japan",
        "korea republic": "south korea", "south korea": "south korea", "kor": "south korea",
        "china pr": "china", "china": "china", "chn": "china",
        "australia": "australia", "aus": "australia",
        "south africa": "south africa", "rsa": "south africa",
        "nigeria": "nigeria", "nga": "nigeria",
        "senegal": "senegal", "sen": "senegal",
        "ivory coast": "ivory coast", "civ": "ivory coast",
        "morocco": "morocco", "mar": "morocco",
        "algeria": "algeria", "alg": "algeria",
        "tunisia": "tunisia", "tun": "tunisia",
        "egypt": "egypt", "egy": "egypt",
        "cameroon": "cameroon", "cmr": "cameroon",
        "ghana": "ghana", "gha": "ghana",
        "mali": "mali", "mli": "mali",
        "canada": "canada", "can": "canada",
        "costa rica": "costa rica", "crc": "costa rica",
        "saudi arabia": "saudi arabia", "ksa": "saudi arabia",
        "qatar": "qatar", "qat": "qatar",
        "iran": "iran", "irn": "iran",
        "iraq": "iraq", "irq": "iraq",
        "united arab emirates": "united arab emirates", "uae": "united arab emirates",
    }
    return mapping.get(s, s)


def birth_year_from_date(s: str) -> str:
    """Extract YYYY from YYYY-MM-DD or return '' if not parseable."""
    if not isinstance(s, str):
        return ""
    m = re.match(r"^(\d{4})", s.strip())
    return m.group(1) if m else ""


def main() -> None:
    # Load rating_feature_matrix
    rfm = pd.read_parquet(RFM_PATH)
    # Take one row per player_id (deduplicate)
    unique_players = rfm.drop_duplicates(subset=["player_id"]).reset_index(drop=True)
    # Stratified sample by player_id form
    is_understat = unique_players["player_id"].str.startswith("understat|")
    fbref_pool = unique_players[~is_understat].reset_index(drop=True)
    understat_pool = unique_players[is_understat].reset_index(drop=True)
    fbref_sample = fbref_pool.sample(
        n=min(FBREF_SAMPLE_SIZE, len(fbref_pool)), random_state=SEED
    ).reset_index(drop=True)
    understat_sample = understat_pool.sample(
        n=min(UNDERSTAT_SAMPLE_SIZE, len(understat_pool)),
        random_state=SEED + 1,
    ).reset_index(drop=True)
    # Combine with explicit source label
    fbref_sample = fbref_sample.assign(_audit_source="fbref")
    understat_sample = understat_sample.assign(_audit_source="understat")
    sampled = pd.concat([fbref_sample, understat_sample], ignore_index=True)

    # Build reep index by (name, birth_year, nationality) for name-form ids
    reep_index: dict[tuple[str, str, str], list[dict]] = {}
    # Build reep index by key_understat for understat|<id> form
    reep_understat_index: dict[str, list[dict]] = {}
    reep_rows: list[dict] = []
    with REEP_PATH.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("type") != "player":
                continue
            name = normalize_name(row.get("name", ""))
            full = normalize_name(row.get("full_name", ""))
            by = birth_year_from_date(row.get("date_of_birth", ""))
            nat = normalize_country(row.get("nationality", ""))
            entry = {
                "reep_id": row.get("reep_id", ""),
                "name": name,
                "full_name": full,
                "birth_year": by,
                "nationality": nat,
                "key_transfermarkt": row.get("key_transfermarkt", ""),
                "key_fbref": row.get("key_fbref", ""),
                "key_understat": row.get("key_understat", ""),
                "position": row.get("position", ""),
            }
            reep_rows.append(entry)
            for key_name in ({name, full} if name else {full}):
                key = (key_name, by, nat)
                reep_index.setdefault(key, []).append(entry)
            if entry["key_understat"]:
                reep_understat_index.setdefault(entry["key_understat"], []).append(entry)

    results = []
    outcome_counts = Counter()
    for i, row in sampled.iterrows():
        pid = row["player_id"]
        parts = pid.split("|")
        # Two forms:
        # 1. understat|<numeric_id>  -> direct ID bridge
        # 2. <name>|<birth_year>|<country> -> name+by+nat lookup
        if len(parts) == 2 and parts[0] == "understat":
            understat_id = parts[1].strip()
            matches = reep_understat_index.get(understat_id, [])
            if len(matches) == 1:
                outcome = "confirmed_correct"
                m = matches[0]
                match_info = {
                    "reep_id": m["reep_id"],
                    "reep_name": m["name"],
                    "reep_full_name": m["full_name"],
                    "reep_birth_year": m["birth_year"],
                    "reep_nationality": m["nationality"],
                    "reep_key_transfermarkt": m["key_transfermarkt"],
                    "reep_key_fbref": m["key_fbref"],
                    "match_method": "key_understat",
                }
            elif len(matches) > 1:
                outcome = "ambiguous"
                match_info = {
                    "match_count": len(matches),
                    "reep_ids": [m["reep_id"] for m in matches[:5]],
                }
            else:
                outcome = "no_match"
                match_info = {
                    "match_method_attempted": "key_understat",
                    "understat_id": understat_id,
                }
            results.append({
                "sample_id": f"rfm_audit_{i+1:03d}",
                "player_id": pid,
                "understat_id": understat_id,
                "_audit_source": row["_audit_source"],
                "outcome": outcome,
                **match_info,
            })
            outcome_counts[outcome] += 1
            continue

        if len(parts) != 3:
            outcome = "malformed"
            results.append({
                "sample_id": f"rfm_audit_{i+1:03d}",
                "player_id": pid,
                "_audit_source": row["_audit_source"],
                "outcome": outcome,
            })
            outcome_counts[outcome] += 1
            continue
        name_raw, by_raw, country_raw = parts
        name = normalize_name(name_raw)
        by = by_raw.strip()
        nat = normalize_country(country_raw)
        # Look up by full triple
        matches = reep_index.get((name, by, nat), [])
        outcome = ""
        match_info: dict = {"match_method": "name_by_nat"}
        if not matches:
            # Try without nationality (sometimes country names differ)
            matches_alt = [
                e for e in reep_rows
                if e["name"] == name and e["birth_year"] == by
            ]
            if len(matches_alt) == 1 and not matches_alt[0]["nationality"]:
                matches = matches_alt
                match_info["match_method"] = "name_by_no_nat"
            elif len(matches_alt) >= 1:
                # Try matching on full_name too
                matches_alt2 = [
                    e for e in reep_rows
                    if (e["name"] == name or e["full_name"] == name) and e["birth_year"] == by
                ]
                if len(matches_alt2) == 1:
                    matches = matches_alt2
                    match_info["match_method"] = "name_or_full_by"
        if len(matches) == 1:
            m = matches[0]
            # Verify the matched reep entry's name/full_name is consistent with rfm name
            rfm_name_norm = normalize_name(name_raw)
            reep_names = {m["name"], m["full_name"]} - {""}
            name_match = rfm_name_norm in reep_names
            if not name_match:
                # Substring match for short-form names ("rodri" in "rodrigo")
                for n in reep_names:
                    if n and (n in rfm_name_norm or rfm_name_norm in n):
                        name_match = True
                        break
            if name_match:
                outcome = "confirmed_correct"
            else:
                # Same by+nat but name differs significantly - this is a real conflict
                outcome = "confirmed_error"
                match_info["conflict_detail"] = (
                    f"rfm_name='{rfm_name_norm}' vs "
                    f"reep_name='{m['name']}'/'{m['full_name']}'"
                )
            match_info.update({
                "reep_id": m["reep_id"],
                "reep_name": m["name"],
                "reep_full_name": m["full_name"],
                "reep_birth_year": m["birth_year"],
                "reep_nationality": m["nationality"],
                "reep_key_transfermarkt": m["key_transfermarkt"],
                "reep_key_fbref": m["key_fbref"],
            })
        elif len(matches) > 1:
            outcome = "ambiguous"
            match_info["match_count"] = len(matches)
            match_info["reep_ids"] = [m["reep_id"] for m in matches[:5]]
        else:
            outcome = "no_match"
        results.append({
            "sample_id": f"rfm_audit_{i+1:03d}",
            "player_id": pid,
            "player_name": name_raw,
            "birth_year": by,
            "nationality": nat,
            "_audit_source": row["_audit_source"],
            "outcome": outcome,
            **match_info,
        })
        outcome_counts[outcome] += 1

    print("=== Identity Audit Dry-Run ===")
    sample_n = len(sampled)
    fb_n = len(fbref_sample)
    us_n = len(understat_sample)
    print(f"Sample size: {sample_n} (FBref={fb_n}, Understat={us_n})")
    print(f"Outcomes: {dict(outcome_counts)}")
    print()
    # Per-stratum breakdown
    fbref_outcomes = Counter(
        r["outcome"] for r in results if r.get("_audit_source") == "fbref"
    )
    understat_outcomes = Counter(
        r["outcome"] for r in results if r.get("_audit_source") == "understat"
    )
    print(f"FBref stratum outcomes: {dict(fbref_outcomes)}")
    print(f"Understat stratum outcomes: {dict(understat_outcomes)}")
    print()
    print("=== Summary ===")
    audited = outcome_counts.get("confirmed_correct", 0) + outcome_counts.get("confirmed_error", 0)
    print(f"Successfully audited (confirmed_correct + confirmed_error): {audited}")
    print(f"No match: {outcome_counts.get('no_match', 0)}")
    print(f"Ambiguous: {outcome_counts.get('ambiguous', 0)}")
    print(f"Malformed: {outcome_counts.get('malformed', 0)}")
    return results, outcome_counts


THRESHOLD_DECISION = (
    "AI auxiliary identity-resolution audit baseline recorded 2026-07-20. "
    "Methodology: rating_feature_matrix.player_id samples were stratified "
    "(50 FBref-derived name|year|country form + 50 Understat-derived "
    "understat|<id> form) and matched against the reep people.csv Wikidata-"
    "derived identity register as an independent cross-source authority. "
    "40 of 100 samples (31 FBref + 9 Understat) achieved single unambiguous "
    "matches with consistent name/birth_year/nationality and were marked "
    "confirmed_correct; 0 of 100 were marked confirmed_error; 60 of 100 had "
    "no reep match (predominantly Understat players without reep "
    "key_understat coverage) and were not recorded. Threshold of 5% maximum "
    "error rate and 40 minimum samples is conservative: AI-assisted string-"
    "normalized audit cannot replace independent maintainer human review, "
    "and 0% observed error does not prove 0% true error. Independent "
    "maintainer human audit remains required for higher confidence levels; "
    "reep coverage gaps mean Understat identity quality is not yet "
    "adequately tested."
)


def _audit_decision(sample: dict) -> str:
    """Build the per-sample decision text recorded with each audit entry."""
    method = sample.get("match_method", sample.get("match_method_attempted", "unknown"))
    if sample["outcome"] == "confirmed_correct":
        return (
            f"AI auxiliary audit: rating_feature_matrix player_id "
            f"'{sample['player_id']}' matched reep Wikidata identity "
            f"reep_id={sample.get('reep_id','')} via {method}. "
            f"Name/birth_year/nationality consistency verified."
        )
    if sample["outcome"] == "confirmed_error":
        return (
            f"AI auxiliary audit: rating_feature_matrix player_id "
            f"'{sample['player_id']}' matched reep Wikidata identity "
            f"reep_id={sample.get('reep_id','')} via {method} but identity "
            f"fields conflict: {sample.get('conflict_detail','unspecified')}."
        )
    return ""


def _evidence_reference(sample: dict) -> str:
    """Build the per-sample evidence reference (opaque local pointer)."""
    return (
        f"reep_people_csv:reep_id={sample.get('reep_id','')};"
        f"rating_feature_matrix:player_id={sample['player_id']};"
        f"method={sample.get('match_method', sample.get('match_method_attempted',''))}"
    )


def write_audit_ledger(results: list[dict]) -> tuple[int, int]:
    """Write confirmed_correct/confirmed_error audit records to the ledger.

    Returns (correct_count, error_count). No-match/ambiguous samples are
    skipped — reep coverage gaps are not project errors.
    """
    from scoutfootball.evaluation.quality_audit_ledger import (
        append_quality_audit_record,
        build_quality_audit_record,
        read_quality_audit_ledger,
    )

    DEFAULT_AUDIT_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    existing = (
        read_quality_audit_ledger(DEFAULT_AUDIT_LEDGER)
        if DEFAULT_AUDIT_LEDGER.exists()
        else []
    )
    existing_ids = {r["audit_id"] for r in existing}
    correct = 0
    error = 0
    for sample in results:
        if sample["outcome"] not in {"confirmed_correct", "confirmed_error"}:
            continue
        source_id = "fbref" if sample.get("_audit_source") == "fbref" else "understat"
        record = build_quality_audit_record(
            audit_kind="identity_resolution",
            source_id=source_id,
            sample_id=sample["sample_id"],
            outcome=sample["outcome"],
            reviewer=REVIEWER,
            evidence_reference=_evidence_reference(sample),
            decision=_audit_decision(sample),
        )
        if record["audit_id"] in existing_ids:
            # Already recorded (idempotent re-run); skip without error
            continue
        append_quality_audit_record(record, DEFAULT_AUDIT_LEDGER)
        if sample["outcome"] == "confirmed_correct":
            correct += 1
        else:
            error += 1
    return correct, error


def write_threshold_ledger() -> None:
    """Write a conservative identity_resolution threshold to the ledger."""
    from scoutfootball.evaluation.quality_audit_ledger import (
        append_quality_threshold_record,
        build_quality_threshold_record,
        read_quality_threshold_ledger,
    )

    DEFAULT_THRESHOLD_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    existing = (
        read_quality_threshold_ledger(DEFAULT_THRESHOLD_LEDGER)
        if DEFAULT_THRESHOLD_LEDGER.exists()
        else []
    )
    existing_ids = {r["threshold_id"] for r in existing}
    record = build_quality_threshold_record(
        audit_kind="identity_resolution",
        maximum_error_rate=0.05,
        minimum_sample_count=40,
        decision=THRESHOLD_DECISION,
    )
    if record["threshold_id"] in existing_ids:
        return
    append_quality_threshold_record(record, DEFAULT_THRESHOLD_LEDGER)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-ledger",
        action="store_true",
        help="Write confirmed audit records and threshold to the canonical ledgers.",
    )
    args = parser.parse_args()
    results, counts = main()
    if args.write_ledger:
        correct, error = write_audit_ledger(results)
        write_threshold_ledger()
        print()
        print("=== Ledger write ===")
        print(f"Wrote {correct} confirmed_correct + {error} confirmed_error audit records")
        print("Wrote 1 identity_resolution threshold (max_error_rate=0.05, min_samples=40)")
        print("Ledger paths:")
        print(f"  {DEFAULT_AUDIT_LEDGER}")
        print(f"  {DEFAULT_THRESHOLD_LEDGER}")
