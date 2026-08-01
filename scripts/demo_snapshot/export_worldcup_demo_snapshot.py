"""Export a reproducible World Cup demo snapshot with Core DataContracts.

This script produces a self-auditing offline snapshot of the World Cup
pack.  Every artifact in the snapshot carries its Core
:class:`~scoutfootball.schemas.storage.DataContract` so a reviewer can
trace each fact back to its source license, snapshot info, lineage and
coverage without running the API server.

The snapshot is reproducible: ``--check`` mode strips volatile timestamps
(``generated_at``, ``as_of`` for tournament state, ``updated_at``) and
compares SHA-256 hashes against a committed ``manifest.json``, so any
drift in the underlying data or contract wiring is detected.

Usage::

    PYTHONPATH=src uv run python scripts/demo_snapshot/export_worldcup_demo_snapshot.py
    PYTHONPATH=src uv run python scripts/demo_snapshot/export_worldcup_demo_snapshot.py --check
    PYTHONPATH=src uv run python scripts/demo_snapshot/export_worldcup_demo_snapshot.py \\
        --output path/to/snapshot_dir

Output layout::

    <output_dir>/
      manifest.json              # checksums + metadata
      contracts.json             # full Core DataContract registry
      schedule.json              # 72 group-stage fixtures
      teams.json                 # 48 teams with strengths
      groups.json                # 12 groups with standings skeleton
      predictions.json           # Bradley-Terry model probabilities
      tournament_summary.json    # maintainer-recorded results state
      README.md                  # human-readable snapshot description
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "data" / "reports" / "worldcup" / "demo_snapshot"

# Fields that carry wall-clock timestamps and would break reproducibility
# if included in the checksum.  These are stripped from the ``--check``
# comparison hash but kept in the exported files for human inspection.
#
# Note: ``as_of`` is stripped globally because tournament_state uses
# ``now()`` for it; static ``as_of`` dates in other contracts are still
# visible in the exported JSON for human audit, just not in the checksum.
_VOLATILE_KEYS: frozenset[str] = frozenset({
    "generated_at",
    "updated_at",
    "created_at",
    "recorded_at",  # lineage entries use now()
    "as_of",  # tournament_state snapshot uses now()
})


def _strip_volatile(obj: Any) -> Any:
    """Recursively remove volatile timestamp keys for checksum comparison."""
    if isinstance(obj, dict):
        return {
            k: _strip_volatile(v)
            for k, v in obj.items()
            if k not in _VOLATILE_KEYS
        }
    if isinstance(obj, list):
        return [_strip_volatile(item) for item in obj]
    if isinstance(obj, tuple):
        return [_strip_volatile(item) for item in obj]
    return obj


def _sha256(payload: Any) -> str:
    """Compute a stable SHA-256 over JSON-serialisable payload."""
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _collect_artifacts() -> dict[str, dict]:
    """Call the World Cup API service layer and return named artifacts.

    Each artifact includes its ``contracts`` and ``fact_types`` fields
    so the snapshot is self-auditing without a separate registry lookup.
    """
    from scoutfootball.api import (
        get_wc_contracts,
        get_wc_groups,
        get_wc_predictions,
        get_wc_schedule,
        get_wc_teams,
        get_wc_tournament_summary,
    )

    return {
        "contracts": get_wc_contracts(),
        "schedule": get_wc_schedule(),
        "teams": get_wc_teams(),
        "groups": get_wc_groups(),
        "predictions": get_wc_predictions(),
        "tournament_summary": get_wc_tournament_summary(),
    }


def _build_manifest(
    output_dir: Path,
    artifacts: dict[str, dict],
) -> dict:
    """Build the snapshot manifest with per-file checksums."""
    from scoutfootball import __version__

    file_hashes: list[dict[str, str]] = []
    for name in sorted(artifacts):
        # Reproducible hash: strip volatile timestamps before hashing.
        stable_payload = _strip_volatile(artifacts[name])
        file_hashes.append({
            "file": f"{name}.json",
            "sha256": _sha256(stable_payload),
            "volatile_keys_stripped": sorted(_VOLATILE_KEYS),
        })

    # Also hash the full registry count so a missing/extra contract is
    # caught even if the per-file hash somehow matches.
    registry = artifacts["contracts"]
    contract_ids = [c["artifact_id"] for c in registry["contracts"]]

    return {
        "schema": "scoutfootball.world-cup-demo-snapshot-manifest",
        "schema_version": "1.0.0",
        "generated_at": _dt.datetime.now(_dt.UTC).isoformat(),
        "package_version": __version__,
        "output_dir": str(output_dir),
        "file_count": len(file_hashes),
        "files": file_hashes,
        "contract_registry": {
            "schema": registry["schema"],
            "version": registry["version"],
            "count": registry["count"],
            "artifact_ids": contract_ids,
        },
        "reproducibility_note": (
            "Per-file sha256 is computed after stripping volatile timestamp "
            "keys (see volatile_keys_stripped).  Re-run with --check to "
            "verify that the snapshot is reproducible."
        ),
    }


def _write_readme(output_dir: Path, artifacts: dict[str, dict]) -> None:
    """Write a human-readable description of the snapshot."""
    registry = artifacts["contracts"]
    # fact_types list aligns positionally with contracts list in the registry.
    contract_rows = zip(
        registry["contracts"], registry["fact_types"], strict=True
    )
    lines = [
        "# World Cup Demo Snapshot",
        "",
        "Self-auditing offline snapshot of the ScoutFootball World Cup pack.",
        "Every artifact carries its Core `DataContract` so a reviewer can",
        "trace each fact back to its source license, snapshot info, lineage",
        "and coverage without running the API server.",
        "",
        "## Contents",
        "",
        f"- `contracts.json` — Core DataContract registry ({registry['count']} contracts)",
        "- `schedule.json` — 72 group-stage fixtures",
        "- `teams.json` — 48 teams with strength ratings",
        "- `groups.json` — 12 groups with standings skeleton",
        "- `predictions.json` — Bradley-Terry model probabilities",
        "- `tournament_summary.json` — maintainer-recorded results state",
        "- `manifest.json` — per-file SHA-256 checksums (volatile keys stripped)",
        "",
        "## Contract Registry",
        "",
        "| Artifact ID | Status | Fact Type |",
        "| --- | --- | --- |",
    ]
    for contract, fact_type in contract_rows:
        artifact_id = contract["artifact_id"]
        status = contract["status"]
        lines.append(f"| `{artifact_id}` | {status} | {fact_type} |")

    lines.extend([
        "",
        "## Reproducibility",
        "",
        "Re-run the export and verify the snapshot is unchanged:",
        "",
        "```bash",
        "PYTHONPATH=src uv run python scripts/demo_snapshot/export_worldcup_demo_snapshot.py \\",
        "    --check",
        "```",
        "",
        "The `--check` mode strips volatile timestamp keys before comparing",
        "SHA-256 hashes, so only data or contract-wiring changes are flagged.",
        "",
        "## Data Sources",
        "",
        "See `contracts.json` for the full source license, snapshot info and",
        "lineage of each artifact.  Expected call-ups are MIT-licensed",
        "maintainer snapshots; ratings are derived from FBref (CC BY-NC-SA)",
        "and Understat (ToS); Opta priors are publicly cited pre-tournament",
        "probabilities.",
        "",
    ])
    (output_dir / "README.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def export_snapshot(output_dir: Path) -> dict:
    """Export the full demo snapshot and return the manifest."""
    artifacts = _collect_artifacts()

    for name, payload in artifacts.items():
        _write_json(output_dir / f"{name}.json", payload)

    manifest = _build_manifest(output_dir, artifacts)
    _write_json(output_dir / "manifest.json", manifest)
    _write_readme(output_dir, artifacts)

    return manifest


def check_snapshot(output_dir: Path) -> int:
    """Verify an existing snapshot matches the current state.

    Returns 0 if the snapshot is reproducible, 1 if drift is detected.
    """
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"ERROR: manifest not found at {manifest_path}", file=sys.stderr)
        return 1

    existing_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = _collect_artifacts()

    # Rebuild the manifest in-memory and compare stable hashes.
    new_manifest = _build_manifest(output_dir, artifacts)

    existing_files = {f["file"]: f["sha256"] for f in existing_manifest["files"]}
    new_files = {f["file"]: f["sha256"] for f in new_manifest["files"]}

    drift_detected = False
    all_files = sorted(set(existing_files) | set(new_files))
    for file_name in all_files:
        old_hash = existing_files.get(file_name)
        new_hash = new_files.get(file_name)
        if old_hash is None:
            print(f"  + {file_name}: new file (not in committed manifest)")
            drift_detected = True
        elif new_hash is None:
            print(f"  - {file_name}: missing from current export")
            drift_detected = True
        elif old_hash != new_hash:
            print(f"  ~ {file_name}: HASH CHANGED")
            print(f"      old: {old_hash}")
            print(f"      new: {new_hash}")
            drift_detected = True
        else:
            print(f"  = {file_name}: ok")

    # Also check the contract registry count and artifact IDs.
    old_ids = set(existing_manifest["contract_registry"]["artifact_ids"])
    new_ids = set(new_manifest["contract_registry"]["artifact_ids"])
    if old_ids != new_ids:
        print("  ~ contract registry artifact IDs changed:")
        print(f"      removed: {old_ids - new_ids}")
        print(f"      added:   {new_ids - old_ids}")
        drift_detected = True

    if drift_detected:
        print("\nDRIFT DETECTED: snapshot is not reproducible.", file=sys.stderr)
        return 1

    print(f"\nOK: {len(all_files)} files match committed manifest.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export a reproducible World Cup demo snapshot.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output directory (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify an existing snapshot matches current state (exit 0=ok, 1=drift).",
    )
    args = parser.parse_args()

    if args.check:
        return check_snapshot(args.output)

    print(f"Exporting World Cup demo snapshot to {args.output} ...")
    manifest = export_snapshot(args.output)
    print(f"  {manifest['file_count']} files written")
    print(f"  contract registry: {manifest['contract_registry']['count']} contracts")
    for file_entry in manifest["files"]:
        print(f"  {file_entry['file']}: {file_entry['sha256'][:16]}...")
    print(f"\nManifest: {args.output / 'manifest.json'}")
    print("Re-verify with: --check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
