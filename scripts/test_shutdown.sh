#!/usr/bin/env bash
# Test that SIGTERM to uvicorn stops all bark containers.
# Run from within devenv shell.
set -euxo pipefail

PORT=19999
DATA_DIR=$(mktemp -d /tmp/bark-shutdown-test-XXXXXX)
NUM_WORKSPACES=10

cleanup() {
  kill $PID 2>/dev/null || true
  docker ps --filter "label=bark.managed=true" -q | xargs -r docker stop 2>/dev/null || true
  rm -rf "$DATA_DIR"
}
trap cleanup EXIT

# Start uvicorn
cd "$(dirname "$0")/../src/backend"
BARK_DATA_DIR="$DATA_DIR" BARK_JWT_SECRET=test BARK_DEFAULT_USER=admin BARK_DEFAULT_PASSWORD=admin BARK_TEST_MODE=1 \
  uvicorn bark_backend.main:app --host 0.0.0.0 --port $PORT &
PID=$!
sleep 3

BASE="http://localhost:$PORT"

# Login
TOKEN=$(curl -s "$BASE/auth/login" \
  -d '{"username":"admin","password":"admin"}' \
  -H "Content-Type: application/json" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Create workspaces
for i in $(seq 1 $NUM_WORKSPACES); do
  curl -s -X POST "$BASE/workspaces?name=ws-$i" -H "Authorization: Bearer $TOKEN" > /dev/null
done
echo "Created $NUM_WORKSPACES workspaces"

# Open a WebSocket to each workspace to start containers
WS_IDS=$(curl -s "$BASE/workspaces" -H "Authorization: Bearer $TOKEN" | \
  python3 -c "import sys,json; [print(w['id']) for w in json.load(sys.stdin)]")

for ws in $WS_IDS; do
  python3 -c "
import asyncio, websockets
async def connect():
    async with websockets.connect('ws://localhost:$PORT/ws?token=$TOKEN') as sock:
        await sock.send('{\"cmd\": \"workspace_connect\", \"workspaceId\": \"$ws\"}')
        await asyncio.sleep(30)
asyncio.run(connect())
" &
done

# Wait for containers to start (poll docker)
echo "Waiting for containers to start..."
for i in $(seq 1 60); do
  COUNT=$(docker ps --filter "label=bark.managed=true" -q | wc -l)
  if [ "$COUNT" -ge "$NUM_WORKSPACES" ]; then
    echo "All $COUNT containers running after ${i}s"
    break
  fi
  echo "  $COUNT/$NUM_WORKSPACES containers after ${i}s"
  sleep 1
done

# Kill only the websocket clients, not uvicorn
WS_PIDS=()
for pid in $(jobs -p); do
  if [ "$pid" != "$PID" ]; then
    kill "$pid" 2>/dev/null || true
    WS_PIDS+=("$pid")
  fi
done
for pid in "${WS_PIDS[@]}"; do
  wait "$pid" 2>/dev/null || true
done

BEFORE=$(docker ps --filter "label=bark.managed=true" -q | wc -l)
echo "Containers before SIGTERM: $BEFORE"

echo "Sending SIGTERM to uvicorn (PID $PID)"
kill $PID

for i in $(seq 1 30); do
  if ! kill -0 $PID 2>/dev/null; then
    echo "Uvicorn exited after ${i}s"
    break
  fi
  sleep 1
done

AFTER=$(docker ps --filter "label=bark.managed=true" -q | wc -l)
echo "Containers after shutdown: $AFTER"

if [ "$AFTER" -eq 0 ]; then
  echo "PASS: all containers stopped"
else
  echo "FAIL: $AFTER containers still running"
  docker ps --filter "label=bark.managed=true" --format "{{.ID}} {{.Names}} {{.Status}}"
  exit 1
fi
