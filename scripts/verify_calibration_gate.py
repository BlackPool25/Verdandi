"""VERIFY gate (Task 7, Step 1b): re-measure tau=0.739 on exclude-held data.

Reads artifacts/oof_identity.parquet (teacher window OOF, current battery) +
artifacts/ranker-calibration.json (recorded exclude-held gate lineage).
Numpy-only, CPU-light, read-only. Prints VERIFY verdict; exit 0 always
(verdict is evidence for the implementer, not a gate on itself).
"""

import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from src.confidence import pick_threshold, platt_fit, platt_predict

HELD5 = ("ASM1", "ASM2", "B7P", "B9", "C6")
RISK_TARGET = 0.3
TAU_SHIP_CANDIDATE = 0.739


def _t_scaled_margins(P, T):
    w = np.power(np.clip(P, 1e-12, 1.0), 1.0 / T)
    w /= w.sum(axis=1, keepdims=True)
    s = np.sort(w, axis=1)
    return s[:, -1] - s[:, -2]


def main():
    oof = pd.read_parquet("artifacts/oof_identity.parquet")
    mcols = [c for c in oof.columns if c.startswith("proba_") and c != "proba_none"]
    P = oof[mcols].to_numpy(dtype=float)
    is_fault = oof["y"].to_numpy() == 1
    is_held = oof["root"].isin(list(HELD5)).to_numpy()
    correct = (
        (oof["pred"].to_numpy(dtype=str) == oof["root"].to_numpy(dtype=str)) & is_fault
    ).astype(int)

    with open("artifacts/ranker-calibration.json", encoding="utf-8") as f:
        rec = json.load(f)["exclude_held5"]["gate"]
    print(f"recorded exclude-held gate: a={rec['a']:.4f} b={rec['b']:.4f} "
          f"tau={rec['tau']:.4f} held5_risk={rec['held5_risk']:.3f} "
          f"held5_cov={rec['held5_coverage']:.3f} (n={rec['held5_n']})")

    out = {}
    for T, tag in ((1.0, "raw"), (2.58, "T=2.58")):
        margins = _t_scaled_margins(P, T) if T != 1.0 else (
            np.sort(P, axis=1)[:, -1] - np.sort(P, axis=1)[:, -2])
        tr = is_fault & ~is_held
        a, b = platt_fit(margins[tr], correct[tr])
        tau_fit = pick_threshold(platt_predict(margins[tr], a, b), correct[tr],
                                 RISK_TARGET)
        conf_h = platt_predict(margins[is_fault & is_held], a, b)
        corr_h = correct[is_fault & is_held]
        for tau, ttag in ((TAU_SHIP_CANDIDATE, "tau=0.739"), (tau_fit, "tau=refit")):
            cov_m = conf_h >= tau
            cov = float(cov_m.mean()) if len(conf_h) else 0.0
            risk = float(1 - corr_h[cov_m].mean()) if cov_m.sum() else 1.0
            print(f"[{tag}] {ttag}={tau:.4f} on exclude-held held-5 fault windows "
                  f"(n={len(corr_h)}): coverage={cov:.3f} risk={risk:.3f} "
                  f"n_covered={int(cov_m.sum())}")
            out[f"{tag}/{ttag}"] = {"tau": float(tau), "coverage": cov,
                                    "risk": risk, "n": len(corr_h),
                                    "n_covered": int(cov_m.sum())}
        out[f"{tag}/fit"] = {"a": float(a), "b": float(b), "tau": float(tau_fit)}
    # Reproducibility check vs recorded raw-margin fit.
    rf = out["raw/fit"]
    print(f"refit raw: a={rf['a']:.4f} (rec {rec['a']:.4f}) b={rf['b']:.4f} "
          f"(rec {rec['b']:.4f}) tau={rf['tau']:.4f} (rec {rec['tau']:.4f})")
    r739 = out["raw/tau=0.739"]["risk"]
    verdict = ("SERVE-IF-RECORD" if r739 <= RISK_TARGET
               else "RE-PICK-or-RE-SCOPE (risk over 0.3 budget)")
    print(f"VERIFY verdict on tau=0.739 transfer: risk={r739:.3f} -> {verdict}")
    with open("artifacts/verify-calibration.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print("saved artifacts/verify-calibration.json")


if __name__ == "__main__":
    main()
