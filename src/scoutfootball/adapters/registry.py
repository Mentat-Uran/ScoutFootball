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
    """Transfermarkt manual import: market value and identity.

    Two on-disk CSV shapes are supported:

    1. **Denormalized single-CSV snapshot** consumed by
       ``adapters.transfermarkt_manual.load_snapshot`` (used by the
       truth-label bridge). Expected columns: ``player_name``,
       ``team_name``, ``snapshot_date``, ``market_value_raw``.
    2. **Normalized two-CSV profiles + valuations** consumed directly by
       ``api._load_market_value_frame`` Path 2 (used by the market-value
       API endpoints). Files: ``player_profiles.csv`` (player_id →
       name/club/position) and ``player_market_value.csv`` (player_id,
       date_unix, value). The API joins on ``player_id`` and strips the
       trailing ``(<id>)`` suffix Transfermarkt appends to display names.

    The schema_mappings below document the **normalized two-CSV path**
    because that is the shape currently on disk (2026-07-31).
    """
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
                source_field="player_profiles.player_id",
                internal_field="transfermarkt_player_id",
                conversion="direct",
                note="Transfermarkt numeric ID; join key between profiles and valuations.",
            ),
            SchemaMapping(
                source_field="player_profiles.player_name",
                internal_field="player_name",
                conversion="direct",
                note=(
                    "Transfermarkt appends '(<id>)' suffix to disambiguate "
                    "duplicates; api._load_market_value_frame strips it via "
                    "regex r'\\s*\\(\\d+\\)\\s*$' so responses carry the bare name."
                ),
            ),
            SchemaMapping(
                source_field="player_profiles.current_club_name",
                internal_field="team_name",
                conversion="direct",
                note="Free-text club name; not normalized to internal team_id.",
            ),
            SchemaMapping(
                source_field="player_profiles.position",
                internal_field="position",
                conversion="direct",
                note=(
                    "Transfermarkt position label (e.g. 'Attack - Right Winger'); "
                    "not normalized to internal RoleFamily."
                ),
            ),
            SchemaMapping(
                source_field="player_market_value.date_unix",
                internal_field="snapshot_date",
                conversion="unit_conversion",
                note="YYYY-MM-DD string parsed to datetime64[ns] via pd.to_datetime.",
            ),
            SchemaMapping(
                source_field="player_market_value.value",
                internal_field="market_value_eur",
                conversion="direct",
                note="Numeric EUR value; Transfermarkt subjective estimate, not market price.",
            ),
            SchemaMapping(
                source_field="player_profiles.player_profile_url",
                internal_field="transfermarkt_profile_url",
                conversion="direct",
            ),
        ),
        conversion_loss_notes=(
            "Manual import only: the maintainer downloads CSVs and places them "
            "in data/raw/transfermarkt_manual/. No automated scraping. Market "
            "values are subjective Transfermarkt estimates, not market prices; "
            "used as supervision labels for the rating NN, not as ground truth. "
            "The date_unix field is data content time, not a source snapshot date. "
            "The denormalized load_snapshot path (used by snapshot_to_truth_labels) "
            "expects a different single-CSV schema and will raise SourceSchemaError "
            "if pointed at the normalized two-CSV files; the two paths serve "
            "different consumers and are not interchangeable."
        ),
        ingestion_cli="scoutfootball ingest --source transfermarkt_manual",
        artifact_paths=(
            "raw/transfermarkt_manual/player_profiles.csv",
            "raw/transfermarkt_manual/player_market_value.csv",
            "raw/transfermarkt_manual/player_latest_market_value.csv",
        ),
        maintained=True,
        notes=(
            "Manual import only; no automated scraping. Maintainer confirmed "
            "personal local use OK; redistribution requires Transfermarkt ToS "
            "review. Market values are subjective estimates, not market prices."
        ),
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


