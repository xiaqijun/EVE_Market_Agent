#!/bin/bash
# Unified startup script for EVE Market Agent
# Usage: bash scripts/start.sh [--no-flower]

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
LOG_DIR="$PROJECT_DIR/logs"
PID_DIR="$PROJECT_DIR/.pids"

mkdir -p "$LOG_DIR" "$PID_DIR"

# Parse args
WITH_FLOWER=true
for arg in "$@"; do
    case "$arg" in
        --no-flower) WITH_FLOWER=false ;;
    esac
done

# Cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down..."
    for pid_file in "$PID_DIR"/*.pid; do
        [ -f "$pid_file" ] && kill "$(cat "$pid_file")" 2>/dev/null
    done
    rm -f "$PID_DIR"/*.pid
    echo "All services stopped."
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start a service in background, save PID
start_service() {
    local name="$1"
    shift
    echo "Starting $name..."
    cd "$BACKEND_DIR"
    source .venv/bin/activate
    "$@" > "$LOG_DIR/${name}.log" 2>&1 &
    echo $! > "$PID_DIR/${name}.pid"
    echo "  $name started (PID $!, log: logs/${name}.log)"
}

start_service "backend"  uvicorn app.main:app --host 0.0.0.0 --port 8000
start_service "worker"   celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2
start_service "beat"     celery -A app.tasks.celery_app beat --loglevel=info

if [ "$WITH_FLOWER" = true ]; then
    start_service "flower" celery -A app.tasks.celery_app flower --port=5555 --broker_api=redis://localhost:6379/0 --url_prefix=flower
fi

echo ""
echo "========================================="
echo "  EVE Market Agent is running"
echo "========================================="
echo "  Backend:  http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
if [ "$WITH_FLOWER" = true ]; then
    echo "  Flower:   http://localhost:5555/flower/"
fi
echo "  Logs:     $LOG_DIR/"
echo "  PIDs:     $PID_DIR/"
echo ""
echo "  Press Ctrl+C to stop all services"
echo "========================================="

# Wait for any child to exit
wait
