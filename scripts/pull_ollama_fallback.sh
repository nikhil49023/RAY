#!/usr/bin/env bash
set -euo pipefail

MODEL="${1:-deepseek-r1:8b}"
OLLAMA_HOST="${OLLAMA_BASE_URL:-http://localhost:11434}"

curl -sS "${OLLAMA_HOST}/api/pull" -d "{\"name\": \"${MODEL}\"}"
echo
echo "Requested pull for model: ${MODEL}"
