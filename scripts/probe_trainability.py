#!/usr/bin/env python3
"""Trainability probe: does schema-v6 carry per-family signal a model could learn?

Signal-existence check only (train-AUC = upper bound, NOT a model claim):
per fault family, LogisticRegression on a few structural features over
fault-window steps vs clean-episode steps. Compares against obs-only baseline.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from src import config, dataset_export, twin
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.metrics import roc_auc_score  # type: ignore[import-untyped]

FAMILIES = ["drift", "bias", "delay", "loss", "breakdown", "quality", "spike"]
STRUCT_FEATURES = [
    "cycle_lag",
    "down_run",
    "dwell_steps",
    "stale_hold_run",
    "reject_flag_count",
    "degrade_flag_count",
    "buffer_occ",
    "state_hist_delta",
]


def family_auc(
    df: pd.DataFrame, family: str, features: list[str], root_col: str = "root_id_step"
) -> float | None:
    """Train-AUC (upper bound) for one family: its fault windows vs all clean steps."""
    fault = df[(df["fault_family"] == family) & (df["y"] == 1)]
    clean = df[df["y"] == 0]
    if len(fault) < 5 or len(clean) < 5:
        return None
    use = [c for c in features if c in df.columns]
    X = pd.concat([fault[use], clean[use]]).to_numpy(dtype=float)
    y = np.array([1] * len(fault) + [0] * len(clean))
    clf = LogisticRegression(max_iter=500)
    clf.fit(X, y)
    return float(roc_auc_score(y, clf.decision_function(X)))


def main(argv: list[str] | None = None) -> int:
    """CLI: export tiny v6 set (2 clean + 1 fault/family), probe per-family AUC."""
    parser = argparse.ArgumentParser(description="v6 trainability probe")
    parser.add_argument("--out", default="artifacts/trainability_probe.json")
    parser.add_argument("--master-seed", type=int, default=777)
    args = parser.parse_args(argv)

    start = time.perf_counter()
    rng = np.random.default_rng(args.master_seed)
    clean_seeds = [401, 402]
    fault_specs: dict[int, dict] = {}
    seed = 500
    origins = ["A2", "B2", "C2", "A8", "B1", "ASM2", "A0"]
    for fam, orig in zip(FAMILIES, origins):
        spec = {"id": f"P-{fam}", "class": fam, "origin": orig, "t0": 150, "dur": 8}
        if fam == "spike":
            spec["mag_sigma"] = 5.0
        elif fam == "drift":
            spec["mag_sigma"] = 5.0
        fault_specs[seed] = spec
        seed += 1
    res = dataset_export.export_v6(
        seeds=clean_seeds + sorted(fault_specs),
        out="artifacts/probe_v6.parquet",
        faults=fault_specs,
    )
    df = dataset_export.load_v6_dataset(res["out"])
    df = df[df["step"] >= config.CAL_WIN]
    report = {"families": {}, "n_rows": len(df)}
    for fam in FAMILIES:
        auc_struct = family_auc(df, fam, STRUCT_FEATURES)
        auc_obs = family_auc(df, fam, [f"obs_{origins[FAMILIES.index(fam)]}"])
        report["families"][fam] = {"auc_struct": auc_struct, "auc_obs_only": auc_obs}
    report["wall_seconds"] = time.perf_counter() - start
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=float), encoding="utf-8")
    for fam, vals in report["families"].items():
        print(f"{fam:10s} struct={vals['auc_struct']:.3f} obs-only={vals['auc_obs_only']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
