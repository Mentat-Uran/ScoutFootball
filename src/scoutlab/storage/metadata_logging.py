"""Metadata helpers for dataset writes and request logs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from scoutlab.schemas import IngestMetadata, SourceRequestLogEntry


def metadata_path_for_dataset(dataset_path: Path) -> Path:
    """Return the sidecar metadata path for one parquet dataset."""

    return dataset_path.parent / f"{dataset_path.name}.metadata.json"


def write_ingest_metadata(
    dataset_path: Path,
    metadata: IngestMetadata,
    *,
    output_row_count: int,
    deduplicated_rows: int,
) -> Path:
    """Persist the latest ingest metadata next to a parquet dataset."""

    metadata_path = metadata_path_for_dataset(dataset_path)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset_path": str(dataset_path),
        "written_at": datetime.now(tz=UTC).isoformat(),
        "output_row_count": output_row_count,
        "deduplicated_rows": deduplicated_rows,
        "metadata": metadata.model_dump(mode="json"),
    }
    metadata_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return metadata_path


def append_source_request_log(log_path: Path, entry: SourceRequestLogEntry) -> None:
    """Append one structured source request record to a JSONL log."""

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry.model_dump(mode="json"), sort_keys=True))
        handle.write("\n")
