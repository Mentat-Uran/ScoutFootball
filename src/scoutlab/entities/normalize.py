"""Normalization helpers for cross-source entity matching."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

import pandas as pd

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


TEAM_NAME_ALIASES: dict[str, str] = {
    "man city": "Manchester City",
    "manchester city": "Manchester City",
    "man utd": "Manchester United",
    "man united": "Manchester United",
    "manchester united": "Manchester United",
    "spurs": "Tottenham Hotspur",
    "tottenham": "Tottenham Hotspur",
    "wolves": "Wolverhampton Wanderers",
    "barca": "FC Barcelona",
    "barcelona": "FC Barcelona",
    "atletico": "Atlético Madrid",
    "atletico madrid": "Atlético Madrid",
    "athletic bilbao": "Athletic Club",
    "bayern": "FC Bayern Munich",
    "bayern munich": "FC Bayern Munich",
    "bayern münchen": "FC Bayern Munich",
    "dortmund": "Borussia Dortmund",
    "psg": "Paris Saint-Germain",
    "paris sg": "Paris Saint-Germain",
    "paris saint-germain": "Paris Saint-Germain",
    "inter": "Inter Milan",
    "inter milano": "Inter Milan",
    "milan": "AC Milan",
    "ac milan": "AC Milan",
    "juve": "Juventus",
    "benfica": "SL Benfica",
    "porto": "FC Porto",
    "sporting": "Sporting CP",
    "sporting lisbon": "Sporting CP",
    "ajax": "AFC Ajax",
    "galatasaray": "Galatasaray SK",
    "fenerbahce": "Fenerbahçe SK",
    "besiktas": "Beşiktaş JK",
    "celtic": "Celtic FC",
    "rangers": "Rangers FC",
    "club brugge": "Club Brugge KV",
}


def normalize_team_name(name: str | None) -> str:
    """Normalize a team name to its canonical form.

    Looks up the lowercased, stripped name in TEAM_NAME_ALIASES first.
    Falls back to the original stripped name if no alias is found.
    Returns empty string for None / NaN / blank input.
    """
    if not name or pd.isna(name):
        return ""
    lower = str(name).strip().lower()
    return TEAM_NAME_ALIASES.get(lower, str(name).strip())


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


def build_player_composite_key(
    name: str,
    born_year: int | None = None,
    nationality: str | None = None,
) -> str:
    """Build a composite key for cross-source player identity matching.

    Format: "{normalized_name}|{born_year}|{normalized_nationality}"
    Missing components are replaced with "NA".
    """
    normalized_name = normalize_person_name(name)
    year_str = str(born_year) if born_year is not None else "NA"
    nat_str = normalize_country_name(nationality) if nationality is not None else "NA"
    return f"{normalized_name}|{year_str}|{nat_str}"


def fuzzy_match_player_key(
    key1: str,
    key2: str,
    *,
    name_similarity_threshold: float = 0.85,
) -> bool:
    """Check if two composite keys likely refer to the same player.

    Uses exact match on born_year and nationality, with fuzzy matching on name.
    """
    parts1 = key1.split("|")
    parts2 = key2.split("|")
    if len(parts1) != 3 or len(parts2) != 3:
        return False

    name1, year1, nat1 = parts1
    name2, year2, nat2 = parts2

    # born_year must match exactly (unless either is "NA")
    if year1 != "NA" and year2 != "NA" and year1 != year2:
        return False

    # nationality must match exactly (unless either is "NA")
    if nat1 != "NA" and nat2 != "NA" and nat1 != nat2:
        return False

    # fuzzy match on name
    similarity = SequenceMatcher(None, name1, name2).ratio()
    return similarity >= name_similarity_threshold
