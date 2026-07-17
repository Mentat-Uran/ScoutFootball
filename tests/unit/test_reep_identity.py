from __future__ import annotations

import json

import pytest

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.reep_identity import (
    REEP_IDENTITY_LOOKUP_TYPE,
    lookup_reep_provider_identity,
)
from scoutfootball.evaluation.source_snapshot_ledger import (
    SNAPSHOT_LEDGER_TYPE,
    SNAPSHOT_LEDGER_VERSION,
)


def _write_people_csv(settings: PlatformSettings, text: str) -> None:
    path = settings.data_root / "raw" / "reep" / "people.csv"
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")


def test_exact_reep_provider_lookup_returns_cross_identifiers(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    _write_people_csv(
        settings,
        "reep_id,key_wikidata,type,name,full_name,key_transfermarkt,key_fbref\n"
        "r1,Q1,player,Alice,Alice Example,123,alice-1\n"
        "r2,Q2,coach,Bob,Bob Example,456,bob-2\n",
    )

    report = lookup_reep_provider_identity(
        provider="transfermarkt", provider_id="123", settings=settings
    )

    assert report["report_type"] == REEP_IDENTITY_LOOKUP_TYPE
    assert report["status"] == "found"
    assert report["match_count"] == 1
    assert report["matches"] == [
        {
            "reep_id": "r1",
            "entity_type": "player",
            "name": "Alice",
            "full_name": "Alice Example",
            "provider_ids": {"transfermarkt": "123", "fbref": "alice-1", "wikidata": "Q1"},
        }
    ]
    assert report["source_snapshot"] == {"status": "not_recorded"}
    assert "truth-label" in " ".join(report["limitations"])


def test_reep_lookup_preserves_duplicate_results_and_limit(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    _write_people_csv(
        settings,
        "reep_id,key_wikidata,type,name,full_name,key_transfermarkt,key_fbref\n"
        "r1,Q1,player,Alice,Alice Example,123,alice-1\n"
        "r2,Q2,player,Alicia,Alicia Example,123,alicia-2\n",
    )

    report = lookup_reep_provider_identity(
        provider="transfermarkt", provider_id="123", settings=settings, limit=1
    )

    assert report["match_count"] == 2
    assert report["returned_count"] == 1
    assert report["truncated"] is True
    assert report["matches"][0]["reep_id"] == "r1"


def test_reep_lookup_reports_an_exact_id_miss(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    _write_people_csv(
        settings,
        "reep_id,key_wikidata,type,name,full_name,key_transfermarkt,key_fbref\n"
        "r1,Q1,player,Alice,Alice Example,123,alice-1\n",
    )

    report = lookup_reep_provider_identity(
        provider="fbref", provider_id="no-such-id", settings=settings
    )

    assert report["status"] == "not_found"
    assert report["match_count"] == 0
    assert report["matches"] == []


def test_reep_lookup_uses_only_explicit_recorded_snapshot(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    _write_people_csv(
        settings,
        "reep_id,key_wikidata,type,name,full_name,key_transfermarkt,key_fbref\n"
        "r1,Q1,player,Alice,Alice Example,123,alice-1\n",
    )
    ledger = tmp_path / "snapshots.jsonl"
    ledger.write_text(
        json.dumps(
            {
                "record_type": SNAPSHOT_LEDGER_TYPE,
                "record_version": SNAPSHOT_LEDGER_VERSION,
                "snapshot_id": "reep:2026-06-21:example",
                "source_id": "reep",
                "snapshot_date": "2026-06-21",
                "recorded_at": "2026-07-17T00:00:00Z",
                "evidence": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = lookup_reep_provider_identity(
        provider="wikidata", provider_id="Q1", settings=settings, snapshot_ledger_path=ledger
    )

    assert report["source_snapshot"] == {
        "status": "recorded",
        "snapshot_id": "reep:2026-06-21:example",
        "snapshot_date": "2026-06-21",
        "recorded_at": "2026-07-17T00:00:00Z",
    }


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"provider": "unknown", "provider_id": "x"}, "provider_invalid"),
        ({"provider": "fbref", "provider_id": " "}, "provider_id_required"),
        ({"provider": "fbref", "provider_id": "x", "limit": 0}, "limit_out_of_range"),
    ],
)
def test_reep_lookup_rejects_invalid_requests(tmp_path, kwargs, message) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    with pytest.raises(ValueError, match=message):
        lookup_reep_provider_identity(settings=settings, **kwargs)


def test_reep_lookup_rejects_paths_outside_registered_source(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    outside = tmp_path / "people.csv"
    outside.write_text("id\n1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="path_outside_registered_source"):
        lookup_reep_provider_identity(
            provider="fbref", provider_id="x", path=outside, settings=settings
        )


def test_reep_lookup_rejects_incomplete_snapshot_schema(tmp_path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    _write_people_csv(settings, "reep_id,key_wikidata\nr1,Q1\n")

    with pytest.raises(ValueError, match="reep_schema_missing"):
        lookup_reep_provider_identity(provider="wikidata", provider_id="Q1", settings=settings)
