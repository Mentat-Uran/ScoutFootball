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


def test_raw_csv_inspection_tolerates_trailing_empty_lines(tmp_path) -> None:
    """Trailing blank lines emitted by some upstream tools (e.g. clubelo.com)
    must not trigger csv_row_width_mismatch; they carry no data and would
    otherwise block snapshot recording without evidence."""
    settings = PlatformSettings.from_root(tmp_path)
    path = settings.data_root / "raw" / "reep" / "people.csv"
    path.parent.mkdir(parents=True)
    # Two trailing blank lines (matches clubelo 2026-06-06.csv shape)
    path.write_text("reep_id,name\n1,Alice\n2,Bob\n\n\n", encoding="utf-8")

    report = inspect_raw_csv(
        source_id="reep",
        path="raw/reep/people.csv",
        settings=settings,
    )

    assert report["artifacts"][0]["inspection"]["row_count"] == 2


def test_raw_csv_inspection_tolerates_middle_empty_line(tmp_path) -> None:
    """A blank line in the middle of the file is also skipped; csv.reader
    returns [] for it and skipping is consistent with the trailing-line
    policy. Partial-width rows still raise."""
    settings = PlatformSettings.from_root(tmp_path)
    path = settings.data_root / "raw" / "reep" / "people.csv"
    path.parent.mkdir(parents=True)
    path.write_text("reep_id,name\n1,Alice\n\n2,Bob\n", encoding="utf-8")

    report = inspect_raw_csv(
        source_id="reep",
        path="raw/reep/people.csv",
        settings=settings,
    )

    assert report["artifacts"][0]["inspection"]["row_count"] == 2


def test_raw_csv_inspection_still_rejects_partial_width_row(tmp_path) -> None:
    """A row with wrong number of non-empty cells is real corruption and
    must still raise, even with the empty-line tolerance in place."""
    settings = PlatformSettings.from_root(tmp_path)
    path = settings.data_root / "raw" / "reep" / "people.csv"
    path.parent.mkdir(parents=True)
    # Row 3 has 3 cells but headers have 2 — this is not an empty line
    path.write_text("reep_id,name\n1,Alice\n2,Bob,extra\n\n", encoding="utf-8")

    with pytest.raises(ValueError, match="csv_row_width_mismatch:3"):
        inspect_raw_csv(source_id="reep", path="raw/reep/people.csv", settings=settings)

