#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  echo "Missing .env file. Run scripts/bootstrap.sh first and add keys."
  exit 1
fi

# Core services only (Firecrawl is optional via --profile firecrawl)
# To include Firecrawl: docker compose --profile firecrawl up -d
echo "Starting core Docker services (LiteLLM, ChromaDB, Qdrant)..."
docker compose up -d litellm chromadb qdrant

echo ""
echo "=== Core Services ==="
echo "LiteLLM:   http://localhost:4000"
echo "ChromaDB:  http://localhost:8000"
echo "Qdrant:    http://localhost:6333"
echo ""
echo "=== Optional Services ==="
echo "Ollama:    docker compose up -d ollama (http://localhost:11434)"
echo "Firecrawl: docker compose --profile firecrawl up -d (http://localhost:3002)"
echo "           Or run: scripts/start_firecrawl_selfhost.sh"
echo ""
echo "App:       run scripts/start_app.sh (API: http://localhost:8002, Web: http://localhost:5173)"
