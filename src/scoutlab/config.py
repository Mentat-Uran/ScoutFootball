"""Project-level settings, path resolution, and ingest configuration."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class PlatformSettings(BaseModel):
    """Resolved project paths for local development."""

    model_config = ConfigDict(frozen=True)

    project_root: Path
    source_root: Path
    test_root: Path
    data_root: Path
    raw_root: Path
    silver_root: Path
    gold_root: Path
    model_root: Path
    report_root: Path
    log_root: Path

    @classmethod
    def from_root(cls, root: Path | None = None) -> PlatformSettings:
        project_root = (root or Path(__file__).resolve().parents[2]).resolve()
        data_root = project_root / "data"
        return cls(
            project_root=project_root,
            source_root=project_root / "src",
            test_root=project_root / "tests",
            data_root=data_root,
            raw_root=data_root / "raw",
            silver_root=data_root / "silver",
            gold_root=data_root / "gold",
            model_root=data_root / "models",
            report_root=data_root / "reports",
            log_root=data_root / "logs",
        )


# ---------------------------------------------------------------------------
# Ingest configuration
# ---------------------------------------------------------------------------


class LeagueConfig(BaseModel):
    """Configuration for a single league across all data sources."""

    model_config = ConfigDict(frozen=True)

    name: str
    fbref_id: str | None = None
    fbref_comp_id: int | None = None
    fbref_slug: str | None = None
    football_data_code: str | None = None
    understat_name: str | None = None
    sofascore_id: int | None = None
    sofifa_id: int | None = None
    api_football_id: int | None = None
    statsbomb_comp_id: int | None = None


class IngestConfig(BaseModel):
    """Centralized configuration for data ingestion pipelines."""

    model_config = ConfigDict(frozen=True)

    leagues: list[LeagueConfig]
    season_start_year: int = 2016
    season_end_year: int = 2026
    sources_enabled: dict[str, bool] = {
        "fbref": True,
        "football_data": True,
        "understat": True,
        "statsbomb_open": True,
        "clubelo": True,
        "sofascore": True,
        "sofifa": True,
        "api_football": False,
    }

    @property
    def seasons(self) -> list[int]:
        """Return season start years from season_start_year to season_end_year (inclusive)."""
        return list(range(self.season_start_year, self.season_end_year + 1))

    @property
    def fbref_leagues(self) -> list[LeagueConfig]:
        """Return leagues that have an fbref_id configured."""
        return [lg for lg in self.leagues if lg.fbref_id is not None]

    @property
    def football_data_leagues(self) -> list[LeagueConfig]:
        """Return leagues that have a football_data_code configured."""
        return [lg for lg in self.leagues if lg.football_data_code is not None]

    @property
    def understat_leagues(self) -> list[LeagueConfig]:
        """Return leagues that have an understat_name configured."""
        return [lg for lg in self.leagues if lg.understat_name is not None]

    @property
    def football_data_season_codes(self) -> list[str]:
        """Return Football-Data season codes like '1617', '1718', etc."""
        codes: list[str] = []
        for year in self.seasons:
            start = year % 100
            end = (year + 1) % 100
            codes.append(f"{start:02d}{end:02d}")
        return codes


# ---------------------------------------------------------------------------
# Default ingest configuration (Big 5 + 5 extended leagues, 10 seasons)
# ---------------------------------------------------------------------------

DEFAULT_INGEST_CONFIG = IngestConfig(
    leagues=[
        # --- Big 5 ---
        LeagueConfig(
            name="Premier League",
            fbref_id="ENG-Premier League",
            fbref_comp_id=9,
            fbref_slug="Premier-League",
            football_data_code="E0",
            understat_name="EPL",
            sofascore_id=17,
            statsbomb_comp_id=2,
        ),
        LeagueConfig(
            name="Championship",
            fbref_id="ENG-Championship",
            fbref_comp_id=10,
            fbref_slug="Championship",
            football_data_code="E1",
            sofascore_id=18,
        ),
        LeagueConfig(
            name="La Liga",
            fbref_id="ESP-La Liga",
            fbref_comp_id=12,
            fbref_slug="La-Liga",
            football_data_code="SP1",
            understat_name="La_Liga",
            sofascore_id=8,
            statsbomb_comp_id=11,
        ),
        LeagueConfig(
            name="Segunda División",
            football_data_code="SP2",
        ),
        LeagueConfig(
            name="Bundesliga",
            fbref_id="GER-Bundesliga",
            fbref_comp_id=20,
            fbref_slug="Bundesliga",
            football_data_code="D1",
            understat_name="Bundesliga",
            sofascore_id=35,
            statsbomb_comp_id=9,
        ),
        LeagueConfig(
            name="2. Bundesliga",
            football_data_code="D2",
        ),
        LeagueConfig(
            name="Serie A",
            fbref_id="ITA-Serie A",
            fbref_comp_id=11,
            fbref_slug="Serie-A",
            football_data_code="I1",
            understat_name="Serie_A",
            sofascore_id=23,
            statsbomb_comp_id=12,
        ),
        LeagueConfig(
            name="Serie B",
            football_data_code="I2",
        ),
        LeagueConfig(
            name="Ligue 1",
            fbref_id="FRA-Ligue 1",
            fbref_comp_id=13,
            fbref_slug="Ligue-1",
            football_data_code="F1",
            understat_name="Ligue_1",
            sofascore_id=34,
            statsbomb_comp_id=7,
        ),
        LeagueConfig(
            name="Ligue 2",
            football_data_code="F2",
        ),
        # --- Extended 5 ---
        LeagueConfig(
            name="Primeira Liga",
            fbref_id="POR-Primeira Liga",
            fbref_comp_id=32,
            fbref_slug="Primeira-Liga",
            football_data_code="P1",
            sofascore_id=138,
        ),
        LeagueConfig(
            name="Eredivisie",
            fbref_id="NED-Eredivisie",
            fbref_comp_id=23,
            fbref_slug="Eredivisie",
            football_data_code="N1",
            sofascore_id=37,
        ),
        LeagueConfig(
            name="Süper Lig",
            fbref_id="TUR-Süper Lig",
            fbref_comp_id=26,
            fbref_slug="Super-Lig",
            football_data_code="T1",
            sofascore_id=94,
        ),
        LeagueConfig(
            name="Scottish Premiership",
            fbref_id="SCO-Scottish Premiership",
            fbref_comp_id=24,
            fbref_slug="Scottish-Premiership",
            football_data_code="SC0",
            sofascore_id=36,
        ),
        LeagueConfig(
            name="First Division A",
            fbref_id="BEL-First Division A",
            fbref_comp_id=22,
            fbref_slug="First-Division-A",
            football_data_code="B1",
            sofascore_id=103,
        ),
    ],
    season_start_year=2016,
    season_end_year=2026,
    sources_enabled={
        "fbref": True,
        "football_data": True,
        "understat": True,
        "statsbomb_open": True,
        "clubelo": True,
        "sofascore": True,
        "sofifa": True,
        "api_football": False,
    },
)


def load_ingest_config(config_dir: Path | None = None) -> IngestConfig:
    """Load IngestConfig from YAML/JSON, falling back to DEFAULT_INGEST_CONFIG.

    Looks for ``data/config/ingest_config.yaml`` or ``ingest_config.json``
    inside *config_dir*.  If *config_dir* is ``None``, resolves from the
    project root (``data/config/``).

    If a file is found, its values are merged on top of the default config
    (partial overrides are supported via Pydantic model construction).
    If no file is found, returns DEFAULT_INGEST_CONFIG unchanged.
    """
    if config_dir is None:
        project_root = Path(__file__).resolve().parents[2]
        config_dir = project_root / "data" / "config"

    yaml_path = config_dir / "ingest_config.yaml"
    json_path = config_dir / "ingest_config.json"

    raw_data: dict | None = None

    if yaml_path.exists():
        try:
            import yaml

            with open(yaml_path) as f:
                raw_data = yaml.safe_load(f)
            logger.info("Loaded ingest config from %s", yaml_path)
        except ImportError:
            logger.warning("PyYAML not installed; skipping %s", yaml_path)
        except Exception as exc:
            logger.warning("Failed to load %s: %s", yaml_path, exc)

    if raw_data is None and json_path.exists():
        try:
            with open(json_path) as f:
                raw_data = json.load(f)
            logger.info("Loaded ingest config from %s", json_path)
        except Exception as exc:
            logger.warning("Failed to load %s: %s", json_path, exc)

    if raw_data is None:
        return DEFAULT_INGEST_CONFIG

    # Merge: start from default dict, overlay user-provided keys
    default_dict = DEFAULT_INGEST_CONFIG.model_dump()
    merged = {**default_dict, **raw_data}

    # If user provided leagues, replace entirely (don't merge individual leagues)
    if "leagues" in raw_data:
        merged["leagues"] = raw_data["leagues"]

    return IngestConfig.model_validate(merged)
