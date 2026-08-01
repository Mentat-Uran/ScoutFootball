#!/usr/bin/env python3
"""Download the `davidcariboo/player-scores` Kaggle dataset (Football Data from
Transfermarkt) into the local ScoutFootball raw data directory.

This is an alternative acquisition path for the `transfermarkt_datasets`
source. The same upstream project (`dcaribou/transfermarkt-datasets`) is
also distributed as a pre-built DuckDB file (~500MB); this script instead
pulls the per-table CSVs published on Kaggle, which the Kaggle CLI fetches
through a documented, authenticated channel.

Layout produced on disk (all paths are Git-ignored via
``data/raw/transfermarkt_datasets/``):

    data/raw/transfermarkt_datasets/
        csv/                # raw Kaggle CSVs (unzipped)
            players.csv
            clubs.csv
            games.csv
            appearances.csv
            player_valuations.csv
            ...
        transfermarkt_kaggle_manifest.json   # source provenance record

Pre-requisites:
    1. The Kaggle CLI must be available. The script invokes it via
       ``uvx kaggle`` so no install into the project venv is required.
       If you prefer a permanent install: ``uv tool install kaggle``.
    2. You must be authenticated. Run once (opens a browser):
           uvx kaggle auth login
       This writes ``~/.kaggle/kaggle.json``. The script will not perform
       the OAuth login for you.

Usage (from the scoutlab project root):

    uv run python scripts/download_transfermarkt_kaggle.py
    uv run python scripts/download_transfermarkt_kaggle.py --force-refresh
    uv run python scripts/download_transfermarkt_kaggle.py --no-unzip

Notes:
    - This dataset is a third-party repackaging of Transfermarkt content.
      It is permitted for personal local use; redistribution or commercial
      use requires separate permission from Transfermarkt. See
      ``docs/DATA_RIGHTS.md`` §2.1.
    - The script is idempotent: it skips files that already exist unless
      ``--force-refresh`` is passed.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

KAGGLE_DATASET_SLUG = "davidcariboo/player-scores"
KAGGLE_DATASET_ID = "davidcariboo/player-scores"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = PROJECT_ROOT / "data" / "raw" / "transfermarkt_datasets" / "csv"
MANIFEST_PATH = (
    PROJECT_ROOT / "data" / "raw" / "transfermarkt_datasets" / "transfermarkt_kaggle_manifest.json"
)

# Tables expected by src/scoutfootball/adapters/transfermarkt_datasets.py.
# These are the canonical CSV filenames emitted by the Kaggle dataset.
EXPECTED_TABLES = (
    "clubs",
    "competitions",
    "appearances",
    "games",
    "players",
    "player_valuations",
    "transfers",
    "game_events",
    "game_lineups",
    "club_games",
    "countries",
    "national_teams",
)


def _resolve_kaggle_command() -> list[str]:
    """Return the kaggle CLI invocation, preferring ``uvx kaggle`` so the
    project venv stays clean. Falls back to a system ``kaggle`` if present.
    """
    system_kaggle = shutil.which("kaggle")
    if system_kaggle:
        return [system_kaggle]
    # uvx runs the package in an isolated environment; ~/.kaggle/kaggle.json
    # is still read from the user home, so auth persists across invocations.
    uvx = shutil.which("uvx") or shutil.which("uv")
    if uvx:
        return [uvx, "x", "kaggle"] if uvx.endswith("uv") else [uvx, "kaggle"]
    raise RuntimeError(
        "kaggle CLI not found. Install with `uv tool install kaggle` or "
        "`pip install kaggle`, or ensure `uvx` is on PATH."
    )


def _check_auth() -> bool:
    """Return True if Kaggle credentials look configured."""
    cred_path = Path.home() / ".kaggle" / "kaggle.json"
    return cred_path.exists()


def _looks_like_auth_error(stderr: str) -> bool:
    """Heuristic: did the Kaggle CLI fail because of missing/invalid creds?"""
    lower = stderr.lower()
    return "401" in stderr or "unauthorized" in lower or "credentials" in lower


def _prompt_auth_instructions() -> None:
    print(
        "Kaggle credentials not found at ~/.kaggle/kaggle.json.\n"
        "Run the following once (opens a browser to log in to Kaggle):\n"
        "    uvx kaggle auth login\n"
        "Then re-run this script.\n"
        "Alternatively, place a kaggle.json file at ~/.kaggle/kaggle.json "
        "(see https://github.com/Kaggle/kaggle-cli#api-credentials).",
        file=sys.stderr,
    )


def _invoke_kaggle(args: list[str]) -> subprocess.CompletedProcess[str]:
    cmd = _resolve_kaggle_command() + args
    print(f"  $ {' '.join(cmd)}", file=sys.stderr)
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def _download_dataset(out_dir: Path, *, unzip: bool, force_refresh: bool) -> bool:
    """Download the Kaggle dataset ZIP into ``out_dir``. Returns True on success."""
    out_dir.mkdir(parents=True, exist_ok=True)
    args = ["datasets", "download", "-d", KAGGLE_DATASET_ID, "-p", str(out_dir)]
    if unzip:
        args.append("--unzip")
    if force_refresh:
        args.append("--force")

    print(f"Downloading Kaggle dataset {KAGGLE_DATASET_ID} -> {out_dir}")
    result = _invoke_kaggle(args)
    if result.returncode != 0:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        if _looks_like_auth_error(result.stderr):
            _prompt_auth_instructions()
        return False
    if result.stdout:
        sys.stderr.write(result.stdout)
    return True


def _list_downloaded_csvs(out_dir: Path) -> list[str]:
    """Return sorted list of CSV filenames present in ``out_dir``."""
    if not out_dir.exists():
        return []
    return sorted(p.name for p in out_dir.glob("*.csv"))


def _write_manifest(
    out_dir: Path,
    manifest_path: Path,
    *,
    csv_files: list[str],
    force_refresh: bool,
) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    present_tables = sorted(set(EXPECTED_TABLES) & {Path(f).stem for f in csv_files})
    missing_tables = sorted(set(EXPECTED_TABLES) - {Path(f).stem for f in csv_files})
    manifest = {
        "source_name": "transfermarkt_datasets",
        "acquisition_method": "kaggle_cli",
        "kaggle_dataset_id": KAGGLE_DATASET_ID,
        "upstream_project": "dcaribou/transfermarkt-datasets",
        "upstream_origin": "Transfermarkt (transfermarkt.com)",
        "license_boundary": (
            "Personal local use only. Transfermarkt ToS prohibit scraping, "
            "redistribution, and commercial reuse without written permission. "
            "See docs/DATA_RIGHTS.md §2.1."
        ),
        "downloaded_at_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "force_refresh": force_refresh,
        "csv_directory": str(out_dir.relative_to(PROJECT_ROOT)),
        "expected_tables": list(EXPECTED_TABLES),
        "present_tables": present_tables,
        "missing_tables": missing_tables,
        "csv_files": csv_files,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote manifest: {manifest_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"Destination directory (default: {DEFAULT_OUT_DIR}).",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Re-download even if files already exist.",
    )
    parser.add_argument(
        "--no-unzip",
        action="store_true",
        help="Leave the dataset as a ZIP instead of extracting CSVs.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only report auth status and exit; do not download.",
    )
    args = parser.parse_args(argv)

    if args.check_only:
        if _check_auth():
            print("OK: Kaggle credentials present at ~/.kaggle/kaggle.json")
            return 0
        _prompt_auth_instructions()
        return 2

    if not _check_auth():
        _prompt_auth_instructions()
        return 2

    out_dir: Path = args.out_dir
    existing = _list_downloaded_csvs(out_dir)
    if existing and not args.force_refresh:
        print(f"Found {len(existing)} existing CSVs in {out_dir}.")
        print("Use --force-refresh to re-download. Writing manifest only.")
        _write_manifest(
            out_dir.resolve(),
            MANIFEST_PATH.resolve(),
            csv_files=existing,
            force_refresh=False,
        )
        return 0

    start = time.monotonic()
    success = _download_dataset(out_dir, unzip=not args.no_unzip, force_refresh=args.force_refresh)
    elapsed = time.monotonic() - start
    if not success:
        print(f"Download failed after {elapsed:.1f}s.", file=sys.stderr)
        return 1
    print(f"Download finished in {elapsed:.1f}s.")

    csv_files = _list_downloaded_csvs(out_dir)
    print(f"Present CSV files ({len(csv_files)}):")
    for name in csv_files:
        size = (out_dir / name).stat().st_size
        print(f"  {name}  ({size / 1024:.1f} KB)")

    _write_manifest(
        out_dir.resolve(),
        MANIFEST_PATH.resolve(),
        csv_files=csv_files,
        force_refresh=args.force_refresh,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
