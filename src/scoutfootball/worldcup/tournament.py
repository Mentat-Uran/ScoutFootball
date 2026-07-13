"""Tournament state, group standings, and qualification scenarios for the
2026 FIFA World Cup.

This module is intentionally pure-Python and side-effect-free: it operates on
plain dictionaries and dataclasses and can be used from the CLI, the API
server, or the test suite. Persistence is handled by the caller via
:func:`load_state` / :func:`save_state`.

The 2026 World Cup format:

- 48 teams in 12 groups (A-L) of 4.
- Single round-robin group stage (3 matches per team, 6 per group, 72 total).
- Top 2 from each group + 8 best third-placed teams advance to Round of 32.
- Knockout rounds: R32 → R16 → QF → SF → Final.

Tiebreakers (FIFA regulations, applied in order):

1. Higher points.
2. Higher goal difference.
3. Higher goals scored.
4. Higher points in head-to-head matches among tied teams.
5. Higher goal difference in head-to-head matches among tied teams.
6. Higher goals scored in head-to-head matches among tied teams.
7. Lower fair-play points (not modelled here — requires disciplinary data).
8. Drawing of lots (not modelled here).

When fewer than all group matches are played, head-to-head tiebreakers only
apply when every tied team has played every other tied team.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC
from pathlib import Path
from typing import Any

from scoutfootball.worldcup.data import (
    GROUPS,
    HOSTS,
    TOURNAMENT_END,
    TOURNAMENT_START,
    Match,
    generate_group_stage_matches,
    get_team_group,
)

SCHEMA_VERSION = "1.0.0"
DEFAULT_STATE_PATH = "data/reports/worldcup/tournament_state.json"


# ── Data classes ─────────────────────────────────────────────────────────


@dataclass
class MatchResult:
    """A recorded result for a single group-stage match."""

    home_goals: int
    away_goals: int
    status: str = "completed"  # completed | scheduled | postponed


@dataclass
class GroupStanding:
    """A single team's standing within its group."""

    team: str
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    goals_for: int = 0
    goals_against: int = 0
    goal_difference: int = 0
    points: int = 0

    @property
    def is_finished(self) -> bool:
        return self.played >= 3


@dataclass
class QualificationScenario:
    """A single outcome permutation for a team's remaining fixtures."""

    description: str
    results: list[dict[str, Any]]
    final_position: int  # 1-4 within group
    advances: bool
    advance_path: str  # "winner" | "runner-up" | "best-third" | "eliminated"


@dataclass
class TeamScenarios:
    """All qualification scenarios for one team."""

    team: str
    group: str
    current_standing: dict[str, Any]
    remaining_matches: list[dict[str, Any]]
    advance_probability: float  # 0-1, fraction of scenarios where team advances
    scenarios: list[QualificationScenario]
    summary: str


@dataclass
class TournamentState:
    """The full tournament state container."""

    schema_version: str = SCHEMA_VERSION
    tournament_start: str = TOURNAMENT_START
    tournament_end: str = TOURNAMENT_END
    matches: list[dict[str, Any]] = field(default_factory=list)
    results: dict[str, dict[str, Any]] = field(default_factory=dict)
    knockout: dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    def match_by_id(self, match_id: str) -> dict[str, Any] | None:
        for m in self.matches:
            if m["match_id"] == match_id:
                return m
        return None

    def knockout_match_by_id(self, match_id: str) -> dict[str, Any] | None:
        for m in self.knockout.get("matches", []):
            if m.get("match_id") == match_id:
                return m
        return None


# ── Match ID helpers ─────────────────────────────────────────────────────


def _match_id(match: Match | dict[str, Any], index: int) -> str:
    """Build a stable match ID from group, matchday, home, away, index."""
    if isinstance(match, Match):
        group = match.group or "X"
        return f"{group}-{match.matchday}-{match.home}-{match.away}-{index:03d}"
    group = match.get("group") or "X"
    md = match.get("matchday", 0)
    home = match.get("home", "")
    away = match.get("away", "")
    return f"{group}-{md}-{home}-{away}-{index:03d}"


def init_state() -> TournamentState:
    """Create an empty tournament state from the official 2026 schedule."""
    schedule = generate_group_stage_matches()
    matches: list[dict[str, Any]] = []
    for i, m in enumerate(schedule):
        matches.append({
            "match_id": _match_id(m, i),
            "matchday": m.matchday,
            "date": m.date,
            "time_et": m.time_et,
            "home": m.home,
            "away": m.away,
            "venue": m.venue,
            "city": m.city,
            "group": m.group,
            "stage": m.stage,
        })
    return TournamentState(
        schema_version=SCHEMA_VERSION,
        tournament_start=TOURNAMENT_START,
        tournament_end=TOURNAMENT_END,
        matches=matches,
        results={},
        notes="",
    )


# ── Standings ────────────────────────────────────────────────────────────


def _match_completed(result: dict[str, Any] | None) -> bool:
    if not result:
        return False
    return result.get("status") == "completed" and "home_goals" in result and "away_goals" in result


