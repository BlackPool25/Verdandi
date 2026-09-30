# M0.2f Coordination Pin & Twin Freeze Sequencing

Status: PINNED / NORMATIVE ARCHITECTURE COORDINATION
Tracking: MINIPRO-25 (M0.2e) & MINIPRO-29 (M0.2f)
Downstream: MINIPRO-19 (Training Pipeline), MINIPRO-10 (Battery Baselines)

---

## 1. Context and Scope Boundary

This document records the architectural contract and operational boundary between:
- **M0.2e (MINIPRO-25, Shreyas)**: Stratification keys, rolling-20 funnel rebalancing (median sunk $\ge 30$), zero-join dataset contract, and v3 schema export.
- **M0.2f (MINIPRO-29, Gowtham)**: Multi-scale temporal aggregates (0.5s, 1.0s, 2.0s windows / rollups) and signal envelope statistics.

To maintain modular development, eliminate race hazards, and guarantee reproducible datasets for the downstream training pipeline (MINIPRO-19), the boundary of field ownership is strictly partitioned.

---

## 2. Owned-Field Partitioning

### 2.1 M0.2e Owned Fields (Stratification Keys & Census)
The following keys are owned exclusively by **M0.2e**. They are computed per episode/step and exported in simulation records (`record["strat"]`) and dataset rows (`artifacts/dataset_v3.parquet`):

| Key | Type | Description | Designated Writers |
|---|---|---|---|
| `episode_id` | `int` | Master episode seed identifier (grouping key for grouped CV) | `src/twin.py`, `src/dataset_export.py` |
| `wear_endpoint` | `float` | End-of-episode machine wear scalar $\max_m(w_m(T))$ | `src/twin.py`, `src/dataset_export.py` |
| `maint_flag` | `bool` | Maintenance intervention indicator | `src/twin.py`, `src/dataset_export.py` |
| `family` | `str` | Primary fault family (`clean`, `drift`, `spike`, `stuck`, etc.) | `src/twin.py`, `src/dataset_export.py` |
| `mode` | `str` | Operational degradation mode (`normal`, `degraded`, `failure`, `rework`) | `src/twin.py`, `src/dataset_export.py` |
| `root_id` | `str` | Primary injection root machine identifier (or `'none'`) | `src/twin.py`, `src/dataset_export.py` |
| `hop` | `int` | Causal propagation distance from root (0 for root, -1 for clean) | `src/twin.py`, `src/dataset_export.py` |
| `root_ids` | `list[str]` / `str` | Canonical collection of all distinct injection root origins | `src/twin.py`, `src/dataset_export.py` |
| `sensor_vs_process` | `str` | Fault class origin (`'sensor'` vs `'process'`) | `src/twin.py`, `src/dataset_export.py` |
| `warmup_steps` | `int` | Transient step count (15 steps) / warmup masking flag | `src/twin.py`, `src/dataset_export.py` |
| `state_histograms` | `dict` / `str` | Normalized per-machine operational state time proportions | `src/twin.py`, `src/dataset_export.py` |
| `funnel_census` | `dict` / `str` | Production census: kits completed, parts sunk, parts scrapped | `src/twin.py`, `src/dataset_export.py` |

**Designated Writer Modules**:
- `src/twin.py`: Canonical creator of simulation episode records (`rec["strat"]`).
- `src/dataset_export.py`: Canonical exporter of tabular dataset rows and `window_config.json`.

No other module may write, mutate, or duplicate these keys.

### 2.2 M0.2f Owned Fields (Multi-Scale Aggregates & Envelopes)
The following fields are owned exclusively by **M0.2f (MINIPRO-29, Gowtham)**:
- **Multi-scale rolling aggregates**:
  - 0.5-second rolling windows / rollups (`rollup_0_5s`, `window_0_5s`, `agg_0_5s`).
  - 1.0-second rolling windows / rollups (`rollup_1_0s`, `window_1_0s`, `agg_1_0s`).
  - 2.0-second rolling windows / rollups (`rollup_2_0s`, `window_2_0s`, `agg_2_0s`).
- **Signal envelope statistics**:
  - `envelope_max`, `envelope_min`, `envelope_mean`, `envelope_std` across observation channels.

### 2.3 Strict Implementation Prohibition
> **ABSOLUTE RULE**: M0.2e **MUST NOT** implement M0.2f aggregates or envelope statistics!
> Any implementation of multi-scale temporal windows or envelope bounds within M0.2e is strictly prohibited to prevent merge divergence and duplicate processing logic.

---

## 3. Rebase Order & Integration Discipline

When integrating M0.2e and M0.2f into the canonical development line:

1. **Rebase Order**:
   - Whichever branch lands second onto `main` **must rebase onto the first**.
   - If M0.2e lands first, M0.2f rebases onto M0.2e's tip.
   - If M0.2f lands first, M0.2e rebases onto M0.2f's tip.

2. **Buffer-Cap Diff Check in CI**:
   - Both milestones touch machine/buffer throughput characteristics. M0.2e introduced AGV-priority variants and bounded buffer-cap overrides to rebalance the production funnel (ensuring rolling-20 median sunk parts $\ge 30$).
   - A CI guard checks `git diff <base> -- src/config.py` for any uncoordinated alterations to `BUFFERS` or variant specifications.
   - Buffer capacity changes must be strictly verified against flow conservation and duty-cycle limits before landing.

---

## 4. Twin-Freeze Sequencing (`TWIN_FROZEN`)

The milestone lifecycle requires an immutable twin baseline before downstream training commences:

```
+------------------------------------+
| M0.2e Merged (Stratification Keys, |
| Funnel Rebalance >= 30, v3 Export) |
+-----------------+------------------+
                  |
                  v
+------------------------------------+
| M0.2f Merged (Multi-Scale Windows, |
| Envelopes & Rollup Aggregates)     |
+-----------------+------------------+
                  |
                  v
+------------------------------------+
|      TWIN FREEZE (TWIN_FROZEN)     |
|   - Zero twin code modifications   |
|   - Immutable simulation baseline  |
+-----------------+------------------+
                  |
                  v
+------------------------------------+
| M0b Battery & Downstream Training  |
| - MINIPRO-19: train_pipeline.py    |
| - MINIPRO-10: 182-run battery test |
+------------------------------------+
```

### Freeze Rules:
1. **Immutable Twin**: Once both M0.2e and M0.2f are merged, `src/twin.py` and `src/config.py` are declared **FROZEN**.
2. **No Post-Freeze Tuning**: Downstream model training (MINIPRO-19) and detector evaluations must train against the frozen twin. Under no circumstances may twin parameters, machine cycle times, or RNG seeds be adjusted to fit downstream detectors.
3. **Formal Schema Bump**: Any future alteration to the twin requires a bump to `TWIN_SCHEMA` (v3 $\to$ v4), a full re-baselining of battery goldens, and formal sign-off.

---

## 5. Duplicate-Writer CI Guard

To enforce this coordination contract continuously in CI:
- An AST-based structural inspection test (`tests/test_duplicate_writer_guard.py`) validates the codebase.
- The test scans the entire `src/` hierarchy to identify all dictionary keys, assignments, and updates written to simulation/dataset outputs.
- Any attempt by an unauthorized module to write M0.2e owned fields, or any attempt by M0.2e to implement M0.2f aggregates, fails the CI build.
- Negative control fixtures verify that unauthorized or conflicting writers immediately trip the guard.
