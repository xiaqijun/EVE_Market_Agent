#!/bin/bash
# Build frontend for production
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND_DIR="$PROJECT_DIR/frontend"

echo "Building frontend..."
cd "$FRONTEND_DIR"
npm run build
echo "Frontend built to $FRONTEND_DIR/dist/"
