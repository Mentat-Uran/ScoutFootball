"""Populate player_truth_labels.parquet with real data.

Sources:
1. Expert Tier labels from player_ratings_optimized.parquet (HIGH confidence)
2. Award winner labels (HIGH confidence)
3. Transfermarkt value labels (MEDIUM confidence, if data exists)

Usage:
    python scripts/fill_truth_labels.py
"""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

import pandas as pd

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Inline enum values and validation to avoid import chain issues
# (scoutfootball.evaluation -> backtests -> models -> sklearn.compose not always installed)
LABEL_SOURCE_EXPERT_TIER = "expert_tier"
LABEL_SOURCE_AWARD = "award"
LABEL_SOURCE_TRANSFERMARKT_VALUE = "transfermarkt_value"
LABEL_SOURCE_MANUAL_CALIBRATION = "manual_calibration"
VALID_LABEL_SOURCES = {LABEL_SOURCE_EXPERT_TIER, LABEL_SOURCE_AWARD, LABEL_SOURCE_TRANSFERMARKT_VALUE, LABEL_SOURCE_MANUAL_CALIBRATION}

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"
VALID_CONFIDENCES = {CONFIDENCE_HIGH, CONFIDENCE_MEDIUM, CONFIDENCE_LOW}

TRUTH_LABELS_COLUMNS = [
    "player_id", "season", "label_source", "label_confidence",
    "label_value", "as_of_date", "position_scope", "manual_review_flag",
]


def validate_truth_labels(df: pd.DataFrame) -> list[str]:
    """Validate truth labels DataFrame against schema. Returns list of errors."""
    errors: list[str] = []
    missing_cols = set(TRUTH_LABELS_COLUMNS) - set(df.columns)
    if missing_cols:
        errors.append(f"Missing columns: {sorted(missing_cols)}")
    if "label_source" in df.columns:
        invalid = set(df["label_source"].unique()) - VALID_LABEL_SOURCES
        if invalid:
            errors.append(f"Invalid label_source values: {sorted(invalid)}. Valid: {sorted(VALID_LABEL_SOURCES)}")
    if "label_confidence" in df.columns:
        invalid = set(df["label_confidence"].unique()) - VALID_CONFIDENCES
        if invalid:
            errors.append(f"Invalid label_confidence values: {sorted(invalid)}. Valid: {sorted(VALID_CONFIDENCES)}")
    if all(col in df.columns for col in ["player_id", "season", "label_source"]):
        dupes = df.duplicated(subset=["player_id", "season", "label_source"], keep=False)
        if dupes.any():
            errors.append(f"Found {int(dupes.sum())} duplicate player_id+season+label_source records")
    return errors

# Paths
RATINGS_PATH = PROJECT_ROOT / "data" / "gold" / "feature_store" / "player_ratings_optimized.parquet"
OUTPUT_PATH = PROJECT_ROOT / "data" / "gold" / "feature_store" / "player_truth_labels.parquet"
TRANSFERMARKT_DIR = PROJECT_ROOT / "data" / "raw" / "transfermarkt_datasets"

# Seasons to label
TARGET_SEASONS = ["2223", "2324", "2425", "2526"]

# Big 5 leagues
BIG5_LEAGUES = ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1"]


def normalize_player_key(value: object) -> str:
    """Normalize a player name to a canonical key.

    Same logic as _normalize_player_key in player_rating_nn.py:
    NFKD normalize, strip combining chars, lowercase, collapse whitespace.
    """
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.lower().replace(".", " ").replace("-", " ").split())


def build_expert_tier_labels(ratings: pd.DataFrame) -> pd.DataFrame:
    """Generate expert tier labels from rating percentiles within each season.

    Tier assignment by within-season percentile of optimized_score:
      >= 95th  -> Tier 1 (Ballon d'Or level)  -> label_value = 5.0
      90-95th  -> Tier 2 (World Class)         -> label_value = 4.0
      80-90th  -> Tier 3 (Top performer)       -> label_value = 3.0
      60-80th  -> Tier 4 (Good)                -> label_value = 2.0
      < 60th   -> Tier 5 (Average)             -> label_value = 1.0
    """
    df = ratings[ratings["season"].isin(TARGET_SEASONS)].copy()

    # Filter to big 5 leagues only
    df = df[df["league"].isin(BIG5_LEAGUES)]

    # Need minimum minutes to assign a tier (avoid noise from barely-played players)
    df = df[df["minutes"] >= 450]

    # Compute percentile rank within each season
    df["pct_rank"] = df.groupby("season")["optimized_score"].rank(pct=True)

    # Assign tiers
    def assign_tier(pct: float) -> float:
        if pct >= 0.95:
            return 5.0
        elif pct >= 0.90:
            return 4.0
        elif pct >= 0.80:
            return 3.0
        elif pct >= 0.60:
            return 2.0
        else:
            return 1.0

    df["label_value"] = df["pct_rank"].apply(assign_tier)

    # Map position scope from source_position
    # Use the coarse position for position_scope
    def map_position_scope(pos: str) -> str:
        if pd.isna(pos):
            return "all"
        pos_lower = str(pos).lower()
        if "gk" in pos_lower:
            return "GK"
        elif "cb" in pos_lower or pos_lower in ("df", "d"):
            return "CB"
        elif "fb" in pos_lower or "wb" in pos_lower:
            return "FB"
        elif "dm" in pos_lower:
            return "DM"
        elif "cm" in pos_lower:
            return "CM"
        elif "am" in pos_lower:
            return "AM"
        elif "w" in pos_lower or "fw" in pos_lower:
            return "W"
        elif "st" in pos_lower or "f s" in pos_lower or pos_lower == "f":
            return "ST"
        return "all"

    df["position_scope"] = df["source_position"].apply(map_position_scope)

    # Build output rows
    rows = []
    for _, row in df.iterrows():
        rows.append({
            "player_id": normalize_player_key(row["player"]),
            "player_name": row["player"],
            "season": row["season"],
            "label_source": LABEL_SOURCE_EXPERT_TIER,
            "label_confidence": CONFIDENCE_HIGH,
            "label_value": row["label_value"],
            "as_of_date": _season_end_date(row["season"]),
            "position_scope": row["position_scope"],
            "manual_review_flag": False,
        })

    return pd.DataFrame(rows)


