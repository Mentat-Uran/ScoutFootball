#!/usr/bin/env python3
"""Bump version across all project files.

Usage:
    python scripts/bump_version.py <new_version>

Example:
    python scripts/bump_version.py 1.0.3

This script updates the version string in all project files that contain it:
  - src/scoutfootball/__init__.py
  - pyproject.toml
  - desktop/package.json
  - desktop/package-lock.json (top-level + packages."")
  - frontend/app.js (APP_VERSION)
  - frontend/index.html (v-prefixed pill)
  - desktop/preload.js (fallback version)
  - tests/unit/test_phase10.py (assertion)
  - frontend/data/health.json
  - CHANGELOG.md (adds new entry)
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (file, old_pattern, replacement_builder)
# old_pattern uses {old} placeholder; replacement uses {new}
SPECS: list[tuple[Path, str, str]] = [
    (ROOT / "src" / "scoutfootball" / "__init__.py",
     '__version__ = "{old}"', '__version__ = "{new}"'),
    (ROOT / "pyproject.toml",
     'version = "{old}"', 'version = "{new}"'),
    (ROOT / "desktop" / "package.json",
     '"version": "{old}"', '"version": "{new}"'),
    (ROOT / "frontend" / "app.js",
     'const APP_VERSION = "{old}"', 'const APP_VERSION = "{new}"'),
    (ROOT / "frontend" / "index.html",
     'v{old}', 'v{new}'),
    (ROOT / "desktop" / "preload.js",
     'process.env.npm_package_version || "{old}"',
     'process.env.npm_package_version || "{new}"'),
    (ROOT / "tests" / "unit" / "test_phase10.py",
     'assert resp.version == "{old}"', 'assert resp.version == "{new}"'),
    (ROOT / "frontend" / "data" / "health.json",
     "version='{old}'", "version='{new}'"),
]

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def current_version() -> str:
    init_py = ROOT / "src" / "scoutfootball" / "__init__.py"
    m = re.search(r'__version__\s*=\s*"([^"]+)"', init_py.read_text())
    if not m:
        raise RuntimeError(f"Cannot find __version__ in {init_py}")
    return m.group(1)


def bump_package_lock(new: str) -> None:
    lock = ROOT / "desktop" / "package-lock.json"
    text = lock.read_text()
    # Top-level "version": "x.y.z"
    text = re.sub(
        r'("name":\s*"scoutfootball",\s*\n\s*"version":\s*)"(\d+\.\d+\.\d+)"',
        rf'\g<1>"{new}"',
        text,
    )
    # packages."".version
    text = re.sub(
        r'("name":\s*"scoutfootball",\s*\n\s*"version":\s*)"(\d+\.\d+\.\d+)"',
        rf'\g<1>"{new}"',
        text,
    )
    lock.write_text(text)


def add_changelog_entry(new: str) -> None:
    cl = ROOT / "CHANGELOG.md"
    text = cl.read_text()
    today = date.today().isoformat()
    entry = f"## [{new}] - {today}\n\n### Changed\n\n- Bump version to {new}.\n\n"
    # Insert before the first ## [ header
    m = re.search(r"^## \[", text, re.MULTILINE)
    if m:
        text = text[:m.start()] + entry + text[m.start():]
    else:
        text = text.rstrip() + "\n\n" + entry
    cl.write_text(text)


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <new_version>")
        sys.exit(1)

    new = sys.argv[1]
    if not SEMVER_RE.match(new):
        print(f"Error: '{new}' is not a valid semver (e.g. 1.0.3)")
        sys.exit(1)

    old = current_version()
    if old == new:
        print(f"Version is already {new}, nothing to do.")
        return

    print(f"Bumping version: {old} -> {new}")

    for path, old_pat, new_pat in SPECS:
        if not path.exists():
            print(f"  SKIP (not found): {path.relative_to(ROOT)}")
            continue
        text = path.read_text()
        old_str = old_pat.format(old=old)
        new_str = new_pat.format(new=new)
        if old_str not in text:
            print(f"  SKIP (pattern not found): {path.relative_to(ROOT)}")
            continue
        text = text.replace(old_str, new_str, 1)
        path.write_text(text)
        print(f"  OK: {path.relative_to(ROOT)}")

    # package-lock.json special handling
    bump_package_lock(new)
    print(f"  OK: desktop/package-lock.json")

    # CHANGELOG
    add_changelog_entry(new)
    print(f"  OK: CHANGELOG.md")

    print(f"\nDone. Version bumped from {old} to {new}.")


if __name__ == "__main__":
    main()
