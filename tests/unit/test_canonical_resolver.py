"""Tests for the canonical player ID resolver (PRS-1 R-005 slice 3).

Covers:

- ``unresolved_canonical_id`` and ``is_unresolved`` form a stable pair: the
  marker is ``unresolved:<source>:<id>`` and is detected back without
  false positives on resolved canonical IDs.
- ``resolve_canonical_ids`` applies active ``confirmed`` mappings, falls
  back to ``unresolved:<source>:<id>`` for unresolved pairs, clears on
  ``revoked``, isolates cross-source keys, coerces numeric/NaN values,
  and refuses to overwrite an existing ``canonical_player_id`` column.
- ``resolution_summary`` reports resolved vs unresolved counts, distinct
  IDs, and per-source breakdowns; returns ``unavailable`` when the
  canonical column is missing.
- ``build_canonical_resolution_report`` is read-only and fail-closed:
  missing/empty ``player_match.parquet`` and corrupt registry all return
  ``status=unavailable``; a healthy workspace with an empty registry
  returns ``status=ok`` with all rows unresolved (honest default).
- ``load_resolved_player_match`` raises on missing parquet and returns a
  resolved DataFrame on success.
- Round-trip: append a confirmed decision → resolve → the row's
  ``canonical_player_id`` matches the recorded mapping.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.canonical_resolver import (
    CANONICAL_RESOLVER_SCHEMA,
    CANONICAL_RESOLVER_VERSION,
    UNRESOLVED_PREFIX,
    build_canonical_resolution_report,
    is_unresolved,
    load_resolved_player_match,
    resolution_summary,
    resolve_canonical_ids,
    unresolved_canonical_id,
)
from scoutfootball.evaluation.identity_registry import (
    append_decision,
    build_decision,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sample_df(**overrides) -> pd.DataFrame:
    """Return a small player_match-shaped DataFrame for resolver tests."""
    base = {
        "source_name": ["fbref", "understat", "statsbomb_open", "fbref"],
        "player_id": [
            "lara|1998|ar",
            "understat|12345",
            "10605",
            "martin|1997|dk",
        ],
        "player_name": ["Lara", "Marco", "Stats Player", "Martin"],
        "season_id": ["2425"] * 4,
    }
    base.update(overrides)
    return pd.DataFrame(base)


def _confirmed_record(
    *,
    source_name: str,
    source_player_id: str,
    canonical_player_id: str,
    revision: int,
    action: str = "confirmed",
) -> dict:
    return build_decision(
        source_name=source_name,
        source_player_id=source_player_id,
        action=action,
        canonical_player_id=canonical_player_id if action == "confirmed" else None,
        evidence="test mapping for resolver",
        decided_by="maintainer",
        revision=revision,
    )


def _write_player_match(root, df: pd.DataFrame | None = None) -> None:
    path = root / "data" / "gold" / "feature_store" / "player_match.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    (df if df is not None else _sample_df()).to_parquet(path, index=False)


# ---------------------------------------------------------------------------
# unresolved_canonical_id / is_unresolved
# ---------------------------------------------------------------------------


class TestUnresolvedMarker:
    def test_marker_format(self) -> None:
        assert (
            unresolved_canonical_id("fbref", "lara|1998|ar")
            == "unresolved:fbref:lara|1998|ar"
        )

    def test_marker_is_detected_as_unresolved(self) -> None:
        assert is_unresolved("unresolved:fbref:lara|1998|ar") is True

    def test_resolved_id_is_not_unresolved(self) -> None:
        assert is_unresolved("canonical:fbref:lara:1998:ar") is False

    def test_non_string_is_not_unresolved(self) -> None:
        assert is_unresolved(None) is False
        assert is_unresolved(float("nan")) is False
        assert is_unresolved(12345) is False

    def test_empty_string_is_not_unresolved(self) -> None:
        # Defensive: an empty canonical_player_id should not be classified
        # as unresolved; callers must check isna() first.
        assert is_unresolved("") is False

    def test_prefix_only_is_unresolved(self) -> None:
        # A bare "unresolved:" prefix is still an unresolved marker by
        # construction, even though it should never be produced.
        assert is_unresolved("unresolved:") is True

    def test_marker_round_trip(self) -> None:
        marker = unresolved_canonical_id("understat", "understat|12345")
        assert is_unresolved(marker) is True
        assert marker.startswith(f"{UNRESOLVED_PREFIX}:")


# ---------------------------------------------------------------------------
# resolve_canonical_ids
# ---------------------------------------------------------------------------


class TestResolveCanonicalIds:
    def test_empty_registry_marks_all_unresolved(self) -> None:
        df = _sample_df()
        out = resolve_canonical_ids(df, records=[])
        assert "canonical_player_id" in out.columns
        assert (out["canonical_player_id"].apply(is_unresolved)).all()
        assert out.loc[0, "canonical_player_id"] == "unresolved:fbref:lara|1998|ar"
        assert out.loc[1, "canonical_player_id"] == "unresolved:understat:understat|12345"

    def test_confirmed_mapping_applied(self) -> None:
        df = _sample_df()
        records = [
            _confirmed_record(
                source_name="fbref",
                source_player_id="lara|1998|ar",
                canonical_player_id="canonical:fbref:lara:1998:ar",
                revision=1,
            ),
        ]
        out = resolve_canonical_ids(df, records=records)
        assert out.loc[0, "canonical_player_id"] == "canonical:fbref:lara:1998:ar"
        # Other rows still unresolved.
        assert is_unresolved(out.loc[1, "canonical_player_id"])
        assert is_unresolved(out.loc[3, "canonical_player_id"])

    def test_revoked_mapping_falls_back_to_unresolved(self) -> None:
        df = _sample_df()
        records = [
            _confirmed_record(
                source_name="fbref",
                source_player_id="lara|1998|ar",
                canonical_player_id="canonical:fbref:lara:1998:ar",
                revision=1,
            ),
            _confirmed_record(
                source_name="fbref",
                source_player_id="lara|1998|ar",
                canonical_player_id="canonical:fbref:lara:1998:ar",
                revision=2,
                action="revoked",
            ),
        ]
        out = resolve_canonical_ids(df, records=records)
        assert out.loc[0, "canonical_player_id"] == "unresolved:fbref:lara|1998|ar"

    def test_cross_source_isolation(self) -> None:
        """Same player_id under different source_name is two independent keys."""
        df = pd.DataFrame(
            {
                "source_name": ["fbref", "understat"],
                "player_id": ["shared_id", "shared_id"],
            }
        )
        records = [
            _confirmed_record(
                source_name="fbref",
                source_player_id="shared_id",
                canonical_player_id="canonical:fbref:shared",
                revision=1,
            ),
        ]
        out = resolve_canonical_ids(df, records=records)
        assert out.loc[0, "canonical_player_id"] == "canonical:fbref:shared"
        # understat row is unresolved even though it has the same player_id.
        assert out.loc[1, "canonical_player_id"] == "unresolved:understat:shared_id"

    def test_input_not_mutated(self) -> None:
        df = _sample_df()
        original_cols = list(df.columns)
        resolve_canonical_ids(df, records=[])
        assert list(df.columns) == original_cols
        assert "canonical_player_id" not in df.columns

    def test_input_with_canonical_col_rejected(self) -> None:
        df = _sample_df()
        df["canonical_player_id"] = "preset"
        with pytest.raises(
            ValueError, match="canonical_resolver_input_already_has_column"
        ):
            resolve_canonical_ids(df, records=[])

    def test_missing_source_name_col(self) -> None:
        df = pd.DataFrame({"player_id": ["a", "b"]})
        out = resolve_canonical_ids(df, records=[])
        assert out.loc[0, "canonical_player_id"] == "unresolved:unknown:a"
        assert out.loc[1, "canonical_player_id"] == "unresolved:unknown:b"

    def test_missing_player_id_col(self) -> None:
        df = pd.DataFrame({"source_name": ["fbref", "understat"]})
        out = resolve_canonical_ids(df, records=[])
        assert out.loc[0, "canonical_player_id"] == "unresolved:fbref:missing"
        assert out.loc[1, "canonical_player_id"] == "unresolved:understat:missing"

    def test_both_key_cols_missing(self) -> None:
        df = pd.DataFrame({"player_name": ["A", "B"]})
        out = resolve_canonical_ids(df, records=[])
        assert (
            out["canonical_player_id"] == "unresolved:unknown:missing"
        ).all()

    def test_nan_source_name_treated_as_missing(self) -> None:
        df = pd.DataFrame(
            {
                "source_name": [None, np.nan, "fbref"],
                "player_id": ["id1", "id2", "id3"],
            }
        )
        out = resolve_canonical_ids(df, records=[])
        assert out.loc[0, "canonical_player_id"] == "unresolved:unknown:id1"
        assert out.loc[1, "canonical_player_id"] == "unresolved:unknown:id2"
        assert out.loc[2, "canonical_player_id"] == "unresolved:fbref:id3"

    def test_nan_player_id_treated_as_missing(self) -> None:
        df = pd.DataFrame(
            {
                "source_name": ["fbref", "understat"],
                "player_id": [np.nan, None],
            }
        )
        out = resolve_canonical_ids(df, records=[])
        assert out.loc[0, "canonical_player_id"] == "unresolved:fbref:missing"
        assert out.loc[1, "canonical_player_id"] == "unresolved:understat:missing"

    def test_both_nan_on_same_row(self) -> None:
        df = pd.DataFrame(
            {"source_name": [np.nan], "player_id": [None]}
        )
        out = resolve_canonical_ids(df, records=[])
        assert out.loc[0, "canonical_player_id"] == "unresolved:unknown:missing"

    def test_numeric_player_id_coerced_to_str(self) -> None:
        """StatsBomb player_id is numeric; pipeline stores it as str, but
        the resolver must also accept int/float to match registry keys."""
        df = pd.DataFrame(
            {
                "source_name": ["statsbomb_open", "statsbomb_open"],
                "player_id": [10605, 10605.0],
            }
        )
        records = [
            _confirmed_record(
                source_name="statsbomb_open",
                source_player_id="10605",
                canonical_player_id="canonical:statsbomb:10605",
                revision=1,
            ),
        ]
        out = resolve_canonical_ids(df, records=records)
        assert (
            out["canonical_player_id"] == "canonical:statsbomb:10605"
        ).all()

    def test_empty_dataframe_returns_empty_with_column(self) -> None:
        df = pd.DataFrame({"source_name": [], "player_id": []})
        out = resolve_canonical_ids(df, records=[])
        assert len(out) == 0
        assert "canonical_player_id" in out.columns

    def test_custom_column_names(self) -> None:
        df = pd.DataFrame({"src": ["fbref"], "pid": ["x"]})
        out = resolve_canonical_ids(
            df,
            records=[],
            source_name_col="src",
            source_player_id_col="pid",
            canonical_col="canon",
        )
        assert out.loc[0, "canon"] == "unresolved:fbref:x"

    def test_multiple_confirmed_mappings(self) -> None:
        df = _sample_df()
        records = [
            _confirmed_record(
                source_name="fbref",
                source_player_id="lara|1998|ar",
                canonical_player_id="canonical:lara",
                revision=1,
            ),
            _confirmed_record(
                source_name="understat",
                source_player_id="understat|12345",
                canonical_player_id="canonical:marco",
                revision=2,
            ),
            _confirmed_record(
                source_name="statsbomb_open",
                source_player_id="10605",
                canonical_player_id="canonical:stats",
                revision=3,
            ),
        ]
        out = resolve_canonical_ids(df, records=records)
        assert out.loc[0, "canonical_player_id"] == "canonical:lara"
        assert out.loc[1, "canonical_player_id"] == "canonical:marco"
        assert out.loc[2, "canonical_player_id"] == "canonical:stats"
        # Fourth row (martin|1997|dk) still unresolved.
        assert is_unresolved(out.loc[3, "canonical_player_id"])

    def test_superseded_record_keeps_latest_canonical(self) -> None:
        """A second confirmed for the same key updates the active mapping;
        supersedes_decision_id does not block the update."""
        df = pd.DataFrame(
            {"source_name": ["fbref"], "player_id": ["lara|1998|ar"]}
        )
        records = [
            _confirmed_record(
                source_name="fbref",
                source_player_id="lara|1998|ar",
                canonical_player_id="canonical:old",
                revision=1,
            ),
            build_decision(
                source_name="fbref",
                source_player_id="lara|1998|ar",
                action="confirmed",
                canonical_player_id="canonical:new",
                evidence="corrected mapping",
                decided_by="maintainer",
                supersedes_decision_id="11111111-1111-1111-1111-111111111111",
                revision=2,
            ),
        ]
        out = resolve_canonical_ids(df, records=records)
        assert out.loc[0, "canonical_player_id"] == "canonical:new"


# ---------------------------------------------------------------------------
# resolution_summary
# ---------------------------------------------------------------------------


class TestResolutionSummary:
    def test_all_unresolved(self) -> None:
        df = resolve_canonical_ids(_sample_df(), records=[])
        summary = resolution_summary(df)
        assert summary["total_rows"] == 4
        assert summary["resolved_rows"] == 0
        assert summary["unresolved_rows"] == 4
        assert summary["distinct_canonical_ids"] == 0
        assert summary["distinct_unresolved_markers"] == 4

    def test_all_resolved(self) -> None:
        df = pd.DataFrame(
            {"source_name": ["fbref", "fbref"], "player_id": ["a", "b"]}
        )
        records = [
            _confirmed_record(
                source_name="fbref",
                source_player_id="a",
                canonical_player_id="canonical:a",
                revision=1,
            ),
            _confirmed_record(
                source_name="fbref",
                source_player_id="b",
                canonical_player_id="canonical:b",
                revision=2,
            ),
        ]
        resolved_df = resolve_canonical_ids(df, records=records)
        summary = resolution_summary(resolved_df)
        assert summary["resolved_rows"] == 2
        assert summary["unresolved_rows"] == 0
        assert summary["distinct_canonical_ids"] == 2
        assert summary["distinct_unresolved_markers"] == 0

    def test_mixed_resolution(self) -> None:
        df = pd.DataFrame(
            {"source_name": ["fbref", "understat"], "player_id": ["a", "b"]}
        )
        records = [
            _confirmed_record(
                source_name="fbref",
                source_player_id="a",
                canonical_player_id="canonical:a",
                revision=1,
            ),
        ]
        resolved_df = resolve_canonical_ids(df, records=records)
        summary = resolution_summary(resolved_df)
        assert summary["resolved_rows"] == 1
        assert summary["unresolved_rows"] == 1
        assert summary["distinct_canonical_ids"] == 1
        assert summary["distinct_unresolved_markers"] == 1

    def test_by_source_breakdown(self) -> None:
        df = pd.DataFrame(
            {
                "source_name": ["fbref", "fbref", "understat"],
                "player_id": ["a", "b", "c"],
            }
        )
        records = [
            _confirmed_record(
                source_name="fbref",
                source_player_id="a",
                canonical_player_id="canonical:a",
                revision=1,
            ),
        ]
        resolved_df = resolve_canonical_ids(df, records=records)
        summary = resolution_summary(resolved_df)
        assert summary["by_source"]["fbref"] == {"resolved": 1, "unresolved": 1}
        assert summary["by_source"]["understat"] == {"resolved": 0, "unresolved": 1}

    def test_empty_dataframe(self) -> None:
        df = resolve_canonical_ids(
            pd.DataFrame({"source_name": [], "player_id": []}), records=[]
        )
        summary = resolution_summary(df)
        assert summary["total_rows"] == 0
        assert summary["resolved_rows"] == 0
        assert summary["unresolved_rows"] == 0
        assert summary["by_source"] == {}

    def test_missing_canonical_col_returns_unavailable(self) -> None:
        df = pd.DataFrame({"source_name": ["fbref"], "player_id": ["a"]})
        summary = resolution_summary(df)
        assert summary["status"] == "unavailable"
        assert "canonical_player_id column missing" in summary["evidence"]["reason"]

    def test_distinct_canonical_ids_counts_unique_values(self) -> None:
        """Two rows mapping to the same canonical ID count as 1 distinct."""
        df = pd.DataFrame(
            {
                "source_name": ["fbref", "understat"],
                "player_id": ["fb_a", "un_b"],
            }
        )
        records = [
            _confirmed_record(
                source_name="fbref",
                source_player_id="fb_a",
                canonical_player_id="canonical:same_person",
                revision=1,
            ),
            _confirmed_record(
                source_name="understat",
                source_player_id="un_b",
                canonical_player_id="canonical:same_person",
                revision=2,
            ),
        ]
        resolved_df = resolve_canonical_ids(df, records=records)
        summary = resolution_summary(resolved_df)
        assert summary["resolved_rows"] == 2
        assert summary["distinct_canonical_ids"] == 1


# ---------------------------------------------------------------------------
# build_canonical_resolution_report
# ---------------------------------------------------------------------------


class TestBuildCanonicalResolutionReport:
    def test_missing_player_match_returns_unavailable(self, tmp_path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        report = build_canonical_resolution_report(settings=settings)
        assert report["schema"] == CANONICAL_RESOLVER_SCHEMA
        assert report["schema_version"] == CANONICAL_RESOLVER_VERSION
        assert report["status"] == "unavailable"
        assert "player_match.parquet missing" in report["evidence"]["reason"]

    def test_empty_player_match_returns_unavailable(self, tmp_path) -> None:
        _write_player_match(tmp_path, df=pd.DataFrame({"source_name": [], "player_id": []}))
        settings = PlatformSettings.from_root(tmp_path)
        report = build_canonical_resolution_report(settings=settings)
        assert report["status"] == "unavailable"
        assert "0 rows" in report["evidence"]["reason"]

    def test_healthy_workspace_with_empty_registry(self, tmp_path) -> None:
        _write_player_match(tmp_path)
        settings = PlatformSettings.from_root(tmp_path)
        report = build_canonical_resolution_report(settings=settings)
        assert report["status"] == "ok"
        evidence = report["evidence"]
        assert evidence["total_rows"] == 4
        assert evidence["resolved_rows"] == 0
        assert evidence["unresolved_rows"] == 4
        assert evidence["distinct_unresolved_markers"] == 4
        # by_source covers all three sources in the fixture.
        assert set(evidence["by_source"].keys()) == {"fbref", "understat", "statsbomb_open"}
        assert evidence["by_source"]["fbref"] == {"resolved": 0, "unresolved": 2}

    def test_healthy_workspace_with_one_confirmed_mapping(self, tmp_path) -> None:
        _write_player_match(tmp_path)
        settings = PlatformSettings.from_root(tmp_path)
        record = _confirmed_record(
            source_name="fbref",
            source_player_id="lara|1998|ar",
            canonical_player_id="canonical:fbref:lara:1998:ar",
            revision=1,
        )
        append_decision(record, settings=settings)

        report = build_canonical_resolution_report(settings=settings)
        assert report["status"] == "ok"
        evidence = report["evidence"]
        assert evidence["resolved_rows"] == 1
        assert evidence["unresolved_rows"] == 3
        assert evidence["distinct_canonical_ids"] == 1
        assert evidence["by_source"]["fbref"] == {"resolved": 1, "unresolved": 1}

    def test_revoked_mapping_makes_row_unresolved(self, tmp_path) -> None:
        _write_player_match(tmp_path)
        settings = PlatformSettings.from_root(tmp_path)
        # Confirm then revoke the same key.
        append_decision(
            _confirmed_record(
                source_name="fbref",
                source_player_id="lara|1998|ar",
                canonical_player_id="canonical:fbref:lara:1998:ar",
                revision=1,
            ),
            settings=settings,
        )
        append_decision(
            build_decision(
                source_name="fbref",
                source_player_id="lara|1998|ar",
                action="revoked",
                canonical_player_id=None,
                evidence="wrong mapping",
                decided_by="maintainer",
                revision=2,
            ),
            settings=settings,
        )
        report = build_canonical_resolution_report(settings=settings)
        evidence = report["evidence"]
        assert evidence["resolved_rows"] == 0
        assert evidence["unresolved_rows"] == 4

    def test_corrupt_registry_returns_unavailable(self, tmp_path) -> None:
        _write_player_match(tmp_path)
        settings = PlatformSettings.from_root(tmp_path)
        # Write a corrupt registry JSONL (invalid JSON on line 1).
        registry_path = settings.gold_root / "identity_registry" / "decisions.jsonl"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text("not valid json\n", encoding="utf-8")

        report = build_canonical_resolution_report(settings=settings)
        assert report["status"] == "unavailable"
        assert "identity registry read failed" in report["evidence"]["reason"]

    def test_report_never_raises_on_unreadable_parquet(self, tmp_path) -> None:
        """A corrupt parquet must not crash the report; it returns unavailable."""
        path = tmp_path / "data" / "gold" / "feature_store" / "player_match.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"not a parquet file")
        settings = PlatformSettings.from_root(tmp_path)
        report = build_canonical_resolution_report(settings=settings)
        assert report["status"] == "unavailable"
        assert "read failed" in report["evidence"]["reason"]


# ---------------------------------------------------------------------------
# load_resolved_player_match
# ---------------------------------------------------------------------------


class TestLoadResolvedPlayerMatch:
    def test_raises_on_missing_parquet(self, tmp_path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        with pytest.raises(ValueError, match="canonical_resolver_load_failed"):
            load_resolved_player_match(settings=settings)

    def test_raises_on_empty_parquet(self, tmp_path) -> None:
        _write_player_match(tmp_path, df=pd.DataFrame({"source_name": [], "player_id": []}))
        settings = PlatformSettings.from_root(tmp_path)
        with pytest.raises(ValueError, match="0 rows"):
            load_resolved_player_match(settings=settings)

    def test_returns_resolved_dataframe(self, tmp_path) -> None:
        _write_player_match(tmp_path)
        settings = PlatformSettings.from_root(tmp_path)
        out = load_resolved_player_match(settings=settings)
        assert isinstance(out, pd.DataFrame)
        assert "canonical_player_id" in out.columns
        assert len(out) == 4
        # Empty registry → all unresolved.
        assert out["canonical_player_id"].apply(is_unresolved).all()

    def test_round_trip_with_registry(self, tmp_path) -> None:
        """Append a confirmed decision, then load_resolved_player_match
        should reflect it on the matching row."""
        _write_player_match(tmp_path)
        settings = PlatformSettings.from_root(tmp_path)
        append_decision(
            _confirmed_record(
                source_name="understat",
                source_player_id="understat|12345",
                canonical_player_id="canonical:marco",
                revision=1,
            ),
            settings=settings,
        )
        out = load_resolved_player_match(settings=settings)
        marco_row = out[out["player_id"] == "understat|12345"].iloc[0]
        assert marco_row["canonical_player_id"] == "canonical:marco"
        # Other rows still unresolved.
        other_rows = out[out["player_id"] != "understat|12345"]
        assert other_rows["canonical_player_id"].apply(is_unresolved).all()


# ---------------------------------------------------------------------------
# Schema stability
# ---------------------------------------------------------------------------


class TestSchemaStability:
    def test_schema_constants_are_strings(self) -> None:
        assert isinstance(CANONICAL_RESOLVER_SCHEMA, str)
        assert isinstance(CANONICAL_RESOLVER_VERSION, str)
        assert CANONICAL_RESOLVER_SCHEMA == "scoutfootball.canonical-resolver"
        assert CANONICAL_RESOLVER_VERSION == "1.0.0"

    def test_report_carries_schema_and_version(self, tmp_path) -> None:
        _write_player_match(tmp_path)
        settings = PlatformSettings.from_root(tmp_path)
        report = build_canonical_resolution_report(settings=settings)
        assert report["schema"] == CANONICAL_RESOLVER_SCHEMA
        assert report["schema_version"] == CANONICAL_RESOLVER_VERSION
        assert "generated_at" in report

    def test_generated_at_is_iso8601(self, tmp_path) -> None:
        _write_player_match(tmp_path)
        settings = PlatformSettings.from_root(tmp_path)
        report = build_canonical_resolution_report(settings=settings)
        ts = report["generated_at"]
        assert ts.endswith("Z")
        # ISO 8601: YYYY-MM-DDTHH:MM:SSZ
        assert len(ts) == 20
        assert ts[4] == "-" and ts[7] == "-" and ts[10] == "T" and ts[13] == ":"


# ---------------------------------------------------------------------------
# JSON serialization safety (for research-health integration)
# ---------------------------------------------------------------------------


class TestJsonSerialization:
    def test_report_is_json_serializable(self, tmp_path) -> None:
        _write_player_match(tmp_path)
        settings = PlatformSettings.from_root(tmp_path)
        report = build_canonical_resolution_report(settings=settings)
        # Must round-trip through JSON without raising.
        text = json.dumps(report, ensure_ascii=False, sort_keys=True)
        loaded = json.loads(text)
        assert loaded["schema"] == CANONICAL_RESOLVER_SCHEMA
        assert loaded["evidence"]["total_rows"] == 4

    def test_summary_by_source_is_str_keyed(self, tmp_path) -> None:
        """by_source keys must be plain strings (not numpy types) so the
        report survives JSON serialization."""
        _write_player_match(tmp_path)
        settings = PlatformSettings.from_root(tmp_path)
        report = build_canonical_resolution_report(settings=settings)
        for source_name in report["evidence"]["by_source"]:
            assert isinstance(source_name, str)
