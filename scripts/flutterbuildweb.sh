#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${DEVENV_ROOT:-$SCRIPT_DIR/..}"

# Auto-fetch plugins on first run
if [ -f "$BARK_PLUGINS_DIR/plugins.yaml" ] && [ ! -f "$BARK_PLUGINS_DIR/plugins.lock" ]; then
  echo "No plugins.lock found, running update-plugins..."
  python3 scripts/update_plugins.py
fi

python3 scripts/import_dart_plugins.py
cd src/frontend && flutter --disable-analytics && flutter pub get && flutter build web --base-href=/ --no-wasm-dry-run --no-web-resources-cdn
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