def compute_group_standings(
    state: TournamentState,
    group: str,
) -> list[GroupStanding]:
    """Compute standings for a single group from recorded results.

    Tiebreakers applied in order: points, goal difference, goals scored,
    head-to-head points, head-to-head goal difference, head-to-head goals
    scored. Returns standings sorted best-to-worst.
    """
    teams = GROUPS.get(group, [])
    standings: dict[str, GroupStanding] = {t: GroupStanding(team=t) for t in teams}

    # Collect completed matches in this group
    group_matches: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for m in state.matches:
        if m.get("group") != group:
            continue
        result = state.results.get(m["match_id"])
        if not _match_completed(result):
            continue
        group_matches.append((m, result))

    # First pass: aggregate stats
    h2h: dict[tuple[str, str], dict[str, int]] = {}
    for m, result in group_matches:
        home = m["home"]
        away = m["away"]
        hg = int(result["home_goals"])
        ag = int(result["away_goals"])
        if home not in standings or away not in standings:
            continue
        standings[home].played += 1
        standings[away].played += 1
        standings[home].goals_for += hg
        standings[home].goals_against += ag
        standings[away].goals_for += ag
        standings[away].goals_against += hg
        if hg > ag:
            standings[home].won += 1
            standings[home].points += 3
            standings[away].lost += 1
        elif hg < ag:
            standings[away].won += 1
            standings[away].points += 3
            standings[home].lost += 1
        else:
            standings[home].drawn += 1
            standings[home].points += 1
            standings[away].drawn += 1
            standings[away].points += 1
        h2h[(home, away)] = {"gf": hg, "ga": ag}
        h2h[(away, home)] = {"gf": ag, "ga": hg}

    for s in standings.values():
        s.goal_difference = s.goals_for - s.goals_against

    # Sort with tiebreakers. We need a stable sort that applies H2H only when
    # every team in a tied group has played every other team in that group.
    team_list = list(standings.values())

    def h2h_available(tied_teams: list[str]) -> bool:
        if len(tied_teams) < 2:
            return False
        for i in range(len(tied_teams)):
            for j in range(len(tied_teams)):
                if i == j:
                    continue
                if (tied_teams[i], tied_teams[j]) not in h2h:
                    return False
        return True

    def h2h_stats(team: str, tied_teams: list[str]) -> tuple[int, int, int]:
        """Return (points, gd, gf) for team in H2H matches among tied teams."""
        pts = gd = gf = 0
        for other in tied_teams:
            if other == team:
                continue
            entry = h2h.get((team, other))
            if not entry:
                continue
            g_for = entry["gf"]
            g_against = entry["ga"]
            gf += g_for
            gd += g_for - g_against
            if g_for > g_against:
                pts += 3
            elif g_for == g_against:
                pts += 1
        return pts, gd, gf

    def sort_key(s: GroupStanding) -> tuple:
        # Default key: points, GD, GF, team name (stable tiebreaker)
        return (s.points, s.goal_difference, s.goals_for, 0, 0, 0, _team_sort_index(s.team))

    # Identify tied clusters and apply H2H within them when applicable
    sorted_default = sorted(team_list, key=sort_key, reverse=True)

    # Group teams by (points, GD, GF) clusters
    final_order: list[GroupStanding] = []
    i = 0
    while i < len(sorted_default):
        cluster = [sorted_default[i]]
        j = i + 1
        while j < len(sorted_default) and (
            sorted_default[j].points == cluster[0].points
            and sorted_default[j].goal_difference == cluster[0].goal_difference
            and sorted_default[j].goals_for == cluster[0].goals_for
        ):
            cluster.append(sorted_default[j])
            j += 1

        if len(cluster) > 1:
            tied_team_names = [c.team for c in cluster]
            if h2h_available(tied_team_names):
                # Re-sort this cluster by H2H stats. Capture tied_team_names
                # via default-arg binding to avoid late-binding closure bug.
                def h2h_sort_key(
                    s: GroupStanding,
                    _tied: list[str] = tied_team_names,
                ) -> tuple:
                    pts, gd, gf = h2h_stats(s.team, _tied)
                    return (pts, gd, gf, _team_sort_index(s.team))

                cluster_sorted = sorted(cluster, key=h2h_sort_key, reverse=True)
                final_order.extend(cluster_sorted)
            else:
                final_order.extend(cluster)
        else:
            final_order.extend(cluster)
        i = j

    return final_order


def _team_sort_index(team: str) -> int:
    """Stable secondary sort key — simply hash the team name to a small int."""
    return hash(team) % 1000


def compute_all_standings(state: TournamentState) -> dict[str, list[GroupStanding]]:
    """Compute standings for all 12 groups."""
    return {letter: compute_group_standings(state, letter) for letter in GROUPS}


# ── Best thirds ──────────────────────────────────────────────────────────