def build_sofascore_manifest() -> AdapterManifest:
    """SofaScore: schedule and team-level league table (experimental).

    Wired through ``scoutfootball ingest --source sofascore`` but not in
    the maintainer's real workflow (confirmed 2026-07-17). The function
    name ``fetch_player_match_stats`` and its docstring imply player
    match ratings, but the implementation reads ``read_schedule`` and
    ``read_league_table`` and returns match-level plus team-level data;
    no player ratings are produced by the current code path. The
    manifest documents actual behavior, not the docstring intent.
    """
    return AdapterManifest(
        source_id="sofascore",
        parser_version="sofascore/v0.1.0",
        module_path="scoutfootball.adapters.sofascore",
        capabilities=(
            AdapterCapability.FIXTURE,
            AdapterCapability.RESULT,
            AdapterCapability.PLAYER_STATS,
        ),
        schema_mappings=(
            SchemaMapping(
                source_field="home_team",
                internal_field="home_team",
                conversion="direct",
                note="Schedule row home team; soccerdata name, not internal team_id.",
            ),
            SchemaMapping(
                source_field="away_team",
                internal_field="away_team",
                conversion="direct",
                note="Schedule row away team; soccerdata name, not internal team_id.",
            ),
            SchemaMapping(
                source_field="date",
                internal_field="match_date",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="home_score",
                internal_field="home_score",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="away_score",
                internal_field="away_score",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="team",
                internal_field="team_name",
                conversion="direct",
                note="From league_table merge; raw soccerdata name.",
            ),
            SchemaMapping(
                source_field="MP",
                internal_field="matches_played",
                conversion="direct",
                note="Team-season aggregate, not player-level.",
            ),
            SchemaMapping(
                source_field="W",
                internal_field="wins",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="D",
                internal_field="draws",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="L",
                internal_field="losses",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="GF",
                internal_field="goals_for",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="GA",
                internal_field="goals_against",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="Pts",
                internal_field="points",
                conversion="direct",
            ),
        ),
        conversion_loss_notes=(
            "Function name and docstring claim player match ratings (player_name, "
            "rating, position, minutes_played) but the implementation returns "
            "schedule + league_table data; player ratings are NOT produced. This "
            "doc/code mismatch is intentional in the manifest: it describes actual "
            "behavior. Uses the unofficial api.sofascore.com endpoint via "
            "soccerdata; not an official API, redistribution boundary unclear. "
            "Requires soccerdata package which is not in default project deps."
        ),
        ingestion_cli="scoutfootball ingest --source sofascore",
        artifact_paths=(
            "raw/sofascore/<league>/<season>/schedule.parquet",
            "raw/sofascore/<league>/<season>/league_table.parquet",
        ),
        maintained=False,
        notes=(
            "Experimental, not in maintainer's real workflow (confirmed 2026-07-17). "
            "Requires soccerdata package. Uses unofficial API; redistribution unclear."
        ),
    )


