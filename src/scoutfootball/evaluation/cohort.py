"""Cohort definition, preview and membership kernel (PRS-1 R-010).

PRS-1 (see ``docs/PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md`` §5, PRS-DATA-002 /
PRS-DATA-003) requires a reusable cohort definition so that every rating
experiment, baseline slice and label set operates on the **same explicitly
defined population** instead of an ad-hoc row filter that silently changes
between runs.

A cohort is a declarative, JSON-serialisable specification of which
player-season rows are in scope. It is built on top of the three PRS-1
foundations delivered in slices 1-6:

- **canonical_player_id** (slice 2-3): cohort membership is keyed by the
  resolved canonical ID (or the source-stable ``unresolved:<source>:<id>``
  marker when no human decision exists). Cohort membership never uses
  ``player_id`` directly, because source-specific IDs are not stable
  across sources or snapshots.
- **evidence grain** (slice 1, 4): each member row carries its
  ``data_granularity`` and ``source_name`` so downstream code can
  distinguish season-proxy evidence from match-level evidence.
- **RoleFamily** (slice 6): the ``role_families`` filter uses the typed
  ``RoleFamily`` vocabulary, not the raw ``position_group`` string, so
  coarse labels (DF/MF/FW) and combo labels ("MF,FW") are handled
  consistently.

This module is read-only and side-effect-free. ``preview_cohort`` does
not modify ``player_match.parquet``; it loads a resolved view (via
``canonical_resolver.load_resolved_player_match``), aggregates to
player-season level, applies the declarative filters, and returns a
membership snapshot with typed exclusion reasons.

Design rules (PRS-1 退出门槛: "cohort 重新运行能得到同一成员与相同 hash"):

1. ``cohort_hash`` is the sha256[:16] of the definition's canonical JSON.
   It depends only on the definition, not on the data. The same definition
   always produces the same hash.
2. ``membership_hash`` is the sha256[:16] of the sorted
   ``canonical_player_id|season_id`` pairs. It depends on both the
   definition and the data. Same definition + same data → same membership
   hash. If the data changes (player added/removed), the membership hash
   changes — surfacing drift rather than hiding it.
3. Filters are AND-combined: a row must pass every active filter to be
   included. ``None`` means "no filter on this dimension"; an empty
   frozenset means "filter active but matches nothing" (a valid but
   useless filter that yields 0 members).
4. Exclusion reasons are typed (``ExclusionReason``), not free text, so
   downstream tooling can count and slice exclusions programmatically.
5. The cohort unit is **player-season** (one row per canonical player per
   season), matching ``rating_feature_matrix.parquet`` granularity. A
   multi-team season is flagged but not split — PRS-1 does not yet
   expose a player-team-season view as a separate cohort unit.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from scoutfootball.config import PlatformSettings
from scoutfootball.evaluation.role_system import RoleFamily, classify_role_family

COHORT_SCHEMA = "scoutfootball.cohort"
COHORT_SCHEMA_VERSION = "1.0.0"

# Cap for excluded_samples in the preview output. Keeps the report
# machine-readable while still giving the maintainer enough signal to
# understand why rows were dropped.
_EXCLUDED_SAMPLE_CAP = 20


class ExclusionReason(StrEnum):
    """Typed reasons a candidate player-season was excluded from a cohort.

    The cohort preview applies filters in a deterministic order and records
    the **first** reason that matches. This means a row that fails both
    ``MIN_MINUTES_NOT_MET`` and ``ROLE_NOT_IN_FILTER`` is counted once,
    under the first filter that rejected it. The order is documented in
    ``preview_cohort`` so the maintainer can reason about which filter is
    the binding constraint.
    """

    COMPETITION_NOT_IN_FILTER = "competition_not_in_filter"
    SEASON_NOT_IN_FILTER = "season_not_in_filter"
    TEAM_NOT_IN_FILTER = "team_not_in_filter"
    ROLE_NOT_IN_FILTER = "role_not_in_filter"
    MIN_MINUTES_NOT_MET = "min_minutes_not_met"
    AGE_OUT_OF_RANGE = "age_out_of_range"
    NO_BORN_YEAR = "no_born_year"
    UNRESOLVED_IDENTITY = "unresolved_identity"
    UNKNOWN_ROLE = "unknown_role"
    MISSING_POSITION_GROUP = "missing_position_group"


@dataclass(frozen=True)
class CohortDefinition:
    """Declarative, JSON-serialisable cohort specification.

    All filter fields default to ``None`` meaning "no filter on this
    dimension". A filter is active when its value is not ``None``; an
    active filter with an empty frozenset matches nothing (valid but
    yields 0 members).

    The ``cohort_hash`` depends only on the definition, so the same
    definition always produces the same hash regardless of when or where
    it is computed. This is the stable identifier that PRS-2/PRS-3 use
    to pin a cohort to a baseline or label set.

    Age filter semantics: ``age_min`` / ``age_max`` are applied per row
    using ``season_start_year - born`` where ``season_start_year`` is
    derived from ``season_id`` (``"2425"`` → 2024). This is an
    approximation (it ignores month-of-birth and mid-season transfers)
    and is documented in the limitations. When ``age_min`` or
    ``age_max`` is set and ``born`` is missing, the row is excluded with
    ``NO_BORN_YEAR`` rather than silently passing or failing.
    """

    name: str
    description: str = ""
    competition_ids: frozenset[str] | None = None
    season_ids: frozenset[str] | None = None
    team_ids: frozenset[str] | None = None
    role_families: frozenset[RoleFamily] | None = None
    min_minutes: int | None = None
    age_min: int | None = None
    age_max: int | None = None
    require_resolved_identity: bool = False
    require_known_role: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict representation.

        Frozensets are sorted lists so the output is deterministic.
        ``None`` filters are omitted to keep the dict minimal; their
        absence means "no filter".
        """
        out: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
        }
        if self.competition_ids is not None:
            out["competition_ids"] = sorted(self.competition_ids)
        if self.season_ids is not None:
            out["season_ids"] = sorted(self.season_ids)
        if self.team_ids is not None:
            out["team_ids"] = sorted(self.team_ids)
        if self.role_families is not None:
            out["role_families"] = sorted(
                f.value for f in self.role_families
            )
        if self.min_minutes is not None:
            out["min_minutes"] = self.min_minutes
        if self.age_min is not None:
            out["age_min"] = self.age_min
        if self.age_max is not None:
            out["age_max"] = self.age_max
        if self.require_resolved_identity:
            out["require_resolved_identity"] = True
        if self.require_known_role:
            out["require_known_role"] = True
        return out

    def to_canonical_json(self) -> str:
        """Return a canonical JSON string for hashing.

        Keys are sorted, whitespace is minimal, and frozensets are
        rendered as sorted lists. The same definition always produces
        the same canonical JSON.
        """
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)

    def cohort_hash(self) -> str:
        """Return sha256[:16] of the canonical definition JSON.

        16 hex chars (64 bits) is enough to make collisions effectively
        impossible for any realistic number of cohort definitions, and
        keeps the hash short enough to display in CLI output and
        research-health reports.
        """
        return hashlib.sha256(self.to_canonical_json().encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class CohortMember:
    """One player-season row in the cohort membership list.

    The membership list is the stable output of ``preview_cohort``: it
    is what PRS-2 baseline slicing and PRS-3 label collection operate on.
    Each member carries enough context to be individually identifiable
    without re-reading the parquet, but the full feature vector lives in
    ``rating_feature_matrix.parquet`` — the cohort only defines **who**
    is in scope, not their feature values.
    """

    canonical_player_id: str
    player_name: str
    season_id: str
    competition_id: str
    team_id: str
    team_name: str
    role_family: str
    minutes_played: float
    source_name: str
    data_granularity: str
    multi_team_season: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_player_id": self.canonical_player_id,
            "player_name": self.player_name,
            "season_id": self.season_id,
            "competition_id": self.competition_id,
            "team_id": self.team_id,
            "team_name": self.team_name,
            "role_family": self.role_family,
            "minutes_played": self.minutes_played,
            "source_name": self.source_name,
            "data_granularity": self.data_granularity,
            "multi_team_season": self.multi_team_season,
        }


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _season_start_year(season_id: Any) -> int | None:
    """Extract the start year from a season_id like ``"2425"``.

    Returns ``20XX`` for the 2000s. Returns ``None`` if the format is
    not recognised. Documented limitation: does not handle 1900s or 2100s
    seasons; the current local data only spans 2016-17 to 2025-26.
    """
    if not isinstance(season_id, str):
        return None
    s = season_id.strip()
    if len(s) != 4 or not s.isdigit():
        return None
    return 2000 + int(s[:2])


