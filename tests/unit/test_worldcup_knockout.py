"""Unit tests for the World Cup knockout bracket module."""

from __future__ import annotations

import pytest

from scoutfootball.worldcup.tournament import (
    KNOCKOUT_ROUNDS,
    apply_knockout_result,
    clear_knockout_result,
    generate_knockout_bracket,
    get_knockout_overview,
    init_state,
    reset_state,
    state_from_dict,
    state_to_dict,
)


@pytest.fixture
def fresh_state():
    return init_state()


@pytest.fixture
def state_with_bracket(fresh_state):
    fresh_state.knockout = generate_knockout_bracket(fresh_state)
    return fresh_state


class TestGenerateKnockoutBracket:
    def test_generates_31_matches(self, fresh_state):
        ko = generate_knockout_bracket(fresh_state)
        assert len(ko["matches"]) == 31

    def test_r32_has_16_matches(self, fresh_state):
        ko = generate_knockout_bracket(fresh_state)
        r32 = [m for m in ko["matches"] if m["round"] == "r32"]
        assert len(r32) == 16

    def test_r16_has_8_matches(self, fresh_state):
        ko = generate_knockout_bracket(fresh_state)
        r16 = [m for m in ko["matches"] if m["round"] == "r16"]
        assert len(r16) == 8

    def test_qf_has_4_matches(self, fresh_state):
        ko = generate_knockout_bracket(fresh_state)
        qf = [m for m in ko["matches"] if m["round"] == "qf"]
        assert len(qf) == 4

    def test_sf_has_2_matches(self, fresh_state):
        ko = generate_knockout_bracket(fresh_state)
        sf = [m for m in ko["matches"] if m["round"] == "sf"]
        assert len(sf) == 2

    def test_final_has_1_match(self, fresh_state):
        ko = generate_knockout_bracket(fresh_state)
        final = [m for m in ko["matches"] if m["round"] == "final"]
        assert len(final) == 1

    def test_provisional_when_group_stage_incomplete(self, fresh_state):
        ko = generate_knockout_bracket(fresh_state)
        assert ko["provisional"] is True

    def test_r32_teams_populated(self, fresh_state):
        ko = generate_knockout_bracket(fresh_state)
        r32 = [m for m in ko["matches"] if m["round"] == "r32"]
        for m in r32:
            assert m["home"] is not None
            assert m["away"] is not None

    def test_later_rounds_have_tbd_teams(self, fresh_state):
        ko = generate_knockout_bracket(fresh_state)
        r16 = [m for m in ko["matches"] if m["round"] == "r16"]
        for m in r16:
            assert m["home"] is None
            assert m["away"] is None

    def test_champion_is_none_initially(self, fresh_state):
        ko = generate_knockout_bracket(fresh_state)
        assert ko["champion"] is None


