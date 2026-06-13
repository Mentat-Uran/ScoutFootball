"""ScoutFootball Desktop — Backend Server Entry Point.

This is the entry point for the PyInstaller-packaged backend executable.
It sets up the correct paths for bundled data and starts the FastAPI server.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _resolve_data_root() -> Path:
    """Resolve the data root directory for the packaged app."""
    # Check environment variable first (set by Electron main process)
    env_root = os.environ.get("SCOUTFOOTBALL_DATA_ROOT")
    if env_root:
        p = Path(env_root)
        if p.exists():
            return p

    # Check if we're running as a PyInstaller bundle
    if getattr(sys, "frozen", False):
        # Running as compiled executable
        # On Windows: data is in extraResources, resolved via SCOUTFOOTBALL_DATA_ROOT
        # set by Electron. If not set, look relative to the executable.
        exe_dir = Path(sys.executable).parent.resolve()

        # Check common data locations relative to the exe
        # NSIS install: C:\Program Files\ScoutFootball\resources\data\...
        for candidate in [
            exe_dir / "data",
            exe_dir.parent / "data",
            exe_dir / "resources" / "data",
        ]:
            if candidate.exists():
                return candidate

        # Fallback: the exe directory itself
        return exe_dir

    # Development mode: use project root
    return Path(__file__).resolve().parents[2]


def main() -> None:
    """Start the ScoutFootball API server."""
    import argparse

    parser = argparse.ArgumentParser(description="ScoutFootball API server")
    parser.add_argument("--port", type=int, default=8600)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    cli_args = parser.parse_args()

    data_root = _resolve_data_root()
    print(f"[server] Resolved data_root: {data_root}")
    print(f"[server] data_root exists: {data_root.exists()}")
    if data_root.exists():
        try:
            contents = list(data_root.iterdir())
            print(f"[server] data_root contents: {[p.name for p in contents[:20]]}")
        except Exception as e:
            print(f"[server] Cannot list data_root: {e}")

    # Check critical data subdirectories
    for subdir in ["gold", "models", "reports"]:
        subpath = data_root / subdir
        if not subpath.exists():
            print(f"[server] WARNING: data_root/{subdir} does not exist")
        else:
            print(f"[server] data_root/{subdir} exists")

    # Set environment for the app
    os.environ["SCOUTFOOTBALL_DATA_ROOT"] = str(data_root)

    # Add src to path if running in dev mode
    if not getattr(sys, "frozen", False):
        src_dir = Path(__file__).resolve().parents[2] / "src"
        if src_dir.exists() and str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))

    try:
        import uvicorn

        from scoutfootball.api_server import create_app

        app = create_app()
        print(f"ScoutFootball API server starting on port {cli_args.port}...")
        print(f"Data root: {data_root}")
        uvicorn.run(app, host=cli_args.host, port=cli_args.port, log_level="info")
    except ImportError as e:
        print(f"Error: Missing dependency: {e}")
        print("Please ensure all dependencies are installed.")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
