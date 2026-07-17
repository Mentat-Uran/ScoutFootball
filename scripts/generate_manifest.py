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
DEFAULT_REFERENCE_OUTPUT = REPO_ROOT / "docs" / "REFERENCE_INDEX.md"


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


def _markdown_cell(value: object) -> str:
    """Render generated manifest values safely inside a Markdown table cell."""
    if value is None:
        return "—"
    if isinstance(value, (list, tuple)):
        value = ", ".join(str(item) for item in value) or "—"
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_reference_index(manifest: dict) -> str:
    """Build a concise human-readable index from the machine manifest.

    The index intentionally lists declared contracts and entry points instead
    of asserting that every local artifact is readable or every remote URL is
    available. Those claims remain the responsibility of the relevant
    preflight and workflow checks.
    """
    architecture = manifest["architecture"]
    capabilities = manifest["capabilities"]["capabilities"]
    contracts = manifest["data_contracts"]["contracts"]

    lines = [
        "# ScoutFootball 参考索引",
        "",
        "> 自动生成：请勿手工编辑。来源为 `data/project_manifest.json`；"
        "重新生成命令为 `PYTHONPATH=src uv run python scripts/generate_manifest.py`。",
        "",
        f"- manifest schema：`{manifest['schema_version']}`",
        f"- package version：`{manifest['package_version']}`",
        f"- manifest generated_at：`{manifest['generated_at']}`",
        f"- content SHA-256：`{manifest['content_sha256']}`",
        "",
        "本页用于定位本地入口和已登记契约；它不证明 Parquet 内容已解码、"
        "样例具有完整覆盖，或线上部署当前可达。请运行相应的 preflight、"
        "契约检查和本地工作流后再作此类陈述。",
        "",
        "## 支持的本地命令",
        "",
    ]
    lines.extend(f"- `{command}`" for command in architecture["supported_commands"])

    lines.extend([
        "",
        "## 能力登记",
        "",
        "| ID | 领域 | 状态 | API | CLI | 前端视图 |",
        "| --- | --- | --- | --- | --- | --- |",
    ])
    for capability in capabilities:
        lines.append(
            "| {id} | {domain} | {status} | {api} | {cli} | {views} |".format(
                id=_markdown_cell(capability["id"]),
                domain=_markdown_cell(capability["domain"]),
                status=_markdown_cell(capability["status"]),
                api=_markdown_cell(capability["api_paths"]),
                cli=_markdown_cell(capability["cli_commands"]),
                views=_markdown_cell(capability["frontend_views"]),
            )
        )

    lines.extend([
        "",
        "## 数据契约登记",
        "",
        "| Artifact | 层 | 状态 | recorded | 来源 / 许可 | 主键 |",
        "| --- | --- | --- | --- | --- | --- |",
    ])
    for contract in contracts:
        license_info = contract.get("license") or {}
        source_and_license = " / ".join(
            part
            for part in (
                license_info.get("source_name"),
                license_info.get("license_name"),
            )
            if part
        )
        lines.append(
            "| {artifact} | {layer} | {status} | {recorded} | {license} | {keys} |".format(
                artifact=_markdown_cell(contract["artifact_id"]),
                layer=_markdown_cell(contract["layer"]),
                status=_markdown_cell(contract["status"]),
                recorded=_markdown_cell(contract["recorded"]),
                license=_markdown_cell(source_and_license),
                keys=_markdown_cell(contract["primary_keys"]),
            )
        )

    return "\n".join(lines) + "\n"


def write_reference_index(manifest: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_reference_index(manifest), encoding="utf-8")


def check_reference_index(manifest: dict, output_path: Path) -> int:
    if not output_path.exists():
        print(f"FAIL: reference index not found at {output_path}")
        return 1
    if output_path.read_text(encoding="utf-8") != render_reference_index(manifest):
        print("FAIL: reference index is stale. Run generate_manifest.py to regenerate.")
        return 1
    print(f"OK: reference index is up to date ({output_path.name})")
    return 0


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
    parser.add_argument(
        "--reference-output",
        type=str,
        default=None,
        help=(
            "Generated Markdown reference index path. Defaults to "
            "docs/REFERENCE_INDEX.md only for the default manifest output."
        ),
    )
    args = parser.parse_args()

    output_path = Path(args.output).resolve()
    reference_output = (
        Path(args.reference_output).resolve()
        if args.reference_output
        else DEFAULT_REFERENCE_OUTPUT if output_path == DEFAULT_OUTPUT else None
    )

    if args.check:
        manifest_status = check_manifest(output_path)
        if manifest_status != 0:
            sys.exit(manifest_status)
        if reference_output is None:
            sys.exit(0)
        existing = json.loads(output_path.read_text(encoding="utf-8"))
        sys.exit(check_reference_index(existing, reference_output))
    else:
        manifest = generate_manifest(output_path)
        if reference_output is not None:
            write_reference_index(manifest, reference_output)
        count = len(manifest["capabilities"]["capabilities"])
        contract_count = len(manifest["data_contracts"]["contracts"])
        reference_note = f"; reference index: {reference_output}" if reference_output else ""
        print(
            f"Generated manifest: {output_path} "
            f"({count} capabilities, {contract_count} data contracts){reference_note}"
        )


if __name__ == "__main__":
    main()
