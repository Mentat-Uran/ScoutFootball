"""Versioned post-match review: maintainer-authored hypothesis-plan-
execution-result comparison.

A post-match review is the closing artifact of the opposition & match
workflow.  It takes an :class:`~scoutfootball.opposition.briefing.OppositionBriefing`
(the hypothesis), optional scenario-tree references (the plan) and the
silver match facts (the execution / result), then records the
maintainer's honest comparison: which hypotheses were confirmed or
falsified, which patterns turned out to be wrong, what new questions
the match surfaced, and the maintainer's free-form opinion + final
recommendation.

The review is a personal local object, not an external fact.  It is
versioned via ``review_id`` and ``revision``; old revisions are kept
in local backups by the store.  The schema is deliberately explicit
about the workflow state — ``status`` moves from ``draft`` to
``finalized`` / ``superseded``, and ``decision`` is only meaningful
once ``status == "finalized"``.

Evidence sections (supporting, counter, hypothesis_result, falsified
pattern, new question) each carry an explicit ``fact_tier`` of
``official`` / ``recorded`` / ``estimated`` / ``unknown`` so a reviewer
can never confuse an official scoreline with a maintainer estimate.
This reuses the fact-tier taxonomy from
:mod:`scoutfootball.opposition.briefing` so the opposition pack shares
one honest-source vocabulary.

Schema
------

``scoutfootball.opposition-post-match-review`` version ``1.0.0``::

    {
      "schema": "scoutfootball.opposition-post-match-review",
      "version": "1.0.0",
      "review_id": "review-2026-08-16-abc123",
      "revision": 1,
      "created_at": "2026-08-16T20:00:00+00:00",
      "updated_at": "2026-08-16T20:00:00+00:00",
      "author": "maintainer",
      "title": "Post-match review: Arsenal 2 Chelsea 1",
      "briefing_id": "briefing-2026-08-15-abc123",
      "match_id": "fd-match-64766",
      "home_team": "Arsenal",
      "away_team": "Chelsea",
      "kickoff_at": "2026-08-15T15:00:00+00:00",
      "competition": "Premier League",
      "season": "2026-27",
      "final_score_home": 2,
      "final_score_away": 1,
      "status": "draft",
      "decision": null,
      "decision_note": "",
      "hypothesis_results": [
        {
          "hypothesis_id": "h-001",
          "planned": "Chelsea right-side overload in 4-2-3-1",
          "observed": "Chelsea stayed in 4-2-3-1 but overloaded the left instead",
          "outcome": "falsified",
          "fact_tier": "recorded",
          "evidence_refs": ["events/2026-08-15/Chelsea-left-overload"]
        }
      ],
      "falsified_patterns": [],
      "new_questions": [],
      "supporting_evidence": [],
      "counter_evidence": [],
      "human_opinion": "",
      "recommendation": "",
      "linked_artifacts": [],
      "notes": "",
      "limitations": [
        "PostMatchReview is a personal local object; not an external fact.",
        "Decision is the maintainer's honest judgment, not an automated recommendation."
      ]
    }
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

REVIEW_SCHEMA = "scoutfootball.opposition-post-match-review"
REVIEW_VERSION = "1.0.0"
MAX_REVIEW_BYTES = 200_000  # 200 KB local limit; reviews carry evidence refs
VALID_FACT_TIERS = {"official", "recorded", "estimated", "unknown"}
VALID_REVIEW_STATUS = {"draft", "finalized", "superseded"}
VALID_REVIEW_DECISIONS = {"confirmed", "falsified", "partial", "inconclusive"}
VALID_HYPOTHESIS_OUTCOMES = {"confirmed", "falsified", "partial"}
VALID_RISK_SEVERITY = {"low", "medium", "high"}


class ReviewValidationError(ValueError):
    """Raised when a post-match review payload fails schema or semantic validation."""


class _EvidenceItem(BaseModel):
    """One piece of evidence (supporting or counter) inside a review.

    The ``fact_tier`` is the maintainer's honest classification of how
    well-sourced the item is, not an automated guess.  ``official``
    means an authoritative source (e.g. an official scoreline, a
    confirmed lineup); ``recorded`` means a verified local artifact
    (e.g. a row in ``team_match.parquet`` or an events JSON); ``estimated``
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
            raise ReviewValidationError(
                f"invalid fact_tier: {value!r} "
                f"(must be one of {sorted(VALID_FACT_TIERS)})"
            )
        return value


