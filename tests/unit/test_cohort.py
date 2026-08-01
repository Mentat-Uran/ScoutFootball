"""Unit tests for the cohort kernel (PRS-1 R-010).

Covers CohortDefinition serialisation and hashing, ExclusionReason enum
stability, compute_membership_hash order-independence, and preview_cohort
filter behaviour (competition, season, team, role, minutes, age, identity).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.cohort import (
    COHORT_SCHEMA,
    COHORT_SCHEMA_VERSION,
    CohortDefinition,
    CohortMember,
    ExclusionReason,
    compute_membership_hash,
    preview_cohort,
)
from scoutfootball.evaluation.role_system import RoleFamily

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _write_player_match(settings: PlatformSettings, df: pd.DataFrame) -> None:
    """Write a player_match.parquet for testing."""
    path = settings.gold_root / "feature_store" / "player_match.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def _make_player_match_df(rows: list[dict] | None = None) -> pd.DataFrame:
    """Build a player_match DataFrame with the columns cohort expects."""
    if rows is None:
        rows = [
            {
                "player_id": "understat|1",
                "player_name": "Player A",
                "team_id": "100",
                "team_name": "Team A",
                "season_id": "2425",
                "competition_id": "ESP-La Liga",
                "position_group": "CB",
                "minutes_played": 2000,
                "source_name": "understat",
                "data_granularity": "season_proxy",
                "born": 1995,
                "multi_team_season": False,
            },
            {
                "player_id": "understat|2",
                "player_name": "Player B",
                "team_id": "200",
                "team_name": "Team B",
                "season_id": "2425",
                "competition_id": "ENG-Premier League",
                "position_group": "MF",
                "minutes_played": 500,
                "source_name": "understat",
                "data_granularity": "season_proxy",
                "born": 2000,
                "multi_team_season": False,
            },
            {
                "player_id": "understat|3",
                "player_name": "Player C",
                "team_id": "100",
                "team_name": "Team A",
                "season_id": "2324",
                "competition_id": "ESP-La Liga",
                "position_group": "FW",
                "minutes_played": 1500,
                "source_name": "understat",
                "data_granularity": "season_proxy",
                "born": 1990,
                "multi_team_season": True,
            },
        ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# ExclusionReason enum
# ---------------------------------------------------------------------------


class TestExclusionReason:
    def test_all_reasons_have_stable_values(self) -> None:
        expected = {
            "competition_not_in_filter",
            "season_not_in_filter",
            "team_not_in_filter",
            "role_not_in_filter",
            "min_minutes_not_met",
            "age_out_of_range",
            "no_born_year",
            "unresolved_identity",
            "unknown_role",
            "missing_position_group",
        }
        actual = {r.value for r in ExclusionReason}
        assert actual == expected

    def test_enum_is_string(self) -> None:
        for reason in ExclusionReason:
            assert isinstance(reason.value, str)


# ---------------------------------------------------------------------------
# CohortDefinition
# ---------------------------------------------------------------------------


class TestCohortDefinitionToDict:
    def test_default_filters_omitted(self) -> None:
        d = CohortDefinition(name="test").to_dict()
        assert d == {"name": "test", "description": ""}

    def test_frozensets_as_sorted_lists(self) -> None:
        d = CohortDefinition(
            name="test",
            competition_ids=frozenset({"ESP-La Liga", "ENG-Premier League"}),
            season_ids=frozenset({"2425", "2324"}),
            role_families=frozenset({RoleFamily.CB, RoleFamily.DM}),
        ).to_dict()
        assert d["competition_ids"] == ["ENG-Premier League", "ESP-La Liga"]
        assert d["season_ids"] == ["2324", "2425"]
        assert d["role_families"] == ["CB", "DM"]

    def test_bool_filters_only_included_when_true(self) -> None:
        d_false = CohortDefinition(name="test").to_dict()
        assert "require_resolved_identity" not in d_false
        assert "require_known_role" not in d_false

        d_true = CohortDefinition(
            name="test",
            require_resolved_identity=True,
            require_known_role=True,
        ).to_dict()
        assert d_true["require_resolved_identity"] is True
        assert d_true["require_known_role"] is True

    def test_min_minutes_and_age(self) -> None:
        d = CohortDefinition(
            name="test", min_minutes=900, age_min=18, age_max=35
        ).to_dict()
        assert d["min_minutes"] == 900
        assert d["age_min"] == 18
        assert d["age_max"] == 35


class TestCohortDefinitionHash:
    def test_same_definition_same_hash(self) -> None:
        d1 = CohortDefinition(
            name="test",
            competition_ids=frozenset({"ESP-La Liga", "ENG-Premier League"}),
            season_ids=frozenset({"2425"}),
        )
        d2 = CohortDefinition(
            name="test",
            competition_ids=frozenset({"ENG-Premier League", "ESP-La Liga"}),
            season_ids=frozenset({"2425"}),
        )
        assert d1.cohort_hash() == d2.cohort_hash()

    def test_different_name_different_hash(self) -> None:
        d1 = CohortDefinition(name="cohort-a")
        d2 = CohortDefinition(name="cohort-b")
        assert d1.cohort_hash() != d2.cohort_hash()

    def test_different_filter_different_hash(self) -> None:
        d1 = CohortDefinition(name="test", min_minutes=900)
        d2 = CohortDefinition(name="test", min_minutes=1000)
        assert d1.cohort_hash() != d2.cohort_hash()

    def test_hash_is_16_hex_chars(self) -> None:
        h = CohortDefinition(name="test").cohort_hash()
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)

    def test_canonical_json_is_sorted(self) -> None:
        d = CohortDefinition(
            name="test",
            competition_ids=frozenset({"B", "A"}),
            season_ids=frozenset({"2", "1"}),
        )
        cj = d.to_canonical_json()
        parsed = json.loads(cj)
        assert parsed["competition_ids"] == ["A", "B"]
        assert parsed["season_ids"] == ["1", "2"]

    def test_frozen_dataclass_is_immutable(self) -> None:
        d = CohortDefinition(name="test")
        with pytest.raises((AttributeError, TypeError)):
            d.name = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# compute_membership_hash
# ---------------------------------------------------------------------------


class TestComputeMembershipHash:
    def test_empty_list(self) -> None:
        h = compute_membership_hash([])
        assert len(h) == 16

    def test_single_member(self) -> None:
        m = CohortMember(
            canonical_player_id="cid-1",
            player_name="P1",
            season_id="2425",
            competition_id="ESP-La Liga",
            team_id="100",
            team_name="Team A",
            role_family="CB",
            minutes_played=2000.0,
            source_name="understat",
            data_granularity="season_proxy",
            multi_team_season=False,
        )
        h = compute_membership_hash([m])
        assert len(h) == 16

    def test_order_independent(self) -> None:
        m1 = CohortMember(
            canonical_player_id="cid-1", player_name="P1", season_id="2425",
            competition_id="", team_id="", team_name="", role_family="CB",
            minutes_played=0.0, source_name="", data_granularity="",
            multi_team_season=False,
        )
        m2 = CohortMember(
            canonical_player_id="cid-2", player_name="P2", season_id="2425",
            competition_id="", team_id="", team_name="", role_family="CM",
            minutes_played=0.0, source_name="", data_granularity="",
            multi_team_season=False,
        )
        h1 = compute_membership_hash([m1, m2])
        h2 = compute_membership_hash([m2, m1])
        assert h1 == h2

    def test_different_members_different_hash(self) -> None:
        m1 = CohortMember(
            canonical_player_id="cid-1", player_name="P1", season_id="2425",
            competition_id="", team_id="", team_name="", role_family="CB",
            minutes_played=0.0, source_name="", data_granularity="",
            multi_team_season=False,
        )
        m2 = CohortMember(
            canonical_player_id="cid-2", player_name="P2", season_id="2425",
            competition_id="", team_id="", team_name="", role_family="CM",
            minutes_played=0.0, source_name="", data_granularity="",
            multi_team_season=False,
        )
        h1 = compute_membership_hash([m1])
        h2 = compute_membership_hash([m2])
        assert h1 != h2


# ---------------------------------------------------------------------------
# preview_cohort
# ---------------------------------------------------------------------------


class TestPreviewCohortFailClosed:
    def test_missing_player_match_returns_unavailable(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        definition = CohortDefinition(name="test")
        report = preview_cohort(definition, settings=settings)
        assert report["schema"] == COHORT_SCHEMA
        assert report["schema_version"] == COHORT_SCHEMA_VERSION
        assert report["status"] == "unavailable"
        assert "reason" in report["evidence"]
        assert report["cohort_hash"] == definition.cohort_hash()

    def test_empty_player_match_returns_unavailable(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_player_match(settings, pd.DataFrame({"player_id": []}))
        definition = CohortDefinition(name="test")
        report = preview_cohort(definition, settings=settings)
        assert report["status"] == "unavailable"
        assert "0 rows" in report["evidence"]["reason"] or "empty" in report["evidence"]["reason"]


class TestPreviewCohortNoFilters:
    def test_all_rows_included(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_player_match(settings, _make_player_match_df())
        definition = CohortDefinition(name="all-players")
        report = preview_cohort(definition, settings=settings)
        assert report["status"] == "ok"
        ev = report["evidence"]
        # 3 player-seasons (each player_id is unique)
        assert ev["total_candidate_rows"] == 3
        assert ev["included_rows"] == 3
        assert ev["excluded_rows"] == 0
        assert len(ev["members"]) == 3
        assert ev["by_exclusion_reason"] == {}

    def test_membership_hash_present(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_player_match(settings, _make_player_match_df())
        definition = CohortDefinition(name="all-players")
        report = preview_cohort(definition, settings=settings)
        assert "membership_hash" in report
        assert len(report["membership_hash"]) == 16

    def test_cohort_hash_matches_definition(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_player_match(settings, _make_player_match_df())
        definition = CohortDefinition(name="all-players", min_minutes=100)
        report = preview_cohort(definition, settings=settings)
        assert report["cohort_hash"] == definition.cohort_hash()


class TestPreviewCohortCompetitionFilter:
    def test_single_competition(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_player_match(settings, _make_player_match_df())
        definition = CohortDefinition(
            name="la-liga", competition_ids=frozenset({"ESP-La Liga"})
        )
        report = preview_cohort(definition, settings=settings)
        ev = report["evidence"]
        # Player A (ESP 2425) + Player C (ESP 2324) = 2 included
        assert ev["included_rows"] == 2
        assert ev["excluded_rows"] == 1
        assert ev["by_exclusion_reason"]["competition_not_in_filter"] == 1

    def test_empty_frozenset_matches_nothing(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_player_match(settings, _make_player_match_df())
        definition = CohortDefinition(
            name="empty-comp", competition_ids=frozenset()
        )
        report = preview_cohort(definition, settings=settings)
        ev = report["evidence"]
        assert ev["included_rows"] == 0
        assert ev["excluded_rows"] == 3


class TestPreviewCohortSeasonFilter:
    def test_single_season(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_player_match(settings, _make_player_match_df())
        definition = CohortDefinition(
            name="season-2425", season_ids=frozenset({"2425"})
        )
        report = preview_cohort(definition, settings=settings)
        ev = report["evidence"]
        # Player A + Player B = 2 included
        assert ev["included_rows"] == 2
        assert ev["excluded_rows"] == 1
        assert ev["by_exclusion_reason"]["season_not_in_filter"] == 1


class TestPreviewCohortTeamFilter:
    def test_single_team(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_player_match(settings, _make_player_match_df())
        definition = CohortDefinition(
            name="team-100", team_ids=frozenset({"100"})
        )
        report = preview_cohort(definition, settings=settings)
        ev = report["evidence"]
        # Player A (team 100, 2425) + Player C (team 100, 2324) = 2
        assert ev["included_rows"] == 2
        assert ev["excluded_rows"] == 1
        assert ev["by_exclusion_reason"]["team_not_in_filter"] == 1


class TestPreviewCohortRoleFilter:
    def test_single_role(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_player_match(settings, _make_player_match_df())
        definition = CohortDefinition(
            name="cbs", role_families=frozenset({RoleFamily.CB})
        )
        report = preview_cohort(definition, settings=settings)
        ev = report["evidence"]
        # Only Player A (CB) = 1
        assert ev["included_rows"] == 1
        # Player B (MF→CM) and Player C (FW→ST) excluded
        assert ev["by_exclusion_reason"]["role_not_in_filter"] == 2

    def test_coarse_label_excluded_by_fine_filter(self, tmp_path: Path) -> None:
        """A player with position_group=MF maps to CM; if role_families
        only includes DM, the row is excluded via role_not_in_filter."""
        settings = PlatformSettings.from_root(tmp_path)
        df = _make_player_match_df([
            {
                "player_id": "u|1", "player_name": "P1", "team_id": "1",
                "team_name": "T1", "season_id": "2425",
                "competition_id": "ESP-La Liga", "position_group": "MF",
                "minutes_played": 1000, "source_name": "understat",
                "data_granularity": "season_proxy", "born": 1995,
                "multi_team_season": False,
            },
        ])
        _write_player_match(settings, df)
        definition = CohortDefinition(
            name="dms-only", role_families=frozenset({RoleFamily.DM})
        )
        report = preview_cohort(definition, settings=settings)
        ev = report["evidence"]
        assert ev["included_rows"] == 0
        assert ev["by_exclusion_reason"]["role_not_in_filter"] == 1

    def test_unknown_role_excluded(self, tmp_path: Path) -> None:
        """A player with position_group=XYZ maps to UNKNOWN; role filter
        excludes via unknown_role."""
        settings = PlatformSettings.from_root(tmp_path)
        df = _make_player_match_df([
            {
                "player_id": "u|1", "player_name": "P1", "team_id": "1",
                "team_name": "T1", "season_id": "2425",
                "competition_id": "ESP-La Liga", "position_group": "XYZ",
                "minutes_played": 1000, "source_name": "understat",
                "data_granularity": "season_proxy", "born": 1995,
                "multi_team_season": False,
            },
        ])
        _write_player_match(settings, df)
        definition = CohortDefinition(
            name="known-roles", role_families=frozenset({RoleFamily.CB, RoleFamily.CM})
        )
        report = preview_cohort(definition, settings=settings)
        ev = report["evidence"]
        assert ev["included_rows"] == 0
        assert ev["by_exclusion_reason"]["unknown_role"] == 1

    def test_missing_position_group_excluded(self, tmp_path: Path) -> None:
        """A player with position_group=None is excluded via
        missing_position_group when role filter is active."""
        settings = PlatformSettings.from_root(tmp_path)
        df = _make_player_match_df([
            {
                "player_id": "u|1", "player_name": "P1", "team_id": "1",
                "team_name": "T1", "season_id": "2425",
                "competition_id": "ESP-La Liga", "position_group": None,
                "minutes_played": 1000, "source_name": "understat",
                "data_granularity": "season_proxy", "born": 1995,
                "multi_team_season": False,
            },
        ])
        _write_player_match(settings, df)
        definition = CohortDefinition(
            name="known-roles", role_families=frozenset({RoleFamily.CB})
        )
        report = preview_cohort(definition, settings=settings)
        ev = report["evidence"]
        assert ev["included_rows"] == 0
        assert ev["by_exclusion_reason"]["missing_position_group"] == 1


class TestPreviewCohortRequireKnownRole:
    def test_excludes_unknown_role(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        df = _make_player_match_df([
            {
                "player_id": "u|1", "player_name": "P1", "team_id": "1",
                "team_name": "T1", "season_id": "2425",
                "competition_id": "ESP-La Liga", "position_group": "CB",
                "minutes_played": 1000, "source_name": "understat",
                "data_granularity": "season_proxy", "born": 1995,
                "multi_team_season": False,
            },
            {
                "player_id": "u|2", "player_name": "P2", "team_id": "1",
                "team_name": "T1", "season_id": "2425",
                "competition_id": "ESP-La Liga", "position_group": "UNK",
                "minutes_played": 1000, "source_name": "understat",
                "data_granularity": "season_proxy", "born": 1995,
                "multi_team_season": False,
            },
        ])
        _write_player_match(settings, df)
        definition = CohortDefinition(name="known", require_known_role=True)
        report = preview_cohort(definition, settings=settings)
        ev = report["evidence"]
        assert ev["included_rows"] == 1
        assert ev["by_exclusion_reason"]["unknown_role"] == 1


class TestPreviewCohortMinMinutes:
    def test_excludes_below_threshold(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_player_match(settings, _make_player_match_df())
        definition = CohortDefinition(name="min-900", min_minutes=900)
        report = preview_cohort(definition, settings=settings)
        ev = report["evidence"]
        # Player A (2000) + Player C (1500) = 2; Player B (500) excluded
        assert ev["included_rows"] == 2
        assert ev["by_exclusion_reason"]["min_minutes_not_met"] == 1

    def test_boundary_inclusive(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_player_match(settings, _make_player_match_df())
        definition = CohortDefinition(name="min-500", min_minutes=500)
        report = preview_cohort(definition, settings=settings)
        ev = report["evidence"]
        # Player B (500) passes because 500 >= 500
        assert ev["included_rows"] == 3


class TestPreviewCohortAgeFilter:
    def test_age_min_excludes_young(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_player_match(settings, _make_player_match_df())
        # Season 2425 → start year 2024
        # Player A: 2024 - 1995 = 29
        # Player B: 2024 - 2000 = 24
        # Player C: season 2324 → 2023 - 1990 = 33
        definition = CohortDefinition(name="age-25+", age_min=25)
        report = preview_cohort(definition, settings=settings)
        ev = report["evidence"]
        # Player A (29) + Player C (33) = 2; Player B (24) excluded
        assert ev["included_rows"] == 2
        assert ev["by_exclusion_reason"]["age_out_of_range"] == 1

    def test_age_max_excludes_old(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_player_match(settings, _make_player_match_df())
        definition = CohortDefinition(name="age-30-", age_max=30)
        report = preview_cohort(definition, settings=settings)
        ev = report["evidence"]
        # Player A (29) + Player B (24) = 2; Player C (33) excluded
        assert ev["included_rows"] == 2
        assert ev["by_exclusion_reason"]["age_out_of_range"] == 1

    def test_missing_born_excluded(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        df = _make_player_match_df([
            {
                "player_id": "u|1", "player_name": "P1", "team_id": "1",
                "team_name": "T1", "season_id": "2425",
                "competition_id": "ESP-La Liga", "position_group": "CB",
                "minutes_played": 1000, "source_name": "understat",
                "data_granularity": "season_proxy", "born": None,
                "multi_team_season": False,
            },
        ])
        _write_player_match(settings, df)
        definition = CohortDefinition(name="age-filter", age_min=18)
        report = preview_cohort(definition, settings=settings)
        ev = report["evidence"]
        assert ev["included_rows"] == 0
        assert ev["by_exclusion_reason"]["no_born_year"] == 1

    def test_invalid_season_id_excluded(self, tmp_path: Path) -> None:
        """If season_id is not parseable (not 4 digits), age filter excludes
        via no_born_year."""
        settings = PlatformSettings.from_root(tmp_path)
        df = _make_player_match_df([
            {
                "player_id": "u|1", "player_name": "P1", "team_id": "1",
                "team_name": "T1", "season_id": "invalid",
                "competition_id": "ESP-La Liga", "position_group": "CB",
                "minutes_played": 1000, "source_name": "understat",
                "data_granularity": "season_proxy", "born": 1995,
                "multi_team_season": False,
            },
        ])
        _write_player_match(settings, df)
        definition = CohortDefinition(name="age-filter", age_min=18)
        report = preview_cohort(definition, settings=settings)
        ev = report["evidence"]
        assert ev["included_rows"] == 0
        assert ev["by_exclusion_reason"]["no_born_year"] == 1


class TestPreviewCohortRequireResolvedIdentity:
    def test_excludes_unresolved(self, tmp_path: Path) -> None:
        """With no registry, all rows are unresolved:<source>:<id>.
        require_resolved_identity=True excludes all of them."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_player_match(settings, _make_player_match_df())
        definition = CohortDefinition(
            name="resolved-only", require_resolved_identity=True
        )
        report = preview_cohort(definition, settings=settings)
        ev = report["evidence"]
        assert ev["included_rows"] == 0
        assert ev["by_exclusion_reason"]["unresolved_identity"] == 3


