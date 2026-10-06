# M0.2g Audit-Fix Build Spec — From Brutal Audit to Trainable Twin (Schema v6)

Owner decisions (locked, from multiple-choice):
1. Fix scope: **ALL critical fixes** (counters + propagation + sensor heads + mag export together, then regen).
2. Step-level anomaly ratio: **keep ~4%** (preserve current density; fix label quality, not volume).
3. Dataset scale: **100+ episodes, randomized timing** (kill the t0=140/150 clock shortcut).
4. Realism: **tool-wear only** (no seasonality/bursts/human-delay in this milestone).
5. Dwell semantics: **state-entry + tput lag** (dwell = steps since this machine entered current state; cycle_lag = steps since its last throughput).
6. Label semantics: **y root-only** (y=1 only at hop-0 root window; fault_mask=1 covers root + hop>0 symptoms).
7. SHF fix: **tolerance + thresholds** (fix float-equality, keep 3/6 SUSPECT/DROPOUT, populate sensor_vs_process from spec).
8. Wear model: **exponential wear** (accelerating drift, negligible early, ramps near wear_endpoint).

Target reader: a fresh implementation agent with repo access. This file is the complete build order. No other audit docs needed.

---

## 1. Anomaly ratio — current state and target (the "how is the ratio" answer)

### Current artifact (`artifacts/dataset_v5.parquet`, 8 seeds `[7,11,13,42,777,1234,999,2026]`)
- Shape: **2400 rows = 8 eps x 300 steps**. Positives: **91 steps => 3.795% (~3.8%)**.
- `y == fault_mask` on every row (mismatch = 0). No symptom/mask split exists yet.
- Fault windows are fixed-position: t0=150 dur=10-15 (breakdown ep 1234: t0=140 dur=15). Ep 7 clean, 7 fault eps.
- Per-family y counts: drift 24 (2 eps x 12), spike 10, delay 12, loss 15, quality 15, breakdown 15.
- Rate-budget denominator (per `check_rate_budget`, `src/twin.py` ~line 2703): scored = T - CAL_WIN - WARMUP transient handling; budget = 8% of scored. Current max window (15 steps) passes, but only because there is 1 fault/episode.

### Target for regen (normative)
- **Step-level definition**: `ratio = sum(y) / N_steps` over ALL exported rows (warmup steps included in denominator, y=0 there by construction since t0 >= CAL_WIN=120 > WARMUP=15). Report two numbers: raw ratio and scored ratio (`sum(y)/sum(step>=CAL_WIN)`).
- **Target band: 3.0% - 5.0% for `y` (root-only), fault_mask (root+symptom) allowed up to 8%** per the rate-budget ceiling. Do NOT chase the budget ceiling for y.
- **Concrete 110-episode plan**: 10 clean + 100 fault episodes => 33,000 rows. With mean root dur ~12: `100*12/33000 = 3.6%` y. Symptoms add ~0.5-1.5x root width depending on tail (see §3), so fault_mask lands ~5-7%. Both in band.
- **Per-family balance**: 7 classes (spike, drift, bias, delay, loss, breakdown, quality). Bias currently has ZERO episodes in the artifact — include it. ~14-15 eps per class over the 100 fault eps. Keep 20% incipient rung share (MAG_LADDER 1-3σ) per class for signal faults; non-signal classes use LOW_RUNG extras (already defined in `src/config.py:113-116`).
- **Clean-episode share**: ~9% (10/110). Enough to measure FPR, not so many it dilutes the ratio.
- **Verification query** (must print after regen):
```python
import pandas as pd
df = pd.read_parquet('artifacts/dataset_v6.parquet')
print('y rate:', df['y'].mean(), '| mask rate:', df['fault_mask'].mean())
print(df.groupby('fault_family')['y'].agg(['sum','count','mean']))
print('symptom share:', ((df['fault_mask']==1)&(df['y']==0)).mean(), '| hop dist:', df['hop_step'].value_counts().to_dict())
```

---

## 2. Audit evidence that forces each fix (so the builder knows WHY)

