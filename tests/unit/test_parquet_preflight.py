"""Unit tests for ``scoutfootball.evaluation.parquet_preflight``.

Covers the scenarios called out in AGENTS.md:

- normal readable parquet (footer agrees with content)
- empty parquet (0 rows decodes cleanly)
- corrupt parquet (footer may exist, content decode fails)
- missing/extra columns relative to an ``expected_columns`` contract
- footer/content mismatch (footer lies about row count)
- pandas MultiIndex column names (the FBref-style tuple columns that
  broke DuckDB's ``path_in_schema`` splitter)
- non-existent and non-parquet paths
- ``summarize_reports`` text/json output
- ``key_artifact_paths`` target scoping
- ``quarantine_unreadable`` dry_run vs real move, including the
  Windows-style absolute-path hijack of ``Path /``
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation import parquet_preflight as pf

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_parquet(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def _write_corrupt_parquet(path: Path) -> None:
    """Write a file with a parquet magic header but garbage body.

    The footer is intentionally unreadable so both pyarrow and DuckDB fail
    to decode it, exercising the ``readable=False`` path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # PAR1 magic + random bytes + PAR1 magic — looks like a parquet file by
    # suffix and magic, but cannot be decoded.
    path.write_bytes(b"PAR1" + b"\x00" * 256 + b"PAR1")


def _settings(tmp_path: Path) -> PlatformSettings:
    return PlatformSettings.from_root(tmp_path)


# ---------------------------------------------------------------------------
# preflight_parquet — single-file behaviour
# ---------------------------------------------------------------------------


