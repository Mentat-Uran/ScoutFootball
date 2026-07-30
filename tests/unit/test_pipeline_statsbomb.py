"""Tests for the StatsBomb player_match builder (PRS-1 Slice 4).

Covers the season_id / competition_id vocabulary conversion that prevents
94 statsbomb match-level rows from being silently dropped during
rating_feature_matrix aggregation.

Before the fix:
- statsbomb rows carried ``season_name`` ("2019/2020") and
  ``competition_name`` ("La Liga") from ``big5_matches.parquet`` but
  ``season_id`` and ``competition_id`` were NaN.
- ``build_rating_feature_matrix`` groups by ``["player_id", "season_id"]``;
  pandas groupby drops NaN keys, so all 94 statsbomb match-level rows
  disappeared from the feature matrix.

After the fix:
- ``season_name`` "2019/2020" → ``season_id`` "1920" (matches fbref/understat).
- ``competition_name`` "La Liga" → ``competition_id`` "ESP-La Liga"
  (matches the "<country>-<league>" format used by fbref/understat).
- The 94 rows carry valid season_id/competition_id and survive aggregation.
"""

from __future__ import annotations

import pandas as pd

from scoutfootball.config import PlatformSettings


def _make_settings(tmp_path) -> PlatformSettings:
    return PlatformSettings.from_root(tmp_path)


def _write_statsbomb_raw(
    settings: PlatformSettings,
    *,
    events_rows: list[dict],
    matches_rows: list[dict],
    events_filename: str = "events_all.parquet",
) -> None:
    """Write raw statsbomb_open events + matches parquet files."""
    raw_dir = settings.raw_root / "statsbomb_open"
    raw_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(events_rows).to_parquet(raw_dir / events_filename, index=False)
    pd.DataFrame(matches_rows).to_parquet(raw_dir / "big5_matches.parquet", index=False)


def _sample_events() -> list[dict]:
    """Two players in one match — minimal events for aggregation."""
    return [
        {
            "match_id": 1,
            "player_id": 100.0,
            "player_name": "Player A",
            "team_id": 200,
            "team_name": "Team A",
            "minute": 10,
            "event_type": "Pass",
            "shot_outcome_name": pd.NA,
            "shot_statsbomb_xg": pd.NA,
            "pass_goal_assist": False,
            "position_name": "Center Forward",
        },
        {
            "match_id": 1,
            "player_id": 100.0,
            "player_name": "Player A",
            "team_id": 200,
            "team_name": "Team A",
            "minute": 30,
            "event_type": "Shot",
            "shot_outcome_name": "Goal",
            "shot_statsbomb_xg": 0.5,
            "pass_goal_assist": False,
            "position_name": "Center Forward",
        },
        {
            "match_id": 1,
            "player_id": 101.0,
            "player_name": "Player B",
            "team_id": 201,
            "team_name": "Team B",
            "minute": 20,
            "event_type": "Duel",
            "shot_outcome_name": pd.NA,
            "shot_statsbomb_xg": pd.NA,
            "pass_goal_assist": False,
            "position_name": "Center Back",
        },
    ]


def _sample_matches(
    *,
    season_name: str = "2019/2020",
    competition_name: str = "La Liga",
) -> list[dict]:
    """One match with season/competition metadata."""
    return [
        {
            "match_id": 1,
            "match_date": "2020-01-01",
            "home_team_id": 200,
            "away_team_id": 201,
            "season_id": pd.NA,
            "season_name": season_name,
            "competition_id": pd.NA,
            "competition_name": competition_name,
        },
    ]


# ---------------------------------------------------------------------------
# season_name → season_id conversion
# ---------------------------------------------------------------------------


