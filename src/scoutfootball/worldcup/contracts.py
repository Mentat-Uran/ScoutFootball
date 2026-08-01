"""Core data contract bindings for the World Cup pack.

This module is the single re-use point between the World Cup pack and the
:mod:`scoutfootball.schemas.storage` Core types.  It builds
:class:`DataContract`, :class:`SnapshotInfo` and :class:`LineageEntry`
instances for every World Cup artifact so the World Cup pack does not
duplicate identity, snapshot or export logic.

Fact taxonomy
-------------

World Cup data carries five fact types, declared on each artifact so
consumers can tell official facts from model estimates:

``official_roster``
    FIFA-published 26-man rosters.  Not yet available for 2026; the
    artifact is recorded as ``status="missing"`` until the official
    squad lists are published.

``expected_callup``
    The static ``SQUADS`` table in :mod:`scoutfootball.worldcup.data`.
    Built from recent national team selections and 2025-26 club form.
    Marked ``status="provisional"``.

``injury_report``
    Per-player injury status.  Not modelled locally; the artifact is
    recorded as ``status="not_tracked"`` so consumers know the
    absence is intentional rather than a missing export.

``rating_coverage``
    Per-player optimized ratings joined from
    ``player_ratings_optimized.parquet`` onto the expected callups.

``model_probability``
    Bradley-Terry strength-ratio outputs (group predictions, knockout
    probabilities, championship probabilities) and the public Opta
    priors in ``OPTA_WIN_PROBABILITY``.

Every public builder here returns a frozen Pydantic model from
``schemas.storage``; no parallel types are introduced.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from enum import StrEnum

from scoutfootball.schemas.storage import (
    CoverageInfo,
    DataContract,
    LineageEntry,
    SnapshotInfo,
    SourceLicense,
)

# ── Fact taxonomy ────────────────────────────────────────────────────────


class WorldCupFactType(StrEnum):
    """Five fact types distinguished in World Cup artifacts."""

    OFFICIAL_ROSTER = "official_roster"
    EXPECTED_CALLUP = "expected_callup"
    INJURY_REPORT = "injury_report"
    RATING_COVERAGE = "rating_coverage"
    MODEL_PROBABILITY = "model_probability"


# ── Static source metadata ───────────────────────────────────────────────
#
# These constants are the single source of truth for World Cup artifact
# identity.  They are referenced by every builder below so the World Cup
# pack never re-implements source license, snapshot or lineage logic.


WORLDCUP_ARTIFACT_PREFIX = "worldcup"

# Stable as_of timestamps for static (non-FIFA) World Cup data.  These are
# documented snapshot dates — the data was compiled from public sources on
# these dates and is not re-pulled automatically.
SNAPSHOT_AS_OF_EXPECTED_CALLUPS = datetime(2026, 5, 15, tzinfo=UTC)
SNAPSHOT_AS_OF_OPTA_PRIORS = datetime(2026, 5, 1, tzinfo=UTC)
SNAPSHOT_AS_OF_RATING_COVERAGE = datetime(2026, 6, 1, tzinfo=UTC)

# Parser / generator version stamps (mirrored from schemas.storage conventions).
PARSER_VERSION_SCHEDULE = "scoutfootball.worldcup.data.v1"
PARSER_VERSION_SQUADS = "scoutfootball.worldcup.data.v1"
PARSER_VERSION_RATINGS = "scoutfootball.optimizer.v1"
PARSER_VERSION_STRENGTH = "scoutfootball.worldcup.strength.v1"
PARSER_VERSION_TOURNAMENT_STATE = "scoutfootball.worldcup.tournament.v1"

# Stable source licenses reused across World Cup artifacts.  These mirror
# the licenses already declared elsewhere in the project for the same
# upstream sources, so the World Cup pack does not invent new terms.
_LICENSE_FBREF_UNDERSTAT = SourceLicense(
    source_name="FBref + Understat (via ScoutFootball optimizer)",
    license_name="CC BY-NC-SA 4.0 (FBref) / Understat ToS",
    attribution_required=True,
    redistribution_allowed=False,
    commercial_use_allowed=False,
    retention_policy_days=None,
    deletion_strategy="Local-only; delete on request",
    source_url="https://fbref.com / https://understat.com",
    notes="Ratings derived by the local ScoutFootball optimizer.",
)

_LICENSE_OPTA_PUBLIC_PRIORS = SourceLicense(
    source_name="Opta public championship priors",
    license_name="Publicly cited pre-tournament probabilities",
    attribution_required=True,
    redistribution_allowed=True,
    commercial_use_allowed=False,
    retention_policy_days=None,
    deletion_strategy="Replace when Opta publishes updated priors",
    source_url="",
    notes="Single decimal per team, published pre-tournament.",
)

_LICENSE_FIFA_FIXTURE = SourceLicense(
    source_name="FIFA World Cup 2026 fixture pattern",
    license_name="Public tournament fixture list",
    attribution_required=True,
    redistribution_allowed=True,
    commercial_use_allowed=False,
    retention_policy_days=None,
    deletion_strategy="Replace when FIFA publishes final schedule",
    source_url="https://www.fifa.com/fifaplus/en/tournaments/mens/worldcup/canadamexicousa2026",
    notes="Dates and venues are approximate until FIFA final confirmation.",
)

_LICENSE_EXPECTED_CALLUPS = SourceLicense(
    source_name="ScoutFootball expected-callup snapshot",
    license_name="MIT (compiled by ScoutFootball maintainer)",
    attribution_required=True,
    redistribution_allowed=True,
    commercial_use_allowed=True,
    retention_policy_days=None,
    deletion_strategy="Overwrite on next snapshot",
    source_url="",
    notes=(
        "Expected call-ups based on recent national team selections and "
        "2025-26 club form.  Replaced by official_roster once FIFA publishes "
        "26-man squads."
    ),
)

_LICENSE_LOCAL_TOURNAMENT_STATE = SourceLicense(
    source_name="ScoutFootball local tournament state",
    license_name="MIT (maintainer-recorded match results)",
    attribution_required=True,
    redistribution_allowed=True,
    commercial_use_allowed=True,
    retention_policy_days=None,
    deletion_strategy="Reset on demand",
    source_url="",
    notes=(
        "Locally recorded group/knockout results entered by the maintainer. "
        "Not an official FIFA result feed."
    ),
)


# ── Builders ─────────────────────────────────────────────────────────────


def _now_utc() -> datetime:
    return datetime.now(tz=UTC)


def build_schedule_snapshot(*, record_count: int) -> SnapshotInfo:
    """Build a :class:`SnapshotInfo` for the 72-match group schedule."""
    return SnapshotInfo(
        snapshot_id=f"{WORLDCUP_ARTIFACT_PREFIX}.schedule.v1",
        as_of=SNAPSHOT_AS_OF_OPTA_PRIORS,
        source_sha256="",  # Static fixture pattern — no upstream hash
        parser_version=PARSER_VERSION_SCHEDULE,
        record_count=record_count,
        generated_at=_now_utc(),
    )


def build_expected_callups_snapshot(*, record_count: int) -> SnapshotInfo:
    """Build a :class:`SnapshotInfo` for the 48-team expected-callup table."""
    return SnapshotInfo(
        snapshot_id=f"{WORLDCUP_ARTIFACT_PREFIX}.expected_callups.v1",
        as_of=SNAPSHOT_AS_OF_EXPECTED_CALLUPS,
        source_sha256="",
        parser_version=PARSER_VERSION_SQUADS,
        record_count=record_count,
        generated_at=_now_utc(),
    )


def build_rating_coverage_snapshot(*, record_count: int) -> SnapshotInfo:
    """Build a :class:`SnapshotInfo` for the per-player rating join."""
    return SnapshotInfo(
        snapshot_id=f"{WORLDCUP_ARTIFACT_PREFIX}.rating_coverage.v1",
        as_of=SNAPSHOT_AS_OF_RATING_COVERAGE,
        source_sha256="",
        parser_version=PARSER_VERSION_RATINGS,
        record_count=record_count,
        generated_at=_now_utc(),
    )


def build_model_probability_snapshot(*, record_count: int) -> SnapshotInfo:
    """Build a :class:`SnapshotInfo` for Bradley-Terry model outputs."""
    return SnapshotInfo(
        snapshot_id=f"{WORLDCUP_ARTIFACT_PREFIX}.model_probability.v1",
        as_of=SNAPSHOT_AS_OF_OPTA_PRIORS,
        source_sha256="",
        parser_version=PARSER_VERSION_STRENGTH,
        record_count=record_count,
        generated_at=_now_utc(),
    )


def build_tournament_state_snapshot(*, record_count: int) -> SnapshotInfo:
    """Build a :class:`SnapshotInfo` for the persisted tournament state."""
    return SnapshotInfo(
        snapshot_id=f"{WORLDCUP_ARTIFACT_PREFIX}.tournament_state.v1",
        as_of=_now_utc(),
        source_sha256="",
        parser_version=PARSER_VERSION_TOURNAMENT_STATE,
        record_count=record_count,
        generated_at=_now_utc(),
    )


def build_expected_callups_lineage(
    *,
    upstream_rating_artifact: str = "rating_feature_matrix",
) -> tuple[LineageEntry, ...]:
    """Lineage for the expected-callup + rating join.

    The expected callups themselves are a static maintainer snapshot, but
    once ratings are joined the artifact depends on the rating feature
    matrix produced by the core pipeline.
    """
    return (
        LineageEntry(
            upstream_id=upstream_rating_artifact,
            upstream_layer="gold",
            downstream_id=f"{WORLDCUP_ARTIFACT_PREFIX}.rating_coverage",
            downstream_layer="worldcup",
            transform="enrich_squad_with_ratings",
            transform_version=PARSER_VERSION_RATINGS,
            recorded_at=_now_utc(),
            status="recorded",
        ),
    )


def build_model_probability_lineage(
    *,
    upstream_rating_artifact: str = "rating_feature_matrix",
) -> tuple[LineageEntry, ...]:
    """Lineage for Bradley-Terry strength and knockout probabilities."""
    return (
        LineageEntry(
            upstream_id=f"{WORLDCUP_ARTIFACT_PREFIX}.rating_coverage",
            upstream_layer="worldcup",
            downstream_id=f"{WORLDCUP_ARTIFACT_PREFIX}.model_probability",
            downstream_layer="worldcup",
            transform="compute_team_strength_details + bradley_terry_montecarlo",
            transform_version=PARSER_VERSION_STRENGTH,
            recorded_at=_now_utc(),
            status="recorded",
        ),
        LineageEntry(
            upstream_id=upstream_rating_artifact,
            upstream_layer="gold",
            downstream_id=f"{WORLDCUP_ARTIFACT_PREFIX}.model_probability",
            downstream_layer="worldcup",
            transform="compute_team_strength_details",
            transform_version=PARSER_VERSION_STRENGTH,
            recorded_at=_now_utc(),
            status="recorded",
        ),
        LineageEntry(
            upstream_id="opta_public_priors",
            upstream_layer="external",
            downstream_id=f"{WORLDCUP_ARTIFACT_PREFIX}.model_probability",
            downstream_layer="worldcup",
            transform="OPTA_WIN_PROBABILITY lookup",
            transform_version="opta.v1",
            recorded_at=_now_utc(),
            status="recorded",
        ),
    )


def build_tournament_state_lineage(
    *,
    upstream_schedule_artifact: str = f"{WORLDCUP_ARTIFACT_PREFIX}.schedule",
) -> tuple[LineageEntry, ...]:
    """Lineage for the persisted tournament state (recorded results)."""
    return (
        LineageEntry(
            upstream_id=upstream_schedule_artifact,
            upstream_layer="worldcup",
            downstream_id=f"{WORLDCUP_ARTIFACT_PREFIX}.tournament_state",
            downstream_layer="worldcup",
            transform="maintainer enters group/knockout results",
            transform_version=PARSER_VERSION_TOURNAMENT_STATE,
            recorded_at=_now_utc(),
            status="recorded",
        ),
    )


# ── Public artifact builders ─────────────────────────────────────────────


def build_schedule_contract(*, record_count: int) -> DataContract:
    """Contract for ``worldcup.schedule`` (72 group-stage fixtures)."""
    return DataContract(
        artifact_id=f"{WORLDCUP_ARTIFACT_PREFIX}.schedule",
        layer="worldcup",
        purpose="Official 2026 FIFA World Cup group-stage fixture pattern.",
        status="delivered",
        license=_LICENSE_FIFA_FIXTURE,
        snapshot=build_schedule_snapshot(record_count=record_count),
        lineage=(),
        coverage=CoverageInfo(
            competition_count=1,
            season_count=1,
            team_count=48,
            player_count=0,
            match_count=record_count,
            date_range_start=datetime(2026, 6, 11, tzinfo=UTC),
            date_range_end=datetime(2026, 7, 19, tzinfo=UTC),
            notes="Group stage only; knockout bracket is generated separately.",
        ),
        primary_keys=("match_id",),
        columns=(),
        recorded=True,
        recorded_note=(
            "Schedule generated from official FIFA fixture pattern; dates "
            "and venues are approximate until FIFA final confirmation."
        ),
    )


def build_expected_callups_contract(*, record_count: int) -> DataContract:
    """Contract for ``worldcup.expected_callups`` (48-team squad lists)."""
    return DataContract(
        artifact_id=f"{WORLDCUP_ARTIFACT_PREFIX}.expected_callups",
        layer="worldcup",
        purpose=(
            "Maintainer-compiled expected call-ups for 48 World Cup teams; "
            "replaced by official_roster once FIFA publishes 26-man squads."
        ),
        status="provisional",
        license=_LICENSE_EXPECTED_CALLUPS,
        snapshot=build_expected_callups_snapshot(record_count=record_count),
        lineage=(),
        coverage=CoverageInfo(
            competition_count=1,
            season_count=1,
            team_count=48,
            player_count=record_count,
            match_count=0,
            date_range_start=None,
            date_range_end=None,
            notes=(
                "Each team lists up to 26 expected call-ups.  Coverage is "
                "planning-only and may include players not in the final "
                "official squad."
            ),
        ),
        primary_keys=("team", "player_name"),
        columns=(),
        recorded=True,
        recorded_note=(
            "Expected call-ups based on recent national team selections "
            "and 2025-26 club form."
        ),
    )


def build_rating_coverage_contract(*, record_count: int) -> DataContract:
    """Contract for ``worldcup.rating_coverage`` (per-player rating join)."""
    return DataContract(
        artifact_id=f"{WORLDCUP_ARTIFACT_PREFIX}.rating_coverage",
        layer="worldcup",
        purpose=(
            "Per-player optimized ratings joined from "
            "player_ratings_optimized onto expected callups."
        ),
        status="delivered",
        license=_LICENSE_FBREF_UNDERSTAT,
        snapshot=build_rating_coverage_snapshot(record_count=record_count),
        lineage=build_expected_callups_lineage(),
        coverage=CoverageInfo(
            competition_count=1,
            season_count=1,
            team_count=48,
            player_count=record_count,
            match_count=0,
            date_range_start=None,
            date_range_end=None,
            notes=(
                "Coverage varies by team.  Non-Big5 league players may lack "
                "rating data and fall back to league proxy ratings."
            ),
        ),
        primary_keys=("team", "player_name"),
        columns=(),
        recorded=True,
        recorded_note=(
            "Ratings derived from FBref/Understat data via ScoutFootball "
            "optimizer.  Non-Big5 league players may lack direct ratings."
        ),
    )


def build_model_probability_contract(*, record_count: int) -> DataContract:
    """Contract for ``worldcup.model_probability`` (Bradley-Terry outputs)."""
    return DataContract(
        artifact_id=f"{WORLDCUP_ARTIFACT_PREFIX}.model_probability",
        layer="worldcup",
        purpose=(
            "Bradley-Terry strength-ratio group predictions and Monte Carlo "
            "knockout probabilities, blended with Opta public priors."
        ),
        status="delivered",
        license=_LICENSE_FBREF_UNDERSTAT,
        snapshot=build_model_probability_snapshot(record_count=record_count),
        lineage=build_model_probability_lineage(),
        coverage=CoverageInfo(
            competition_count=1,
            season_count=1,
            team_count=48,
            player_count=0,
            match_count=0,
            date_range_start=None,
            date_range_end=None,
            notes=(
                "Probabilities are rough estimates from a simplified "
                "strength-ratio model.  Not a real match prediction."
            ),
        ),
        primary_keys=("team",),
        columns=(),
        recorded=True,
        recorded_note=(
            "Model outputs from compute_team_strength_details + "
            "Bradley-Terry Monte Carlo.  Opta priors blended for top teams."
        ),
    )


def build_tournament_state_contract(*, record_count: int) -> DataContract:
    """Contract for ``worldcup.tournament_state`` (persisted results)."""
    return DataContract(
        artifact_id=f"{WORLDCUP_ARTIFACT_PREFIX}.tournament_state",
        layer="worldcup",
        purpose=(
            "Locally recorded group and knockout results entered by the "
            "maintainer.  Not an official FIFA result feed."
        ),
        status="delivered",
        license=_LICENSE_LOCAL_TOURNAMENT_STATE,
        snapshot=build_tournament_state_snapshot(record_count=record_count),
        lineage=build_tournament_state_lineage(),
        coverage=CoverageInfo(
            competition_count=1,
            season_count=1,
            team_count=48,
            player_count=0,
            match_count=record_count,
            date_range_start=datetime(2026, 6, 11, tzinfo=UTC),
            date_range_end=datetime(2026, 7, 19, tzinfo=UTC),
            notes=(
                "record_count is the number of locally recorded results, "
                "not the number of scheduled matches."
            ),
        ),
        primary_keys=("match_id",),
        columns=(),
        recorded=True,
        recorded_note=(
            "Maintainer-recorded results.  Reset clears results but keeps "
            "the schedule."
        ),
    )


def build_official_roster_stub_contract() -> DataContract:
    """Contract stub for ``worldcup.official_roster`` (not yet published)."""
    return DataContract(
        artifact_id=f"{WORLDCUP_ARTIFACT_PREFIX}.official_roster",
        layer="worldcup",
        purpose=(
            "FIFA-published 26-man rosters.  Not yet available for 2026; "
            "expected_callups is used as a provisional stand-in."
        ),
        status="missing",
        license=None,
        snapshot=None,
        lineage=(),
        coverage=None,
        primary_keys=("team", "player_name"),
        columns=(),
        recorded=False,
        recorded_note=(
            "Will be filled when FIFA publishes the official 26-man squads "
            "for the 2026 World Cup."
        ),
    )


def build_injury_report_stub_contract() -> DataContract:
    """Contract stub for ``worldcup.injury_report`` (not tracked locally)."""
    return DataContract(
        artifact_id=f"{WORLDCUP_ARTIFACT_PREFIX}.injury_report",
        layer="worldcup",
        purpose=(
            "Per-player injury status.  Not modelled locally; declared as "
            "not_tracked so consumers know the absence is intentional."
        ),
        status="not_tracked",
        license=None,
        snapshot=None,
        lineage=(),
        coverage=None,
        primary_keys=("team", "player_name"),
        columns=(),
        recorded=False,
        recorded_note=(
            "Injury reports are not ingested by ScoutFootball.  Consumers "
            "must consult official team announcements."
        ),
    )


def build_worldcup_contract_registry(
    *,
    schedule_match_count: int = 72,
    expected_callups_player_count: int = 0,
    rating_coverage_player_count: int = 0,
    model_probability_team_count: int = 48,
    tournament_state_result_count: int = 0,
    include_stubs: bool = True,
) -> tuple[DataContract, ...]:
    """Build the full World Cup contract registry.

    Parameters mirror the live counts returned by the API so the registry
    is reproducible from real state rather than hard-coded.
    """
    contracts: list[DataContract] = [
        build_schedule_contract(record_count=schedule_match_count),
        build_expected_callups_contract(record_count=expected_callups_player_count),
        build_rating_coverage_contract(record_count=rating_coverage_player_count),
        build_model_probability_contract(record_count=model_probability_team_count),
        build_tournament_state_contract(record_count=tournament_state_result_count),
    ]
    if include_stubs:
        contracts.append(build_official_roster_stub_contract())
        contracts.append(build_injury_report_stub_contract())
    return tuple(contracts)


def contract_to_dict(contract: DataContract) -> dict:
    """Serialize a :class:`DataContract` to a JSON-safe dict.

    This is the canonical export shape reused by every World Cup endpoint
    so the World Cup pack does not re-implement export logic per artifact.
    """
    payload: dict = {
        "artifact_id": contract.artifact_id,
        "layer": contract.layer,
        "purpose": contract.purpose,
        "status": contract.status,
        "recorded": contract.recorded,
        "recorded_note": contract.recorded_note,
    }
    if contract.license is not None:
        payload["license"] = contract.license.model_dump(mode="json")
    if contract.snapshot is not None:
        payload["snapshot"] = contract.snapshot.model_dump(mode="json")
    if contract.lineage:
        payload["lineage"] = [entry.model_dump(mode="json") for entry in contract.lineage]
    if contract.coverage is not None:
        payload["coverage"] = contract.coverage.model_dump(mode="json")
    if contract.primary_keys:
        payload["primary_keys"] = list(contract.primary_keys)
    return payload


def contracts_to_dict(contracts: Iterable[DataContract]) -> list[dict]:
    """Serialize a sequence of contracts to a JSON-safe list."""
    return [contract_to_dict(c) for c in contracts]


def fact_type_for_artifact(artifact_id: str) -> WorldCupFactType:
    """Map a World Cup ``artifact_id`` to its :class:`WorldCupFactType`.

    Raises ``ValueError`` for unknown artifact IDs so callers cannot
    silently mis-tag a payload.
    """
    mapping = {
        f"{WORLDCUP_ARTIFACT_PREFIX}.schedule": WorldCupFactType.EXPECTED_CALLUP,
        f"{WORLDCUP_ARTIFACT_PREFIX}.expected_callups": WorldCupFactType.EXPECTED_CALLUP,
        f"{WORLDCUP_ARTIFACT_PREFIX}.official_roster": WorldCupFactType.OFFICIAL_ROSTER,
        f"{WORLDCUP_ARTIFACT_PREFIX}.injury_report": WorldCupFactType.INJURY_REPORT,
        f"{WORLDCUP_ARTIFACT_PREFIX}.rating_coverage": WorldCupFactType.RATING_COVERAGE,
        f"{WORLDCUP_ARTIFACT_PREFIX}.model_probability": WorldCupFactType.MODEL_PROBABILITY,
        f"{WORLDCUP_ARTIFACT_PREFIX}.tournament_state": WorldCupFactType.EXPECTED_CALLUP,
    }
    if artifact_id not in mapping:
        raise ValueError(f"Unknown World Cup artifact id: {artifact_id!r}")
    return mapping[artifact_id]


__all__ = [
    "WorldCupFactType",
    "WORLDCUP_ARTIFACT_PREFIX",
    "SNAPSHOT_AS_OF_EXPECTED_CALLUPS",
    "SNAPSHOT_AS_OF_OPTA_PRIORS",
    "SNAPSHOT_AS_OF_RATING_COVERAGE",
    "PARSER_VERSION_SCHEDULE",
    "PARSER_VERSION_SQUADS",
    "PARSER_VERSION_RATINGS",
    "PARSER_VERSION_STRENGTH",
    "PARSER_VERSION_TOURNAMENT_STATE",
    "build_schedule_contract",
    "build_schedule_snapshot",
    "build_expected_callups_contract",
    "build_expected_callups_snapshot",
    "build_expected_callups_lineage",
    "build_rating_coverage_contract",
    "build_rating_coverage_snapshot",
    "build_model_probability_contract",
    "build_model_probability_snapshot",
    "build_model_probability_lineage",
    "build_tournament_state_contract",
    "build_tournament_state_snapshot",
    "build_tournament_state_lineage",
    "build_official_roster_stub_contract",
    "build_injury_report_stub_contract",
    "build_worldcup_contract_registry",
    "contract_to_dict",
    "contracts_to_dict",
    "fact_type_for_artifact",
]