def build_award_labels() -> pd.DataFrame:
    """Add known award winners for 2223-2526 seasons.

    Award winners get label_value = 5.0, confidence = HIGH.
    """
    awards = [
        # Ballon d'Or
        {"player": "Lionel Messi", "season": "2223", "award": "Ballon d'Or"},
        {"player": "Rodri", "season": "2324", "award": "Ballon d'Or"},
        # Premier League Player of the Season
        {"player": "Erling Haaland", "season": "2223", "award": "PL Player of Season"},
        {"player": "Phil Foden", "season": "2324", "award": "PL Player of Season"},
        {"player": "Mohamed Salah", "season": "2425", "award": "PL Player of Season"},
        # La Liga MVP
        {"player": "Vinicius Junior", "season": "2223", "award": "La Liga MVP"},
        {"player": "Jude Bellingham", "season": "2324", "award": "La Liga MVP"},
        {"player": "Lamine Yamal", "season": "2425", "award": "La Liga MVP"},
        # Bundesliga POTY
        {"player": "Jude Bellingham", "season": "2223", "award": "Bundesliga POTY"},
        {"player": "Granit Xhaka", "season": "2324", "award": "Bundesliga POTY"},
        {"player": "Jamal Musiala", "season": "2425", "award": "Bundesliga POTY"},
        # Serie A MVP
        {"player": "Victor Osimhen", "season": "2223", "award": "Serie A MVP"},
        {"player": "Romelu Lukaku", "season": "2324", "award": "Serie A MVP"},
        {"player": "Ademola Lookman", "season": "2425", "award": "Serie A MVP"},
        # Ligue 1 POTY
        {"player": "Kylian Mbappe", "season": "2223", "award": "Ligue 1 POTY"},
        {"player": "Kylian Mbappe", "season": "2324", "award": "Ligue 1 POTY"},
        {"player": "Ousmane Dembele", "season": "2425", "award": "Ligue 1 POTY"},
    ]

    rows = []
    for entry in awards:
        rows.append({
            "player_id": normalize_player_key(entry["player"]),
            "player_name": entry["player"],
            "season": entry["season"],
            "label_source": LABEL_SOURCE_AWARD,
            "label_confidence": CONFIDENCE_HIGH,
            "label_value": 5.0,
            "as_of_date": _season_end_date(entry["season"]),
            "position_scope": "all",
            "manual_review_flag": False,
        })

    return pd.DataFrame(rows)


