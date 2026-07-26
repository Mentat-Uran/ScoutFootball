"""Versioned recruitment brief: maintainer-authored player requirement.

A brief is the entry point of the recruitment workflow.  It describes
what the maintainer is looking for (team, position, role, budget, age,
contract, league, language, risk preferences) so candidate search can
filter and rank players against the requirement.

The brief is a personal local object, not an external fact.  It is
versioned via ``brief_id`` and ``revision``; old revisions are kept in
local backups by the store.  The schema is deliberately explicit about
optional fields — a brief with only a position and a league is valid,
because the maintainer may not have decided on budget or contract yet.

Schema
------

``scoutfootball.recruitment-brief`` version ``1.0.0``:

    {
      "schema": "scoutfootball.recruitment-brief",
      "version": "1.0.0",
      "brief_id": "brief-2026-07-23-abc123",
      "revision": 1,
      "created_at": "2026-07-23T10:00:00+00:00",
      "updated_at": "2026-07-23T10:00:00+00:00",
      "author": "maintainer",
      "title": "Left-back for Arsenal first team",
      "team": "Arsenal",
      "position_group": "DF",
      "position_detail": "LB",
      "role": "attacking_fullback",
      "budget_eur": 30000000,
      "age_min": 21,
      "age_max": 27,
      "contract_years_min": 3,
      "league_preferences": ["Premier League", "La Liga"],
      "language_preferences": ["English"],
      "risk_tolerance": "medium",
      "minimum_minutes": 1500,
      "notes": "Priority window: summer 2026.",
      "limitations": [
        "Brief is a personal local object; not an external fact.",
        (
          "Candidate coverage depends on the rating snapshot; "
          "low-coverage leagues may be under-represented."
        )
      ]
    }
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

BRIEF_SCHEMA = "scoutfootball.recruitment-brief"
BRIEF_VERSION = "1.0.0"
MAX_BRIEF_BYTES = 100_000  # 100 KB local limit; briefs are small text records
VALID_POSITION_GROUPS = {"DF", "MF", "FW", "GK"}
VALID_RISK_TOLERANCES = {"low", "medium", "high"}


class BriefValidationError(ValueError):
    """Raised when a brief payload fails schema or semantic validation."""


class RecruitmentBrief(BaseModel):
    """Pydantic model for a versioned recruitment brief.

    The model is the single source of truth for brief shape: the store,
    CLI and API all round-trip through ``model_dump`` / ``model_validate``
    so there is no separate hand-rolled serialization.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    schema_name: str = Field(default=BRIEF_SCHEMA, alias="schema")
    version: str = Field(default=BRIEF_VERSION)
    brief_id: str = Field(min_length=1, max_length=128)
    revision: int = Field(default=1, ge=1)
    created_at: datetime
    updated_at: datetime
    author: str = Field(default="maintainer", min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    team: str = Field(default="", max_length=128)
    position_group: str = Field(min_length=1, max_length=8)
    position_detail: str = Field(default="", max_length=8)
    role: str = Field(default="", max_length=128)
    budget_eur: int | None = Field(default=None, ge=0)
    age_min: int | None = Field(default=None, ge=15, le=50)
    age_max: int | None = Field(default=None, ge=15, le=50)
    contract_years_min: int | None = Field(default=None, ge=1, le=10)
    league_preferences: tuple[str, ...] = Field(default_factory=tuple)
    language_preferences: tuple[str, ...] = Field(default_factory=tuple)
    risk_tolerance: str = Field(default="medium")
    minimum_minutes: int | None = Field(default=None, ge=0, le=10000)
    notes: str = Field(default="", max_length=4000)
    limitations: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("schema_name")
    @classmethod
    def _validate_schema(cls, value: str) -> str:
        if value != BRIEF_SCHEMA:
            raise BriefValidationError(
                f"unsupported brief schema: {value!r} (expected {BRIEF_SCHEMA!r})"
            )
        return value

    @field_validator("version")
    @classmethod
    def _validate_version(cls, value: str) -> str:
        if value != BRIEF_VERSION:
            raise BriefValidationError(
                f"unsupported brief version: {value!r} (expected {BRIEF_VERSION!r})"
            )
        return value

    @field_validator("position_group")
    @classmethod
    def _validate_position_group(cls, value: str) -> str:
        if value not in VALID_POSITION_GROUPS:
            raise BriefValidationError(
                f"invalid position_group: {value!r} "
                f"(must be one of {sorted(VALID_POSITION_GROUPS)})"
            )
        return value

    @field_validator("risk_tolerance")
    @classmethod
    def _validate_risk_tolerance(cls, value: str) -> str:
        if value not in VALID_RISK_TOLERANCES:
            raise BriefValidationError(
                f"invalid risk_tolerance: {value!r} "
                f"(must be one of {sorted(VALID_RISK_TOLERANCES)})"
            )
        return value

    @field_validator("age_max")
    @classmethod
    def _validate_age_range(cls, value: int | None, info) -> int | None:
        age_min = info.data.get("age_min")
        if value is not None and age_min is not None and value < age_min:
            raise BriefValidationError(
                f"age_max ({value}) must be >= age_min ({age_min})"
            )
        return value

    def to_storage_payload(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict for local storage.

        Tuples are converted to lists so the payload is JSON-serializable
        by the standard ``json`` module without a custom encoder.
        """
        payload = self.model_dump(mode="json")
        payload["league_preferences"] = list(self.league_preferences)
        payload["language_preferences"] = list(self.language_preferences)
        payload["limitations"] = list(self.limitations)
        return payload

    @classmethod
    def from_storage_payload(cls, payload: dict[str, Any]) -> RecruitmentBrief:
        """Deserialize from a local-storage dict, validating all fields."""
        return cls.model_validate(payload)


_BRIEF_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$")


def validate_brief_id(brief_id: str) -> str:
    """Validate a brief_id string.

    A brief_id must be 1-128 chars, alphanumeric + ``-`` / ``_``,
    starting with an alphanumeric character.  This keeps the id safe
    for use as a filename component in the local store.
    """
    if not isinstance(brief_id, str) or not _BRIEF_ID_PATTERN.match(brief_id):
        raise BriefValidationError(
            f"invalid brief_id: {brief_id!r} "
            "(must be 1-128 chars, alphanumeric + - / _, starting alphanumeric)"
        )
    return brief_id


def validate_brief_payload(payload: object) -> RecruitmentBrief:
    """Validate an arbitrary payload as a recruitment brief.

    Accepts a dict (from JSON parse) and returns a validated
    :class:`RecruitmentBrief`.  Raises :class:`BriefValidationError`
    on any schema, type or semantic error.

    This is the canonical entry point used by the CLI, API and store
    so validation logic is not duplicated.
    """
    if not isinstance(payload, dict):
        raise BriefValidationError(
            f"brief payload must be a JSON object, got {type(payload).__name__}"
        )

    brief_id = payload.get("brief_id")
    if not isinstance(brief_id, str):
        raise BriefValidationError("brief_id is required and must be a string")
    validate_brief_id(brief_id)

    try:
        return RecruitmentBrief.model_validate(payload)
    except BriefValidationError:
        raise
    except Exception as exc:  # pydantic ValidationError
        raise BriefValidationError(str(exc)) from exc


__all__ = [
    "BRIEF_SCHEMA",
    "BRIEF_VERSION",
    "MAX_BRIEF_BYTES",
    "VALID_POSITION_GROUPS",
    "VALID_RISK_TOLERANCES",
    "BriefValidationError",
    "RecruitmentBrief",
    "validate_brief_id",
    "validate_brief_payload",
]
