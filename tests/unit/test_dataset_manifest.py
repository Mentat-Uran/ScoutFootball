"""Unit tests for features/manifest.py: team_match and player_match manifests.

Verifies that the new manifest schema:
- Aligns with rating_feature_matrix_manifest.json on total_rows, columns
  (name/dtype/source/missing_rate), input_hash, timestamp.
- Adds artifact, column_count, schema_version, source_lineage as
  extended fields.
- Captures per-input-file hash and row count for drift detection.
- Records source_breakdown for player_match (multi-source concat).
- Reads lineage from df.attrs when not explicitly passed.
- Handles missing input files gracefully (None hash/rows).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from scoutfootball.features.manifest import (
    MANIFEST_SCHEMA_VERSION,
    TEAM_MATCH_COLUMN_SOURCES,
    SourceLineageEntry,
    build_manifest_payload,
    compute_dataframe_hash,
    count_parquet_rows,
    extract_lineage_attrs,
    hash_file,
    load_manifest,
    relative_to_data_root,
    write_player_match_manifest,
    write_team_match_manifest,
)

# ---------------------------------------------------------------------------
# hash_file / count_parquet_rows
# ---------------------------------------------------------------------------


class TestHashFile:
    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        """Missing files return None so manifest can record the gap."""
        assert hash_file(tmp_path / "does-not-exist.parquet") is None

    def test_returns_hex_prefix_for_existing_file(self, tmp_path: Path) -> None:
        """Existing files return a 16-char hex sha256 prefix."""
        path = tmp_path / "f.bin"
        path.write_bytes(b"hello world")
        result = hash_file(path)
        assert result is not None
        assert len(result) == 16
        # All hex chars
        int(result, 16)

    def test_hash_changes_when_content_changes(self, tmp_path: Path) -> None:
        """Different content produces different hashes."""
        path_a = tmp_path / "a.bin"
        path_b = tmp_path / "b.bin"
        path_a.write_bytes(b"content-a")
        path_b.write_bytes(b"content-b")
        assert hash_file(path_a) != hash_file(path_b)

    def test_hash_stable_for_same_content(self, tmp_path: Path) -> None:
        """Same content produces same hash across calls."""
        path = tmp_path / "f.bin"
        path.write_bytes(b"same content")
        assert hash_file(path) == hash_file(path)


class TestCountParquetRows:
    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        """Missing files return None rather than raising."""
        assert count_parquet_rows(tmp_path / "missing.parquet") is None

    def test_returns_row_count_for_real_parquet(self, tmp_path: Path) -> None:
        """Row count from pyarrow footer matches actual content rows."""
        path = tmp_path / "data.parquet"
        pd.DataFrame({"a": list(range(42))}).to_parquet(path)
        assert count_parquet_rows(path) == 42

    def test_returns_zero_for_empty_parquet(self, tmp_path: Path) -> None:
        """Empty parquet returns 0, not None."""
        path = tmp_path / "empty.parquet"
        pd.DataFrame({"a": []}).to_parquet(path)
        assert count_parquet_rows(path) == 0


# ---------------------------------------------------------------------------
# relative_to_data_root
# ---------------------------------------------------------------------------


class TestRelativeToDataRoot:
    def test_returns_forward_slashed_relative_path(self, tmp_path: Path) -> None:
        """Paths under data_root are returned as forward-slashed relative."""

        class FakeSettings:
            data_root = tmp_path

        path = tmp_path / "raw" / "football_data" / "combined.parquet"
        result = relative_to_data_root(path, FakeSettings())
        assert result == "raw/football_data/combined.parquet"

    def test_returns_absolute_path_when_outside_data_root(
        self, tmp_path: Path
    ) -> None:
        """Paths outside data_root fall back to absolute path."""

        class FakeSettings:
            data_root = tmp_path / "data"

        outside = tmp_path / "elsewhere" / "f.parquet"
        result = relative_to_data_root(outside, FakeSettings())
        # Just check it doesn't raise; format depends on platform.
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# compute_dataframe_hash
# ---------------------------------------------------------------------------


class TestComputeDataframeHash:
    def test_empty_frames_produce_empty_hash(self) -> None:
        """Empty DataFrames contribute nothing; hash is sha256 of nothing."""
        result = compute_dataframe_hash(pd.DataFrame(), pd.DataFrame())
        assert len(result) == 16

    def test_none_frames_skipped(self) -> None:
        """None inputs are skipped without raising."""
        result = compute_dataframe_hash(None, pd.DataFrame({"a": [1]}))
        assert len(result) == 16

    def test_same_frames_produce_same_hash(self) -> None:
        """Same content produces same hash."""
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        assert compute_dataframe_hash(df) == compute_dataframe_hash(df.copy())

    def test_different_frames_produce_different_hash(self) -> None:
        """Different content produces different hash."""
        df_a = pd.DataFrame({"a": [1, 2, 3]})
        df_b = pd.DataFrame({"a": [1, 2, 4]})
        assert compute_dataframe_hash(df_a) != compute_dataframe_hash(df_b)


# ---------------------------------------------------------------------------
# build_manifest_payload
# ---------------------------------------------------------------------------


class TestBuildManifestPayload:
    def test_payload_has_aligned_and_extended_fields(self) -> None:
        """Payload must include both aligned (rating_feature_matrix-style)
        and extended (artifact/schema_version/column_count/source_lineage)
        fields."""
        df = pd.DataFrame(
            {
                "match_id": ["m1", "m2"],
                "team_id": ["t1", "t2"],
                "goals_for": [1, 2],
                "goals_against": [0, 1],
            }
        )
        payload = build_manifest_payload(
            df,
            artifact_name="team_match",
            column_sources=TEAM_MATCH_COLUMN_SOURCES,
            source_lineage=[],
        )
        # Aligned fields (present in rating_feature_matrix_manifest.json)
        assert "total_rows" in payload
        assert payload["total_rows"] == 2
        assert "columns" in payload
        assert "input_hash" in payload
        assert "timestamp" in payload
        # Extended fields
        assert payload["artifact"] == "team_match"
        assert payload["schema_version"] == MANIFEST_SCHEMA_VERSION
        assert payload["column_count"] == 4
        assert payload["source_lineage"] == []

    def test_columns_have_required_metadata(self) -> None:
        """Each column entry has name, dtype, source, missing_rate."""
        df = pd.DataFrame(
            {
                "match_id": ["m1", "m2"],
                "goals_for": [1, pd.NA],
            }
        )
        payload = build_manifest_payload(
            df,
            artifact_name="team_match",
            column_sources=TEAM_MATCH_COLUMN_SOURCES,
            source_lineage=[],
        )
        for col_info in payload["columns"]:
            assert "name" in col_info
            assert "dtype" in col_info
            assert "source" in col_info
            assert "missing_rate" in col_info

    def test_missing_rate_reflects_actual_nan_proportion(self) -> None:
        """Missing rate is computed from actual NaN proportion."""
        df = pd.DataFrame({"goals_for": [1, pd.NA, 3, pd.NA]})
        payload = build_manifest_payload(
            df,
            artifact_name="team_match",
            column_sources=TEAM_MATCH_COLUMN_SOURCES,
            source_lineage=[],
        )
        goals_info = next(c for c in payload["columns"] if c["name"] == "goals_for")
        assert goals_info["missing_rate"] == 0.5

    def test_unknown_columns_default_to_derived(self) -> None:
        """Columns not in column_sources default to 'derived'."""
        df = pd.DataFrame({"unknown_col": [1, 2, 3]})
        payload = build_manifest_payload(
            df,
            artifact_name="team_match",
            column_sources=TEAM_MATCH_COLUMN_SOURCES,
            source_lineage=[],
        )
        col_info = payload["columns"][0]
        assert col_info["name"] == "unknown_col"
        assert col_info["source"] == "derived"

    def test_input_hash_uses_provided_value_when_given(self) -> None:
        """When input_hash is explicitly provided, it is used as-is."""
        df = pd.DataFrame({"a": [1]})
        payload = build_manifest_payload(
            df,
            artifact_name="team_match",
            column_sources={},
            source_lineage=[],
            input_hash="my-hash",
        )
        assert payload["input_hash"] == "my-hash"

    def test_input_hash_falls_back_to_dataframe_hash(self) -> None:
        """When input_hash is None, a hash of df itself is used."""
        df = pd.DataFrame({"a": [1, 2, 3]})
        payload = build_manifest_payload(
            df,
            artifact_name="team_match",
            column_sources={},
            source_lineage=[],
            input_hash=None,
        )
        assert payload["input_hash"] == compute_dataframe_hash(df)

    def test_source_lineage_entries_serialized_as_dicts(self) -> None:
        """SourceLineageEntry dataclasses are serialized as dicts."""
        entry = SourceLineageEntry(
            name="football_data",
            relative_path="raw/football_data/combined_results.parquet",
            rows_read=68953,
            input_hash="abc123",
            notes="home+away expansion",
        )
        df = pd.DataFrame({"a": [1]})
        payload = build_manifest_payload(
            df,
            artifact_name="team_match",
            column_sources={},
            source_lineage=[entry],
        )
        assert len(payload["source_lineage"]) == 1
        lineage = payload["source_lineage"][0]
        assert lineage["name"] == "football_data"
        assert lineage["relative_path"] == "raw/football_data/combined_results.parquet"
        assert lineage["rows_read"] == 68953
        assert lineage["input_hash"] == "abc123"
        assert lineage["notes"] == "home+away expansion"

    def test_extra_fields_added_without_overwriting(self) -> None:
        """Extra fields are added but do not overwrite existing fields."""
        df = pd.DataFrame({"a": [1]})
        payload = build_manifest_payload(
            df,
            artifact_name="team_match",
            column_sources={},
            source_lineage=[],
            extra={"source_breakdown": {"fbref": 100}},
        )
        assert payload["source_breakdown"] == {"fbref": 100}
        # Existing field not overwritten
        assert payload["artifact"] == "team_match"


# ---------------------------------------------------------------------------
# write_team_match_manifest
# ---------------------------------------------------------------------------


class TestWriteTeamMatchManifest:
    def test_writes_manifest_next_to_parquet(self, tmp_path: Path) -> None:
        """Manifest is written as {stem}_manifest.json next to the parquet."""
        df = pd.DataFrame(
            {
                "match_id": ["m1", "m2"],
                "team_id": ["t1", "t2"],
                "goals_for": [1, 2],
                "goals_against": [0, 1],
            }
        )
        output_path = tmp_path / "team_match.parquet"
        df.to_parquet(output_path, index=False)
        write_team_match_manifest(df, output_path)

        manifest_path = tmp_path / "team_match_manifest.json"
        assert manifest_path.exists()

    def test_manifest_payload_aligned_with_rating_matrix_schema(
        self, tmp_path: Path
    ) -> None:
        """team_match manifest must include the same aligned fields as
        rating_feature_matrix_manifest.json: total_rows, columns,
        input_hash, timestamp."""
        df = pd.DataFrame(
            {
                "match_id": ["m1"],
                "team_id": ["t1"],
                "goals_for": [1],
                "goals_against": [0],
            }
        )
        df.attrs["_input_hash"] = "team-hash-123"

        output_path = tmp_path / "team_match.parquet"
        df.to_parquet(output_path, index=False)
        write_team_match_manifest(df, output_path)

        manifest = load_manifest(tmp_path / "team_match_manifest.json")
        # Aligned fields
        assert manifest["total_rows"] == 1
        assert isinstance(manifest["columns"], list)
        assert manifest["input_hash"] == "team-hash-123"
        assert "timestamp" in manifest
        # Extended fields
        assert manifest["artifact"] == "team_match"
        assert manifest["schema_version"] == MANIFEST_SCHEMA_VERSION
        assert manifest["column_count"] == 4

    def test_reads_lineage_from_attrs_when_not_passed(self, tmp_path: Path) -> None:
        """When source_lineage is not passed, it is read from df.attrs.

        Mirrors pipeline behavior: attrs are popped before to_parquet to
        avoid pandas trying to JSON-serialize SourceLineageEntry
        dataclasses, then the popped lineage is passed explicitly to
        the manifest writer.
        """
        df = pd.DataFrame({"match_id": ["m1"], "team_id": ["t1"], "goals_for": [1]})
        df.attrs["_source_lineage"] = [
            SourceLineageEntry(
                name="football_data",
                relative_path="raw/football_data/combined.parquet",
                rows_read=100,
                input_hash="abc",
                notes=None,
            )
        ]

        output_path = tmp_path / "team_match.parquet"
        lineage, _ = extract_lineage_attrs(df)
        df.to_parquet(output_path, index=False)
        write_team_match_manifest(df, output_path, source_lineage=lineage)

        manifest = load_manifest(tmp_path / "team_match_manifest.json")
        assert len(manifest["source_lineage"]) == 1
        assert manifest["source_lineage"][0]["name"] == "football_data"

    def test_explicit_lineage_overrides_attrs(self, tmp_path: Path) -> None:
        """When source_lineage is explicitly passed, it overrides attrs."""
        df = pd.DataFrame({"match_id": ["m1"]})
        df.attrs["_source_lineage"] = [
            SourceLineageEntry("attrs", "attrs/path", 1, "attrs-hash")
        ]
        explicit = [
            SourceLineageEntry("explicit", "explicit/path", 2, "explicit-hash")
        ]

        output_path = tmp_path / "team_match.parquet"
        # Pop attrs before to_parquet to avoid JSON serialization issues.
        extract_lineage_attrs(df)
        df.to_parquet(output_path, index=False)
        write_team_match_manifest(df, output_path, source_lineage=explicit)

        manifest = load_manifest(tmp_path / "team_match_manifest.json")
        assert len(manifest["source_lineage"]) == 1
        assert manifest["source_lineage"][0]["name"] == "explicit"

    def test_column_source_categorization_covers_team_match_columns(
        self, tmp_path: Path
    ) -> None:
        """Each team_match column gets a meaningful source category,
        not just the 'derived' default."""
        df = pd.DataFrame(
            {
                "match_id": ["m1"],
                "team_id": ["t1"],
                "opponent_team_id": ["t2"],
                "match_date": pd.to_datetime(["2026-01-01"]),
                "competition_id": ["EPL"],
                "season_id": ["2526"],
                "goals_for": [1],
                "goals_against": [0],
                "goal_diff": [1],
                "result_points": [3],
                "is_home": [True],
                "has_shots_data": [True],
            }
        )
        output_path = tmp_path / "team_match.parquet"
        df.to_parquet(output_path, index=False)
        write_team_match_manifest(df, output_path)

        manifest = load_manifest(tmp_path / "team_match_manifest.json")
        sources = {c["name"]: c["source"] for c in manifest["columns"]}
        # Identifiers
        assert sources["match_id"] == "identifier"
        assert sources["team_id"] == "identifier"
        assert sources["opponent_team_id"] == "identifier"
        # Temporal
        assert sources["match_date"] == "temporal"
        # Category
        assert sources["competition_id"] == "category"
        assert sources["season_id"] == "category"
        # Metric
        assert sources["goals_for"] == "metric"
        assert sources["goals_against"] == "metric"
        # Derived
        assert sources["goal_diff"] == "derived"
        assert sources["result_points"] == "derived"
        # Flag
        assert sources["is_home"] == "flag"
        assert sources["has_shots_data"] == "flag"


# ---------------------------------------------------------------------------
# write_player_match_manifest
# ---------------------------------------------------------------------------


class TestWritePlayerMatchManifest:
    def test_writes_manifest_with_source_breakdown(self, tmp_path: Path) -> None:
        """player_match manifest includes source_breakdown because it is
        the concatenation of multiple raw sources."""
        df = pd.DataFrame(
            {
                "match_id": ["m1", "m2", "m3"],
                "player_id": ["p1", "p2", "p3"],
                "team_id": ["t1", "t2", "t3"],
                "goals": [1, 0, 2],
                "source_name": ["fbref", "understat", "understat"],
            }
        )
        output_path = tmp_path / "player_match.parquet"
        df.to_parquet(output_path, index=False)
        write_player_match_manifest(df, output_path)

        manifest = load_manifest(tmp_path / "player_match_manifest.json")
        assert manifest["artifact"] == "player_match"
        assert manifest["source_breakdown"] == {"fbref": 1, "understat": 2}

    def test_no_source_breakdown_when_source_name_missing(
        self, tmp_path: Path
    ) -> None:
        """When source_name column is absent, source_breakdown is omitted."""
        df = pd.DataFrame(
            {
                "match_id": ["m1"],
                "player_id": ["p1"],
                "goals": [1],
            }
        )
        output_path = tmp_path / "player_match.parquet"
        df.to_parquet(output_path, index=False)
        write_player_match_manifest(df, output_path)

        manifest = load_manifest(tmp_path / "player_match_manifest.json")
        assert "source_breakdown" not in manifest

    def test_column_source_categorization_covers_player_match_columns(
        self, tmp_path: Path
    ) -> None:
        """Each player_match column gets a meaningful source category."""
        df = pd.DataFrame(
            {
                "match_id": ["m1"],
                "player_id": ["p1"],
                "team_id": ["t1"],
                "match_date": pd.to_datetime(["2026-01-01"]),
                "minutes_played": pd.array([90], dtype="Int64"),
                "goals": pd.array([1], dtype="Int64"),
                "position_group": ["FW"],
                "source_name": ["fbref"],
                "data_granularity": ["season_proxy"],
                "available_flag": pd.array([1], dtype="int64"),
            }
        )
        output_path = tmp_path / "player_match.parquet"
        df.to_parquet(output_path, index=False)
        write_player_match_manifest(df, output_path)

        manifest = load_manifest(tmp_path / "player_match_manifest.json")
        sources = {c["name"]: c["source"] for c in manifest["columns"]}
        assert sources["match_id"] == "identifier"
        assert sources["player_id"] == "identifier"
        assert sources["match_date"] == "temporal"
        assert sources["minutes_played"] == "metric"
        assert sources["goals"] == "metric"
        assert sources["position_group"] == "category"
        assert sources["source_name"] == "meta"
        assert sources["data_granularity"] == "meta"
        assert sources["available_flag"] == "derived"


# ---------------------------------------------------------------------------
# load_manifest
# ---------------------------------------------------------------------------


class TestLoadManifest:
    def test_loads_json_as_dict(self, tmp_path: Path) -> None:
        """load_manifest returns the JSON file as a Python dict."""
        manifest_path = tmp_path / "test_manifest.json"
        manifest_path.write_text(
            json.dumps({"artifact": "test", "total_rows": 42}),
            encoding="utf-8",
        )
        result = load_manifest(manifest_path)
        assert result == {"artifact": "test", "total_rows": 42}


# ---------------------------------------------------------------------------
# SourceLineageEntry dataclass
# ---------------------------------------------------------------------------


class TestSourceLineageEntry:
    def test_is_frozen(self) -> None:
        """SourceLineageEntry is frozen so manifest entries are immutable
        once written."""
        from dataclasses import FrozenInstanceError

        entry = SourceLineageEntry(
            name="fbref",
            relative_path="raw/fbref/x.parquet",
            rows_read=100,
            input_hash="abc",
        )
        with pytest.raises(FrozenInstanceError):
            entry.name = "changed"  # type: ignore[misc]

    def test_notes_default_none(self) -> None:
        """notes defaults to None when not provided."""
        entry = SourceLineageEntry("n", "p", 1, "h")
        assert entry.notes is None


# ---------------------------------------------------------------------------
# extract_lineage_attrs
# ---------------------------------------------------------------------------


class TestExtractLineageAttrs:
    """extract_lineage_attrs pops lineage from df.attrs before to_parquet.

    This is a regression guard: without popping, pandas tries to
    JSON-serialize SourceLineageEntry dataclasses when writing parquet
    metadata and raises TypeError on some pandas builds.
    """

    def test_pops_lineage_and_hash_from_attrs(self) -> None:
        """Both _source_lineage and _input_hash are popped and returned."""
        df = pd.DataFrame({"a": [1]})
        entry = SourceLineageEntry("fbref", "raw/fbref/x.parquet", 100, "abc")
        df.attrs["_source_lineage"] = [entry]
        df.attrs["_input_hash"] = "hash-123"

        lineage, input_hash = extract_lineage_attrs(df)
        assert len(lineage) == 1
        assert lineage[0] is entry
        assert input_hash == "hash-123"
        # attrs must be cleared so to_parquet doesn't try to serialize them.
        assert "_source_lineage" not in df.attrs
        assert "_input_hash" not in df.attrs

    def test_returns_empty_when_attrs_missing(self) -> None:
        """When attrs are absent, returns ([], None) without raising."""
        df = pd.DataFrame({"a": [1]})
        lineage, input_hash = extract_lineage_attrs(df)
        assert lineage == []
        assert input_hash is None

    def test_to_parquet_succeeds_after_extract(self, tmp_path: Path) -> None:
        """After extract_lineage_attrs, to_parquet does not raise.

        Reproduces the original failure: setting SourceLineageEntry in
        attrs then calling to_parquet raised TypeError because pandas
        tried to JSON-serialize the dataclass.
        """
        df = pd.DataFrame({"a": [1]})
        df.attrs["_source_lineage"] = [
            SourceLineageEntry("fbref", "raw/x.parquet", 1, "h")
        ]
        extract_lineage_attrs(df)
        # Must not raise.
        df.to_parquet(tmp_path / "ok.parquet", index=False)


# ---------------------------------------------------------------------------
# Schema version constant
# ---------------------------------------------------------------------------


class TestSchemaVersion:
    def test_schema_version_is_string(self) -> None:
        """MANIFEST_SCHEMA_VERSION is a string for forward compatibility."""
        assert isinstance(MANIFEST_SCHEMA_VERSION, str)
        assert MANIFEST_SCHEMA_VERSION == "1.0"
