#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  echo "Missing virtual environment at ${ROOT_DIR}/.venv"
  echo "Run scripts/bootstrap.sh first."
  exit 1
fi

"${ROOT_DIR}/.venv/bin/python" -m pip install --upgrade pip
"${ROOT_DIR}/.venv/bin/python" -m pip install -r "${ROOT_DIR}/requirements-agentic.txt"

echo "Agentic stack installed."
