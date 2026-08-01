"""Versioned decision dossier: maintainer-authored candidate decision package.

A dossier is the closing artifact of the recruitment workflow.  It takes
a :class:`~scoutfootball.recruitment.brief.RecruitmentBrief` (the
requirement) and one candidate player, then collects the maintainer's
honest assessment: supporting evidence, counter-evidence, comparison
objects, risks, free-form human opinion and a final recommendation.

The dossier is a personal local object, not an external fact.  It is
versioned via ``dossier_id`` and ``revision``; old revisions are kept
in local backups by the store.  The schema is deliberately explicit
about the workflow state — ``status`` moves from ``draft`` to
``decided`` / ``rejected`` / ``superseded``, and ``decision`` is only
meaningful once ``status == "decided"``.

Evidence sections (supporting, counter, comparison, risk) each carry
an explicit ``fact_tier`` of ``official`` / ``recorded`` /
``estimated`` / ``unknown`` so a reviewer can never confuse an official
squad announcement with a maintainer estimate.  This reuses the
fact-tier taxonomy from :mod:`scoutfootball.opposition.briefing` so the
recruitment and opposition packs share one honest-source vocabulary.

Schema
------

``scoutfootball.recruitment-decision-dossier`` version ``1.0.0``::

    {
      "schema": "scoutfootball.recruitment-decision-dossier",
      "version": "1.0.0",
      "dossier_id": "dossier-2026-07-24-abc123",
      "revision": 1,
      "created_at": "2026-07-24T10:00:00+00:00",
      "updated_at": "2026-07-24T10:00:00+00:00",
      "author": "maintainer",
      "title": "Decision dossier: Player X for Arsenal LB",
      "brief_id": "brief-2026-07-23-abc123",
      "candidate_player_id": "understat|1234",
      "candidate_player_name": "Player X",
      "candidate_team_name": "Current Club Y",
      "candidate_season_id": "2425",
      "status": "draft",
      "decision": null,
      "decision_note": "",
      "supporting_evidence": [
        {
          "evidence_id": "ev-001",
          "fact_tier": "recorded",
          "summary": "Top 5% in crosses p90 over 2425 season.",
          "evidence_refs": ["fbref/2425/PlayerX"]
        }
      ],
      "counter_evidence": [],
      "comparisons": [],
      "risks": [],
      "human_opinion": "",
      "recommendation": "",
      "linked_artifacts": [],
      "notes": "",
      "limitations": [
        "Dossier is a personal local object; not an external fact.",
        "Decision is the maintainer's honest judgment, not an automated recommendation."
      ]
    }
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DOSSIER_SCHEMA = "scoutfootball.recruitment-decision-dossier"
DOSSIER_VERSION = "1.0.0"
MAX_DOSSIER_BYTES = 200_000  # 200 KB local limit; dossiers carry evidence refs
VALID_FACT_TIERS = {"official", "recorded", "estimated", "unknown"}
VALID_DOSSIER_STATUS = {"draft", "decided", "rejected", "superseded"}
VALID_DECISION_VALUES = {"proceed", "hold", "reject", "defer"}
VALID_RISK_SEVERITY = {"low", "medium", "high"}


class DossierValidationError(ValueError):
    """Raised when a dossier payload fails schema or semantic validation."""


class _EvidenceItem(BaseModel):
    """One piece of evidence (supporting or counter) inside a dossier.

    The ``fact_tier`` is the maintainer's honest classification of how
    well-sourced the item is, not an automated guess.  ``official``
    means an authoritative source (e.g. an official squad list, an
    announced transfer fee); ``recorded`` means a verified local
    artifact (e.g. a row in ``player_match.parquet``); ``estimated``
    means a maintainer estimate or model output; ``unknown`` means the
    maintainer has not yet classified it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str = Field(min_length=1, max_length=64)
    fact_tier: str = Field(default="unknown")
    summary: str = Field(default="", max_length=4000)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("fact_tier")
    @classmethod
    def _validate_fact_tier(cls, value: str) -> str:
        if value not in VALID_FACT_TIERS:
            raise DossierValidationError(
                f"invalid fact_tier: {value!r} "
                f"(must be one of {sorted(VALID_FACT_TIERS)})"
            )
        return value


