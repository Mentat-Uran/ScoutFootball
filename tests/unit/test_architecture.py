from scoutlab.architecture import build_default_architecture


def test_architecture_covers_required_phase_one_modules() -> None:
    architecture = build_default_architecture()

    module_names = {module.name for module in architecture.module_boundaries}
    assert {
        "adapters",
        "entities",
        "storage",
        "features",
        "models",
        "evaluation",
        "viz",
        "app",
    }.issubset(module_names)


def test_architecture_commands_include_live_entrypoints() -> None:
    architecture = build_default_architecture()

    assert "uv sync" in architecture.supported_commands
    assert "uv run pytest" in architecture.supported_commands
    assert "uv run ruff check ." in architecture.supported_commands
    assert "uv run python -m scoutlab" in architecture.supported_commands
