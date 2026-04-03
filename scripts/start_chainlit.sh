#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${ROOT_DIR}/.env"
  set +a
fi

HOST="${CHAINLIT_HOST:-0.0.0.0}"
PORT="${CHAINLIT_PORT:-8001}"

if [[ ! -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  echo "Missing virtual environment at ${ROOT_DIR}/.venv"
  echo "Run scripts/bootstrap.sh first."
  exit 1
fi

# Prevent generic shell DEBUG values (for example DEBUG=release)
# from being interpreted as Chainlit's --debug option.
unset DEBUG

exec "${ROOT_DIR}/.venv/bin/python" -m chainlit run "${ROOT_DIR}/app/chainlit_app.py" --host "${HOST}" --port "${PORT}"
