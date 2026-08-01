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
    load_resolved_player_ratings,
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


def _sample_ratings_df(**overrides) -> pd.DataFrame:
    """Return a small player_ratings_optimized-shaped DataFrame.

    The legacy ratings table only carries the human-readable ``player`` +
    ``season`` columns (no ``player_id`` / ``source_name``). The resolver
    recovers the source key by joining to ``player_match.parquet`` on
    ``(player, season)`` → ``(player_name, season_id)``.
    """
    base = {
        "player": ["Lara", "Marco", "Unmatched Player", "Martin"],
        "season": ["2425"] * 4,
        "rating": [7.1, 6.8, 5.5, 6.4],
    }
    base.update(overrides)
    return pd.DataFrame(base)


def _write_player_ratings(root, df: pd.DataFrame | None = None) -> None:
    path = root / "data" / "gold" / "feature_store" / "player_ratings_optimized.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    (df if df is not None else _sample_ratings_df()).to_parquet(path, index=False)


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
# load_resolved_player_ratings (PRS-1 slice 8b)
# ---------------------------------------------------------------------------


class TestLoadResolvedPlayerRatings:
    """The legacy ratings table only carries ``player`` + ``season``. The
    resolver recovers the source key by joining to ``player_match.parquet``
    on ``(player, season)`` → ``(player_name, season_id)`` and then applies
    the identity registry's active mappings.

    These tests pin the join contract and the honest fallbacks documented
    in the ``load_resolved_player_ratings`` docstring.
    """

    def test_raises_on_missing_ratings_parquet(self, tmp_path) -> None:
        """No player_ratings_optimized.parquet → ValueError (the ratings
        table is the primary input; without it there is nothing to
        resolve)."""
        settings = PlatformSettings.from_root(tmp_path)
        with pytest.raises(ValueError, match="canonical_resolver_load_failed"):
            load_resolved_player_ratings(settings=settings)

    def test_raises_on_empty_ratings_parquet(self, tmp_path) -> None:
        _write_player_ratings(tmp_path, df=pd.DataFrame({"player": [], "season": []}))
        settings = PlatformSettings.from_root(tmp_path)
        with pytest.raises(ValueError, match="0 rows"):
            load_resolved_player_ratings(settings=settings)

    def test_raises_when_ratings_already_has_canonical_col(self, tmp_path) -> None:
        """The resolver never silently overwrites an existing canonical
        decision. If the ratings table already carries the column, the
        caller must drop it first."""
        ratings = _sample_ratings_df()
        ratings["canonical_player_id"] = "preset"
        _write_player_ratings(tmp_path, df=ratings)
        _write_player_match(tmp_path)
        settings = PlatformSettings.from_root(tmp_path)
        with pytest.raises(
            ValueError, match="canonical_resolver_input_already_has_column"
        ):
            load_resolved_player_ratings(settings=settings)

    def test_missing_player_match_falls_back_to_unresolved_unknown_missing(
        self, tmp_path
    ) -> None:
        """When player_match.parquet is unavailable, the resolver cannot
        recover the source key. Every row gets the explicit
        ``unresolved:unknown:missing`` marker so downstream consumers see
        the unresolved state instead of trusting a source-specific ID."""
        _write_player_ratings(tmp_path)
        settings = PlatformSettings.from_root(tmp_path)
        out = load_resolved_player_ratings(settings=settings)
        assert isinstance(out, pd.DataFrame)
        assert "canonical_player_id" in out.columns
        assert "player_id" in out.columns
        assert "source_name" in out.columns
        assert "canonical_match_ambiguous" in out.columns
        # All rows honestly report unresolved:unknown:missing.
        assert (out["canonical_player_id"] == "unresolved:unknown:missing").all()
        # No source key recovered.
        assert out["player_id"].isna().all()
        assert out["source_name"].isna().all()
        # Ambiguous flag is False (no join happened).
        assert (~out["canonical_match_ambiguous"]).all()

    def test_join_recovers_source_key_for_matched_rows(self, tmp_path) -> None:
        """Ratings rows whose (player, season) matches a player_match row
        inherit that row's ``player_id`` + ``source_name`` and get a
        resolved canonical_player_id when the registry has an active
        confirmed mapping for the recovered key."""
        _write_player_match(tmp_path)
        _write_player_ratings(tmp_path)
        settings = PlatformSettings.from_root(tmp_path)
        # Confirm a mapping for Marco's understat key (from _sample_df).
        append_decision(
            _confirmed_record(
                source_name="understat",
                source_player_id="understat|12345",
                canonical_player_id="canonical:marco",
                revision=1,
            ),
            settings=settings,
        )
        out = load_resolved_player_ratings(settings=settings)
        # Marco's row recovered the source key and got the canonical ID.
        marco = out[out["player"] == "Marco"].iloc[0]
        assert marco["player_id"] == "understat|12345"
        assert marco["source_name"] == "understat"
        assert marco["canonical_player_id"] == "canonical:marco"
        assert marco["canonical_match_ambiguous"] is False or bool(
            marco["canonical_match_ambiguous"]
        ) is False
        # Lara also matched player_match (fbref|lara|1998|ar) but has no
        # registry mapping, so she stays unresolved with the source key.
        lara = out[out["player"] == "Lara"].iloc[0]
        assert lara["player_id"] == "lara|1998|ar"
        assert lara["source_name"] == "fbref"
        assert is_unresolved(lara["canonical_player_id"])
        assert lara["canonical_player_id"] == "unresolved:fbref:lara|1998|ar"

    def test_unmatched_ratings_row_gets_unresolved_unknown_missing(
        self, tmp_path
    ) -> None:
        """A ratings row with no (player, season) match in player_match
        cannot recover its source key. It gets the defensive
        ``unresolved:unknown:missing`` marker (the same fallback used
        when player_match.parquet is missing entirely)."""
        _write_player_match(tmp_path)
        _write_player_ratings(tmp_path)
        settings = PlatformSettings.from_root(tmp_path)
        out = load_resolved_player_ratings(settings=settings)
        unmatched = out[out["player"] == "Unmatched Player"].iloc[0]
        assert unmatched["canonical_player_id"] == "unresolved:unknown:missing"
        # Source key is NaN — the join did not recover anything.
        assert pd.isna(unmatched["player_id"])
        assert pd.isna(unmatched["source_name"])

    def test_ambiguous_match_flagged(self, tmp_path) -> None:
        """When multiple player_match rows share the same
        (player_name, season_id), the first match's source key is used
        but the row is flagged ``canonical_match_ambiguous=True`` so
        downstream consumers do not trust the canonical ID silently."""
        # Two player_match rows for "Lara" in season "2425" with
        # different source keys (the same-name aliasing risk documented
        # in the PRS-1 identity audit).
        pm_df = pd.DataFrame(
            {
                "source_name": ["fbref", "understat"],
                "player_id": ["lara|1998|ar", "lara|1998|ar_duplicate"],
                "player_name": ["Lara", "Lara"],
                "season_id": ["2425", "2425"],
            }
        )
        _write_player_match(tmp_path, df=pm_df)
        _write_player_ratings(tmp_path)
        settings = PlatformSettings.from_root(tmp_path)
        out = load_resolved_player_ratings(settings=settings)
        lara = out[out["player"] == "Lara"].iloc[0]
        assert bool(lara["canonical_match_ambiguous"]) is True

    def test_empty_registry_marks_all_matched_rows_unresolved(self, tmp_path) -> None:
        """With no confirmed mappings, matched rows keep the source-stable
        ``unresolved:<source>:<id>`` marker (not unresolved:unknown:missing,
        because the source key was successfully recovered)."""
        _write_player_match(tmp_path)
        _write_player_ratings(tmp_path)
        settings = PlatformSettings.from_root(tmp_path)
        out = load_resolved_player_ratings(settings=settings)
        marco = out[out["player"] == "Marco"].iloc[0]
        assert marco["canonical_player_id"] == "unresolved:understat:understat|12345"

    def test_input_ratings_not_mutated(self, tmp_path) -> None:
        _write_player_match(tmp_path)
        _write_player_ratings(tmp_path)
        settings = PlatformSettings.from_root(tmp_path)
        ratings_path = (
            tmp_path / "data" / "gold" / "feature_store" / "player_ratings_optimized.parquet"
        )
        before = ratings_path.read_bytes()
        load_resolved_player_ratings(settings=settings)
        assert ratings_path.read_bytes() == before

    def test_round_trip_with_registry(self, tmp_path) -> None:
        """Append a confirmed mapping → load_resolved_player_ratings
        reflects it on the matching ratings row."""
        _write_player_match(tmp_path)
        _write_player_ratings(tmp_path)
        settings = PlatformSettings.from_root(tmp_path)
        append_decision(
            _confirmed_record(
                source_name="fbref",
                source_player_id="lara|1998|ar",
                canonical_player_id="canonical:lara",
                revision=1,
            ),
            settings=settings,
        )
        out = load_resolved_player_ratings(settings=settings)
        lara = out[out["player"] == "Lara"].iloc[0]
        assert lara["canonical_player_id"] == "canonical:lara"


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