class _HypothesisResult(BaseModel):
    """One hypothesis comparison inside a post-match review.

    A hypothesis result compares what the briefing / scenario tree
    planned (``planned``) with what actually happened in the match
    (``observed``), then records the maintainer's honest outcome
    classification: ``confirmed`` (the planned pattern occurred),
    ``falsified`` (the planned pattern did not occur) or ``partial``
    (some elements occurred, others did not).  Like evidence items,
    hypothesis results carry a ``fact_tier`` so the maintainer can
    distinguish a verified match observation (``recorded``) from a
    subjective interpretation (``estimated``).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    hypothesis_id: str = Field(min_length=1, max_length=64)
    planned: str = Field(default="", max_length=2000)
    observed: str = Field(default="", max_length=2000)
    outcome: str = Field(default="partial")
    fact_tier: str = Field(default="unknown")
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("outcome")
    @classmethod
    def _validate_outcome(cls, value: str) -> str:
        if value not in VALID_HYPOTHESIS_OUTCOMES:
            raise ReviewValidationError(
                f"invalid outcome: {value!r} "
                f"(must be one of {sorted(VALID_HYPOTHESIS_OUTCOMES)})"
            )
        return value

    @field_validator("fact_tier")
    @classmethod
    def _validate_fact_tier(cls, value: str) -> str:
        if value not in VALID_FACT_TIERS:
            raise ReviewValidationError(
                f"invalid fact_tier: {value!r} "
                f"(must be one of {sorted(VALID_FACT_TIERS)})"
            )
        return value


class _FalsifiedPattern(BaseModel):
    """One falsified pattern entry inside a post-match review.

    A falsified pattern is a pattern card (or informal pattern) that
    the match evidence contradicted.  ``severity`` is the maintainer's
    honest severity classification (low/medium/high) — how strongly
    the match refuted the pattern, not how damaging the pattern itself
    was.  Falsified patterns are evidence themselves, so they carry
    ``fact_tier`` and ``evidence_refs``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern_id: str = Field(min_length=1, max_length=64)
    summary: str = Field(min_length=1, max_length=2000)
    severity: str = Field(default="medium")
    fact_tier: str = Field(default="unknown")
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("severity")
    @classmethod
    def _validate_severity(cls, value: str) -> str:
        if value not in VALID_RISK_SEVERITY:
            raise ReviewValidationError(
                f"invalid severity: {value!r} "
                f"(must be one of {sorted(VALID_RISK_SEVERITY)})"
            )
        return value

    @field_validator("fact_tier")
    @classmethod
    def _validate_fact_tier(cls, value: str) -> str:
        if value not in VALID_FACT_TIERS:
            raise ReviewValidationError(
                f"invalid fact_tier: {value!r} "
                f"(must be one of {sorted(VALID_FACT_TIERS)})"
            )
        return value


