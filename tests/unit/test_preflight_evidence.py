"""Tests for portable evidence reports generated from Parquet preflight."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.parquet_preflight import preflight_parquet
from scoutfootball.evaluation.preflight_evidence import (
    PREFLIGHT_EVIDENCE_VERSION,
    build_preflight_evidence_report,
    write_preflight_evidence_report,
)


def _write_parquet(path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)


def test_evidence_report_links_observation_to_recorded_source_license(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    relative = "raw/football_data/combined_results.parquet"
    _write_parquet(settings.data_root / relative, pd.DataFrame({"match_id": [1, 2]}))
    inspection = preflight_parquet(relative, settings=settings)

    payload = build_preflight_evidence_report(
        [inspection], target="raw", generated_at="2026-07-17T00:00:00Z"
    )

    assert payload["report_version"] == PREFLIGHT_EVIDENCE_VERSION
    assert payload["generator"]["package_version"]
    assert payload["generator"]["contract_registry_generated_at"]
    assert payload["summary"]["ok"] == 1
    assert payload["summary"]["contracts_recorded"] == 1
    assert payload["summary"]["licenses_recorded"] == 1
    assert payload["summary"]["snapshots_recorded"] == 0
    artifact = payload["artifacts"][0]
    assert artifact["inspection"]["row_count"] == 2
    assert artifact["provenance"]["contract"]["artifact_id"] == "raw/football_data"
    assert artifact["provenance"]["source_license"]["status"] == "recorded"
    assert artifact["provenance"]["snapshot"]["status"] == "not_recorded"
    assert artifact["provenance"]["lineage"]["status"] == "not_recorded"


def test_evidence_report_does_not_invent_unregistered_provenance(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    relative = "raw/unregistered/source.parquet"
    _write_parquet(settings.data_root / relative, pd.DataFrame({"id": [1]}))
    inspection = preflight_parquet(relative, settings=settings)

    payload = build_preflight_evidence_report([inspection], target="raw")

    provenance = payload["artifacts"][0]["provenance"]
    assert provenance["contract"]["status"] == "not_recorded"
    assert provenance["source_license"]["status"] == "not_recorded"
    assert provenance["snapshot"]["status"] == "not_recorded"
    assert provenance["lineage"]["status"] == "not_recorded"


def test_write_evidence_report_refuses_overwrite_without_explicit_flag(tmp_path) -> None:
    output = tmp_path / "reports" / "preflight-evidence.json"
    first = {"report_type": "test", "value": 1}
    write_preflight_evidence_report(first, output)
    assert json.loads(output.read_text(encoding="utf-8")) == first

    with pytest.raises(FileExistsError, match="overwrite-evidence"):
        write_preflight_evidence_report({"value": 2}, output)

    write_preflight_evidence_report({"value": 2}, output, overwrite=True)
    assert json.loads(output.read_text(encoding="utf-8")) == {"value": 2}
