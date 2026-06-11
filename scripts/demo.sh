#!/usr/bin/env bash
# ScoutFootball v1.0.0 — Quick Demo Script
# Run this to verify the pipeline works end-to-end and start the web UI.
#
# Usage:
#   bash scripts/demo.sh              # Full pipeline + start servers
#   bash scripts/demo.sh --skip-pipe  # Skip pipeline, just start servers
#   bash scripts/demo.sh --validate   # Only validate data, don't start servers

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "=========================================="
echo "  ScoutFootball v1.0.0 Demo"
echo "=========================================="
echo ""

# Check dependencies
if ! command -v uv &>/dev/null; then
    echo "ERROR: 'uv' not found. Install it: https://docs.astral.sh/uv/"
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found."
    exit 1
fi

echo "[1/5] Syncing dependencies..."
uv sync --quiet

SKIP_PIPE=false
VALIDATE_ONLY=false
for arg in "$@"; do
    case $arg in
        --skip-pipe) SKIP_PIPE=true ;;
        --validate)  VALIDATE_ONLY=true ;;
    esac
done

if [ "$SKIP_PIPE" = false ]; then
    echo "[2/5] Running data validation..."
    PYTHONPATH=src uv run python -m scoutfootball validate 2>&1 | tail -5
    echo ""

    echo "[3/5] Running pipeline (ingest → build-features → train)..."
    echo "      This may take a few minutes on first run..."
    PYTHONPATH=src uv run python -m scoutfootball ingest 2>&1 | tail -3
    PYTHONPATH=src uv run python -m scoutfootball build-features 2>&1 | tail -3
    PYTHONPATH=src uv run python -m scoutfootball train 2>&1 | tail -3
    echo ""
else
    echo "[2/5] Skipping pipeline (--skip-pipe)"
    echo "[3/5] Skipping pipeline (--skip-pipe)"
fi

if [ "$VALIDATE_ONLY" = true ]; then
    echo "Validation complete. Exiting (--validate)."
    exit 0
fi

echo "[4/5] Starting FastAPI backend on port 8600..."
PYTHONPATH=src uv run python -m scoutfootball serve &
API_PID=$!
sleep 2

# Check if API started
if kill -0 $API_PID 2>/dev/null; then
    echo "      API server running (PID $API_PID)"
else
    echo "      WARNING: API server failed to start. Frontend will use demo data."
    API_PID=""
fi

echo "[5/5] Starting frontend on port 8601..."
echo ""
echo "=========================================="
echo "  Open http://localhost:8601 in your browser"
echo "  API backend: http://localhost:8600"
echo "=========================================="
echo ""
echo "  Press Ctrl+C to stop all servers."
echo ""

# Serve frontend
if command -v python3 &>/dev/null; then
    python3 -m http.server 8601 --directory frontend &
    WEB_PID=$!
else
    echo "ERROR: python3 not available for frontend server."
    exit 1
fi

# Cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down..."
    [ -n "${API_PID:-}" ] && kill $API_PID 2>/dev/null || true
    [ -n "${WEB_PID:-}" ] && kill $WEB_PID 2>/dev/null || true
    echo "Done."
}
trap cleanup EXIT INT TERM

# Wait for either process to exit
wait -n $API_PID $WEB_PID 2>/dev/null || wait
