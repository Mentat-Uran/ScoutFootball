"""Canonical architecture manifest for the scaffold."""

from __future__ import annotations

from .schemas import DataDirectorySpec, ModuleBoundary, ProjectArchitecture


def build_default_architecture() -> ProjectArchitecture:
    return ProjectArchitecture(
        package_name="scoutlab",
        status=(
            "Phase 9 Streamlit MVP initialized; "
            "adapter, bridge-building, feature-store, baseline-model, "
            "and interactive visualization primitives exist."
        ),
        module_boundaries=(
            ModuleBoundary(
                name="adapters",
                purpose="External data ingestion and manual import boundaries.",
                planned_components=(
                    "statsbomb_open",
                    "football_data",
                    "clubelo",
                    "understat",
                    "fbref",
                    "transfermarkt_manual",
                ),
            ),
            ModuleBoundary(
                name="entities",
                purpose="Canonical team/player identity resolution and bridge tables.",
                planned_components=("normalization", "matching", "bridge_tables"),
            ),
            ModuleBoundary(
                name="storage",
                purpose="DuckDB, Parquet and filesystem layout utilities.",
                planned_components=("duckdb_io", "parquet_io", "metadata_logging"),
            ),
            ModuleBoundary(
                name="features",
                purpose="Feature table generation without future leakage.",
                planned_components=("team_match", "player_match", "rolling_features"),
            ),
            ModuleBoundary(
                name="models",
                purpose="Interpretable modeling tasks and artifact boundaries.",
                planned_components=("market_value", "match_prediction", "style_embedding"),
            ),
            ModuleBoundary(
                name="evaluation",
                purpose="Time-series backtests, calibration and model reports.",
                planned_components=("backtests", "calibration", "reporting"),
            ),
            ModuleBoundary(
                name="viz",
                purpose="Plotly chart definitions for research outputs.",
                planned_components=("player_compare", "trend_charts", "probability_matrix"),
            ),
            ModuleBoundary(
                name="app",
                purpose="Streamlit views that only read local artifacts.",
                planned_components=("player_compare_page", "market_value_page", "match_page"),
            ),
        ),
        data_directories=(
            DataDirectorySpec(
                layer="raw",
                relative_path="raw/statsbomb_open",
                purpose="Immutable official open-data JSON snapshots.",
            ),
            DataDirectorySpec(
                layer="raw",
                relative_path="raw/football_data",
                purpose="Downloaded CSV baselines for fixtures, results and odds.",
            ),
            DataDirectorySpec(
                layer="raw",
                relative_path="raw/clubelo",
                purpose="Team Elo snapshots before silver normalization.",
            ),
            DataDirectorySpec(
                layer="raw",
                relative_path="raw/understat",
                purpose="Cached supplemental attacking metrics.",
            ),
            DataDirectorySpec(
                layer="raw",
                relative_path="raw/fbref",
                purpose="Low-frequency cached standard-table extracts.",
            ),
            DataDirectorySpec(
                layer="raw",
                relative_path="raw/transfermarkt_manual",
                purpose="Manually provided market and contract snapshots.",
            ),
            DataDirectorySpec(
                layer="silver",
                relative_path="silver/dimensions",
                purpose="Normalized competitions, teams, players and seasons.",
            ),
            DataDirectorySpec(
                layer="silver",
                relative_path="silver/facts",
                purpose="Normalized matches, lineups, events and market snapshots.",
            ),
            DataDirectorySpec(
                layer="silver",
                relative_path="silver/bridge",
                purpose="Cross-source identity bridge tables and review logs.",
            ),
            DataDirectorySpec(
                layer="gold",
                relative_path="gold/marts",
                purpose="Analytical marts for research and reporting.",
            ),
            DataDirectorySpec(
                layer="gold",
                relative_path="gold/feature_store",
                purpose="Reusable feature tables keyed by entity and cutoff date.",
            ),
            DataDirectorySpec(
                layer="models",
                relative_path="models/training_sets",
                purpose="Frozen training datasets with version metadata.",
            ),
            DataDirectorySpec(
                layer="models",
                relative_path="models/artifacts",
                purpose="Serialized models, configs and feature manifests.",
            ),
            DataDirectorySpec(
                layer="models",
                relative_path="models/oof_predictions",
                purpose="Out-of-fold predictions for validation and calibration.",
            ),
            DataDirectorySpec(
                layer="reports",
                relative_path="reports/html",
                purpose="Rendered local HTML research reports.",
            ),
            DataDirectorySpec(
                layer="reports",
                relative_path="reports/pdf",
                purpose="Exported PDF reports when later enabled.",
            ),
            DataDirectorySpec(
                layer="logs",
                relative_path="logs/ingestion",
                purpose="Source request logs, hashes and ingest manifests.",
            ),
            DataDirectorySpec(
                layer="logs",
                relative_path="logs/validation",
                purpose="Schema checks, data-quality reports and drift warnings.",
            ),
        ),
        supported_commands=(
            "uv sync",
            "uv run pytest",
            "uv run ruff check .",
            "uv run python -m scoutlab",
        ),
    )
