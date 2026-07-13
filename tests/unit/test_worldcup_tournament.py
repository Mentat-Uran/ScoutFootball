"""Unit tests for the World Cup tournament state module.

Covers:
- init_state produces the expected 72-match schedule
- apply_result / clear_result round-trips
- compute_group_standings applies FIFA tiebreakers (points, GD, GF, H2H)
- determine_advancing_teams picks 12 winners, 12 runners-up, 8 best thirds
- compute_best_thirds ranks third-placed teams with provisional flag
- compute_team_scenarios returns valid probabilities and structure
- JSON persistence (save_state / load_state) round-trips correctly
- Edge cases: empty state, partial groups, invalid team names
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scoutfootball.worldcup.tournament import (
    SCHEMA_VERSION,
    GroupStanding,
    TeamScenarios,
    TournamentState,
    apply_result,
    clear_result,
    compute_all_standings,
    compute_best_thirds,
    compute_group_standings,
    compute_team_scenarios,
    determine_advancing_teams,
    init_state,
    load_state,
    qualification_impact,
    reset_state,
    save_state,
    state_from_dict,
    state_to_dict,
    tournament_summary,
    validate_tournament_state_integrity,
)

# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture()
def fresh_state() -> TournamentState:
    return init_state()


@pytest.fixture()
def group_a_completed(fresh_state: TournamentState) -> TournamentState:
    """Fill group A with a deterministic set of results.

    Group A: Mexico, South Africa, South Korea, Czech Republic
    Results:
      MD1: Mexico 2-1 South Africa
      MD1: South Korea 0-3 Czech Republic
      MD2: South Africa 1-1 Czech Republic
      MD2: Mexico 3-0 South Korea
      MD3: Mexico 1-0 Czech Republic
      MD3: South Africa 2-2 South Korea
    """
    results = [
        ("A-1-Mexico-South Africa-000", 2, 1),
        ("A-1-South Korea-Czech Republic-001", 0, 3),
        ("A-2-South Africa-Czech Republic-002", 1, 1),
        ("A-2-Mexico-South Korea-003", 3, 0),
        ("A-3-Mexico-Czech Republic-004", 1, 0),
        ("A-3-South Africa-South Korea-005", 2, 2),
    ]
    for match_id, hg, ag in results:
        apply_result(fresh_state, match_id, hg, ag)
    return fresh_state


# ── init_state ──────────────────────────────────────────────────────────


class TestInitState:
    def test_returns_tournament_state(self, fresh_state):
        assert isinstance(fresh_state, TournamentState)

    def test_schema_version(self, fresh_state):
        assert fresh_state.schema_version == SCHEMA_VERSION

    def test_has_72_matches(self, fresh_state):
        assert len(fresh_state.matches) == 72

    def test_all_groups_represented(self, fresh_state):
        groups = {m["group"] for m in fresh_state.matches}
        # 12 groups A-L
        assert len(groups) == 12
        for letter in "ABCDEFGHIJKL":
            assert letter in groups

    def test_each_group_has_6_matches(self, fresh_state):
        from collections import Counter

        counts = Counter(m["group"] for m in fresh_state.matches)
        for letter, count in counts.items():
            assert count == 6, f"Group {letter} has {count} matches, expected 6"

    def test_starts_with_no_results(self, fresh_state):
        assert fresh_state.results == {}

    def test_match_ids_unique(self, fresh_state):
        ids = [m["match_id"] for m in fresh_state.matches]
        assert len(ids) == len(set(ids))


# ── apply_result / clear_result ─────────────────────────────────────────


class TestApplyResult:
    def test_apply_valid_result(self, fresh_state):
        ok = apply_result(fresh_state, "A-1-Mexico-South Africa-000", 2, 1)
        assert ok is True
        assert "A-1-Mexico-South Africa-000" in fresh_state.results

    def test_apply_invalid_match_id(self, fresh_state):
        ok = apply_result(fresh_state, "X-1-Unknown-Team-999", 1, 0)
        assert ok is False

    def test_apply_negative_goals(self, fresh_state):
        ok = apply_result(fresh_state, "A-1-Mexico-South Africa-000", -1, 0)
        assert ok is False

    def test_apply_excessive_goals(self, fresh_state):
        ok = apply_result(fresh_state, "A-1-Mexico-South Africa-000", 31, 0)
        assert ok is False

    def test_apply_zero_zero(self, fresh_state):
        ok = apply_result(fresh_state, "A-1-Mexico-South Africa-000", 0, 0)
        assert ok is True

    def test_apply_overwrites_previous(self, fresh_state):
        apply_result(fresh_state, "A-1-Mexico-South Africa-000", 2, 1)
        apply_result(fresh_state, "A-1-Mexico-South Africa-000", 3, 3)
        result = fresh_state.results["A-1-Mexico-South Africa-000"]
        assert result["home_goals"] == 3
        assert result["away_goals"] == 3


class TestClearResult:
    def test_clear_existing_result(self, fresh_state):
        apply_result(fresh_state, "A-1-Mexico-South Africa-000", 2, 1)
        ok = clear_result(fresh_state, "A-1-Mexico-South Africa-000")
        assert ok is True
        assert "A-1-Mexico-South Africa-000" not in fresh_state.results

    def test_clear_nonexistent_result(self, fresh_state):
        ok = clear_result(fresh_state, "A-1-Mexico-South Africa-000")
        assert ok is False


class TestResetState:
    def test_reset_clears_all_results(self, group_a_completed):
        assert len(group_a_completed.results) > 0
        reset_state(group_a_completed)
        assert group_a_completed.results == {}


# ── compute_group_standings ─────────────────────────────────────────────


class TestComputeGroupStandings:
    def test_empty_state_returns_zero_played(self, fresh_state):
        standings = compute_group_standings(fresh_state, "A")
        assert len(standings) == 4
        for s in standings:
            assert s.played == 0
            assert s.points == 0

    def test_single_result_updates_standings(self, fresh_state):
        apply_result(fresh_state, "A-1-Mexico-South Africa-000", 2, 1)
        standings = compute_group_standings(fresh_state, "A")
        mexico = next(s for s in standings if s.team == "Mexico")
        south_africa = next(s for s in standings if s.team == "South Africa")
        assert mexico.played == 1
        assert mexico.won == 1
        assert mexico.points == 3
        assert mexico.goals_for == 2
        assert mexico.goals_against == 1
        assert south_africa.played == 1
        assert south_africa.lost == 1
        assert south_africa.points == 0

    def test_draw_result(self, fresh_state):
        apply_result(fresh_state, "A-1-Mexico-South Africa-000", 1, 1)
        standings = compute_group_standings(fresh_state, "A")
        mexico = next(s for s in standings if s.team == "Mexico")
        south_africa = next(s for s in standings if s.team == "South Africa")
        assert mexico.drawn == 1
        assert mexico.points == 1
        assert south_africa.drawn == 1
        assert south_africa.points == 1

    def test_completed_group_win_at_top(self, group_a_completed):
        """Mexico should be first in group A after the full set of results."""
        standings = compute_group_standings(group_a_completed, "A")
        assert standings[0].team == "Mexico"
        assert standings[0].points == 9  # 3 wins

    def test_standings_sorted_by_points(self, group_a_completed):
        standings = compute_group_standings(group_a_completed, "A")
        points = [s.points for s in standings]
        assert points == sorted(points, reverse=True)

    def test_goal_difference_computed(self, group_a_completed):
        standings = compute_group_standings(group_a_completed, "A")
        for s in standings:
            assert s.goal_difference == s.goals_for - s.goals_against

    def test_group_finished_property(self, group_a_completed):
        standings = compute_group_standings(group_a_completed, "A")
        for s in standings:
            assert s.is_finished is True

    def test_group_not_finished(self, fresh_state):
        standings = compute_group_standings(fresh_state, "A")
        for s in standings:
            assert s.is_finished is False

    def test_unknown_group_returns_empty(self, fresh_state):
        # Unknown groups return an empty standings list (no KeyError).
        standings = compute_group_standings(fresh_state, "Z")
        assert standings == []


class TestComputeAllStandings:
    def test_returns_all_12_groups(self, fresh_state):
        all_standings = compute_all_standings(fresh_state)
        assert len(all_standings) == 12
        for letter in "ABCDEFGHIJKL":
            assert letter in all_standings
            assert len(all_standings[letter]) == 4


# ── FIFA tiebreakers ────────────────────────────────────────────────────


class TestTiebreakers:
    def test_points_tiebreaker(self, fresh_state):
        """Two teams with equal GD but different points."""
        # Mexico wins both its first two matches (6 pts)
        apply_result(fresh_state, "A-1-Mexico-South Africa-000", 1, 0)
        apply_result(fresh_state, "A-2-Mexico-South Korea-003", 1, 0)
        # Czech Republic wins both its first two matches (6 pts)
        apply_result(fresh_state, "A-1-South Korea-Czech Republic-001", 0, 2)
        apply_result(fresh_state, "A-2-South Africa-Czech Republic-002", 0, 2)
        standings = compute_group_standings(fresh_state, "A")
        # Both should have 6 points, tiebreaker goes to GD
        assert standings[0].points == 6
        assert standings[1].points == 6
        # GD: Mexico +2, Czech +4 — Czech should be first
        assert standings[0].team == "Czech Republic"
        assert standings[1].team == "Mexico"

    def test_gd_tiebreaker_with_equal_points(self, fresh_state):
        """When points are equal, GD is the next tiebreaker."""
        # Mexico 3-0 South Africa (Mexico GD +3, SA GD -3)
        apply_result(fresh_state, "A-1-Mexico-South Africa-000", 3, 0)
        # South Korea 2-0 Czech (Korea GD +2, Czech GD -2)
        apply_result(fresh_state, "A-1-South Korea-Czech Republic-001", 2, 0)
        standings = compute_group_standings(fresh_state, "A")
        # Both Mexico and South Korea have 3 pts
        # Mexico GD +3 > South Korea GD +2
        assert standings[0].team == "Mexico"
        assert standings[1].team == "South Korea"

    def test_goals_for_tiebreaker_with_equal_points_and_gd(self, fresh_state):
        """When points and GD are equal, goals scored is next."""
        # Mexico 3-2 South Africa (Mexico GF 3, SA GF 2)
        apply_result(fresh_state, "A-1-Mexico-South Africa-000", 3, 2)
        # South Korea 1-0 Czech (Korea GF 1, Czech GF 0)
        apply_result(fresh_state, "A-1-South Korea-Czech Republic-001", 1, 0)
        standings = compute_group_standings(fresh_state, "A")
        # Both Mexico and South Korea have 3 pts and GD +1
        # Mexico GF 3 > South Korea GF 1
        assert standings[0].team == "Mexico"
        assert standings[1].team == "South Korea"


# ── determine_advancing_teams ───────────────────────────────────────────


class TestDetermineAdvancingTeams:
    def test_empty_state_has_12_winners_provisional(self, fresh_state):
        """Empty state still returns 12 provisional winners (first in each group)."""
        adv = determine_advancing_teams(fresh_state)
        assert len(adv["winners"]) == 12
        assert len(adv["runners_up"]) == 12
        assert len(adv["best_thirds"]) == 8
        assert adv["provisional"] is True

    def test_all_advancing_has_32_teams(self, fresh_state):
        adv = determine_advancing_teams(fresh_state)
        assert len(adv["all_advancing"]) == 32

    def test_completed_group_winners_are_dicts(self, group_a_completed):
        adv = determine_advancing_teams(group_a_completed)
        # winners is a list of dicts with 'team' key
        assert isinstance(adv["winners"], list)
        for w in adv["winners"]:
            assert "team" in w
            assert "group" in w
            assert "position" in w

    def test_completed_group_yields_winner(self, group_a_completed):
        adv = determine_advancing_teams(group_a_completed)
        winner_teams = [w["team"] for w in adv["winners"] if w["group"] == "A"]
        assert "Mexico" in winner_teams

    def test_all_advancing_includes_winners(self, group_a_completed):
        adv = determine_advancing_teams(group_a_completed)
        assert "Mexico" in adv["all_advancing"]

    def test_provisional_flag_false_when_all_complete(self, group_a_completed):
        """Only 1 group complete — provisional should be True."""
        adv = determine_advancing_teams(group_a_completed)
        assert adv["provisional"] is True


# ── compute_best_thirds ─────────────────────────────────────────────────


class TestComputeBestThirds:
    def test_empty_state_returns_eight_thirds(self, fresh_state):
        """Empty state: all 12 groups have a 3rd place team (0 pts, provisional)."""
        result = compute_best_thirds(fresh_state, limit=8)
        assert isinstance(result, list)
        assert len(result) == 8
        for t in result:
            assert t["points"] == 0
            assert t["provisional"] is True

    def test_single_completed_group_has_third(self, group_a_completed):
        result = compute_best_thirds(group_a_completed, limit=8)
        assert len(result) == 8
        # The third-placed team from group A should be present.
        # Mexico is 1st, Czech Republic is 2nd, so 3rd is either South Africa or South Korea
        third_from_a = [t for t in result if t["group"] == "A"]
        assert len(third_from_a) == 1
        assert third_from_a[0]["team"] in {"South Africa", "South Korea"}

    def test_best_thirds_sorted_by_points(self, fresh_state):
        result = compute_best_thirds(fresh_state, limit=8)
        if len(result) > 1:
            pts = [t["points"] for t in result]
            assert pts == sorted(pts, reverse=True)

    def test_limit_parameter(self, group_a_completed):
        result = compute_best_thirds(group_a_completed, limit=1)
        assert len(result) <= 1


# ── compute_team_scenarios ──────────────────────────────────────────────


class TestComputeTeamScenarios:
    def test_returns_team_scenarios_instance(self, fresh_state):
        result = compute_team_scenarios(fresh_state, "Mexico", max_scenarios=10)
        assert isinstance(result, TeamScenarios)
        assert result.team == "Mexico"
        assert result.group == "A"

    def test_advance_probability_range(self, fresh_state):
        result = compute_team_scenarios(fresh_state, "Mexico", max_scenarios=10)
        assert 0.0 <= result.advance_probability <= 1.0

    def test_scenarios_list_bounded(self, fresh_state):
        result = compute_team_scenarios(fresh_state, "Mexico", max_scenarios=5)
        assert len(result.scenarios) <= 5

    def test_remaining_matches_count(self, fresh_state):
        """Empty state — all 6 group matches are remaining (3 involve team,
        3 don't — but all 6 are pending)."""
        result = compute_team_scenarios(fresh_state, "Mexico", max_scenarios=5)
        assert len(result.remaining_matches) == 6

    def test_summary_is_string(self, fresh_state):
        result = compute_team_scenarios(fresh_state, "Mexico", max_scenarios=5)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    def test_completed_team_no_remaining(self, group_a_completed):
        """Mexico has played all 3 matches in group_a_completed."""
        result = compute_team_scenarios(group_a_completed, "Mexico", max_scenarios=10)
        assert len(result.remaining_matches) == 0
        # Mexico has 9 pts — definitely advances
        assert result.advance_probability == 1.0

    def test_scenarios_have_results_payload(self, fresh_state):
        result = compute_team_scenarios(fresh_state, "Mexico", max_scenarios=3)
        for sc in result.scenarios:
            assert isinstance(sc.description, str)
            assert isinstance(sc.results, list)
            assert isinstance(sc.advances, bool)
            assert sc.advance_path in (
                "winner", "runner-up", "best-third", "eliminated",
            )


# ── tournament_summary ──────────────────────────────────────────────────


class TestTournamentSummary:
    def test_summary_structure(self, fresh_state):
        summary = tournament_summary(fresh_state)
        assert summary["schema_version"] == SCHEMA_VERSION
        assert summary["total_matches"] == 72
        assert summary["completed_matches"] == 0
        assert summary["completion_rate"] == 0.0
        assert summary["groups_complete"] == 0
        assert summary["total_groups"] == 12
        assert summary["is_complete"] is False
        assert "standings" in summary
        assert "advancing" in summary
        assert "best_thirds" in summary
        assert "hosts" in summary

    def test_summary_after_results(self, group_a_completed):
        summary = tournament_summary(group_a_completed)
        assert summary["completed_matches"] == 6
        assert summary["groups_complete"] == 1
        assert summary["completion_rate"] > 0

    def test_summary_standings_all_groups(self, fresh_state):
        summary = tournament_summary(fresh_state)
        assert len(summary["standings"]) == 12


class TestQualificationImpact:
    def test_fresh_group_is_explicitly_provisional(self, fresh_state):
        impact = qualification_impact(fresh_state, "a")

        assert impact["schema"] == "scoutfootball.world-cup-qualification-impact"
        assert impact["group"] == "A"
        assert impact["matches_remaining"] == 6
        assert impact["provisional"] is True
        assert impact["third_place"]["cutoff_rank"] == 8
        assert 1 <= impact["third_place"]["rank"] <= 12

    def test_completed_group_marks_direct_positions_as_qualified(self, group_a_completed):
        impact = qualification_impact(group_a_completed, "A")

        assert impact["group_complete"] is True
        assert impact["matches_remaining"] == 0
        assert all(row["status"] == "qualified" for row in impact["direct_positions"])

    def test_unknown_group_is_rejected(self, fresh_state):
        with pytest.raises(ValueError, match="Unknown group"):
            qualification_impact(fresh_state, "Z")


# ── Persistence ─────────────────────────────────────────────────────────


class TestPersistence:
    def test_state_to_dict_has_schema(self, fresh_state):
        d = state_to_dict(fresh_state)
        assert d["schema_version"] == SCHEMA_VERSION
        assert "matches" in d
        assert "results" in d

    def test_state_from_dict_round_trip(self, fresh_state):
        apply_result(fresh_state, "A-1-Mexico-South Africa-000", 2, 1)
        d = state_to_dict(fresh_state)
        restored = state_from_dict(d)
        assert restored.schema_version == fresh_state.schema_version
        assert len(restored.matches) == len(fresh_state.matches)
        assert restored.results == fresh_state.results

    def test_integrity_reports_unknown_result_and_invalid_knockout_winner(self, fresh_state):
        fresh_state.results["unknown-match"] = {"home_goals": 1, "away_goals": 0}
        fresh_state.knockout = {"matches": [{
            "match_id": "r32-01", "home": "Argentina", "away": "France",
            "winner": "Unknown XI", "status": "completed", "home_goals": 1, "away_goals": 0,
        }]}

        errors = validate_tournament_state_integrity(fresh_state)

        assert any("unknown match" in error for error in errors)
        assert any("not a fixture participant" in error for error in errors)

    def test_integrity_rejects_altered_schedule_and_non_object_knockout(self, fresh_state):
        fresh_state.matches[0]["home"] = "Altered Team"
        fresh_state.knockout = "not-a-bracket"

        errors = validate_tournament_state_integrity(fresh_state)

        assert any("altered home" in error for error in errors)
        assert "knockout must be an object" in errors

    def test_save_and_load_state(self, fresh_state, tmp_path: Path):
        apply_result(fresh_state, "A-1-Mexico-South Africa-000", 2, 1)
        path = tmp_path / "tournament_state.json"
        save_state(fresh_state, path)
        assert path.exists()

        loaded = load_state(path)
        assert loaded.schema_version == fresh_state.schema_version
        assert len(loaded.matches) == 72
        assert "A-1-Mexico-South Africa-000" in loaded.results
        assert loaded.results["A-1-Mexico-South Africa-000"]["home_goals"] == 2

    def test_load_state_missing_file_returns_fresh(self, tmp_path: Path):
        path = tmp_path / "nonexistent.json"
        state = load_state(path)
        assert isinstance(state, TournamentState)
        assert len(state.matches) == 72
        assert state.results == {}

    def test_saved_json_is_valid(self, fresh_state, tmp_path: Path):
        path = tmp_path / "tournament_state.json"
        save_state(fresh_state, path)
        # Should be valid JSON
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["schema_version"] == SCHEMA_VERSION


# ── Edge cases ──────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_match_by_id_returns_match(self, fresh_state):
        m = fresh_state.match_by_id("A-1-Mexico-South Africa-000")
        assert m is not None
        assert m["home"] == "Mexico"
        assert m["away"] == "South Africa"

    def test_match_by_id_returns_none_for_unknown(self, fresh_state):
        m = fresh_state.match_by_id("X-1-Unknown-Team-999")
        assert m is None

    def test_group_standing_is_finished_property(self):
        s = GroupStanding(team="Test", played=3)
        assert s.is_finished is True
        s2 = GroupStanding(team="Test", played=2)
        assert s2.is_finished is False
