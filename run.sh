#!/usr/bin/env bash
# Verdandi Twin — one-command local run: sim bridge + frontend viewer.
# Usage: ./run.sh [--seed 777] [--port 19104] [--no-browser]
# Open:  http://localhost:19104/sim?seed=777
# Stop:  Ctrl-C (both servers shut down).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEED=777
PORT=19104
BROWSER=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --seed) SEED="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --no-browser) BROWSER=0; shift ;;
    --help|-h) sed -n '2,6p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1 (see --help)"; exit 1 ;;
  esac
done

command -v python3 >/dev/null || { echo "need python3"; exit 1; }
command -v npm >/dev/null || { echo "need npm"; exit 1; }
python3 -c "import uvicorn, fastapi, simpy" 2>/dev/null || {
  echo "install backend deps first: pip install -r requirements.txt -r services/sim_bridge/requirements.txt"
  exit 1
}
[[ -d "$REPO_ROOT/frontend/node_modules" ]] || { echo "run first: cd frontend && npm install"; exit 1; }

cleanup() { kill "$BRIDGE_PID" "$WEB_PID" 2>/dev/null; }
trap cleanup EXIT

cd "$REPO_ROOT"
python3 -m uvicorn services.sim_bridge.app:app --host 127.0.0.1 --port 8000 &>/tmp/verdandi-bridge.log &
BRIDGE_PID=$!
for _ in $(seq 1 60); do curl -sf http://127.0.0.1:8000/health >/dev/null && break; sleep 0.5; done
curl -sf http://127.0.0.1:8000/health >/dev/null || { echo "bridge failed to start (see /tmp/verdandi-bridge.log)"; exit 1; }
echo "bridge  -> http://127.0.0.1:8000/health"

cd "$REPO_ROOT/frontend"
npm run dev -- --port "$PORT" --strictPort &>/tmp/verdandi-web.log &
WEB_PID=$!
for _ in $(seq 1 60); do curl -sf "http://localhost:$PORT/" >/dev/null && break; sleep 0.5; done
echo "viewer  -> http://localhost:$PORT/sim?seed=$SEED"

URL="http://localhost:$PORT/sim?seed=$SEED"
[[ "$BROWSER" == 1 ]] && (command -v xdg-open >/dev/null && xdg-open "$URL" >/dev/null 2>&1 || echo "open: $URL")
echo "Press Ctrl-C to stop."
wait
