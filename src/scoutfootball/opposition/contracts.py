"""Core data contract bindings for the Opposition & Match pack.

This module is the single re-use point between the Opposition & Match
pack and the :mod:`scoutfootball.schemas.storage` Core types.  It builds
:class:`DataContract`, :class:`SnapshotInfo` and :class:`LineageEntry`
instances for every Opposition artifact so the pack does not duplicate
identity, snapshot or export logic.

Fact taxonomy
-------------

Opposition & Match data carries four fact types, declared on each
artifact so consumers can tell source-limited briefings from derived
pattern cards, scenario trees and post-match reviews:

``match_briefing``
    A source-limited briefing for one upcoming match.  Each fact
    section (opponent strength, recent form, key players, set pieces,
    injuries, tactical notes) carries an explicit ``fact_tier`` of
    ``official`` / ``recorded`` / ``estimated`` / ``unknown`` so the
    reviewer can never confuse an official squad list with a
    maintainer estimate.  Recorded as ``status="delivered"`` once
    saved.

``pattern_card``
    A recurring opponent pattern linked to match evidence and video
    timecodes.  Records sample count, opponent / score state and a
    qualitative stability label.  Recorded as ``status="provisional"``
    because patterns are working hypotheses, not certified truths.

``scenario_tree``
    A scenario tree connecting the tactical board to match states
    (leading / trailing, different formations, absences, set pieces).
    Recorded as ``status="provisional"`` because scenario branches
    are planning artifacts, not predictions.

``post_match_review``
    A post-match review comparing hypothesis-plan-execution-result,
    recording falsified patterns and new questions.  Recorded as
    ``status="delivered"`` once the review is closed.

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


class OppositionFactType(StrEnum):
    """Four fact types distinguished in Opposition & Match artifacts."""

    MATCH_BRIEFING = "match_briefing"
    PATTERN_CARD = "pattern_card"
    SCENARIO_TREE = "scenario_tree"
    POST_MATCH_REVIEW = "post_match_review"


# ── Static source metadata ───────────────────────────────────────────────


OPPOSITION_ARTIFACT_PREFIX = "opposition"

# Parser / generator version stamps.
PARSER_VERSION_BRIEFING = "scoutfootball.opposition.briefing.v1"
PARSER_VERSION_PATTERN = "scoutfootball.opposition.pattern.v1"
PARSER_VERSION_SCENARIO = "scoutfootball.opposition.scenario.v1"
PARSER_VERSION_REVIEW = "scoutfootball.opposition.review.v1"

# The opposition pack is personal-local: the maintainer authors briefings,
# pattern cards, scenario trees and post-match reviews.  The license
# reflects that the artifact is the maintainer's own work, not external
# data.  Model probabilities or external facts that appear inside a
# briefing carry their own upstream licenses (StatsBomb / FBref /
# Understat) via lineage, not via this artifact license.
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
        "Personal local opposition & match object authored by the "
        "ScoutFootball maintainer.  Not external data; model probabilities "
        "or external facts embedded inside a briefing carry their own "
        "upstream licenses via lineage."
    ),
)


# ── Builders ─────────────────────────────────────────────────────────────


def _now_utc() -> datetime:
    return datetime.now(tz=UTC)


def build_briefing_snapshot(*, record_count: int = 1) -> SnapshotInfo:
    """Build a :class:`SnapshotInfo` for a saved match briefing."""
    return SnapshotInfo(
        snapshot_id=f"{OPPOSITION_ARTIFACT_PREFIX}.briefing.v1",
        as_of=_now_utc(),
        source_sha256="",
        parser_version=PARSER_VERSION_BRIEFING,
        record_count=record_count,
        generated_at=_now_utc(),
    )


def build_pattern_card_snapshot(*, record_count: int = 1) -> SnapshotInfo:
    """Build a :class:`SnapshotInfo` for a saved pattern card."""
    return SnapshotInfo(
        snapshot_id=f"{OPPOSITION_ARTIFACT_PREFIX}.pattern_card.v1",
        as_of=_now_utc(),
        source_sha256="",
        parser_version=PARSER_VERSION_PATTERN,
        record_count=record_count,
        generated_at=_now_utc(),
    )


def build_scenario_tree_snapshot(*, record_count: int = 1) -> SnapshotInfo:
    """Build a :class:`SnapshotInfo` for a saved scenario tree."""
    return SnapshotInfo(
        snapshot_id=f"{OPPOSITION_ARTIFACT_PREFIX}.scenario_tree.v1",
        as_of=_now_utc(),
        source_sha256="",
        parser_version=PARSER_VERSION_SCENARIO,
        record_count=record_count,
        generated_at=_now_utc(),
    )


def build_post_match_review_snapshot(*, record_count: int = 1) -> SnapshotInfo:
    """Build a :class:`SnapshotInfo` for a saved post-match review."""
    return SnapshotInfo(
        snapshot_id=f"{OPPOSITION_ARTIFACT_PREFIX}.post_match_review.v1",
        as_of=_now_utc(),
        source_sha256="",
        parser_version=PARSER_VERSION_REVIEW,
        record_count=record_count,
        generated_at=_now_utc(),
    )


def build_pattern_card_lineage(
    *,
    upstream_briefing_artifact: str = f"{OPPOSITION_ARTIFACT_PREFIX}.briefing",
    upstream_events_artifact: str = "silver.facts.events",
) -> tuple[LineageEntry, ...]:
    """Lineage for a pattern card.

    A pattern card depends on the briefing that scopes the match context
    and on the event layer that produced the actions and video timecodes
    referenced by the pattern.  Both upstreams are recorded so a reviewer
    can trace why a pattern appeared and which event snapshot it was
    derived from.
    """
    return (
        LineageEntry(
            upstream_id=upstream_briefing_artifact,
            upstream_layer="opposition",
            downstream_id=f"{OPPOSITION_ARTIFACT_PREFIX}.pattern_card",
            downstream_layer="opposition",
            transform="extract_pattern_from_briefing_context",
            transform_version=PARSER_VERSION_PATTERN,
            recorded_at=_now_utc(),
            status="recorded",
        ),
        LineageEntry(
            upstream_id=upstream_events_artifact,
            upstream_layer="silver",
            downstream_id=f"{OPPOSITION_ARTIFACT_PREFIX}.pattern_card",
            downstream_layer="opposition",
            transform="cluster_actions_into_pattern",
            transform_version=PARSER_VERSION_PATTERN,
            recorded_at=_now_utc(),
            status="recorded",
        ),
    )


def build_scenario_tree_lineage(
    *,
    upstream_briefing_artifact: str = f"{OPPOSITION_ARTIFACT_PREFIX}.briefing",
    upstream_pattern_artifact: str = f"{OPPOSITION_ARTIFACT_PREFIX}.pattern_card",
) -> tuple[LineageEntry, ...]:
    """Lineage for a scenario tree.

    A scenario tree depends on the briefing that scopes the match context
    and on the pattern cards that populate its branches.  Both upstreams
    are recorded so a reviewer can trace which patterns informed each
    scenario branch.
    """
    return (
        LineageEntry(
            upstream_id=upstream_briefing_artifact,
            upstream_layer="opposition",
            downstream_id=f"{OPPOSITION_ARTIFACT_PREFIX}.scenario_tree",
            downstream_layer="opposition",
            transform="branch_briefing_into_scenarios",
            transform_version=PARSER_VERSION_SCENARIO,
            recorded_at=_now_utc(),
            status="recorded",
        ),
        LineageEntry(
            upstream_id=upstream_pattern_artifact,
            upstream_layer="opposition",
            downstream_id=f"{OPPOSITION_ARTIFACT_PREFIX}.scenario_tree",
            downstream_layer="opposition",
            transform="attach_pattern_to_branch",
            transform_version=PARSER_VERSION_SCENARIO,
            recorded_at=_now_utc(),
            status="recorded",
        ),
    )


def build_post_match_review_lineage(
    *,
    upstream_briefing_artifact: str = f"{OPPOSITION_ARTIFACT_PREFIX}.briefing",
    upstream_scenario_artifact: str = f"{OPPOSITION_ARTIFACT_PREFIX}.scenario_tree",
    upstream_result_artifact: str = "silver.facts.matches",
) -> tuple[LineageEntry, ...]:
    """Lineage for a post-match review.

    A review depends on the briefing (hypothesis), the scenario tree
    (plan), and the silver match facts (execution / result).  All three
    upstreams are recorded so the review can compare hypothesis-plan-
    execution-result without losing traceability.
    """
    return (
        LineageEntry(
            upstream_id=upstream_briefing_artifact,
            upstream_layer="opposition",
            downstream_id=f"{OPPOSITION_ARTIFACT_PREFIX}.post_match_review",
            downstream_layer="opposition",
            transform="load_hypothesis_from_briefing",
            transform_version=PARSER_VERSION_REVIEW,
            recorded_at=_now_utc(),
            status="recorded",
        ),
        LineageEntry(
            upstream_id=upstream_scenario_artifact,
            upstream_layer="opposition",
            downstream_id=f"{OPPOSITION_ARTIFACT_PREFIX}.post_match_review",
            downstream_layer="opposition",
            transform="load_plan_from_scenario_tree",
            transform_version=PARSER_VERSION_REVIEW,
            recorded_at=_now_utc(),
            status="recorded",
        ),
        LineageEntry(
            upstream_id=upstream_result_artifact,
            upstream_layer="silver",
            downstream_id=f"{OPPOSITION_ARTIFACT_PREFIX}.post_match_review",
            downstream_layer="opposition",
            transform="load_execution_and_result_from_match_facts",
            transform_version=PARSER_VERSION_REVIEW,
            recorded_at=_now_utc(),
            status="recorded",
        ),
    )


# ── Public artifact builders ─────────────────────────────────────────────


def build_briefing_contract(*, record_count: int = 1) -> DataContract:
    """Contract for ``opposition.briefing`` (source-limited match briefing)."""
    return DataContract(
        artifact_id=f"{OPPOSITION_ARTIFACT_PREFIX}.briefing",
        layer="opposition",
        purpose=(
            "Source-limited match briefing: each fact section carries an "
            "explicit fact_tier of official / recorded / estimated / "
            "unknown.  Personal local object, not an external fact."
        ),
        status="delivered",
        license=_LICENSE_MAINTAINER_LOCAL,
        snapshot=build_briefing_snapshot(record_count=record_count),
        lineage=(),
        coverage=CoverageInfo(
            competition_count=0,
            season_count=0,
            team_count=0,
            player_count=0,
            match_count=record_count,
            date_range_start=None,
            date_range_end=None,
            notes=(
                "A briefing covers one upcoming match.  External facts "
                "embedded inside a briefing carry their own upstream "
                "licenses via lineage; the briefing artifact itself is a "
                "maintainer local object."
            ),
        ),
        primary_keys=("briefing_id",),
        columns=(),
        recorded=True,
        recorded_note=(
            "Briefing authored by the ScoutFootball maintainer.  Versioned "
            "via briefing_id and revision; old revisions are kept in local "
            "backups.  Each fact section's fact_tier is the maintainer's "
            "honest classification, not an automated guess."
        ),
    )


def build_pattern_card_contract(*, record_count: int = 1) -> DataContract:
    """Contract for ``opposition.pattern_card`` (recurring opponent pattern)."""
    return DataContract(
        artifact_id=f"{OPPOSITION_ARTIFACT_PREFIX}.pattern_card",
        layer="opposition",
        purpose=(
            "Recurring opponent pattern with sample count, opponent / "
            "score state, stability label and links to match evidence "
            "and video timecodes.  A working hypothesis, not a certified "
            "truth."
        ),
        status="provisional",
        license=_LICENSE_MAINTAINER_LOCAL,
        snapshot=build_pattern_card_snapshot(record_count=record_count),
        lineage=build_pattern_card_lineage(),
        coverage=CoverageInfo(
            competition_count=0,
            season_count=0,
            team_count=0,
            player_count=0,
            match_count=0,
            date_range_start=None,
            date_range_end=None,
            notes=(
                "A pattern card describes a recurring pattern.  Coverage "
                "is the responsibility of the sample list attached to the "
                "card; low sample counts must lower confidence."
            ),
        ),
        primary_keys=("pattern_id",),
        columns=(),
        recorded=True,
        recorded_note=(
            "Pattern card authored by the maintainer.  Status is "
            "provisional because patterns are working hypotheses; "
            "revisioned via pattern_id."
        ),
    )


def build_scenario_tree_contract(*, record_count: int = 1) -> DataContract:
    """Contract for ``opposition.scenario_tree`` (tactical board scenarios)."""
    return DataContract(
        artifact_id=f"{OPPOSITION_ARTIFACT_PREFIX}.scenario_tree",
        layer="opposition",
        purpose=(
            "Scenario tree connecting the tactical board to match states: "
            "leading / trailing, different formations, absences and set "
            "pieces.  A planning artifact, not a prediction."
        ),
        status="provisional",
        license=_LICENSE_MAINTAINER_LOCAL,
        snapshot=build_scenario_tree_snapshot(record_count=record_count),
        lineage=build_scenario_tree_lineage(),
        coverage=CoverageInfo(
            competition_count=0,
            season_count=0,
            team_count=0,
            player_count=0,
            match_count=0,
            date_range_start=None,
            date_range_end=None,
            notes=(
                "A scenario tree covers one match's planning branches.  "
                "Coverage is not applicable; branches evolve with the "
                "maintainer's judgment."
            ),
        ),
        primary_keys=("scenario_id",),
        columns=(),
        recorded=True,
        recorded_note=(
            "Scenario tree authored by the maintainer.  Status is "
            "provisional because scenario branches are planning "
            "artifacts; revisioned via scenario_id."
        ),
    )


def build_post_match_review_contract(*, record_count: int = 1) -> DataContract:
    """Contract for ``opposition.post_match_review`` (post-match review)."""
    return DataContract(
        artifact_id=f"{OPPOSITION_ARTIFACT_PREFIX}.post_match_review",
        layer="opposition",
        purpose=(
            "Post-match review comparing hypothesis-plan-execution-result. "
            "Records falsified patterns and new questions.  Closed once "
            "the review reaches a decision."
        ),
        status="delivered",
        license=_LICENSE_MAINTAINER_LOCAL,
        snapshot=build_post_match_review_snapshot(record_count=record_count),
        lineage=build_post_match_review_lineage(),
        coverage=CoverageInfo(
            competition_count=0,
            season_count=0,
            team_count=0,
            player_count=0,
            match_count=record_count,
            date_range_start=None,
            date_range_end=None,
            notes=(
                "A review covers one played match.  External match facts "
                "embedded inside the review carry their own upstream "
                "licenses via lineage; the review artifact itself is a "
                "maintainer local object."
            ),
        ),
        primary_keys=("review_id",),
        columns=(),
        recorded=True,
        recorded_note=(
            "Review authored by the maintainer.  Lineage records the "
            "briefing (hypothesis), scenario tree (plan) and silver match "
            "facts (execution / result) that produced the review context."
        ),
    )


def build_opposition_contract_registry(
    *,
    briefing_count: int = 0,
    pattern_card_count: int = 0,
    scenario_tree_count: int = 0,
    post_match_review_count: int = 0,
) -> tuple[DataContract, ...]:
    """Build the full Opposition & Match contract registry.

    Parameters mirror the live counts returned by the store so the
    registry is reproducible from real state rather than hard-coded.
    """
    contracts: list[DataContract] = []
    if briefing_count > 0:
        contracts.append(build_briefing_contract(record_count=briefing_count))
    if pattern_card_count > 0:
        contracts.append(build_pattern_card_contract(record_count=pattern_card_count))
    if scenario_tree_count > 0:
        contracts.append(build_scenario_tree_contract(record_count=scenario_tree_count))
    if post_match_review_count > 0:
        contracts.append(
            build_post_match_review_contract(record_count=post_match_review_count)
        )
    return tuple(contracts)


def contract_to_dict(contract: DataContract) -> dict:
    """Serialize a :class:`DataContract` to a JSON-safe dict.

    Mirrors the Recruitment pack serializer so the Opposition pack does
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


