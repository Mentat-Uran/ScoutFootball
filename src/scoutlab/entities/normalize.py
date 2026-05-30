"""Normalization helpers for cross-source entity matching."""

from __future__ import annotations

import re
import unicodedata

TEAM_STOPWORDS = {
    "ac",
    "afc",
    "athletic",
    "atletico",
    "cf",
    "club",
    "fc",
    "fk",
    "football",
    "sc",
    "sfc",
    "sporting",
    "sv",
    "the",
}
COUNTRY_ALIASES = {
    "eng": "england",
    "en": "england",
    "gb": "united kingdom",
    "uk": "united kingdom",
    "es": "spain",
    "esp": "spain",
    "de": "germany",
    "ger": "germany",
    "fr": "france",
    "fra": "france",
    "it": "italy",
    "ita": "italy",
    "nl": "netherlands",
    "ned": "netherlands",
    "por": "portugal",
    "pt": "portugal",
    "usa": "united states",
    "us": "united states",
    "u s a": "united states",
}
POSITION_ALIASES = {
    "goalkeeper": "gk",
    "keeper": "gk",
    "gk": "gk",
    "defender": "def",
    "center back": "cb",
    "centre back": "cb",
    "full back": "fb",
    "wing back": "wb",
    "midfielder": "mid",
    "attacking midfielder": "am",
    "defensive midfielder": "dm",
    "forward": "fwd",
    "striker": "fwd",
    "winger": "wing",
}
NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9\s]+")
MULTISPACE_PATTERN = re.compile(r"\s+")


def normalize_person_name(name: str | None) -> str:
    """Normalize a player/person name for deterministic matching."""

    return _normalize_core(name)


def normalize_team_name(name: str | None) -> str:
    """Normalize a team name and strip low-signal club affixes."""

    normalized = _normalize_core(name)
    if not normalized:
        return ""
    tokens = [token for token in normalized.split() if token not in TEAM_STOPWORDS]
    return " ".join(tokens)


def normalize_country_name(country: str | None) -> str:
    """Normalize country names and short aliases."""

    normalized = _normalize_core(country)
    if not normalized:
        return ""
    return COUNTRY_ALIASES.get(normalized, normalized)


def normalize_position_group(position: str | None) -> str:
    """Normalize loose position labels into comparable groups."""

    normalized = _normalize_core(position)
    if not normalized:
        return ""
    return POSITION_ALIASES.get(normalized, normalized)


def _normalize_core(value: str | None) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = text.replace("&", " and ")
    text = text.replace("/", " ")
    text = NON_ALNUM_PATTERN.sub(" ", text)
    text = MULTISPACE_PATTERN.sub(" ", text)
    return text.strip()
