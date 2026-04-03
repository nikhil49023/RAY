#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "${ROOT_DIR}/.env" && -f "${ROOT_DIR}/.env.example" ]]; then
  cp "${ROOT_DIR}/.env.example" "${ROOT_DIR}/.env"
fi

exec "${ROOT_DIR}/.venv/bin/python" -m streamlit run "${ROOT_DIR}/scripts/settings_ui.py" \
  --server.address 0.0.0.0 \
  --server.port 8501