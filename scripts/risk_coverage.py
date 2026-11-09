#!/usr/bin/env python3
"""Risk-vs-coverage curve from OOF window scores (replaces hand-tuned gates).

Confidence = |score - 0.5| * 2 (distance from the decision boundary).
For each threshold tau: coverage = fraction with confidence >= tau,
risk = error rate on covered windows. Output picks the operating point
at target risk; callers (diagnose battery, finalize) consume the JSON.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd


def risk_coverage(
    df: pd.DataFrame, n_grid: int = 21
) -> list[tuple[float, float]]:
    """Return [(coverage, risk)] from tau=0 (all) to tau=1 (most sure)."""
    s = np.asarray(df["score"], dtype=float) if len(df) else np.array([])
    y = np.asarray(df["y"], dtype=int) if len(df) else np.array([])
    if len(s) == 0:
        return []
    conf = np.abs(s - 0.5) * 2.0
    pred = (s >= 0.5).astype(int)
    out = []
    for tau in np.linspace(0.0, 1.0, n_grid):
        m = conf >= tau
        cov = float(m.mean())
        risk = float((pred[m] != y[m]).mean()) if m.any() else 0.0
        out.append((round(cov, 4), round(risk, 4)))
    return out


def pick_point(
    rc: list[tuple[float, float]], max_risk: float = 0.05
) -> tuple[float, float]:
    """Highest-coverage point within the risk budget (coverage, tau)."""
    n = len(rc)
    for i, (cov, risk) in enumerate(rc):
        if risk <= max_risk:
            return (cov, round(i / max(1, n - 1), 4))
    return (rc[-1][0], 1.0)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="risk-coverage from OOF parquet")
    ap.add_argument("--oof", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--max-risk", type=float, default=0.05)
    args = ap.parse_args(argv)
    df = pd.read_parquet(args.oof)
    rc = risk_coverage(df)
    cov, tau = pick_point(rc, args.max_risk)
    res = {"curve": rc, "operating": {"coverage": cov, "tau": tau, "max_risk": args.max_risk}}
    print(f"coverage={cov:.3f} tau={tau:.3f} at risk<={args.max_risk} (MEASURED)")
    if args.out:
        pathlib.Path(args.out).write_text(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