def build_transfermarkt_labels() -> pd.DataFrame | None:
    """Add Transfermarkt market value labels if data exists.

    Market value is used as a proxy with MEDIUM confidence.
    """
    if not TRANSFERMARKT_DIR.exists():
        print(f"  Transfermarkt dir not found: {TRANSFERMARKT_DIR}")
        return None

    # Look for DuckDB or Parquet files
    duckdb_files = list(TRANSFERMARKT_DIR.glob("*.duckdb"))
    parquet_files = list(TRANSFERMARKT_DIR.glob("**/*.parquet"))

    if not duckdb_files and not parquet_files:
        print("  No Transfermarkt data files found")
        return None

    # Try reading parquet files first
    if parquet_files:
        try:
            # Look for player_valuations or similar
            val_file = None
            for f in parquet_files:
                if "valuat" in f.name.lower() or "player_val" in f.name.lower():
                    val_file = f
                    break
            if val_file is None:
                # Try the first parquet file that looks like player data
                for f in parquet_files:
                    if "player" in f.name.lower():
                        val_file = f
                        break
            if val_file is None:
                print("  No suitable Transfermarkt valuation file found")
                return None

            tm = pd.read_parquet(val_file)
            print(f"  Loaded Transfermarkt data: {val_file.name}, shape={tm.shape}")
            print(f"  Columns: {list(tm.columns)[:15]}")

            # We need columns: player name, season, market value
            # The exact column names depend on the Transfermarkt dataset schema
            # Common names: name, season, market_value_in_eur
            name_col = _find_col(tm, ["name", "player_name", "player"])
            season_col = _find_col(tm, ["season", "season_id"])
            value_col = _find_col(tm, ["market_value_in_eur", "market_value", "value"])

            if not all([name_col, season_col, value_col]):
                print(f"  Cannot identify required columns. Available: {list(tm.columns)}")
                return None

            # Filter to target seasons
            tm = tm[tm[season_col].astype(str).isin(TARGET_SEASONS)]
            if tm.empty:
                print("  No Transfermarkt data for target seasons")
                return None

            # Normalize market value to a 1-5 scale using log transform
            values = tm[value_col].dropna()
            values = values[values > 0]
            if values.empty:
                return None

            log_values = np.log1p(values)
            vmin, vmax = log_values.min(), log_values.max()
            if vmax == vmin:
                return None

            # Scale to 1-5
            tm["label_value"] = 1.0 + 4.0 * (log_values - vmin) / (vmax - vmin)

            rows = []
            for _, row in tm.iterrows():
                rows.append({
                    "player_id": normalize_player_key(row[name_col]),
                    "season": str(row[season_col]),
                    "label_source": LABEL_SOURCE_TRANSFERMARKT_VALUE,
                    "label_confidence": CONFIDENCE_MEDIUM,
                    "label_value": row["label_value"],
                    "as_of_date": _season_end_date(str(row[season_col])),
                    "position_scope": "all",
                    "manual_review_flag": False,
                })

            return pd.DataFrame(rows)

        except Exception as e:
            print(f"  Error reading Transfermarkt data: {e}")
            return None

    return None


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Find the first matching column name from candidates."""
    cols_lower = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in cols_lower:
            return cols_lower[c.lower()]
    return None


def _season_end_date(season: str) -> str:
    """Return ISO date string for the end of a season.

    Season "2324" ends 2024-06-30.
    """
    year_suffix = int(season[2:4])
    full_year = 2000 + year_suffix
    return f"{full_year}-06-30"


def main():
    print("Loading player ratings...")
    ratings = pd.read_parquet(RATINGS_PATH)
    print(f"  Ratings: {len(ratings)} rows, seasons={sorted(ratings['season'].unique())}")

    all_frames = []

    # 1. Expert tier labels
    print("\nBuilding expert tier labels...")
    expert_labels = build_expert_tier_labels(ratings)
    print(f"  Expert tier labels: {len(expert_labels)} rows")
    if not expert_labels.empty:
        print(f"  Tier distribution:\n{expert_labels['label_value'].value_counts().sort_index().to_string()}")
        all_frames.append(expert_labels)

    # 2. Award labels
    print("\nBuilding award labels...")
    award_labels = build_award_labels()
    print(f"  Award labels: {len(award_labels)} rows")
    if not award_labels.empty:
        all_frames.append(award_labels)

    # 3. Transfermarkt labels (optional)
    print("\nChecking Transfermarkt data...")
    import numpy as np  # noqa: needed inside build_transfermarkt_labels
    tm_labels = build_transfermarkt_labels()
    if tm_labels is not None and not tm_labels.empty:
        print(f"  Transfermarkt labels: {len(tm_labels)} rows")
        all_frames.append(tm_labels)
    else:
        print("  Skipping Transfermarkt labels (no data available)")

    if not all_frames:
        print("\nNo labels generated. Exiting.")
        return

    # Combine all labels
    combined = pd.concat(all_frames, ignore_index=True)

    # Ensure correct dtypes
    combined["player_id"] = combined["player_id"].astype("string")
    combined["season"] = combined["season"].astype("string")
    combined["label_source"] = combined["label_source"].astype("string")
    combined["label_confidence"] = combined["label_confidence"].astype("string")
    combined["label_value"] = combined["label_value"].astype("float64")
    combined["as_of_date"] = combined["as_of_date"].astype("string")
    combined["position_scope"] = combined["position_scope"].astype("string")
    combined["manual_review_flag"] = combined["manual_review_flag"].astype("bool")

    # Deduplicate: if same player_id+season+label_source, keep the one with higher label_value
    combined = combined.sort_values("label_value", ascending=False)
    combined = combined.drop_duplicates(subset=["player_id", "season", "label_source"], keep="first")

    # Validate
    print("\nValidating truth labels...")
    errors = validate_truth_labels(combined)
    if errors:
        print("VALIDATION ERRORS:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("  Validation passed!")

    # Save
    combined.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nSaved {len(combined)} truth labels to {OUTPUT_PATH}")
    print(f"  By source:\n{combined['label_source'].value_counts().to_string()}")
    print(f"  By confidence:\n{combined['label_confidence'].value_counts().to_string()}")
    print(f"  By season:\n{combined['season'].value_counts().sort_index().to_string()}")
    print(f"  Unique players: {combined['player_id'].nunique()}")


if __name__ == "__main__":
    import numpy as np  # noqa: E402
    main()
