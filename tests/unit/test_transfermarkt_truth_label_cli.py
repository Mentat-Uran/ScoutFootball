"""End-to-end CLI coverage for dated local Transfermarkt truth-label imports."""

from __future__ import annotations

import hashlib
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
        {
            "player_id": ["Alice Example|2000|England"],
            "player_name": ["Alice Example"],
            "season_id": ["2425"],
        },
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
    assert summary["identity"]["mapped_rows"] == 1
    assert summary["identity"]["review_rows"] == 0
    assert summary["input_provenance"]["snapshot"]["sha256"] == hashlib.sha256(
        snapshot.read_bytes()
    ).hexdigest()
    assert summary["input_provenance"]["feature_matrix"]["size_bytes"] > 0
    assert pd.read_parquet(output)["label_source"].tolist() == ["award"]


def test_transfermarkt_import_replaces_only_matching_source_key(tmp_path, monkeypatch) -> None:
    snapshot = tmp_path / "snapshot.csv"
    output = tmp_path / "truth_labels.parquet"
    feature_matrix = tmp_path / "rating_feature_matrix.parquet"
    _write_snapshot(snapshot)
    _write_existing_labels(output)
    pd.DataFrame(
        {
            "player_id": ["alice example|2000|england"],
            "player_name": ["Alice Example"],
            "team_name": ["Example FC"],
            "season_id": ["2425"],
        },
    ).to_parquet(feature_matrix, index=False)

    args = (
        "import-transfermarkt-truth-labels",
        "--snapshot", str(snapshot),
        "--season", "2425",
        "--output", str(output),
        "--feature-matrix", str(feature_matrix),
    )
    _run_cli(monkeypatch, *args)
    _write_snapshot(snapshot, "12m")
    _run_cli(monkeypatch, *args)

    labels = pd.read_parquet(output)
    assert len(labels) == 2
    assert set(labels["label_source"]) == {"award", "transfermarkt_value"}
    value = labels.loc[labels["label_source"] == "transfermarkt_value", "label_value"].item()
    assert value == 12_000_000.0
    identity = json.loads(
        (tmp_path / "transfermarkt_identity_report.json").read_text(encoding="utf-8"),
    )
    assert identity["mapped_rows"] == 1
    assert identity["input_provenance"]["snapshot"]["sha256"] == hashlib.sha256(
        snapshot.read_bytes()
    ).hexdigest()


def test_transfermarkt_review_confirmation_is_bound_to_current_input_hashes(
    tmp_path, monkeypatch
) -> None:
    snapshot = tmp_path / "snapshot.csv"
    output = tmp_path / "truth_labels.parquet"
    feature_matrix = tmp_path / "rating_feature_matrix.parquet"
    report = tmp_path / "identity_report.json"
    ledger = tmp_path / "identity_ledger.jsonl"
    _write_snapshot(snapshot)
    pd.DataFrame(
        {
            "player_id": ["alice|one", "alice|two"],
            "player_name": ["Alice Example", "Alice Example"],
            "team_name": ["Other FC", "Different FC"],
            "season_id": ["2425", "2425"],
        }
    ).to_parquet(feature_matrix, index=False)
    args = (
        "import-transfermarkt-truth-labels",
        "--snapshot", str(snapshot),
        "--season", "2425",
        "--output", str(output),
        "--feature-matrix", str(feature_matrix),
        "--identity-report", str(report),
    )

    _run_cli(monkeypatch, *args)
    assert not output.exists()
    _run_cli(
        monkeypatch,
        "transfermarkt-identity-review",
        "--report", str(report),
        "--ledger", str(ledger),
        "--source-row", "0",
        "--action", "confirmed",
        "--canonical-player-id", "alice|two",
    )
    _run_cli(monkeypatch, *args, "--identity-ledger", str(ledger))

    labels = pd.read_parquet(output)
    assert labels["player_id"].tolist() == ["alice|two"]
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["review_decisions"]["confirmed_rows"] == 1


def test_identity_revocation_reconciles_only_proven_label_rows(
    tmp_path, monkeypatch, capsys
) -> None:
    snapshot = tmp_path / "snapshot.csv"
    output = tmp_path / "truth_labels.parquet"
    feature_matrix = tmp_path / "rating_feature_matrix.parquet"
    report = tmp_path / "identity_report.json"
    identity_ledger = tmp_path / "identity_ledger.jsonl"
    label_ledger = tmp_path / "label_ledger.jsonl"
    _write_snapshot(snapshot)
    _write_existing_labels(output)
    pd.DataFrame(
        {
            "player_id": ["alice|one", "alice|two"],
            "player_name": ["Alice Example", "Alice Example"],
            "team_name": ["Other FC", "Different FC"],
            "season_id": ["2425", "2425"],
        }
    ).to_parquet(feature_matrix, index=False)
    import_args = (
        "import-transfermarkt-truth-labels",
        "--snapshot", str(snapshot),
        "--season", "2425",
        "--output", str(output),
        "--feature-matrix", str(feature_matrix),
        "--identity-report", str(report),
        "--identity-ledger", str(identity_ledger),
        "--label-ledger", str(label_ledger),
    )

    _run_cli(monkeypatch, *import_args)
    _run_cli(
        monkeypatch,
        "transfermarkt-identity-review",
        "--report", str(report),
        "--ledger", str(identity_ledger),
        "--source-row", "0",
        "--action", "confirmed",
        "--canonical-player-id", "alice|two",
    )
    _run_cli(monkeypatch, *import_args)
    assert set(pd.read_parquet(output)["label_source"]) == {"award", "transfermarkt_value"}

    _run_cli(
        monkeypatch,
        "transfermarkt-identity-review",
        "--report", str(report),
        "--ledger", str(identity_ledger),
        "--source-row", "0",
        "--action", "revoked",
    )
    capsys.readouterr()
    _run_cli(
        monkeypatch,
        "reconcile-transfermarkt-truth-labels",
        "--labels", str(output),
        "--identity-ledger", str(identity_ledger),
        "--label-ledger", str(label_ledger),
    )
    preview = json.loads(capsys.readouterr().out)
    assert preview["dry_run"] is True
    assert preview["removable_rows"] == 1
    assert set(pd.read_parquet(output)["label_source"]) == {"award", "transfermarkt_value"}

    _run_cli(
        monkeypatch,
        "reconcile-transfermarkt-truth-labels",
        "--labels", str(output),
        "--identity-ledger", str(identity_ledger),
        "--label-ledger", str(label_ledger),
        "--apply",
    )
    labels = pd.read_parquet(output)
    assert labels["label_source"].tolist() == ["award"]
