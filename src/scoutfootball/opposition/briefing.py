"""Versioned source-limited match briefing.

A briefing is the entry point of the opposition & match workflow.  It
describes one upcoming match (opponent, kickoff, competition) together
with a set of fact sections (opponent strength, recent form, key
players, set pieces, injuries, tactical notes).  Each fact section
carries an explicit ``fact_tier`` of ``official`` / ``recorded`` /
``estimated`` / ``unknown`` so the reviewer can never confuse an
official squad list with a maintainer estimate.

The briefing is a personal local object, not an external fact.  It is
versioned via ``briefing_id`` and ``revision``; old revisions are kept
in local backups by the store.  The schema is deliberately explicit
about optional fields — a briefing with only an opponent name and a
kickoff is valid, because the maintainer may not have collected
evidence yet.

Schema
------

``scoutfootball.opposition-briefing`` version ``1.0.0``::

    {
      "schema": "scoutfootball.opposition-briefing",
      "version": "1.0.0",
      "briefing_id": "briefing-2026-07-23-abc123",
      "revision": 1,
      "created_at": "2026-07-23T10:00:00+00:00",
      "updated_at": "2026-07-23T10:00:00+00:00",
      "author": "maintainer",
      "title": "Match briefing: Arsenal vs Chelsea",
      "match_id": "fd-match-64766",
      "home_team": "Arsenal",
      "away_team": "Chelsea",
      "kickoff_at": "2026-08-15T15:00:00+00:00",
      "competition": "Premier League",
      "season": "2026-27",
      "sections": [
        {
          "section_id": "opponent_strength",
          "fact_tier": "recorded",
          "summary": "Chelsea are 4th in the table, +12 xGD over last 6.",
          "evidence_refs": ["fbref/2026-27/Chelsea", "team_match.parquet#row=64760"]
        },
        {
          "section_id": "key_players",
          "fact_tier": "official",
          "summary": "Palmer expected to start; Jackson doubtful.",
          "evidence_refs": ["official-squad-list-2026-08-15"]
        }
      ],
      "linked_pattern_card_ids": ["pattern-chelsea-right-overload"],
      "linked_scenario_tree_id": null,
      "linked_post_match_review_id": null,
      "notes": "Watch for Chelsea's right-side overload in 4-2-3-1.",
      "limitations": [
        "Briefing is a personal local object; not an external fact.",
        "fact_tier is the maintainer's honest classification, not automated."
      ]
    }
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

BRIEFING_SCHEMA = "scoutfootball.opposition-briefing"
BRIEFING_VERSION = "1.0.0"
MAX_BRIEFING_BYTES = 200_000  # 200 KB local limit; briefings may carry evidence refs
VALID_FACT_TIERS = {"official", "recorded", "estimated", "unknown"}
VALID_SECTION_IDS = {
    "opponent_strength",
    "recent_form",
    "key_players",
    "set_pieces",
    "injuries",
    "tactical_notes",
}


class BriefingValidationError(ValueError):
    """Raised when a briefing payload fails schema or semantic validation."""


class BriefingSection(BaseModel):
    """One fact section of a match briefing.

    The ``fact_tier`` is the maintainer's honest classification of how
    well-sourced the section is, not an automated guess.  A section
    marked ``official`` must have at least one evidence ref pointing to
    an authoritative source (e.g. an official squad list); ``unknown``
    means the maintainer has not yet classified it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str = Field(min_length=1, max_length=64)
    fact_tier: str = Field(default="unknown")
    summary: str = Field(default="", max_length=4000)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("fact_tier")
    @classmethod
    def _validate_fact_tier(cls, value: str) -> str:
        if value not in VALID_FACT_TIERS:
            raise BriefingValidationError(
                f"invalid fact_tier: {value!r} "
                f"(must be one of {sorted(VALID_FACT_TIERS)})"
            )
        return value

    @field_validator("section_id")
    @classmethod
    def _validate_section_id(cls, value: str) -> str:
        # Section IDs are either one of the known set or a custom
        # identifier prefixed with ``custom:`` so consumers can tell
        # maintainer-defined sections from the standard taxonomy.
        if value in VALID_SECTION_IDS:
            return value
        if value.startswith("custom:") and len(value) <= 64:
            tail = value[len("custom:"):]
            if not tail or not re.match(r"^[a-zA-Z0-9_][a-zA-Z0-9_-]*$", tail):
                raise BriefingValidationError(
                    f"invalid custom section_id: {value!r} "
                    "(tail must match [a-zA-Z0-9_][a-zA-Z0-9_-]*)"
                )
            return value
        raise BriefingValidationError(
            f"invalid section_id: {value!r} "
            f"(must be one of {sorted(VALID_SECTION_IDS)} or 'custom:<tail>')"
        )


