"""CLI tests for the ``resolve-canonical-ids`` command (PRS-1 R-005 slice 3).

Covers:
- ``resolve-canonical-ids`` with no ``player_match.parquet`` exits 0 and
  reports ``status=unavailable`` (read-only diagnostic, not a failure).
- ``resolve-canonical-ids`` with ``player_match.parquet`` and an empty
  registry exits 0 and reports all rows unresolved (honest default).
- ``resolve-canonical-ids`` after appending a confirmed mapping exits 0
  and reports one resolved row.
- ``resolve-canonical-ids --sample N`` also prints N sample rows showing
  ``source_name``, ``player_id`` and ``canonical_player_id``.
- ``resolve-canonical-ids --sample N`` with no player_match prints the
  unavailable report and no sample section.
"""

from __future__ import annotations

import json
import sys

import pandas as pd
import pytest

from scoutfootball.__main__ import main


@pytest.fixture
def isolated_data_root(tmp_path, monkeypatch):
    """Point SCOUTFOOTBALL_DATA_ROOT at a temp dir so CLI reads are isolated."""
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setenv("SCOUTFOOTBALL_DATA_ROOT", str(data_root))
    return data_root


def _run_cli(argv: list[str], capsys):
    """Run the CLI with the given argv and return (exit_code, out, err)."""
    old_argv = sys.argv
    sys.argv = ["scoutfootball"] + argv
    try:
        main()
        captured = capsys.readouterr()
        return 0, captured.out, captured.err
    except SystemExit as exc:
        captured = capsys.readouterr()
        return exc.code, captured.out, captured.err
    finally:
        sys.argv = old_argv


def _write_player_match(data_root) -> None:
    """Write a minimal player_match.parquet the resolver can read."""
    path = data_root / "gold" / "feature_store" / "player_match.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "player_id": ["lara|1998|ar", "understat|12345", "10605"],
            "player_name": ["Lara", "Marco", "Stats"],
            "source_name": ["fbref", "understat", "statsbomb_open"],
            "season_id": ["2425"] * 3,
        }
    ).to_parquet(path, index=False)


# ── resolve-canonical-ids ──────────────────────────────────────────────


def test_resolve_canonical_ids_no_player_match(isolated_data_root, capsys):
    """No player_match.parquet → exits 0, status=unavailable."""
    code, out, err = _run_cli(["resolve-canonical-ids"], capsys)
    assert code == 0
    report = json.loads(out)
    assert report["schema"] == "scoutfootball.canonical-resolver"
    assert report["status"] == "unavailable"
    assert "player_match.parquet missing" in report["evidence"]["reason"]


def test_resolve_canonical_ids_empty_registry_all_unresolved(
    isolated_data_root, capsys
):
    """player_match.parquet + empty registry → exits 0, all unresolved."""
    _write_player_match(isolated_data_root)
    code, out, err = _run_cli(["resolve-canonical-ids"], capsys)
    assert code == 0
    report = json.loads(out)
    assert report["status"] == "ok"
    evidence = report["evidence"]
    assert evidence["total_rows"] == 3
    assert evidence["resolved_rows"] == 0
    assert evidence["unresolved_rows"] == 3
    assert set(evidence["by_source"].keys()) == {"fbref", "understat", "statsbomb_open"}


def test_resolve_canonical_ids_with_one_confirmed_mapping(
    isolated_data_root, capsys
):
    """A confirmed registry decision resolves one row."""
    _write_player_match(isolated_data_root)
    # Append a confirmed mapping via CLI.
    _run_cli(
        [
            "identity-registry-append",
            "--source",
            "fbref",
            "--source-id",
            "lara|1998|ar",
            "--canonical-id",
            "canonical:fbref:lara:1998:ar",
            "--evidence",
            "transfermarkt snapshot row 12 maps here",
        ],
        capsys,
    )
    # Now resolve.
    code, out, err = _run_cli(["resolve-canonical-ids"], capsys)
    assert code == 0
    report = json.loads(out)
    evidence = report["evidence"]
    assert evidence["resolved_rows"] == 1
    assert evidence["unresolved_rows"] == 2
    assert evidence["distinct_canonical_ids"] == 1
    assert evidence["by_source"]["fbref"] == {"resolved": 1, "unresolved": 0}


def test_resolve_canonical_ids_with_sample(isolated_data_root, capsys):
    """--sample N prints the summary plus N sample rows."""
    _write_player_match(isolated_data_root)
    code, out, err = _run_cli(["resolve-canonical-ids", "--sample", "2"], capsys)
    assert code == 0
    # The output is JSON followed by a text sample block. Split on the
    # sample separator so we can parse the JSON prefix independently.
    assert "--- sample ---" in out
    json_part, sample_part = out.split("--- sample ---", 1)
    report = json.loads(json_part.strip())
    assert report["status"] == "ok"
    # Sample block contains the three expected column headers and at most
    # 2 data rows (the fixture has 3 rows but --sample 2 caps it).
    assert "source_name" in sample_part
    assert "player_id" in sample_part
    assert "canonical_player_id" in sample_part
    # All sample canonical_player_id values are unresolved markers (empty registry).
    assert "unresolved:fbref:lara|1998|ar" in sample_part


def test_resolve_canonical_ids_sample_zero_omits_sample_block(
    isolated_data_root, capsys
):
    """--sample 0 (default) prints only the JSON report, no sample block."""
    _write_player_match(isolated_data_root)
    code, out, err = _run_cli(["resolve-canonical-ids"], capsys)
    assert code == 0
    assert "--- sample ---" not in out
    report = json.loads(out)
    assert report["status"] == "ok"


def test_resolve_canonical_ids_sample_with_no_player_match(
    isolated_data_root, capsys
):
    """--sample N with no player_match prints unavailable report and no sample."""
    code, out, err = _run_cli(["resolve-canonical-ids", "--sample", "5"], capsys)
    assert code == 0
    assert "--- sample ---" not in out
    report = json.loads(out)
    assert report["status"] == "unavailable"


def test_resolve_canonical_ids_revoked_mapping_makes_row_unresolved(
    isolated_data_root, capsys
):
    """Confirm then revoke → the row falls back to unresolved."""
    _write_player_match(isolated_data_root)
    # Confirm.
    _run_cli(
        [
            "identity-registry-append",
            "--source",
            "understat",
            "--source-id",
            "understat|12345",
            "--canonical-id",
            "canonical:marco",
            "--evidence",
            "first attempt",
        ],
        capsys,
    )
    # Revoke.
    _run_cli(
        [
            "identity-registry-revoke",
            "--source",
            "understat",
            "--source-id",
            "understat|12345",
            "--evidence",
            "was wrong; no replacement",
        ],
        capsys,
    )
    # Resolve.
    code, out, err = _run_cli(["resolve-canonical-ids"], capsys)
    assert code == 0
    report = json.loads(out)
    evidence = report["evidence"]
    assert evidence["resolved_rows"] == 0
    assert evidence["unresolved_rows"] == 3