| # | Defect | Evidence (repro) | Root cause (file:lines) |
|---|--------|------------------|-------------------------|
| 1 | `cycle_lag == dwell_steps == t+1` exactly (positional clock shortcut) | `python3 -c` probe: `(df.cycle_lag==df.dwell_steps).all()==True`, `==df.t+1` True | `src/dataset_export.py:368-369`: `max(dwell_counts)`, `max(steps_since_tput)`. Some machine never changes state / never puts, so max == t+1 |
| 2 | `hop_step` all 0 on positives, -1 elsewhere; zero propagation labels | `df[df.y==1].hop_step.value_counts()` => {0:91} | `src/dataset_export.py:306-314`: hardcoded `hop_step_val=0` in window, -1 outside. `derive_roots_and_hops` (`src/twin.py:1652-1668`) is episode-level only, never per-step |
| 3 | `shf_flag` all OK (2400/2400) even with `stale_hold_run`=4 | `pd.crosstab(df.shf_flag,df.y)` all OK; loss ep 777 has stale runs 1-4 yet OK | `src/dataset_export.py:280-287`: `cur_obs == last_obs` float-exact equality almost never true for AR(1)+sine noise; loss stale-hold copies exact float so only that path increments, but `max_stale` is global-max and threshold logic at :316-322 rarely trips because `stale_counts` resets on any micro-change |
| 4 | `sensor_vs_process` all `unknown` (2400/2400) | value_counts => unknown 2400 | `src/twin.py:2101`, `src/dataset_export.py:344-346`: hardcoded "unknown" + `test_twin_stratification_funnel.py:220` pins it |
| 5 | H_part dead: `reject_flag_count` all 0, `rwk_passes` all 0, `funnel_delta` constant 32-39 identical clean/fault, `degrade_flag_count` mean higher on clean (16.6) than breakdown (14.9) | describe/groupby probes | `src/dataset_export.py:391-401`: funnel_delta uses FINAL flow_stats (episode-constant), degrade is cumulative episode counter, quality reject_rate path exists in twin (`_quality_rate`, `_asm_mid_process`) but contract faults (reject_rate=0.30) produce no REJECT_ROUTE events at this throughput — plus only 15-step windows |
| 6 | Fixed fault positions t0=140/150 => wall-clock shortcut | per-episode yspan probe: all windows [140..165] | `export_contract_dataset_v5` (`src/dataset_export.py:780-860`) hardcodes t0/dur per fault dict; `_try_place` randomizer exists but contract path doesn't use it |
| 7 | 3/7 families invisible on H_obs (delay 0.67σ, loss 1.12σ, quality 0.83σ mean |z|); spike 7.0σ trivial | SNR probe (median/IQR fit on clean ep 7) | Real physics gap is EXPECTED for delay/loss/quality (they act via states/routing, not obs deviation) — but H_state/H_part heads that should carry them are defects #1/#5 |
| 8 | Grouped median/IQR baseline: thr=3 F1raw 0.128 P 0.084 R 0.26 FPR 13%; delay/loss/quality recall = 0.0 | baseline probe script (see §7) | 26-channel max|z| multiple-comparison + sub-noise faults. Honest floor, not a bug per se |
| 9 | Only 8 episodes => 5-fold StratifiedGroupKFold yields single-episode test folds | CV probe | Artifact scale, fixed by §6 regen |
| 10 | `mag_sigma`/`sev`/`rung` never exported => incipient 1-3σ mix unverifiable | `[c for c in df.columns if 'mag'...]` => [] | `specs` carry mag in `rec["faults"]` but export loop never writes per-step mag columns |

---

## 3. Normative per-step label semantics (Schema v6)

Replace the `dataset_export.py:292-314` block with:

