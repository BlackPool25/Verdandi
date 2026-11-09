# Diagnosis flow (agreed) — Verdandi manufacturing twin

Source of truth for the diagnosis layer. Status: agreed design; implementation in progress on `m0b-t-build`.
Frozen: detector v7 (`artifacts/window-gain-w128-v7`), twin dynamics, `docs/m0b_mass_manifest.json`.
Never touch main repo. Conventional commits, small diffs. TDD: failing test first. Full suite green.

## 1. Goal + bars (standing)

- Attribution top-1 ≥ 0.5 pooled, sensor ≥ 0.4; onset median error ≤ 25 ticks; no family regression > 2 pts; transfer gap always reported (5 held-out machines ASM1/ASM2/B7P/B9/C6, currently 0.40 top-1).
- Abstain scored separately from misattribution. Same-battery comparisons only (T=300 vs supplement T=1000 never mixed).
- Numbers labeled MEASURED / ASSUMED / DERIVED with lineage.

## 2. End-to-end flow

```
detect (frozen v7, 2-of-3 confirm → anchor)
  → changed set (PELT + state/counter onsets)
  → candidates = BFS radius-2 BOTH dirs from changed ∪ {anchor} (2–5 nodes, fallback full 26)
  → node scores (Head-A ranker: LambdaRank open-set; RBC veto = sensor specialist)
  → path DP: best root→anchor path ≤ 3 nodes, geomean of node scores, uniform edges (data weights later)
  → twin-fork forecast: fault-branch vs clean-branch from t_det forward H → predicted cascade + hit ticks
  → incident store link-or-create (postgres docker; sqlite hermetic for tests)
  → report: root + p(path), onset, fault_family, per-node table, upstream cause, downstream predicted-vs-actual, linked thread
```

## 3. Detection (done, frozen)

- Window-GBM sklearn HistGBM, 23 invariant feats, GroupKFold. Tuned window-F1 0.89, hit 0.92, clean-FP 0.01.
- Per-rung: caricature (4–7σ) thr 0.544 F1 0.940 SHIPS; incipient (1–3σ) thr 0.315 F1 0.802 detection-only + fleet index. Per-family recalls in `docs/OPERATING_POINTS.md`.
- Trigger fires median 142 ticks pre-fault (left-overlap, recall-first). 56/60 top-1 are texture-onset STARVED machines — anchor is often a downstream victim, not the root. This is why pure upstream-1-2 pruning is unsafe (see §4).

## 4. Candidates: topology-constrained, both directions

