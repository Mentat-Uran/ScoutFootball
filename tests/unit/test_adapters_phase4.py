import json
from pathlib import Path

import pandas as pd
import pytest

from scoutfootball.adapters.common import CachedHttpClient, HttpResponse, SourceSchemaError
from scoutfootball.adapters.fbref import FBREF_RATE_LIMIT_SECONDS, fetch_player_standard
from scoutfootball.adapters.fbref_soccerdata import (
    bundesliga_is_missing,
    merge_stat_frames,
    normalize_big5_combined_frame,
)
from scoutfootball.adapters.transfermarkt_manual import load_snapshot
from scoutfootball.adapters.understat import fetch_league_players
from scoutfootball.config import PlatformSettings
from scoutfootball.storage.duckdb_io import connect_duckdb


class HeaderAwareTransport:
    def __init__(self, payloads: dict[str, bytes]) -> None:
        self.payloads = payloads
        self.calls: list[tuple[str, dict[str, str] | None]] = []

    def __call__(
        self,
        url: str,
        timeout_seconds: float,
        headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        del timeout_seconds
        self.calls.append((url, headers))
        return HttpResponse(body=self.payloads[url], status_code=200)


def test_understat_fetch_league_players_parses_current_endpoint_shape(tmp_path: Path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    payload = json.dumps(
        {
            "teams": {},
            "dates": [],
            "players": [
                {
                    "id": "1",
                    "player_name": "A. Forward",
                    "team_title": "Alpha FC",
                    "games": "12",
                    "time": "900",
                    "goals": "8",
                    "assists": "3",
                    "npg": "7",
                    "xG": "6.7",
                    "xA": "2.1",
                    "npxG": "5.9",
                    "xGChain": "10.4",
                    "xGBuildup": "3.6",
                }
            ],
        }
    ).encode("utf-8")
    url = "https://understat.com/getLeagueData/EPL/2025"
    transport = HeaderAwareTransport({url: payload})
    client = CachedHttpClient(settings=settings, transport=transport, retry_delay_seconds=0.0)

    result = fetch_league_players("EPL", 2025, client=client, settings=settings)

    assert result.dataframe.loc[0, "player_name"] == "A. Forward"
    assert result.dataframe.loc[0, "xGBuildup"] == "3.6"
    assert result.metadata.record_count == 1
    assert transport.calls[0][1]["X-Requested-With"] == "XMLHttpRequest"


def test_understat_field_change_raises_structured_error(tmp_path: Path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    payload = json.dumps({"players": [{"id": "1", "player_name": "A. Forward"}]}).encode("utf-8")
    url = "https://understat.com/getLeagueData/EPL/2025"
    transport = HeaderAwareTransport({url: payload})
    client = CachedHttpClient(settings=settings, transport=transport, retry_delay_seconds=0.0)

    with pytest.raises(SourceSchemaError, match="missing fields"):
        fetch_league_players("EPL", 2025, client=client, settings=settings)


def test_fbref_fetch_player_standard_uses_low_frequency_cache_and_parses_table(
    tmp_path: Path,
) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    html = b"""
    <html><body>
    <!--
    <table id="stats_standard">
      <thead>
        <tr>
          <th>Rk</th><th>Player</th><th>Squad</th><th>Min</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>1</td><td>A. Forward</td><td>Alpha FC</td><td>900</td></tr>
        <tr><td>2</td><td>B. Midfielder</td><td>Beta FC</td><td>850</td></tr>
      </tbody>
    </table>
    -->
    </body></html>
    """
    url = "https://fbref.com/en/comps/9/2025-2026/stats/2025-2026-Premier-League-Stats"
    transport = HeaderAwareTransport({url: html})
    client = CachedHttpClient(
        settings=settings,
        transport=transport,
        rate_limit_seconds=0.0,
        retry_delay_seconds=0.0,
    )

    result = fetch_player_standard(
        ["ENG-Premier League"],
        [2025],
        client=client,
        settings=settings,
    )

    assert result.dataframe["Player"].tolist() == ["A. Forward", "B. Midfielder"]
    assert result.dataframe.loc[0, "league"] == "ENG-Premier League"
    assert "fbref/Premier-League/2025-2026/stats_standard.html" in str(
        result.metadata.cache_path,
    )
    assert FBREF_RATE_LIMIT_SECONDS == 6.5

    cached = fetch_player_standard(
        ["ENG-Premier League"],
        [2025],
        client=client,
        settings=settings,
    )
    assert cached.metadata.request_log.cache_hit is True
    assert len(transport.calls) == 1


def test_fbref_missing_table_raises_structured_error(tmp_path: Path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    url = "https://fbref.com/en/comps/9/2025-2026/stats/2025-2026-Premier-League-Stats"
    transport = HeaderAwareTransport({url: b"<html><body><p>no table</p></body></html>"})
    client = CachedHttpClient(
        settings=settings,
        transport=transport,
        rate_limit_seconds=0.0,
        retry_delay_seconds=0.0,
    )

    with pytest.raises(SourceSchemaError, match="standard stats table"):
        fetch_player_standard(["ENG-Premier League"], [2025], client=client, settings=settings)


def test_bundesliga_is_missing_detects_big5_gap() -> None:
    frame = pd.DataFrame({"minutes": [900, 850]})
    frame.index = pd.MultiIndex.from_tuples(
        [
            ("ENG-Premier League", "2223", "Alpha FC", "A. Forward"),
            ("ESP-La Liga", "2223", "Beta FC", "B. Midfielder"),
        ],
        names=["league", "season", "team", "player"],
    )

    assert bundesliga_is_missing(frame) is True


def test_normalize_big5_combined_frame_maps_nan_league_to_bundesliga() -> None:
    frame = pd.DataFrame({"minutes": [720]})
    frame.index = pd.MultiIndex.from_tuples(
        [
            (float("nan"), "2223", "Bayern Munich", "J. Musiala"),
        ],
        names=["league", "season", "team", "player"],
    )

    normalized = normalize_big5_combined_frame(frame)

    assert ("GER-Bundesliga", "2223", "Bayern Munich", "J. Musiala") in normalized.index
    assert bundesliga_is_missing(normalized) is False


def test_merge_stat_frames_appends_bundesliga_and_deduplicates_index() -> None:
    big5 = pd.DataFrame({"minutes": [900, 850]})
    big5.index = pd.MultiIndex.from_tuples(
        [
            ("ENG-Premier League", "2223", "Alpha FC", "A. Forward"),
            (float("nan"), "2223", "Gamma FC", "C. Defender"),
        ],
        names=["league", "season", "team", "player"],
    )
    bundesliga = pd.DataFrame({"minutes": [780, 780]})
    bundesliga.index = pd.MultiIndex.from_tuples(
        [
            ("GER-Bundesliga", "2223", "Gamma FC", "C. Defender"),
            ("ESP-La Liga", "2223", "Beta FC", "B. Midfielder"),
        ],
        names=["league", "season", "team", "player"],
    )

    combined = merge_stat_frames(big5, bundesliga)

    assert ("GER-Bundesliga", "2223", "Gamma FC", "C. Defender") in combined.index
    assert len(combined) == 3
    assert combined.loc[("ESP-La Liga", "2223", "Beta FC", "B. Midfielder"), "minutes"] == 780


def test_transfermarkt_manual_load_snapshot_from_csv_and_parquet(tmp_path: Path) -> None:
    csv_path = tmp_path / "tm_snapshot.csv"
    csv_path.write_text(
        "Player,Club,Date,Market Value,Contract expires,Transfer Fee\n"
        "A. Forward,Alpha FC,2026-05-31,€12.5m,2027-06-30,€8m\n",
        encoding="utf-8",
    )

    csv_result = load_snapshot(csv_path)

    assert csv_result.dataframe.loc[0, "player_name"] == "A. Forward"
    assert csv_result.dataframe.loc[0, "market_value"] == 12_500_000.0
    assert csv_result.dataframe.loc[0, "transfer_fee"] == 8_000_000.0
    assert csv_result.dataframe.loc[0, "data_source"] == "transfermarkt_manual"

    parquet_path = tmp_path / "tm_snapshot.parquet"
    parquet_frame = pd.DataFrame(
        [
            {
                "player_name": "B. Midfielder",
                "team_name": "Beta FC",
                "snapshot_date": "2026-05-31",
                "market_value_raw": "750k",
                "contract_end": "2026-12-31",
            }
        ]
    )
    connection = connect_duckdb()
    try:
        connection.register("parquet_frame", parquet_frame)
        connection.execute(f"COPY parquet_frame TO '{parquet_path}' (FORMAT PARQUET)")
    finally:
        connection.close()

    parquet_result = load_snapshot(parquet_path)

    assert parquet_result.dataframe.loc[0, "market_value"] == 750_000.0
    assert parquet_result.dataframe.loc[0, "team_name"] == "Beta FC"


def test_transfermarkt_manual_rejects_bad_schema_and_bad_extension(tmp_path: Path) -> None:
    bad_csv_path = tmp_path / "bad_snapshot.csv"
    bad_csv_path.write_text("Player,Club,Date\nA. Forward,Alpha FC,2026-05-31\n", encoding="utf-8")

    with pytest.raises(SourceSchemaError, match="missing columns"):
        load_snapshot(bad_csv_path)

    bad_extension_path = tmp_path / "snapshot.xlsx"
    bad_extension_path.write_text("not used", encoding="utf-8")

    with pytest.raises(ValueError, match=".csv or .parquet"):
        load_snapshot(bad_extension_path)