def build_sofifa_manifest() -> AdapterManifest:
    """SoFIFA: FIFA player attributes via soccerdata (experimental).

    Wired through ``scoutfootball ingest --source sofifa`` but the
    pipeline ``_ingest_sofifa`` is a placeholder that returns 'skipped:
    SoFIFA adapter not yet implemented' without calling the adapter, so
    no data actually flows through the CLI today.
    """
    return AdapterManifest(
        source_id="sofifa",
        parser_version="sofifa/v0.1.0",
        module_path="scoutfootball.adapters.sofifa",
        capabilities=(AdapterCapability.PLAYER_STATS,),
        schema_mappings=(
            SchemaMapping(
                source_field="player",
                internal_field="player_name",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="team",
                internal_field="team_name",
                conversion="direct",
                note="SoFIFA club name; not normalized to internal team_id.",
            ),
            SchemaMapping(
                source_field="overall_rating",
                internal_field="overall_rating",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="potential",
                internal_field="potential",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="pac",
                internal_field="pac",
                conversion="derived",
                note="Direct column if present, else averaged from acceleration+sprint_speed.",
            ),
            SchemaMapping(
                source_field="sho",
                internal_field="sho",
                conversion="derived",
                note="Direct column if present, else averaged from 7 shooting sub-attributes.",
            ),
            SchemaMapping(
                source_field="pas",
                internal_field="pas",
                conversion="derived",
                note="Direct column if present, else averaged from 6 passing sub-attributes.",
            ),
            SchemaMapping(
                source_field="dri",
                internal_field="dri",
                conversion="derived",
                note="Direct column if present, else averaged from 5 dribbling sub-attributes.",
            ),
            SchemaMapping(
                source_field="def",
                internal_field="def",
                conversion="derived",
                note="Direct column if present, else averaged from 4 defending sub-attributes.",
            ),
            SchemaMapping(
                source_field="phy",
                internal_field="phy",
                conversion="derived",
                note="Direct column if present, else averaged from 4 physical sub-attributes.",
            ),
            SchemaMapping(
                source_field="age",
                internal_field="age",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="preferred_foot",
                internal_field="preferred_foot",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="international_reputation",
                internal_field="international_reputation",
                conversion="direct",
            ),
        ),
        conversion_loss_notes=(
            "FIFA composite attributes (PAC/SHO/PAS/DRI/DEF/PHY) are derived by "
            "averaging sub-attributes when the composite column is not directly "
            "available; the averaging is a heuristic, not EA Sports' official "
            "formula. FIFA player attributes are EA Sports intellectual property "
            "derived from the FIFA/EA FC video game, not real-world measurements; "
            "they are useful for player comparison but should not be reported as "
            "physical performance. Requires soccerdata package which is not in "
            "default project deps. The pipeline _ingest_sofifa is a placeholder "
            "that does not actually invoke this adapter."
        ),
        ingestion_cli="scoutfootball ingest --source sofifa",
        artifact_paths=(
            "raw/sofifa/<league>/<season>/player_attributes.parquet",
        ),
        maintained=False,
        notes=(
            "Experimental, not in maintainer's real workflow (confirmed 2026-07-17). "
            "Pipeline ingest is a placeholder; adapter code exists but is not invoked. "
            "FIFA attributes are EA Sports IP, not real-world measurements."
        ),
    )


def build_api_football_manifest() -> AdapterManifest:
    """API-Football: injuries and transfers via official API (experimental).

    Wired through ``scoutfootball ingest --source api_football``; the
    pipeline catches ``ApiKeyMissingError`` and skips gracefully when no
    key is configured, so the platform works without it. Free-tier
    limit is 100 requests/day.
    """
    return AdapterManifest(
        source_id="api_football",
        parser_version="api_football/v0.1.0",
        module_path="scoutfootball.adapters.api_football",
        capabilities=(
            AdapterCapability.INJURY,
            AdapterCapability.TRANSFER,
        ),
        schema_mappings=(
            # /injuries endpoint
            SchemaMapping(
                source_field="player.name",
                internal_field="player_name",
                conversion="direct",
                note="From /injuries response.player.name.",
            ),
            SchemaMapping(
                source_field="team.name",
                internal_field="team_name",
                conversion="direct",
                note="From /injuries response.team.name.",
            ),
            SchemaMapping(
                source_field="injury.type",
                internal_field="injury_type",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="injury.reason",
                internal_field="reason",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="injury.date_start",
                internal_field="date_start",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="injury.date_end",
                internal_field="date_end",
                conversion="direct",
                note="May be empty for ongoing injuries.",
            ),
            # /transfers endpoint
            SchemaMapping(
                source_field="player.name",
                internal_field="player_name",
                conversion="direct",
                note="From /transfers response.player.name.",
            ),
            SchemaMapping(
                source_field="transfers[].from.name",
                internal_field="from_team",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="transfers[].to.name",
                internal_field="to_team",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="transfers[].type",
                internal_field="transfer_type",
                conversion="direct",
            ),
            SchemaMapping(
                source_field="transfers[].date",
                internal_field="date",
                conversion="direct",
                note="Date object flattened to string; format varies.",
            ),
            SchemaMapping(
                source_field="transfers[].fee",
                internal_field="fee",
                conversion="direct",
                note="Free-text fee string; not parsed to numeric value.",
            ),
        ),
        conversion_loss_notes=(
            "Requires API_FOOTBALL_KEY environment variable; free-tier limit 100 "
            "requests/day enforced by _DailyRequestCounter. The /coachs endpoint "
            "is implemented in fetch_coaches but does not map to any documented "
            "capability and is not exposed in this manifest. Transfer fee is a "
            "free-text string (e.g. '€25m', 'loan', 'free') and is not parsed to "
            "a numeric value by this adapter. Paginated responses are merged into "
            "a single JSON cache file; the original page boundaries are lost."
        ),
        ingestion_cli="scoutfootball ingest --source api_football",
        artifact_paths=(
            "raw/api_football/injuries/<league_id>/<season>.json",
            "raw/api_football/transfers/<team_id>.json",
            "raw/api_football/coaches/<league_id>/<season>.json",
        ),
        maintained=False,
        notes=(
            "Experimental, not in maintainer's real workflow (confirmed 2026-07-17). "
            "Requires API_FOOTBALL_KEY; free-tier 100 requests/day. "
            "API-Football (api-sports.io) official license."
        ),
    )