- Twin DAG (`src/twin.py:1672-1692`): chains A0→…→A9→ASM0, B0→…→B9→ASM0 with B2→{B7P,B7S}→B8 fork, C0→…→C7→{PKG0,ASM0}, PKG0→PKG1/PKG2, ASM0→ASM1→INSP0→ASM2→RWK0→C0 loop.
- Propagation is bidirectional: downstream STARVATION/routing, upstream BLOCKAGE (`compute_hop` BFS both dirs, `src/twin.py:1695-1721`).
- Rule: candidates = radius-2 both-dirs closure around trigger + changed set (`src/possibility.py:neighborhood`, `radius=2`, conditional 1-hop expansion through changed nodes). Typical size 2–5 vs 26.
- Why not upstream-only: blockage goes up, starvation goes down; fork branches (B7P vs B7S) and the ASM→RWK0→C0 loop escape a 1–2 upstream window; sensor faults are local (single-node path). Upstream-only prunes true roots when anchor is a STARVED victim.
- Guardrails: measure prune recall P(true root ∈ set); kill prune if < 0.95. Fallback: full-26 scoring + `abstain-low-recall` flag when constrained set is empty.
- Literature: ST-GraphRCA topology reachability mask (F1 0.89, https://www.mdpi.com/1424-8220/26/5/1474); OpenRCA 2.0 PAVE path enumeration (https://arxiv.org/html/2606.27154v2) — both prune by reachability then score full paths, not depth-1-2 only.

## 5. Node scoring (Head-A, identity allowed; detector stays quarantined)

- Open-set per-(episode,machine) ranker, never a 26-way classifier (classifier `classes_` can never emit unseen machines — structural trap, verified; vacuous `--cv machine` path removed).
- Features per candidate row: frozen deviation for that machine, within-episode rank + z (comparative, not absolute), train-fold prior rate, modality flags, `machine-id` one-hot/target backoff (attribution-only), episode context (severity, fault_family).
- Model: LightGBM `LGBMRanker objective=lambdarank`, `lambdarank_truncation_level` 5–10 (default 20 wastes budget at K≈3–5), `lambdarank_norm=True`, `eval_at=[1,2,3]`; start `num_leaves {7,15,31}`, `min_data_in_leaf {5,10,20}`, GroupKFold by episode-family; metrics top-1 (=NDCG@1) + MRR + NDCG@3 + bootstrap CI. Rank scores uncalibrated (translation-invariant) → abstain on margin `m=s1−s2`.
- Lineage: Burges 2006 intranet 400 queries × 59.4 docs worked (MEASURED); our scale DERIVED 340×26=8,840 rows, 25:1 in-query imbalance.
- Specialists: PROCESS order re-ranker (first-k tuple + pairwise precedence + template agreement, stage-2 re-rank only — Javanbakht 2022 test 0.96 k=20/v=5, https://arxiv.org/html/2203.11321v1); SENSOR RBC veto (§6). Bar/kill: pass pooled ≥ 0.50 + sensor ≥ 0.40; kill if pooled < 0.45 or no beat vs 0.562 pooled.

## 6. Sensor veto (RBC, not projection)

- Killed gates measured raw alignment `|r·ξ|` / Mahalanobis on coupled-state residuals: dominance flat 0.45–0.50, argmax 1–3/24. Twin couples everything through state offsets — pure smearing (Westerhuis/Qin consensus).
- RBC measures counterfactual index reduction: `RBC_i = (ξiᵀMx)² / (ξiᵀMξi)`, `M_SPE=C̃=P̃P̃ᵀ`, `M_T2=PΛ⁻¹Pᵀ` (verified ACC'11 survey §II). Substrate = sensor-level PCA (healthy sensors), not coupled state. Guarantee: correct single-sensor isolation in large-fault limit (Alcala & Qin 2009); Weng 2024 RB ≈ 90%+ vs PCA FDR < 40% (MEASURED, fetched).
- Veto: confirm sensor only if top-1 RBC share ≥ τ (sweep 0.3/0.5) stable ≥ k samples, else ABSTAIN. Bar sensor ≥ 0.40, process regression ≤ 2 pts; else drop veto (twin coupling is binding).

## 7. Path DP (causal trace = path, not single node)

- `best_path(scores, edges, anchor, max_len=3)` (`src/possibility.py`): DFS backwards over reverse DAG, paths ≤ 3 nodes ending at anchor; path score = geometric mean of node possibilities (length-comparable); prob = score / Σ scores. Uniform edge weights now; TE/data weights only if path underfits (lag-flow walk 0.056 killed — symmetric untested correlation; LSTE needs directed+conditioned+tested weights).
- RWR/PPR generalizes this DP (eIRWR 2026, https://arxiv.org/html/2608.08073v1; MicroRCA Wu 2020): propagate anomaly evidence with restart at changed nodes; our DP-≤3 is RWR depth-capped. Keep DP now, lift cap later without redesign.

## 8. Downstream forecast (twin fork, not ML prediction)

- At confirm tick `t_det` with diagnosed `{root, fault_family, t0_est}`: run TWO separate `run_episode` calls (same seed): fault-branch (diagnosed fault) + clean-branch (`fault=None`). No snapshot API exists — full re-runs sliced to `[t_det, t_det+H]`, H=150 default.
- Leakage rule: branch inputs = prefix + diagnosed fault only, never the GT future record. Sim == truth today, so the API boundary (prefix+diagnosis in, future out) is what keeps it honest when twin ≠ truth later.
- Predicted-affected = nodes with `state ∈ {STARVED,BLOCKED,DOWN}` (or obs-deviation > kσ) in fault-branch but clean in clean-branch; first-hit tick each, ordered = predicted cascade; `hop_est` via `compute_hop(root,·,≤3)`.
- What-if (future reroute work): same fork with `extra={reroute:…}` or fault truncated at `t_fix`; affected-set shrink = quantified benefit. Supplement-only `extra` flags, frozen dynamics untouched.
- Reroute action set is plant policy — out of scope for this layer.

## 9. Incident store + linking (dedup downstream fires)

- DB verdict (searxng-researched): **plain Postgres (`postgres:16-alpine` docker service `db`)** for live; **stdlib sqlite** for tests (hermetic, no docker in CI).
  - Why not Timescale/Influx/QuestDB/Prometheus: workload is relational (FK incidents→symptoms→predictions, time-window + reachability joins, transactional status updates, few hundred rows/episode) — vanilla Postgres wins on simplicity + same SQL; Timescale is an upgrade path (same dialect, hypertables) only if per-tick obs moves into the DB (billions of rows). Telemetry-first stores have weak FKs/updates. SQLite single-writer lock storms under replay load — server DB for live.
  - Code `src/incidents_store.py`: DB-API, `memory()` (sqlite `:memory:`) vs `from_env()` (`DATABASE_URL` → `psycopg`, else sqlite file). Dependency: add `psycopg[binary]` to requirements (currently absent — sqlite only).
- Schema (3 tables): `incidents(id, root_machine, fault_family, t0_est, seed, status, created_at)`; `predicted_cascade(incident_id→incidents, machine, pred_tick, hop_est)`; `symptoms(id, incident_id→incidents, machine, onset_tick, own_state, pred_hit, linked_at)`.
- Link rule on each new confirm at `(m, t)`: find open incidents same seed with `compute_hop(root,m,≤3)` reachable AND `m ∈ predicted` (if predictions exist) AND `t ∈ [t0_est, t0_est+H+slack]` (slack 25). Hit → insert symptom `linked`, suppress new incident (standard dedup + correlate: identical collapses, causal links even when metrics differ). Miss → new incident + its own forecast branch.
- Compose: add `db` service + volume to `compose.yaml` (api/web exist; no db today).

## 10. Report (per incident, the deliverable)

```
root_machine + p(path) | fault_family | rung | t0_est | onset_tick
path: [root → … → anchor] (each with hop_est, pred_hit_tick, actual_tick|pending)
per-node table: machine | onset | onset_kind | own_state | top-3 metric Δ/σ with values | hop_est | pred_tick vs actual
upstream cause (1 line) + downstream impact (predicted list with pred_hit flags)
linked thread: all symptom fires attached to this incident
abstain flag + reason (low-recall fallback | thin margin | empty set)
```

## 11. Rigor rules (non-negotiable)

- TDD every behavior; frozen manifests + frozen twin; same-battery comparisons; GT columns (`root_id`, `t0`) eval-only except Head-A train inputs; attribution trains ungated, serves gated.
- Detector quarantine: detector scripts never import identity lane (`test_finalize_model` pins 23 invariant feats).
- No `torch` outside `src/roi_head.py` (LightGBM CPU ok). No banned dict keys in new src: use `fault_family`, `coord_class`/`sensor_verdict`, `hop_est` (never `family`, `sensor_vs_process`, `hop`).
- Worker-pool initarg order bug: always run slice tests with n-jobs>1 after touching worker plumbing.

## 12. Killed (do not retry without new evidence)

Naive obs argmax 0.12; coordination-count 0.372; mean-fusion 0.67; gated combiner 0.63; torch ROI ×2 (LOMO 0.0); lag-flow 0.056; invariant-feat ties pruned; CUSUM/EWMA/SR; naive + whitened directional gates; strength-weighted 0.0; rung-aware confirm; delay comp 0.542; score-gated onsets 0.991 vs 0.996; CROPS clutter-only; oracle-onset 0.0 (proximity buries GT); variation 0.11/0.22; closed-set transfer eval (structural 0.000 trap).

## 13. Implementation status (this branch)

- DONE: `best_path` + tests (`tests/test_cascade_path.py`, `src/possibility.py`); `IncidentStore` + link tests (`tests/test_incident_link.py`, `src/incidents_store.py`, sqlite backend).
- NEXT: `src/forecast.py` `predict_cascade` (test `tests/test_forecast.py` written RED, implementation pending) → compose `db` service + `psycopg` dep → report builder → prune-recall measurement → LambdaRank Head-A harness.
