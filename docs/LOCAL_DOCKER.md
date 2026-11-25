# Local Docker testing (compose)

## Run it

```bash
# from the repo root (this file's directory)

# Dev loop (hot-reload) — for testing the viewer yourself:
# (name the two services explicitly: a bare `up` would also start the prod api/web/db)
docker compose --profile dev up --build api-dev web-dev

# Prod shape (nginx + no reload) — what CI/shipping runs:
docker compose up --build
```

- Dev viewer: <http://localhost:19104/sim> (vite; edits to `src/`, `services/`, `frontend/src/` reload live)
- Dev bridge directly: <http://localhost:8000/health> (also `/schema`, `POST /episode`, `/stream`)
- Prod viewer: <http://localhost:19104/sim> (host port = `WEB_PORT`, container nginx :80)
- Stop: `docker compose --profile dev stop api-dev web-dev` (or `down` to remove). Rebuild after dependency changes: `--build`.

## What to test (the chat)

The "chat" surface is the narration + diagnosis flow in `/sim`:

1. Open `/sim`, draft a fault (seed + fault class/origin/t0/dur) and post the episode — this hits `POST /episode`.
2. Watch the tick stream (`/stream`, SSE) drive TopologyView, MachinePanel, StripChart, EventFeed.
3. NarrationBar (bottom bar) narrates the cascade from the template ladder — click it to inspect.
4. DiagnosisCard: paste a packet JSON into the card panel → what/where/severity/action + evidence chips wired to `onSelect`/`onStepTo`.
5. T12 gates stay green in-container: `docker compose --profile dev exec web-dev npm run gates` and `docker compose --profile dev exec -e PYTHONPATH=/app api-dev python -m pytest tests/test_report_incident.py -q -p no:cacheprovider`.

## Where the values change (knobs)

| You want to change | Where | How |
|---|---|---|
| Web dev port (19104) | `compose.yaml` `web-dev.ports` | `WEB_PORT=19105 docker compose --profile dev up`, or a local `.env` file with `WEB_PORT=19105` |
| API dev port (8000) | `compose.yaml` `api-dev.ports` | `API_PORT=8001 ...` — the vite proxy follows `VITE_BRIDGE_URL`, so no other file changes |
| Which bridge the dev UI talks to | `VITE_BRIDGE_URL` env, or per-page `?bridge=` query param | compose default is `http://api-dev:8000`; override: `VITE_BRIDGE_URL=http://localhost:8001`; browser-only: `/sim?bridge=http://host:port` (no rebuild — vite reads it at dev-server start; nginx-prod always uses same-origin) |
| Prod web host port | `compose.yaml` `web.ports` | `WEB_PORT=8080 docker compose up` (container stays :80) |
| Fault/seed/naturals per episode | in the `/sim` UI form, or `POST /episode` body (`seed`, `faults[]`, `enable_natural_breakdown`) | runtime values, not config — no compose change |
| Python deps for the bridge | `requirements.txt` + `services/sim_bridge/requirements.txt` | edit, then `--build` (image layer rebuild) |
| Node deps for the viewer | `frontend/package.json` | edit, then `--build` |
| Running pytest inside api-dev | exec with repo on path | `docker compose --profile dev exec -e PYTHONPATH=/app api-dev python -m pytest <test> -q -p no:cacheprovider` (repo root is `/app`; code mounts keep it current) |

Notes:

- The bridge precomputes episodes server-side from `src/` — no data volume needed for this loop. The `verdandi-artifacts` volume (prod `api`) and postgres (`db`) serve full-fidelity replay/live store; the dev profile skips both (sqlite-hermetic default).
- LLM paths (Tev `tev1:4b` via Ollama, phrasing templates) are host-side eval tooling, not part of this stack — the served viewer uses the template ladder, never live LLM calls.
