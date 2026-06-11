#!/usr/bin/env bash
# ScoutFootball Desktop — Build Script
# Builds the Electron app with embedded Python backend for macOS and/or Windows.
#
# Usage:
#   bash scripts/build-desktop.sh              # Build for current platform
#   bash scripts/build-desktop.sh --mac        # Build for macOS only
#   bash scripts/build-desktop.sh --win        # Build for Windows only
#   bash scripts/build-desktop.sh --all        # Build for both platforms
#   bash scripts/build-desktop.sh --backend    # Build Python backend only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DESKTOP_DIR="$PROJECT_DIR/desktop"
BUILD_TARGET=""
BACKEND_ONLY=false

for arg in "$@"; do
    case $arg in
        --mac)       BUILD_TARGET="mac" ;;
        --win)       BUILD_TARGET="win" ;;
        --all)       BUILD_TARGET="all" ;;
        --backend)   BACKEND_ONLY=true ;;
    esac
done

cd "$DESKTOP_DIR"

echo "=========================================="
echo "  ScoutFootball Desktop Build"
echo "=========================================="
echo ""

# ── Step 1: Build Python backend ───────────────────────────────
echo "[1/4] Building Python backend with PyInstaller..."

# Install Python dependencies for the backend
cd "$PROJECT_DIR"
uv sync --quiet

# Install PyInstaller if not present
uv run pip install pyinstaller --quiet 2>/dev/null || true

# Build the backend executable
cd "$DESKTOP_DIR"
uv run pyinstaller \
    --clean \
    --noconfirm \
    --distpath backend-dist \
    --workpath backend-build \
    scoutfootball-server.spec

echo "      Backend built: backend-dist/scoutfootball-server/"
echo ""

if [ "$BACKEND_ONLY" = true ]; then
    echo "Backend build complete (--backend flag). Skipping Electron build."
    exit 0
fi

# ── Step 2: Copy frontend files ────────────────────────────────
echo "[2/4] Copying frontend files..."
rm -rf frontend
mkdir -p frontend
cp "$PROJECT_DIR/frontend/index.html" frontend/
cp "$PROJECT_DIR/frontend/style.css" frontend/
cp "$PROJECT_DIR/frontend/app.js" frontend/
cp "$PROJECT_DIR/frontend/tactical-board.js" frontend/
cp "$PROJECT_DIR/frontend/tactical-renderer.js" frontend/
echo "      Frontend copied."
echo ""

# ── Step 3: Copy backend executable ────────────────────────────
echo "[3/4] Setting up backend in Electron resources..."
# The backend executable will be placed in extraResources during electron-builder build
echo ""

# ── Step 4: Install Electron dependencies and build ────────────
echo "[4/4] Building Electron app..."

# Install Node dependencies
if [ ! -d "node_modules" ]; then
    npm install
fi

# Build based on target
if [ -z "$BUILD_TARGET" ]; then
    # Auto-detect platform
    case "$(uname -s)" in
        Darwin*)  BUILD_TARGET="mac" ;;
        MINGW*|MSYS*|CYGWIN*)  BUILD_TARGET="win" ;;
        *)        BUILD_TARGET="mac" ;;
    esac
fi

case $BUILD_TARGET in
    mac)
        echo "      Building for macOS..."
        npx electron-builder --mac
        echo ""
        echo "=========================================="
        echo "  macOS build complete!"
        echo "  Output: desktop/dist/"
        echo "=========================================="
        ls -la dist/*.dmg 2>/dev/null || echo "  (Check desktop/dist/ for output)"
        ;;
    win)
        echo "      Building for Windows..."
        npx electron-builder --win
        echo ""
        echo "=========================================="
        echo "  Windows build complete!"
        echo "  Output: desktop/dist/"
        echo "=========================================="
        ls -la dist/*.exe 2>/dev/null || echo "  (Check desktop/dist/ for output)"
        ;;
    all)
        echo "      Building for macOS and Windows..."
        npx electron-builder --mac --win
        echo ""
        echo "=========================================="
        echo "  Build complete!"
        echo "  Output: desktop/dist/"
        echo "=========================================="
        ls -la dist/
        ;;
esac