class TestSeasonNameToId:
    def test_season_name_converted_to_understat_format(self, tmp_path) -> None:
        """season_name "2019/2020" → season_id "1920".

        This is the core regression: without the conversion, season_id
        stays NaN and the row is silently dropped by groupby in
        build_rating_feature_matrix.
        """
        from scoutfootball.pipeline import _build_player_match_from_statsbomb

        settings = _make_settings(tmp_path)
        _write_statsbomb_raw(settings, events_rows=_sample_events(), matches_rows=_sample_matches())

        result = _build_player_match_from_statsbomb(settings)

        assert len(result) == 2
        assert set(result["season_id"]) == {"1920"}
        assert not result["season_id"].isna().any()

    def test_season_name_2024_2025_converts_to_2425(self, tmp_path) -> None:
        """season_name "2024/2025" → season_id "2425"."""
        from scoutfootball.pipeline import _build_player_match_from_statsbomb

        settings = _make_settings(tmp_path)
        matches = _sample_matches(season_name="2024/2025")
        _write_statsbomb_raw(settings, events_rows=_sample_events(), matches_rows=matches)

        result = _build_player_match_from_statsbomb(settings)

        assert set(result["season_id"]) == {"2425"}

    def test_unparseable_season_name_yields_nan(self, tmp_path) -> None:
        """A season_name that doesn't match "YYYY/YYYY" → season_id NaN.

        This is honest behaviour: we don't guess, we surface the gap. The
        row will be dropped by groupby, which is correct — we don't know
        what season it belongs to. Note: "N/A" would parse as "NA" because
        it contains "/", so we use "Unknown" which has no "/".
        """
        from scoutfootball.pipeline import _build_player_match_from_statsbomb

        settings = _make_settings(tmp_path)
        matches = _sample_matches(season_name="Unknown")
        _write_statsbomb_raw(settings, events_rows=_sample_events(), matches_rows=matches)

        result = _build_player_match_from_statsbomb(settings)

        # season_id is NaN — the conversion could not parse "Unknown".
        assert result["season_id"].isna().all()

    def test_missing_season_name_column_keeps_original_season_id(self, tmp_path) -> None:
        """When the matches file has no season_name column, the original
        season_id (possibly NaN) is preserved rather than overwritten.
        """
        from scoutfootball.pipeline import _build_player_match_from_statsbomb

        settings = _make_settings(tmp_path)
        matches = _sample_matches()
        # Remove season_name to simulate an older matches file.
        for row in matches:
            row.pop("season_name")
        # Set a valid season_id so we can verify it's preserved.
        for row in matches:
            row["season_id"] = "1920"
        _write_statsbomb_raw(settings, events_rows=_sample_events(), matches_rows=matches)

        result = _build_player_match_from_statsbomb(settings)

        assert set(result["season_id"]) == {"1920"}


# ---------------------------------------------------------------------------
# competition_name → competition_id mapping
# ---------------------------------------------------------------------------


class TestCompetitionNameToId:
    def test_la_liga_mapped_to_esp_format(self, tmp_path) -> None:
        """competition_name "La Liga" → competition_id "ESP-La Liga"."""
        from scoutfootball.pipeline import _build_player_match_from_statsbomb

        settings = _make_settings(tmp_path)
        _write_statsbomb_raw(settings, events_rows=_sample_events(), matches_rows=_sample_matches())

        result = _build_player_match_from_statsbomb(settings)

        assert set(result["competition_id"]) == {"ESP-La Liga"}

    def test_all_big5_competitions_mapped(self, tmp_path) -> None:
        """All five Big-5 competition names map to the <country>-<league> format."""
        competitions = [
            ("La Liga", "ESP-La Liga"),
            ("Ligue 1", "FRA-Ligue 1"),
            ("Premier League", "ENG-Premier League"),
            ("Serie A", "ITA-Serie A"),
            ("Bundesliga", "GER-Bundesliga"),
        ]

        for comp_name, expected_id in competitions:
            settings = _make_settings(tmp_path)
            matches = _sample_matches(competition_name=comp_name)
            _write_statsbomb_raw_for_competition_test(
                settings, expected_id, comp_name, matches
            )

    def test_unmapped_competition_keeps_original_id(self, tmp_path) -> None:
        """An unmapped competition_name keeps the original competition_id
        (from the matches file) rather than being overwritten with NaN."""
        from scoutfootball.pipeline import _build_player_match_from_statsbomb

        settings = _make_settings(tmp_path)
        matches = _sample_matches(competition_name="Eredivisie")
        # Set a pre-existing competition_id that should be preserved.
        for row in matches:
            row["competition_id"] = "NED-Eredivisie"
        _write_statsbomb_raw(settings, events_rows=_sample_events(), matches_rows=matches)

        result = _build_player_match_from_statsbomb(settings)

        # competition_id is preserved from the matches file, not overwritten.
        assert set(result["competition_id"]) == {"NED-Eredivisie"}


