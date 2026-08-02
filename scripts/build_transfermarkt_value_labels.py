"""Build provenance-safe market-value proxy labels from local snapshots.

The repository has a local historical Transfermarkt market-value table and a
player profile table, but the two files do not carry a stable shared player
identity with the rating matrix.  This script joins them only through the
existing deterministic name/season resolver, records unresolved rows, and
never treats a fuzzy match as confirmed.

The generated labels are source-policy eligible *proxy* labels.  They are not
independent proof of football ability and must not be described as such.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from scoutfootball.entities.normalize import normalize_person_name
from scoutfootball.evaluation.transfermarkt_identity import (
    apply_resolved_transfermarkt_identities,
    resolve_transfermarkt_snapshot_identities,
    transfermarkt_identity_report,
)
from scoutfootball.evaluation.transfermarkt_label_reconciliation import (
    append_transfermarkt_label_import_records,
    build_transfermarkt_label_import_records,
    write_truth_labels_atomically,
)
from scoutfootball.evaluation.truth_labels import (
    TRUTH_LABELS_COLUMNS,
    create_empty_truth_labels,
    merge_truth_label_rows,
    validate_truth_labels,
)

_PLAYER_ID_SUFFIX = re.compile(r"\s*\([^)]*\)\s*$")
_DEFAULT_SEASONS = tuple(
    f"{year % 100:02d}{(year + 1) % 100:02d}" for year in range(2016, 2025)
)


def _sha256_files(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.name):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _season_from_date(value: pd.Timestamp) -> str:
    start_year = int(value.year) if int(value.month) >= 7 else int(value.year) - 1
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"


def _clean_player_name(value: object) -> str:
    return _PLAYER_ID_SUFFIX.sub("", str(value or "")).strip()


def _load_market_snapshot(data_root: Path, seasons: set[str]) -> tuple[pd.DataFrame, list[Path]]:
    source_dir = data_root / "raw" / "transfermarkt_manual"
    values_path = source_dir / "player_market_value.csv"
    profiles_path = source_dir / "player_profiles.csv"
    if not values_path.is_file() or not profiles_path.is_file():
        raise FileNotFoundError("Transfermarkt market history and profiles are required")

    values = pd.read_csv(values_path, low_memory=False)
    profiles = pd.read_csv(
        profiles_path,
        usecols=["player_id", "player_name"],
        low_memory=False,
    )
    required_values = {"player_id", "date_unix", "value"}
    if required_values - set(values.columns):
        missing = sorted(required_values - set(values.columns))
        raise ValueError(f"market history missing columns: {missing}")

    values["snapshot_date"] = pd.to_datetime(values["date_unix"], errors="coerce")
    values["market_value"] = pd.to_numeric(values["value"], errors="coerce")
    values = values.loc[
        values["snapshot_date"].notna() & values["market_value"].gt(0)
    ].copy()
    values["season"] = values["snapshot_date"].map(_season_from_date)
    values = values.loc[values["season"].isin(seasons)].copy()
    values = values.sort_values(["player_id", "season", "snapshot_date"])
    values = values.drop_duplicates(["player_id", "season"], keep="last")
    values = values.merge(profiles, on="player_id", how="left", validate="many_to_one")
    values["player_name"] = values["player_name"].map(_clean_player_name)
    values = values.loc[values["player_name"].ne("")].copy()

    # The historical profile table does not contain the player's historical
    # club.  Leaving team_name empty is intentional: the identity resolver may
    # accept only a unique name/season candidate, never a guessed club.
    snapshot = values.rename(columns={"market_value": "raw_market_value"})[
        ["player_name", "season", "snapshot_date", "raw_market_value"]
    ].copy()
    snapshot["team_name"] = ""
    snapshot["snapshot_date"] = snapshot["snapshot_date"].dt.strftime("%Y-%m-%d")
    return snapshot.reset_index(drop=True), [values_path, profiles_path]


def _scale_values(snapshot: pd.DataFrame) -> pd.Series:
    """Convert currency to a bounded within-season 1..100 percentile proxy."""

    log_values = np.log1p(snapshot["raw_market_value"].astype(float))
    ranks = log_values.groupby(snapshot["season"]).rank(method="average", pct=True)
    return (ranks * 99.0 + 1.0).astype(float)


def build_labels(
    data_root: Path,
    *,
    feature_matrix_path: Path | None = None,
    seasons: set[str] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any]]:
    """Build canonical labels and an identity/coverage report in memory."""

    target_seasons = seasons or set(_DEFAULT_SEASONS)
    snapshot, source_paths = _load_market_snapshot(data_root, target_seasons)
    matrix_path = feature_matrix_path or (
        data_root / "gold" / "feature_store" / "rating_feature_matrix.parquet"
    )
    feature_matrix = pd.read_parquet(matrix_path)
    source_labels = pd.DataFrame(
        {
            "player_id": snapshot["player_name"].map(normalize_person_name).astype("string"),
            "season": snapshot["season"].astype("string"),
            "label_source": "transfermarkt_value",
            "label_confidence": "medium",
            "label_value": _scale_values(snapshot),
            "as_of_date": snapshot["snapshot_date"].astype("string"),
            "position_scope": "all",
            "manual_review_flag": False,
        },
        columns=TRUTH_LABELS_COLUMNS,
    )

    mapped_parts: list[pd.DataFrame] = []
    reports: dict[str, Any] = {}
    for season in sorted(target_seasons):
        season_mask = snapshot["season"].eq(season)
        season_snapshot = snapshot.loc[season_mask].reset_index(drop=True)
        season_labels = source_labels.loc[season_mask].reset_index(drop=True)
        result = resolve_transfermarkt_snapshot_identities(
            season_snapshot,
            feature_matrix,
            season=season,
        )
        mapped = apply_resolved_transfermarkt_identities(season_labels, result)
        mapped_parts.append(mapped)
        reports[season] = transfermarkt_identity_report(result)

    mapped_labels = (
        pd.concat(mapped_parts, ignore_index=True)
        if mapped_parts
        else create_empty_truth_labels()
    )
    mapped_labels = mapped_labels[TRUTH_LABELS_COLUMNS].copy()
    duplicate_mask = mapped_labels.duplicated(
        subset=["player_id", "season", "label_source"], keep=False
    )
    duplicate_rows = int(duplicate_mask.sum())
    if duplicate_rows:
        # Several provider profiles can resolve to one canonical rating ID.
        # Keep the higher within-season value deterministically; do not write
        # duplicate labels or silently average distinct provider records.
        mapped_labels = (
            mapped_labels.sort_values(
                ["player_id", "season", "label_source", "label_value"],
                ascending=[True, True, True, False],
            )
            .drop_duplicates(["player_id", "season", "label_source"], keep="first")
            .reset_index(drop=True)
        )
    report = {
        "source": "transfermarkt_manual.player_market_value + player_profiles",
        "target_semantics": "independent market-value proxy; not player-ability truth",
        "scale": "within-season log-market-value percentile mapped to 1..100",
        "source_files": [str(path) for path in source_paths],
        "source_sha256": _sha256_files(source_paths),
        "feature_matrix": str(matrix_path),
        "feature_matrix_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest(),
        "seasons": sorted(target_seasons),
        "snapshot_rows": int(len(snapshot)),
        "mapped_rows": int(len(mapped_labels)),
        "duplicate_mapped_rows_collapsed": duplicate_rows,
        "by_season": reports,
        "limitations": [
            (
                "Historical Transfermarkt profiles do not provide historical clubs here; "
                "only unique name/season identities are accepted."
            ),
            (
                "Market value is an independent proxy signal, not an independent causal "
                "measure of player ability."
            ),
            "Unresolved and ambiguous rows are excluded from supervision and remain in the report.",
        ],
    }
    errors = validate_truth_labels(mapped_labels)
    if errors:
        raise ValueError("generated labels failed validation: " + "; ".join(errors))
    provenance = {
        "snapshot": {"sha256": report["source_sha256"]},
        "feature_matrix": {"sha256": report["feature_matrix_sha256"]},
    }
    return mapped_labels, report, provenance


def apply_labels(
    labels: pd.DataFrame,
    *,
    report: dict[str, Any],
    provenance: dict[str, Any],
    output_path: Path,
    label_ledger_path: Path,
) -> dict[str, Any]:
    """Merge labels, validate, and write the append-only import evidence."""

    existing = (
        pd.read_parquet(output_path) if output_path.is_file() else create_empty_truth_labels()
    )
    combined, replaced = merge_truth_label_rows(existing, labels)
    errors = validate_truth_labels(combined)
    if errors:
        raise ValueError("combined labels failed validation: " + "; ".join(errors))
    import_records = build_transfermarkt_label_import_records(
        labels,
        pd.DataFrame(
            {
                "source_row": labels.index.astype(int),
                "canonical_player_id": labels["player_id"].astype(str),
                "method": "name_season_unique",
            }
        ),
        input_provenance=provenance,
        season="multi-season",
        labels_path=output_path,
    )
    write_truth_labels_atomically(combined, output_path)
    append_transfermarkt_label_import_records(import_records, label_ledger_path)
    return {
        **report,
        "output_path": str(output_path),
        "label_ledger_path": str(label_ledger_path),
        "existing_rows": int(len(existing)),
        "combined_rows": int(len(combined)),
        "replaced_rows": int(replaced),
        "import_ledger_rows": int(len(import_records)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/gold/feature_store/player_truth_labels.parquet"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("data/reports/data_health/transfermarkt_value_labels.json"),
    )
    parser.add_argument("--label-ledger", type=Path, default=None)
    parser.add_argument("--seasons", nargs="*", default=None)
    parser.add_argument("--apply", action="store_true", help="Write labels and import ledger")
    args = parser.parse_args()

    data_root = args.data_root.resolve()
    output_path = args.output.resolve()
    labels, report, provenance = build_labels(
        data_root,
        seasons=set(args.seasons) if args.seasons else None,
    )
    if args.apply:
        ledger_path = (
            args.label_ledger.resolve()
            if args.label_ledger is not None
            else output_path.with_name("transfermarkt_truth_label_import_ledger.jsonl")
        )
        report = apply_labels(
            labels,
            report=report,
            provenance=provenance,
            output_path=output_path,
            label_ledger_path=ledger_path,
        )
    else:
        report["dry_run"] = True
        report["would_add_rows"] = int(len(labels))
        report["would_write"] = False
    report_path = args.report.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
