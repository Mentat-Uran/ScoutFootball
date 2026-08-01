#!/usr/bin/env bash
# ScoutFootball v1.0.0 — Quick Demo Script
# Run this to verify the pipeline works end-to-end and start the web UI.
#
# The web UI and API are served on the same origin by FastAPI — no separate
# frontend server is needed.
#
# Usage:
#   bash scripts/demo.sh              # Full pipeline + start server
#   bash scripts/demo.sh --skip-pipe  # Skip pipeline, just start server
#   bash scripts/demo.sh --validate   # Only validate data, don't start server
#   bash scripts/demo.sh --smoke      # Start server, run health check, exit

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

PORT="${SCOUTFOOTBALL_PORT:-8000}"
HOST="${SCOUTFOOTBALL_HOST:-127.0.0.1}"

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

echo "[1/4] Syncing dependencies..."
uv sync --quiet

SKIP_PIPE=false
VALIDATE_ONLY=false
SMOKE_ONLY=false
for arg in "$@"; do
    case $arg in
        --skip-pipe) SKIP_PIPE=true ;;
        --validate)  VALIDATE_ONLY=true ;;
        --smoke)     SMOKE_ONLY=true ;;
    esac
done

if [ "$SKIP_PIPE" = false ]; then
    echo "[2/4] Running data validation..."
    PYTHONPATH=src uv run python -m scoutfootball validate 2>&1 | tail -5
    echo ""

    echo "[3/4] Running pipeline (ingest → build-features → train)..."
    echo "      This may take a few minutes on first run..."
    PYTHONPATH=src uv run python -m scoutfootball ingest 2>&1 | tail -3
    PYTHONPATH=src uv run python -m scoutfootball build-features 2>&1 | tail -3
    PYTHONPATH=src uv run python -m scoutfootball train 2>&1 | tail -3
    echo ""
else
    echo "[2/4] Skipping pipeline (--skip-pipe)"
    echo "[3/4] Skipping pipeline (--skip-pipe)"
fi

if [ "$VALIDATE_ONLY" = true ]; then
    echo "Validation complete. Exiting (--validate)."
    exit 0
fi

echo "[4/4] Starting FastAPI server on ${HOST}:${PORT}..."
echo "      (same-origin: API + frontend served by FastAPI)"
PYTHONPATH=src uv run python -m scoutfootball serve --host "$HOST" --port "$PORT" &
SERVER_PID=$!
sleep 2

# Check if server started
if kill -0 $SERVER_PID 2>/dev/null; then
    echo "      Server running (PID $SERVER_PID)"
else
    echo "      ERROR: Server failed to start."
    exit 1
fi

# Smoke test: verify /health and frontend respond
echo ""
echo "  Running smoke test..."
SMOKE_OK=true

if command -v curl &>/dev/null; then
    HEALTH_RESPONSE=$(curl -sf "http://${HOST}:${PORT}/health" 2>/dev/null || echo "")
    if [ -n "$HEALTH_RESPONSE" ]; then
        echo "  ✓ /health: $HEALTH_RESPONSE"
    else
        echo "  ✗ /health: no response"
        SMOKE_OK=false
    fi

    FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://${HOST}:${PORT}/" 2>/dev/null || echo "000")
    if [ "$FRONTEND_STATUS" = "200" ]; then
        echo "  ✓ / (frontend): HTTP 200"
    else
        echo "  ✗ / (frontend): HTTP $FRONTEND_STATUS"
        SMOKE_OK=false
    fi
else
    echo "  (curl not found, skipping HTTP smoke test)"
fi

if [ "$SMOKE_ONLY" = true ]; then
    echo ""
    kill $SERVER_PID 2>/dev/null || true
    if [ "$SMOKE_OK" = true ]; then
        echo "  Smoke test passed."
        exit 0
    else
        echo "  Smoke test failed."
        exit 1
    fi
fi

echo ""
echo "=========================================="
echo "  Open http://${HOST}:${PORT} in your browser"
echo "  (API and frontend on the same origin)"
echo "=========================================="
echo ""
echo "  Press Ctrl+C to stop the server."
echo ""

# Cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down..."
    [ -n "${SERVER_PID:-}" ] && kill $SERVER_PID 2>/dev/null || true
    echo "Done."
}
trap cleanup EXIT INT TERM

# Wait for the server process to exit
wait $SERVER_PID 2>/dev/null || wait