def _coerce_str(value: Any) -> str | None:
    """Return the value as a non-empty str, or None if missing/NaN/empty."""
    if value is None:
        return None
    if isinstance(value, str):
        return value if value else None
    if isinstance(value, bool):
        return None
    if isinstance(value, float):
        if value != value:  # NaN
            return None
        if value.is_integer():
            return str(int(value))
        return str(value)
    if isinstance(value, int):
        return str(value)
    return str(value) if value else None


def _coerce_int(value: Any) -> int | None:
    """Return the value as int, or None if missing/NaN/non-numeric."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != value:  # NaN
            return None
        if value.is_integer():
            return int(value)
        return None
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _coerce_float(value: Any) -> float:
    """Return the value as float, defaulting to 0.0 for missing/NaN.

    Used for minutes_played where a missing value should be treated as
    0 (the player recorded no minutes) rather than excluded — the
    ``min_minutes`` filter handles the exclusion.
    """
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        if value != value:  # NaN
            return 0.0
        return float(value)
    return 0.0


def compute_membership_hash(members: list[CohortMember]) -> str:
    """Return sha256[:16] of the sorted member key pairs.

    The key is ``canonical_player_id|season_id``. Sorting makes the hash
    independent of row order, so the same membership set always produces
    the same hash regardless of how the rows were produced.
    """
    keys = sorted(f"{m.canonical_player_id}|{m.season_id}" for m in members)
    joined = "|".join(keys)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def _aggregate_player_seasons(df: Any) -> list[dict[str, Any]]:
    """Aggregate player_match rows to player-season level.

    Groups by ``(canonical_player_id, season_id)`` and sums minutes,
    takes first of competition/team/role/source columns. Returns a list
    of dicts (one per player-season) in stable order.
    """
    if df is None or "canonical_player_id" not in df.columns:
        return []

    # Ensure season_id is present; without it we cannot group.
    if "season_id" not in df.columns:
        return []

    # Sum minutes_played per player-season.
    if "minutes_played" in df.columns:
        minutes = (
            df.groupby(
                ["canonical_player_id", "season_id"], dropna=False
            )["minutes_played"]
            .sum(min_count=1)
            .reset_index()
        )
    else:
        minutes = (
            df.groupby(
                ["canonical_player_id", "season_id"], dropna=False
            )
            .size()
            .reset_index(name="_count")
        )
        minutes["minutes_played"] = 0.0

    # Take first value for identity/meta columns.
    first_cols = [
        "player_name",
        "competition_id",
        "team_id",
        "team_name",
        "position_group",
        "source_name",
        "data_granularity",
        "born",
        "multi_team_season",
    ]
    first_cols = [c for c in first_cols if c in df.columns]
    if first_cols:
        firsts = (
            df.groupby(
                ["canonical_player_id", "season_id"], dropna=False
            )[first_cols]
            .first()
            .reset_index()
        )
        merged = minutes.merge(
            firsts, on=["canonical_player_id", "season_id"], how="left"
        )
    else:
        merged = minutes
        for c in first_cols:
            merged[c] = None

    # Sort for stable output.
    sort_cols = [c for c in ["canonical_player_id", "season_id"] if c in merged.columns]
    merged = merged.sort_values(sort_cols).reset_index(drop=True)

    return merged.to_dict("records")


def preview_cohort(
    definition: CohortDefinition,
    settings: PlatformSettings | None = None,
) -> dict[str, Any]:
    """Apply a ``CohortDefinition`` to ``player_match.parquet`` and return
    a membership preview with typed exclusion reasons.

    The preview is read-only and fail-closed: missing/unreadable
    player_match or a corrupt identity registry returns
    ``status=unavailable`` with the reason in ``evidence``. An empty
    membership (all rows excluded) is ``status=ok`` with 0 members —
    that is a valid cohort result, not a failure.

    Filter application order (first match wins for exclusion reason):

    1. ``competition_ids`` → ``COMPETITION_NOT_IN_FILTER``
    2. ``season_ids`` → ``SEASON_NOT_IN_FILTER``
    3. ``team_ids`` → ``TEAM_NOT_IN_FILTER``
    4. ``role_families`` / ``require_known_role`` → ``ROLE_NOT_IN_FILTER``
       / ``UNKNOWN_ROLE`` / ``MISSING_POSITION_GROUP``
    5. ``min_minutes`` → ``MIN_MINUTES_NOT_MET``
    6. ``age_min`` / ``age_max`` → ``AGE_OUT_OF_RANGE`` / ``NO_BORN_YEAR``
    7. ``require_resolved_identity`` → ``UNRESOLVED_IDENTITY``
    """
    resolved = settings or PlatformSettings.from_root()

    # Load resolved player_match (adds canonical_player_id column).
    try:
        from scoutfootball.evaluation.canonical_resolver import (
            load_resolved_player_match,
        )

        df = load_resolved_player_match(resolved)
    except (ValueError, OSError) as exc:
        return {
            "schema": COHORT_SCHEMA,
            "schema_version": COHORT_SCHEMA_VERSION,
            "generated_at": _now(),
            "status": "unavailable",
            "cohort_hash": definition.cohort_hash(),
            "evidence": {"reason": f"load_resolved_player_match failed: {exc}"},
            "definition": definition.to_dict(),
            "limitations": _LIMITATIONS,
        }

    if df is None or len(df) == 0:
        return {
            "schema": COHORT_SCHEMA,
            "schema_version": COHORT_SCHEMA_VERSION,
            "generated_at": _now(),
            "status": "unavailable",
            "cohort_hash": definition.cohort_hash(),
            "evidence": {"reason": "player_match.parquet is empty or unreadable"},
            "definition": definition.to_dict(),
            "limitations": _LIMITATIONS,
        }

    rows = _aggregate_player_seasons(df)
    total_candidates = len(rows)

    members: list[CohortMember] = []
    excluded: list[dict[str, Any]] = []
    by_reason: dict[str, int] = {}

    for row in rows:
        reason = _evaluate_row(row, definition)
        if reason is None:
            members.append(_row_to_member(row))
        else:
            reason_key = reason.value
            by_reason[reason_key] = by_reason.get(reason_key, 0) + 1
            if len(excluded) < _EXCLUDED_SAMPLE_CAP:
                excluded.append(_row_to_excluded_sample(row, reason))

    membership_hash = compute_membership_hash(members)

    return {
        "schema": COHORT_SCHEMA,
        "schema_version": COHORT_SCHEMA_VERSION,
        "generated_at": _now(),
        "status": "ok",
        "cohort_hash": definition.cohort_hash(),
        "membership_hash": membership_hash,
        "definition": definition.to_dict(),
        "evidence": {
            "total_candidate_rows": total_candidates,
            "included_rows": len(members),
            "excluded_rows": total_candidates - len(members),
            "by_exclusion_reason": by_reason,
            "excluded_samples": excluded,
            "members": [m.to_dict() for m in members],
        },
        "limitations": _LIMITATIONS,
    }


def _evaluate_row(
    row: dict[str, Any], definition: CohortDefinition
) -> ExclusionReason | None:
    """Evaluate a single player-season row against the definition.

    Returns the first matching ``ExclusionReason`` or ``None`` if the
    row passes all filters. The order is documented in
    ``preview_cohort`` and kept stable so exclusion counts are
    reproducible.
    """
    # 1. Competition filter
    if definition.competition_ids is not None:
        comp = _coerce_str(row.get("competition_id"))
        if comp is None or comp not in definition.competition_ids:
            return ExclusionReason.COMPETITION_NOT_IN_FILTER

    # 2. Season filter
    if definition.season_ids is not None:
        season = _coerce_str(row.get("season_id"))
        if season is None or season not in definition.season_ids:
            return ExclusionReason.SEASON_NOT_IN_FILTER

    # 3. Team filter
    if definition.team_ids is not None:
        team = _coerce_str(row.get("team_id"))
        if team is None or team not in definition.team_ids:
            return ExclusionReason.TEAM_NOT_IN_FILTER

    # 4. Role filter / require_known_role
    pg = row.get("position_group")
    role = classify_role_family(pg)

    if definition.role_families is not None:
        if role == RoleFamily.UNKNOWN:
            if pg is None or (isinstance(pg, float) and pg != pg):
                return ExclusionReason.MISSING_POSITION_GROUP
            return ExclusionReason.UNKNOWN_ROLE
        if role not in definition.role_families:
            return ExclusionReason.ROLE_NOT_IN_FILTER

    if definition.require_known_role and role == RoleFamily.UNKNOWN:
        if pg is None or (isinstance(pg, float) and pg != pg):
            return ExclusionReason.MISSING_POSITION_GROUP
        return ExclusionReason.UNKNOWN_ROLE

    # 5. min_minutes filter
    if definition.min_minutes is not None:
        minutes = _coerce_float(row.get("minutes_played"))
        if minutes < definition.min_minutes:
            return ExclusionReason.MIN_MINUTES_NOT_MET

    # 6. Age filter
    if definition.age_min is not None or definition.age_max is not None:
        born = _coerce_int(row.get("born"))
        if born is None:
            return ExclusionReason.NO_BORN_YEAR
        season_start = _season_start_year(row.get("season_id"))
        if season_start is None:
            return ExclusionReason.NO_BORN_YEAR
        age = season_start - born
        if definition.age_min is not None and age < definition.age_min:
            return ExclusionReason.AGE_OUT_OF_RANGE
        if definition.age_max is not None and age > definition.age_max:
            return ExclusionReason.AGE_OUT_OF_RANGE

    # 7. require_resolved_identity
    if definition.require_resolved_identity:
        from scoutfootball.evaluation.canonical_resolver import is_unresolved

        cid = _coerce_str(row.get("canonical_player_id"))
        if cid is None or is_unresolved(cid):
            return ExclusionReason.UNRESOLVED_IDENTITY

    return None


def _row_to_member(row: dict[str, Any]) -> CohortMember:
    """Build a ``CohortMember`` from an aggregated player-season row."""
    pg = row.get("position_group")
    role = classify_role_family(pg)
    return CohortMember(
        canonical_player_id=_coerce_str(row.get("canonical_player_id")) or "",
        player_name=_coerce_str(row.get("player_name")) or "",
        season_id=_coerce_str(row.get("season_id")) or "",
        competition_id=_coerce_str(row.get("competition_id")) or "",
        team_id=_coerce_str(row.get("team_id")) or "",
        team_name=_coerce_str(row.get("team_name")) or "",
        role_family=role.value,
        minutes_played=_coerce_float(row.get("minutes_played")),
        source_name=_coerce_str(row.get("source_name")) or "",
        data_granularity=_coerce_str(row.get("data_granularity")) or "",
        multi_team_season=bool(row.get("multi_team_season") is True),
    )


def _row_to_excluded_sample(
    row: dict[str, Any], reason: ExclusionReason
) -> dict[str, Any]:
    """Build a compact excluded-sample dict for the preview output."""
    return {
        "canonical_player_id": _coerce_str(row.get("canonical_player_id")) or "",
        "player_name": _coerce_str(row.get("player_name")) or "",
        "season_id": _coerce_str(row.get("season_id")) or "",
        "competition_id": _coerce_str(row.get("competition_id")) or "",
        "team_id": _coerce_str(row.get("team_id")) or "",
        "role_family": classify_role_family(row.get("position_group")).value,
        "minutes_played": _coerce_float(row.get("minutes_played")),
        "exclusion_reason": reason.value,
    }


_LIMITATIONS: list[str] = [
    (
        "Read-only local preview; does not modify player_match.parquet "
        "or rating_feature_matrix.parquet. Cohort membership is computed "
        "on each call from the current resolved player_match view."
    ),
    (
        "cohort_hash is sha256[:16] of the definition's canonical JSON; "
        "it depends only on the definition, not on the data. The same "
        "definition always produces the same hash. membership_hash "
        "depends on both definition and data, so it changes when the "
        "underlying player_match.parquet changes — surfacing drift "
        "rather than hiding it."
    ),
    (
        "Cohort unit is player-season (one row per canonical_player_id + "
        "season_id), matching rating_feature_matrix granularity. "
        "multi_team_season is flagged but not split; a future PRS slice "
        "may add a player-team-season cohort view."
    ),
    (
        "Age filter uses season_start_year - born where season_start_year "
        "is derived from season_id ('2425' -> 2024). This is an "
        "approximation: it ignores month-of-birth and mid-season "
        "transfers. Rows with missing born are excluded via "
        "NO_BORN_YEAR rather than silently passing."
    ),
    (
        "require_resolved_identity=True excludes rows whose "
        "canonical_player_id is an unresolved:<source>:<id> marker. "
        "With the current 10-record registry, most rows are unresolved; "
        "this filter is only useful after broader identity registry "
        "coverage."
    ),
    (
        "Exclusion reasons are first-match-wins in a fixed filter order "
        "(competition -> season -> team -> role -> minutes -> age -> "
        "identity). A row failing multiple filters is counted once under "
        "the first matching reason."
    ),
]


__all__ = [
    "COHORT_SCHEMA",
    "COHORT_SCHEMA_VERSION",
    "CohortDefinition",
    "CohortMember",
    "ExclusionReason",
    "compute_membership_hash",
    "preview_cohort",
]
