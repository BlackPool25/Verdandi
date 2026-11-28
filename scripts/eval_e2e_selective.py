"""Measured E2E selective risk at the served gate (W-e2e66, Shreyas/PRISSUE-66).

Replaces the DERIVED abstain-gated pooled number (0.214 coverage @ ~0.70
selective accuracy, derived from window-level transfer: (2665/4200) x 0.337)
with an EPISODE-level measurement: the live gate in `src.diagnose`
(`diagnose_incident` + `load_calibrator`, tau=0.739 served point) is run over
recorded fault episodes from the frozen battery. Nothing about calibration
is reimplemented here -- the calibrator dict comes from
`src.calibration_artifact.load_calibrator()` (default
`artifacts/calibration.json`).

Trigger honesty (read this before quoting numbers):
  * The frozen detector model file is absent from this tree, so detector
    triggers cannot be replayed. Trigger is the ORACLE first fault tick
    (first `fault_mask == 1` step) per episode.
  * What is MEASURED: gate coverage + selective accuracy CONDITIONAL on
    detection (perfect-retrieval assumption). Full-E2E composition with the
    separately MEASURED retrieval (retrained frozen sentinel 0.800 @ thr 0.6
    + 2-of-3, n=4200/600, DIAGNOSIS_QUALITY.md) is printed as COMPOSED, never
    as end-to-end measured.
  * Scores are measured from the frame (max |prefix-z| over the
    post-trigger window, same math as scripts/report_incident.measure_scores),
    never invented. GT columns (root_id/fault_mask/fault_family) are used
    only for trigger + scoring, i.e. evaluation-only per src/diagnose.py.

Inputs used (existing artifacts/caches only, NO battery generation):
  * artifacts/m0b_mass_*.parquet (frozen T~285 battery, read-only)
  * artifacts/calibration.json via load_calibrator (live gate)
  * src/diagnose.py diagnose_incident (live gate, not copied)

Usage: python scripts/eval_e2e_selective.py [--n 200] [--seed 0] [--out JSON]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from src.calibration_artifact import load_calibrator

# Separately MEASURED retrieval on the same battery class (frozen T=300,
# 4200 fault + 600 clean): retrained frozen sentinel, thr 0.6 + 2-of-3,
# clean-fire 0.032. Composition only -- not re-measured here.
RETRIEVAL_MEASURED = 0.800
RETRIEVAL_LINEAGE = (
    "retrained frozen sentinel thr 0.6 + 2-of-3, n=4200/600, "
    "docs/DIAGNOSIS_QUALITY.md retrieval table"
)


def default_tau() -> float:
    """Served gate point, read live from the calibrator artifact."""
    return float(load_calibrator()["tau"])


def select_trigger(g: pd.DataFrame) -> int | None:
    """Oracle trigger: first fault tick (evaluation-only GT use)."""
    if "fault_mask" not in g.columns or "step" not in g.columns:
        return None
    hit = g.loc[g["fault_mask"] == 1, "step"]
    return int(hit.min()) if len(hit) else None


def measure_scores(
    g: pd.DataFrame, obs_cols: list[str], diag: list[dict],
    trigger: int, window: int = 40,
) -> dict[str, float]:
    """Per-machine detection strength: max |prefix-z| over [trigger, +window).

    Measured from the frame (prefix median/MAD, exactly src.diagnose._znorm).
    """
    from src.diagnose import _znorm

    scores: dict[str, float] = {}
    for r in diag:
        col = f"obs_{r['machine']}"
        if col not in g.columns or "step" not in g.columns:
            scores[r["machine"]] = 0.0
            continue
        v = g[col].to_numpy(dtype=float)
        z = np.abs(_znorm(v))
        steps = g["step"].to_numpy()
        sel = (steps >= trigger) & (steps < trigger + window)
        scores[r["machine"]] = float(z[sel].max()) if sel.any() else 0.0
    return scores


def run_episode(
    g: pd.DataFrame,
    obs_cols: list[str],
    edges: dict[str, list[str]],
    truth_root: str,
    family: str,
    trigger: int,
    calibrator: dict,
) -> dict:
    """One episode through the LIVE gate. Returns covered/correct/reason."""
    from src.diagnose import diagnose_from_trigger, diagnose_incident

    kept = diagnose_from_trigger(g, obs_cols, trigger, back=16)
    scores = measure_scores(g, obs_cols, kept, trigger) if kept else None
    report = diagnose_incident(
        g, obs_cols, trigger, edges, seed=int(g["episode_id"].iloc[0]),
        fault_family=family or "unknown", scores=scores, calibrator=calibrator,
    )
    reason = report.get("abstain")
    root = report.get("root")
    covered = reason is None
    conf = (report.get("confidence") or {}).get("top1")
    return {
        "covered": bool(covered),
        "correct": bool(covered and root == truth_root),
        "reason": reason,
        "root": root,
        "truth": truth_root,
        "conf": (None if conf is None else float(conf)),
        "tau": float(calibrator.get("tau", float("nan"))),
    }


def aggregate(outcomes: list[dict]) -> dict:
    """Coverage + selective accuracy/risk + abstain histogram."""
    n = len(outcomes)
    n_cov = sum(1 for o in outcomes if o["covered"])
    coverage = (n_cov / n) if n else 0.0
    n_ok = sum(1 for o in outcomes if o["covered"] and o["correct"])
    if n_cov:
        sel_acc = n_ok / n_cov
        sel_risk = 1.0 - sel_acc
    else:
        sel_acc, sel_risk = None, None
    abst: dict[str, int] = {}
    for o in outcomes:
        if not o["covered"]:
            abst[str(o["reason"])] = abst.get(str(o["reason"]), 0) + 1
    return {
        "n": n,
        "n_covered": n_cov,
        "coverage": coverage,
        "selective_accuracy": sel_acc,
        "selective_risk": sel_risk,
        "abstain": abst,
    }


def sample_fault_episodes(pattern: str, n: int, seed: int) -> list[tuple[str, int]]:
    """Deterministic sample of fault episodes as (shard_path, episode_id).

    Column-projection scan only (episode_id + root_id); full frames are read
    later and only for sampled episodes' shards.
    """
    rng = np.random.default_rng(seed)
    eps: list[tuple[str, int]] = []
    for path in sorted(glob.glob(pattern)):
        ids = pd.read_parquet(path, columns=["episode_id", "root_id"])
        for ep, root in zip(ids["episode_id"].to_numpy(), ids["root_id"].to_numpy()):
            if str(root) != "none":
                eps.append((path, int(ep)))
    order = rng.permutation(len(eps))
    take = [eps[i] for i in order[:n]]
    take.sort()
    return take


def main(n_eps: int = 200, seed: int = 0, out: str | None = None) -> dict:
    from src.twin import _DOWNSTREAM_MACHINES

    edges = {k: list(v) for k, v in _DOWNSTREAM_MACHINES.items()}
    calibrator = load_calibrator()
    sample = sample_fault_episodes("artifacts/m0b_mass_*.parquet", n_eps, seed)
    by_shard: dict[str, list[int]] = {}
    for path, ep in sample:
        by_shard.setdefault(path, []).append(ep)
    frames: dict[int, pd.DataFrame] = {}
    for path, eps in by_shard.items():
        df = pd.read_parquet(path)
        for ep in eps:
            frames[ep] = df[df["episode_id"] == ep].sort_values("step").reset_index(drop=True)
    obs_cols = [c for c in next(iter(frames.values())).columns if c.startswith("obs_")]
    outcomes: list[dict] = []
    per_ep: list[dict] = []
    for _, ep in sample:
        g = frames[ep]
        trigger = select_trigger(g)
        if trigger is None:
            outcomes.append({"covered": False, "correct": False,
                             "reason": "no-fault-tick", "root": None,
                             "truth": None, "conf": None,
                             "tau": float(calibrator.get("tau", float("nan")))})
            continue
        truth = str(g["root_id"].mode().iloc[0])
        fam = str(g["family"].mode().iloc[0]) if "family" in g.columns else "unknown"
        o = run_episode(g, obs_cols, edges, truth, fam, trigger, calibrator)
        outcomes.append(o)
        per_ep.append({"ep": ep, **o})
    m = aggregate(outcomes)
    m["retrieval_measured"] = RETRIEVAL_MEASURED
    m["pooled_coverage_composed"] = RETRIEVAL_MEASURED * m["coverage"]
    m["lineage"] = {
        "n": m["n"], "seed": seed,
        "battery": "artifacts/m0b_mass_*.parquet (frozen, read-only)",
        "trigger": "oracle first fault_mask tick (perfect-retrieval assumption)",
        "gate": "live src.diagnose.diagnose_incident + load_calibrator()",
        "calibrator": {k: calibrator.get(k) for k in ("T", "a", "b", "tau", "risk_target")},
        "scores": "measured max|prefix-z| post-trigger window (not invented)",
        "retrieval_lineage": RETRIEVAL_LINEAGE,
        "episodes": [ep for _, ep in sample],
    }
    sel_acc = m["selective_accuracy"]
    sel_acc_s = "None" if sel_acc is None else f"{sel_acc:.3f}"
    sel_risk = m["selective_risk"]
    sel_risk_s = "None" if sel_risk is None else f"{sel_risk:.3f}"
    print(f"e2e-selective gate-conditional (MEASURED, n={m['n']} seed={seed}): "
          f"coverage={m['coverage']:.3f} selective-acc={sel_acc_s} "
          f"selective-risk={sel_risk_s} "
          f"tau={float(calibrator.get('tau')):.3f} abstain={m['abstain']}")
    print(f"e2e-selective pooled (COMPOSED, not E2E-measured): "
          f"{RETRIEVAL_MEASURED:.3f}(retrieval) x {m['coverage']:.3f}(gate) = "
          f"{m['pooled_coverage_composed']:.3f} coverage @ "
          f"{sel_acc_s} selective-acc")
    print("derived predecessor (window-level transfer, SUPERSEDED as E2E): "
          "0.214 coverage @ ~0.70 selective-acc")
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"summary": {k: v for k, v in m.items() if k != "lineage"},
                       "lineage": m["lineage"], "episodes": per_ep},
                      f, indent=2, sort_keys=True)
            f.write("\n")
        print(f"wrote {out}")
    return m


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="measured E2E selective risk (gate-conditional)")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    main(n_eps=args.n, seed=args.seed, out=args.out)