def build_transfermarkt_datasets_manifest() -> AdapterManifest:
    """transfermarkt-datasets: bulk DuckDB export (experimental).

    Downloads a pre-built ~500MB DuckDB file from
    ``dcaribou/transfermarkt-datasets`` and exports individual tables
    to Parquet without field-level transformation. The adapter is a
    table dumper, not a field mapper: schema_mappings is intentionally
    empty because no source-to-internal field mapping occurs at this
    layer.
    """
    return AdapterManifest(
        source_id="transfermarkt_datasets",
        parser_version="transfermarkt_datasets/v0.1.0",
        module_path="scoutfootball.adapters.transfermarkt_datasets",
        capabilities=(
            AdapterCapability.MARKET_VALUE,
            AdapterCapability.TRANSFER,
            AdapterCapability.PLAYER_STATS,
            AdapterCapability.LINEUP,
            AdapterCapability.FIXTURE,
            AdapterCapability.RESULT,
        ),
        schema_mappings=(
            # Intentionally empty: this adapter dumps raw tables to Parquet
            # without field-level mapping. Downstream code performs any
            # needed transformations. Documenting fake mappings here would
            # violate the manifest's conservatism principle.
        ),
        conversion_loss_notes=(
            "Adapter exports raw DuckDB tables to Parquet without field-level "
            "transformation; schema_mappings is empty because no source-to-"
            "internal mapping occurs at this layer. The ~500MB DuckDB file is "
            "downloaded from an external R2 storage URL on first use and cached "
            "locally; subsequent runs read the cache. Tables are dumped as-is, "
            "so downstream consumers must handle schema drift in the upstream "
            "dataset. The adapter does not verify column names against an "
            "internal schema; it only checks that the expected table names "
            "exist in the DuckDB file. game_events table is exported but not "
            "claimed as EVENT capability because the schema is unverified and "
            "not consumed by any current pipeline."
        ),
        ingestion_cli="scoutfootball ingest --source transfermarkt_datasets",
        artifact_paths=(
            "raw/transfermarkt_datasets/transfermarkt-datasets.duckdb",
            "raw/transfermarkt_datasets/player_valuations.parquet",
            "raw/transfermarkt_datasets/transfers.parquet",
            "raw/transfermarkt_datasets/appearances.parquet",
            "raw/transfermarkt_datasets/game_lineups.parquet",
            "raw/transfermarkt_datasets/games.parquet",
            "raw/transfermarkt_datasets/club_games.parquet",
        ),
        maintained=False,
        notes=(
            "Experimental, not in maintainer's real workflow (confirmed 2026-07-17). "
            "Downloads ~500MB external DuckDB file from dcaribou/transfermarkt-datasets. "
            "Maintainer confirmed personal local use OK (2026-07-17); redistribution "
            "requires checking upstream dataset license and Transfermarkt ToS."
        ),
    )


