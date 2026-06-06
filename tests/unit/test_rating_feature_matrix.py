"""Unit tests for rating feature matrix: missing fields, fallback, matrix, manifest."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scoutfootball.features.rating_matrix import (
    FIELD_GROUPS,
    build_rating_feature_matrix,
    compute_finishing_shrinkage,
    fill_missing_with_position_median,
    mark_missing_fields,
    write_feature_manifest,
)

# ---------------------------------------------------------------------------
# mark_missing_fields
# ---------------------------------------------------------------------------


class TestMarkMissingFields:
    def test_all_nan_marks_missing_true(self) -> None:
        """When all fields in a group are NaN, the group is marked missing."""
        df = pd.DataFrame({
            "tackles": [pd.NA, pd.NA],
            "interceptions": [pd.NA, pd.NA],
            "clearances": [pd.NA, pd.NA],
            "blocks": [pd.NA, pd.NA],
        })
        result = mark_missing_fields(df)
        assert result["defense_missing"].all()

    def test_some_data_marks_missing_false(self) -> None:
        """When any field in a group has data, the group is not marked missing."""
        df = pd.DataFrame({
            "tackles": [3, pd.NA],
            "interceptions": [pd.NA, pd.NA],
            "clearances": [pd.NA, pd.NA],
            "blocks": [pd.NA, pd.NA],
        })
        result = mark_missing_fields(df)
        assert result["defense_missing"].iloc[0] == False  # noqa: E712
        assert result["defense_missing"].iloc[1] == True  # noqa: E712

    def test_no_group_columns_marks_missing_true(self) -> None:
        """When no columns from a group exist, it is marked as missing."""
        df = pd.DataFrame({"goals": [1, 2]})
        result = mark_missing_fields(df)
        # possession group has no columns present
        assert result["possession_missing"].all()
        # goalkeeper group has no columns present
        assert result["goalkeeper_missing"].all()

    def test_multiple_groups_independent(self) -> None:
        """Each group is evaluated independently."""
        df = pd.DataFrame({
            "tackles": [5],
            "interceptions": [2],
            "clearances": [3],
            "blocks": [1],
            "touches": [pd.NA],
            "dribbles": [pd.NA],
            "dispossessed": [pd.NA],
        })
        result = mark_missing_fields(df)
        assert result["defense_missing"].iloc[0] == False  # noqa: E712
        assert result["possession_missing"].iloc[0] == True  # noqa: E712

    def test_empty_dataframe(self) -> None:
        """Empty DataFrame should not raise and should add missing columns."""
        df = pd.DataFrame()
        result = mark_missing_fields(df)
        for group_name in FIELD_GROUPS:
            assert f"{group_name}_missing" in result.columns


# ---------------------------------------------------------------------------
# fill_missing_with_position_median
# ---------------------------------------------------------------------------


class TestFillMissingWithPositionMedian:
    def test_fills_with_position_median_not_zero(self) -> None:
        """Missing fields should be filled with position-group median, not 0."""
        df = pd.DataFrame({
            "position_group": ["DF", "DF", "MF", "MF"],
            "tackles": [5.0, pd.NA, 2.0, pd.NA],
            "interceptions": [3.0, pd.NA, 1.0, pd.NA],
            "clearances": [4.0, pd.NA, pd.NA, pd.NA],
            "blocks": [1.0, pd.NA, pd.NA, pd.NA],
            "defense_missing": [False, True, False, True],
        })
        result = fill_missing_with_position_median(df)
        # Row 1 (DF, missing): tackles should be filled with DF median = 5.0
        assert result["tackles"].iloc[1] == 5.0
        # Row 3 (MF, missing): tackles should be filled with MF median = 2.0
        assert result["tackles"].iloc[3] == 2.0
        # Should NOT be 0
        assert result["tackles"].iloc[1] != 0
        assert result["tackles"].iloc[3] != 0

    def test_fallback_to_global_median_without_position(self) -> None:
        """Without position_group, fall back to global median."""
        df = pd.DataFrame({
            "touches": [100.0, pd.NA],
            "dribbles": [10.0, pd.NA],
            "dispossessed": [5.0, pd.NA],
            "possession_missing": [False, True],
        })
        result = fill_missing_with_position_median(df)
        # Global median of touches = 100.0
        assert result["touches"].iloc[1] == 100.0

    def test_does_not_fill_non_missing_rows(self) -> None:
        """Rows not marked as missing should not be filled."""
        df = pd.DataFrame({
            "position_group": ["DF", "DF"],
            "tackles": [5.0, pd.NA],
            "interceptions": [3.0, pd.NA],
            "clearances": [4.0, pd.NA],
            "blocks": [1.0, pd.NA],
            "defense_missing": [False, False],
        })
        result = fill_missing_with_position_median(df)
        # Row 1 is not marked missing, so NaN should remain
        assert pd.isna(result["tackles"].iloc[1])

    def test_custom_missing_cols(self) -> None:
        """Custom missing_cols mapping should be used when provided."""
        custom_groups = {"attack": ["goals", "shots"]}
        df = pd.DataFrame({
            "position_group": ["FW", "FW"],
            "goals": [10.0, pd.NA],
            "shots": [30.0, pd.NA],
            "attack_missing": [False, True],
        })
        result = fill_missing_with_position_median(df, missing_cols=custom_groups)
        assert result["goals"].iloc[1] == 10.0

    def test_empty_dataframe(self) -> None:
        """Empty DataFrame should not raise."""
        df = pd.DataFrame()
        result = fill_missing_with_position_median(df)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# build_rating_feature_matrix
# ---------------------------------------------------------------------------


class TestBuildRatingFeatureMatrix:
    def _sample_player_match(self) -> pd.DataFrame:
        return pd.DataFrame({
            "player_id": ["p1", "p1", "p2"],
            "player_name": ["Alice", "Alice", "Bob"],
            "team_id": ["t1", "t1", "t2"],
            "team_name": ["Team A", "Team A", "Team B"],
            "season_id": ["2024", "2024", "2024"],
            "competition_id": ["PL", "PL", "LL"],
            "position_group": ["FW", "FW", "MF"],
            "match_date": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-01-15"]),
            "match_id": ["m1", "m2", "m3"],
            "minutes_played": [90, 45, 90],
            "goals": [1, 0, 0],
            "assists": [0, 1, 1],
            "shots": [3, 1, 2],
            "shots_on_target": [1, 0, 1],
            "npxg": [0.5, 0.1, 0.2],
            "xa": [0.2, 0.3, 0.4],
            "starts": [1, 0, 1],
            "available_flag": [1, 1, 1],
            "tackles": [0, 1, 3],
            "passes": [30, 15, 50],
            "xT_added": [pd.NA, pd.NA, pd.NA],
            "source_name": ["fbref", "fbref", "statsbomb_open"],
        })

    def _sample_player_rolling(self) -> pd.DataFrame:
        return pd.DataFrame({
            "player_id": ["p1", "p2"],
            "season_id": ["2024", "2024"],
            "goals_2": [1, 0],
        })

    def test_matrix_has_expected_columns(self) -> None:
        """Feature matrix should have numeric, category, and marker columns."""
        pm = self._sample_player_match()
        pr = self._sample_player_rolling()
        matrix = build_rating_feature_matrix(pm, pr)

        # Numeric columns
        for col in ["goals", "assists", "shots", "minutes_played"]:
            assert col in matrix.columns, f"Missing numeric column: {col}"

        # Category columns
        assert "position_group" in matrix.columns

        # Missing markers
        for group_name in FIELD_GROUPS:
            assert f"{group_name}_missing" in matrix.columns

        # Source coverage
        source_cols = [c for c in matrix.columns if c.endswith("_source_covered")]
        assert len(source_cols) > 0

    def test_one_row_per_player_season(self) -> None:
        """Matrix should have one row per player-season."""
        pm = self._sample_player_match()
        pr = self._sample_player_rolling()
        matrix = build_rating_feature_matrix(pm, pr)
        # p1 has 2 matches in season 2024 -> 1 row; p2 has 1 match -> 1 row
        assert len(matrix) == 2

    def test_empty_input_returns_empty(self) -> None:
        """Empty player_match should return empty DataFrame."""
        pm = pd.DataFrame()
        pr = pd.DataFrame()
        matrix = build_rating_feature_matrix(pm, pr)
        assert matrix.empty

    def test_input_hash_stored_in_attrs(self) -> None:
        """Input hash should be stored in DataFrame attrs."""
        pm = self._sample_player_match()
        pr = self._sample_player_rolling()
        matrix = build_rating_feature_matrix(pm, pr)
        assert "_input_hash" in matrix.attrs
        assert len(matrix.attrs["_input_hash"]) > 0


# ---------------------------------------------------------------------------
# write_feature_manifest
# ---------------------------------------------------------------------------


class TestWriteFeatureManifest:
    def test_manifest_has_required_fields(self, tmp_path: Path) -> None:
        """Manifest JSON should contain total_rows, columns, input_hash, timestamp."""
        matrix = pd.DataFrame({
            "player_id": ["p1", "p2"],
            "goals": [5, 3],
            "position_group": ["FW", "MF"],
            "defense_missing": [True, False],
        })
        matrix.attrs["_input_hash"] = "abc123"

        output_path = tmp_path / "rating_feature_matrix.parquet"
        matrix.to_parquet(output_path, index=False)
        write_feature_manifest(matrix, output_path)

        manifest_path = tmp_path / "rating_feature_matrix_manifest.json"
        assert manifest_path.exists()

        with open(manifest_path) as f:
            manifest = json.load(f)

        assert "total_rows" in manifest
        assert manifest["total_rows"] == 2
        assert "columns" in manifest
        assert "input_hash" in manifest
        assert manifest["input_hash"] == "abc123"
        assert "timestamp" in manifest

    def test_manifest_columns_have_metadata(self, tmp_path: Path) -> None:
        """Each column entry should have name, dtype, source, missing_rate."""
        matrix = pd.DataFrame({
            "goals": [5, pd.NA],
            "defense_missing": [True, False],
        })
        matrix.attrs["_input_hash"] = "test"

        output_path = tmp_path / "rating_feature_matrix.parquet"
        matrix.to_parquet(output_path, index=False)
        write_feature_manifest(matrix, output_path)

        manifest_path = tmp_path / "rating_feature_matrix_manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)

        for col_info in manifest["columns"]:
            assert "name" in col_info
            assert "dtype" in col_info
            assert "source" in col_info
            assert "missing_rate" in col_info

    def test_manifest_missing_rate_accurate(self, tmp_path: Path) -> None:
        """Missing rate should reflect actual NaN proportion."""
        matrix = pd.DataFrame({
            "goals": [5, pd.NA, 3, pd.NA],
        })
        matrix.attrs["_input_hash"] = "test"

        output_path = tmp_path / "rating_feature_matrix.parquet"
        matrix.to_parquet(output_path, index=False)
        write_feature_manifest(matrix, output_path)

        manifest_path = tmp_path / "rating_feature_matrix_manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)

        goals_info = next(c for c in manifest["columns"] if c["name"] == "goals")
        assert goals_info["missing_rate"] == 0.5


# ---------------------------------------------------------------------------
# compute_finishing_shrinkage
# ---------------------------------------------------------------------------


class TestComputeFinishingShrinkage:
    def test_few_shots_shrinks_toward_zero(self) -> None:
        """Player with 3 shots, goals-xG=+1.0 → shrunk value close to 0."""
        df = pd.DataFrame({
            "goals": [4.0],
            "npxg": [3.0],
            "shots": [3],
        })
        result = compute_finishing_shrinkage(df)
        # raw = (4-3)/3 ≈ 0.333; shrunk = (3/(3+50)) * 0.333 ≈ 0.019
        assert result.iloc[0] < 0.05
        assert result.iloc[0] > 0  # still positive, not exactly 0

    def test_many_shots_preserves_signal(self) -> None:
        """Player with 100 shots, goals-xG=+5.0 → shrunk value close to raw."""
        df = pd.DataFrame({
            "goals": [25.0],
            "npxg": [20.0],
            "shots": [100],
        })
        result = compute_finishing_shrinkage(df)
        # raw = 5/100 = 0.05; shrunk = (100/150) * 0.05 ≈ 0.0333
        raw = 5.0 / 100
        assert result.iloc[0] > raw * 0.6  # at least 60% preserved

    def test_zero_shots_returns_zero(self) -> None:
        """Player with 0 shots → shrunk = 0."""
        df = pd.DataFrame({
            "goals": [0.0],
            "npxg": [0.0],
            "shots": [0],
        })
        result = compute_finishing_shrinkage(df)
        assert result.iloc[0] == 0.0

    def test_nan_goals_xg_returns_zero(self) -> None:
        """Player with NaN goals/xg → shrunk = 0."""
        df = pd.DataFrame({
            "goals": [pd.NA],
            "npxg": [pd.NA],
            "shots": [10],
        })
        result = compute_finishing_shrinkage(df)
        assert result.iloc[0] == 0.0

    def test_larger_k_more_shrinkage(self) -> None:
        """Larger K produces more shrinkage (shrunk value closer to 0)."""
        df = pd.DataFrame({
            "goals": [5.0],
            "npxg": [3.0],
            "shots": [10],
        })
        result_k50 = compute_finishing_shrinkage(df, shrinkage_k=50.0)
        result_k200 = compute_finishing_shrinkage(df, shrinkage_k=200.0)
        assert abs(result_k200.iloc[0]) < abs(result_k50.iloc[0])

    def test_custom_column_names(self) -> None:
        """Custom column names should be used instead of defaults."""
        df = pd.DataFrame({
            "g": [3.0],
            "x": [1.0],
            "s": [5],
        })
        result = compute_finishing_shrinkage(
            df, goals_col="g", xg_col="x", shots_col="s",
        )
        # raw = (3-1)/5 = 0.4; shrunk = (5/55) * 0.4 ≈ 0.0364
        assert result.iloc[0] > 0
        assert result.iloc[0] < 0.4

    def test_returns_same_index(self) -> None:
        """Output Series should have the same index as input DataFrame."""
        df = pd.DataFrame({
            "goals": [1.0, 2.0, 3.0],
            "npxg": [0.5, 1.5, 2.5],
            "shots": [5, 10, 15],
        })
        result = compute_finishing_shrinkage(df)
        assert list(result.index) == list(df.index)


# ---------------------------------------------------------------------------
# finishing columns in build_rating_feature_matrix
# ---------------------------------------------------------------------------


class TestFinishingInFeatureMatrix:
    def _sample_player_match(self) -> pd.DataFrame:
        return pd.DataFrame({
            "player_id": ["p1", "p1", "p2"],
            "player_name": ["Alice", "Alice", "Bob"],
            "team_id": ["t1", "t1", "t2"],
            "team_name": ["Team A", "Team A", "Team B"],
            "season_id": ["2024", "2024", "2024"],
            "competition_id": ["PL", "PL", "LL"],
            "position_group": ["FW", "FW", "MF"],
            "match_date": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-01-15"]),
            "match_id": ["m1", "m2", "m3"],
            "minutes_played": [90, 45, 90],
            "goals": [1, 0, 0],
            "assists": [0, 1, 1],
            "shots": [3, 1, 2],
            "shots_on_target": [1, 0, 1],
            "npxg": [0.5, 0.1, 0.2],
            "xa": [0.2, 0.3, 0.4],
            "starts": [1, 0, 1],
            "available_flag": [1, 1, 1],
            "tackles": [0, 1, 3],
            "passes": [30, 15, 50],
            "xT_added": [pd.NA, pd.NA, pd.NA],
            "source_name": ["fbref", "fbref", "statsbomb_open"],
        })

    def _sample_player_rolling(self) -> pd.DataFrame:
        return pd.DataFrame({
            "player_id": ["p1", "p2"],
            "season_id": ["2024", "2024"],
            "goals_2": [1, 0],
        })

    def test_finishing_columns_present(self) -> None:
        """Feature matrix should contain finishing_raw and finishing_shrunk."""
        pm = self._sample_player_match()
        pr = self._sample_player_rolling()
        matrix = build_rating_feature_matrix(pm, pr)
        assert "finishing_raw" in matrix.columns
        assert "finishing_shrunk" in matrix.columns

    def test_finishing_shrunk_less_than_raw(self) -> None:
        """Shrunk finishing should have smaller absolute value than raw."""
        pm = self._sample_player_match()
        pr = self._sample_player_rolling()
        matrix = build_rating_feature_matrix(pm, pr)
        # For any non-zero raw finishing, shrunk should be closer to 0
        non_zero = matrix["finishing_raw"] != 0
        if non_zero.any():
            assert (
                matrix.loc[non_zero, "finishing_shrunk"].abs()
                <= matrix.loc[non_zero, "finishing_raw"].abs()
            ).all()
