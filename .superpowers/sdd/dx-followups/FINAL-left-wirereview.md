# FINAL-left-wirereview — `assert_delay_starved_mass` wiring into `src/diagnose.py:387` (READ-ONLY review, no code edits)

Worktree: `m0b-t-build`. No edits, no commits, no tests run, no Linear.
Sibling lane owns the wiring diff; this review covers the WIRING PLAN vs the contract,
plus the end-of-session diff check.

## 0. Diff status: NO DIFF at start AND end

- Session start: `git diff --stat src/diagnose.py` → empty.
- Session end: `git diff --stat src/diagnose.py` → empty; `git status --short src/diagnose.py` → clean.
- HEAD `9fd75f0` already carries the F5 assertion (`src/possibility.py:382-413`, 9/9 GREEN per FINAL-f5-review).
- So: **no spec-compliance / no-collateral-change diff review was possible. §6 records the checklist the diff must satisfy when it lands.**

## 1. Contract under review (pinned, not re-litigated)

- `tests/test_possibility.py:71-117`: 5 pins — `(4,6,2)→ok/visible`, `(2,9,2)→CONSERVATION`,
  `(6,1,2,shield=0)→VISIBILITY`, `(6,1,2,shield=6)→ok/shielded`, `(6,0,0)→ok/vacuous`.
- Impl `src/possibility.py:382-413`: `n==0→vacuous` first; `starved > injected*n → raise CONSERVATION`;
  `starved < injected-shield → raise VISIBILITY`; `shield>0 and starved<injected → shielded`; else `visible`.
  Strict `>`/`<`, **no `tol` parameter** (FINAL-f5-review §5.4: omission accepted for int pins only).
- Probe grounding (FINAL-probeassist): steps-to-steps with fan-out `n`; ep 41242 is the VISIBILITY specimen;
  `H=30` window inflates S; shield stays a parameter.

## 2. Placement ruling: candidate #1 (`src/diagnose.py:387`) — APPROVED with shape conditions

- `ranked = upstream_paths(evidence, edges, anchor)` is the correct trust point: it is where a decoupled
  delay (ep 41242 pattern) would otherwise promote a phantom path into `root`/`path`.
- Ordering is safe: `:387` sits **before** the calibration gate (`:400-406`) and **before**
  `store.create_incident` / `link_or_create` writes (`:417-426`), so an early-return abstain
  cannot persist a phantom incident — same precedent as `research-calibration.md:105` (gate after rank, before `build_report`).
- **Mandatory shape** (mirror the `:400-406` calibration-gate return, cf. `test_below_tau_abstains_via_reporter_path`
  which pins `root is None` + preserved `path`/`path_prob` for the dossier):
  early-return `{root: None, fault_family, path, path_prob, nodes: [], upstream: "", downstream: [], linked: [], abstain: <code>}`
  using `ranked[0]` for path preservation. **Never fall through to `build_report` (`:427`)** —
  `report.py:56` unconditionally sets `abstain` to `None`/`"single-node"`, which would silently discard the trip.

## 3. Abstain-code mapping ruling: converting AssertionError → existing code is REJECTED; new code REQUIRED

Existing reason-code enum (verified):
`silent-clean` → `abstain_sensor`; `low-confidence-calibrated` → `abstain_low_conf`;
`low-recall` → `abstain_paths`; `single-node` → `abstain_paths` (`scripts/report_incident.py:40-46`);
plus `abstain_reason()`'s `low-confidence`/`ambiguous-margin` (unused in `diagnose_incident`).

| Existing code | Reuse verdict | Reason |
|---|---|---|
| `low-confidence-calibrated` | **REJECT** | Means "conf < tau". A physics-conservation trip carries no conf/tau semantics; reuse would corrupt calibration-gate DQ accounting (selective-risk/coverage mix) and force either fabricated or missing `confidence{top1,tau}` fields that `test_below_tau…` pins for that code. |
| `low-recall` | **REJECT** | Means "evidence set empty after nb filter" (`:374-379`). Here evidence is non-empty but distrusted — opposite situation; reuse mislabels and breaks the DQ meaning of the 72-count `low-recall` bucket in the committed 233/72/87 abstain mix. |
| `silent-clean` | **REJECT** | Means "no onsets, never a guess" (`:346-352`). A mass-gate trip fires precisely when onsets DO exist. |
| `single-node` | **REJECT** | Owned by `report.py:56` path-formation rule, downstream of `:387`; unreachable as an early-return value and semantically unrelated. |

- **Correct mapping: a NEW distinct reason** (e.g. `decoupled-delay`, or `delay-visibility`/`delay-conservation` if the sibling wants the two legs distinguished in DQ).
  Downstream-safe, verified: `report_incident.py:247` falls back unknown reasons to `abstain_low_conf` scope;
  `eval_e2e_selective.py:140-143` buckets abstains dynamically by reason string; `run_report:231-237`
  emits an abstain packet with preserved paths on any non-None reason. No downstream code breaks on a new string.
- Interim allowance (only if the sibling is barred from adding a string): reuse is tolerated SOLELY as
  `low-recall` **plus** a `confidence`/note field recording the actual `CONSERVATION`/`VISIBILITY` message,
  with DQ disaggregation — graded CONDITIONAL, not clean.

## 4. Behavior risks beyond the single site (wiring-time, not impl-time)

