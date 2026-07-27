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


def test_raw_csv_inspection_accepts_project_root_relative_path(tmp_path) -> None:
    """Paths relative to project root (e.g. "data/raw/reep/people.csv")
    must work in addition to paths relative to data_root (e.g.
    "raw/reep/people.csv"). The maintainer naturally passes "data/..."
    from the project root, and the naive data_root join would produce a
    double-"data" prefix; the strip-prefix fallback resolves this."""
    settings = PlatformSettings.from_root(tmp_path)
    path = settings.data_root / "raw" / "reep" / "people.csv"
    path.parent.mkdir(parents=True)
    path.write_text("reep_id,name\n1,Alice\n2,Bob\n", encoding="utf-8")

    # "data/raw/reep/people.csv" relative to project root (tmp_path)
    report = inspect_raw_csv(
        source_id="reep",
        path="data/raw/reep/people.csv",
        settings=settings,
    )

    assert report["artifacts"][0]["inspection"]["row_count"] == 2
    assert report["artifacts"][0]["artifact_path"] == "raw/reep/people.csv"


def test_raw_csv_inspection_accepts_data_root_relative_path_backward_compat(
    tmp_path,
) -> None:
    """Paths relative to data_root (e.g. "raw/reep/people.csv") must
    continue to work after the project-root-relative fallback is added."""
    settings = PlatformSettings.from_root(tmp_path)
    path = settings.data_root / "raw" / "reep" / "people.csv"
    path.parent.mkdir(parents=True)
    path.write_text("reep_id,name\n1,Alice\n", encoding="utf-8")

    report = inspect_raw_csv(
        source_id="reep",
        path="raw/reep/people.csv",
        settings=settings,
    )

    assert report["artifacts"][0]["inspection"]["row_count"] == 1


def test_raw_csv_inspection_project_root_relative_missing_file_reports_missing(
    tmp_path,
) -> None:
    """When the maintainer passes a "data/..." path that does not exist
    on disk, the error should be source_file_missing (not
    path_outside_registered_source), so the message points at the real
    problem rather than a confusing escape failure."""
    settings = PlatformSettings.from_root(tmp_path)
    # Create the registered source root but not the file.
    (settings.data_root / "raw" / "reep").mkdir(parents=True)

    with pytest.raises(ValueError, match="source_file_missing"):
        inspect_raw_csv(
            source_id="reep",
            path="data/raw/reep/nonexistent.csv",
            settings=settings,
        )


def test_raw_csv_inspection_strip_prefix_works_with_custom_data_root_name(
    tmp_path,
) -> None:
    """When SCOUTFOOTBALL_DATA_ROOT points to a folder whose name is not
    "data" (e.g. "my_data"), the strip-prefix fallback should still
    handle "my_data/raw/..." paths correctly."""
    custom_data_root = tmp_path / "my_data"
    settings = PlatformSettings.from_root(tmp_path)
    # Manually override data_root to simulate SCOUTFOOTBALL_DATA_ROOT.
    path = custom_data_root / "raw" / "reep" / "people.csv"
    path.parent.mkdir(parents=True)
    path.write_text("reep_id,name\n1,Alice\n", encoding="utf-8")
    # Rebuild settings with custom data_root.
    from scoutfootball.config import PlatformSettings as PS

    settings = PS.model_construct(
        project_root=tmp_path,
        source_root=tmp_path / "src",
        test_root=tmp_path / "tests",
        data_root=custom_data_root,
        raw_root=custom_data_root / "raw",
        silver_root=custom_data_root / "silver",
        gold_root=custom_data_root / "gold",
        model_root=custom_data_root / "models",
        report_root=custom_data_root / "reports",
        log_root=custom_data_root / "logs",
    )

    report = inspect_raw_csv(
        source_id="reep",
        path="my_data/raw/reep/people.csv",
        settings=settings,
    )

    assert report["artifacts"][0]["inspection"]["row_count"] == 1

