"""Adapter manifest registry.

Builds ``AdapterManifest`` objects for the seven registered sources
and aggregates them into a single ``AdapterRegistry``. Manifests are
hand-curated from the actual ingester code and pipeline builders; if
a field mapping is not yet documented it is omitted rather than
guessed.

The registry is the I1 entry point for "what sources does this
project support and what does each one provide". Later I1 slices
(atomic-SPADL alignment, video references, tracking adapters) will
extend the same manifests instead of building a parallel catalog.
"""

from __future__ import annotations

import datetime as _dt

from scoutfootball import __version__
from scoutfootball.adapters.manifest import (
    AdapterCapability,
    AdapterManifest,
    AdapterRegistry,
    SchemaMapping,
)


def build_statsbomb_open_manifest() -> AdapterManifest:
    """StatsBomb Open Data: events, matches, lineups."""
    return AdapterManifest(
        source_id="statsbomb_open",
        parser_version="statsbomb_open/v0.1.0",
        module_path="scoutfootball.adapters.statsbomb_open",
        capabilities=(
            AdapterCapability.EVENT,
            AdapterCapability.LINEUP,
            AdapterCapability.FIXTURE,
            AdapterCapability.RESULT,
        ),
        schema_mappings=(
            SchemaMapping(
                source_field="event_id",
                internal_field="event_id",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="type.name",
                internal_field="event_type",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="player.id",
                internal_field="player_id",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="team.id",
                internal_field="team_id",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="minute",
                internal_field="minute",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="second",
                internal_field="second",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="location",
                internal_field="location",
                conversion="direct",
                note="Pitch coordinates in StatsBomb 120x80 convention; not normalized to 0-1.",
            ),
            SchemaMapping(
                source_field="pass.end_location",
                internal_field="pass_end_location",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="shot.statsbomb_xg",
                internal_field="shot_statsbomb_xg",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="match_id",
                internal_field="match_id",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="match.match_date",
                internal_field="match_date",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="lineup.player_id",
                internal_field="lineup_player_id",
                conversion="direct",
            ),
        ),
        conversion_loss_notes=(
            "StatsBomb event JSON is nested; the adapter flattens only the fields "
            "the project consumes. Fields not listed here (e.g. freeze_frame, "
            "tactics, substitutions detail) are dropped and not recoverable from "
            "the cached parquet. SPADL conversion lives in "
            "scoutfootball.action_value.spadl_adapter and is recorded separately."
        ),
        ingestion_cli="scoutfootball ingest --source statsbomb_open",
        artifact_paths=(
            "raw/statsbomb_open/events_sample.parquet",
            "raw/statsbomb_open/events_all.parquet",
            "raw/statsbomb_open/big5_matches.parquet",
            "raw/statsbomb_open/matches_all.parquet",
            "raw/statsbomb_open/lineups_all.parquet",
            "raw/statsbomb_open/lineups_sample.parquet",
            "raw/statsbomb_open/competitions.json",
        ),
        maintained=True,
        notes=(
            "Open Data User Protocol: free for research, attribution required, "
            "no redistribution of raw data."
        ),
    )


