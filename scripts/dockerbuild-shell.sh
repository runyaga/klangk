#!/usr/bin/env bash
# Build the shell-only Docker image (no Pi agent).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${DEVENV_ROOT:-$SCRIPT_DIR/..}"

IMAGE="bark-shell"

echo "==> Building shell-only image"
docker build --platform linux/amd64 \
  -f src/docker/Dockerfile.shell \
  -t "$IMAGE" src/docker/

echo "==> Done: $IMAGE"
