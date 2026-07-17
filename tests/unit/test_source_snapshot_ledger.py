from __future__ import annotations

import json

import pytest

from scoutfootball.evaluation.source_snapshot_ledger import (
    append_source_snapshot_record,
    build_source_snapshot_record,
    latest_snapshot_by_source,
    read_source_snapshot_ledger,
)


def _evidence(path) -> None:
    path.write_text(
        json.dumps(
            {
                "report_type": "scoutfootball.parquet_preflight_evidence",
                "report_version": "1.0",
                "generated_at": "2026-07-17T00:00:00Z",
                "artifacts": [
                    {
                        "artifact_path": "raw/football_data/results.parquet",
                        "inspection": {
                            "content_hash": "abc",
                            "schema_hash": "schema",
                            "row_count": 2,
                            "reader": "duckdb",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_append_only_snapshot_ledger_records_explicit_date_and_evidence(tmp_path) -> None:
    evidence_path = tmp_path / "evidence.json"
    ledger_path = tmp_path / "source_snapshots.jsonl"
    _evidence(evidence_path)

    record = build_source_snapshot_record(
        source_id="football_data",
        snapshot_date="2026-07-16",
        evidence_path=evidence_path,
        recorded_at="2026-07-17T00:00:00Z",
    )
    append_source_snapshot_record(record, ledger_path)

    records = read_source_snapshot_ledger(ledger_path)
    assert records == [record]
    assert record["snapshot_date"] == "2026-07-16"
    assert record["evidence"]["artifact_count"] == 1
    assert latest_snapshot_by_source(records)["football_data"]["snapshot_id"] == record[
        "snapshot_id"
    ]
    with pytest.raises(FileExistsError, match="snapshot_already_recorded"):
        append_source_snapshot_record(record, ledger_path)


def test_snapshot_ledger_rejects_missing_source_evidence_and_invalid_dates(tmp_path) -> None:
    evidence_path = tmp_path / "evidence.json"
    _evidence(evidence_path)

    with pytest.raises(ValueError, match="evidence_has_no_artifacts_for_source"):
        build_source_snapshot_record(
            source_id="understat",
            snapshot_date="2026-07-16",
            evidence_path=evidence_path,
        )
    with pytest.raises(ValueError, match="snapshot_date_invalid"):
        build_source_snapshot_record(
            source_id="football_data",
            snapshot_date="not-a-date",
            evidence_path=evidence_path,
        )