def build_football_data_manifest() -> AdapterManifest:
    """Football-Data.co.uk: fixtures and results CSV."""
    return AdapterManifest(
        source_id="football_data",
        parser_version="football_data/v0.1.0",
        module_path="scoutfootball.adapters.football_data",
        capabilities=(
            AdapterCapability.FIXTURE,
            AdapterCapability.RESULT,
        ),
        schema_mappings=(
            SchemaMapping(
                source_field="Div",
                internal_field="division",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="Date",
                internal_field="match_date",
                conversion="unit_conversion",
                note="DD/MM/YY string parsed to datetime64[ns].",
            ),
            SchemaMapping(
                source_field="HomeTeam",
                internal_field="home_team",
                conversion="direct",
                note="Raw string; normalized to internal team_id in silver layer.",
            ),
            SchemaMapping(
                source_field="AwayTeam",
                internal_field="away_team",
                conversion="direct",
                note="Raw string; normalized to internal team_id in silver layer.",
            ),
            SchemaMapping(
                source_field="FTHG",
                internal_field="goals_for",
                conversion="direct",
                note="Home goals; assigned to home team's goals_for on team_match.",
            ),
            SchemaMapping(
                source_field="FTAG",
                internal_field="goals_against",
                conversion="direct",
                note="Away goals; assigned to home team's goals_against on team_match.",
            ),
            SchemaMapping(
                source_field="FTR",
                internal_field="result",
                conversion="direct",
                note="H/D/A; mapped to home-team point count (3/1/0).",
            ),
            SchemaMapping(
                source_field="HS",
                internal_field="shots",
                conversion="direct",
                note="Home shots; missing for some leagues/seasons.",
            ),
            SchemaMapping(
                source_field="AS",
                internal_field="shots_on_target",
                conversion="approximate",
                note="Away shots used as proxy when HS/AS naming diverges; see pipeline.",
            ),
            SchemaMapping(
                source_field="B365H",
                internal_field="odds_home",
                conversion="direct",
                note="Bet365 closing odds; one of many bookmaker columns retained.",
            ),
        ),
        conversion_loss_notes=(
            "Football-Data CSV uses one row per match (not per team); the pipeline "
            "explodes each match into two team_match rows (home and away) and "
            "assigns goals_for/goals_against from the home/away perspective. "
            "Future-match placeholder rows (FTHG/FTAG/FTR all NaN) are filtered "
            "before match_id assignment. xG columns are not provided by this source "
            "(project xG comes from understat/fbref)."
        ),
        ingestion_cli="scoutfootball ingest --source football_data",
        artifact_paths=(
            "raw/football_data/combined_results.parquet",
            "raw/football_data/<season>/<league>.csv",
        ),
        maintained=True,
        notes="Non-commercial use; attribution suggested. 10 seasons, 20 leagues.",
    )


def build_clubelo_manifest() -> AdapterManifest:
    """ClubElo: team Elo rating snapshots."""
    return AdapterManifest(
        source_id="clubelo",
        parser_version="clubelo/v0.1.0",
        module_path="scoutfootball.adapters.clubelo",
        capabilities=(AdapterCapability.RATING,),
        schema_mappings=(
            SchemaMapping(
                source_field="Club",
                internal_field="team_name",
                conversion="direct",
                note="Raw ClubElo name; matched to internal team_id via normalize_team_name.",
            ),
            SchemaMapping(
                source_field="Country",
                internal_field="country",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="Level",
                internal_field="level",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="Elo",
                internal_field="elo_rating",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="from",
                internal_field="valid_from",
                conversion="direct",
                note="Snapshot validity start date.",
            ),
            SchemaMapping(
                source_field="to",
                internal_field="valid_to",
                conversion="direct",
                note="Snapshot validity end date; current ratings have 'to' empty.",
            ),
        ),
        conversion_loss_notes=(
            "ClubElo provides one rating per club per snapshot date; the pipeline "
            "joins to team_match by (team_name, match_date) and selects the most "
            "recent valid snapshot before kickoff. Rating drift between snapshots "
            "is not interpolated."
        ),
        ingestion_cli="scoutfootball ingest --source clubelo",
        artifact_paths=(
            "raw/clubelo/<YYYY-MM-DD>.csv",
        ),
        maintained=True,
        notes="Public data; attribution suggested. Snapshot date is the CSV filename.",
    )


