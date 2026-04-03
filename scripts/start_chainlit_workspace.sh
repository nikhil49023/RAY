#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"${ROOT_DIR}/scripts/start_docker_stack.sh"
exec "${ROOT_DIR}/scripts/start_chainlit.sh"
