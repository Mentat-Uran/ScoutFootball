"""Generate the project-level manifest for release gating.

Combines the architecture manifest, capability registry, and data
contract registry into a single ``project_manifest.json`` that is
used as a release gate: stale manifests or contract mismatches
block the build.

Usage::

    PYTHONPATH=src uv run python scripts/generate_manifest.py
    PYTHONPATH=src uv run python scripts/generate_manifest.py --check
    PYTHONPATH=src uv run python scripts/generate_manifest.py --output path/to/manifest.json
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "data" / "project_manifest.json"


def _build_manifest() -> dict:
    from scoutfootball import __version__
    from scoutfootball.architecture import (
        build_capability_registry,
        build_data_contract_registry,
        build_default_architecture,
    )

    arch = build_default_architecture()
    caps = build_capability_registry()
    contracts = build_data_contract_registry()

    return {
        "schema_version": "1.0.0",
        "generated_at": _dt.datetime.now(_dt.UTC).isoformat(),
        "package_version": __version__,
        "architecture": arch.model_dump(mode="json"),
        "capabilities": caps.model_dump(mode="json"),
        "data_contracts": contracts.model_dump(mode="json"),
    }


def _strip_timestamps(obj: object) -> object:
    if isinstance(obj, dict):
        return {
            k: _strip_timestamps(v)
            for k, v in obj.items()
            if k not in ("generated_at", "content_sha256")
        }
    if isinstance(obj, list):
        return [_strip_timestamps(item) for item in obj]
    if isinstance(obj, tuple):
        return tuple(_strip_timestamps(item) for item in obj)
    return obj


def _manifest_hash(manifest: dict) -> str:
    stable = _strip_timestamps(manifest)
    canonical = json.dumps(stable, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def generate_manifest(output_path: Path) -> dict:
    manifest = _build_manifest()
    manifest["content_sha256"] = _manifest_hash(manifest)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifest


def check_manifest(output_path: Path) -> int:
    if not output_path.exists():
        print(f"FAIL: manifest not found at {output_path}")
        return 1

    existing = json.loads(output_path.read_text(encoding="utf-8"))
    existing_hash = _manifest_hash(existing)
    fresh = _build_manifest()
    fresh_hash = _manifest_hash(fresh)

    if existing_hash == fresh_hash:
        print(f"OK: manifest is up to date ({output_path.name})")
        return 0

    print("FAIL: manifest is stale. Run generate_manifest.py to regenerate.")
    print(f"  existing hash: {existing_hash[:16]}...")
    print(f"  expected hash: {fresh_hash[:16]}...")
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate or verify the project manifest for release gating"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_OUTPUT),
        help=f"Output path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if manifest is up to date instead of writing",
    )
    args = parser.parse_args()

    output_path = Path(args.output).resolve()

    if args.check:
        sys.exit(check_manifest(output_path))
    else:
        manifest = generate_manifest(output_path)
        count = len(manifest["capabilities"]["capabilities"])
        contract_count = len(manifest["data_contracts"]["contracts"])
        print(
            f"Generated manifest: {output_path} "
            f"({count} capabilities, {contract_count} data contracts)"
        )


if __name__ == "__main__":
    main()
