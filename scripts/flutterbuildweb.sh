#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${DEVENV_ROOT:-$SCRIPT_DIR/..}"

# Auto-fetch plugins on first run
if [ -f "$KLANGK_PLUGINS_DIR/plugins.yaml" ] && [ ! -f "$KLANGK_PLUGINS_DIR/plugins.lock" ]; then
  echo "No plugins.lock found, running update-plugins..."
  python3 scripts/update_plugins.py
fi

python3 scripts/import_dart_plugins.py

# The frontend depends on flterm >=0.0.3, which requires Dart 3.12 / Flutter
# 3.44 (private-named-parameters language feature). The nix toolchain ships
# Flutter 3.41 / Dart 3.11, so the web build runs against a host Flutter.
# Override the binary with KLANGK_WEB_FLUTTER (e.g. /opt/homebrew/bin/flutter);
# defaults to whatever `flutter` is on PATH.
FLUTTER="${KLANGK_WEB_FLUTTER:-flutter}"
DART_VER="$("$FLUTTER" --version 2>/dev/null | grep -oiE 'Dart (SDK version: )?[0-9]+\.[0-9]+\.[0-9]+' | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
if [ -n "$DART_VER" ]; then
  IFS=. read -r DMAJ DMIN _ <<<"$DART_VER"
  if [ "$DMAJ" -lt 3 ] || { [ "$DMAJ" -eq 3 ] && [ "$DMIN" -lt 12 ]; }; then
    echo "ERROR: $FLUTTER ships Dart $DART_VER, but flterm >=0.0.3 needs Dart >=3.12." >&2
    echo "       Set KLANGK_WEB_FLUTTER to a Flutter 3.44+ install (e.g. host Homebrew)." >&2
    exit 1
  fi
fi

cd src/frontend && "$FLUTTER" --disable-analytics && "$FLUTTER" pub get && "$FLUTTER" build web --release --base-href=/ --no-wasm-dry-run --no-web-resources-cdn
rm -f build/web/flutter_service_worker.js

# Cache-busting: append a content hash to flutter_bootstrap.js reference
# in index.html. Since index.html is served with no-cache headers, browsers
# always get the latest reference. The ?v= query string busts cached copies
# of the bootstrap script, which in turn loads a fresh main.dart.js (whose
# URL is embedded in the build config with a service worker version).
BUILD_DIR=build/web
HASH=$(sha256sum "$BUILD_DIR/main.dart.js" | cut -c1-12)
sed -i "s|flutter_bootstrap.js|flutter_bootstrap.js?v=${HASH}|" "$BUILD_DIR/index.html"
echo "Cache-bust: v=$HASH"
