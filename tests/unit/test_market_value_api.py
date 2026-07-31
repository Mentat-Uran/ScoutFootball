"""Market value (身价) API contract tests.

Verifies the three market-value endpoints' service functions:

- ``get_market_value_summary`` — aggregate stats + top-10
- ``list_market_value_players`` — paginated player list with filters
- ``get_player_market_value_history`` — single-player history

Coverage areas:

1. **Fail-closed empty state**: when no Transfermarkt data is on disk,
   every endpoint returns ``status="no_data"`` with a ``source`` block
   listing the checked paths — never an empty 200 that masks missing data.
2. **Source attribution**: every populated response carries
   ``source.source_name``, ``source.source_uri``, ``source.license_boundary``,
   and ``source.currency`` so consumers cannot mistake subjective
   Transfermarkt estimates for market prices.
3. **player_name cleaning**: Transfermarkt profiles append ``(<id>)`` to
   display names; the API strips the suffix so responses carry bare names.
4. **Filters & pagination**: ``min_value_eur`` / ``max_value_eur`` /
   ``team`` / ``position`` / ``sort_by`` / ``sort_order`` / ``limit`` /
   ``offset`` behave as documented.
5. **History lookup**: exact match, substring fallback, not_found, and
   invalid player_name.

All tests use ``tmp_path`` + ``SimpleNamespace`` settings; no real data
dependencies.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

from scoutfootball.api import (
    get_market_value_summary,
    get_player_market_value_history,
    list_market_value_players,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_settings(tmp_path: Path) -> SimpleNamespace:
    """Build a fake settings object pointing at ``tmp_path``.

    ``api._load_market_value_frame`` reads ``settings.raw_root`` and
    ``settings.data_root``. The real ``PlatformSettings`` nests
    ``raw_root`` under ``data_root`` (``data/raw/...``), and the API
    builds ``source_uri`` via ``path.relative_to(settings.data_root)``;
    the test fixture mirrors that layout so relative_to does not raise.
    """
    data_root = tmp_path / "data"
    raw_root = data_root / "raw"
    raw_root.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(raw_root=raw_root, data_root=data_root)


def _write_manual_csvs(
    tmp_path: Path,
    *,
    profiles_rows: list[dict] | None = None,
    valuations_rows: list[dict] | None = None,
    valuations_filename: str = "player_market_value.csv",
) -> Path:
    """Write normalized two-CSV Transfermarkt manual data under tmp_path.

    Files land under ``tmp_path/data/raw/transfermarkt_manual/`` to match
    the real platform layout expected by ``api._load_market_value_frame``.
    """
    raw_root = tmp_path / "data" / "raw" / "transfermarkt_manual"
    raw_root.mkdir(parents=True, exist_ok=True)

    if profiles_rows is None:
        profiles_rows = [
            {
                "player_id": 1,
                "player_name": "Test Player One (1)",
                "current_club_name": "FC Alpha",
                "position": "Attack - Right Winger",
            },
            {
                "player_id": 2,
                "player_name": "Test Player Two (2)",
                "current_club_name": "FC Beta",
                "position": "Defender - Centre-Back",
            },
            {
                "player_id": 3,
                "player_name": "Duplicate Name (3)",
                "current_club_name": "FC Gamma",
                "position": "Midfield - Central",
            },
            {
                "player_id": 4,
                "player_name": "Duplicate Name (4)",
                "current_club_name": "FC Delta",
                "position": "Midfield - Defensive",
            },
        ]
    if valuations_rows is None:
        valuations_rows = [
            {"player_id": 1, "date_unix": "2024-01-01", "value": 10_000_000.0},
            {"player_id": 1, "date_unix": "2024-06-01", "value": 15_000_000.0},
            {"player_id": 2, "date_unix": "2024-01-01", "value": 5_000_000.0},
            {"player_id": 3, "date_unix": "2024-01-01", "value": 1_000_000.0},
            {"player_id": 4, "date_unix": "2024-01-01", "value": 2_000_000.0},
        ]

    pd.DataFrame(profiles_rows).to_csv(
        raw_root / "player_profiles.csv", index=False
    )
    pd.DataFrame(valuations_rows).to_csv(
        raw_root / valuations_filename, index=False
    )
    return raw_root


# ---------------------------------------------------------------------------
# 1. Fail-closed empty state
# ---------------------------------------------------------------------------


class TestMarketValueEmptyState:
    """When no Transfermarkt data is on disk, return honest empty state."""

    def test_summary_no_data_returns_no_data_status(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = get_market_value_summary()
        assert result["status"] == "no_data"
        assert result["source"]["source_name"] == "none"
        assert result["source"]["currency"] == "EUR"
        assert "license_boundary" in result["source"]
        assert "checked_paths" in result["source"]
        assert "evidence" in result
        assert "reason" in result["evidence"]

    def test_summary_no_data_lists_checked_paths(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = get_market_value_summary()
        checked = result["source"]["checked_paths"]
        # Must include the transfermarkt_datasets + transfermarkt_manual paths
        assert any("transfermarkt_datasets" in p for p in checked)
        assert any("transfermarkt_manual" in p for p in checked)
        assert any("player_profiles.csv" in p for p in checked)
        assert any("player_market_value.csv" in p for p in checked)

    def test_list_players_no_data_returns_empty_list(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = list_market_value_players()
        assert result["status"] == "no_data"
        assert result["count"] == 0
        assert result["players"] == []
        assert "source" in result

    def test_history_no_data_returns_empty_histories(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = get_player_market_value_history("Anyone")
        assert result["status"] == "no_data"
        assert result["histories"] == []
        assert result["player_name"] == "Anyone"


# ---------------------------------------------------------------------------
# 2. Source attribution on populated responses
# ---------------------------------------------------------------------------


class TestMarketValueSourceAttribution:
    """Every populated response must carry source attribution."""

    def test_summary_carries_source_name_and_uri(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = get_market_value_summary()
        assert result["status"] == "ok"
        assert result["source"]["source_name"] == "transfermarkt_manual"
        assert result["source"]["source_uri"].endswith("player_market_value.csv")
        assert result["source"]["currency"] == "EUR"
        assert "Personal local use only" in result["source"]["license_boundary"]
        assert "Transfermarkt" in result["source"]["license_boundary"]

    def test_list_players_carries_source_attribution(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = list_market_value_players(limit=2)
        assert result["status"] == "ok"
        assert result["source"]["source_name"] == "transfermarkt_manual"
        assert result["source"]["currency"] == "EUR"

    def test_history_carries_source_attribution(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = get_player_market_value_history("Test Player One")
        assert result["status"] == "ok"
        assert result["source"]["source_name"] == "transfermarkt_manual"


# ---------------------------------------------------------------------------
# 3. player_name cleaning (strip trailing "(<id>)" suffix)
# ---------------------------------------------------------------------------


class TestMarketValuePlayerNameCleaning:
    """Transfermarkt appends "(<id>)" to display names; API must strip it."""

    def test_summary_top_players_have_bare_names(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = get_market_value_summary()
        for player in result["top_players"]:
            name = player["player_name"] or ""
            # No trailing "(<digits>)" suffix should remain.
            assert not name.endswith(")")
            assert "(" not in name

    def test_list_players_names_have_no_id_suffix(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = list_market_value_players(limit=10)
        for player in result["players"]:
            name = player["player_name"] or ""
            assert "(" not in name, f"player_name still carries id suffix: {name!r}"

    def test_history_player_name_is_bare(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = get_player_market_value_history("Test Player One")
        for hist in result["histories"]:
            name = hist["player_name"] or ""
            assert "(" not in name


# ---------------------------------------------------------------------------
# 4. Summary content
# ---------------------------------------------------------------------------


class TestMarketValueSummaryContent:
    """Summary aggregates: total_players, distribution, top_players."""

    def test_summary_counts_distinct_players(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = get_market_value_summary()
        # 4 distinct player_ids in the fixture.
        assert result["total_players"] == 4
        # 5 valuation rows total.
        assert result["total_snapshots"] == 5

    def test_summary_distribution_sums_to_total_players(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = get_market_value_summary()
        dist = result["value_distribution_eur"]
        assert sum(dist.values()) == result["total_players"]
        # Bands are mutually exclusive and cover the full range.
        assert set(dist.keys()) == {"<1m", "1m-5m", "5m-20m", "20m-50m", ">=50m"}

    def test_summary_top_players_sorted_descending(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = get_market_value_summary()
        top = result["top_players"]
        values = [p["market_value_eur"] for p in top]
        assert values == sorted(values, reverse=True)

    def test_summary_top_player_is_latest_snapshot(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = get_market_value_summary()
        # Player 1 has two snapshots (10m, 15m); latest is 15m.
        top1 = result["top_players"][0]
        assert top1["player_name"] == "Test Player One"
        assert top1["market_value_eur"] == 15_000_000.0
        assert top1["snapshot_date"] == "2024-06-01"

    def test_summary_includes_date_range(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = get_market_value_summary()
        assert result["earliest_snapshot_date"] == "2024-01-01"
        assert result["latest_snapshot_date"] == "2024-06-01"


# ---------------------------------------------------------------------------
# 5. list_market_value_players filters & pagination
# ---------------------------------------------------------------------------


class TestMarketValueListFilters:
    """Filters: min/max value, team, position, sort, pagination."""

    def test_min_value_filter(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = list_market_value_players(min_value_eur=5_000_000)
        # Players with latest >= 5m: 1 (15m), 2 (5m) → 2 players.
        assert result["count"] == 2
        for p in result["players"]:
            assert p["market_value_eur"] >= 5_000_000

    def test_max_value_filter(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = list_market_value_players(max_value_eur=2_000_000)
        # Players with latest <= 2m: 3 (1m), 4 (2m) → 2 players.
        assert result["count"] == 2
        for p in result["players"]:
            assert p["market_value_eur"] <= 2_000_000

    def test_team_substring_filter_case_insensitive(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = list_market_value_players(team="alpha")
        assert result["count"] == 1
        assert result["players"][0]["team_name"] == "FC Alpha"

    def test_position_substring_filter(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = list_market_value_players(position="Midfield")
        # Players 3 and 4 have "Midfield" in position.
        assert result["count"] == 2

    def test_sort_by_player_name_ascending(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = list_market_value_players(
                sort_by="player_name", sort_order="asc"
            )
        names = [p["player_name"] for p in result["players"]]
        assert names == sorted(names)

    def test_pagination_limit_and_offset(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            page1 = list_market_value_players(limit=2, offset=0)
            page2 = list_market_value_players(limit=2, offset=2)
        assert page1["returned"] == 2
        assert page2["returned"] == 2
        assert page1["count"] == page2["count"] == 4
        page1_ids = {p["player_id"] for p in page1["players"]}
        page2_ids = {p["player_id"] for p in page2["players"]}
        assert page1_ids.isdisjoint(page2_ids)

    def test_empty_filter_result_returns_ok_with_zero(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = list_market_value_players(min_value_eur=1_000_000_000)
        assert result["status"] == "ok"
        assert result["count"] == 0
        assert result["players"] == []
        assert "filters_applied" in result

    def test_invalid_sort_by_falls_back_to_market_value(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = list_market_value_players(sort_by="not_a_field")
        assert result["sort"]["by"] == "market_value_eur"


# ---------------------------------------------------------------------------
# 6. get_player_market_value_history
# ---------------------------------------------------------------------------


class TestMarketValuePlayerHistory:
    """Single-player history: exact match, substring, not_found, invalid."""

    def test_exact_match_returns_history(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = get_player_market_value_history("Test Player One")
        assert result["status"] == "ok"
        assert result["matched_players"] == 1
        hist = result["histories"][0]
        assert hist["player_name"] == "Test Player One"
        assert hist["snapshot_count"] == 2
        assert hist["latest_market_value_eur"] == 15_000_000.0
        assert hist["first_snapshot_date"] == "2024-01-01"
        assert hist["latest_snapshot_date"] == "2024-06-01"

    def test_case_insensitive_match(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = get_player_market_value_history("test player one")
        assert result["status"] == "ok"
        assert result["matched_players"] == 1

    def test_substring_fallback(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = get_player_market_value_history("Two")
        assert result["status"] == "ok"
        assert result["matched_players"] == 1
        assert result["histories"][0]["player_name"] == "Test Player Two"

    def test_duplicate_name_returns_multiple_histories(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = get_player_market_value_history("Duplicate Name")
        assert result["status"] == "ok"
        assert result["matched_players"] == 2
        player_ids = {h["player_id"] for h in result["histories"]}
        assert player_ids == {"3", "4"}

    def test_not_found_returns_not_found_status(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = get_player_market_value_history("Nonexistent Player")
        assert result["status"] == "not_found"
        assert result["histories"] == []
        assert "evidence" in result
        assert "reason" in result["evidence"]

    def test_empty_player_name_returns_error(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = get_player_market_value_history("")
        assert result["status"] == "error"
        assert result["error"] == "invalid_player_name"

    def test_whitespace_player_name_returns_error(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = get_player_market_value_history("   ")
        assert result["status"] == "error"
        assert result["error"] == "invalid_player_name"

    def test_snapshots_sorted_ascending_by_date(self, tmp_path: Path) -> None:
        _write_manual_csvs(tmp_path)
        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = get_player_market_value_history("Test Player One")
        snapshots = result["histories"][0]["snapshots"]
        dates = [s["snapshot_date"] for s in snapshots]
        assert dates == sorted(dates)


# ---------------------------------------------------------------------------
# 7. player_latest_market_value.csv alternative filename
# ---------------------------------------------------------------------------


class TestMarketValueLatestSnapshotFile:
    """When player_latest_market_value.csv exists, prefer it over history."""

    def test_prefers_latest_file_when_both_exist(self, tmp_path: Path) -> None:
        # Write both files. The latest file has a more recent snapshot.
        _write_manual_csvs(
            tmp_path,
            valuations_rows=[
                {"player_id": 1, "date_unix": "2024-01-01", "value": 10_000_000.0},
            ],
            valuations_filename="player_market_value.csv",
        )
        raw_root = tmp_path / "data" / "raw" / "transfermarkt_manual"
        pd.DataFrame(
            [
                {"player_id": 1, "date_unix": "2025-01-01", "value": 25_000_000.0},
            ]
        ).to_csv(raw_root / "player_latest_market_value.csv", index=False)

        settings = _make_settings(tmp_path)
        with patch("scoutfootball.api._settings", return_value=settings):
            result = get_market_value_summary()
        assert result["status"] == "ok"
        assert result["source"]["source_uri"].endswith(
            "player_latest_market_value.csv"
        )
        # Latest file's snapshot (25m) should be reflected in top player.
        top1 = result["top_players"][0]
        assert top1["market_value_eur"] == 25_000_000.0


# ---------------------------------------------------------------------------
# 8. JSON-serializable
# ---------------------------------------------------------------------------


def test_summary_result_is_json_serializable(tmp_path: Path) -> None:
    import json

    _write_manual_csvs(tmp_path)
    settings = _make_settings(tmp_path)
    with patch("scoutfootball.api._settings", return_value=settings):
        result = get_market_value_summary()
    # Must not raise.
    json.dumps(result)


def test_list_players_result_is_json_serializable(tmp_path: Path) -> None:
    import json

    _write_manual_csvs(tmp_path)
    settings = _make_settings(tmp_path)
    with patch("scoutfootball.api._settings", return_value=settings):
        result = list_market_value_players(limit=2)
    json.dumps(result)


def test_history_result_is_json_serializable(tmp_path: Path) -> None:
    import json

    _write_manual_csvs(tmp_path)
    settings = _make_settings(tmp_path)
    with patch("scoutfootball.api._settings", return_value=settings):
        result = get_player_market_value_history("Test Player One")
    json.dumps(result)


# ---------------------------------------------------------------------------
# 9. latest_market_value.csv missing falls back to history
# ---------------------------------------------------------------------------


def test_summary_works_with_only_history_file(tmp_path: Path) -> None:
    """If only player_market_value.csv exists (no _latest_), use it."""
    _write_manual_csvs(
        tmp_path,
        valuations_rows=[
            {"player_id": 1, "date_unix": "2024-01-01", "value": 8_000_000.0},
            {"player_id": 2, "date_unix": "2024-01-01", "value": 3_000_000.0},
        ],
        valuations_filename="player_market_value.csv",
    )
    settings = _make_settings(tmp_path)
    with patch("scoutfootball.api._settings", return_value=settings):
        result = get_market_value_summary()
    assert result["status"] == "ok"
    assert result["source"]["source_uri"].endswith("player_market_value.csv")
    assert result["total_players"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