def compute_best_thirds(
    state: TournamentState,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Rank third-placed teams across all 12 groups, return top *limit*.

    Tiebreakers: points, GD, GF, group letter (alphabetical as final resort).
    Teams that have not yet finished 3rd (or whose group is incomplete) are
    still included if they currently sit in 3rd, but flagged as ``provisional``.
    """
    standings_all = compute_all_standings(state)
    thirds: list[dict[str, Any]] = []
    for letter, standings in standings_all.items():
        if len(standings) < 3:
            continue
        third = standings[2]
        # Provisional if the team hasn't completed all 3 group matches
        provisional = not third.is_finished
        thirds.append({
            "group": letter,
            "team": third.team,
            "played": third.played,
            "points": third.points,
            "goal_difference": third.goal_difference,
            "goals_for": third.goals_for,
            "goals_against": third.goals_against,
            "provisional": provisional,
        })
    thirds.sort(
        key=lambda x: (
            -x["points"],
            -x["goal_difference"],
            -x["goals_for"],
            x["group"],
            x["team"],
        )
    )
    return thirds[:limit]


# ── Advancing teams ──────────────────────────────────────────────────────


def determine_advancing_teams(
    state: TournamentState,
) -> dict[str, Any]:
    """Determine the 32 advancing teams from group stage results.

    Returns a dict with ``winners`` (12), ``runners_up`` (12),
    ``best_thirds`` (8), and ``all_advancing`` (32). When groups are
    incomplete, provisional results are used and flagged.
    """
    standings_all = compute_all_standings(state)
    winners: list[dict[str, Any]] = []
    runners_up: list[dict[str, Any]] = []
    for letter, standings in standings_all.items():
        if not standings:
            continue
        w = standings[0]
        winners.append(_standing_to_dict(w, letter, "winner"))
        if len(standings) >= 2:
            r = standings[1]
            runners_up.append(_standing_to_dict(r, letter, "runner-up"))

    best_thirds = compute_best_thirds(state, limit=8)

    return {
        "winners": winners,
        "runners_up": runners_up,
        "best_thirds": best_thirds,
        "all_advancing": (
            [w["team"] for w in winners]
            + [r["team"] for r in runners_up]
            + [t["team"] for t in best_thirds]
        ),
        "provisional": any(not _is_complete_group(state, g) for g in GROUPS),
    }


def qualification_impact(state: TournamentState, group: str) -> dict[str, Any]:
    """Explain the current local qualification picture for one group.

    This is a standings interpretation only.  It does not predict results or
    assert an official qualification decision while any group is incomplete.
    """
    letter = group.upper()
    if letter not in GROUPS:
        raise ValueError(f"Unknown group: {group!r}")
    standings = compute_group_standings(state, letter)
    all_thirds = compute_best_thirds(state, limit=12)
    third = all_thirds[[entry["group"] for entry in all_thirds].index(letter)]
    third_rank = next(
        index + 1 for index, entry in enumerate(all_thirds) if entry["group"] == letter
    )
    cutline = all_thirds[7] if len(all_thirds) >= 8 else None
    completed = sum(
        _match_completed(state.results.get(match["match_id"]))
        for match in state.matches if match.get("group") == letter
    )
    return {
        "schema": "scoutfootball.world-cup-qualification-impact",
        "version": "1.0.0",
        "group": letter,
        "group_complete": completed == 6,
        "matches_recorded": completed,
        "matches_remaining": max(0, 6 - completed),
        "direct_positions": [
            {"position": index + 1, "team": row.team, "status": (
                "qualified" if completed == 6 else "currently_direct"
            )}
            for index, row in enumerate(standings[:2])
        ],
        "third_place": {
            **third,
            "rank": third_rank,
            "cutoff_rank": 8,
            "currently_within_cutoff": third_rank <= 8,
        },
        "cutline": cutline,
        "provisional": completed != 6 or any(entry["provisional"] for entry in all_thirds),
        "limitations": [
            "Based only on locally recorded group results.",
            "Best-third ordering is provisional until every relevant group match is recorded.",
            "This is not an official qualification decision or a match prediction.",
        ],
    }


def _is_complete_group(state: TournamentState, group: str) -> bool:
    """Check if all 6 group-stage matches in this group have results."""
    count = 0
    for m in state.matches:
        if m.get("group") != group:
            continue
        if _match_completed(state.results.get(m["match_id"])):
            count += 1
    return count >= 6


def _standing_to_dict(s: GroupStanding, group: str, position: str) -> dict[str, Any]:
    return {
        "team": s.team,
        "group": group,
        "position": position,
        "played": s.played,
        "points": s.points,
        "goal_difference": s.goal_difference,
        "goals_for": s.goals_for,
        "goals_against": s.goals_against,
        "won": s.won,
        "drawn": s.drawn,
        "lost": s.lost,
    }


# ── State mutations ──────────────────────────────────────────────────────


def apply_result(
    state: TournamentState,
    match_id: str,
    home_goals: int,
    away_goals: int,
    *,
    status: str = "completed",
) -> bool:
    """Apply or overwrite a match result. Returns True on success."""
    match = state.match_by_id(match_id)
    if not match:
        return False
    if home_goals < 0 or away_goals < 0:
        return False
    if home_goals > 30 or away_goals > 30:
        return False
    state.results[match_id] = {
        "home_goals": int(home_goals),
        "away_goals": int(away_goals),
        "status": status,
    }
    return True


def clear_result(state: TournamentState, match_id: str) -> bool:
    """Remove a recorded result. Returns True if a result was cleared."""
    if match_id in state.results:
        del state.results[match_id]
        return True
    return False


def reset_state(state: TournamentState) -> None:
    """Clear all recorded results (group stage and knockout) but keep the schedule."""
    state.results = {}
    state.knockout = {}


# ── Qualification scenarios ──────────────────────────────────────────────


def _enumerate_outcomes(matches: list[dict[str, Any]]) -> list[list[tuple[str, str, str]]]:
    """Return all outcome combinations for *matches*.

    Each outcome is a list of (match_id, home_result, away_result) tuples
    where result is "win" | "draw" | "loss" from the home team's perspective.
    Three outcomes per match → 3^n combinations.
    """
    if not matches:
        return [[]]
    n = len(matches)
    if n > 6:
        # Too many combinations to enumerate (3^6 = 729, 3^7 = 2187 — cap at 6)
        return []
    outcomes: list[list[tuple[str, str, str]]] = []
    options = [("win", "loss"), ("draw", "draw"), ("loss", "win")]
    for combo_idx in range(3 ** n):
        combo: list[tuple[str, str, str]] = []
        v = combo_idx
        for m in matches:
            r = v % 3
            v //= 3
            home_r, away_r = options[r]
            combo.append((m["match_id"], home_r, away_r))
        outcomes.append(combo)
    return outcomes


def _apply_outcome_to_state(
    state: TournamentState,
    outcome: list[tuple[str, str, str]],
) -> TournamentState:
    """Build a hypothetical state with *outcome* applied to remaining matches.

    The outcome tuples encode win/draw/loss; we convert to a representative
    scoreline (1-0, 0-0, 0-1) for standings computation. Goal totals affect
    only the GD/GF tiebreakers, not whether a team wins.
    """
    import copy

    sim_state = copy.deepcopy(state)
    for match_id, home_r, _away_r in outcome:
        m = sim_state.match_by_id(match_id)
        if not m:
            continue
        if home_r == "win":
            hg, ag = 1, 0
        elif home_r == "draw":
            hg, ag = 0, 0
        else:
            hg, ag = 0, 1
        sim_state.results[match_id] = {
            "home_goals": hg,
            "away_goals": ag,
            "status": "completed",
        }
    return sim_state


def compute_team_scenarios(
    state: TournamentState,
    team: str,
    *,
    max_scenarios: int = 30,
) -> TeamScenarios:
    """Compute qualification scenarios for *team*.

    Enumerates all win/draw/loss combinations of the team's remaining group
    matches (and any other unfinished matches in the group) and reports the
    share of outcomes where the team advances.

    Parameters
    ----------
    state:
        Current tournament state.
    team:
        Team name (must be in a World Cup group).
    max_scenarios:
        Maximum number of detailed scenarios to return (3^n can be large).
    """
    group = get_team_group(team)
    if group is None:
        return TeamScenarios(
            team=team,
            group="",
            current_standing={},
            remaining_matches=[],
            advance_probability=0.0,
            scenarios=[],
            summary=f"Team '{team}' not found in any World Cup group.",
        )

    # Current standings
    current = compute_group_standings(state, group)
    current_pos = next(
        (i + 1 for i, s in enumerate(current) if s.team == team),
        None,
    )
    current_standing = next(
        (asdict(s) for s in current if s.team == team),
        {},
    )

    # Remaining matches in this group (including ones not involving *team*)
    remaining: list[dict[str, Any]] = []
    for m in state.matches:
        if m.get("group") != group:
            continue
        if _match_completed(state.results.get(m["match_id"])):
            continue
        remaining.append(m)

    outcomes = _enumerate_outcomes(remaining)
    if not outcomes:
        # Either no remaining matches or too many combinations
        # If no remaining matches, just report current state
        if not remaining:
            advancing = determine_advancing_teams(state)
            advances = team in advancing["all_advancing"]
            path = _classify_advance(state, team, group, current_pos)
            return TeamScenarios(
                team=team,
                group=group,
                current_standing=current_standing,
                remaining_matches=[],
                advance_probability=1.0 if advances else 0.0,
                scenarios=[QualificationScenario(
                    description="No remaining matches — final standing",
                    results=[],
                    final_position=current_pos or 0,
                    advances=advances,
                    advance_path=path,
                )],
                summary=(
                    f"{team} has finished all group matches and is currently "
                    f"{current_pos or '?'} in group {group}. "
                    f"{'Advances' if advances else 'Eliminated'} as {path}."
                ),
            )
        # Too many combinations — fall back to sampling (cap at max_scenarios)
        import random

        rng = random.Random(42)
        outcomes = rng.sample(outcomes, min(max_scenarios, len(outcomes)))

    advance_count = 0
    scenarios: list[QualificationScenario] = []
    for outcome in outcomes[:max_scenarios]:
        sim_state = _apply_outcome_to_state(state, outcome)
        sim_standings = compute_group_standings(sim_state, group)
        sim_pos = next(
            (i + 1 for i, s in enumerate(sim_standings) if s.team == team),
            None,
        )
        sim_advancing = determine_advancing_teams(sim_state)
        advances = team in sim_advancing["all_advancing"]
        path = _classify_advance(sim_state, team, group, sim_pos)
        if advances:
            advance_count += 1

        # Build a human-readable description
        desc_parts: list[str] = []
        for match_id, home_r, _away_r in outcome:
            m = sim_state.match_by_id(match_id)
            if not m:
                continue
            if home_r == "win":
                desc_parts.append(f"{m['home']} beats {m['away']}")
            elif home_r == "draw":
                desc_parts.append(f"{m['home']} draws {m['away']}")
            else:
                desc_parts.append(f"{m['home']} loses to {m['away']}")
        description = "; ".join(desc_parts) if desc_parts else "No changes"

        # Results payload — preserve original match metadata from *state*
        results_payload = []
        for match_id, home_r, away_r in outcome:
            orig_match = state.match_by_id(match_id) or {}
            results_payload.append({
                "match_id": match_id,
                "home": orig_match.get("home", ""),
                "away": orig_match.get("away", ""),
                "home_outcome": home_r,
                "away_outcome": away_r,
            })

        scenarios.append(QualificationScenario(
            description=description,
            results=results_payload,
            final_position=sim_pos or 0,
            advances=advances,
            advance_path=path,
        ))

    probability = advance_count / len(outcomes) if outcomes else 0.0

    # Build a concise summary
    if not remaining:
        summary = (
            f"{team} has completed all group matches. Current position: "
            f"{current_pos or '?'}. "
            f"Advance probability: {probability:.0%} (final)."
        )
    else:
        summary = (
            f"{team} has {len(remaining)} remaining group match(es) in group {group}. "
            f"Across {len(outcomes)} enumerated scenarios, {team} advances "
            f"in {advance_count} ({probability:.0%}). "
            f"Current position: {current_pos or '?'}."
        )

    return TeamScenarios(
        team=team,
        group=group,
        current_standing=current_standing,
        remaining_matches=[_match_summary(m) for m in remaining],
        advance_probability=probability,
        scenarios=scenarios,
        summary=summary,
    )


def _classify_advance(
    state: TournamentState,
    team: str,
    group: str,
    position: int | None,
) -> str:
    """Classify how *team* advances (or doesn't) given current standings."""
    if position is None:
        return "unknown"
    if position == 1:
        return "winner"
    if position == 2:
        return "runner-up"
    if position == 3:
        best_thirds = compute_best_thirds(state, limit=8)
        if any(t["team"] == team for t in best_thirds):
            return "best-third"
        return "eliminated"
    return "eliminated"


def _match_summary(m: dict[str, Any]) -> dict[str, Any]:
    return {
        "match_id": m["match_id"],
        "matchday": m.get("matchday"),
        "date": m.get("date"),
        "home": m.get("home"),
        "away": m.get("away"),
        "venue": m.get("venue"),
        "city": m.get("city"),
    }


# ── Persistence ──────────────────────────────────────────────────────────


def state_to_dict(state: TournamentState) -> dict[str, Any]:
    """Serialize tournament state to a JSON-safe dict."""
    return {
        "schema_version": state.schema_version,
        "tournament_start": state.tournament_start,
        "tournament_end": state.tournament_end,
        "matches": state.matches,
        "results": state.results,
        "knockout": state.knockout,
        "notes": state.notes,
        "created_at": state.created_at,
        "updated_at": state.updated_at,
    }


def state_from_dict(
    data: dict[str, Any], *, validate_integrity: bool = True
) -> TournamentState:
    """Reconstruct a TournamentState from a dict, validating schema version.

    ``validate_integrity=False`` is reserved for read-only import diagnostics.
    Normal callers, including persisted state loading, always retain the full
    integrity gate.
    """
    if not isinstance(data, dict):
        raise ValueError("Tournament state must be an object")
    schema = data.get("schema_version", "")
    if not schema.startswith("1."):
        raise ValueError(
            f"Unsupported tournament state schema version: {schema!r}. "
            f"Expected 1.x."
        )
    matches = data.get("matches") or []
    if not isinstance(matches, list):
        raise ValueError("Tournament state 'matches' must be a list")
    results = data.get("results") or {}
    if not isinstance(results, dict):
        raise ValueError("Tournament state 'results' must be a dict")
    state = TournamentState(
        schema_version=schema,
        tournament_start=data.get("tournament_start", TOURNAMENT_START),
        tournament_end=data.get("tournament_end", TOURNAMENT_END),
        matches=matches,
        results=results,
        knockout=data.get("knockout") or {},
        notes=data.get("notes", ""),
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
    )
    if validate_integrity:
        integrity_errors = validate_tournament_state_integrity(state)
        if integrity_errors:
            raise ValueError(f"Invalid tournament state: {integrity_errors[0]}")
    return state


def validate_tournament_state_integrity(state: TournamentState) -> list[str]:
    """Return bounded structural errors for imported tournament state."""
    errors: list[str] = []
    if not isinstance(state.matches, list):
        return ["group matches must be a list"]
    expected_matches = {match["match_id"]: match for match in init_state().matches}
    match_ids: set[str] = set()
    for match in state.matches:
        if not isinstance(match, dict):
            errors.append("group match is not an object")
            continue
        match_id = match.get("match_id")
        if not isinstance(match_id, str) or not match_id:
            errors.append("group match has an invalid match_id")
            continue
        if match_id in match_ids:
            errors.append(f"duplicate group match {match_id!r}")
            continue
        match_ids.add(match_id)
        expected = expected_matches.get(match_id)
        if expected is None:
            errors.append(f"unknown group match {match_id!r}")
            continue
        for schedule_field in ("group", "matchday", "home", "away", "stage"):
            if match.get(schedule_field) != expected[schedule_field]:
                errors.append(f"group match {match_id!r} has altered {schedule_field}")
                break
    if match_ids != set(expected_matches):
        errors.append("group match list does not match the official tournament schedule")
    for match_id, result in state.results.items():
        if match_id not in match_ids:
            errors.append(f"result references unknown match {match_id!r}")
        if not isinstance(result, dict):
            errors.append(f"result for {match_id!r} is not an object")
            continue
        for score_field in ("home_goals", "away_goals"):
            value = result.get(score_field)
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 30:
                errors.append(f"result {match_id!r} has invalid {score_field}")
    knockout = state.knockout
    if not isinstance(knockout, dict):
        errors.append("knockout must be an object")
        return errors[:20]
    matches = knockout.get("matches", [])
    if not isinstance(matches, list):
        errors.append("knockout matches must be a list")
        return errors[:20]
    for match in matches:
        if not isinstance(match, dict):
            errors.append("knockout match is not an object")
            continue
        home, away, winner = match.get("home"), match.get("away"), match.get("winner")
        completed = match.get("status") == "completed"
        if winner is not None and winner not in (home, away):
            errors.append(
                f"knockout winner is not a fixture participant for {match.get('match_id')!r}"
            )
        if completed and (
            winner is None or match.get("home_goals") is None or match.get("away_goals") is None
        ):
            errors.append(f"completed knockout match lacks result for {match.get('match_id')!r}")
        if match.get("prediction_snapshot") is not None and not completed:
            errors.append(
                f"uncompleted knockout match has prediction snapshot for {match.get('match_id')!r}"
            )
    return errors[:20]


def save_state(state: TournamentState, path: str | Path) -> Path:
    """Save tournament state as pretty-printed JSON. Returns the path written."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(state_to_dict(state), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return p


def load_state(path: str | Path | None = None) -> TournamentState:
    """Load tournament state from a JSON file.

    If *path* is None or the file does not exist, returns a fresh empty state
    based on the official 2026 schedule.
    """
    if path is None:
        path = DEFAULT_STATE_PATH
    p = Path(path)
    if not p.exists():
        return init_state()
    data = json.loads(p.read_text(encoding="utf-8"))
    return state_from_dict(data)


# ── Tournament summary ───────────────────────────────────────────────────


def tournament_summary(state: TournamentState) -> dict[str, Any]:
    """Build a comprehensive summary of the current tournament state."""
    total_matches = len(state.matches)
    completed = sum(1 for m in state.matches if _match_completed(state.results.get(m["match_id"])))
    standings_all = compute_all_standings(state)
    advancing = determine_advancing_teams(state)

    return {
        "schema_version": state.schema_version,
        "tournament_start": state.tournament_start,
        "tournament_end": state.tournament_end,
        "total_matches": total_matches,
        "completed_matches": completed,
        "completion_rate": round(completed / total_matches, 4) if total_matches else 0.0,
        "groups_complete": sum(1 for g in GROUPS if _is_complete_group(state, g)),
        "total_groups": len(GROUPS),
        "standings": {
            letter: [asdict(s) for s in standings]
            for letter, standings in standings_all.items()
        },
        "advancing": advancing,
        "best_thirds": compute_best_thirds(state, limit=8),
        "is_complete": completed >= total_matches,
        "hosts": list(HOSTS),
        "knockout": get_knockout_overview(state),
    }


# ── Knockout stage ───────────────────────────────────────────────────────


# Round labels and match counts for the 2026 World Cup knockout stage.
KNOCKOUT_ROUNDS: list[tuple[str, str, int]] = [
    ("r32", "Round of 32", 16),
    ("r16", "Round of 16", 8),
    ("qf", "Quarter-Finals", 4),
    ("sf", "Semi-Finals", 2),
    ("final", "Final", 1),
]


def _seed_knockout_r32(
    advancing: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build 16 Round-of-32 matchups from advancing teams.

    Seeding logic: 12 group winners are sorted by (points, goal_difference,
    goals_for) and seeded 1-12. 12 runners-up are sorted the same way and
    paired against winners so that the strongest winner faces the weakest
    runner-up. 8 best thirds are then distributed to the remaining slots.

    Each matchup dict has: match_id, round, position, home, away,
    home_seed, away_seed, home_group, away_group.
    """
    winners = sorted(
        advancing.get("winners", []),
        key=lambda w: (-w.get("points", 0), -w.get("goal_difference", 0), -w.get("goals_for", 0)),
    )
    runners = sorted(
        advancing.get("runners_up", []),
        key=lambda r: (-r.get("points", 0), -r.get("goal_difference", 0), -r.get("goals_for", 0)),
    )
    thirds = list(advancing.get("best_thirds", []))

    matchups: list[dict[str, Any]] = []
    # First 12 matchups: winner[i] vs runner-up[11-i] (strong vs weak)
    for i in range(12):
        w = winners[i] if i < len(winners) else None
        r = runners[11 - i] if (11 - i) < len(runners) else None
        if not w or not r:
            continue
        matchups.append({
            "match_id": f"r32-{i + 1:02d}",
            "round": "r32",
            "position": i + 1,
            "home": w.get("team"),
            "away": r.get("team"),
            "home_seed": f"1st-{w.get('group', '?')}",
            "away_seed": f"2nd-{r.get('group', '?')}",
            "home_group": w.get("group"),
            "away_group": r.get("group"),
        })

    # Remaining 4 matchups: best thirds paired against remaining runners-up
    # We pair third[j] with runner-up[j] (strongest third vs strongest remaining runner)
    for j in range(4):
        t = thirds[j] if j < len(thirds) else None
        r = runners[j] if j < len(runners) else None
        if not t or not r:
            continue
        pos = 13 + j
        matchups.append({
            "match_id": f"r32-{pos:02d}",
            "round": "r32",
            "position": pos,
            "home": r.get("team"),
            "away": t.get("team"),
            "home_seed": f"2nd-{r.get('group', '?')}",
            "away_seed": f"3rd-{t.get('group', '?')}",
            "home_group": r.get("group"),
            "away_group": t.get("group"),
        })

    return matchups


def _build_knockout_rounds(
    r32_matchups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build all knockout matches (R32 through Final) with empty slots for
    later rounds. R32 is populated from *r32_matchups*; later rounds have
    home/away set to None until winners are determined.
    """
    matches: list[dict[str, Any]] = []
    for m in r32_matchups:
        matches.append({
            **m,
            "home_goals": None,
            "away_goals": None,
            "winner": None,
            "status": "scheduled",
        })

    # R16: 8 matches, each fed by 2 consecutive R32 matches
    for i in range(8):
        matches.append({
            "match_id": f"r16-{i + 1:02d}",
            "round": "r16",
            "position": i + 1,
            "home": None,
            "away": None,
            "home_seed": f"Winner R32-{2 * i + 1:02d}",
            "away_seed": f"Winner R32-{2 * i + 2:02d}",
            "home_group": None,
            "away_group": None,
            "home_goals": None,
            "away_goals": None,
            "winner": None,
            "status": "scheduled",
        })

    # QF: 4 matches
    for i in range(4):
        matches.append({
            "match_id": f"qf-{i + 1:02d}",
            "round": "qf",
            "position": i + 1,
            "home": None,
            "away": None,
            "home_seed": f"Winner R16-{2 * i + 1:02d}",
            "away_seed": f"Winner R16-{2 * i + 2:02d}",
            "home_group": None,
            "away_group": None,
            "home_goals": None,
            "away_goals": None,
            "winner": None,
            "status": "scheduled",
        })

    # SF: 2 matches
    for i in range(2):
        matches.append({
            "match_id": f"sf-{i + 1:02d}",
            "round": "sf",
            "position": i + 1,
            "home": None,
            "away": None,
            "home_seed": f"Winner QF-{2 * i + 1:02d}",
            "away_seed": f"Winner QF-{2 * i + 2:02d}",
            "home_group": None,
            "away_group": None,
            "home_goals": None,
            "away_goals": None,
            "winner": None,
            "status": "scheduled",
        })

    # Final: 1 match
    matches.append({
        "match_id": "final-01",
        "round": "final",
        "position": 1,
        "home": None,
        "away": None,
        "home_seed": "Winner SF-01",
        "away_seed": "Winner SF-02",
        "home_group": None,
        "away_group": None,
        "home_goals": None,
        "away_goals": None,
        "winner": None,
        "status": "scheduled",
    })

    return matches


def generate_knockout_bracket(state: TournamentState) -> dict[str, Any]:
    """Generate the full knockout bracket from current group standings.

    Returns a dict with ``matches`` (list of all 31 knockout matches from R32
    through Final) and ``generated`` (timestamp). If the group stage is not
    yet complete, the bracket is marked as ``provisional``.

    Raises ValueError if fewer than 32 advancing teams can be determined
    (e.g. group stage has no results at all and no provisional advancement
    can be computed).
    """
    advancing = determine_advancing_teams(state)
    r32 = _seed_knockout_r32(advancing)
    if len(r32) < 16:
        raise ValueError(
            f"Cannot generate knockout bracket: only {len(r32)} R32 matchups "
            f"could be seeded. Need 16 (32 teams)."
        )
    all_matches = _build_knockout_rounds(r32)
    return {
        "matches": all_matches,
        "generated": _now_iso(),
        "provisional": advancing.get("provisional", True),
        "champion": None,
    }


def apply_knockout_result(
    state: TournamentState,
    match_id: str,
    home_goals: int,
    away_goals: int,
    *,
    penalties_winner: str | None = None,
) -> TournamentState:
    """Record a knockout match result and auto-advance the winner.

    If the score is level after regulation, *penalties_winner* must be
    provided to determine the winner. The winner is automatically placed into
    the next round's matchup.

    Raises ValueError if the match is not found, already has a result, or
    if a draw is recorded without a penalties winner.
    """
    if not state.knockout:
        raise ValueError(
            "No knockout bracket has been generated. "
            "Run `generate_knockout_bracket` first."
        )

    match = state.knockout_match_by_id(match_id)
    if not match:
        raise ValueError(f"Knockout match {match_id!r} not found.")

    if match.get("winner"):
        raise ValueError(f"Match {match_id!r} already has a result (winner: {match['winner']}).")

    if match.get("home") is None or match.get("away") is None:
        raise ValueError(
            f"Match {match_id!r} is not ready: one or both teams have not been determined."
        )

    if home_goals < 0 or away_goals < 0:
        raise ValueError("Goals must be non-negative.")

    home = match["home"]
    away = match["away"]

    # Determine winner
    if home_goals > away_goals:
        winner = home
    elif away_goals > home_goals:
        winner = away
    else:
        # Draw — penalties required
        if penalties_winner not in (home, away):
            raise ValueError(
                f"Drawn match requires penalties_winner to be '{home}' or '{away}', "
                f"got {penalties_winner!r}."
            )
        winner = penalties_winner

    # Update the match in-place
    match["home_goals"] = home_goals
    match["away_goals"] = away_goals
    match["winner"] = winner
    match["status"] = "completed"
    if home_goals == away_goals:
        match["decided_by"] = "penalties"
        match["penalties_winner"] = penalties_winner
    else:
        match["decided_by"] = "regular"

    # Advance winner to next round
    _advance_winner(state, match)

    # If this was the final, set champion
    if match["round"] == "final":
        state.knockout["champion"] = winner

    return state


def clear_knockout_result(state: TournamentState, match_id: str) -> TournamentState:
    """Clear a knockout match result and cascade-clear downstream matches.

    Clearing a result also clears any results in later rounds that depended
    on this match's winner, since those matchups would no longer be valid.
    """
    if not state.knockout:
        raise ValueError("No knockout bracket has been generated.")

    match = state.knockout_match_by_id(match_id)
    if not match:
        raise ValueError(f"Knockout match {match_id!r} not found.")

    if not match.get("winner"):
        raise ValueError(f"Match {match_id!r} has no recorded result to clear.")

    # Find and clear all downstream matches that this winner fed into
    _cascade_clear_downstream(state, match)

    # Clear this match
    match["home_goals"] = None
    match["away_goals"] = None
    match["winner"] = None
    match["status"] = "scheduled"
    match.pop("decided_by", None)
    match.pop("penalties_winner", None)
    match.pop("prediction_snapshot", None)

    if match["round"] == "final":
        state.knockout.pop("champion", None)

    return state


def _advance_winner(state: TournamentState, match: dict[str, Any]) -> None:
    """Place the winner of *match* into the next round's matchup."""
    round_code = match["round"]
    pos = match["position"]

    round_order = [r[0] for r in KNOCKOUT_ROUNDS]
    if round_code not in round_order:
        return
    idx = round_order.index(round_code)
    if idx >= len(round_order) - 1:
        return  # Final — no next round

    next_round = round_order[idx + 1]
    # Next round position: ceil(pos / 2)
    next_pos = (pos + 1) // 2
    # Is the winner home or away in the next match?
    is_home = (pos % 2 == 1)

    next_match = None
    for m in state.knockout.get("matches", []):
        if m.get("round") == next_round and m.get("position") == next_pos:
            next_match = m
            break

    if next_match:
        if is_home:
            next_match["home"] = match["winner"]
        else:
            next_match["away"] = match["winner"]


def _cascade_clear_downstream(state: TournamentState, match: dict[str, Any]) -> None:
    """Clear all downstream matches whose team slot was fed by *match*."""
    round_code = match["round"]
    pos = match["position"]

    round_order = [r[0] for r in KNOCKOUT_ROUNDS]
    if round_code not in round_order:
        return
    idx = round_order.index(round_code)
    if idx >= len(round_order) - 1:
        return

    next_round = round_order[idx + 1]
    next_pos = (pos + 1) // 2
    is_home = (pos % 2 == 1)

    next_match = None
    for m in state.knockout.get("matches", []):
        if m.get("round") == next_round and m.get("position") == next_pos:
            next_match = m
            break

    if not next_match:
        return

    # If the next match has a result, clear it first (recursive)
    if next_match.get("winner"):
        _cascade_clear_downstream(state, next_match)
        next_match["home_goals"] = None
        next_match["away_goals"] = None
        next_match["winner"] = None
        next_match["status"] = "scheduled"
        next_match.pop("decided_by", None)
        next_match.pop("penalties_winner", None)
        next_match.pop("prediction_snapshot", None)
        if next_match["round"] == "final":
            state.knockout.pop("champion", None)

    # Clear the team slot
    if is_home:
        next_match["home"] = None
    else:
        next_match["away"] = None


def get_knockout_overview(state: TournamentState) -> dict[str, Any]:
    """Return a summary of the knockout stage state.

    If no bracket has been generated, returns ``{"generated": False}``.
    """
    ko = state.knockout
    if not ko or not ko.get("matches"):
        return {"generated": False}

    matches = ko.get("matches", [])
    by_round: dict[str, list[dict[str, Any]]] = {}
    for code, _label, _count in KNOCKOUT_ROUNDS:
        round_matches = [m for m in matches if m.get("round") == code]
        by_round[code] = round_matches

    completed = sum(1 for m in matches if m.get("status") == "completed")
    total = len(matches)

    # Determine current round (first round with unplayed matches)
    current_round = None
    for code, _label, _ in KNOCKOUT_ROUNDS:
        round_matches = by_round.get(code, [])
        has_unplayed = any(m.get("status") != "completed" for m in round_matches)
        if has_unplayed and round_matches:
            current_round = code
            break

    return {
        "generated": True,
        "provisional": ko.get("provisional", True),
        "generated_at": ko.get("generated"),
        "champion": ko.get("champion"),
        "current_round": current_round,
        "completed_matches": completed,
        "total_matches": total,
        "rounds": {
            code: {
                "label": label,
                "matches": round_matches,
            }
            for code, label, _ in KNOCKOUT_ROUNDS
            for round_matches in [by_round.get(code, [])]
        },
    }


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    from datetime import datetime

    return datetime.now(UTC).isoformat()
