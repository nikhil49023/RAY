#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f .env ]]; then
  echo "Missing .env file. Run scripts/bootstrap.sh first and add keys."
  exit 1
fi

docker compose up -d

echo "LiteLLM:   http://localhost:4000"
echo "ChromaDB:  http://localhost:8000"
echo "Ollama:    http://localhost:11434"
echo "Chainlit:  run scripts/start_chainlit.sh (default http://localhost:8001)"