def build_understat_manifest() -> AdapterManifest:
    """Understat: player-season attacking metrics."""
    return AdapterManifest(
        source_id="understat",
        parser_version="understat/v0.1.0",
        module_path="scoutfootball.adapters.understat",
        capabilities=(AdapterCapability.PLAYER_STATS,),
        schema_mappings=(
            SchemaMapping(
                source_field="id",
                internal_field="player_id",
                conversion="direct",
                note="Prefixed as 'understat|<id>' in player_match for source attribution.",
            ),
            SchemaMapping(
                source_field="player_name",
                internal_field="player_name",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="team_title",
                internal_field="team_name",
                conversion="approximate",
                note=(
                    "Season-mid transfers produce comma-joined multi-team strings "
                    "(e.g. 'Monaco,Nice'); pipeline keeps the first club as primary "
                    "and sets multi_team_season=True to preserve traceability."
                ),
            ),
            SchemaMapping(
                source_field="games",
                internal_field="matches_played",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="goals",
                internal_field="goals",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="assists",
                internal_field="assists",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="shots",
                internal_field="shots",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="time",
                internal_field="minutes_played",
                conversion="unit_conversion",
                note="Understat stores minutes as integer; pipeline preserves as-is.",
            ),
            SchemaMapping(
                source_field="xG",
                internal_field="npxg",
                conversion="approximate",
                note="Understat xG includes penalties; pipeline treats as npxg proxy.",
            ),
            SchemaMapping(
                source_field="xA",
                internal_field="xa",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="season",
                internal_field="season_id",
                conversion="unit_conversion",
                note="'201617' string mapped to '1617' season_id for internal consistency.",
            ),
        ),
        conversion_loss_notes=(
            "Understat JSON has one row per player-season; the adapter expands to "
            "one row per player per season (no match-level granularity from this "
            "source). Player-position is not provided; pipeline infers position "
            "from fbref/statsbomb when available. Float fields go through JSON "
            "serialize/deserialize and may have ULP-level precision differences; "
            "audits use math.isclose rather than exact equality."
        ),
        ingestion_cli="scoutfootball ingest --source understat",
        artifact_paths=(
            "raw/understat/players_10seasons.parquet",
            "raw/understat/players_<league>.json",
        ),
        maintained=True,
        notes="Public data; scrape respects robots.txt and ToS. 10 seasons, 6 leagues.",
    )


def build_fbref_manifest() -> AdapterManifest:
    """FBref: player-season standard tables."""
    return AdapterManifest(
        source_id="fbref",
        parser_version="fbref/v0.1.0",
        module_path="scoutfootball.adapters.fbref",
        capabilities=(AdapterCapability.PLAYER_STATS,),
        schema_mappings=(
            SchemaMapping(
                source_field="player",
                internal_field="player_name",
                conversion="direct",
                note="FBref raw stores player as DataFrame index.",
            ),
            SchemaMapping(
                source_field="('Performance', 'Gls')",
                internal_field="goals",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="('Performance', 'Ast')",
                internal_field="assists",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="('Playing Time', 'MP')",
                internal_field="matches_played",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="('Playing Time', 'Min')",
                internal_field="minutes_played",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="('Playing Time', 'Starts')",
                internal_field="starts",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="born",
                internal_field="born",
                conversion="direct",
                note="Birth year used to construct player_id 'name|birth_year|country'.",
            ),
            SchemaMapping(
                source_field="nation",
                internal_field="nationality",
                conversion="approximate",
                note="FBref uses FIFA 3-letter codes; pipeline normalizes via lookup.",
            ),
            SchemaMapping(
                source_field="comp",
                internal_field="league",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="season",
                internal_field="season_id",
                conversion="direct",
            ),
        ),
        conversion_loss_notes=(
            "FBref raw uses pandas MultiIndex columns ('Performance', 'Gls'); the "
            "adapter flattens via _flatten_raw helper. npxG/xA/shots are not in "
            "the standard table (they live in separate shooting/misc files) and "
            "are not loaded by this adapter. Player_id is constructed from "
            "name|birth_year|country rather than a stable FBref identifier, so "
            "cross-source identity resolution relies on the reep lookup."
        ),
        ingestion_cli="scoutfootball ingest --source fbref",
        artifact_paths=(
            "raw/fbref/player_stats_big5_3seasons.parquet",
        ),
        maintained=True,
        notes="Personal research only; no redistribution of raw data.",
    )


