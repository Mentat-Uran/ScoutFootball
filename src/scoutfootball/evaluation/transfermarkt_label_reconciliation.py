"""Provenance-safe reconciliation for revoked Transfermarkt identity decisions."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

from scoutfootball.evaluation.transfermarkt_identity_review import read_identity_review_ledger
from scoutfootball.evaluation.truth_labels import TRUTH_LABELS_COLUMNS

LABEL_LEDGER_TYPE = "scoutfootball.transfermarkt_truth_label_import_ledger"
LABEL_LEDGER_VERSION = "1.0"
_LABEL_KEY_COLUMNS = ("player_id", "season", "label_source")


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _label_key(row: dict[str, Any]) -> list[str]:
    return [str(row[column]) for column in _LABEL_KEY_COLUMNS]


def _label_fingerprint(row: dict[str, Any]) -> str:
    payload = {column: _json_value(row.get(column)) for column in TRUTH_LABELS_COLUMNS}
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()


def _json_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def build_transfermarkt_label_import_records(
    source_labels: pd.DataFrame,
    mappings: pd.DataFrame,
    *,
    input_provenance: dict[str, Any],
    season: str,
    labels_path: Path | str,
    recorded_at: str | None = None,
) -> list[dict[str, Any]]:
    """Capture only resolved labels and their exact identity-import context."""
    snapshot = input_provenance.get("snapshot") if isinstance(input_provenance, dict) else None
    matrix = input_provenance.get("feature_matrix") if isinstance(input_provenance, dict) else None
    snapshot_hash = snapshot.get("sha256") if isinstance(snapshot, dict) else None
    matrix_hash = matrix.get("sha256") if isinstance(matrix, dict) else None
    if not all(isinstance(value, str) and value for value in (snapshot_hash, matrix_hash)):
        raise ValueError("label_import_provenance_missing")
    if source_labels.empty or mappings.empty:
        return []
    labels = source_labels.reset_index(drop=True).copy()
    labels["source_row"] = labels.index.astype(int)
    merged = labels.merge(
        mappings[["source_row", "canonical_player_id", "method"]],
        on="source_row",
        how="inner",
    )
    records: list[dict[str, Any]] = []
    for row in merged.to_dict(orient="records"):
        label = {column: row.get(column) for column in TRUTH_LABELS_COLUMNS}
        label["player_id"] = str(row["canonical_player_id"])
        records.append(
            {
                "record_type": LABEL_LEDGER_TYPE,
                "record_version": LABEL_LEDGER_VERSION,
                "record_id": str(uuid4()),
                "recorded_at": recorded_at or _now(),
                "labels_path": str(Path(labels_path).resolve()),
                "snapshot_sha256": snapshot_hash,
                "feature_matrix_sha256": matrix_hash,
                "season": str(season),
                "source_row": int(row["source_row"]),
                "canonical_player_id": str(row["canonical_player_id"]),
                "identity_method": str(row["method"]),
                "label_key": _label_key(label),
                "label_fingerprint": _label_fingerprint(label),
            }
        )
    return records


def read_transfermarkt_label_import_ledger(path: Path | str) -> list[dict[str, Any]]:
    ledger = Path(path).resolve()
    if not ledger.exists():
        return []
    records: list[dict[str, Any]] = []
    for number, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"label_ledger_blank_line:{number}")
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"label_ledger_invalid_json:{number}") from exc
        required = {
            "record_type",
            "record_id",
            "recorded_at",
            "snapshot_sha256",
            "feature_matrix_sha256",
            "season",
            "source_row",
            "canonical_player_id",
            "identity_method",
            "label_key",
            "label_fingerprint",
        }
        if (
            not isinstance(record, dict)
            or record.get("record_type") != LABEL_LEDGER_TYPE
            or not required.issubset(record)
            or not isinstance(record["source_row"], int)
            or not isinstance(record["label_key"], list)
            or len(record["label_key"]) != len(_LABEL_KEY_COLUMNS)
        ):
            raise ValueError(f"label_ledger_record_invalid:{number}")
        records.append(record)
    return records


def append_transfermarkt_label_import_records(
    records: list[dict[str, Any]], path: Path | str
) -> Path:
    ledger = Path(path).resolve()
    if not records:
        return ledger
    existing_ids = {
        record["record_id"] for record in read_transfermarkt_label_import_ledger(ledger)
    }
    if any(record["record_id"] in existing_ids for record in records):
        raise ValueError("label_ledger_duplicate_record_id")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return ledger


def reconcile_revoked_transfermarkt_labels(
    labels: pd.DataFrame,
    *,
    identity_ledger_path: Path | str,
    label_ledger_path: Path | str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Preview narrowly proven removals; never infer provenance for old rows."""
    identity_records = read_identity_review_ledger(identity_ledger_path)
    label_records = read_transfermarkt_label_import_ledger(label_ledger_path)
    latest_decisions: dict[tuple[str, str, str, int], dict[str, Any]] = {}
    for record in identity_records:
        key = (
            record["snapshot_sha256"],
            record["feature_matrix_sha256"],
            record["season"],
            record["source_row"],
        )
        latest_decisions[key] = record
    revoked = {
        key for key, decision in latest_decisions.items() if decision.get("action") == "revoked"
    }
    current_by_key = {
        tuple(_label_key(row)): row
        for row in labels.to_dict(orient="records")
        if str(row.get("label_source")) == "transfermarkt_value"
    }
    latest_import_by_key: dict[tuple[str, ...], dict[str, Any]] = {}
    for record in label_records:
        key = tuple(record["label_key"])
        latest_import_by_key[key] = record

    removable: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for label_key, record in latest_import_by_key.items():
        context = (
            record["snapshot_sha256"],
            record["feature_matrix_sha256"],
            record["season"],
            record["source_row"],
        )
        if context not in revoked or record["identity_method"] != "manual_review_confirmed":
            continue
        current = current_by_key.get(label_key)
        if current is None:
            skipped.append({"label_key": list(label_key), "reason": "label_not_current"})
            continue
        if _label_fingerprint(current) != record["label_fingerprint"]:
            skipped.append({"label_key": list(label_key), "reason": "label_superseded_or_changed"})
            continue
        removable.append({"label_key": list(label_key), "source_row": record["source_row"]})

    remove_keys = {tuple(item["label_key"]) for item in removable}
    current_keys = labels.apply(lambda row: tuple(_label_key(row.to_dict())), axis=1)
    reconciled = labels.loc[~current_keys.isin(remove_keys)].copy()
    report = {
        "report_type": "scoutfootball.transfermarkt_truth_label_reconciliation",
        "report_version": "1.0.0",
        "generated_at": _now(),
        "identity_ledger_records": len(identity_records),
        "label_import_ledger_records": len(label_records),
        "revoked_identity_contexts": len(revoked),
        "removable_rows": len(removable),
        "removable": removable,
        "skipped": skipped,
        "limitations": [
            (
                "Only labels with a matching append-only import record and unchanged "
                "row fingerprint are removable."
            ),
            (
                "Historical labels without this provenance ledger remain untouched and "
                "require maintainer review."
            ),
        ],
    }
    return reconciled, report


def write_truth_labels_atomically(labels: pd.DataFrame, path: Path | str) -> Path:
    output = Path(path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.stem}.reconcile{output.suffix}")
    try:
        labels.to_parquet(temporary, index=False)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return output