class _ComparisonItem(BaseModel):
    """One comparison object inside a dossier.

    A comparison points at another candidate (``comparison_player_id``)
    and summarises how they differ from the primary candidate.  Like
    evidence items, comparisons carry a ``fact_tier`` so the maintainer
    can distinguish a like-for-like stat comparison (``recorded``) from
    a stylistic judgment (``estimated``).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    comparison_id: str = Field(min_length=1, max_length=64)
    comparison_player_id: str = Field(default="", max_length=128)
    comparison_player_name: str = Field(default="", max_length=128)
    fact_tier: str = Field(default="unknown")
    summary: str = Field(default="", max_length=4000)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("fact_tier")
    @classmethod
    def _validate_fact_tier(cls, value: str) -> str:
        if value not in VALID_FACT_TIERS:
            raise DossierValidationError(
                f"invalid fact_tier: {value!r} "
                f"(must be one of {sorted(VALID_FACT_TIERS)})"
            )
        return value


class _RiskItem(BaseModel):
    """One risk entry inside a dossier.

    ``severity`` is the maintainer's honest severity classification
    (low/medium/high), not an automated score.  Risks are evidence
    themselves, so they carry ``fact_tier`` and ``evidence_refs`` just
    like supporting/counter evidence.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    risk_id: str = Field(min_length=1, max_length=64)
    summary: str = Field(min_length=1, max_length=2000)
    severity: str = Field(default="medium")
    fact_tier: str = Field(default="unknown")
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("severity")
    @classmethod
    def _validate_severity(cls, value: str) -> str:
        if value not in VALID_RISK_SEVERITY:
            raise DossierValidationError(
                f"invalid severity: {value!r} "
                f"(must be one of {sorted(VALID_RISK_SEVERITY)})"
            )
        return value

    @field_validator("fact_tier")
    @classmethod
    def _validate_fact_tier(cls, value: str) -> str:
        if value not in VALID_FACT_TIERS:
            raise DossierValidationError(
                f"invalid fact_tier: {value!r} "
                f"(must be one of {sorted(VALID_FACT_TIERS)})"
            )
        return value


class DecisionDossier(BaseModel):
    """Pydantic model for a versioned candidate decision dossier.

    The model is the single source of truth for dossier shape: the
    store, CLI and API all round-trip through ``model_dump`` /
    ``model_validate`` so there is no separate hand-rolled serialization.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    schema_name: str = Field(default=DOSSIER_SCHEMA, alias="schema")
    version: str = Field(default=DOSSIER_VERSION)
    dossier_id: str = Field(min_length=1, max_length=128)
    revision: int = Field(default=1, ge=1)
    created_at: datetime
    updated_at: datetime
    author: str = Field(default="maintainer", min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    brief_id: str = Field(default="", max_length=128)
    candidate_player_id: str = Field(default="", max_length=128)
    candidate_player_name: str = Field(default="", max_length=128)
    candidate_team_name: str = Field(default="", max_length=128)
    candidate_season_id: str = Field(default="", max_length=32)
    status: str = Field(default="draft")
    decision: str | None = Field(default=None)
    decision_note: str = Field(default="", max_length=4000)
    supporting_evidence: tuple[_EvidenceItem, ...] = Field(default_factory=tuple)
    counter_evidence: tuple[_EvidenceItem, ...] = Field(default_factory=tuple)
    comparisons: tuple[_ComparisonItem, ...] = Field(default_factory=tuple)
    risks: tuple[_RiskItem, ...] = Field(default_factory=tuple)
    human_opinion: str = Field(default="", max_length=8000)
    recommendation: str = Field(default="", max_length=4000)
    linked_artifacts: tuple[str, ...] = Field(default_factory=tuple)
    notes: str = Field(default="", max_length=4000)
    limitations: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("schema_name")
    @classmethod
    def _validate_schema(cls, value: str) -> str:
        if value != DOSSIER_SCHEMA:
            raise DossierValidationError(
                f"unsupported dossier schema: {value!r} (expected {DOSSIER_SCHEMA!r})"
            )
        return value

    @field_validator("version")
    @classmethod
    def _validate_version(cls, value: str) -> str:
        if value != DOSSIER_VERSION:
            raise DossierValidationError(
                f"unsupported dossier version: {value!r} (expected {DOSSIER_VERSION!r})"
            )
        return value

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        if value not in VALID_DOSSIER_STATUS:
            raise DossierValidationError(
                f"invalid status: {value!r} "
                f"(must be one of {sorted(VALID_DOSSIER_STATUS)})"
            )
        return value

    @field_validator("decision")
    @classmethod
    def _validate_decision(cls, value: str | None) -> str | None:
        if value is not None and value not in VALID_DECISION_VALUES:
            raise DossierValidationError(
                f"invalid decision: {value!r} "
                f"(must be one of {sorted(VALID_DECISION_VALUES)} or null)"
            )
        return value

    @field_validator("supporting_evidence")
    @classmethod
    def _validate_supporting_evidence_ids_unique(
        cls, value: tuple[_EvidenceItem, ...]
    ) -> tuple[_EvidenceItem, ...]:
        return _ensure_unique_ids(value, "evidence_id", "supporting_evidence")

    @field_validator("counter_evidence")
    @classmethod
    def _validate_counter_evidence_ids_unique(
        cls, value: tuple[_EvidenceItem, ...]
    ) -> tuple[_EvidenceItem, ...]:
        return _ensure_unique_ids(value, "evidence_id", "counter_evidence")

    @field_validator("comparisons")
    @classmethod
    def _validate_comparison_ids_unique(
        cls, value: tuple[_ComparisonItem, ...]
    ) -> tuple[_ComparisonItem, ...]:
        return _ensure_unique_ids(value, "comparison_id", "comparisons")

    @field_validator("risks")
    @classmethod
    def _validate_risk_ids_unique(
        cls, value: tuple[_RiskItem, ...]
    ) -> tuple[_RiskItem, ...]:
        return _ensure_unique_ids(value, "risk_id", "risks")

    @model_validator(mode="after")
    def _validate_decision_consistency(self) -> DecisionDossier:
        """A dossier may only carry a decision when status is ``decided``.

        ``rejected`` and ``superseded`` are closing states too, but the
        explicit ``decision`` field (proceed/hold/reject/defer) is only
        meaningful for a ``decided`` dossier.  This keeps the workflow
        honest: a ``draft`` dossier cannot pretend to have a decision,
        and a ``decided`` dossier must state what the decision was.
        """
        if self.status == "decided" and not self.decision:
            raise DossierValidationError(
                "status='decided' requires a non-null decision "
                f"(one of {sorted(VALID_DECISION_VALUES)})"
            )
        if self.status != "decided" and self.decision is not None:
            raise DossierValidationError(
                f"decision can only be set when status='decided' "
                f"(got status={self.status!r}, decision={self.decision!r})"
            )
        return self

    def to_storage_payload(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict for local storage.

        Tuples are converted to lists so the payload is JSON-serializable
        by the standard ``json`` module without a custom encoder.
        """
        payload = self.model_dump(mode="json")
        payload["supporting_evidence"] = [
            e.model_dump(mode="json") for e in self.supporting_evidence
        ]
        payload["counter_evidence"] = [
            e.model_dump(mode="json") for e in self.counter_evidence
        ]
        payload["comparisons"] = [c.model_dump(mode="json") for c in self.comparisons]
        payload["risks"] = [r.model_dump(mode="json") for r in self.risks]
        payload["linked_artifacts"] = list(self.linked_artifacts)
        payload["limitations"] = list(self.limitations)
        return payload

    @classmethod
    def from_storage_payload(cls, payload: dict[str, Any]) -> DecisionDossier:
        """Deserialize from a local-storage dict, validating all fields."""
        return cls.model_validate(payload)


