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
    # Check environment variable first
    env_root = os.environ.get("SCOUTFOOTBALL_DATA_ROOT")
    if env_root:
        p = Path(env_root)
        if p.exists():
            return p

    # Check if we're running as a PyInstaller bundle
    if getattr(sys, "frozen", False):
        # Running as compiled executable
        bundle_dir = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        # Data is in extraResources
        if sys.platform == "darwin":
            # macOS: Resources dir is next to the .app bundle
            resources_dir = bundle_dir.parent / "Resources"
            if resources_dir.exists():
                return resources_dir
        # Windows/Linux: data is next to the executable
        exe_dir = Path(sys.executable).parent
        return exe_dir

    # Development mode: use project root
    return Path(__file__).resolve().parents[2]


def main() -> None:
    """Start the ScoutFootball API server."""
    data_root = _resolve_data_root()

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
        print("ScoutFootball API server starting on port 8600...")
        print(f"Data root: {data_root}")
        uvicorn.run(app, host="127.0.0.1", port=8600, log_level="info")
    except ImportError as e:
        print(f"Error: Missing dependency: {e}")
        print("Please ensure all dependencies are installed.")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
