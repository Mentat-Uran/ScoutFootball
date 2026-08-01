import json
from pathlib import Path
from urllib.error import URLError

import pytest

from scoutfootball.adapters.clubelo import fetch_elo_by_date
from scoutfootball.adapters.common import (
    CachedHttpClient,
    HttpResponse,
    SourceFetchError,
    SourceSchemaError,
)
from scoutfootball.adapters.football_data import download_csv
from scoutfootball.adapters.statsbomb_open import load_events, load_lineups, load_matches
from scoutfootball.config import PlatformSettings


class StaticTransport:
    def __init__(self, payloads: dict[str, bytes]) -> None:
        self.payloads = payloads
        self.calls: list[str] = []

    def __call__(
        self,
        url: str,
        timeout_seconds: float,
        headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        del timeout_seconds, headers
        self.calls.append(url)
        return HttpResponse(body=self.payloads[url], status_code=200)


class FlakyTransport:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.calls = 0

    def __call__(
        self,
        url: str,
        timeout_seconds: float,
        headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        del url, timeout_seconds, headers
        self.calls += 1
        if self.calls == 1:
            raise URLError("temporary network error")
        return HttpResponse(body=self.payload, status_code=200)


def test_statsbomb_loaders_flatten_json_and_use_cache(tmp_path: Path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    base_url = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
    transport = StaticTransport(
        {
            f"{base_url}/matches/43/106.json": json.dumps(
                [
                    {
                        "match_id": 3772072,
                        "match_date": "2023-08-10",
                        "home_team": {"home_team_id": 1, "home_team_name": "Alpha FC"},
                        "away_team": {"away_team_id": 2, "away_team_name": "Beta FC"},
                        "competition": {"competition_id": 43, "competition_name": "WSL"},
                        "season": {"season_id": 106, "season_name": "2023/2024"},
                    }
                ]
            ).encode("utf-8"),
            f"{base_url}/events/3772072.json": json.dumps(
                [
                    {
                        "id": "evt-1",
                        "period": 1,
                        "minute": 12,
                        "second": 3,
                        "type": {"name": "Pass"},
                        "team": {"id": 1, "name": "Alpha FC"},
                        "player": {"id": 10, "name": "A. Player"},
                        "location": [30.0, 40.0],
                        "pass": {"end_location": [50.0, 60.0], "height": {"name": "Ground Pass"}},
                    }
                ]
            ).encode("utf-8"),
            f"{base_url}/lineups/3772072.json": json.dumps(
                [
                    {
                        "team_id": 1,
                        "team_name": "Alpha FC",
                        "lineup": [{"player_id": 10, "player_name": "A. Player"}],
                    }
                ]
            ).encode("utf-8"),
        }
    )
    client = CachedHttpClient(settings=settings, transport=transport, retry_delay_seconds=0.0)

    matches_result = load_matches(43, 106, client=client, settings=settings)
    events_result = load_events(3772072, client=client, settings=settings)
    lineups_result = load_lineups(3772072, client=client, settings=settings)

    assert matches_result.dataframe.loc[0, "home_team_id"] == 1
    assert matches_result.metadata.record_count == 1
    assert matches_result.metadata.request_log.cache_hit is False
    assert events_result.dataframe.loc[0, "event_type"] == "Pass"
    assert events_result.dataframe.loc[0, "location_x"] == 30.0
    assert events_result.dataframe.loc[0, "pass_end_location_y"] == 60.0
    assert lineups_result.dataframe.loc[0, "team_name"] == "Alpha FC"

    cached_matches = load_matches(43, 106, client=client, settings=settings)
    assert cached_matches.metadata.request_log.cache_hit is True
    assert transport.calls.count(f"{base_url}/matches/43/106.json") == 1


def test_statsbomb_schema_validation_raises_structured_error(tmp_path: Path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    base_url = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
    transport = StaticTransport(
        {
            f"{base_url}/matches/43/106.json": json.dumps([{"match_id": 1}]).encode("utf-8"),
        }
    )
    client = CachedHttpClient(settings=settings, transport=transport, retry_delay_seconds=0.0)

    with pytest.raises(SourceSchemaError, match="missing fields"):
        load_matches(43, 106, client=client, settings=settings)


def test_football_data_retries_then_uses_cache(tmp_path: Path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    payload = b"Div,Date,HomeTeam,AwayTeam,FTHG,FTAG\nE0,10/08/2025,Alpha FC,Beta FC,2,1\n"
    transport = FlakyTransport(payload)
    client = CachedHttpClient(settings=settings, transport=transport, retry_delay_seconds=0.0)

    result = download_csv("E0", "2526", client=client, settings=settings)
    cached_result = download_csv("E0", "2526", client=client, settings=settings)

    assert transport.calls == 2
    assert result.dataframe.loc[0, "HomeTeam"] == "Alpha FC"
    assert cached_result.metadata.request_log.cache_hit is True


def test_football_data_invalid_schema_raises_structured_error(tmp_path: Path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    transport = StaticTransport(
        {
            "https://www.football-data.co.uk/mmz4281/2526/E0.csv": (
                b"Date,HomeTeam\n2025-08-10,Alpha FC\n"
            )
        }
    )
    client = CachedHttpClient(settings=settings, transport=transport, retry_delay_seconds=0.0)

    with pytest.raises(SourceSchemaError, match="missing columns"):
        download_csv("E0", "2526", client=client, settings=settings)


def test_clubelo_parses_csv_and_fills_missing_club_names(tmp_path: Path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    payload = (
        b"Rank,Club,Country,Level,Elo,From,To\n"
        b"1,,ENG,1,1901,2026-05-01,2026-05-01\n"
        b"2,Beta FC,ESP,1,1880,2026-05-01,2026-05-01\n"
    )
    transport = StaticTransport({"http://api.clubelo.com/2026-05-01": payload})
    client = CachedHttpClient(settings=settings, transport=transport, retry_delay_seconds=0.0)

    result = fetch_elo_by_date("2026-05-01", client=client, settings=settings)

    assert bool(result.dataframe.loc[0, "missing_club_name"]) is True
    assert result.dataframe.loc[0, "Club"].startswith("__missing_club_")
    assert result.metadata.record_count == 2


def test_clubelo_validates_input_date_and_fetch_failures(tmp_path: Path) -> None:
    settings = PlatformSettings.from_root(tmp_path)
    client = CachedHttpClient(
        settings=settings,
        transport=FlakyTransport(b""),
        retry_delay_seconds=0.0,
        retry_attempts=1,
    )

    with pytest.raises(ValueError, match="ISO date string"):
        fetch_elo_by_date("2026/05/01", client=client, settings=settings)

    with pytest.raises(SourceFetchError, match="Failed to fetch"):
        fetch_elo_by_date("2026-05-01", client=client, settings=settings)
