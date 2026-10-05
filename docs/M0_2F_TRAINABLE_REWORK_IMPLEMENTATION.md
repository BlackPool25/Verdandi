# M0.2f Trainable Rework — Implementation Spec (for implementation agent)

> Scope: fix PR #16 (`pr16-m0-2f-gowtham`, MINIPRO-29 / PRISSUE-29) so fallback retains anomalies, export is supervised-trainable, quality is kept but isolated, and CI brutally gates anomaly quality for next stages (MINIPRO-19 training pipeline, MINIPRO-10 battery).
> Decisions LOCKED by owner (2026-10-05): (1) Fallback = `B=null + prefix/RMQ cover`, (2) Labels = per-step `y` + purge, (3) Heads = 3 split heads, (4) Balance = weights-first + budgets, (5) Norm/splits/cal = M-first + StratifiedGroupKFold + 3-arm.
> Normative parents: `docs/M0_2F_FALLBACK_AUDIT.md`, training-preprocessing-spec §3–§5, upgrade-spec §5, `docs/M0_2F_COORDINATION.md`.
> Twin truth: T=300, CAL_WIN=120, WARMUP=15, 26 machines, 36-stream SeedSequence, `config.TWIN_SCHEMA=4` → bump to **5** in this change.

---

## 1. Brutal review of PR #16 HEAD (`6cc2ec4`) — what is wrong, file:line

Source reviewed: `git show pr16-m0-2f-gowtham:src/window_export.py` (643 lines), `tests/test_window_export.py` (863 lines), diff to `main` = only those + guard loosening. No changes to `twin.py / config.py / dataset_export.py`.

### 1.1 `derive_base_window()` is a stub that always returns UNRESOLVED (P0 defect)
- Lines 116–159: ignores `calibration` content entirely (only reads shape). Docstring at lines 13–23 claims authoritative path `detrend → AC → DFT → agreement → median` — **none of it is implemented**. `_compute_scale_lengths()` (line 162) is dead code, never called.
- PR description claims "Resolved path: 0.5B/B/2B" — false on current code; every run takes fallback.
- `run_calibration()` exists on main (`twin.py:2142`, returns `(105,26)` clean obs) but result is discarded.

### 1.2 Fallback `q=25 → 25/50/100` fabricates physics (audit: NOT DEFENSIBLE)
- Lines 73–80, 107–113: `q=25` constant with comment "ENGINEERING FALLBACK CHOICE" — no derivation from N, no sensitivity report.
- N confusion unresolved: audit assumes N=105 (steps 15..120), twin T=300, PR windows applied to full 300-step episodes. At T=300: w=100 → 201 stride-1 positions; w=25 → 276. Fault `dur` 8–25 (config.FAULT_RANGES) → w=100 dilutes a 1-sample pulse by ~1/√100 and a 12-step drift by ~3×. Matched-filter violation (audit §2): one N-only triple cannot serve L=1 and L≫1 simultaneously.
- No `B_i`, no `scale_status` at top level; `scale_status="unresolved_fallback"` only inside `m0_2f` section (line 523). No `B_i=null` contract, no deferred-selection path.

### 1.3 Window-local Hilbert envelope is unreconstructible (audit Case B — must not ship)
- Lines 200–266 `envelope_features()`: `hilbert(x)` + `rfft` **recomputed inside each window**. Finite-window Hilbert (FFT bins, leakage, edge transients) + filter state differ per window → `E_whole ≠ concat(E_blocks)`. Audit §6: NOT DEFENSIBLE.
- Band `0.1fs–0.5fs` at fs=1 with w=25 → rfftfreq resolution 1/25=0.04 Hz, ~10 bins in band; w=100 → 0.01 Hz, ~40 bins. Band-energy ratios are **not comparable across scales**.
- `s(t)=(e-mean)² → |FFT|²` ratio is ad-hoc; no `envelope_definition_id+version`, no GES2N pin, no global-`p[t]` prefix. Raw-waveform matching prohibited (§9.1) but nothing enforces it.
- Cost: `hilbert` per window ≈ 26 ch × (276+251+201)=728 windows/episode ≈ **18.9k FFTs/episode** — blows the +4% wall budget (upgrade-spec §8).

