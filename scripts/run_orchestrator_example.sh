#!/usr/bin/env bash
set -euo pipefail

python3 -m agents.orchestrator run_pipeline --url "${1:-https://mendable.ai}" --chart "bar" --target_language_code "gu-IN"
