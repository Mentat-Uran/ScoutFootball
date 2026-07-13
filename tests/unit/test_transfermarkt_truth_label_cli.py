"""End-to-end CLI coverage for dated local Transfermarkt truth-label imports."""

from __future__ import annotations

import json
import sys

import pandas as pd

from scoutfootball.__main__ import main
from scoutfootball.evaluation.truth_labels import create_empty_truth_labels


def _write_snapshot(path, value: str = "10m") -> None:
    pd.DataFrame(
        {
            "player": ["Alice Example"],
            "club": ["Example FC"],
            "date": ["2025-05-20"],
            "market_value": [value],
        },
    ).to_csv(path, index=False)


def _write_existing_labels(path) -> None:
    labels = create_empty_truth_labels()
    labels.loc[0] = {
        "player_id": "Other Player",
        "season": "2425",
        "label_source": "award",
        "label_confidence": "high",
        "label_value": 1.0,
        "as_of_date": "2025-05-01",
        "position_scope": "all",
        "manual_review_flag": False,
    }
    labels.to_parquet(path, index=False)


def _run_cli(monkeypatch, *arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["scoutfootball", *arguments])
    main()


def test_transfermarkt_import_dry_run_previews_date_and_feature_coverage(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    snapshot = tmp_path / "snapshot.csv"
    output = tmp_path / "truth_labels.parquet"
    feature_matrix = tmp_path / "rating_feature_matrix.parquet"
    _write_snapshot(snapshot)
    _write_existing_labels(output)
    pd.DataFrame(
        {"player_id": ["Alice Example|2000|England"], "season_id": ["2425"]},
    ).to_parquet(feature_matrix, index=False)

    _run_cli(
        monkeypatch,
        "import-transfermarkt-truth-labels",
        "--snapshot", str(snapshot),
        "--season", "2425",
        "--output", str(output),
        "--feature-matrix", str(feature_matrix),
        "--dry-run",
    )

    summary = json.loads(capsys.readouterr().out)
    assert summary["incoming_rows"] == 1
    assert summary["as_of_date_min"] == "2025-05-20"
    assert summary["feature_coverage"] == {
        "status": "checked",
        "unique_player_seasons": 1,
        "matched_player_seasons": 1,
        "unmatched_player_seasons": 0,
    }
    assert pd.read_parquet(output)["label_source"].tolist() == ["award"]


def test_transfermarkt_import_replaces_only_matching_source_key(tmp_path, monkeypatch) -> None:
    snapshot = tmp_path / "snapshot.csv"
    output = tmp_path / "truth_labels.parquet"
    _write_snapshot(snapshot)
    _write_existing_labels(output)

    args = (
        "import-transfermarkt-truth-labels",
        "--snapshot", str(snapshot),
        "--season", "2425",
        "--output", str(output),
        "--feature-matrix", str(tmp_path / "missing_features.parquet"),
    )
    _run_cli(monkeypatch, *args)
    _write_snapshot(snapshot, "12m")
    _run_cli(monkeypatch, *args)

    labels = pd.read_parquet(output)
    assert len(labels) == 2
    assert set(labels["label_source"]) == {"award", "transfermarkt_value"}
    value = labels.loc[labels["label_source"] == "transfermarkt_value", "label_value"].item()
    assert value == 12_000_000.0