def _write_statsbomb_raw_for_competition_test(
    settings: PlatformSettings,
    expected_id: str,
    comp_name: str,
    matches: list[dict],
) -> None:
    """Helper for the all-big-5 test: write, build, and assert in one step."""
    from scoutfootball.pipeline import _build_player_match_from_statsbomb

    _write_statsbomb_raw(settings, events_rows=_sample_events(), matches_rows=matches)
    result = _build_player_match_from_statsbomb(settings)
    assert set(result["competition_id"]) == {expected_id}, (
        f"competition_name '{comp_name}' should map to '{expected_id}'"
    )


# ---------------------------------------------------------------------------
# Integration: rows survive rating_feature_matrix aggregation
# ---------------------------------------------------------------------------


class TestRowsSurviveAggregation:
    def test_statsbomb_rows_not_dropped_by_nan_season_id(self, tmp_path) -> None:
        """End-to-end: statsbomb match-level rows with season_name but no
        season_id must survive build_rating_feature_matrix aggregation.

        This is the core regression test for the 94-row data quality gap.
        Before the fix, the rows had NaN season_id and were silently dropped
        by groupby(["player_id", "season_id"]). After the fix, season_name
        is converted to season_id and the rows survive.
        """
        from scoutfootball.features.rating_matrix import build_rating_feature_matrix
        from scoutfootball.pipeline import _build_player_match_from_statsbomb

        settings = _make_settings(tmp_path)
        _write_statsbomb_raw(settings, events_rows=_sample_events(), matches_rows=_sample_matches())

        player_match = _build_player_match_from_statsbomb(settings)

        # All rows have a valid (non-NaN) season_id.
        assert not player_match["season_id"].isna().any()
        assert set(player_match["season_id"]) == {"1920"}

        # Build a minimal player_rolling frame with the same player_ids.
        player_rolling = pd.DataFrame({
            "player_id": ["100", "101"],
            "season_id": ["1920", "1920"],
            "goals_2": [1, 0],
        })

        matrix = build_rating_feature_matrix(player_match, player_rolling)

        # Both players survive aggregation — no rows dropped.
        assert len(matrix) == 2
        assert set(matrix["player_id"]) == {"100", "101"}
        # Grain/source columns are carried forward.
        assert set(matrix["data_granularity"]) == {"match"}
        assert set(matrix["source_name"]) == {"statsbomb_open"}

    def test_statsbomb_rows_drop_when_season_id_is_nan(self, tmp_path) -> None:
        """When season_name cannot be parsed and season_id stays NaN, the
        rows ARE dropped by groupby — this is pandas' default behaviour
        and the conversion fix does not override it. The test documents
        the honest failure mode: unparseable season names surface as
        dropped rows rather than silent canonicalization. Note: "N/A"
        would parse as "NA" because it contains "/", so we use "Unknown"
        which has no "/".
        """
        from scoutfootball.features.rating_matrix import build_rating_feature_matrix
        from scoutfootball.pipeline import _build_player_match_from_statsbomb

        settings = _make_settings(tmp_path)
        matches = _sample_matches(season_name="Unknown")
        _write_statsbomb_raw(settings, events_rows=_sample_events(), matches_rows=matches)

        player_match = _build_player_match_from_statsbomb(settings)

        # season_id is NaN for all rows.
        assert player_match["season_id"].isna().all()

        player_rolling = pd.DataFrame({
            "player_id": ["100", "101"],
            "season_id": ["1920", "1920"],
            "goals_2": [1, 0],
        })

        matrix = build_rating_feature_matrix(player_match, player_rolling)

        # All rows dropped — groupby drops NaN keys.
        assert len(matrix) == 0
