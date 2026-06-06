#!/usr/bin/env python3
"""Fetch transfermarkt-datasets: download DuckDB and export priority tables to Parquet."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scoutfootball.adapters.transfermarkt_datasets import (
    PRIORITY_TABLES,
    download_duckdb,
    export_priority_tables,
    export_table,
)
from scoutfootball.config import PlatformSettings


def main():
    settings = PlatformSettings.from_root()

    print("=" * 60)
    print("Transfermarkt-Datasets Importer")
    print("=" * 60)

    # Step 1: Download DuckDB
    print("\n[1/3] Downloading DuckDB file...")
    try:
        duckdb_path = download_duckdb(settings=settings)
        size_mb = duckdb_path.stat().st_size / (1024 * 1024)
        print(f"  DuckDB ready: {duckdb_path} ({size_mb:.1f} MB)")
    except RuntimeError as e:
        print(f"  FAILED: {e}")
        return False

    # Step 2: Export priority tables
    print("\n[2/3] Exporting priority tables...")
    results = export_priority_tables(settings=settings)

    for table_name, status in results.items():
        icon = "OK" if status.startswith("ok") else "ERR"
        print(f"  [{icon}] {table_name}: {status}")

    ok_count = sum(1 for s in results.values() if s.startswith("ok"))
    if ok_count == 0:
        print("\nAll exports failed, aborting.")
        return False

    # Step 3: Summary stats
    print("\n[3/3] Summary statistics...")
    for table_name in PRIORITY_TABLES:
        if not results.get(table_name, "").startswith("ok"):
            continue
        try:
            result = export_table(table_name, settings=settings)
            df = result.dataframe
            print(f"\n  --- {table_name} ---")
            print(f"  Rows: {len(df):,}")
            print(f"  Columns ({len(df.columns)}): {', '.join(df.columns[:12])}")
            if len(df.columns) > 12:
                print(f"    ... and {len(df.columns) - 12} more")

            # Date range for tables with date columns
            for col in ("date", "transfer_date", "last_season"):
                if col in df.columns:
                    try:
                        dates = df[col].dropna()
                        if len(dates) > 0:
                            print(f"  {col} range: {dates.min()} ~ {dates.max()}")
                    except Exception:
                        pass

            # Market value stats for player_valuations
            if table_name == "player_valuations":
                mv = df["market_value_in_eur"].dropna()
                print(
                    f"  market_value_in_eur: min={mv.min():,.0f}, "
                    f"median={mv.median():,.0f}, max={mv.max():,.0f}"
                )
                print(f"  Unique players: {df['player_id'].nunique():,}")
                print(f"  Unique clubs: {df['player_club_id'].nunique():,}")
                print("  >> This replaces synthetic market values in the pipeline")

            # Lineup coverage
            if table_name == "game_lineups":
                print(f"  Unique games: {df['game_id'].nunique():,}")
                print(f"  Unique players: {df['player_id'].nunique():,}")
                if "type" in df.columns:
                    print(f"  Types: {df['type'].value_counts().to_dict()}")

            # Event coverage
            if table_name == "game_events":
                print(f"  Unique games: {df['game_id'].nunique():,}")
                if "type" in df.columns:
                    print(f"  Event types: {df['type'].value_counts().to_dict()}")

            # Transfer coverage
            if table_name == "transfers":
                print(f"  Unique players: {df['player_id'].nunique():,}")
                if "transfer_fee" in df.columns:
                    fees = df["transfer_fee"].dropna()
                    print(f"  transfer_fee: {len(fees):,} records, median={fees.median():,.0f}")

            # Player position distribution
            if table_name == "players":
                if "position" in df.columns:
                    print(f"  Positions: {df['position'].value_counts().to_dict()}")
                if "sub_position" in df.columns:
                    sub_pos = df["sub_position"].value_counts().head(10).to_dict()
                    print(f"  Sub-positions (top 10): {sub_pos}")

        except Exception as e:
            print(f"  Error summarizing {table_name}: {e}")

    print("\n" + "=" * 60)
    print(f"Done: {ok_count}/{len(PRIORITY_TABLES)} tables exported")
    print(f"Output: {settings.raw_root / 'transfermarkt_datasets'}")
    print("=" * 60)
    return ok_count > 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
