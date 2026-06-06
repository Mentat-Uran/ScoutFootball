import pytest

from scoutfootball.schemas import build_core_table_definitions


def test_core_table_definitions_cover_phase_two_contract() -> None:
    tables = build_core_table_definitions()

    names = {table.name for table in tables}
    assert {
        "competition",
        "season",
        "team",
        "player",
        "match",
        "team_match",
        "player_match",
        "event",
        "bridge_source_team",
        "bridge_source_player",
        "market_snapshot",
    }.issubset(names)


def test_table_definition_validate_columns_rejects_missing_required_columns() -> None:
    team_match = next(
        table for table in build_core_table_definitions() if table.name == "team_match"
    )

    with pytest.raises(ValueError, match="missing required columns"):
        team_match.validate_columns(("match_id", "team_id", "goals_for"))
