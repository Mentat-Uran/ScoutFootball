# ScoutFootball Desktop

Standalone desktop application for ScoutFootball — runs the full analytics platform without requiring Python or command-line setup.

## Features

- **Native app** — runs as a standalone application on macOS and Windows
- **Bundled data** — includes pre-computed player ratings, match predictions, and scouting queues
- **Auto-updates** — checks GitHub releases for updates on startup
- **System tray** — minimizes to tray for quick access
- **Offline-first** — all data and models are local; no internet required after install

## Building

### Prerequisites

- **Node.js** 18+ and npm
- **Python** 3.11+ with uv
- **PyInstaller** (installed automatically by build script)

### Build for current platform

```bash
bash scripts/build-desktop.sh
```

### Build for specific platform

```bash
bash scripts/build-desktop.sh --mac    # macOS (.dmg + .zip)
bash scripts/build-desktop.sh --win    # Windows (.exe + .zip)
bash scripts/build-desktop.sh --all    # Both platforms
```

### Build Python backend only

```bash
bash scripts/build-desktop.sh --backend
```

## Output

Build artifacts are in `desktop/dist/`:

- **macOS**: `ScoutFootball-{version}.dmg` (Intel + Apple Silicon)
- **Windows**: `ScoutFootball Setup {version}.exe` (x64)

## Architecture

```
ScoutFootball.app / ScoutFootball.exe
├── Electron shell (native window, tray, auto-update)
├── Frontend (static HTML/CSS/JS — Liquid Glass UI)
├── Python backend (PyInstaller-compiled FastAPI server)
└── Data (pre-computed Parquet files, ~12MB)
```

## Auto-Updates

The app checks GitHub releases for updates on startup. When an update is available:
1. A dialog prompts to download
2. Progress bar shows download status
3. User chooses to restart now or later

Updates are published as GitHub releases with platform-specific assets.

## Development

```bash
# Run in development mode (uses system Python)
cd desktop
npm install
npm start
```

## Data Bundling

The following data is included in the app:

| File | Size | Content |
|---|---|---|
| `player_ratings_optimized.parquet` | 2.0MB | 30K player ratings |
| `rating_feature_matrix.parquet` | 227KB | Feature matrix |
| `team_match.parquet` | 190KB | Match results |
| `scoutlab.duckdb` | 6.0MB | Analytics database |
| `models/artifacts/` | 60KB | Poisson + Dixon-Coles models |
| `data/reports/` | — | Scouting queues |

Total bundled data: ~12MB

## Updating Bundled Data

To update the data in a new release:

1. Run the pipeline locally: `scoutfootball ingest && scoutfootball build-features && scoutfootball train`
2. The build script automatically copies the latest data from `data/`
3. Build and publish a new release