class TestApplyKnockoutResult:
    def test_home_win_advances_home(self, state_with_bracket):
        state = state_with_bracket
        m = state.knockout_match_by_id("r32-01")
        home = m["home"]
        apply_knockout_result(state, "r32-01", 2, 0)
        assert m["winner"] == home
        assert m["home_goals"] == 2
        assert m["away_goals"] == 0
        assert m["status"] == "completed"
        assert m["decided_by"] == "regular"

    def test_away_win_advances_away(self, state_with_bracket):
        state = state_with_bracket
        m = state.knockout_match_by_id("r32-01")
        away = m["away"]
        apply_knockout_result(state, "r32-01", 0, 3)
        assert m["winner"] == away

    def test_draw_requires_penalties_winner(self, state_with_bracket):
        state = state_with_bracket
        with pytest.raises(ValueError, match="penalties_winner"):
            apply_knockout_result(state, "r32-01", 1, 1)

    def test_draw_with_penalties(self, state_with_bracket):
        state = state_with_bracket
        m = state.knockout_match_by_id("r32-01")
        home = m["home"]
        apply_knockout_result(state, "r32-01", 1, 1, penalties_winner=home)
        assert m["winner"] == home
        assert m["decided_by"] == "penalties"
        assert m["penalties_winner"] == home

    def test_invalid_penalties_winner(self, state_with_bracket):
        state = state_with_bracket
        with pytest.raises(ValueError, match="penalties_winner"):
            apply_knockout_result(state, "r32-01", 1, 1, penalties_winner="InvalidTeam")

    def test_negative_goals_rejected(self, state_with_bracket):
        state = state_with_bracket
        with pytest.raises(ValueError, match="non-negative"):
            apply_knockout_result(state, "r32-01", -1, 0)

    def test_duplicate_result_rejected(self, state_with_bracket):
        state = state_with_bracket
        apply_knockout_result(state, "r32-01", 2, 0)
        with pytest.raises(ValueError, match="already has a result"):
            apply_knockout_result(state, "r32-01", 1, 0)

    def test_match_not_found(self, state_with_bracket):
        state = state_with_bracket
        with pytest.raises(ValueError, match="not found"):
            apply_knockout_result(state, "r99-01", 2, 0)

    def test_no_bracket_generated(self, fresh_state):
        with pytest.raises(ValueError, match="No knockout bracket"):
            apply_knockout_result(fresh_state, "r32-01", 2, 0)

    def test_winner_advances_to_next_round_home_slot(self, state_with_bracket):
        state = state_with_bracket
        m = state.knockout_match_by_id("r32-01")
        home = m["home"]
        apply_knockout_result(state, "r32-01", 2, 0)
        r16_01 = state.knockout_match_by_id("r16-01")
        assert r16_01["home"] == home
        assert r16_01["away"] is None

    def test_winner_advances_to_next_round_away_slot(self, state_with_bracket):
        state = state_with_bracket
        m = state.knockout_match_by_id("r32-02")
        away = m["away"]
        apply_knockout_result(state, "r32-02", 0, 1)
        r16_01 = state.knockout_match_by_id("r16-01")
        assert r16_01["away"] == away

    def test_not_ready_match_rejected(self, state_with_bracket):
        state = state_with_bracket
        # R16 matches have no teams yet
        with pytest.raises(ValueError, match="not ready"):
            apply_knockout_result(state, "r16-01", 2, 0)


class TestClearKnockoutResult:
    def test_clear_removes_result(self, state_with_bracket):
        state = state_with_bracket
        apply_knockout_result(state, "r32-01", 2, 0)
        clear_knockout_result(state, "r32-01")
        m = state.knockout_match_by_id("r32-01")
        assert m["winner"] is None
        assert m["home_goals"] is None
        assert m["status"] == "scheduled"

    def test_clear_cascades_downstream(self, state_with_bracket):
        state = state_with_bracket
        # Record R32-01 and R32-02, then R16-01
        apply_knockout_result(state, "r32-01", 2, 0)
        apply_knockout_result(state, "r32-02", 1, 0)
        r16_01 = state.knockout_match_by_id("r16-01")
        assert r16_01["home"] is not None
        assert r16_01["away"] is not None
        apply_knockout_result(state, "r16-01", 3, 1)

        # Now clear R32-01 — should cascade clear R16-01
        clear_knockout_result(state, "r32-01")
        r16_01 = state.knockout_match_by_id("r16-01")
        assert r16_01["home"] is None
        assert r16_01["winner"] is None
        # Away slot (from R32-02) should still be filled
        assert r16_01["away"] is not None

    def test_clear_no_result_rejected(self, state_with_bracket):
        state = state_with_bracket
        with pytest.raises(ValueError, match="no recorded result"):
            clear_knockout_result(state, "r32-01")

    def test_clear_final_clears_champion(self, state_with_bracket):
        state = state_with_bracket
        # Record all matches through to final
        for i in range(1, 17):
            mid = f"r32-{i:02d}"
            apply_knockout_result(state, mid, 1, 0)
        for i in range(1, 9):
            mid = f"r16-{i:02d}"
            apply_knockout_result(state, mid, 1, 0)
        for i in range(1, 5):
            mid = f"qf-{i:02d}"
            apply_knockout_result(state, mid, 1, 0)
        for i in range(1, 3):
            mid = f"sf-{i:02d}"
            apply_knockout_result(state, mid, 1, 0)
        apply_knockout_result(state, "final-01", 2, 1)
        assert state.knockout["champion"] is not None

        clear_knockout_result(state, "final-01")
        assert state.knockout.get("champion") is None


