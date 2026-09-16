#!/usr/bin/env bash
# T11 end-to-end demo: bridge up -> seed 777 F-21 (drift@B2 t0=150 dur=12
# mag 5.2, topology-A schema v2) -> open /sim -> autoplay 1x -> pause at t=160 -> step ->
# screenshot. Idempotent: reuses healthy servers, else restarts own.
# Logs to .omo/evidence/task-11-verdandi-pixel-twin-frontend.log, video to
# .omo/evidence/task-11-verdandi-pixel-twin-frontend.webm.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND="$REPO/frontend"
EVIDENCE="$REPO/.omo/evidence"
LOG="$EVIDENCE/task-11-verdandi-pixel-twin-frontend.log"
WEBM="$EVIDENCE/task-11-verdandi-pixel-twin-frontend.webm"
PNG="$EVIDENCE/task-11-verdandi-pixel-twin-frontend.png"
BRIDGE="http://127.0.0.1:8000"
WEB="http://localhost:19106"
VIDEO_DIR="/tmp/t11-video"
BRIDGE_PID=""; WEB_PID=""

mkdir -p "$REPO/demo" "$EVIDENCE"
: > "$LOG"

log() { echo "$*" | tee -a "$LOG"; }
fail() { log "FAIL: $*"; exit 1; }

cleanup() {
  [ -n "$WEB_PID" ] && kill "$WEB_PID" 2>/dev/null || true
  [ -n "$BRIDGE_PID" ] && kill "$BRIDGE_PID" 2>/dev/null || true
}
trap cleanup EXIT

is_up() { curl -s -m 3 -o /dev/null "$1"; }

# --- bridge ---------------------------------------------------------------
if is_up "$BRIDGE/health"; then
  log "bridge: reusing healthy $BRIDGE"
else
  log "bridge: starting uvicorn :8000"
  (cd "$REPO" && python3 -m uvicorn services.sim_bridge.app:app \
    --host 127.0.0.1 --port 8000 >>"$LOG" 2>&1 & echo $! > /tmp/t11-bridge.pid)
  BRIDGE_PID="$(cat /tmp/t11-bridge.pid)"
  for _ in $(seq 1 60); do is_up "$BRIDGE/health" && break; sleep 1; done
  is_up "$BRIDGE/health" || fail "bridge is down and could not be started. ACTION: run 'pip install -r services/sim_bridge/requirements.txt' then 'python3 -m uvicorn services.sim_bridge.app:app --host 127.0.0.1 --port 8000' and re-run demo/frontend.sh (no stack trace: the bridge process never became healthy)."
  log "bridge: up (pid $BRIDGE_PID)"
fi

# --- seed 777 F-21, digest must match the check_replay FAULT ----------------
SEED_RESP="$(curl -s -m 10 -X POST "$BRIDGE/episode" -H 'content-type: application/json' \
  -d '{"seed":777,"faults":{"id":"F-21","class":"drift","origin":"B2","t0":150,"dur":12,"mag_sigma":5.2}}')" \
  || fail "POST /episode failed. ACTION: confirm the bridge is healthy at $BRIDGE/health, then re-run demo/frontend.sh."
EP_ID="$(echo "$SEED_RESP" | python3 -c 'import json,sys; print(json.load(sys.stdin)["episode_id"])')" \
  || fail "POST /episode returned non-JSON. ACTION: restart the bridge and re-run demo/frontend.sh."
DIGEST="$(echo "$SEED_RESP" | python3 -c 'import json,sys; print(json.load(sys.stdin)["replay_digest"])')"
log "seed-777 F-21 episode=$EP_ID digest=$DIGEST"
[ "$DIGEST" = "523b0b9e71f47d355cf4e4f4b7f73d29c333747d253d3b016c1edf2957bbd8c4" ] \
  || fail "digest mismatch for seed 777 F-21 (want 523b0b9e71f47d.., got $DIGEST). ACTION: run 'python3 services/sim_bridge/scripts/check_replay.py --seed 777' and fix the twin/bridge before re-running."
log "digest matches check_replay FAULT"

# --- vite ------------------------------------------------------------------
if curl -s -m 3 -o /dev/null "$WEB/sim"; then
  log "web: reusing healthy $WEB"