def build_transfermarkt_manual_manifest() -> AdapterManifest:
    """Transfermarkt manual import: market value and identity."""
    return AdapterManifest(
        source_id="transfermarkt_manual",
        parser_version="transfermarkt_manual/v0.1.0",
        module_path="scoutfootball.adapters.transfermarkt_manual",
        capabilities=(
            AdapterCapability.MARKET_VALUE,
            AdapterCapability.IDENTITY,
        ),
        schema_mappings=(
            SchemaMapping(
                source_field="player_id",
                internal_field="transfermarkt_player_id",
                conversion="direct",
                note="Transfermarkt numeric ID; used as truth-label anchor.",
            ),
            SchemaMapping(
                source_field="player_name",
                internal_field="player_name",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="current_market_value_eur",
                internal_field="market_value_eur",
                conversion="direct",
                note="Latest snapshot value; historical values in player_market_value.csv.",
            ),
            SchemaMapping(
                source_field="date_unix",
                internal_field="snapshot_date",
                conversion="unit_conversion",
                note="Unix timestamp converted to datetime for snapshot ledger.",
            ),
            SchemaMapping(
                source_field="player_market_value_eur",
                internal_field="historical_market_value_eur",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="player_profile_url",
                internal_field="transfermarkt_profile_url",
                conversion="direct",
            ),
        ),
        conversion_loss_notes=(
            "Manual import only: the maintainer downloads CSVs and places them "
            "in data/raw/transfermarkt_manual/. No automated scraping. Market "
            "values are subjective Transfermarkt estimates, not market prices; "
            "used as supervision labels for the rating NN, not as ground truth. "
            "The date_unix field is data content time, not a source snapshot date."
        ),
        ingestion_cli="scoutfootball ingest --source transfermarkt_manual",
        artifact_paths=(
            "raw/transfermarkt_manual/player_profiles.csv",
            "raw/transfermarkt_manual/player_market_value.csv",
            "raw/transfermarkt_manual/player_latest_market_value.csv",
        ),
        maintained=True,
        notes="Manual import only; no automated scraping.",
    )


def build_reep_manifest() -> AdapterManifest:
    """Reep: Wikidata-derived identity register (read-only lookup)."""
    return AdapterManifest(
        source_id="reep",
        parser_version="reep/v0.1.0",
        module_path="scoutfootball.evaluation.reep_identity",
        capabilities=(AdapterCapability.IDENTITY,),
        schema_mappings=(
            SchemaMapping(
                source_field="reep_id",
                internal_field="reep_id",
                conversion="direct",
                note="Stable Wikidata-derived identifier.",
            ),
            SchemaMapping(
                source_field="name",
                internal_field="name",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="full_name",
                internal_field="full_name",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="key_transfermarkt",
                internal_field="transfermarkt_id",
                conversion="direct",
                note="Cross-source identifier for Transfermarkt reconciliation.",
            ),
            SchemaMapping(
                source_field="key_fbref",
                internal_field="fbref_id",
                conversion="direct",
                note="Cross-source identifier for FBref reconciliation.",
            ),
            SchemaMapping(
                source_field="key_understat",
                internal_field="understat_id",
                conversion="direct",
                note="Cross-source identifier for Understat reconciliation.",
            ),
            SchemaMapping(
                source_field="nationality",
                internal_field="nationality",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="birth_year",
                internal_field="birth_year",
                conversion="direct",
            ),
        ),
        conversion_loss_notes=(
            "Reep is a read-only identity reference, not an ingester: there is no "
            "pipeline that writes silver/gold artifacts from reep rows. The "
            "reep-identity-lookup CLI performs exact-match lookups by provider ID "
            "and returns limited cross-identifiers for manual review. Reep does "
            "not establish market-value, performance, or truth-label facts."
        ),
        ingestion_cli="scoutfootball reep-identity-lookup --provider <p> --id <id>",
        artifact_paths=(
            "raw/reep/people.csv",
            "raw/reep/meta.json",
        ),
        maintained=True,
        notes="CC0 1.0 Universal; redistribution allowed. Identity reference only.",
    )


def build_adapter_registry() -> AdapterRegistry:
    """Build the canonical adapter manifest registry.

    The registry is generated in code (not loaded from a file) so it
    stays in sync with the adapter modules. Each manifest is built by
    a dedicated function that documents the actual fields the adapter
    reads and writes.
    """
    manifests = (
        build_statsbomb_open_manifest(),
        build_football_data_manifest(),
        build_clubelo_manifest(),
        build_understat_manifest(),
        build_fbref_manifest(),
        build_transfermarkt_manual_manifest(),
        build_reep_manifest(),
    )
    return AdapterRegistry(
        generated_at=_dt.datetime.now(_dt.UTC).isoformat(),
        package_version=__version__,
        manifests=manifests,
    )