- Let each spec have `[t0, t1)` root window (`t1 = t0+dur`, breakdown-ladder: `t0+ceil(dur*mttr_mult)` — reuse `shared["gwin"]` semantics from `src/twin.py:1816-1824`).
- **Root steps**: `t in [t0,t1)` for any spec => `y=1`, `fault_mask=1`, `root_id_step=<origin>`, `hop_step=0`, `fault_family=<class>`, `fault_mode=classify_fault_mode(class)`, `mag_sigma=<spec mag>`, `mag_rung=incipient|caricature`.
- **Symptom steps**: `t in [t0, t1+SYMPTOM_TAIL)` (default SYMPTOM_TAIL=8, config-constant) where a non-root machine `m` with `compute_hop(origin,m) in 1..3` (reuse `src/twin.py:1600-1649` adjacency) is in STARVED/BLOCKED/DOWN while root window active or trailing => `y=0`, `fault_mask=1`, `root_id_step=<origin>`, `hop_step=<min hop among symptomatic machines at t>`, family/mode/mag copied from the causing spec.
- **Clean steps**: `y=0, fault_mask=0, hop_step=-1, root_id_step="none", fault_family="none", fault_mode="normal", mag_sigma=0.0, mag_rung="none"`.
- Multi-fault overlap: nearest-cause wins (smallest hop, then earliest t0). Same-machine gap>=5 rule already enforced by `_validate`.
- `sensor_vs_process` per step: observation-only classes (spike/drift/bias/loss) => `"sensor"`; physical (delay/breakdown/quality/wear_drift) => `"process"`. Episode `strat` field follows the same mapping (first spec), dropping the "unknown" pin.
- New columns (all sorted-keys deterministic, parquet v2.6/snappy as today): `mag_sigma float`, `mag_rung str`, `symptom_mask int (0/1, == fault_mask & ~y)`.

---

## 4. H_state counter redefinitions (fix #1, "state-entry + tput lag")

Per-machine trackers in the export loop are CORRECT (`dwell_counts`, `steps_since_tput`, `down_counts` at `dataset_export.py:231-237,261-278`) — only the row collapse is wrong. Change:

- `dwell_steps`: steps since the **root machine** entered its current state (its `dwell_counts[root_idx]`). If clean step (no active spec), use **median** of `dwell_counts` across 26 (robust, never t+1). Delete `max()` usage.
- `cycle_lag`: steps since the **root machine** last had throughput>0 (its `steps_since_tput[root_idx]`). Clean steps: median across 26.
- `down_run`: root machine's `down_counts[root_idx]` (0 when not DOWN). Clean: 0.
- `stale_hold_run`: root machine's `stale_counts[root_idx]` with tolerance fix (§5). Keep `recent_stale` trailing-window? No — replace with root counter; trailing smear hides onset. Detection latency needs exact onset.
- `buffer_occ`: sum of buffers over the **affected subgraph** (root + hop<=2 machines per adjacency), NOT global 26-sum. Clean: global median over episode? Simpler: sum over root+hop<=2 always (well-defined clean or fault).
- `state_hist_delta`: fraction of affected-subgraph machines in RUN (not global 26-fraction; global is dominated by always-RUN feeders).
- ADD per-machine columns (sorted keys, cheap at 110 eps): `dwell_<M>`, `tputlag_<M>`, `downrun_<M>` for all 26 M? That is 78 int cols x 33k rows — fine for parquet. These let Phase-1 GBDT use lagged tabular without re-deriving. If size cap complains, keep at least `dwell_` + `tputlag_` sets.
- Update `V5_REQUIRED_STATE_HEAD_COLS` test to v6 set (keep old 6 names with new semantics + new per-machine cols).

---

## 5. SHF + stale-hold tolerance fix (fix #3)

- `src/dataset_export.py:280-282`: replace `cur_obs == last_obs[m_idx]` with `abs(cur_obs - last_obs[m_idx]) <= SHF_TOL * sigma_m` where `SHF_TOL=1e-9` floor or `1e-6*sigma` (add `SHF_TOL=1e-9` to `src/config.py`). Loss stale-hold (`obs_row[t-1]` copy in twin) still trips; AR(1) micro-jitter no longer false-trips NOR permanently resets the counter on 1e-12 drift.
- Keep thresholds: SUSPECT>=3, DROPOUT>=6 (owner-locked). `shf_flag` becomes per-row global-worst as today (max over machines) — acceptable; per-machine shf optional (skip unless free).
- `stale_hold_run` = root-machine counter (see §4). Verify loss ep 777 shows SUSPECT/DROPOUT during its window after fix (acceptance test).

---

## 6. H_part signal fix (fix #5, minimal — no new physics except wear)

