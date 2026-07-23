"""Core data contract bindings for the Recruitment pack.

This module is the single re-use point between the Recruitment pack and
the :mod:`scoutfootball.schemas.storage` Core types.  It builds
:class:`DataContract`, :class:`SnapshotInfo` and :class:`LineageEntry`
instances for every Recruitment artifact so the Recruitment pack does
not duplicate identity, snapshot or export logic.

Fact taxonomy
-------------

Recruitment data carries three fact types, declared on each artifact so
consumers can tell maintainer-authored requirements from derived model
recommendations:

``scouting_requirement``
    A maintainer-authored recruitment brief (team, position, role,
    budget, age, contract, league, language, risk preferences).  This
    is a personal local object, not an external fact; it is recorded
    as ``status="delivered"`` once saved.

``role_profile``
    A user-editable role definition with responsibilities and metrics.
    The role ontology is explicitly not a universal truth — fixed
    position weights are not packaged as general facts.  Recorded as
    ``status="provisional"`` because role definitions evolve with the
    maintainer's judgment.

``decision_dossier``
    A decision package for one candidate: supporting evidence,
    counter-evidence, comparison objects, risks, human opinion and
    final recommendation.  Recorded as ``status="delivered"`` once
    the dossier reaches a decision, ``status="draft"`` while still in
    review.

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


class RecruitmentFactType(StrEnum):
    """Three fact types distinguished in Recruitment artifacts."""

    SCOUTING_REQUIREMENT = "scouting_requirement"
    ROLE_PROFILE = "role_profile"
    DECISION_DOSSIER = "decision_dossier"


# ── Static source metadata ───────────────────────────────────────────────


RECRUITMENT_ARTIFACT_PREFIX = "recruitment"

# Parser / generator version stamps.
PARSER_VERSION_BRIEF = "scoutfootball.recruitment.brief.v1"
PARSER_VERSION_ROLE = "scoutfootball.recruitment.role.v1"
PARSER_VERSION_DOSSIER = "scoutfootball.recruitment.dossier.v1"

# The recruitment pack is personal-local: the maintainer authors briefs,
# role profiles and dossiers.  The license reflects that the artifact is
# the maintainer's own work, not external data.  Derived ratings or
# model outputs that appear inside a dossier carry their own upstream
# licenses (FBref/Understat) via lineage, not via this artifact license.
_LICENSE_MAINTAINER_LOCAL = SourceLicense(
    source_name="ScoutFootball maintainer local object",
    license_name="MIT (maintainer-authored)",
    attribution_required=True,
    redistribution_allowed=True,
    commercial_use_allowed=True,
    retention_policy_days=None,
    deletion_strategy="Delete on maintainer request",
    source_url="",
    notes=(
        "Personal local recruitment object authored by the ScoutFootball "
        "maintainer.  Not external data; derived ratings or model outputs "
        "embedded inside a dossier carry their own upstream licenses via "
        "lineage."
    ),
)


# ── Builders ─────────────────────────────────────────────────────────────


def _now_utc() -> datetime:
    return datetime.now(tz=UTC)


def build_brief_snapshot(*, record_count: int = 1) -> SnapshotInfo:
    """Build a :class:`SnapshotInfo` for a saved recruitment brief."""
    return SnapshotInfo(
        snapshot_id=f"{RECRUITMENT_ARTIFACT_PREFIX}.brief.v1",
        as_of=_now_utc(),
        source_sha256="",
        parser_version=PARSER_VERSION_BRIEF,
        record_count=record_count,
        generated_at=_now_utc(),
    )


def build_role_profile_snapshot(*, record_count: int = 1) -> SnapshotInfo:
    """Build a :class:`SnapshotInfo` for a saved role profile."""
    return SnapshotInfo(
        snapshot_id=f"{RECRUITMENT_ARTIFACT_PREFIX}.role_profile.v1",
        as_of=_now_utc(),
        source_sha256="",
        parser_version=PARSER_VERSION_ROLE,
        record_count=record_count,
        generated_at=_now_utc(),
    )


def build_decision_dossier_snapshot(*, record_count: int = 1) -> SnapshotInfo:
    """Build a :class:`SnapshotInfo` for a saved decision dossier."""
    return SnapshotInfo(
        snapshot_id=f"{RECRUITMENT_ARTIFACT_PREFIX}.decision_dossier.v1",
        as_of=_now_utc(),
        source_sha256="",
        parser_version=PARSER_VERSION_DOSSIER,
        record_count=record_count,
        generated_at=_now_utc(),
    )


def build_decision_dossier_lineage(
    *,
    upstream_rating_artifact: str = "rating_feature_matrix",
    upstream_brief_artifact: str = f"{RECRUITMENT_ARTIFACT_PREFIX}.brief",
) -> tuple[LineageEntry, ...]:
    """Lineage for a decision dossier.

    A dossier depends on the brief that defines the requirement and on
    the rating feature matrix that produced the candidate's optimized
    score.  Both upstreams are recorded so a reviewer can trace why a
    candidate appeared and against which requirement.
    """
    return (
        LineageEntry(
            upstream_id=upstream_brief_artifact,
            upstream_layer="recruitment",
            downstream_id=f"{RECRUITMENT_ARTIFACT_PREFIX}.decision_dossier",
            downstream_layer="recruitment",
            transform="match_candidate_to_brief_requirement",
            transform_version=PARSER_VERSION_DOSSIER,
            recorded_at=_now_utc(),
            status="recorded",
        ),
        LineageEntry(
            upstream_id=upstream_rating_artifact,
            upstream_layer="gold",
            downstream_id=f"{RECRUITMENT_ARTIFACT_PREFIX}.decision_dossier",
            downstream_layer="recruitment",
            transform="attach_optimized_score_and_confidence",
            transform_version=PARSER_VERSION_DOSSIER,
            recorded_at=_now_utc(),
            status="recorded",
        ),
    )


# ── Public artifact builders ─────────────────────────────────────────────


def build_brief_contract(*, record_count: int = 1) -> DataContract:
    """Contract for ``recruitment.brief`` (maintainer-authored requirement)."""
    return DataContract(
        artifact_id=f"{RECRUITMENT_ARTIFACT_PREFIX}.brief",
        layer="recruitment",
        purpose=(
            "Maintainer-authored recruitment brief: team, position, role, "
            "budget, age, contract, league, language and risk preferences. "
            "A personal local object, not an external fact."
        ),
        status="delivered",
        license=_LICENSE_MAINTAINER_LOCAL,
        snapshot=build_brief_snapshot(record_count=record_count),
        lineage=(),
        coverage=CoverageInfo(
            competition_count=0,
            season_count=0,
            team_count=0,
            player_count=0,
            match_count=0,
            date_range_start=None,
            date_range_end=None,
            notes=(
                "A brief describes a requirement, not a dataset.  Coverage "
                "is the responsibility of the candidate search that consumes "
                "the brief."
            ),
        ),
        primary_keys=("brief_id",),
        columns=(),
        recorded=True,
        recorded_note=(
            "Brief authored by the ScoutFootball maintainer.  Versioned via "
            "brief_id and revision; old revisions are kept in local backups."
        ),
    )


def build_role_profile_contract(*, record_count: int = 1) -> DataContract:
    """Contract for ``recruitment.role_profile`` (user-editable role ontology)."""
    return DataContract(
        artifact_id=f"{RECRUITMENT_ARTIFACT_PREFIX}.role_profile",
        layer="recruitment",
        purpose=(
            "User-editable role definition with responsibilities and metrics. "
            "The role ontology is explicitly not a universal truth; fixed "
            "position weights are not packaged as general facts."
        ),
        status="provisional",
        license=_LICENSE_MAINTAINER_LOCAL,
        snapshot=build_role_profile_snapshot(record_count=record_count),
        lineage=(),
        coverage=CoverageInfo(
            competition_count=0,
            season_count=0,
            team_count=0,
            player_count=0,
            match_count=0,
            date_range_start=None,
            date_range_end=None,
            notes=(
                "A role profile describes a subjective role definition.  "
                "Coverage is not applicable; the profile evolves with the "
                "maintainer's judgment."
            ),
        ),
        primary_keys=("role_id",),
        columns=(),
        recorded=True,
        recorded_note=(
            "Role profile authored by the maintainer.  Status is provisional "
            "because role definitions evolve; revisioned via role_id."
        ),
    )


def build_decision_dossier_contract(*, record_count: int = 1) -> DataContract:
    """Contract for ``recruitment.decision_dossier`` (candidate decision package)."""
    return DataContract(
        artifact_id=f"{RECRUITMENT_ARTIFACT_PREFIX}.decision_dossier",
        layer="recruitment",
        purpose=(
            "Decision package for one candidate: supporting evidence, "
            "counter-evidence, comparison objects, risks, human opinion and "
            "final recommendation.  Status is draft while in review, "
            "delivered once a decision is reached."
        ),
        status="delivered",
        license=_LICENSE_MAINTAINER_LOCAL,
        snapshot=build_decision_dossier_snapshot(record_count=record_count),
        lineage=build_decision_dossier_lineage(),
        coverage=CoverageInfo(
            competition_count=0,
            season_count=0,
            team_count=0,
            player_count=record_count,
            match_count=0,
            date_range_start=None,
            date_range_end=None,
            notes=(
                "A dossier covers one candidate.  Derived ratings and model "
                "outputs inside the dossier carry their own upstream licenses "
                "via lineage; the dossier artifact itself is a maintainer "
                "local object."
            ),
        ),
        primary_keys=("dossier_id",),
        columns=(),
        recorded=True,
        recorded_note=(
            "Dossier authored by the maintainer.  Lineage records the brief "
            "and rating feature matrix that produced the candidate context."
        ),
    )


def build_recruitment_contract_registry(
    *,
    brief_count: int = 0,
    role_profile_count: int = 0,
    decision_dossier_count: int = 0,
) -> tuple[DataContract, ...]:
    """Build the full Recruitment contract registry.

    Parameters mirror the live counts returned by the store so the
    registry is reproducible from real state rather than hard-coded.
    """
    contracts: list[DataContract] = []
    if brief_count > 0:
        contracts.append(build_brief_contract(record_count=brief_count))
    if role_profile_count > 0:
        contracts.append(build_role_profile_contract(record_count=role_profile_count))
    if decision_dossier_count > 0:
        contracts.append(
            build_decision_dossier_contract(record_count=decision_dossier_count)
        )
    return tuple(contracts)


def contract_to_dict(contract: DataContract) -> dict:
    """Serialize a :class:`DataContract` to a JSON-safe dict.

    Mirrors the World Cup pack serializer so the Recruitment pack does
    not re-implement export logic per artifact.
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


