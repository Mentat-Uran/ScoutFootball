"""CLI entrypoint for ScoutLab pipeline operations."""

from __future__ import annotations

import argparse
import sys

from scoutlab.architecture import build_default_architecture


def _cmd_info(_args: argparse.Namespace) -> None:
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
    print("\n".join(lines))


def _cmd_ingest(args: argparse.Namespace) -> None:
    from scoutlab.pipeline import run_daily_ingest

    results = run_daily_ingest(sources=tuple(args.sources))
    for source, status in results.items():
        print(f"  {source}: {status}")


def _cmd_build_features(_args: argparse.Namespace) -> None:
    from scoutlab.pipeline import run_build_features

    results = run_build_features()
    for feature_set, status in results.items():
        print(f"  {feature_set}: {status}")


def _cmd_train(_args: argparse.Namespace) -> None:
    from scoutlab.pipeline import run_weekly_train

    results = run_weekly_train()
    for model, status in results.items():
        print(f"  {model}: {status}")


def _cmd_validate(_args: argparse.Namespace) -> None:
    from scoutlab.evaluation.validation import run_pre_training_validation

    report = run_pre_training_validation()
    print(report.summary())


def _cmd_serve(args: argparse.Namespace) -> None:
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn not installed. Run: uv add uvicorn")
        sys.exit(1)

    from scoutlab.api_server import create_app

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="scoutlab",
        description="ScoutLab — local-first football data research platform",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("info", help="Show project info and module status")

    ingest_p = sub.add_parser("ingest", help="Run daily data ingestion")
    ingest_p.add_argument(
        "--sources",
        nargs="+",
        default=["statsbomb_open", "football_data", "clubelo"],
        help="Data sources to ingest",
    )

    sub.add_parser("build-features", help="Build feature store from raw data")
    sub.add_parser("train", help="Run weekly model training")
    sub.add_parser("validate", help="Run pre-training data validation")

    serve_p = sub.add_parser("serve", help="Start FastAPI server")
    serve_p.add_argument("--host", default="0.0.0.0")
    serve_p.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()

    handlers = {
        "info": _cmd_info,
        "ingest": _cmd_ingest,
        "build-features": _cmd_build_features,
        "train": _cmd_train,
        "validate": _cmd_validate,
        "serve": _cmd_serve,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)
    handler(args)


if __name__ == "__main__":
    main()