else
  log "web: starting vite :19106"
  (cd "$FRONTEND" && node node_modules/vite/bin/vite.js \
    --port 19106 --strictPort >>"$LOG" 2>&1 & echo $! > /tmp/t11-web.pid)
  WEB_PID="$(cat /tmp/t11-web.pid)"
  for _ in $(seq 1 120); do curl -s -m 3 -o /dev/null "$WEB/sim" && break; sleep 1; done
  curl -s -m 3 -o /dev/null "$WEB/sim" || fail "vite is down and could not be started. ACTION: run 'npm install' in frontend/, then re-run demo/frontend.sh."
  log "web: up (pid $WEB_PID)"
fi

# --- tour (autoplay -> pause@160 -> step -> screenshot) ----------------------
rm -rf "$VIDEO_DIR"; mkdir -p "$VIDEO_DIR"
log "tour: starting"
(cd "$FRONTEND" && T11_WEB="$WEB" T11_PNG="$PNG" T11_VIDEO_DIR="$VIDEO_DIR" \
  node ../demo/frontend-tour.mjs 2>&1 | tee -a "$LOG") || fail "browser tour failed (see above). ACTION: confirm bridge $BRIDGE/health and web $WEB/sim are reachable, then re-run demo/frontend.sh."
VID_SRC="$(ls "$VIDEO_DIR"/*.webm 2>/dev/null | head -1 || true)"
[ -n "$VID_SRC" ] || fail "no tour video recorded. ACTION: re-run demo/frontend.sh; if it persists, run playwright with --debug against $WEB/sim."
mv "$VID_SRC" "$WEBM"
log "video=$WEBM screenshot=$PNG"

# --- failure probe: kill bridge -> banner; restart -> resume ------------------
PROBE_JS='import { chromium, expect } from "@playwright/test"; const b = await chromium.launch(); const p = await b.newPage(); await p.goto(process.env.T11_WEB + "/sim?seed=777"); '
if [ -n "$BRIDGE_PID" ]; then
  kill "$BRIDGE_PID" 2>/dev/null || true; BRIDGE_PID=""
  for _ in $(seq 1 30); do is_up "$BRIDGE/health" || break; sleep 1; done
  (cd "$FRONTEND" && T11_WEB="$WEB" node --input-type=module -e "$PROBE_JS"'await p.getByTestId("disconnected-banner").waitFor({ timeout: 30000 }); console.log("probe: banner visible while bridge down"); console.log("probe: topology intact=" + (await p.getByTestId("topology").count())); await b.close();' 2>&1 | tee -a "$LOG") \
    || fail "banner did not appear while bridge is down. ACTION: check tickSource connected derivation, then re-run."
  (cd "$REPO" && python3 -m uvicorn services.sim_bridge.app:app --host 127.0.0.1 --port 8000 >>"$LOG" 2>&1 & echo $! > /tmp/t11-bridge.pid)
  BRIDGE_PID="$(cat /tmp/t11-bridge.pid)"
  for _ in $(seq 1 60); do is_up "$BRIDGE/health" && break; sleep 1; done
  (cd "$FRONTEND" && T11_WEB="$WEB" node --input-type=module -e "$PROBE_JS"'await p.getByTestId("buffer-level-SBUF").waitFor({ timeout: 60000 }); await p.waitForTimeout(3000); console.log("probe: banner after resume=" + (await p.getByTestId("disconnected-banner").count())); console.log("probe: rows=" + (await p.getByTestId("row-count").textContent())); await b.close();' 2>&1 | tee -a "$LOG") \
    || fail "page did not resume after bridge restart. ACTION: check stream resume (?from_step) then re-run."
  log "probe: banner + resume OK"
else
  log "probe: skipped (bridge reused, not owned by this run)"
fi

# --- single-EventSource assertion (SimPage path) ------------------------------
test ! -f "$FRONTEND/src/sim/panelFeed.ts" || fail "panelFeed.ts still exists (unification incomplete)."
ES_COUNT="$(grep -rn "new EventSource" "$FRONTEND/src" | wc -l)"
log "eventsource-sites=$ES_COUNT (tickSource + controls/api + events/standalone)"
[ "$ES_COUNT" -eq 3 ] || fail "expected 3 EventSource sites, found $ES_COUNT."

log "DEMO-PASS"
