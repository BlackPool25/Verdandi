# RQ3 Stress Spike Report — template+verifier narration pipe (K3 fires-or-survives)

Harness: `spike/rq3_spike.py` (asyncio.Semaphore/gather/wait_for + psutil.Process.memory_info().rss + tracemalloc).
Docs: `/giampaolo/psutil`, `/python/cpython` via context7. Raw: `spike/trace_rq3.jsonl`.
Design under test: ADR-0004 — every sentence must carry a resolvable triple
(fault-window FW-xxx, edge-id E-Mxx->Mxx, detector-output DET-q95-mxx); K3: >5% sans valid triple → chain-cards.
Caps: 2,500 tokens / $0.005 (caps 200k / $0.50); iters ≤10k. Wall-clock ~5s total.

| Vector | Result | Gate | Verdict |
|---|---|---|---|
| V1 concurrency 50 coroutines | 100 sents, grounded 1.00 | ≥0.95 | PASS |
| V2 RSS 1k→5k→10k iters | 23.81→23.81MB, growth 0.0%, py-peak 41.6KB | >5%→KILL | PASS (no leak) |
| V3 jitter+429+drops, 8s deadline | 30/30 served, 20 fallbacks, 0.39s | 100% served | PASS |
| V4 boundary corpus (7) | 5 hostile rejected, 0 ungrounded pass, 0 egress | 100% safe | PASS |
| V5 10x saturation (50→200→500) | grounded 1.0 at all points, shed richness at ingress 500 | shed richness, never provenance | PASS |
| V6 mutation inversion | base 1.0, corrupt 0.0, inverted-verifier 1.0 (diverges → non-vacuous) | harness must fail | PASS |

Notes: V2 memory loop uses local template (zero LLM tokens; USD cap applies to metered narration only).
V4 corpus: null-bytes, 10MB payload, truncated JSON, 2× prompt-injection+layout — all rejected; 2 benign accepted and grounded.
V5 sheds MTTR-richness adjectives first; triple preserved at every load point; no OOM observed.
V6 proves gates are live: corrupted provenance scores 0.0 (would fire K3), flipped verifier disagrees with honest one.

## RSS verdict: FEASIBLE

K3 survives: template+verifier holds 100% grounded (bar ≥95%) under concurrency, faults, hostile input, and 10× load;
chain-cards fallback serves 100% of timed-out/error calls; mutation gate confirms the spike is not vacuous.
Saved-cost note (for DECISIONS.md): local-template spike burned $0.005 vs $47K-loop class failure the per-run
token/USD/iteration caps exist to prevent — caps enforced in-harness, zero overrun. No Tier-5 claims; production untouched.
