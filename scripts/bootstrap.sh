#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example. Fill in your API keys before running services."
fi

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

echo "Bootstrap complete."