class TestFullBracketProgression:
    def test_full_tournament_crowns_champion(self, state_with_bracket):
        state = state_with_bracket
        # Record all 31 matches
        for code, _label, count in KNOCKOUT_ROUNDS:
            for i in range(1, count + 1):
                mid = f"{code}-{i:02d}" if code != "final" else "final-01"
                m = state.knockout_match_by_id(mid)
                if m["home"] is None or m["away"] is None:
                    # This match should have been auto-filled by prior results
                    continue
                apply_knockout_result(state, mid, 1, 0)

        assert state.knockout["champion"] is not None
        overview = get_knockout_overview(state)
        assert overview["completed_matches"] == 31

    def test_r16_fills_after_both_r32_winners(self, state_with_bracket):
        state = state_with_bracket
        apply_knockout_result(state, "r32-01", 2, 0)
        apply_knockout_result(state, "r32-02", 1, 0)
        r16_01 = state.knockout_match_by_id("r16-01")
        assert r16_01["home"] is not None
        assert r16_01["away"] is not None


class TestGetKnockoutOverview:
    def test_no_bracket_returns_not_generated(self, fresh_state):
        overview = get_knockout_overview(fresh_state)
        assert overview["generated"] is False

    def test_generated_bracket_overview(self, state_with_bracket):
        overview = get_knockout_overview(state_with_bracket)
        assert overview["generated"] is True
        assert overview["total_matches"] == 31
        assert overview["completed_matches"] == 0
        assert overview["current_round"] == "r32"
        assert overview["champion"] is None

    def test_current_round_advances(self, state_with_bracket):
        state = state_with_bracket
        # Complete all R32 matches
        for i in range(1, 17):
            mid = f"r32-{i:02d}"
            apply_knockout_result(state, mid, 1, 0)
        overview = get_knockout_overview(state)
        assert overview["current_round"] == "r16"

    def test_rounds_structure(self, state_with_bracket):
        overview = get_knockout_overview(state_with_bracket)
        rounds = overview["rounds"]
        assert "r32" in rounds
        assert "r16" in rounds
        assert "qf" in rounds
        assert "sf" in rounds
        assert "final" in rounds
        assert rounds["r32"]["label"] == "Round of 32"
        assert len(rounds["r32"]["matches"]) == 16


class TestPersistenceWithKnockout:
    def test_state_to_dict_includes_knockout(self, state_with_bracket):
        d = state_to_dict(state_with_bracket)
        assert "knockout" in d
        assert d["knockout"]["generated"] is not False or "matches" in d["knockout"]

    def test_round_trip_preserves_knockout(self, state_with_bracket):
        state = state_with_bracket
        apply_knockout_result(state, "r32-01", 2, 0)
        d = state_to_dict(state)
        restored = state_from_dict(d)
        assert restored.knockout is not None
        assert len(restored.knockout.get("matches", [])) == 31
        m = restored.knockout_match_by_id("r32-01")
        assert m["winner"] is not None
        assert m["home_goals"] == 2

    def test_empty_knockout_round_trips(self, fresh_state):
        d = state_to_dict(fresh_state)
        restored = state_from_dict(d)
        assert restored.knockout == {}


class TestResetState:
    def test_reset_clears_knockout(self, state_with_bracket):
        state = state_with_bracket
        apply_knockout_result(state, "r32-01", 2, 0)
        reset_state(state)
        assert state.knockout == {}
        assert state.results == {}


class TestKnockoutMatchIds:
    def test_match_ids_are_unique(self, state_with_bracket):
        ids = [m["match_id"] for m in state_with_bracket.knockout["matches"]]
        assert len(ids) == len(set(ids))

    def test_match_id_format(self, state_with_bracket):
        for m in state_with_bracket.knockout["matches"]:
            assert m["match_id"].startswith(("r32-", "r16-", "qf-", "sf-", "final-"))

    def test_positions_are_sequential(self, state_with_bracket):
        for code, _label, count in KNOCKOUT_ROUNDS:
            matches = [m for m in state_with_bracket.knockout["matches"] if m["round"] == code]
            positions = [m["position"] for m in matches]
            assert positions == list(range(1, count + 1))