def _ensure_unique_ids(items: tuple, id_field: str, container_name: str) -> tuple:
    """Shared helper: ensure each item's ``id_field`` is unique within ``items``."""
    seen: set[str] = set()
    for item in items:
        item_id = getattr(item, id_field)
        if item_id in seen:
            raise DossierValidationError(
                f"duplicate {id_field} in {container_name}: {item_id!r}"
            )
        seen.add(item_id)
    return items


_DOSSIER_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$")


def validate_dossier_id(dossier_id: str) -> str:
    """Validate a dossier_id string.

    A dossier_id must be 1-128 chars, alphanumeric + ``-`` / ``_``,
    starting with an alphanumeric character.  This keeps the id safe
    for use as a filename component in the local store.
    """
    if not isinstance(dossier_id, str) or not _DOSSIER_ID_PATTERN.match(dossier_id):
        raise DossierValidationError(
            f"invalid dossier_id: {dossier_id!r} "
            "(must be 1-128 chars, alphanumeric + - / _, starting alphanumeric)"
        )
    return dossier_id


def validate_dossier_payload(payload: object) -> DecisionDossier:
    """Validate an arbitrary payload as a decision dossier.

    Accepts a dict (from JSON parse) and returns a validated
    :class:`DecisionDossier`.  Raises :class:`DossierValidationError`
    on any schema, type or semantic error.

    This is the canonical entry point used by the CLI, API and store
    so validation logic is not duplicated.
    """
    if not isinstance(payload, dict):
        raise DossierValidationError(
            f"dossier payload must be a JSON object, got {type(payload).__name__}"
        )

    dossier_id = payload.get("dossier_id")
    if not isinstance(dossier_id, str):
        raise DossierValidationError("dossier_id is required and must be a string")
    validate_dossier_id(dossier_id)

    try:
        return DecisionDossier.model_validate(payload)
    except DossierValidationError:
        raise
    except Exception as exc:  # pydantic ValidationError
        raise DossierValidationError(str(exc)) from exc


__all__ = [
    "DOSSIER_SCHEMA",
    "DOSSIER_VERSION",
    "MAX_DOSSIER_BYTES",
    "VALID_FACT_TIERS",
    "VALID_DOSSIER_STATUS",
    "VALID_DECISION_VALUES",
    "VALID_RISK_SEVERITY",
    "DossierValidationError",
    "DecisionDossier",
    "validate_dossier_id",
    "validate_dossier_payload",
]