- `degrade_flag_count`: trailing-15-step count of LATE_VERDICT DEGRADE events (not episode-cumulative). Today's cumulative counter only rises and can't localize.
- `reject_flag_count`: trailing-15-step count of REJECT_ROUTE events (same pattern as `recent_rejects`, which already exists — just export the trailing value, not `max(trailing, cumulative)`).
- `rwk_passes`: keep max-passes semantics (already correct) BUT quality faults must actually produce rejects: raise contract quality `reject_rate` to FAULT_RANGES mid (0.25) for caricature and LOW_RUNG (0.05-0.12) for incipient, and extend quality dur to 15-20 so ASM2 completes enough parts inside the window. Verify `rwk_passes>0` on quality eps post-fix.
- `funnel_delta`: per-step `sunk(t)-sunk(t-1)`? Flow stats are episode-final only in `rec`. Cheapest correct: `kits_completed(t)` can't be reconstructed post-hoc — instead export `funnel_rate = kits_completed_episode / T` (constant, documents throughput) AND `scrap_flag = 1 if scrapped>0 else 0`. Do NOT keep the current constant-mislabeled-as-delta. Name it `funnel_rate` + `scrapped_total` (rename; update contract test).
- No other routing changes. RWK0/INSP0 logic untouched.

---

## 7. Exponential tool-wear drift (fix: realism, wear-only)

Design constraints: deterministic per (seed, faults), zero new RNG streams if possible, oracle digests WILL change (rebaseline §9), GAMMA_SIGMA reuse.

- `src/config.py` additions:
```python
WEAR_EXP = {"ALPHA": 1.0/240.0, "TAU": 0.6, "GAMMA_SIGMA": 2.0, "CAP_SIGMA": 0.5}
```
- Twin implementation (in `_line_process`, `_insp0_process`, `_asm_mid_process`, `_asm0_process`, `_rwk0_process` — or centrally in `_sample_signal` if wear passed in): maintain per-machine `wear[m]` starting 0; each step where state==RUN: `wear[m] += ALPHA * exp(wear[m]/TAU)`. Cap contribution at CAP_SIGMA. Obs bias: `val += GAMMA_SIGMA * wear[m] * sigma * (1 if state==RUN else 0.5)`.
  Rationale for exponential: matches owner pick (negligible first ~150 steps, visible ramp near episode end on high-duty machines, interacts with maint_flag future work). Deterministic (no draws). `compute_wear` post-hoc scalar stays for strat/wear_endpoint (recompute against same equation or keep linear-lite? KEEP linear-lite `compute_wear` untouched to avoid breaking strat tests; the in-loop drift is the new physics, post-hoc scalar is just a census feature).