def build_whoscored_manifest() -> AdapterManifest:
    """WhoScored: player ratings, match events, missing players via Selenium (experimental).

    The adapter module exports three fetch functions (player ratings,
    match events, missing players) backed by soccerdata's WhoScored
    scraper, which drives Selenium/Chrome against whoscored.com match
    pages. The functions are importable from
    ``scoutfootball.adapters`` but are NOT wired into
    ``run_daily_ingest``: passing ``whoscored`` to the pipeline returns
    ``"skipped: unknown source 'whoscored'"``. The manifest documents
    this honestly so consumers do not infer the source is ingestible
    from its presence in the registry.
    """
    return AdapterManifest(
        source_id="whoscored",
        parser_version="whoscored/v0.1.0",
        module_path="scoutfootball.adapters.whoscored",
        capabilities=(
            AdapterCapability.RATING,
            AdapterCapability.EVENT,
            AdapterCapability.INJURY,
        ),
        schema_mappings=(
            # fetch_player_match_ratings output
            SchemaMapping(
                source_field="player_name",
                internal_field="player_name",
                conversion="direct",
                note=(
                    "Scraped from match page ratings table; "
                    "source is WhoScored player name string."
                ),
            ),
            SchemaMapping(
                source_field="team_name",
                internal_field="team_name",
                conversion="direct",
                note="Derived from schedule home_team/away_team for the side being scraped.",
            ),
            SchemaMapping(
                source_field="match_date",
                internal_field="match_date",
                conversion="direct",
                note="From schedule row date; not the scrape timestamp.",
            ),
            SchemaMapping(
                source_field="rating",
                internal_field="rating",
                conversion="direct",
                note="WhoScored 1-10 player match rating derived from Opta event data.",
            ),
            SchemaMapping(
                source_field="position",
                internal_field="position",
                conversion="direct",
                note="Scraped from match page; not normalized to internal position codes.",
            ),
            # fetch_match_events output
            SchemaMapping(
                source_field="match_id",
                internal_field="match_id",
                conversion="direct",
                note=(
                    "WhoScored game_id from schedule; "
                    "not the same namespace as statsbomb match_id."
                ),
            ),
            SchemaMapping(
                source_field="event_type",
                internal_field="event_type",
                conversion="direct",
                note="Renamed from soccerdata 'type' column.",
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
                source_field="x",
                internal_field="x",
                conversion="approximate",
                note="WhoScored pitch coordinates; scale convention not normalized to 0-1.",
            ),
            SchemaMapping(
                source_field="y",
                internal_field="y",
                conversion="approximate",
                note="WhoScored pitch coordinates; scale convention not normalized to 0-1.",
            ),
            SchemaMapping(
                source_field="end_x",
                internal_field="end_x",
                conversion="approximate",
            ),
            SchemaMapping(
                source_field="end_y",
                internal_field="end_y",
                conversion="approximate",
            ),
            SchemaMapping(
                source_field="is_shot",
                internal_field="is_shot",
                conversion="direct",
                note="Defaulted to False when source column missing.",
            ),
            SchemaMapping(
                source_field="is_goal",
                internal_field="is_goal",
                conversion="direct",
                note="Defaulted to False when source column missing.",
            ),
            SchemaMapping(
                source_field="card_type",
                internal_field="card_type",
                conversion="direct",
                note="NaN when source column missing.",
            ),
            SchemaMapping(
                source_field="outcome_type",
                internal_field="outcome_type",
                conversion="direct",
                note="NaN when source column missing.",
            ),
            # fetch_missing_players output
            SchemaMapping(
                source_field="reason",
                internal_field="reason",
                conversion="direct",
                note="Injury/suspension reason text from WhoScored missing-players feed.",
            ),
            SchemaMapping(
                source_field="status",
                internal_field="status",
                conversion="direct",
                note="Missing-player status string; not normalized to an enum.",
            ),
        ),
        conversion_loss_notes=(
            "Three fetch functions exist but none is wired into run_daily_ingest: "
            "passing 'whoscored' to scoutfootball ingest returns 'skipped: unknown "
            "source'. Player ratings are scraped from match pages via Selenium with "
            "a 2-second sleep per match, making large-season scraping slow and "
            "fragile; when scraping fails the adapter falls back to returning the "
            "schedule with NaN ratings and empty player_name, which downstream "
            "consumers must not mistake for real ratings. Event coordinates (x, y, "
            "end_x, end_y) are kept as raw WhoScored values and not normalized to "
            "the StatsBomb 120x80 convention or a 0-1 scale; cross-source event "
            "alignment with statsbomb_open is not safe without explicit "
            "coordinate transformation. match_id is WhoScored's game_id namespace "
            "and does not collide with statsbomb match_id. The missing-players "
            "match_date is derived from the schedule 'game' column when present, "
            "else NaT. Requires soccerdata + Selenium + Chrome/Chromium, none of "
            "which are in default project deps. Uses unofficial Selenium scraping "
            "of whoscored.com; ToS and redistribution boundary unclear."
        ),
        ingestion_cli="scoutfootball ingest --sources whoscored",
        artifact_paths=(
            "raw/whoscored/<league>/<season>/player_ratings.parquet",
            "raw/whoscored/<league>/<season>/match_events.parquet",
            "raw/whoscored/<league>/<season>/missing_players.parquet",
        ),
        maintained=False,
        notes=(
            "Experimental, not in maintainer's real workflow (confirmed 2026-07-17). "
            "Adapter functions are importable but NOT wired into run_daily_ingest: "
            "the pipeline returns 'skipped: unknown source' for whoscored. "
            "Requires soccerdata + Selenium + Chrome/Chromium. "
            "Uses unofficial Selenium scraping of whoscored.com; redistribution unclear."
        ),
    )


