#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SELFHOST_DIR="${ROOT_DIR}/data/firecrawl-selfhost"

if [[ ! -d "${SELFHOST_DIR}" ]]; then
  git clone --depth=1 https://github.com/mendableai/firecrawl "${SELFHOST_DIR}"
fi

pushd "${SELFHOST_DIR}" >/dev/null
if [[ ! -f .env ]]; then
  cp .env.example .env || true
fi

echo "Starting Firecrawl self-host stack from ${SELFHOST_DIR}"
echo "Note: Firecrawl self-host needs substantial CPU/RAM compared to lightweight stacks."

docker compose up -d
popd >/dev/null

echo "Firecrawl self-host started (if compose completed successfully)."
echo "Set FIRECRAWL_BASE_URL in project .env to http://localhost:3002 when ready."