class _NewQuestion(BaseModel):
    """One new question surfaced by the match.

    A new question is an open issue the maintainer could not answer
    from the current evidence and wants to investigate in future
    briefings or reviews.  ``scope`` is a short free-form label (e.g.
    ``"set pieces"``, ``"in-game adaptation"``) so consumers can group
    related questions later; it is not an enum because question scope
    is open-ended.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    question_id: str = Field(min_length=1, max_length=64)
    summary: str = Field(min_length=1, max_length=2000)
    scope: str = Field(default="", max_length=128)
    fact_tier: str = Field(default="unknown")
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("fact_tier")
    @classmethod
    def _validate_fact_tier(cls, value: str) -> str:
        if value not in VALID_FACT_TIERS:
            raise ReviewValidationError(
                f"invalid fact_tier: {value!r} "
                f"(must be one of {sorted(VALID_FACT_TIERS)})"
            )
        return value


class PostMatchReview(BaseModel):
    """Pydantic model for a versioned post-match review.

    The model is the single source of truth for review shape: the
    store, CLI and API all round-trip through ``model_dump`` /
    ``model_validate`` so there is no separate hand-rolled serialization.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema: str = Field(default=REVIEW_SCHEMA)
    version: str = Field(default=REVIEW_VERSION)
    review_id: str = Field(min_length=1, max_length=128)
    revision: int = Field(default=1, ge=1)
    created_at: datetime
    updated_at: datetime
    author: str = Field(default="maintainer", min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    briefing_id: str = Field(default="", max_length=128)
    match_id: str = Field(default="", max_length=128)
    home_team: str = Field(default="", max_length=128)
    away_team: str = Field(default="", max_length=128)
    kickoff_at: datetime | None = Field(default=None)
    competition: str = Field(default="", max_length=128)
    season: str = Field(default="", max_length=32)
    final_score_home: int | None = Field(default=None, ge=0)
    final_score_away: int | None = Field(default=None, ge=0)
    status: str = Field(default="draft")
    decision: str | None = Field(default=None)
    decision_note: str = Field(default="", max_length=4000)
    hypothesis_results: tuple[_HypothesisResult, ...] = Field(default_factory=tuple)
    falsified_patterns: tuple[_FalsifiedPattern, ...] = Field(default_factory=tuple)
    new_questions: tuple[_NewQuestion, ...] = Field(default_factory=tuple)
    supporting_evidence: tuple[_EvidenceItem, ...] = Field(default_factory=tuple)
    counter_evidence: tuple[_EvidenceItem, ...] = Field(default_factory=tuple)
    human_opinion: str = Field(default="", max_length=8000)
    recommendation: str = Field(default="", max_length=4000)
    linked_artifacts: tuple[str, ...] = Field(default_factory=tuple)
    notes: str = Field(default="", max_length=4000)
    limitations: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("schema")
    @classmethod
    def _validate_schema(cls, value: str) -> str:
        if value != REVIEW_SCHEMA:
            raise ReviewValidationError(
                f"unsupported review schema: {value!r} (expected {REVIEW_SCHEMA!r})"
            )
        return value

    @field_validator("version")
    @classmethod
    def _validate_version(cls, value: str) -> str:
        if value != REVIEW_VERSION:
            raise ReviewValidationError(
                f"unsupported review version: {value!r} (expected {REVIEW_VERSION!r})"
            )
        return value

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        if value not in VALID_REVIEW_STATUS:
            raise ReviewValidationError(
                f"invalid status: {value!r} "
                f"(must be one of {sorted(VALID_REVIEW_STATUS)})"
            )
        return value

    @field_validator("decision")
    @classmethod
    def _validate_decision(cls, value: str | None) -> str | None:
        if value is not None and value not in VALID_REVIEW_DECISIONS:
            raise ReviewValidationError(
                f"invalid decision: {value!r} "
                f"(must be one of {sorted(VALID_REVIEW_DECISIONS)} or null)"
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

    @field_validator("hypothesis_results")
    @classmethod
    def _validate_hypothesis_ids_unique(
        cls, value: tuple[_HypothesisResult, ...]
    ) -> tuple[_HypothesisResult, ...]:
        return _ensure_unique_ids(value, "hypothesis_id", "hypothesis_results")

    @field_validator("falsified_patterns")
    @classmethod
    def _validate_pattern_ids_unique(
        cls, value: tuple[_FalsifiedPattern, ...]
    ) -> tuple[_FalsifiedPattern, ...]:
        return _ensure_unique_ids(value, "pattern_id", "falsified_patterns")

    @field_validator("new_questions")
    @classmethod
    def _validate_question_ids_unique(
        cls, value: tuple[_NewQuestion, ...]
    ) -> tuple[_NewQuestion, ...]:
        return _ensure_unique_ids(value, "question_id", "new_questions")

    @model_validator(mode="after")
    def _validate_decision_consistency(self) -> PostMatchReview:
        """A review may only carry a decision when status is ``finalized``.

        ``superseded`` is a closing state too, but the explicit
        ``decision`` field (confirmed/falsified/partial/inconclusive)
        is only meaningful for a ``finalized`` review.  This keeps the
        workflow honest: a ``draft`` review cannot pretend to have a
        decision, and a ``finalized`` review must state what the
        decision was.
        """
        if self.status == "finalized" and not self.decision:
            raise ReviewValidationError(
                "status='finalized' requires a non-null decision "
                f"(one of {sorted(VALID_REVIEW_DECISIONS)})"
            )
        if self.status != "finalized" and self.decision is not None:
            raise ReviewValidationError(
                f"decision can only be set when status='finalized' "
                f"(got status={self.status!r}, decision={self.decision!r})"
            )
        return self

    def to_storage_payload(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict for local storage.

        Tuples are converted to lists so the payload is JSON-serializable
        by the standard ``json`` module without a custom encoder.
        """
        payload = self.model_dump(mode="json")
        payload["hypothesis_results"] = [
            h.model_dump(mode="json") for h in self.hypothesis_results
        ]
        payload["falsified_patterns"] = [
            p.model_dump(mode="json") for p in self.falsified_patterns
        ]
        payload["new_questions"] = [
            q.model_dump(mode="json") for q in self.new_questions
        ]
        payload["supporting_evidence"] = [
            e.model_dump(mode="json") for e in self.supporting_evidence
        ]
        payload["counter_evidence"] = [
            e.model_dump(mode="json") for e in self.counter_evidence
        ]
        payload["linked_artifacts"] = list(self.linked_artifacts)
        payload["limitations"] = list(self.limitations)
        return payload

    @classmethod
    def from_storage_payload(cls, payload: dict[str, Any]) -> PostMatchReview:
        """Deserialize from a local-storage dict, validating all fields."""
        return cls.model_validate(payload)


def _ensure_unique_ids(items: tuple, id_field: str, container_name: str) -> tuple:
    """Shared helper: ensure each item's ``id_field`` is unique within ``items``."""
    seen: set[str] = set()
    for item in items:
        item_id = getattr(item, id_field)
        if item_id in seen:
            raise ReviewValidationError(
                f"duplicate {id_field} in {container_name}: {item_id!r}"
            )
        seen.add(item_id)
    return items


_REVIEW_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$")


def validate_review_id(review_id: str) -> str:
    """Validate a review_id string.

    A review_id must be 1-128 chars, alphanumeric + ``-`` / ``_``,
    starting with an alphanumeric character.  This keeps the id safe
    for use as a filename component in the local store.
    """
    if not isinstance(review_id, str) or not _REVIEW_ID_PATTERN.match(review_id):
        raise ReviewValidationError(
            f"invalid review_id: {review_id!r} "
            "(must be 1-128 chars, alphanumeric + - / _, starting alphanumeric)"
        )
    return review_id


def validate_review_payload(payload: object) -> PostMatchReview:
    """Validate an arbitrary payload as a post-match review.

    Accepts a dict (from JSON parse) and returns a validated
    :class:`PostMatchReview`.  Raises :class:`ReviewValidationError`
    on any schema, type or semantic error.

    This is the canonical entry point used by the CLI, API and store
    so validation logic is not duplicated.
    """
    if not isinstance(payload, dict):
        raise ReviewValidationError(
            f"review payload must be a JSON object, got {type(payload).__name__}"
        )

    review_id = payload.get("review_id")
    if not isinstance(review_id, str):
        raise ReviewValidationError("review_id is required and must be a string")
    validate_review_id(review_id)

    try:
        return PostMatchReview.model_validate(payload)
    except ReviewValidationError:
        raise
    except Exception as exc:  # pydantic ValidationError
        raise ReviewValidationError(str(exc)) from exc


__all__ = [
    "REVIEW_SCHEMA",
    "REVIEW_VERSION",
    "MAX_REVIEW_BYTES",
    "VALID_FACT_TIERS",
    "VALID_REVIEW_STATUS",
    "VALID_REVIEW_DECISIONS",
    "VALID_HYPOTHESIS_OUTCOMES",
    "VALID_RISK_SEVERITY",
    "ReviewValidationError",
    "PostMatchReview",
    "validate_review_id",
    "validate_review_payload",
]
