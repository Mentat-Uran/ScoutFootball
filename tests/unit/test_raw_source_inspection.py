from __future__ import annotations

import json

import pytest

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.raw_source_inspection import (
    RAW_SOURCE_INSPECTION_TYPE,
    inspect_raw_csv,
    write_raw_source_inspection_report,
)


def test_raw_csv_inspection_records_structure_without_cell_values(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    path = settings.data_root / "raw" / "reep" / "people.csv"
    path.parent.mkdir(parents=True)
    path.write_text("reep_id,name\n1,Alice\n2,Bob\n", encoding="utf-8")

    report = inspect_raw_csv(
        source_id="reep",
        path="raw/reep/people.csv",
        settings=settings,
        generated_at="2026-07-17T00:00:00Z",
    )

    inspection = report["artifacts"][0]["inspection"]
    assert report["report_type"] == RAW_SOURCE_INSPECTION_TYPE
    assert report["artifacts"][0]["artifact_path"] == "raw/reep/people.csv"
    assert inspection["row_count"] == 2
    assert inspection["column_count"] == 2
    assert inspection["content_hash"]
    assert "Alice" not in json.dumps(report)


def test_raw_csv_inspection_rejects_path_escape_and_bad_rows(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    source = settings.data_root / "raw" / "reep" / "people.csv"
    source.parent.mkdir(parents=True)
    source.write_text("reep_id,name\n1,Alice,extra\n", encoding="utf-8")
    outside = tmp_path / "outside.csv"
    outside.write_text("id\n1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="csv_row_width_mismatch:2"):
        inspect_raw_csv(source_id="reep", path=source, settings=settings)
    with pytest.raises(ValueError, match="path_outside_registered_source"):
        inspect_raw_csv(source_id="reep", path=outside, settings=settings)


def test_raw_csv_inspection_writer_refuses_replace_without_opt_in(tmp_path) -> None:
    output = tmp_path / "inspection.json"
    report = {"report_type": RAW_SOURCE_INSPECTION_TYPE}

    write_raw_source_inspection_report(report, output)
    with pytest.raises(FileExistsError, match="evidence_exists_use_overwrite"):
        write_raw_source_inspection_report(report, output)
    write_raw_source_inspection_report(report, output, overwrite=True)
