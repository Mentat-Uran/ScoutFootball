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
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    def match_by_id(self, match_id: str) -> dict[str, Any] | None:
        for m in self.matches:
            if m["match_id"] == match_id:
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
    """Clear all recorded results but keep the schedule."""
    state.results = {}


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
        "notes": state.notes,
        "created_at": state.created_at,
        "updated_at": state.updated_at,
    }


def state_from_dict(data: dict[str, Any]) -> TournamentState:
    """Reconstruct a TournamentState from a dict, validating schema version."""
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
    return TournamentState(
        schema_version=schema,
        tournament_start=data.get("tournament_start", TOURNAMENT_START),
        tournament_end=data.get("tournament_end", TOURNAMENT_END),
        matches=matches,
        results=results,
        notes=data.get("notes", ""),
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
    )


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
    }
