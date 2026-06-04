"""SoFIFA adapter for FIFA player attributes via soccerdata."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

import pandas as pd

from scoutlab.adapters.base import AdapterResult, SourceMetadata
from scoutlab.adapters.common import SourceSchemaError
from scoutlab.config import PlatformSettings
from scoutlab.schemas import SourceRequestLogEntry

logger = logging.getLogger(__name__)

SOURCE_NAME = "sofifa"
PARSER_VERSION = "sofifa/v0.1.0"

SO_FIFA_API = "https://sofifa.com"

# Internal league key -> SoFIFA league name (soccerdata convention)
LEAGUE_MAPPINGS: dict[str, str] = {
    "ENG-Premier League": "[England] Premier League",
    "Premier League": "[England] Premier League",
    "ESP-La Liga": "[Spain] La Liga",
    "La Liga": "[Spain] La Liga",
    "GER-Bundesliga": "[Germany] Bundesliga",
    "Bundesliga": "[Germany] Bundesliga",
    "ITA-Serie A": "[Italy] Serie A",
    "Serie A": "[Italy] Serie A",
    "FRA-Ligue 1": "[France] Ligue 1",
    "Ligue 1": "[France] Ligue 1",
    "POR-Primeira Liga": "[Portugal] Primeira Liga",
    "Primeira Liga": "[Portugal] Primeira Liga",
    "NED-Eredivisie": "[Netherlands] Eredivisie",
    "Eredivisie": "[Netherlands] Eredivisie",
    "TUR-Süper Lig": "[Turkey] Süper Lig",
    "Süper Lig": "[Turkey] Süper Lig",
    "SCO-Scottish Premiership": "[Scotland] Premiership",
    "Scottish Premiership": "[Scotland] Premiership",
    "BEL-First Division A": "[Belgium] Pro League",
    "First Division A": "[Belgium] Pro League",
}

# FIFA version year -> fifa_edition string in SoFIFA
_FIFA_EDITION_MAP: dict[int, str] = {
    20: "FIFA 20",
    21: "FIFA 21",
    22: "FIFA 22",
    23: "FIFA 23",
    24: "FC 24",
    25: "FC 25",
}


def fetch_player_attributes(
    league: str,
    season: int,
    *,
    client: object | None = None,
    settings: PlatformSettings | None = None,
    force_refresh: bool = False,
) -> AdapterResult:
    """Fetch FIFA player attributes from SoFIFA via soccerdata.

    Parameters
    ----------
    league : str
        SoFIFA league name (e.g. "ENG-Premier League", "POR-Primeira Liga").
    season : int
        FIFA version year (e.g. 24 for FC 24, 25 for FC 25).
    client : object, optional
        Unused; soccerdata handles its own HTTP.
    settings : PlatformSettings, optional
        Platform settings for path resolution.
    force_refresh : bool
        If True, bypass soccerdata's cache.

    Returns
    -------
    AdapterResult
        DataFrame with columns: player_name, team_name, position,
        overall_rating, potential, pac, sho, pas, dri, def, phy,
        age, height, weight, preferred_foot, international_reputation,
        weak_foot, skill_moves, league, season.
    """
    try:
        import soccerdata as sd
    except ImportError as exc:
        raise ImportError(
            "soccerdata is required for the SoFIFA adapter. "
            "Install it with: uv pip install soccerdata"
        ) from exc

    resolved_settings = settings or PlatformSettings.from_root()
    sofifa_league = _resolve_league(league)
    fifa_edition = _resolve_fifa_edition(season)

    # Initialize scraper with "all" versions so we can filter by edition
    try:
        scraper = sd.SoFIFA(
            leagues=sofifa_league,
            versions="all",
            no_cache=force_refresh,
            data_dir=resolved_settings.raw_root / SOURCE_NAME / "soccerdata_cache",
        )
    except Exception as exc:
        raise SourceSchemaError(
            f"Failed to initialize SoFIFA scraper for {league} season={season}: {exc}"
        ) from exc

    # Find the latest version_id for the requested FIFA edition
    try:
        all_versions = scraper.read_versions()
    except Exception as exc:
        raise SourceSchemaError(
            f"Failed to read SoFIFA versions for {league} season={season}: {exc}"
        ) from exc

    edition_versions = all_versions[
        all_versions["fifa_edition"] == fifa_edition
    ]
    if edition_versions.empty:
        raise SourceSchemaError(
            f"No SoFIFA versions found for FIFA edition '{fifa_edition}' "
            f"(season={season})"
        )

    # Pick the latest update for this edition
    latest_version_id = edition_versions.index[-1]
    scraper.versions = edition_versions.tail(n=1)

    # Fetch player list (player_id, player, team, league, version info)
    try:
        players_df = scraper.read_players()
    except Exception as exc:
        raise SourceSchemaError(
            f"Failed to read SoFIFA players for {league} season={season}: {exc}"
        ) from exc

    if players_df.empty:
        raise SourceSchemaError(
            f"SoFIFA returned no player data for {league} season={season}"
        )

    # Fetch detailed player ratings
    try:
        ratings_df = scraper.read_player_ratings()
    except Exception as exc:
        raise SourceSchemaError(
            f"Failed to read SoFIFA player ratings for {league} season={season}: {exc}"
        ) from exc

    if ratings_df.empty:
        raise SourceSchemaError(
            f"SoFIFA returned no player ratings for {league} season={season}"
        )

    # Merge players + ratings on player name / index
    players_flat = players_df.reset_index()
    ratings_flat = ratings_df.reset_index()

    # Both have 'player' column; merge on it
    merged = players_flat.merge(
        ratings_flat,
        on="player",
        how="left",
        suffixes=("", "_rating"),
    )

    # Build output frame with standardized column names
    frame = _standardize_columns(merged)
    frame["league"] = league
    frame["season"] = season

    # Save parquet for traceability
    cache_path = (
        resolved_settings.raw_root
        / SOURCE_NAME
        / sofifa_league.replace(" ", "_").replace("[", "").replace("]", "")
        / str(season)
        / "player_attributes.parquet"
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(cache_path, index=False)

    # Build metadata
    source_uri = f"{SO_FIFA_API}/players?league={sofifa_league}&version={latest_version_id}"
    payload = cache_path.read_bytes()
    payload_sha256 = hashlib.sha256(payload).hexdigest()

    request_log = SourceRequestLogEntry(
        source_name=SOURCE_NAME,
        source_uri=source_uri,
        requested_at=datetime.now(tz=UTC),
        parser_version=PARSER_VERSION,
        response_sha256=payload_sha256,
        cache_hit=not force_refresh,
        status_code=200,
    )
    metadata = SourceMetadata(
        source_name=SOURCE_NAME,
        source_uri=source_uri,
        cache_path=cache_path,
        parser_version=PARSER_VERSION,
        source_file_sha256=payload_sha256,
        request_log=request_log,
        record_count=len(frame),
    )

    return AdapterResult(dataframe=frame, metadata=metadata)


def _resolve_league(league: str) -> str:
    """Resolve a league identifier to the SoFIFA league name."""
    mapping = LEAGUE_MAPPINGS.get(league)
    if mapping is None:
        raise ValueError(f"Unsupported SoFIFA league identifier: {league}")
    return mapping


def _resolve_fifa_edition(season: int) -> str:
    """Map a FIFA version year (e.g. 24) to the SoFIFA edition string."""
    edition = _FIFA_EDITION_MAP.get(season)
    if edition is None:
        supported = ", ".join(str(s) for s in sorted(_FIFA_EDITION_MAP))
        raise ValueError(
            f"Unsupported SoFIFA season={season}. Supported: {supported}"
        )
    return edition


# SoFIFA column name -> output column name
_COLUMN_MAP: dict[str, str] = {
    "player": "player_name",
    "team": "team_name",
    "overall_rating": "overall_rating",
    "potential": "potential",
    "acceleration": "pac",
    "sprint_speed": "pac",
    "finishing": "sho",
    "short_passing": "pas",
    "dribbling": "dri",
    "defensive_awareness": "def",
    "strength": "phy",
    "age": "age",
    "height": "height",
    "weight": "weight",
    "preferred_foot": "preferred_foot",
    "international_reputation": "international_reputation",
    "weak_foot": "weak_foot",
    "skill_moves": "skill_moves",
}


def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Select and rename columns to the output schema.

    SoFIFA returns many detailed stats. We aggregate the six
    composite attributes (PAC, SHO, PAS, DRI, DEF, PHY) from
    their sub-attributes when the composites are not directly
    available.
    """
    out = pd.DataFrame()

    out["player_name"] = df.get("player", pd.NA)
    out["team_name"] = df.get("team", pd.NA)

    # Position: SoFIFA read_players doesn't always include it;
    # try to extract from ratings if available
    if "position" in df.columns:
        out["position"] = df["position"]
    else:
        out["position"] = pd.NA

    # Overall / Potential
    out["overall_rating"] = _to_numeric(df.get("overall_rating", pd.NA))
    out["potential"] = _to_numeric(df.get("potential", pd.NA))

    # Composite attributes: use direct columns if available,
    # otherwise average sub-attributes
    out["pac"] = _composite_or_avg(df, "pac", ["acceleration", "sprint_speed"])
    out["sho"] = _composite_or_avg(
        df, "sho",
        ["finishing", "heading_accuracy", "volleys",
         "shot_power", "long_shots", "penalties", "positioning"],
    )
    out["pas"] = _composite_or_avg(
        df, "pas", ["crossing", "short_passing", "long_passing", "curve", "fk_accuracy", "vision"]
    )
    out["dri"] = _composite_or_avg(
        df, "dri", ["dribbling", "ball_control", "curve", "agility", "balance"]
    )
    out["def"] = _composite_or_avg(
        df, "def", ["defensive_awareness", "standing_tackle", "sliding tackle", "interceptions"]
    )
    out["phy"] = _composite_or_avg(
        df, "phy", ["strength", "aggression", "jumping", "stamina"]
    )

    # Bio attributes
    out["age"] = _to_numeric(df.get("age", pd.NA))
    out["height"] = df.get("height", pd.NA)
    out["weight"] = df.get("weight", pd.NA)
    out["preferred_foot"] = df.get("preferred_foot", pd.NA)
    out["international_reputation"] = _to_numeric(df.get("international_reputation", pd.NA))
    out["weak_foot"] = _to_numeric(df.get("weak_foot", pd.NA))
    out["skill_moves"] = _to_numeric(df.get("skill_moves", pd.NA))

    return out


def _composite_or_avg(
    df: pd.DataFrame,
    composite_col: str,
    sub_cols: list[str],
) -> pd.Series:
    """Return the composite column if present, else average sub-attributes."""
    if composite_col in df.columns:
        return _to_numeric(df[composite_col])
    available = [c for c in sub_cols if c in df.columns]
    if not available:
        return pd.Series(pd.NA, index=df.index)
    numeric = df[available].apply(_to_numeric)
    return numeric.mean(axis=1).round(0).astype("Int64")


def _to_numeric(series: pd.Series | object) -> pd.Series:
    """Convert a series to nullable Int64, coercing errors."""
    if isinstance(series, pd.Series):
        return pd.to_numeric(series, errors="coerce").astype("Int64")
    return pd.Series(pd.NA, dtype="Int64")