- **R1 — Family gating (largest risk).** The assertion is meaningful only for `delay` faults.
  `diagnose_incident` receives `fault_family`; the wire MUST no-op for non-delay families (and for
  `fault_family="unknown"` unless the delay origin is positively identified). A family-blind wire would
  abstain breakdown episodes whose downstream STARVED comes from line stop, not delay mass —
  shifting the measured E2E coverage **0.020** and the committed 233/72/87 abstain histogram
  (`artifacts/e2e-selective-n200-s{0,1}.json`) without regen. Condition C1.
- **R2 — Feature derivation inputs don't exist at `:387`.** `evidence[r]` is only `{onset, score}`.
  `injected` (busy/delay steps at origin), `starved` (STARVED-step sum over downstream), `n_downstream`
  (topology BFS, cf. `_DOWNSTREAM_MACHINES`: C2→C6→C7 gives `n=2`; sinks give `n=0`), and
  `buffer_shield_steps` (pre-onset `buffer_C26+C67`-style cover) must be derived from `g`/columns that
  may be absent (synthetic frames in `test_calibration_gate`, 2-machine A0/B9 frames, telemetry frames).
  Missing columns must → skip-gate (treat as vacuous/pass), never `KeyError`, never trip on absent data. Condition C2.
- **R3 — Window boundedness.** Per FINAL-probeassist §3, `H=30`-style post-windows inflate S with recovery
  starvation (gate never trips → dead code) while too-tight windows undercount S (false trips).
  The window must be onset-anchored and documented, not baked into the assertion. Condition C3.
- **R4 — Float/tol.** Committed impl has strict inequalities and no `tol` (FINAL-f5-num H1/H3: latent wiring hazard).
  Throughput-derived floats fed directly will flake at boundaries. Wiring must quantize to integer steps
  before calling, or the impl gains `tol` (original-lane scope — flag, don't smuggle). Condition C4.
- **R5 — `except AssertionError` breadth.** The try/except must wrap ONLY the `assert_delay_starved_mass(...)`
  call, never the `upstream_paths(...)` call. Wrapping both converts genuine path-enumeration bugs into
  silent abstains and defeats the kill-bar invariant (`test_kill_bar_forced_top1`). Condition C5.
- **R6 — Double-violation ordering is fine** (conservation-first is deterministic; non-negative inputs can't
  trip both), but the two legs should remain distinguishable in logs/DQ (see §3 new-code ruling).
- **R7 — Scope limit (documented, not blocking).** Wiring `:387` guards serving (`diagnose_incident`) only;
  the offline tuning loop `scripts/eval_paths.py:137` (candidate #4) keeps measuring decoupled episodes.
  Acceptable if stated; do not claim the tuning signal is cleaned.
- **R8 — Store parity.** All early abstains leave no store row (W-minors Minor-3, deferred by design).
  The new abstain path extends that gap consistently — no action, just don't present it as fixed.
- **R9 — Existing pins.** `test_kill_bar_forced_top1`, `test_below_tau…`, `test_gate_obs_only`,
  `test_routes` (calls `upstream_paths` directly — untouched by a diagnose-side wire), and the e2e scripts
  are unaffected PROVIDED C1 (family gating) holds; the sibling must add its own wiring test (TDD, sibling scope).

## 5. Return-shape / downstream checklist for the wire (for §6)

Early-return dict must contain: `root None`, preserved `path`/`path_prob` from `ranked[0]`,
`nodes []`, `upstream ""`, `downstream []`, `linked []`, `abstain` = new code, and a `confidence`-carrying
or explicitly-absent convention consistent with `:400-406` (downstream readers use
`report.get("confidence") or {}` — both scripts are None-safe, but keep the convention explicit).

## 6. Diff review: PENDING (no diff landed)

When the sibling diff lands, accept iff ALL hold (else REJECT/CONDITIONAL):
1. Hunk confined to `diagnose_incident` around `:387` (additive try/except + early return; no signature change to `upstream_paths`/`rank_nodes`, no reordering of existing gates/writes).
2. Abstain code is NEW and distinct (per §3), or §3-interim-allowance fully satisfied.
3. Family gate present (C1); missing-column skip present (C2); bounded documented window (C3); int-step quantization or `tol` handling (C4); narrow except around the assert call only (C5).
4. Early return preserves `path`/`path_prob`, never falls through to `build_report` (§2).
5. New wiring test pins: delay-family VISIBILITY trip → abstain (ep-41242 pattern), non-delay family → unaffected,
   missing buffer columns → no trip, vacuous sink → no trip.
6. Full related suite green: `tests/test_possibility.py`, `tests/test_calibration_gate.py`,
   `tests/test_gate_obs_only.py`, `tests/test_pipeline.py`, `tests/test_eval_e2e_selective.py`
   (no committed-artifact invalidation; e2e numbers unchanged on non-delay families).

## Verdict: CONDITIONAL

- **Placement (candidate #1, `:387`): APPROVE** — correct trust point, safe pre-write ordering, correct precedent.
- **AssertionError → existing abstain code: REJECT** for all four existing codes (table §3); a **new distinct
  reason string is required** (downstream-verified safe).
- **Overall: CONDITIONAL** on C1 (delay-family gating), C2 (missing-column skip), C3 (bounded window),
  C4 (int steps/tol), C5 (narrow except), plus §6 items 1–6 on the eventual diff. No collateral behavior
  change is expected if C1–C5 hold; R1 violation alone would invalidate the committed 0.020 E2E lineage.
