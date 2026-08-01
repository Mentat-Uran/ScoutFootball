"""Read-only lookups in a local Reep people snapshot.

Reep is an identity-reference input only.  These lookups expose provider IDs
and person names for a maintainer to review; they never assert a canonical
ScoutFootball player identity or write a truth label, rating, or roster.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from scoutfootball.architecture import build_data_contract_registry
from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.source_snapshot_ledger import (
    latest_snapshot_by_source,
    read_source_snapshot_ledger,
)

REEP_IDENTITY_LOOKUP_TYPE = "scoutfootball.reep_identity_lookup"
REEP_IDENTITY_LOOKUP_VERSION = "1.0"

_PROVIDER_COLUMNS = {
    "transfermarkt": "key_transfermarkt",
    "fbref": "key_fbref",
    "wikidata": "key_wikidata",
}
_REQUIRED_COLUMNS = frozenset(
    {
        "reep_id",
        "type",
        "name",
        "full_name",
        *_PROVIDER_COLUMNS.values(),
    }
)


def _registered_raw_root(source_id: str) -> str:
    for contract in build_data_contract_registry().contracts:
        if (
            contract.layer == "raw"
            and contract.license is not None
            and contract.license.source_name == source_id
        ):
            return contract.artifact_id.replace("\\", "/").strip("/")
    raise ValueError("source_not_registered")


def _resolve_reep_csv(path: Path | str, settings: PlatformSettings) -> Path:
    root = _registered_raw_root("reep")
    source_root = (settings.data_root / root).resolve()
    candidate = Path(path)
    resolved = (
        (settings.data_root / candidate).resolve()
        if not candidate.is_absolute()
        else candidate.resolve()
    )
    try:
        resolved.relative_to(source_root)
    except ValueError as exc:
        raise ValueError("path_outside_registered_source") from exc
    if resolved.suffix.lower() != ".csv":
        raise ValueError("csv_required")
    if not resolved.is_file():
        raise ValueError("source_file_missing")
    return resolved


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _snapshot_status(snapshot_ledger_path: Path | str | None) -> dict[str, str]:
    if snapshot_ledger_path is None:
        return {"status": "not_recorded"}
    latest = latest_snapshot_by_source(
        read_source_snapshot_ledger(snapshot_ledger_path)
    ).get("reep")
    if latest is None:
        return {"status": "not_recorded"}
    return {
        "status": "recorded",
        "snapshot_id": latest["snapshot_id"],
        "snapshot_date": latest["snapshot_date"],
        "recorded_at": latest["recorded_at"],
    }


def _match_record(row: dict[str, str | None]) -> dict[str, Any]:
    return {
        "reep_id": _clean(row.get("reep_id")),
        "entity_type": _clean(row.get("type")),
        "name": _clean(row.get("name")),
        "full_name": _clean(row.get("full_name")),
        "provider_ids": {
            provider: _clean(row.get(column)) for provider, column in _PROVIDER_COLUMNS.items()
        },
    }


def lookup_reep_provider_identity(
    *,
    provider: str,
    provider_id: str,
    path: Path | str = "raw/reep/people.csv",
    settings: PlatformSettings | None = None,
    limit: int = 20,
    snapshot_ledger_path: Path | str | None = None,
) -> dict[str, Any]:
    """Find exact provider-ID matches in a local registered Reep CSV.

    The lookup deliberately scans the complete file so duplicate provider IDs
    remain visible.  Exact matching avoids turning name similarity into an
    identity decision.
    """
    if provider not in _PROVIDER_COLUMNS:
        raise ValueError("provider_invalid")
    identifier = provider_id.strip()
    if not identifier:
        raise ValueError("provider_id_required")
    if not 1 <= limit <= 100:
        raise ValueError("limit_out_of_range")

    settings = settings or PlatformSettings.from_root()
    resolved = _resolve_reep_csv(path, settings)
    column = _PROVIDER_COLUMNS[provider]
    matches: list[dict[str, Any]] = []
    match_count = 0
    try:
        with resolved.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, restkey="__extra_columns__", restval=None)
            headers = set(reader.fieldnames or [])
            missing = sorted(_REQUIRED_COLUMNS - headers)
            if missing:
                raise ValueError(f"reep_schema_missing:{','.join(missing)}")
            for row in reader:
                if row.get("__extra_columns__") is not None or any(
                    row.get(header) is None for header in reader.fieldnames or []
                ):
                    raise ValueError(f"csv_row_width_mismatch:{reader.line_num}")
                if _clean(row.get(column)) != identifier:
                    continue
                match_count += 1
                if len(matches) < limit:
                    matches.append(_match_record(row))
    except UnicodeDecodeError as exc:
        raise ValueError("csv_utf8_required") from exc
    except csv.Error as exc:
        raise ValueError(f"csv_unreadable:{exc}") from exc

    return {
        "report_type": REEP_IDENTITY_LOOKUP_TYPE,
        "report_version": REEP_IDENTITY_LOOKUP_VERSION,
        "source_id": "reep",
        "lookup": {
            "provider": provider,
            "provider_column": column,
            "provider_id": identifier,
            "match_mode": "exact",
        },
        "status": "found" if match_count else "not_found",
        "match_count": match_count,
        "returned_count": len(matches),
        "truncated": match_count > len(matches),
        "matches": matches,
        "source_snapshot": _snapshot_status(snapshot_ledger_path),
        "limitations": [
            "The lookup reads only the selected local Reep CSV and does not upload data.",
            (
                "A provider-ID match is a review aid, not a confirmed ScoutFootball "
                "canonical identity."
            ),
            (
                "This lookup does not read Transfermarkt files or create market-value, "
                "roster, rating, or truth-label data."
            ),
            (
                "A recorded snapshot date is a maintainer declaration and does not establish "
                "provider completeness or currentness."
            ),
        ],
    }
