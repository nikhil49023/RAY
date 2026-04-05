#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT_DIR/godmode-agent"

echo "Starting core backend services (Docker)..."
"$ROOT_DIR/scripts/start_docker_stack.sh"

export PYTHONPATH="$APP_DIR"

if [ -f "$APP_DIR/venv/bin/python" ]; then
    PYTHON_CMD="$APP_DIR/venv/bin/python"
elif [ -f "$ROOT_DIR/.venv/bin/python" ]; then
    PYTHON_CMD="$ROOT_DIR/.venv/bin/python"
else
    PYTHON_CMD="python3"
fi

echo "Starting FastAPI God Mode backend..."
cd "$APP_DIR"
"$PYTHON_CMD" -m uvicorn apps.api.server:app --host 0.0.0.0 --port 8002 --reload &
API_PID=$!

echo "Starting React/Vite frontend..."
cd "$APP_DIR/apps/web"
if [ ! -d "node_modules" ]; then
    npm install
fi
npm run dev -- --host &
WEB_PID=$!

# Trap termination signals to kill background processes
trap "kill \$API_PID \$WEB_PID; exit" EXIT INT TERM

echo "App is starting..."
wait