def fact_type_for_artifact(artifact_id: str) -> OppositionFactType:
    """Map an Opposition ``artifact_id`` to its :class:`OppositionFactType`.

    Raises ``ValueError`` for unknown artifact IDs so callers cannot
    silently mis-tag a payload.
    """
    mapping = {
        f"{OPPOSITION_ARTIFACT_PREFIX}.briefing": OppositionFactType.MATCH_BRIEFING,
        f"{OPPOSITION_ARTIFACT_PREFIX}.pattern_card": OppositionFactType.PATTERN_CARD,
        f"{OPPOSITION_ARTIFACT_PREFIX}.scenario_tree": OppositionFactType.SCENARIO_TREE,
        f"{OPPOSITION_ARTIFACT_PREFIX}.post_match_review": OppositionFactType.POST_MATCH_REVIEW,
    }
    if artifact_id not in mapping:
        raise ValueError(f"Unknown Opposition artifact id: {artifact_id!r}")
    return mapping[artifact_id]


__all__ = [
    "OppositionFactType",
    "OPPOSITION_ARTIFACT_PREFIX",
    "PARSER_VERSION_BRIEFING",
    "PARSER_VERSION_PATTERN",
    "PARSER_VERSION_SCENARIO",
    "PARSER_VERSION_REVIEW",
    "build_briefing_contract",
    "build_briefing_snapshot",
    "build_pattern_card_contract",
    "build_pattern_card_snapshot",
    "build_pattern_card_lineage",
    "build_scenario_tree_contract",
    "build_scenario_tree_snapshot",
    "build_scenario_tree_lineage",
    "build_post_match_review_contract",
    "build_post_match_review_snapshot",
    "build_post_match_review_lineage",
    "build_opposition_contract_registry",
    "contract_to_dict",
    "contracts_to_dict",
    "fact_type_for_artifact",
]