- Wire `maint_flag`: set True + reset wear when? Out of scope — keep False (today's value), wear accumulates per episode only (no cross-episode memory; episodes are independent).
- Fault class `wear_drift` already in `_PHYSICAL_CLASSES` — no new class needed; the background drift is always-on, not a fault window.

---

## 8. Regen manifest: 100+ episodes, randomized t0, ~4% (fix #6, #9)

- Build on `build_faults_variant(master_seed)` (`src/twin.py:2488`), NOT hand dicts. It already gives 182-row machine×class cross-product with 20% incipient share, rep pins, mag_rung/sev. Add:
  - `t0` comes from `_try_place` uniform `[CAL_WIN, T-dur]` — already randomized. KEEP. The fixed-t0 problem is only in `export_contract_dataset_v5` hand dicts; the new manifest path must use variant rows.
  - New function `export_contract_dataset_v6(out_dir, master_seed=12345, n_episodes=110, n_clean=10)` in `src/dataset_export.py`: sample 100 fault rows from variant manifest stratified by class (14-15/class incl. bias; 20% incipient each), assign each to one episode seed (deterministic: `seeds = [10001..10110]` or SeedSequence-spawned; document), 10 clean episodes (fault=None). Per-episode single fault keeps budget trivially green; run `check_rate_budget` per episode (union<=14.4 steps at scored=180 … note: dur up to 25 breaches! cap sampled dur<=14 or pass cap_budget=True rows — reuse the `cap_budget` path from variant builder).
  - Enforce per-episode `check_rate_budget` + global ratio assert 3-5% y before writing parquet (fail loudly).
- Seeds: deterministic list in metadata (as today). Suggest `list(range(20001, 20111))`.
- Size: 110*300=33,000 rows x (~170+80 new cols) — well under 100MB cap. Verify.

---

## 9. Versioning, digests, and test updates (builder MUST do)

- Bump `TWIN_SCHEMA 5 -> 6`, `CODE_VERSION "twin-2.4.0-topology-A" -> "twin-2.5.0-topology-A"` in `src/config.py`. Schema 6 = v5 + §3/§4/§5/§6/§7 semantics.
- `replay_digest` (`src/twin.py` ~2719) hashes obs/states — wear drift changes obs => all 4 pinned digests in `tests/test_twin_split_census_topology_a.py:57-60` change. Recompute via `twin.replay_digest(twin.run_episode(...))` and update. Same for any battery JSON under `docs-battery-*.json` referenced by `test_twin_battery_topology_a.py` (regenerate with the battery script, don't hand-edit numbers).
- `test_twin_stratification_funnel.py:220` (`sensor_vs_process == "unknown"`) MUST be updated to the §3 mapping (sensor/process per class + clean=="unknown"? clean has no spec — keep "unknown" for clean, mapped value for fault eps).
- `test_dataset_v5_contract.py`: add v6 contract test file (don't delete v5 test — flag-day: `load_v5_dataset` rejects v6 loudly, new `load_v6_dataset` accepts v6). New required cols: mag_sigma, mag_rung, symptom_mask, funnel_rate, per-machine dwell/tputlag sets.
- `train_pipeline.py`: `fit_per_machine_median_iqr` + `compute_raw_pointwise_f1` unchanged (already correct). ADD `compute_pr_auc_and_latency(y_true, scores, t)` helper? Optional but recommended for the prescribed metrics (PR-AUC + median Δt). Ban list documentation: never feed `cycle_lag/dwell_steps` v5 semantics; v6 root-anchored versions allowed.
- Docs: update `docs/SIM_SPEC.md` Table 3.1 + §4/§5/§8 for v6 semantics (labels, counters, wear equation, sensor mapping). Keep it brief — table deltas + equation.

---

## 10. Acceptance checklist (all must pass before "simulation closed")

1. `python -m pytest -n auto -q` => all green (434+ tests incl. new v6 contract + propagation + wear tests).
2. Ratio probe (§1 query): y in 3-5%, fault_mask <=8%, hop dist shows 0 + 1..3 mass, all 7 families present with per-family y>0.
3. Counter probe: `(df.dwell_steps==df.t+1).mean() < 0.05` (no longer degenerate); `dwell_<root>` columns vary within episode.
4. SHF probe: loss episodes show SUSPECT/DROPOUT in window; clean episodes ~all OK.
5. Sensor probe: `sensor_vs_process` in {sensor, process, unknown}; unknown only on clean.
6. H_part probe: quality eps have `reject_flag_count>0` or `rwk_passes>0` in window; `funnel_rate` varies across eps.
7. Mag probe: `mag_sigma` nonzero iff fault_mask==1; incipient share of fault steps 15-25%.
8. Baseline probe (grouped, fit-clean-episodes-only, thr on max|z| over H_obs): report F1raw/PR-AUC/per-family recall/delay — expect spike/breakdown recalled, delay/loss/quality still weak on H_obs alone (that's WHY H_state/H_part fixes exist; follow-up modeling milestone consumes them).
9. CV probe: StratifiedGroupKFold(5) over 110 eps => every test fold has >=2 fault + >=1 clean episodes and >=2 families.
10. Determinism: 2x same-seed export bit-identical sha256.

## 11. Suggested build order (3 PRs)

- PR1 (twin): wear drift + sensor mapping + strat changes + digest rebaseline + tests.
- PR2 (export): v6 labels/counters/SHF/H_part/mag columns + v6 contract + loader flag-day + tests.
- PR3 (data): v6 manifest regen (110 eps) + ratio/CV/baseline evidence + SIM_SPEC delta + close-out verdict.

Out of scope (explicitly NOT this milestone): seasonality, non-Gaussian bursts, human-delay variance, GNN/TCN modeling, PA-metric library, live-stream serving.
