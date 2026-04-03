#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# RAY — Firecrawl Self-Host Startup
# ═══════════════════════════════════════════════════════════════════
# Two modes:
#   1. Integrated mode (default): Uses the firecrawl services
#      defined in the project's docker-compose.yml
#   2. Standalone mode (--standalone): Clones the upstream repo
#      and uses its own docker-compose.yml
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── Color output helpers ─────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}╔═══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   RAY — Firecrawl Self-Host Launcher      ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════╝${NC}"

# ── Integrated mode: just start from project docker-compose.yml ──
if [[ "${1:-}" != "--standalone" ]]; then
  echo ""
  echo -e "${GREEN}▸ Starting Firecrawl via project docker-compose.yml${NC}"
  echo -e "  Services: firecrawl-api (port 3002), firecrawl-redis, firecrawl-playwright"
  echo ""

  pushd "${ROOT_DIR}" >/dev/null
  docker compose up -d firecrawl-api firecrawl-redis firecrawl-playwright
  popd >/dev/null

  echo ""
  echo -e "${GREEN}✓ Firecrawl self-host started${NC}"
  echo -e "  API endpoint:  ${YELLOW}http://localhost:3002${NC}"
  echo -e "  Health check:  ${YELLOW}http://localhost:3002/health${NC}"
  echo -e "  Auth:          ${YELLOW}Disabled (USE_DB_AUTHENTICATION=false)${NC}"
  echo ""
  echo -e "  ${CYAN}No API key needed for self-hosted Firecrawl.${NC}"
  echo -e "  Set FIRECRAWL_BASE_URL=http://localhost:3002 in .env or chat settings."
  exit 0
fi

# ── Standalone mode: clone upstream and run ──────────────────────
SELFHOST_DIR="${ROOT_DIR}/data/firecrawl-selfhost"

echo ""
echo -e "${GREEN}▸ Standalone mode — cloning upstream Firecrawl${NC}"

if [[ ! -d "${SELFHOST_DIR}" ]]; then
  git clone --depth=1 https://github.com/mendableai/firecrawl "${SELFHOST_DIR}"
fi

pushd "${SELFHOST_DIR}" >/dev/null
if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    cp .env.example .env
  fi
  # Set defaults for self-host
  {
    echo ""
    echo "# RAY self-host defaults"
    echo "PORT=3002"
    echo "HOST=0.0.0.0"
    echo "USE_DB_AUTHENTICATION=false"
    echo "NUM_WORKERS_PER_QUEUE=2"
  } >> .env
fi

echo -e "  Starting from ${SELFHOST_DIR}"
echo -e "  ${YELLOW}Note: Firecrawl standalone needs substantial CPU/RAM.${NC}"

docker compose up -d
popd >/dev/null

echo ""
echo -e "${GREEN}✓ Firecrawl standalone stack started${NC}"
echo -e "  API endpoint:  ${YELLOW}http://localhost:3002${NC}"
echo -e "  Set FIRECRAWL_BASE_URL=http://localhost:3002 in .env or chat settings."
