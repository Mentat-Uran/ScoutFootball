"""CLI entrypoint for inspecting the current scaffold."""

from __future__ import annotations

from scoutlab.architecture import build_default_architecture


def render_summary() -> str:
    architecture = build_default_architecture()
    lines = [
        f"package: {architecture.package_name}",
        f"status: {architecture.status}",
        "modules:",
    ]
    lines.extend(
        f"  - {module.name}: {module.purpose}"
        for module in architecture.module_boundaries
    )
    lines.append("commands:")
    lines.extend(f"  - {command}" for command in architecture.supported_commands)
    return "\n".join(lines)


def main() -> None:
    print(render_summary())


if __name__ == "__main__":
    main()
