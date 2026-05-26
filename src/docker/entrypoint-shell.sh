#!/bin/sh
# Minimal entrypoint for shell-only containers (no Pi agent).
# Same user setup as the full entrypoint, but skips Pi config and
# runs sleep instead of pi --mode rpc.

if [ "$(id -u)" = "0" ]; then
  chown bark:bark /home/bark /work
  exec gosu bark "$0" "$@"
fi

set -e

git config --global --add safe.directory /work 2>/dev/null

# Signal that setup is complete (same mechanism as the full entrypoint).
touch /tmp/.bark-ready

# Keep the container alive. Terminal and exec sessions use docker exec.
exec sleep infinity
