#!/bin/bash
# Stop all EVE Market Agent services

PID_DIR="$(cd "$(dirname "$0")/.." && pwd)/.pids"

if [ ! -d "$PID_DIR" ] || [ -z "$(ls "$PID_DIR"/*.pid 2>/dev/null)" ]; then
    echo "No running services found."
    exit 0
fi

echo "Stopping services..."
for pid_file in "$PID_DIR"/*.pid; do
    name=$(basename "$pid_file" .pid)
    pid=$(cat "$pid_file")
    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid"
        echo "  Stopped $name (PID $pid)"
    else
        echo "  $name (PID $pid) already stopped"
    fi
    rm -f "$pid_file"
done
echo "Done."