def build_capology_manifest() -> AdapterManifest:
    """Capology: player salary data via ScraperFC (experimental).

    The adapter module exports ``fetch_player_salaries`` backed by
    ScraperFC's Capology scraper. The function is importable from
    ``scoutfootball.adapters`` but is NOT wired into
    ``run_daily_ingest``: passing ``capology`` to the pipeline returns
    ``"skipped: unknown source 'capology'"``. Salary is a player-level
    contract fact (not a market-value estimate), so the capability is
    PLAYER_STATS rather than MARKET_VALUE.
    """
    return AdapterManifest(
        source_id="capology",
        parser_version="capology/v0.1.0",
        module_path="scoutfootball.adapters.capology",
        capabilities=(AdapterCapability.PLAYER_STATS,),
        schema_mappings=(
            SchemaMapping(
                source_field="player_name",
                internal_field="player_name",
                conversion="direct",
                note="Heuristic-detected from raw ScraperFC columns (player/name lookup).",
            ),
            SchemaMapping(
                source_field="team_name",
                internal_field="team_name",
                conversion="direct",
                note="Heuristic-detected from raw club/team columns.",
            ),
            SchemaMapping(
                source_field="position",
                internal_field="position",
                conversion="direct",
                note=(
                    "Heuristic-detected from pos/position columns; "
                    "not normalized to internal position codes."
                ),
            ),
            SchemaMapping(
                source_field="weekly_gross_salary",
                internal_field="weekly_gross_salary",
                conversion="approximate",
                note=(
                    "Parsed from raw string by stripping non-digit chars; "
                    "currency hardcoded to GBP."
                ),
            ),
            SchemaMapping(
                source_field="annual_gross_salary",
                internal_field="annual_gross_salary",
                conversion="approximate",
                note=(
                    "Parsed from raw string by stripping non-digit chars; "
                    "currency hardcoded to GBP."
                ),
            ),
            SchemaMapping(
                source_field="weekly_net_salary",
                internal_field="weekly_net_salary",
                conversion="approximate",
                note=(
                    "Parsed from raw string by stripping non-digit chars; "
                    "currency hardcoded to GBP."
                ),
            ),
            SchemaMapping(
                source_field="annual_net_salary",
                internal_field="annual_net_salary",
                conversion="approximate",
                note=(
                    "Parsed from raw string by stripping non-digit chars; "
                    "currency hardcoded to GBP."
                ),
            ),
            SchemaMapping(
                source_field="expiry_date",
                internal_field="expiry_date",
                conversion="direct",
                note="Contract expiry date string; not parsed to datetime.",
            ),
        ),
        conversion_loss_notes=(
            "fetch_player_salaries is importable but NOT wired into run_daily_ingest: "
            "passing 'capology' to scoutfootball ingest returns 'skipped: unknown "
            "source'. ScraperFC returns a MultiIndex-column DataFrame whose exact "
            "column names vary by Capology page structure; the adapter uses "
            "heuristic _detect_column_mapping (lowercase substring match) to find "
            "player/team/position/salary columns, so any Capology HTML redesign "
            "can silently misroute columns. Salary values are parsed from raw "
            "strings by stripping non-digit characters and replacing empties with "
            "0.0, which masks parse failures as zero salary rather than raising. "
            "Currency is hardcoded to GBP via scraper.scrape_salaries(season, "
            "league, 'gbp'); other currencies are not exposed. Salary is a "
            "contract fact reported by Capology, not a market-value estimate, so "
            "the capability is PLAYER_STATS rather than MARKET_VALUE. Requires "
            "ScraperFC which is not in default project deps. Uses unofficial "
            "scraping of capology.com; ToS and redistribution boundary unclear."
        ),
        ingestion_cli="scoutfootball ingest --sources capology",
        artifact_paths=(
            "raw/capology/<league>/<season>/player_salaries.parquet",
        ),
        maintained=False,
        notes=(
            "Experimental, not in maintainer's real workflow (confirmed 2026-07-17). "
            "Adapter function is importable but NOT wired into run_daily_ingest: "
            "the pipeline returns 'skipped: unknown source' for capology. "
            "Requires ScraperFC. Currency hardcoded to GBP. "
            "Uses unofficial scraping of capology.com; redistribution unclear."
        ),
    )


def build_adapter_registry() -> AdapterRegistry:
    """Build the canonical adapter manifest registry.

    The registry is generated in code (not loaded from a file) so it
    stays in sync with the adapter modules. Each manifest is built by
    a dedicated function that documents the actual fields the adapter
    reads and writes.

    The registry includes both maintained sources (in the maintainer's
    real workflow) and experimental sources (implemented but not in
    active use, marked ``maintained=False``). Experimental sources are
    registered so the manifest surface honestly reflects the codebase;
    consumers can filter on ``maintained=True`` to see only active sources.
    """
    manifests = (
        build_statsbomb_open_manifest(),
        build_football_data_manifest(),
        build_clubelo_manifest(),
        build_understat_manifest(),
        build_fbref_manifest(),
        build_transfermarkt_manual_manifest(),
        build_reep_manifest(),
        build_sofascore_manifest(),
        build_sofifa_manifest(),
        build_api_football_manifest(),
        build_transfermarkt_datasets_manifest(),
        build_whoscored_manifest(),
        build_capology_manifest(),
    )
    return AdapterRegistry(
        generated_at=_dt.datetime.now(_dt.UTC).isoformat(),
        package_version=__version__,
        manifests=manifests,
    )