class OppositionBriefing(BaseModel):
    """Pydantic model for a versioned source-limited match briefing.

    The model is the single source of truth for briefing shape: the
    store, CLI and API all round-trip through ``model_dump`` /
    ``model_validate`` so there is no separate hand-rolled serialization.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    schema_name: str = Field(default=BRIEFING_SCHEMA, alias="schema")
    version: str = Field(default=BRIEFING_VERSION)
    briefing_id: str = Field(min_length=1, max_length=128)
    revision: int = Field(default=1, ge=1)
    created_at: datetime
    updated_at: datetime
    author: str = Field(default="maintainer", min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    match_id: str = Field(default="", max_length=128)
    home_team: str = Field(default="", max_length=128)
    away_team: str = Field(default="", max_length=128)
    kickoff_at: datetime | None = Field(default=None)
    competition: str = Field(default="", max_length=128)
    season: str = Field(default="", max_length=32)
    sections: tuple[BriefingSection, ...] = Field(default_factory=tuple)
    linked_pattern_card_ids: tuple[str, ...] = Field(default_factory=tuple)
    linked_scenario_tree_id: str | None = Field(default=None, max_length=128)
    linked_post_match_review_id: str | None = Field(default=None, max_length=128)
    notes: str = Field(default="", max_length=4000)
    limitations: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("schema_name")
    @classmethod
    def _validate_schema(cls, value: str) -> str:
        if value != BRIEFING_SCHEMA:
            raise BriefingValidationError(
                f"unsupported briefing schema: {value!r} (expected {BRIEFING_SCHEMA!r})"
            )
        return value

    @field_validator("version")
    @classmethod
    def _validate_version(cls, value: str) -> str:
        if value != BRIEFING_VERSION:
            raise BriefingValidationError(
                f"unsupported briefing version: {value!r} (expected {BRIEFING_VERSION!r})"
            )
        return value

    @field_validator("sections")
    @classmethod
    def _validate_section_ids_unique(
        cls, value: tuple[BriefingSection, ...]
    ) -> tuple[BriefingSection, ...]:
        seen: set[str] = set()
        for section in value:
            if section.section_id in seen:
                raise BriefingValidationError(
                    f"duplicate section_id: {section.section_id!r}"
                )
            seen.add(section.section_id)
        return value

    def to_storage_payload(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict for local storage.

        Tuples are converted to lists so the payload is JSON-serializable
        by the standard ``json`` module without a custom encoder.
        """
        payload = self.model_dump(mode="json")
        payload["sections"] = [s.model_dump(mode="json") for s in self.sections]
        payload["linked_pattern_card_ids"] = list(self.linked_pattern_card_ids)
        payload["limitations"] = list(self.limitations)
        return payload

    @classmethod
    def from_storage_payload(cls, payload: dict[str, Any]) -> OppositionBriefing:
        """Deserialize from a local-storage dict, validating all fields."""
        return cls.model_validate(payload)


_BRIEFING_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$")


def validate_briefing_id(briefing_id: str) -> str:
    """Validate a briefing_id string.

    A briefing_id must be 1-128 chars, alphanumeric + ``-`` / ``_``,
    starting with an alphanumeric character.  This keeps the id safe
    for use as a filename component in the local store.
    """
    if not isinstance(briefing_id, str) or not _BRIEFING_ID_PATTERN.match(briefing_id):
        raise BriefingValidationError(
            f"invalid briefing_id: {briefing_id!r} "
            "(must be 1-128 chars, alphanumeric + - / _, starting alphanumeric)"
        )
    return briefing_id


def validate_briefing_payload(payload: object) -> OppositionBriefing:
    """Validate an arbitrary payload as a match briefing.

    Accepts a dict (from JSON parse) and returns a validated
    :class:`OppositionBriefing`.  Raises :class:`BriefingValidationError`
    on any schema, type or semantic error.

    This is the canonical entry point used by the CLI, API and store
    so validation logic is not duplicated.
    """
    if not isinstance(payload, dict):
        raise BriefingValidationError(
            f"briefing payload must be a JSON object, got {type(payload).__name__}"
        )

    briefing_id = payload.get("briefing_id")
    if not isinstance(briefing_id, str):
        raise BriefingValidationError("briefing_id is required and must be a string")
    validate_briefing_id(briefing_id)

    try:
        return OppositionBriefing.model_validate(payload)
    except BriefingValidationError:
        raise
    except Exception as exc:  # pydantic ValidationError
        raise BriefingValidationError(str(exc)) from exc


__all__ = [
    "BRIEFING_SCHEMA",
    "BRIEFING_VERSION",
    "MAX_BRIEFING_BYTES",
    "VALID_FACT_TIERS",
    "VALID_SECTION_IDS",
    "BriefingValidationError",
    "BriefingSection",
    "OppositionBriefing",
    "validate_briefing_id",
    "validate_briefing_payload",
]
