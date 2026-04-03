#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GOAL="${*:-Analyze available local documents and produce a compact dashboard.}"

exec "${ROOT_DIR}/.venv/bin/python" -m agents.agentic_orchestrator run_goal --objective "${GOAL}"