def test_preflight_normal_file_has_footer_and_content(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    rel = "gold/feature_store/sample.parquet"
    path = settings.data_root / rel
    _write_parquet(path, pd.DataFrame({"match_id": [1, 2, 3], "x": [0.1, 0.2, None]}))

    report = pf.preflight_parquet(rel, settings=settings)

    assert report.exists
    assert report.readable
    assert report.reader in {"duckdb", "pandas"}
    assert report.row_count == 3
    assert report.column_count == 2
    assert set(report.columns) == {"match_id", "x"}
    assert report.null_counts is not None
    assert report.null_counts["x"] == 1
    assert report.num_row_groups is not None and report.num_row_groups >= 1
    assert report.footer_row_count == 3
    assert set(report.footer_columns) == {"match_id", "x"}
    assert report.writer_version is not None and len(report.writer_version) > 0
    assert not report.footer_content_mismatch
    assert report.schema_hash is not None and len(report.schema_hash) == 64
    assert report.content_hash is not None and len(report.content_hash) == 64
    assert report.sample_ok is True
    assert report.ok


def test_preflight_empty_file_decodes_cleanly(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    rel = "gold/feature_store/empty.parquet"
    path = settings.data_root / rel
    _write_parquet(path, pd.DataFrame({"a": [], "b": []}))

    report = pf.preflight_parquet(rel, settings=settings)

    assert report.readable
    assert report.row_count == 0
    assert report.footer_row_count == 0
    assert not report.footer_content_mismatch
    assert report.ok  # 0 rows is valid, just noted
    assert any("0 rows" in n for n in report.notes)


def test_preflight_corrupt_file_is_unreadable(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    rel = "raw/corrupt/sample.parquet"
    path = settings.data_root / rel
    _write_corrupt_parquet(path)

    report = pf.preflight_parquet(rel, settings=settings)

    assert report.exists
    assert not report.readable
    assert report.read_error is not None and "duckdb" in report.read_error
    assert report.reader is None
    assert report.row_count is None
    assert report.columns is None
    assert report.schema_hash is None
    assert report.content_hash is None
    assert not report.ok


def test_preflight_missing_file(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    report = pf.preflight_parquet("gold/does_not_exist.parquet", settings=settings)

    assert not report.exists
    assert not report.readable
    assert "does not exist" in (report.read_error or "")
    assert not report.ok


def test_preflight_non_parquet_suffix(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    rel = "raw/notes.txt"
    path = settings.data_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("hello", encoding="utf-8")

    report = pf.preflight_parquet(rel, settings=settings)

    assert report.exists
    assert not report.readable
    assert "wrong suffix" in (report.read_error or "")
    assert not report.ok


def test_preflight_expected_columns_reports_missing_and_extra(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    rel = "gold/feature_store/sample.parquet"
    path = settings.data_root / rel
    _write_parquet(path, pd.DataFrame({"a": [1], "b": [2], "c": [3]}))

    report = pf.preflight_parquet(
        rel, settings=settings, expected_columns=["a", "b", "missing_one"]
    )

    assert report.readable
    assert any("missing_one" in n for n in report.notes)
    assert any("c" in n and "extra" in n for n in report.notes)


def test_preflight_footer_content_mismatch_when_rows_diverge(tmp_path: Path) -> None:
    """Force a mismatch by writing a valid parquet then truncating rows in
    the content read via monkeypatching the reader.

    The footer is read by pyarrow's ``ParquetFile.metadata`` (which still
    reports the original row count), while the content reader returns a
    shorter frame. This simulates the AGENTS.md "footer says 2187 but
    content decodes empty" class of conflict without needing a real
    corrupt-but-decodable file.
    """
    settings = _settings(tmp_path)
    rel = "gold/feature_store/sample.parquet"
    path = settings.data_root / rel
    _write_parquet(path, pd.DataFrame({"a": [1, 2, 3, 4, 5]}))

    original_duckdb = pf._read_content_duckdb
    original_pandas = pf._read_content_pandas

    def _short_duckdb(_path: Path) -> tuple[pd.DataFrame, str]:
        return pd.DataFrame({"a": [1, 2]}), "duckdb"

    def _short_pandas(_path: Path) -> tuple[pd.DataFrame, str]:
        return pd.DataFrame({"a": [1, 2]}), "pandas"

    pf._read_content_duckdb = _short_duckdb  # type: ignore[assignment]
    pf._read_content_pandas = _short_pandas  # type: ignore[assignment]
    try:
        report = pf.preflight_parquet(rel, settings=settings)
    finally:
        pf._read_content_duckdb = original_duckdb  # type: ignore[assignment]
        pf._read_content_pandas = original_pandas  # type: ignore[assignment]

    assert report.readable
    assert report.row_count == 2
    assert report.footer_row_count == 5
    assert report.footer_content_mismatch
    assert any("footer_row_count=5" in n for n in report.notes)
    assert not report.ok


def test_preflight_handles_multiindex_columns(tmp_path: Path) -> None:
    """FBref-style pandas MultiIndex columns must be preserved as top-level
    string names, not split on the tuple's ``, `` separator.

    This is the regression case for DuckDB's ``split_part(path_in_schema, ', ', 1)``
    approach that mangled ``('Per 90 Minutes', 'Ast')`` into ``('Per 90 Minutes'``.
    """
    settings = _settings(tmp_path)
    rel = "raw/fbref/player_standard.parquet"
    path = settings.data_root / rel
    cols = pd.MultiIndex.from_tuples(
        [("Player", "name"), ("Per 90 Minutes", "Ast"), ("Per 90 Minutes", "Gls")]
    )
    df = pd.DataFrame(
        [["x", 0.1, 0.2], ["y", 0.3, 0.4]], columns=cols
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)

    report = pf.preflight_parquet(rel, settings=settings)

    assert report.readable
    # pyarrow returns the stringified tuple names verbatim. The key assertion
    # is that the DuckDB ``split_part(path_in_schema, ', ', 1)`` bug does not
    # recur: the full tuple string ``"('Per 90 Minutes', 'Ast')"`` must be
    # preserved, not truncated to ``"('Per 90 Minutes'"``.
    assert report.column_count == 3
    assert len(set(report.columns)) == 3
    assert "('Per 90 Minutes', 'Ast')" in report.columns
    assert "('Per 90 Minutes', 'Gls')" in report.columns
    assert report.ok


def test_preflight_absolute_path_outside_data_root(tmp_path: Path) -> None:
    """Explicit absolute path outside data_root is resolved as-is, and
    ``relative_path`` falls back to the absolute path string."""
    settings = _settings(tmp_path)
    outside = tmp_path.parent / "outside_probe.parquet"
    _write_parquet(outside, pd.DataFrame({"a": [1, 2]}))
    try:
        report = pf.preflight_parquet(outside, settings=settings)
        assert report.readable
        assert report.row_count == 2
        # relative_path is the absolute string when not under data_root
        assert Path(report.relative_path) == outside
    finally:
        outside.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# summarize_reports
# ---------------------------------------------------------------------------


def test_summarize_reports_text_includes_counts_and_paths(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    ok_path = settings.data_root / "ok.parquet"
    bad_path = settings.data_root / "bad.parquet"
    _write_parquet(ok_path, pd.DataFrame({"a": [1, 2]}))
    _write_corrupt_parquet(bad_path)

    reports = [
        pf.preflight_parquet("ok.parquet", settings=settings),
        pf.preflight_parquet("bad.parquet", settings=settings),
    ]
    text = pf.summarize_reports(reports, fmt="text")

    assert "1/2 ok" in text
    assert "1 unreadable" in text
    assert "ok.parquet" in text
    assert "bad.parquet" in text


def test_summarize_reports_json_round_trips(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    path = settings.data_root / "ok.parquet"
    _write_parquet(path, pd.DataFrame({"a": [1, 2, 3]}))
    reports = [pf.preflight_parquet("ok.parquet", settings=settings)]

    payload = json.loads(pf.summarize_reports(reports, fmt="json"))

    assert payload["total"] == 1
    assert payload["ok"] == 1
    assert payload["unreadable"] == 0
    assert payload["reports"][0]["row_count"] == 3
    assert payload["reports"][0]["columns"] == ["a"]


# ---------------------------------------------------------------------------
# key_artifact_paths / preflight_key_artifacts
# ---------------------------------------------------------------------------


def test_key_artifact_paths_raw_only_returns_existing_raw(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    # Create one raw file from KEY_RAW_ARTIFACTS, leave others missing.
    _write_parquet(
        settings.data_root / pf.KEY_RAW_ARTIFACTS[0],
        pd.DataFrame({"x": [1]}),
    )
    # Also create a gold file to ensure raw scope excludes it.
    _write_parquet(
        settings.data_root / pf.KEY_GOLD_ARTIFACTS[0],
        pd.DataFrame({"y": [1]}),
    )

    paths = pf.key_artifact_paths("raw", settings=settings)

    assert paths == [pf.KEY_RAW_ARTIFACTS[0]]


def test_key_artifact_paths_key_keeps_missing_flagged_files(tmp_path: Path) -> None:
    """``key`` scope must surface AGENTS.md-flagged conflict files even
    when missing, so the gap appears in the report rather than 404 noise."""
    settings = _settings(tmp_path)
    paths = pf.key_artifact_paths("key", settings=settings)
    # Nothing exists on disk, but all flagged paths should still be returned.
    assert pf.KEY_RAW_ARTIFACTS[0] in paths
    assert pf.KEY_GOLD_ARTIFACTS[0] in paths


def test_key_artifact_paths_all_discovers_extra_parquets(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    extra = settings.data_root / "raw" / "extra" / "discovered.parquet"
    _write_parquet(extra, pd.DataFrame({"z": [1]}))

    paths = pf.key_artifact_paths("all", settings=settings)

    assert "raw/extra/discovered.parquet" in paths


def test_preflight_key_artifacts_returns_one_report_per_path(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write_parquet(
        settings.data_root / pf.KEY_RAW_ARTIFACTS[0],
        pd.DataFrame({"x": [1]}),
    )
    reports = pf.preflight_key_artifacts("raw", settings=settings)
    assert len(reports) == 1
    assert reports[0].row_count == 1


# ---------------------------------------------------------------------------
# quarantine
# ---------------------------------------------------------------------------


def test_quarantine_dry_run_moves_nothing(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    rel = "raw/corrupt/sample.parquet"
    path = settings.data_root / rel
    _write_corrupt_parquet(path)

    reports = [pf.preflight_parquet(rel, settings=settings)]
    result = pf.quarantine_unreadable(reports, settings=settings, dry_run=True)

    assert result.moved == ()
    assert rel in result.skipped
    assert result.manifest_path is None
    # File is still in place.
    assert path.exists()
    assert not (settings.data_root / "quarantine").exists()


def test_quarantine_real_move_creates_destination_and_manifest(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    rel = "raw/corrupt/sample.parquet"
    path = settings.data_root / rel
    _write_corrupt_parquet(path)

    reports = [pf.preflight_parquet(rel, settings=settings)]
    result = pf.quarantine_unreadable(reports, settings=settings, dry_run=False)

    assert len(result.moved) == 1
    assert result.moved[0] == rel
    assert result.manifest_path is not None
    manifest_file = Path(result.manifest_path)
    assert manifest_file.exists()
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert len(manifest) == 1
    assert manifest[0]["relative_path"] == rel
    assert manifest[0]["read_error"] is not None

    # Original is gone, destination exists under quarantine/ preserving structure.
    assert not path.exists()
    dest = settings.data_root / "quarantine" / rel
    assert dest.exists()


def test_quarantine_skips_readable_files(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    rel = "gold/ok.parquet"
    path = settings.data_root / rel
    _write_parquet(path, pd.DataFrame({"a": [1, 2]}))

    reports = [pf.preflight_parquet(rel, settings=settings)]
    result = pf.quarantine_unreadable(reports, settings=settings, dry_run=False)

    assert result.moved == ()
    assert result.manifest_path is None
    # Readable file is left in place.
    assert path.exists()


def test_quarantine_handles_absolute_path_outside_data_root(tmp_path: Path) -> None:
    """Regression test for the Windows ``Path /`` absolute-path hijack.

    Joining ``quarantine_dir / "C:\\foo\\bar.parquet"`` resolves to
    ``C:\\foo\\bar.parquet`` on Windows, so ``shutil.move`` would be a
    no-op rename. The fix flattens such files to ``<hash>_<name>`` under
    quarantine_dir.
    """
    settings = _settings(tmp_path)
    # Place a corrupt file OUTSIDE data_root.
    outside = tmp_path.parent / "outside_corrupt.parquet"
    _write_corrupt_parquet(outside)
    try:
        report = pf.preflight_parquet(outside, settings=settings)
        assert not report.readable

        result = pf.quarantine_unreadable(
            [report], settings=settings, dry_run=False
        )

        assert len(result.moved) == 1
        # Original is gone.
        assert not outside.exists()
        # Destination exists under quarantine/ with hash-prefixed name.
        quarantine_dir = settings.data_root / "quarantine"
        moved_files = list(quarantine_dir.glob("*.parquet"))
        assert len(moved_files) == 1
        assert moved_files[0].name.startswith(
            "outside_corrupt"
        ) or moved_files[0].name.endswith("outside_corrupt.parquet")
        # Filename should not be the raw absolute path (no colon, no drive).
        assert ":" not in moved_files[0].name
    finally:
        outside.unlink(missing_ok=True)


def test_quarantine_destination_preserves_data_root_subdir(tmp_path: Path) -> None:
    """Files under data_root keep their relative subdir under quarantine."""
    settings = _settings(tmp_path)
    rel = "raw/fbref/player_standard.parquet"
    path = settings.data_root / rel
    _write_corrupt_parquet(path)

    report = pf.preflight_parquet(rel, settings=settings)
    dest = pf._quarantine_destination(settings.data_root / "quarantine", report)

    assert dest == settings.data_root / "quarantine" / rel
    assert dest.parent == settings.data_root / "quarantine" / "raw" / "fbref"


def test_quarantine_destination_flattens_absolute_paths(tmp_path: Path) -> None:
    """Files outside data_root are flattened to hash_name to avoid the
    Windows ``Path /`` hijack."""
    settings = _settings(tmp_path)
    outside = tmp_path.parent / "outside.parquet"
    _write_parquet(outside, pd.DataFrame({"a": [1]}))
    try:
        report = pf.preflight_parquet(outside, settings=settings)
        dest = pf._quarantine_destination(
            settings.data_root / "quarantine", report
        )
        # Dest is directly under quarantine_dir, not under a subdirectory
        # derived from the absolute path.
        assert dest.parent == settings.data_root / "quarantine"
        assert dest.name.endswith("outside.parquet")
        # No drive separator in the name.
        assert ":" not in dest.name
        assert "\\" not in dest.name
    finally:
        outside.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# to_dict
# ---------------------------------------------------------------------------


def test_report_to_dict_serialises_tuples_as_lists(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    rel = "gold/sample.parquet"
    _write_parquet(settings.data_root / rel, pd.DataFrame({"a": [1], "b": [2]}))
    report = pf.preflight_parquet(rel, settings=settings)

    d = report.to_dict()

    assert isinstance(d["columns"], list)
    assert isinstance(d["footer_columns"], list)
    assert isinstance(d["notes"], list)
    assert set(d["columns"]) == {"a", "b"}
