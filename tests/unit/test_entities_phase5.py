from datetime import date

import pandas as pd

from scoutlab.entities import (
    match_players,
    match_teams,
    normalize_country_name,
    normalize_person_name,
    normalize_position_group,
    normalize_team_name,
)


def test_normalization_helpers_strip_accents_punctuation_and_suffixes() -> None:
    assert normalize_person_name("João Félix") == "joao felix"
    assert normalize_team_name("Paris Saint-Germain FC") == "paris saint germain"
    assert normalize_country_name("ENG") == "england"
    assert normalize_position_group("Attacking Midfielder") == "am"


def test_match_teams_builds_bridge_with_required_metadata() -> None:
    source = pd.DataFrame(
        [{"id": "src-1", "team_name": "Paris Saint-Germain FC", "country_name": "France"}],
    )
    canonical = pd.DataFrame(
        [{"team_id": "team-1", "team_name": "Paris Saint Germain", "country_name": "FRA"}],
    )

    result = match_teams(source, canonical, source_name="understat")

    assert result.bridges.loc[0, "team_id"] == "team-1"
    assert result.bridges.loc[0, "method"] == "deterministic_exact"
    assert result.bridges.loc[0, "score"] == 1.0
    assert result.bridges.loc[0, "approved_by"] == "system:auto"
    assert pd.notna(result.bridges.loc[0, "approved_at"])


def test_match_teams_does_not_auto_merge_similar_names_with_country_conflict() -> None:
    source = pd.DataFrame(
        [{"id": "src-1", "team_name": "United FC", "country_name": "England"}],
    )
    canonical = pd.DataFrame(
        [{"team_id": "team-1", "team_name": "United", "country_name": "Spain"}],
    )

    result = match_teams(source, canonical, source_name="fbref")

    assert result.bridges.empty
    assert result.rejected.loc[0, "reason"] == "country_conflict"


def test_match_players_matches_on_name_dob_and_nationality() -> None:
    source = pd.DataFrame(
        [
            {
                "id": "src-1",
                "player_name": "João Félix",
                "date_of_birth": date(1999, 11, 10),
                "nationality": "POR",
            }
        ],
    )
    canonical = pd.DataFrame(
        [
            {
                "player_id": "player-1",
                "player_name": "Joao Felix",
                "date_of_birth": date(1999, 11, 10),
                "nationality": "Portugal",
            }
        ],
    )

    result = match_players(source, canonical, source_name="statsbomb_open")

    assert result.bridges.loc[0, "player_id"] == "player-1"
    assert result.bridges.loc[0, "method"] == "deterministic_exact"
    assert result.review_queue.empty


def test_match_players_does_not_auto_merge_birthday_conflicts() -> None:
    source = pd.DataFrame(
        [
            {
                "id": "src-1",
                "player_name": "John Smith",
                "date_of_birth": date(2000, 1, 1),
                "nationality": "England",
            }
        ],
    )
    canonical = pd.DataFrame(
        [
            {
                "player_id": "player-1",
                "player_name": "John Smith",
                "date_of_birth": date(1999, 1, 1),
                "nationality": "England",
            }
        ],
    )

    result = match_players(source, canonical, source_name="understat")

    assert result.bridges.empty
    assert result.rejected.loc[0, "reason"] == "dob_conflict"


def test_match_players_falls_back_to_team_season_position_when_dob_missing() -> None:
    source = pd.DataFrame(
        [
            {
                "id": "src-1",
                "player_name": "A. Midfielder",
                "nationality": "Spain",
                "team_name": "Alpha FC",
                "season": "2025",
                "position_group": "Attacking Midfielder",
            }
        ],
    )
    canonical = pd.DataFrame(
        [
            {
                "player_id": "player-1",
                "player_name": "A Midfielder",
                "nationality": "Spain",
                "team_name": "Alpha",
                "season": "2025",
                "primary_position_group": "am",
            }
        ],
    )

    result = match_players(source, canonical, source_name="fbref")

    assert result.bridges.loc[0, "player_id"] == "player-1"
    assert result.bridges.loc[0, "method"] == "deterministic_team_season_position"


def test_match_players_sends_mid_confidence_name_matches_to_review() -> None:
    source = pd.DataFrame(
        [{"id": "src-1", "player_name": "John Smit", "nationality": "England"}],
    )
    canonical = pd.DataFrame(
        [{"player_id": "player-1", "player_name": "John Smith", "nationality": "England"}],
    )

    result = match_players(source, canonical, source_name="transfermarkt_manual")

    assert result.bridges.empty
    assert result.review_queue.loc[0, "reason"] == "fuzzy_review"