class TestPreviewCohortCombinedFilters:
    def test_first_match_wins(self, tmp_path: Path) -> None:
        """A row failing multiple filters is counted once under the first
        matching reason (filter order: competition -> season -> team ->
        role -> minutes -> age -> identity)."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_player_match(settings, _make_player_match_df())
        # Player B: ENG-Premier League, 2425, team 200, MF→CM, 500 min, age 24
        definition = CohortDefinition(
            name="multi-filter",
            competition_ids=frozenset({"ESP-La Liga"}),
            min_minutes=900,
            age_min=25,
        )
        report = preview_cohort(definition, settings=settings)
        ev = report["evidence"]
        # Player B fails competition first (ENG not in ESP)
        # Player A and C pass competition (both ESP)
        # Player A: 2000 min, age 29 → passes all
        # Player C: 1500 min, age 33 → passes all
        assert ev["included_rows"] == 2
        assert ev["by_exclusion_reason"]["competition_not_in_filter"] == 1
        # min_minutes and age are not counted for Player B because
        # competition already excluded it
        assert "min_minutes_not_met" not in ev["by_exclusion_reason"]
        assert "age_out_of_range" not in ev["by_exclusion_reason"]


class TestPreviewCohortExcludedSamples:
    def test_capped_at_20(self, tmp_path: Path) -> None:
        """excluded_samples should be capped at 20 rows."""
        settings = PlatformSettings.from_root(tmp_path)
        # 25 rows, all excluded by competition filter
        rows = [
            {
                "player_id": f"u|{i}",
                "player_name": f"P{i}",
                "team_id": str(i),
                "team_name": f"T{i}",
                "season_id": "2425",
                "competition_id": "FRA-Ligue 1",
                "position_group": "CB",
                "minutes_played": 1000,
                "source_name": "understat",
                "data_granularity": "season_proxy",
                "born": 1995,
                "multi_team_season": False,
            }
            for i in range(25)
        ]
        _write_player_match(settings, pd.DataFrame(rows))
        definition = CohortDefinition(
            name="esp-only", competition_ids=frozenset({"ESP-La Liga"})
        )
        report = preview_cohort(definition, settings=settings)
        ev = report["evidence"]
        assert ev["excluded_rows"] == 25
        assert ev["by_exclusion_reason"]["competition_not_in_filter"] == 25
        assert len(ev["excluded_samples"]) == 20

    def test_excluded_sample_has_required_fields(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_player_match(settings, _make_player_match_df())
        definition = CohortDefinition(
            name="esp-only", competition_ids=frozenset({"ESP-La Liga"})
        )
        report = preview_cohort(definition, settings=settings)
        ev = report["evidence"]
        if ev["excluded_samples"]:
            s = ev["excluded_samples"][0]
            assert "canonical_player_id" in s
            assert "player_name" in s
            assert "season_id" in s
            assert "exclusion_reason" in s
            assert "minutes_played" in s
            assert "role_family" in s


class TestPreviewCohortMembershipHashStability:
    def test_same_data_same_hash(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_player_match(settings, _make_player_match_df())
        definition = CohortDefinition(name="test")
        r1 = preview_cohort(definition, settings=settings)
        r2 = preview_cohort(definition, settings=settings)
        assert r1["membership_hash"] == r2["membership_hash"]

    def test_different_data_different_hash(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_player_match(settings, _make_player_match_df())
        definition = CohortDefinition(name="test")
        r1 = preview_cohort(definition, settings=settings)

        # Add a 4th player
        df = pd.concat([
            _make_player_match_df(),
            pd.DataFrame([{
                "player_id": "u|4", "player_name": "P4", "team_id": "400",
                "team_name": "T4", "season_id": "2425",
                "competition_id": "ESP-La Liga", "position_group": "GK",
                "minutes_played": 1800, "source_name": "understat",
                "data_granularity": "season_proxy", "born": 1998,
                "multi_team_season": False,
            }]),
        ], ignore_index=True)
        _write_player_match(settings, df)
        r2 = preview_cohort(definition, settings=settings)
        assert r1["membership_hash"] != r2["membership_hash"]


class TestPreviewCohortOutput:
    def test_limitations_non_empty(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_player_match(settings, _make_player_match_df())
        report = preview_cohort(CohortDefinition(name="t"), settings=settings)
        assert len(report["limitations"]) > 0

    def test_json_serializable(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_player_match(settings, _make_player_match_df())
        report = preview_cohort(CohortDefinition(name="t"), settings=settings)
        # Must not raise
        json.dumps(report, ensure_ascii=False)

    def test_member_has_required_fields(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_player_match(settings, _make_player_match_df())
        report = preview_cohort(CohortDefinition(name="t"), settings=settings)
        m = report["evidence"]["members"][0]
        assert "canonical_player_id" in m
        assert "player_name" in m
        assert "season_id" in m
        assert "competition_id" in m
        assert "team_id" in m
        assert "team_name" in m
        assert "role_family" in m
        assert "minutes_played" in m
        assert "source_name" in m
        assert "data_granularity" in m
        assert "multi_team_season" in m

    def test_definition_in_report(self, tmp_path: Path) -> None:
        settings = PlatformSettings.from_root(tmp_path)
        _write_player_match(settings, _make_player_match_df())
        definition = CohortDefinition(
            name="la-liga-cbs",
            description="La Liga center backs",
            competition_ids=frozenset({"ESP-La Liga"}),
            role_families=frozenset({RoleFamily.CB}),
            min_minutes=900,
        )
        report = preview_cohort(definition, settings=settings)
        assert report["definition"]["name"] == "la-liga-cbs"
        assert report["definition"]["description"] == "La Liga center backs"
        assert report["definition"]["competition_ids"] == ["ESP-La Liga"]
        assert report["definition"]["role_families"] == ["CB"]
        assert report["definition"]["min_minutes"] == 900


class TestPreviewCohortMultiTeamSeason:
    def test_multi_team_season_flagged(self, tmp_path: Path) -> None:
        """A player with multi_team_season=True should be flagged in the
        member output but not excluded (v1 does not split)."""
        settings = PlatformSettings.from_root(tmp_path)
        _write_player_match(settings, _make_player_match_df())
        definition = CohortDefinition(name="test")
        report = preview_cohort(definition, settings=settings)
        members = report["evidence"]["members"]
        # Player C has multi_team_season=True
        player_c = [m for m in members if m["player_name"] == "Player C"][0]
        assert player_c["multi_team_season"] is True
        # Players A and B have multi_team_season=False
        player_a = [m for m in members if m["player_name"] == "Player A"][0]
        assert player_a["multi_team_season"] is False


class TestSeasonStartYear:
    def test_valid_season_ids(self) -> None:
        from scoutfootball.evaluation.cohort import _season_start_year

        assert _season_start_year("2425") == 2024
        assert _season_start_year("1617") == 2016
        assert _season_start_year("2526") == 2025

    def test_invalid_season_ids(self) -> None:
        from scoutfootball.evaluation.cohort import _season_start_year

        assert _season_start_year("invalid") is None
        assert _season_start_year("12345") is None
        assert _season_start_year(None) is None
        assert _season_start_year(2425) is None  # not a string
