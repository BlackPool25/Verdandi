# What was fixed — issue by issue, and where to see it

Branch: m0b-t-build work. All 15 assigned Linear issues CLOSED 2026-11-25 with evidence comments; PR-time follow-ups drafted (not posted) for 66 + 74.

## See it live (dev stack: `docker compose --profile dev up api-dev web-dev`)

| Shot | File | What it proves |
|---|---|---|
| /sim overview | `01-sim-overview.png` | TopologyView + MachinePanel + StripChart + EventFeed streaming a real posted episode (seed 7, C2 breakdown) |
| Narration | `02-narration.png` | NarrationBar template ladder narrating the cascade (click-to-inspect) |
| Diagnosis card (decided) | `03-diagnosis-decided.png` | DiagnosisCard: what/where/severity/action + evidence chips (fixture: seed-777 breakdown A0, conf 0.94 ≥ τ 0.739) |
| Diagnosis card (abstain) | `04-diagnosis-abstain.png` | AbstainBanner: reason + packet + coverage instead of a guess (fixture: clean seed-777) |
| Dossier | `05-dossier.png` | DossierView disclosure (trace nodes + ranked paths, opened for the shot) |
| Anomalies / Metrics | `06-anomalies.png`, `07-metrics.png` | The other two viewer pages |

Note: the card/dossier shots use a dev-only `/demo/diagnosis` route (DEV-guarded, prod bundle untouched) fed by the committed vitest fixtures — in `/live` the loader stays default-off (null artifact renders nothing) until the packet-fetch wiring lands.

## Issue map (62–75; 61/65–71 per Task-1 scope doc)

- **66 Ship decision (abstain-gated)** — measured selective E2E **0.020** (8/400 @ acc 0.625) replaced derived 0.214; scope unchanged. Docs: REPORT §6, SHIP §3:62, DQ follow-up record. Visible: abstain banner + DiagnosisCard render reason/coverage/action, never a guess (`04`).
- **61 Calibration gate** — T=2.58 + Platt live, τ=0.739, VERIFY risk 0.044 exclude-held (n=8582); gate input-shape record (134 vs 138) + served-artifact verify. Visible: conf-gated decisions; `diagnose_incident` abstains `abstain_low_conf` below τ.
- **62 Tev decider — STRUCK** — canonical machine **0.113** (shuffle fixed-arm; Task-4 0.094 drift noted, robust) << 0.671; shuffled order identical (no position bias). Kept for phrasing only. Docs: 7 sites reconciled + drift lineage note.
- **74 v2 physics — SCOPED (flipped 2026-11-25)** — production-ambient rerun (naturals ON): ON 0.733 vs 0.694 BUT cf 0.117 > 0.093 → general claim fails; quality/loss-only win stands. Docs: SIM rerun table, SHIP:43 + sha pins, ARCH. Linear 74 needs the flip comment at PR time (drafted).
- **75 Splits + open-set retrain** — family-stratified episode-grouped CV + embargo NONE REQUIRED; exclude-held-5 retrain recorded (abstain ≈0.51 @ risk 0.413 over budget — forced-accuracy transfer not claimed).
- **63 Rerank — STRUCK** (0.667 → 0.665, both < 0.7); **64 paths — diagnostic-only** (teleport Δ+0, regen baseline 0.072/0.287/k1.8); mean-k typo fixed (1.1 → 1.8).
- **72 Faithfulness** — abstain pairing rule + claim_recall; recall top-up; NLI deferred (gated path, fail-closed).
- **65 Sensor — ABSTAIN BY DESIGN** (0.033–0.067 vs 0.4 bar, n=60). Visible: `abstain_sensor` in the card (`03` evidence chips).
- **67/68 Operator card + dossier** — DiagnosisCard/DossierView panels in /sim rail, T12 gates green, theme untouched (`03`, `05`; dossier is a `<details>` disclosure, opened for the shot).
- **69 Review-context audit** — void numbers (v1 0.963, PR#31) absent from ship docs (live only as labeled superseded refs); F13/F19 pins; PR#30 set empty.
- **70 Cost metric** — permanently deferred (accuracy-only bars stand).
- **71 Phrasing** — template-only fallback, verifier fail-closed (Ollama path gated).
- **73 E2E wiring** — `eval_e2e_selective.py` + artifacts; onset grid re-measured (global 0.8 locked p50 0/max 128; per-family p50 0/max 32).

## Wave hygiene (visible in tree, not on screen)

- Docs audit: 21 minors closed (detection bar ≤0.05, stale line pointers refreshed, pre-regen rows labeled, F19 sha pins restored on the v2 row, SOLVE_GAPS retired).
- Machine-readable summaries committed: `artifacts/tev_shuffle62.json`, `artifacts/onset_grid.json`.
- Docker: dev profile (`api-dev` :8000 + `web-dev` :19104, hot-reload) proven end-to-end through the containers; `docs/LOCAL_DOCKER.md` knob map.
- Still open: F5 delay-STARVED-mass assertion (lane active; excluded from merge until GREEN), PR-time Linear comments (66/74 drafts in `FINAL-lineardrafts.md`), merge itself (awaiting your order).