### 1.4 Zero trainable anomaly signal in the artifact
- `export_multiscale()` (329–433) + `run_m0_2f_export()` (559–643): calls `run_episode(seed, None)` — **clean episode only**. `window_features.parquet` contains zero fault windows. Anomaly retention = 0 by construction.
- Row schema (315–324): `channel, scale, window_len, t_start, t_end, mean, rms, min, max, envelope_*` + `episode_id_ref`. **Missing**: per-step `y`, fault/GT mask, `warmup_flag`, SHF/DOWN flags, `family/mode/root_id`, state/buffer/event/part-flag columns. `episode_id_ref` deliberately dodges M0.2e `episode_id` ownership → breaks zero-join grouped-CV contract (can't group by episode).
- Single-head obs-only: `rolling_features_for_channel()` takes 1-D obs. Empirically probed on seed 777 (fault t0=150 dur=12 mag=5σ): spike 5.0σ ✓, drift 2.71σ ramp ✓, bias 5.0σ ✓, **delay 0.0σ, loss 0.09σ mean / 0.58σ max, breakdown state-only DOWN, quality part-flag only**. Obs mean/RMS over fixed windows **cannot** retain delay/loss/breakdown/quality — they live in dwell/stale-hold/state-histogram/part-flag space (§1.6 below).
- `export_multiscale()` overwrites `window_features.parquet` per call (no append/multi-episode), no sha256/size-cap/row-group hardening (`pq.write_table` bare, cf. dataset_export hardened writer v2.6/snappy/no-dict).
- `detrend_signal()` (scipy) imported but never used in pipeline — dead code + extra dep in hot path.

### 1.5 Tests (863 lines) assert the wrong things
- Cover: hand aggregates, sine-envelope ≈A, zero-energy safe 0.0, fallback counts, stride-1, no-pad, determinism, boundary, v3 regression, no-scaler. **Missing entirely**: reconstruction property (all `(s,w)` allclose), float non-identity, RMS-needs-sumsq, envelope-A/B (global passes / window-local must FAIL), no-fabrication (`B_i is null`), per-class anomaly-retention (fault-vs-clean separation per family), leakage (episode-recovery ≤ chance+2pp), pooled-B validation. A suite that passes while shipping zero anomalies is vacuous.
- No pytest marks (`k1..k5/battery/adversarial/mutation`): CI `battery` job (`-m "k1 or k2 or k3 or k4 or k5 or battery"`) **never collects** the PR tests. Quality gate blind to M0.2f.
- Guard gap: `M0_2F_OWNED_FIELDS` lacks `envelope_band_energy, episode_id_ref, t_start, t_end, mean, rms` — new writers bypass the guard.

### 1.6 Per-class trainability on main today (probed seed 777, origin A2/ASM2)
| class | fault-window obs shift | trainability now | reason |
|---|---|---|---|
| spike | 5.0σ | 7/10 | strong but no y/windows |
| drift | 2.71σ mean, 5.0σ max (ramp) | 6/10 | fixed w dilutes ramp |
| bias | 5.0σ | 7/10 | survives averaging |
| delay | 0.0σ | 2/10 | cycle+dwell only, no feature |
| loss | 0.09σ / 0.58σ | 3/10 | stale-hold needs run-length + SHF |
| breakdown | −3σ offset, DOWN state | 4/10 | needs DOWN-duration, masked as unlearnable |
| quality | 2.25σ at origin*, part-flag routed | 2/10 | *origin-obs misleading; signal is ASM2 REJECT + RWK passes, never exported |
| **overall** | — | **3/10 NOT trainable** | no labels + no windows + 4/7 classes need non-obs heads |

---

## 2. Target architecture (locked) — 1 sample = stride-1 window + purge

```
resolved channel   → B_i=b, status=resolved   → rows 0.5b / b / 2b (unchanged semantics)
unresolved channel → B_i=null, status=unresolved → NEUTRAL COVER (prefix S,Q + RMQ sidecar;
                        schema-compatible alt: dyadic {1,2,4,8,16,32,64} rolling bank)
                        downstream DEFERS scale choice (supervised search, grouped CV, purge/embargo=1 window)
```

- **Labels**: schema v5 per-step `y, fault_mask, warmup_flag, shf_flag, down_flag, family, mode, root_id/hop` (+ existing M0.2e keys). Window label from exact GT overlap, never whole-window-positive.
- **Heads**: H-obs (spike/drift/bias, obs+current windows), H-state (delay/loss/breakdown: dwell/cycle, stale-hold runs, DOWN-duration, buffer occupancy, state-hist deltas), H-part (quality, isolated: DEGRADE/REJECT counts, ASM2 reject-rate, RWK passes, funnel deltas; own threshold).
- **Balance**: fault steps ≤8%/episode, 1–3σ ladder ≥20%, STARVED-heavy ≥25% episodes, kits ≥30 median via funnel variants; class-weights + per-class thresholds; SMOTE default-OFF, inside-`imblearn.pipeline` only by ablation.
- **Norm/splits/cal**: per-machine median/IQR on RUN-normal-only inside folds (reversal wire to global if M−G<+2pp); `StratifiedGroupKFold` by `episode_id` with wear/family/state strata; 3-arm calibration on clean validation only; report raw-F1 PA-off + alerts/1000 @20/150/5 + worst-machine.
- **Envelope**: ONE pinned global definition `GES2N-v1` (versioned ID): `p[t]=e[t]²` computed once per channel per episode on full-length signal; windowed energy = `sum(p[t])` via prefix. Window-local recompute REJECTED by test.

---

## 3. File-by-file changes

### 3.1 `src/window_export.py` — REWRITE (M0.2f-owned, keep module path so PR stays mergeable)
Keep public names the PR tests use (`aggregate_window`, `envelope_features` signature, `rolling_features_for_channel`, `export_multiscale`, `build_m0_2f_window_config_section`, `derive_base_window`) but fix semantics:

```python
ENVELOPE_DEFINITION_ID = "GES2N-v1"
ENVELOPE_CODE_VERSION = "window-export-2.0.0-m0.2f"
DYADIC_BANK = (1, 2, 4, 8, 16, 32, 64)  # schema-compatible cover; comment cites audit §5 (representation, not physics)

def rolling_bank(x, W) -> dict  # pure: rolling sum/sumsq/min/max, stride-1, no pad, no RNG
def prefix_repr(x, p) -> dict   # S[k]=Σ_{t<k}x[t], Q[k]=Σx², P[k]=Σp[t]; + sparse-table/segment-tree RMQ for min/max
def reconstruct(cover, s, w) -> dict  # binary-partition recombine → mean/RMS/min/max + Σ p; RMS from sumsq ONLY
def global_envelope(x, definition_id=ENVELOPE_DEFINITION_ID) -> tuple[e, p]  # full-length Hilbert ONCE per channel; rejects per-window recompute
def derive_base_window(calibration, *, estimator="pooled-acf", seeds, folds) -> dict
    # POOLED training-episodes only, RUN-normal-only, excl warmup(15)/fault-GT/DOWN/DROPOUT/post-maint.
    # Returns {base_window: int | "UNRESOLVED", B_i: int|null, scale_status: resolved|unresolved, ...}.
    # Single-episode ACF peak → UNRESOLVED (variance ~1/N documented). Stable pooled peak across folds/seeds → resolved; else UNRESOLVED (a finding, not failure).
    # NEVER returns q=25 triple. Delete _FALLBACK_Q.
def export_cover(episode_obs, episode_id, channel_names, derivation, *, out_dir, mode="sidecar"|"dyadic") -> dict
    # sidecar (preferred): per channel per episode S,Q,P + RMQ + metadata {B_i, scale_status, envelope_definition_id+version, episode_id, warmup/fault masks}
    # dyadic (schema-compatible alt): rolling bank over DYADIC_BANK with recombination contract in metadata
def build_m0_2f_window_config_section(derivation, *, fs=1.0) -> dict
    # MUST include: B_i (nullable), scale_status, scale_cover ("prefix-rmq"|"dyadic-1..64"), envelope_definition_id+version, episode_id, recombination_contract, float_tolerance_note (allclose, not ==)
```

Delete: `_FALLBACK_Q`, `_compute_fallback_scale_lengths`, window-local `envelope_band_energy` ratio, `detrend_signal` (or keep pure + test, but NOT in pipeline), `run_m0_2f_export` clean-only path (replace with fault-aware `run_m0_2f_export(seed, faults, ...)` that exports GT masks alongside).
Hardened writer: `pq.write_table(..., version="2.6", coerce_timestamps="us", use_dictionary=False, compression="snappy", row_group_size=1024)` + sha256 log. No `scaler.pkl` assert stays. No `twin/config` value duplication (import only `MACHINE_INDEX, T, WARMUP_STEPS` — allowed; never copy numbers).

### 3.2 `src/dataset_export.py` — schema v5 additive (M0.2e + M0.2f coordination)
- `TWIN_SCHEMA 4 → 5` in `src/config.py` (+ `CODE_VERSION` suffix bump). Add `load_v5_dataset()` + flag-day: `load_v4_dataset` rejects v5 loudly; `load_v3_dataset` rejects ≥4 (extend).
- Per-step label columns in `export()` inner loop (derive from `twin.run_episode` `specs` + `states`): `y (0/1 fault-cover)`, `fault_mask`, `fault_family`, `fault_mode (observation-only|physical-propagation)`, `is_warmup`, `shf_flag (OK|SUSPECT|DROPOUT: stale-hold detect)`, `is_down`, `root_id_step`, `hop_step`. Keep all v4 columns (sorted-column determinism, hardened writer, size cap, no-scaler assert unchanged).
- Split-head feature columns (compute per step, no future leak — causal windows only): H-state: `dwell_steps, cycle_lag, stale_hold_run, down_run, buffer_occ, state_hist_delta`; H-part: `degrade_flag_count, reject_flag_count, rwk_passes, funnel_delta`. H-obs stays window-side (window_export), not per-step.
- `build_window_config()`: add `B_i (nullable), scale_status, scale_cover, envelope_definition_id+version, schema_version=5`; `ownership.M0.2f += [scale_status, B_i, envelope_definition_id]`; keep M0.2e prohibition.
- `export_contract_dataset_v4` → add `export_contract_dataset_v5` with balanced families incl. delay/loss/quality + 1–3σ ladder faults (see §5 budgets).

### 3.3 `src/train_pipeline.py` (NEW, thin contract — full MINIPRO-19 battery later)
- `build_windows(df_v5, cover)`: branch on `scale_status`: resolved → 0.5B/B/2B; unresolved → query any w from cover (deferred supervised search, purge/embargo=1 window).
- Splits: `StratifiedGroupKFold(groups=episode_id)`, wear/family/state strata; `imblearn.pipeline` so norms/SMOTE fit inside folds; leakage unit test hook.
- Norm: M-first per-machine median/IQR on RUN-normal-only; reversal wire.
- Imbalance: class-weight + per-class thresholds (`TunedThresholdClassifierCV`-style); SMOTE off unless ablation flag.
- Calibration: 3 arms on clean-validation-only; report raw-F1 PA-off + alerts/1000 @20/150/5 + worst-machine. No PA metrics anywhere.

### 3.4 `tests/` — new + fixed (all marked; CI collects them)
| file | marks | contents (Given/When/Then, one When each) |
|---|---|---|
| `tests/test_window_export.py` (rewrite, keep PR hand-aggregate cases) | `k1 k3 battery` | reconstruction property (seeded episodes, all `(s,w)` incl. w∈{1,53,64,65,100,105}, odd starts, max overlap → allclose); float non-identity (large-offset/tiny-var adversarial → `==` fails, allclose passes); RMS-needs-sumsq (direct-RMS combine FAILS, sumsq passes); envelope-A/B (windowed-sum(global) passes / window-local recompute must FAIL); no-fabrication (unresolved → `B_i is null`, no 0.5B/B/2B cols, cover+version present); counts (615 vs 5565 at N=105); `derive_base_window` single-episode → UNRESOLVED, pooled-stable → resolved |
| `tests/test_anomaly_retention.py` (NEW — the brutal quality gate) | `battery k2` | per family (spike/drift/bias/delay/loss/breakdown/quality): fault-window feature separation vs clean (effect-size / AUROC floor); obs-head fires on spike/drift/bias, H-state fires on delay/loss/breakdown, H-part fires on quality; FAIL if delay/loss/quality rely on obs-mean alone |
| `tests/test_leakage.py` (NEW) | `k3 battery adversarial` | episode-recovery ≤ chance+2pp; norm-refit detection; SMOTE-outside rejection; cover/pooled-B fit on train seeds only; purge/embargo enforced |
| `tests/test_dataset_v5_contract.py` (NEW) | `k1 battery` | v5 columns incl. per-step labels + head features; sorted columns; hardened writer opts; v4-reader-rejects-v5; no scaler.pkl |
| `tests/test_duplicate_writer_guard.py` (extend PR's loosening) | `k1` | add `envelope_band_energy, episode_id_ref, t_start, t_end, B_i, scale_status, envelope_definition_id` to M0.2f set OR (better) replace `episode_id_ref` with real `episode_id` join + designate `dataset_export.export` as co-writer; keep DESIGNATED_M0_2F_OWNERS |
| `tests/test_window_export.py` existing PR classes | keep | keep Tests 1–4,8–10,12–14 (hand agg, envelope-stat vs global def, stride, independence, boundary, regression, no-scaler); DELETE/REWRITE Tests 5–7,11 (base-window determinism, no-CAL_WIN, 0.5/1/2×, version) to new semantics |

### 3.5 CI (`.github/workflows/ci.yml`)
- `battery` job: add `python -m pytest tests/test_anomaly_retention.py tests/test_leakage.py tests/test_dataset_v5_contract.py tests/test_window_export.py -q` (or ensure marks collected: add marks to the `-m` expression).
- `killbars-security`: extend schema assert to `TWIN_SCHEMA == 5`; add `window-cover recombination` + `envelope global-vs-local` asserts; keep 0-diverge ×5, no-downsampling.
- Add `trainability` step (or extend battery): `python scripts/check_gates.py` stays for F1/AC1/flip; ADD per-family retention gate script `scripts/check_anomaly_quality.py --min-auroc ... --families all` (fail-closed; see §5 bars).

### 3.6 Docs
- Update `docs/M0_2F_FALLBACK_AUDIT.md` status line (window_export exists, v2 semantics) — audit math unchanged.
- `docs/SIM_SPEC.md` §5/§8 amendment: v5 columns, envelope ID, split-head features, budgets (§5 below). Keep wave/bearing boundary (§9.1) + no-PA (F1 Locked).

---

## 4. What NOT to do (hard prohibitions)
1. No `q=25` / `N/8 / N/12 / N^(2/3)` constants anywhere (grep-gated).
2. No window-local Hilbert/filter envelope; no `envelope_band_energy` ratio without global-`p[t]` + version ID.
3. No whole-window-positive labeling; no PA / overlap-TP / test-searched thresholds.
4. No SMOTE/norm/GMM/POT fit outside folds; no scaler.pkl; no global single scaler as default.
5. No obs-only single head for all 7 classes; no dropping quality (isolate with own head/threshold instead).
6. No twin physics tuning to fit detectors (TWIN FREEZE: `twin.py/config.py` frozen except `TWIN_SCHEMA`/`CODE_VERSION` bump).
7. No Sim2Real / transfer / ROI claim without ≥50 paired-real windows/channel (§9.2).

---

## 5. Generation budgets the twin/export MUST satisfy (training back-propagates to generation)
- Fault steps ≤8% of scored steps/episode (T5 calibratability).
- 1–3σ incipient ladder rung at ≥20% of injections (else H1/H2 caricature-conditional).
- STARVED-heavy (≥40% STARVED) ≥25% of training episodes + 10% BLOCKED-visible (else H3 untestable).
- Funnel: kits-completed ≥30/episode-batch median via AGV-priority + buffer-cap variants (else assembly/rework have no examples).
- Warmup 15 flagged, excluded from fits, kept in transient-inclusive precision pool.
- Per-family retention bars (raw, PA-off, grouped CV): H-obs AUROC ≥0.80 on spike/drift/bias; H-state ≥0.70 on delay/loss/breakdown; H-part ≥0.65 on quality (quality kept + isolated, not dropped); unknown-family slice recall_unknown ≥0.30 reported, never tuned.

---

## 6. Implementation order (suggested, single agent)
1. `src/window_export.py` rewrite + `tests/test_window_export.py` (red→green: reconstruction first).
2. `src/config.py` bump + `dataset_export.py` v5 labels/heads + `tests/test_dataset_v5_contract.py` + guard update.
3. `tests/test_anomaly_retention.py` + `tests/test_leakage.py` (prove retention + no-leak).
4. `src/train_pipeline.py` thin contract wired to cover.
5. CI wiring + `scripts/check_anomaly_quality.py`.
6. Full suite: `ruff check src/ tests/ && ruff format --check src/ tests/`, `mypy src/` (if clean today; else don't introduce NEW errors), `pytest tests/ -q`, wall-budget note.

## 7. Commit / push (owner has perms; sign-off required)
- Branch: implement ON `pr16-m0-2f-gowtham` (fetch: `git fetch origin 'pull/16/head:pr16-m0-2f-gowtham'`), or cherry-pick onto it — PR #16 must be the vehicle (do NOT open a new PR).
- Commits: `git commit -s -m "<type>(m0.2f): <what> ..."` (signed-off, `-s` mandatory).
- Push: `git push origin pr16-m0-2f-gowtham:m0-2f-gowtham` (or `HEAD:refs/heads/m0-2f-gowtham`); verify `gh pr view 16 --json state,commits` shows new commit. Never force-push; never commit to `main`.
- PR comment afterwards summarizing: fallback replaced (B=null+cover), labels added (v5), heads split (quality isolated), retention/leakage gates green, wall delta.

## 8. Done criteria
- [ ] No `25/50/100`, no `q`, no window-local envelope in `src/` (grep clean).
- [ ] Unresolved → `B_i is null` + cover + versioned envelope ID; reconstruction tests green.
- [ ] v5 export has per-step y/masks/flags; v4 reader rejects v5; no scaler.pkl.
- [ ] Retention gate green per family (quality kept, own head, ≥0.65); leakage tests green.
- [ ] CI collects new tests (marks) + schema==5 asserts; full suite + ruff green.
- [ ] Pushed to PR #16 branch with `-s` sign-off; PR comment posted.

*End — implement exactly this; where spec conflicts with PR #16 code, this spec wins. Where this spec conflicts with the audit's math, the audit wins and this spec must be amended, not the math.*