def fact_type_for_artifact(artifact_id: str) -> RecruitmentFactType:
    """Map a Recruitment ``artifact_id`` to its :class:`RecruitmentFactType`.

    Raises ``ValueError`` for unknown artifact IDs so callers cannot
    silently mis-tag a payload.
    """
    mapping = {
        f"{RECRUITMENT_ARTIFACT_PREFIX}.brief": RecruitmentFactType.SCOUTING_REQUIREMENT,
        f"{RECRUITMENT_ARTIFACT_PREFIX}.role_profile": RecruitmentFactType.ROLE_PROFILE,
        f"{RECRUITMENT_ARTIFACT_PREFIX}.decision_dossier": RecruitmentFactType.DECISION_DOSSIER,
    }
    if artifact_id not in mapping:
        raise ValueError(f"Unknown Recruitment artifact id: {artifact_id!r}")
    return mapping[artifact_id]


__all__ = [
    "RecruitmentFactType",
    "RECRUITMENT_ARTIFACT_PREFIX",
    "PARSER_VERSION_BRIEF",
    "PARSER_VERSION_ROLE",
    "PARSER_VERSION_DOSSIER",
    "build_brief_contract",
    "build_brief_snapshot",
    "build_role_profile_contract",
    "build_role_profile_snapshot",
    "build_decision_dossier_contract",
    "build_decision_dossier_snapshot",
    "build_decision_dossier_lineage",
    "build_recruitment_contract_registry",
    "contract_to_dict",
    "contracts_to_dict",
    "fact_type_for_artifact",
]
