#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
  echo "Created .env from .env.example. Fill in your API keys before running services."
fi

if [[ ! -d "$ROOT_DIR/.venv" ]]; then
  python3 -m venv "$ROOT_DIR/.venv"
fi

"$ROOT_DIR/.venv/bin/python" -m pip install --upgrade pip

echo "Bootstrap complete."
echo "Next: ./scripts/install_agentic_stack.sh"
