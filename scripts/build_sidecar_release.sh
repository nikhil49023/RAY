#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-v0.1.0}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELEASE_DIR="$ROOT_DIR/release"
STAGING_DIR="$RELEASE_DIR/staging/$VERSION"
APP_DIR="$STAGING_DIR/ray-sidecar-app"
ZIP_PATH="$RELEASE_DIR/ray-sidecar-app-$VERSION.zip"
TAR_PATH="$RELEASE_DIR/ray-sidecar-app-$VERSION.tar.gz"
SHA_PATH="$RELEASE_DIR/ray-sidecar-app-$VERSION.sha256"

rm -rf "$STAGING_DIR"
mkdir -p "$APP_DIR" "$RELEASE_DIR"

tar \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='release' \
  --exclude='godmode-agent/venv' \
  --exclude='godmode-agent/apps/web/node_modules' \
  --exclude='godmode-agent/apps/web/dist' \
  --exclude='data' \
  --exclude='__pycache__' \
  --exclude='.ruff_cache' \
  -cf - \
  docker-compose.sidecar.yml \
  README_SIDECAR.md \
  .env.example \
  LICENSE \
  requirements.txt \
  requirements-agentic.txt \
  requirements-langgraph.txt \
  godmode-agent \
  scripts \
  | tar -xf - -C "$APP_DIR"

rm -f "$ZIP_PATH" "$TAR_PATH" "$SHA_PATH"

(cd "$STAGING_DIR" && zip -qr "$ZIP_PATH" ray-sidecar-app)
tar -czf "$TAR_PATH" -C "$STAGING_DIR" ray-sidecar-app
sha256sum "$ZIP_PATH" "$TAR_PATH" > "$SHA_PATH"

printf 'Created:\n- %s\n- %s\n- %s\n' "$ZIP_PATH" "$TAR_PATH" "$SHA_PATH"
