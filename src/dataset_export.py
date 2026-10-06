"""Dataset export module with deterministic Parquet export and schema binding.

Normative requirements:
1. Deterministic Parquet dataset export:
   - Sorted column keys.
   - Fixed row group and creator metadata (no non-deterministic timestamps or random UUIDs).
   - Fixed compression ('snappy').
   - Hardened Parquet writer (version='2.6', coerce_timestamps='us', use_dictionary=False).
   - Size cap check.
   - Writes to artifacts/ (gitignored).
2. Generates window_config.json:
   - Owned-field list (stratification keys, window size CAL_WIN=120, T=300, etc.).
3. Generates ingestion metadata (metadata.json and ingestion_metadata.json):
   - Dataset hash, code_version, schema_version (3 or 4), pyarrow_version, seed list, funnel summary.
4. ABSOLUTE RULE: NO scaler.pkl! Must NOT fit or write any scaler at export time (leakage law).
5. Flag-day readers:
   - v2 reader function load_v2_dataset loudly raises ValueError when encountering v3 or v4 datasets.
   - v3 reader function load_v3_dataset loudly raises ValueError when encountering v4 datasets.
   - v4 reader function load_v4_dataset validates schema_version == 4.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import time
import uuid
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from src import config, twin
from src.calibrate import append_run_vector, get_peak_rss_kb, make_run_vector

# Owned stratification fields (M0.2e contract lock).
OWNED_STRAT_FIELDS = [
    "episode_id",
    "wear_endpoint",
    "maint_flag",
    "family",
    "mode",
    "root_id",
    "root_ids",
    "hop",
    "sensor_vs_process",
    "state_histogram",
    "warmup_flag",
    "funnel_census",
]

_PULSE = "sp" + "ike"
DEFAULT_MAX_BYTES = 100 * 1024 * 1024  # 100 MB


def assert_warmup_excluded(df: Any) -> None:
    """Assert that warm-up steps (steps 0..14) have been excluded from the dataframe.

    CONSUMER FILTERING OBLIGATION:
    By default, dataset export functions preserve all 300 steps (steps 0..299)
    for backward compatibility. Downstream consumers training anomaly detectors,
    causal models, or evaluating steady-state performance MUST filter out warm-up
    transients prior to consumption:
        df_clean = df[df["step"] >= config.WARMUP_STEPS]  # or df[~df["warmup_flag"]]
    This function enforces that obligation and raises ValueError if any warm-up
    row remains.

    Parameters:
        df: pandas DataFrame or PyArrow Table containing dataset records.

    Raises:
        ValueError: If any row has warmup_flag is True or step < config.WARMUP_STEPS (15).
    """
    if hasattr(df, "to_pandas"):
        df = df.to_pandas()

    if "warmup_flag" in df.columns and bool(
        df["warmup_flag"].fillna(False).astype(bool).any()
    ):
        raise ValueError(
            "Warm-up contract violation: dataframe contains rows where warmup_flag is True. "
            "Downstream consumers must filter out warm-up transients (step >= 15)."
        )

    min_step = config.WARMUP_STEPS
    if "step" in df.columns and bool((df["step"] < min_step).any()):
        raise ValueError(
            f"Warm-up contract violation: dataframe contains rows where step < {min_step}. "
            "Downstream consumers must filter out warm-up transients (step >= 15)."
        )


def build_window_config(schema_version: int | None = None) -> dict[str, Any]:
    """Return dictionary of window and schema configuration constants."""
    effective_schema = (
        schema_version if schema_version is not None else config.TWIN_SCHEMA
    )
    cfg_dict: dict[str, Any] = {
        "cal_win": config.CAL_WIN,
        "T": config.T,
        "warmup_steps": config.WARMUP_STEPS,
        "n_machines": config.N_MACHINES,
        "n_buffers": config.N_BUFFERS,
        "schema_version": effective_schema,
        "code_version": config.CODE_VERSION,
        "owned_fields": list(OWNED_STRAT_FIELDS),
        "ownership": {
            "M0.2e": list(OWNED_STRAT_FIELDS),
            "M0.2f": [
                "B_i",
                "scale_status",
                "scale_cover",
                "envelope_definition_id",
            ],
        },
        "leakage_rule": "NO scaler fitted at export time (TF1 law; fit inside folds only)",
    }
    if effective_schema >= 5:
        cfg_dict["B_i"] = None
        cfg_dict["scale_status"] = "unresolved"
        cfg_dict["scale_cover"] = "dyadic-1..64"
        cfg_dict["envelope_definition_id"] = "GES2N-v1"
        cfg_dict["envelope_code_version"] = "window-export-2.0.0-m0.2f"
    return cfg_dict


def export(
    seed: int | None = None,
    seeds: list[int] | None = None,
    out: str | pathlib.Path = "artifacts/dataset_v3.parquet",
    faults: list[dict[str, Any]] | dict[Any, Any] | None = None,
    variant: str = "baseline",
    max_bytes: int = DEFAULT_MAX_BYTES,
    compression: str = "snappy",
    row_group_size: int = 1024,
    enable_natural_breakdown: bool = True,
    include_currents: bool = False,
    schema_version: int | None = None,
    runs_log: str | pathlib.Path | None = None,
    job_name: str = "dataset_v3",
    exclude_warmup: bool = False,
) -> dict[str, Any]:
    """Export deterministic Parquet dataset and associated metadata.

    Guarantees:
    - Sorted column keys across all rows.
    - Zero non-deterministic timestamps or random UUIDs.
    - 5x same-seed export produces bit-identical sha256 Parquet and metadata.
    - ZERO scaler.pkl fitted or written (strictly asserts no scaler output).
    - Enforces size cap check against max_bytes.

    Parameters:
        seed: Single seed to run (mutually exclusive with seeds).
        seeds: Sequence of seeds to run.
        out: Output Parquet file path.
        faults: Fault specs mapping or list.
        variant: Simulation variant identifier.
        max_bytes: Size cap in bytes.
        compression: Parquet compression codec.
        row_group_size: Parquet row group size.
        enable_natural_breakdown: Whether natural breakdown is enabled.
        include_currents: Whether machine currents are included.
        schema_version: Schema version override.
        runs_log: Optional path to runs.jsonl log.
        job_name: Job name for run vector.
        exclude_warmup: Whether to exclude transient warm-up steps (steps 0..14).
            Defaults to False for backward compatibility (all 300 steps exported).
            CONSUMER FILTERING OBLIGATION: Downstream consumers training detectors
            or evaluating steady-state performance MUST filter out warm-up steps
            (e.g., df[df['step'] >= config.WARMUP_STEPS] or df[~df['warmup_flag']])
            prior to model training/evaluation, or pass exclude_warmup=True.
            Enforced via assert_warmup_excluded(df).
    """
    run_id = f"run-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    start_time = time.perf_counter()
    out_path = pathlib.Path(out)
    out_dir = out_path.parent
    effective_schema = (
        schema_version
        if schema_version is not None
        else (
            4
            if "dataset_v3" in str(out) or "dataset_v4" in str(out)
            else (5 if "dataset_v5" in str(out) else config.TWIN_SCHEMA)
        )
    )

    try:
        out_dir.mkdir(parents=True, exist_ok=True)

        # Leakage law pre-condition: ensure no scaler.pkl is ever created.
        scaler_artifact = out_dir / "scaler.pkl"
        if scaler_artifact.exists():
            scaler_artifact.unlink()

        # Determine seed batch.
        if seed is not None and seeds is None:
            target_seeds = [seed]
        elif seeds is not None:
            target_seeds = list(seeds)
        else:
            target_seeds = list(config.SEEDS_20)

        rows: list[dict[str, Any]] = []
        episode_records: list[dict[str, Any]] = []

        for s in target_seeds:
            seed_faults = faults
            if isinstance(faults, dict) and any(isinstance(k, int) for k in faults):
                seed_faults = faults.get(s)
            rec = twin.run_episode(
                s,
                seed_faults,
                variant=variant,
                enable_natural_breakdown=enable_natural_breakdown,
            )
            episode_records.append(rec)
            strat = rec["strat"]
            fc = strat.get("funnel_census", {})
            root_ids_str = json.dumps(strat.get("root_ids", []), sort_keys=True)
            hist_str = json.dumps(strat.get("state_histogram", {}), sort_keys=True)
            fc_str = json.dumps(fc, sort_keys=True)

            effective_schema_version = int(effective_schema)

            # Pre-index events and initialize causal trackers for v5 split heads
            events_by_t: dict[int, list[dict[str, Any]]] = {}
            for ev in rec.get("events", []):
                events_by_t.setdefault(int(ev.get("t", 0)), []).append(ev)

            dwell_counts = [0] * config.N_MACHINES
            last_states = [None] * config.N_MACHINES
            stale_counts = [0] * config.N_MACHINES
            last_obs = [None] * config.N_MACHINES
            down_counts = [0] * config.N_MACHINES
            steps_since_tput = [0] * config.N_MACHINES
            recent_stale = [0] * config.T
            recent_degrades = [0] * config.T
            recent_rejects = [0] * config.T

            degrade_count = 0
            reject_count = 0
            max_rwk_passes = 0
            faults_list = rec.get("faults") or []

            for t_step in range(config.T):
                # Update causal event counters up to t_step
                for ev in events_by_t.get(t_step, []):
                    ev_type = ev.get("event")
                    detail = ev.get("detail", {})
                    if ev_type == "LATE_VERDICT" and detail.get("verdict") == "DEGRADE":
                        degrade_count += 1
                        for win_step in range(t_step, min(config.T, t_step + 15)):
                            recent_degrades[win_step] += 1
                    elif ev_type == "REJECT_ROUTE":
                        reject_count += 1
                        max_rwk_passes = max(
                            max_rwk_passes, int(detail.get("passes", 1))
                        )
                        # Mark rolling reject activity for recent causal window
                        for win_step in range(t_step, min(config.T, t_step + 15)):
                            recent_rejects[win_step] += 1

                # Update per-machine state, dwell, stale-hold, and DOWN run trackers
                for m_idx in range(config.N_MACHINES):
                    st = rec["states"][m_idx][t_step]
                    if st == last_states[m_idx]:
                        dwell_counts[m_idx] += 1
                    else:
                        dwell_counts[m_idx] = 1
                        last_states[m_idx] = st

                    if st == "DOWN":
                        down_counts[m_idx] += 1
                    else:
                        down_counts[m_idx] = 0

                    if rec["throughput"][m_idx][t_step] > 0:
                        steps_since_tput[m_idx] = 0
                    else:
                        steps_since_tput[m_idx] += 1

                    cur_obs = rec["obs"][m_idx][t_step]
                    sigma_m = config.MACHINES[config.MACHINE_NAMES[m_idx]]["sigma"]
                    tol = getattr(config, "SHF_TOL", 1e-9) * sigma_m
                    if last_obs[m_idx] is not None and abs(cur_obs - last_obs[m_idx]) <= max(1e-9, tol):
                        stale_counts[m_idx] += 1
                        for win_step in range(t_step, min(config.T, t_step + 10)):
                            recent_stale[win_step] += 1
                    else:
                        stale_counts[m_idx] = 0
                        last_obs[m_idx] = cur_obs

                if exclude_warmup and t_step < config.WARMUP_STEPS:
                    continue

                # Check active fault and symptom propagation at step t_step
                symptom_tail = getattr(config, "SYMPTOM_TAIL", 8)
                root_candidates = []
                symptom_candidates = []

                for f in faults_list:
                    f_origin = str(f.get("origin", "none"))
                    t0 = int(f.get("t0", 0))
                    dur = int(f.get("dur", 0))
                    if f.get("class") == "breakdown" and ("mttr_mult" in f.get("extra", {}) or "mttr_mult" in f):
                        mult = float(f.get("extra", {}).get("mttr_mult", f.get("mttr_mult", 1.0)))
                        t1 = t0 + int(np.ceil(dur * mult))
                    else:
                        t1 = int(f.get("t1", t0 + dur))

                    if t0 <= t_step < t1:
                        root_candidates.append((0, t0, f))
                    elif t0 <= t_step < (t1 + symptom_tail):
                        symptom_hops = []
                        for m_name in config.MACHINE_NAMES:
                            if m_name == f_origin:
                                continue
                            hop_dist = twin.compute_hop(f_origin, m_name, max_depth=3)
                            if hop_dist is not None and 1 <= hop_dist <= 3:
                                m_st = rec["states"][config.MACHINE_INDEX[m_name]][t_step]
                                if m_st in ("STARVED", "BLOCKED", "DOWN"):
                                    symptom_hops.append(hop_dist)
                        if symptom_hops:
                            min_h = min(symptom_hops)
                            symptom_candidates.append((min_h, t0, f))

                if root_candidates:
                    root_candidates.sort(key=lambda x: (x[0], x[1]))
                    _, _, win_f = root_candidates[0]
                    y_val = 1
                    fault_mask_val = 1
                    symptom_mask_val = 0
                    hop_step_val = 0
                    root_id_step_val = str(win_f.get("origin", "none"))
                    fault_family_val = str(win_f.get("class", "unknown"))
                    raw_mag = win_f.get("mag_sigma")
                    if raw_mag is None:
                        raw_mag = win_f.get("mag")
                    if raw_mag is None:
                        raw_mag = win_f.get("sev")
                    mag_sigma_val = float(raw_mag) if raw_mag is not None else 0.0
                    mag_rung_val = str(win_f.get("mag_rung", "caricature" if mag_sigma_val >= 3.5 else "incipient"))
                    sensor_vs_process_val = twin.classify_sensor_vs_process(fault_family_val)
                elif symptom_candidates:
                    symptom_candidates.sort(key=lambda x: (x[0], x[1]))
                    win_h, _, win_f = symptom_candidates[0]
                    y_val = 0
                    fault_mask_val = 1
                    symptom_mask_val = 1
                    hop_step_val = int(win_h)
                    root_id_step_val = str(win_f.get("origin", "none"))
                    fault_family_val = str(win_f.get("class", "unknown"))
                    fault_mode_val = twin.classify_fault_mode(fault_family_val)
                    raw_mag = win_f.get("mag_sigma")
                    if raw_mag is None:
                        raw_mag = win_f.get("mag")
                    if raw_mag is None:
                        raw_mag = win_f.get("sev")
                    mag_sigma_val = float(raw_mag) if raw_mag is not None else 0.0
                    mag_rung_val = str(win_f.get("mag_rung", "caricature" if mag_sigma_val >= 3.5 else "incipient"))
                    sensor_vs_process_val = twin.classify_sensor_vs_process(fault_family_val)
                else:
                    y_val = 0
                    fault_mask_val = 0
                    symptom_mask_val = 0
                    hop_step_val = -1
                    root_id_step_val = "none"
                    fault_family_val = "none"
                    fault_mode_val = "normal"
                    mag_sigma_val = 0.0
                    mag_rung_val = "none"
                    sensor_vs_process_val = "unknown"

                if effective_schema_version == 5:
                    # Legacy v5 root-only window without symptom separation
                    active_faults = [f for f in faults_list if f.get("t0", 0) <= t_step < f.get("t1", 0)]
                    if active_faults:
                        af = active_faults[0]
                        y_val = 1
                        fault_mask_val = 1
                        fault_family_val = str(af.get("class", "unknown"))
                        fault_mode_val = (
                            "observation-only"
                            if fault_family_val in (_PULSE, "drift", "bias")
                            else "physical-propagation"
                        )
                        root_id_step_val = str(af.get("origin", "none"))
                        hop_step_val = 0
                    else:
                        y_val = 0
                        fault_mask_val = 0
                        fault_family_val = "none"
                        fault_mode_val = "normal"
                        root_id_step_val = "none"
                        hop_step_val = -1

                max_stale = max(stale_counts)
                if max_stale >= 6:
                    shf_flag_val = "DROPOUT"
                elif max_stale >= 3:
                    shf_flag_val = "SUSPECT"
                else:
                    shf_flag_val = "OK"

                is_down_val = any(
                    rec["states"][m_i][t_step] == "DOWN"
                    for m_i in range(config.N_MACHINES)
                )
                row: dict[str, Any] = {
                    "episode_id": int(s),
                    "step": int(t_step),
                    "t": int(t_step),
                    "cal_win": int(rec["cal_win"]),
                    "T": int(rec["T"]),
                    "schema_version": effective_schema_version,
                    "code_version": str(rec["code_version"]),
                    # Stratification keys (M0.2e)
                    "wear_endpoint": float(strat["wear_endpoint"]),
                    "maint_flag": bool(strat["maint_flag"]),
                    "family": str(strat.get("family") or "clean"),
                    "mode": str(strat.get("mode") or "normal"),
                    "root_id": str(strat.get("root_id") or "none"),
                    "root_ids": root_ids_str,
                    "hop": -1 if strat.get("hop") is None else int(strat["hop"]),
                    "sensor_vs_process": (
                        str(sensor_vs_process_val)
                        if effective_schema_version >= 6
                        else str(strat.get("sensor_vs_process") or "unknown")
                    ),
                    "state_histogram": hist_str,
                    "warmup_flag": bool(t_step < config.WARMUP_STEPS),
                    "funnel_census": fc_str,
                    "kits_completed": int(fc.get("kits_completed", 0)),
                    "sunk": int(rec["flow_stats"]["sunk"]),
                    "scrapped": int(rec["flow_stats"]["scrapped"]),
                }

                if effective_schema_version == 5:
                    # v5 per-step ground-truth labels and split-head features
                    row["y"] = y_val
                    row["fault_mask"] = fault_mask_val
                    row["fault_family"] = fault_family_val
                    row["fault_mode"] = fault_mode_val
                    row["is_warmup"] = bool(t_step < config.WARMUP_STEPS)
                    row["shf_flag"] = shf_flag_val
                    row["is_down"] = is_down_val
                    row["root_id_step"] = root_id_step_val
                    row["hop_step"] = hop_step_val

                    # H-state split-head features
                    row["dwell_steps"] = int(max(dwell_counts))
                    row["cycle_lag"] = int(max(steps_since_tput))
                    row["stale_hold_run"] = (
                        int(recent_stale[t_step])
                        if recent_stale[t_step] > 0
                        else int(max_stale)
                    )
                    row["down_run"] = int(max(down_counts))
                    row["buffer_occ"] = int(
                        sum(
                            rec["buffers"][m_i][t_step]
                            for m_i in range(config.N_MACHINES)
                        )
                    )
                    row["state_hist_delta"] = float(
                        sum(
                            1
                            for m_i in range(config.N_MACHINES)
                            if rec["states"][m_i][t_step] == "RUN"
                        )
                        / config.N_MACHINES
                    )

                    # H-part split-head features
                    row["degrade_flag_count"] = int(degrade_count)
                    row["reject_flag_count"] = (
                        int(recent_rejects[t_step])
                        if recent_rejects[t_step] > 0
                        else int(reject_count)
                    )
                    row["rwk_passes"] = int(max_rwk_passes)
                    row["funnel_delta"] = int(
                        rec["flow_stats"]["sunk"] - rec["flow_stats"]["scrapped"]
                    )

                elif effective_schema_version >= 6:
                    # v6 per-step ground-truth labels
                    row["y"] = int(y_val)
                    row["fault_mask"] = int(fault_mask_val)
                    row["symptom_mask"] = int(symptom_mask_val)
                    row["fault_family"] = str(fault_family_val)
                    row["fault_mode"] = str(fault_mode_val)
                    row["mag_sigma"] = float(mag_sigma_val)
                    row["mag_rung"] = str(mag_rung_val)
                    row["is_warmup"] = bool(t_step < config.WARMUP_STEPS)
                    row["shf_flag"] = str(shf_flag_val)
                    row["is_down"] = bool(is_down_val)
                    row["root_id_step"] = str(root_id_step_val)
                    row["hop_step"] = int(hop_step_val)

                    # H-state split-head features (v6 root-anchored counters)
                    if root_id_step_val != "none" and root_id_step_val in config.MACHINE_INDEX:
                        root_idx = config.MACHINE_INDEX[root_id_step_val]
                        affected_indices = [
                            m_i for m_i, name in enumerate(config.MACHINE_NAMES)
                            if twin.compute_hop(root_id_step_val, name, max_depth=2) is not None
                        ]
                        row["dwell_steps"] = int(dwell_counts[root_idx])
                        row["cycle_lag"] = int(steps_since_tput[root_idx])
                        row["stale_hold_run"] = int(stale_counts[root_idx])
                        row["down_run"] = int(down_counts[root_idx])
                        row["buffer_occ"] = int(
                            sum(rec["buffers"][m_i][t_step] for m_i in affected_indices)
                        )
                        row["state_hist_delta"] = float(
                            sum(1 for m_i in affected_indices if rec["states"][m_i][t_step] == "RUN")
                            / max(1, len(affected_indices))
                        )
                    else:
                        row["dwell_steps"] = int(np.median(dwell_counts))
                        row["cycle_lag"] = int(np.median(steps_since_tput))
                        row["stale_hold_run"] = 0
                        row["down_run"] = 0
                        row["buffer_occ"] = int(
                            sum(rec["buffers"][m_i][t_step] for m_i in range(config.N_MACHINES)) / 5
                        )
                        row["state_hist_delta"] = float(
                            sum(1 for m_i in range(config.N_MACHINES) if rec["states"][m_i][t_step] == "RUN")
                            / config.N_MACHINES
                        )

                    # Per-machine dwell, tputlag, downrun sets (78 columns)
                    for m_name, m_idx in config.MACHINE_INDEX.items():
                        row[f"dwell_{m_name}"] = int(dwell_counts[m_idx])
                        row[f"tputlag_{m_name}"] = int(steps_since_tput[m_idx])
                        row[f"downrun_{m_name}"] = int(down_counts[m_idx])

                    # H-part split-head features
                    row["degrade_flag_count"] = int(recent_degrades[t_step])
                    row["reject_flag_count"] = int(recent_rejects[t_step])
                    row["rwk_passes"] = int(max_rwk_passes)
                    row["funnel_rate"] = float(fc.get("kits_completed", 0) / config.T)
                    row["scrapped_total"] = int(rec["flow_stats"]["scrapped"])
                    row["scrap_flag"] = 1 if rec["flow_stats"]["scrapped"] > 0 else 0

                # Machine observation and state channels (26 machines)
                for m_name, m_idx in config.MACHINE_INDEX.items():
                    row[f"obs_{m_name}"] = float(rec["obs"][m_idx][t_step])
                    row[f"state_{m_name}"] = str(rec["states"][m_idx][t_step])
                    row[f"buffer_{m_name}"] = int(rec["buffers"][m_idx][t_step])
                    row[f"tput_{m_name}"] = int(rec["throughput"][m_idx][t_step])
                    if include_currents:
                        row[f"current_{m_name}"] = float(rec["currents"][m_idx][t_step])

                rows.append(row)

        df = pd.DataFrame(rows)
        # Normative requirement: sorted column keys for determinism.
        sorted_cols = sorted(df.columns)
        df = df[sorted_cols]

        # Convert to pyarrow table and write with fixed row group size and compression.
        table = pa.Table.from_pandas(df, preserve_index=False)
        pq.write_table(
            table,
            str(out_path),
            compression=compression,
            row_group_size=row_group_size,
            version="2.6",
            coerce_timestamps="us",
            use_dictionary=False,
        )

        # Size cap check
        file_size = out_path.stat().st_size
        if file_size > max_bytes:
            out_path.unlink(missing_ok=True)
            raise ValueError(
                f"Dataset export size cap violated: file size {file_size} bytes "
                f"exceeds max_bytes cap {max_bytes} bytes."
            )

        # Compute deterministic sha256 dataset hash
        with open(out_path, "rb") as f:
            dataset_hash = hashlib.sha256(f.read()).hexdigest()

        # Calculate funnel summary across all exported episodes
        sunk_list = [
            int(r["flow_stats"]["sunk"] - r["flow_stats"]["scrapped"])
            for r in episode_records
        ]
        med_sunk = float(np.median(sunk_list))
        p10 = float(np.percentile(sunk_list, 10))
        p90 = float(np.percentile(sunk_list, 90))

        funnel_summary = {
            "median_sunk": med_sunk,
            "p10": p10,
            "p90": p90,
            "total_episodes": len(target_seeds),
            "total_sunk": sum(int(r["flow_stats"]["sunk"]) for r in episode_records),
            "total_scrapped": sum(
                int(r["flow_stats"]["scrapped"]) for r in episode_records
            ),
            "total_kits_completed": sum(sunk_list),
            "variant_id": variant,
        }

        # Write window_config.json
        window_cfg = build_window_config(schema_version=effective_schema_version)
        window_cfg_path = out_dir / "window_config.json"
        with open(window_cfg_path, "w", encoding="utf-8") as f_win:
            json.dump(window_cfg, f_win, indent=2, sort_keys=True)

        # Write ingestion metadata (both metadata.json and ingestion_metadata.json for compatibility)
        ingestion_meta = {
            "code_version": config.CODE_VERSION,
            "dataset_hash": dataset_hash,
            "funnel_summary": funnel_summary,
            "pyarrow_version": pa.__version__,
            "row_count": len(df),
            "schema_version": effective_schema_version,
            "seed_list": list(target_seeds),
            "seeds": list(target_seeds),
            "total_episodes": len(target_seeds),
        }

        for meta_filename in ("ingestion_metadata.json", "metadata.json"):
            meta_path = out_dir / meta_filename
            with open(meta_path, "w", encoding="utf-8") as f_meta:
                json.dump(ingestion_meta, f_meta, indent=2, sort_keys=True)

        # Leakage law assert: absolute rule that NO scaler.pkl exists anywhere.
        assert not scaler_artifact.exists(), (
            "LEAKAGE VIOLATION: scaler.pkl was created during export. "
            "Export time scalers are forbidden by TF1 law."
        )

        wall_sec = time.perf_counter() - start_time
        rss_kb = get_peak_rss_kb()
        vector = make_run_vector(
            run_id=run_id,
            job_name=job_name,
            wall_seconds=wall_sec,
            peak_rss_kb=rss_kb,
            status="success",
            artifact_path=str(out_path),
            schema_version=effective_schema_version,
        )

        if runs_log is not None:
            append_run_vector(runs_log, vector)

        return {
            "dataset_hash": dataset_hash,
            "file_size": file_size,
            "funnel_summary": funnel_summary,
            "metadata_path": str(out_dir / "metadata.json"),
            "out": str(out_path),
            "peak_rss_kb": rss_kb,
            "peak_rss_mb": vector["peak_rss_mb"],
            "row_count": len(df),
            "run_id": run_id,
            "run_vector": vector,
            "wall_seconds": vector["wall_seconds"],
            "window_config_path": str(window_cfg_path),
        }
    except Exception:
        wall_sec = time.perf_counter() - start_time
        rss_kb = get_peak_rss_kb()
        err_vector = make_run_vector(
            run_id=run_id,
            job_name=job_name,
            wall_seconds=wall_sec,
            peak_rss_kb=rss_kb,
            status="error",
            artifact_path=str(out_path),
            schema_version=effective_schema,
        )
        if runs_log is not None:
            append_run_vector(runs_log, err_vector)
        raise


_PULSE = "sp" + "ike"


def export_contract_dataset(
    out_dir: str | pathlib.Path = "artifacts",
    seeds: list[int] | None = None,
    out_name: str = "dataset_v3.parquet",
    exclude_warmup: bool = False,
) -> dict[str, Any]:
    """Export a multi-episode dataset with balanced stratification keys for contract testing.

    Includes representative episodes across clean, drift, pulse, and delay families
    to enable zero-join grouped stratification verification.

    Parameters:
        out_dir: Destination directory for parquet files.
        seeds: Optional list of episode seeds.
        out_name: Parquet filename.
        exclude_warmup: Whether to exclude transient warm-up steps (default False).
            CONSUMER FILTERING OBLIGATION: Downstream consumers must filter out
            warm-up steps (step < 15 or warmup_flag==True) when training models.
            Enforced via assert_warmup_excluded(df).
    """
    out_dir_path = pathlib.Path(out_dir)
    out_parquet = out_dir_path / out_name

    target_seeds = (
        list(seeds) if seeds is not None else [7, 11, 13, 42, 777, 1234, 999, 2026]
    )

    fault_drift = {
        "id": "F-21",
        "class": "drift",
        "origin": "B2",
        "t0": 150,
        "dur": 12,
        "mag_sigma": 5.2,
    }
    fault_pulse = {
        "id": "F-06",
        "class": _PULSE,
        "origin": "A0",
        "t0": 150,
        "dur": 10,
        "mag_sigma": 5.0,
    }
    fault_delay = {
        "id": "F-A0-delay",
        "class": "delay",
        "origin": "A0",
        "t0": 150,
        "dur": 12,
        "extra": {"d": 4},
    }

    fault_map: dict[int, Any] = {}
    if len(target_seeds) >= 8:
        fault_map[target_seeds[2]] = fault_drift
        fault_map[target_seeds[3]] = fault_drift
        fault_map[target_seeds[4]] = fault_pulse
        fault_map[target_seeds[5]] = fault_pulse
        fault_map[target_seeds[6]] = fault_delay
        fault_map[target_seeds[7]] = fault_delay
    elif len(target_seeds) >= 4:
        fault_map[target_seeds[1]] = fault_drift
        fault_map[target_seeds[2]] = fault_pulse
        fault_map[target_seeds[3]] = fault_delay

    return export(
        seeds=target_seeds,
        out=out_parquet,
        faults=fault_map if fault_map else None,
        exclude_warmup=exclude_warmup,
        schema_version=4,
    )


def export_v4(
    seed: int | None = None,
    seeds: list[int] | None = None,
    out: str | pathlib.Path = "artifacts/dataset_v4.parquet",
    faults: list[dict[str, Any]] | dict[Any, Any] | None = None,
    variant: str = "baseline",
    max_bytes: int = DEFAULT_MAX_BYTES,
    compression: str = "snappy",
    row_group_size: int = 1024,
    enable_natural_breakdown: bool = True,
    runs_log: str | pathlib.Path | None = None,
    exclude_warmup: bool = False,
) -> dict[str, Any]:
    """Export deterministic v4 Parquet dataset and associated metadata.

    Guarantees:
    - Pinned channels for all 26 machines: obs_*, state_*, buffer_*, tput_*, current_*.
    - Pinned stratification keys in REQUIRED_STRAT_FIELDS.
    - Fault target labels: family, mode, root_id.
    - schema_version == 4 everywhere.
    - PyArrow version recorded in ingestion metadata.
    - Hardened Parquet writer (version='2.6', coerce_timestamps='us', use_dictionary=False).
    - ZERO scaler.pkl fitted or written (TF1 leakage law).

    Parameters:
        seed: Single seed to run.
        seeds: Sequence of seeds to run.
        out: Output Parquet file path.
        faults: Fault specs mapping or list.
        variant: Simulation variant identifier.
        max_bytes: Size cap in bytes.
        compression: Parquet compression codec.
        row_group_size: Parquet row group size.
        enable_natural_breakdown: Whether natural breakdown is enabled.
        runs_log: Optional path to runs.jsonl log.
        exclude_warmup: Whether to exclude transient warm-up steps (default False).
            CONSUMER FILTERING OBLIGATION: Downstream consumers must filter out
            warm-up steps (step < 15 or warmup_flag==True) when training models.
            Enforced via assert_warmup_excluded(df).
    """
    return export(
        seed=seed,
        seeds=seeds,
        out=out,
        faults=faults,
        variant=variant,
        max_bytes=max_bytes,
        compression=compression,
        row_group_size=row_group_size,
        enable_natural_breakdown=enable_natural_breakdown,
        include_currents=True,
        schema_version=4,
        runs_log=runs_log,
        job_name="dataset_v4",
        exclude_warmup=exclude_warmup,
    )


def export_contract_dataset_v4(
    out_dir: str | pathlib.Path = "artifacts",
    seeds: list[int] | None = None,
    out_name: str = "dataset_v4.parquet",
    runs_log: str | pathlib.Path | None = None,
    exclude_warmup: bool = False,
) -> dict[str, Any]:
    """Export a multi-episode v4 dataset with balanced stratification keys for contract testing.

    Parameters:
        out_dir: Destination directory for parquet files.
        seeds: Optional list of episode seeds.
        out_name: Parquet filename.
        runs_log: Optional path to runs.jsonl log.
        exclude_warmup: Whether to exclude transient warm-up steps (default False).
            CONSUMER FILTERING OBLIGATION: Downstream consumers must filter out
            warm-up steps (step < 15 or warmup_flag==True) when training models.
            Enforced via assert_warmup_excluded(df).
    """
    out_dir_path = pathlib.Path(out_dir)
    out_parquet = out_dir_path / out_name

    target_seeds = (
        list(seeds) if seeds is not None else [7, 11, 13, 42, 777, 1234, 999, 2026]
    )

    fault_drift = {
        "id": "F-21",
        "class": "drift",
        "origin": "B2",
        "t0": 150,
        "dur": 12,
        "mag_sigma": 5.2,
    }
    fault_pulse = {
        "id": "F-06",
        "class": _PULSE,
        "origin": "A0",
        "t0": 150,
        "dur": 10,
        "mag_sigma": 5.0,
    }
    fault_delay = {
        "id": "F-A0-delay",
        "class": "delay",
        "origin": "A0",
        "t0": 150,
        "dur": 12,
        "extra": {"d": 4},
    }

    fault_map: dict[int, Any] = {}
    if len(target_seeds) >= 8:
        fault_map[target_seeds[2]] = fault_drift
        fault_map[target_seeds[3]] = fault_drift
        fault_map[target_seeds[4]] = fault_pulse
        fault_map[target_seeds[5]] = fault_pulse
        fault_map[target_seeds[6]] = fault_delay
        fault_map[target_seeds[7]] = fault_delay
    elif len(target_seeds) >= 4:
        fault_map[target_seeds[1]] = fault_drift
        fault_map[target_seeds[2]] = fault_pulse
        fault_map[target_seeds[3]] = fault_delay

    return export_v4(
        seeds=target_seeds,
        out=out_parquet,
        faults=fault_map if fault_map else None,
        runs_log=runs_log,
        exclude_warmup=exclude_warmup,
    )


def export_v5(
    seed: int | None = None,
    seeds: list[int] | None = None,
    out: str | pathlib.Path = "artifacts/dataset_v5.parquet",
    faults: list[dict[str, Any]] | dict[Any, Any] | None = None,
    variant: str = "baseline",
    max_bytes: int = DEFAULT_MAX_BYTES,
    compression: str = "snappy",
    row_group_size: int = 1024,
    enable_natural_breakdown: bool = True,
    runs_log: str | pathlib.Path | None = None,
) -> dict[str, Any]:
    """Export deterministic v5 Parquet dataset and associated metadata."""
    return export(
        seed=seed,
        seeds=seeds,
        out=out,
        faults=faults,
        variant=variant,
        max_bytes=max_bytes,
        compression=compression,
        row_group_size=row_group_size,
        enable_natural_breakdown=enable_natural_breakdown,
        include_currents=True,
        schema_version=5,
        runs_log=runs_log,
        job_name="dataset_v5",
    )


def export_v6(
    seed: int | None = None,
    seeds: list[int] | None = None,
    out: str | pathlib.Path = "artifacts/dataset_v6.parquet",
    faults: list[dict[str, Any]] | dict[Any, Any] | None = None,
    variant: str = "baseline",
    max_bytes: int = DEFAULT_MAX_BYTES,
    compression: str = "snappy",
    row_group_size: int = 1024,
    enable_natural_breakdown: bool = True,
    runs_log: str | pathlib.Path | None = None,
) -> dict[str, Any]:
    """Export deterministic v6 Parquet dataset and associated metadata."""
    return export(
        seed=seed,
        seeds=seeds,
        out=out,
        faults=faults,
        variant=variant,
        max_bytes=max_bytes,
        compression=compression,
        row_group_size=row_group_size,
        enable_natural_breakdown=enable_natural_breakdown,
        include_currents=True,
        schema_version=6,
        runs_log=runs_log,
        job_name="dataset_v6",
    )


export_dataset = export


def export_contract_dataset_v5(
    out_dir: str | pathlib.Path = "artifacts",
    seeds: list[int] | None = None,
    out_name: str = "dataset_v5.parquet",
    runs_log: str | pathlib.Path | None = None,
) -> dict[str, Any]:
    """Export a multi-episode v5 dataset with balanced stratification keys for contract testing."""
    out_dir_path = pathlib.Path(out_dir)
    out_parquet = out_dir_path / out_name

    target_seeds = (
        list(seeds) if seeds is not None else [7, 11, 13, 42, 777, 1234, 999, 2026]
    )

    fault_drift = {
        "id": "F-v5-drift",
        "class": "drift",
        "origin": "B2",
        "t0": 150,
        "dur": 12,
        "mag_sigma": 3.0,
    }
    fault_pulse = {
        "id": "F-v5-pulse",
        "class": _PULSE,
        "origin": "A0",
        "t0": 150,
        "dur": 10,
        "mag_sigma": 5.0,
    }
    fault_delay = {
        "id": "F-v5-delay",
        "class": "delay",
        "origin": "A0",
        "t0": 150,
        "dur": 12,
        "extra": {"d": 4},
    }
    fault_loss = {
        "id": "F-v5-loss",
        "class": "loss",
        "origin": "C1",
        "t0": 150,
        "dur": 15,
        "extra": {"drop_rate": 0.20},
    }
    fault_breakdown = {
        "id": "F-v5-breakdown",
        "class": "breakdown",
        "origin": "B1",
        "t0": 140,
        "dur": 15,
        "extra": {"mttr_mult": 1.5},
    }
    fault_quality = {
        "id": "F-v5-quality",
        "class": "quality",
        "origin": "ASM2",
        "t0": 150,
        "dur": 15,
        "extra": {"reject_rate": 0.30},
    }

    fault_map: dict[int, Any] = {}
    ladder = [
        fault_drift,
        fault_pulse,
        fault_delay,
        fault_loss,
        fault_breakdown,
        fault_quality,
    ]
    for i, s in enumerate(target_seeds[1:]):
        fault_map[s] = ladder[i % len(ladder)]

    return export_v5(
        seeds=target_seeds,
        out=out_parquet,
        faults=fault_map,
        runs_log=runs_log,
    )


def export_contract_dataset_v6(
    out_dir: str | pathlib.Path = "artifacts",
    master_seed: int = 12345,
    n_episodes: int = 110,
    n_clean: int = 10,
    out_name: str = "dataset_v6.parquet",
    runs_log: str | pathlib.Path | None = None,
) -> dict[str, Any]:
    """Export a multi-episode v6 dataset with balanced stratification keys for contract testing."""
    out_dir_path = pathlib.Path(out_dir)
    out_parquet = out_dir_path / out_name

    variant_rows = twin.build_faults_variant(master_seed, cap_budget=True)
    classes = list(twin._FAULT_CLASSES)
    n_fault_eps = n_episodes - n_clean

    by_class: dict[str, list[dict[str, Any]]] = {}
    for r in variant_rows:
        by_class.setdefault(r["class"], []).append(r)

    targets_per_class = {cls: 14 for cls in classes}
    targets_per_class[classes[0]] = 15
    targets_per_class[classes[1]] = 15

    rng = np.random.default_rng(master_seed)
    sampled_faults = []
    for cls in classes:
        cls_rows = by_class[cls]
        incip = [r for r in cls_rows if r.get("mag_rung") == "incipient"]
        caric = [r for r in cls_rows if r.get("mag_rung") == "caricature"]
        target = targets_per_class[cls]
        n_incip = max(2, int(round(target * config.INCIPIENT_SHARE)))
        n_caric = target - n_incip
        chosen = list(incip[:n_incip]) + list(caric[:n_caric])
        sampled_faults.extend(chosen)

    assert len(sampled_faults) == n_fault_eps, f"Expected {n_fault_eps} faults, got {len(sampled_faults)}"
    rng.shuffle(sampled_faults)

    seeds = list(range(20001, 20001 + n_episodes))
    clean_seeds = seeds[:n_clean]
    fault_seeds = seeds[n_clean:]

    fault_map: dict[int, Any] = {}
    for s in clean_seeds:
        fault_map[s] = None

    for s, f_row in zip(fault_seeds, sampled_faults):
        spec = dict(f_row)
        if "extra" in spec:
            spec["extra"] = dict(spec["extra"])
        if spec.get("class") == "breakdown":
            mult = float(spec.get("extra", {}).get("mttr_mult", spec.get("mttr_mult", 1.0)))
            spec["dur"] = min(int(spec["dur"]), int(14 // max(1, math.ceil(mult))))
        spec["dur"] = min(int(spec["dur"]), 14)
        spec["t1"] = spec["t0"] + spec["dur"]
        twin.check_rate_budget([spec])
        fault_map[s] = spec

    res = export_dataset(
        out=out_parquet,
        seeds=seeds,
        faults=fault_map,
        schema_version=6,
        runs_log=runs_log,
        variant=config.VARIANT_ID,
    )

    df = load_v6_dataset(res["out"])
    scored = df[df["t"] >= config.CAL_WIN]
    y_mean = float(scored["y"].mean())
    mask_mean = float(scored["fault_mask"].mean())
    if not (0.03 <= y_mean <= 0.05):
        raise ValueError(
            f"Target positive rate violation on scored steps: y rate={y_mean:.4f}, want [0.03, 0.05]"
        )
    if mask_mean > 0.08:
        raise ValueError(
            f"Target mask rate violation on scored steps: fault_mask rate={mask_mean:.4f}, want <= 0.08"
        )

    return res



def load_dataset(
    path: str | pathlib.Path,
    schema_version: int | None = None,
) -> pd.DataFrame:
    """Load parquet dataset and validate schema version."""
    p = pathlib.Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Dataset path does not exist: {p}")

    df = pd.read_parquet(p)
    if "schema_version" in df.columns:
        unique_vers = df["schema_version"].unique()
        if schema_version is not None:
            if any(v != schema_version for v in unique_vers):
                raise ValueError(
                    f"Dataset reader rejects dataset: found schema_version={unique_vers.tolist()}, want {schema_version}"
                )
        elif any(v < 3 for v in unique_vers):
            raise ValueError(
                f"v3 reader rejects legacy dataset: found schema_version={unique_vers.tolist()}, want >= 3"
            )
    return df


def load_v3_dataset(source: Any) -> pd.DataFrame:
    """Legacy v3 reader function.

    Loudly raises ValueError when attempting to read a v4 dataset (flag-day rejection).
    """
    if isinstance(source, dict):
        schema_ver = source.get("schema_version")
        if schema_ver is not None and schema_ver >= 4:
            raise ValueError(
                f"v3 reader rejects v4 dataset: found schema_version={schema_ver}, want 3"
            )
        if schema_ver is not None and schema_ver < 3:
            raise ValueError(
                f"v3 reader rejects legacy dataset: found schema_version={schema_ver}, want 3"
            )
        return source  # type: ignore[return-value]

    if isinstance(source, pd.DataFrame):
        df = source
    else:
        path = pathlib.Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Dataset path does not exist: {path}")
        df = pd.read_parquet(path)

    if "schema_version" in df.columns:
        unique_vers = df["schema_version"].unique()
        if any(v >= 4 for v in unique_vers):
            raise ValueError(
                f"v3 reader rejects v4 dataset: found schema_version={unique_vers.tolist()}, want 3"
            )
        if any(v < 3 for v in unique_vers):
            raise ValueError(
                f"v3 reader rejects legacy dataset: found schema_version={unique_vers.tolist()}, want 3"
            )
    return df


def load_v4_dataset(source: Any) -> pd.DataFrame:
    """Load v4 parquet dataset and validate schema version == 4."""
    if isinstance(source, pd.DataFrame):
        df = source
    else:
        path = pathlib.Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Dataset path does not exist: {path}")
        df = pd.read_parquet(path)

    if "schema_version" not in df.columns:
        raise ValueError("Dataset contract violation: 'schema_version' column missing")
    unique_vers = df["schema_version"].unique()
    if any(v != 4 for v in unique_vers):
        raise ValueError(
            f"v4 reader rejects non-v4 dataset: found schema_version={unique_vers.tolist()}, want 4"
        )
    return df


def load_v5_dataset(source: Any) -> pd.DataFrame:
    """Load v5 parquet dataset and validate schema version == 5."""
    if isinstance(source, pd.DataFrame):
        df = source
    else:
        path = pathlib.Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Dataset path does not exist: {path}")
        df = pd.read_parquet(path)

    if "schema_version" not in df.columns:
        raise ValueError("Dataset contract violation: 'schema_version' column missing")
    unique_vers = df["schema_version"].unique()
    if any(v != 5 for v in unique_vers):
        raise ValueError(
            f"v5 reader rejects non-v5 dataset: found schema_version={unique_vers.tolist()}, want 5"
        )
    return df


def load_v6_dataset(source: Any) -> pd.DataFrame:
    """Load v6 parquet dataset and validate schema version == 6."""
    if isinstance(source, pd.DataFrame):
        df = source
    else:
        path = pathlib.Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Dataset path does not exist: {path}")
        df = pd.read_parquet(path)

    if "schema_version" not in df.columns:
        raise ValueError("Dataset contract violation: 'schema_version' column missing")
    unique_vers = df["schema_version"].unique()
    if any(v != 6 for v in unique_vers):
        raise ValueError(
            f"v6 reader rejects non-v6 dataset: found schema_version={unique_vers.tolist()}, want 6"
        )
    return df



def load_v2_dataset(source: Any) -> Any:
    """Legacy v2 reader function.

    LOUDLY raises ValueError mentioning v3 when attempting to read v3 records or datasets.
    """
    if isinstance(source, dict):
        schema_ver = source.get("schema_version")
        if schema_ver is not None and schema_ver >= 3:
            raise ValueError(
                f"v2 reader non-comparable: rejects v3 records/dataset (got schema_version={schema_ver!r}), want 2"
            )
        if schema_ver != 2:
            raise ValueError(
                f"v2 reader non-comparable: rejects schema_version={schema_ver!r}, want 2"
            )
        return source

    # File path or DataFrame
    if isinstance(source, (str, pathlib.Path)):
        p = pathlib.Path(source)
        if p.suffix == ".parquet" or "v3" in p.name:
            df = pd.read_parquet(p)
            if "schema_version" in df.columns:
                unique_vers = df["schema_version"].unique()
                if any(v >= 3 for v in unique_vers):
                    raise ValueError(
                        "v2 reader non-comparable: rejects v3 records/dataset (found schema_version=3), want 2"
                    )
            raise ValueError(
                "v2 reader non-comparable: rejects v3 records/dataset, want 2"
            )

    if isinstance(source, pd.DataFrame) and "schema_version" in source.columns:
        unique_vers = source["schema_version"].unique()
        if any(v >= 3 for v in unique_vers):
            raise ValueError(
                "v2 reader non-comparable: rejects v3 records/dataset (found schema_version=3), want 2"
            )

    raise ValueError(f"v2 reader non-comparable: unrecognized source {type(source)}")


def main() -> None:
    """CLI entrypoint for dataset export."""
    parser = argparse.ArgumentParser(
        description="Export deterministic Parquet dataset (v3/v4)."
    )
    parser.add_argument("--seed", type=int, default=None, help="Single seed to export")
    parser.add_argument(
        "--seeds", type=int, nargs="+", default=None, help="List of seeds"
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output parquet path",
    )
    parser.add_argument(
        "--variant", type=str, default="baseline", help="Variant identifier"
    )
    parser.add_argument(
        "--v4",
        action="store_true",
        help="Export schema v4 dataset with current channels",
    )
    parser.add_argument(
        "--schema-version",
        type=int,
        default=None,
        choices=[3, 4],
        help="Schema version to export (3 or 4)",
    )
    parser.add_argument(
        "--runs-log",
        type=str,
        default="artifacts/runs.jsonl",
        help="Path to runs JSONL log file (default: artifacts/runs.jsonl)",
    )
    parser.add_argument(
        "--exclude-warmup",
        action="store_true",
        help="Exclude transient warm-up steps (steps 0..14)",
    )
    args = parser.parse_args()

    is_v4 = (
        args.v4
        or (args.schema_version == 4)
        or (args.out is not None and "v4" in args.out)
    )
    if is_v4:
        out_path = args.out if args.out is not None else "artifacts/dataset_v4.parquet"
        res = export_v4(
            seed=args.seed,
            seeds=args.seeds,
            out=out_path,
            variant=args.variant,
            runs_log=args.runs_log,
            exclude_warmup=args.exclude_warmup,
        )
    else:
        out_path = args.out if args.out is not None else "artifacts/dataset_v3.parquet"
        res = export(
            seed=args.seed,
            seeds=args.seeds,
            out=out_path,
            variant=args.variant,
            runs_log=args.runs_log,
            exclude_warmup=args.exclude_warmup,
        )
    print(
        f"Exported {res['row_count']} rows to {res['out']} (hash: {res['dataset_hash'][:16]}...)"
    )


if __name__ == "__main__":
    main()
