"""Fit Task-7 calibration artifact (teacher-window T + Platt, PRISSUE-61).

Reads artifacts/oof_identity.parquet (teacher window OOF, current battery).
Reuses src/confidence fns only (+ the serve-time margin helper from
src.calibration_artifact so fit/serve margins are byte-identical).
Never imports src/calibrate (twin acquisition) or detector code.

Served tau is FROZEN at 0.739 (11-11 held-5 operating point,
docs/DIAGNOSIS_QUALITY.md transfer row); VERIFY transfer on current
exclude-held held-5 windows is measured here and recorded in the
artifact. Writes artifacts/calibration.json {T, a, b, tau, ...}.
"""

import hashlib
import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from src import config
from src.calibration_artifact import scaled_margin
from src.confidence import pick_threshold, platt_fit, platt_predict

HELD5 = ("ASM1", "ASM2", "B7P", "B9", "C6")
T_FROZEN = 2.58  # 11-11 teacher fit (DIAGNOSIS_QUALITY: Calibration)
TAU_FROZEN = 0.739  # 11-11 held-5 operating point @ risk<=0.3
RISK_TARGET = 0.3
PARQUET = "artifacts/oof_identity.parquet"


def _margins_tscaled(P: np.ndarray, T: float) -> np.ndarray:
    out = np.empty(P.shape[0])
    for i, row in enumerate(P):
        probs = {j: float(v) for j, v in enumerate(row)}
        out[i], _ = scaled_margin(probs, T)
    return out


def main() -> dict:
    with open(PARQUET, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    oof = pd.read_parquet(PARQUET)
    mcols = [c for c in oof.columns if c.startswith("proba_") and c != "proba_none"]
    P = oof[mcols].to_numpy(dtype=float)
    is_fault = oof["y"].to_numpy() == 1
    is_held = oof["root"].isin(list(HELD5)).to_numpy()
    correct = (
        (oof["pred"].to_numpy(dtype=str) == oof["root"].to_numpy(dtype=str)) & is_fault
    ).astype(int)

    margins = _margins_tscaled(P, T_FROZEN)
    tr = is_fault & ~is_held
    a, b = platt_fit(margins[tr], correct[tr])
    tau_refit = pick_threshold(platt_predict(margins[tr], a, b), correct[tr],
                               RISK_TARGET)
    # VERIFY transfer: frozen tau on exclude-held held-5 fault windows.
    conf_h = platt_predict(margins[is_fault & is_held], a, b)
    corr_h = correct[is_fault & is_held]
    cov_m = conf_h >= TAU_FROZEN
    transfer = {
        "slice": "exclude-held held-5 fault windows",
        "n": len(corr_h),
        "tau_applied": TAU_FROZEN,
        "coverage": float(cov_m.mean()) if len(corr_h) else 0.0,
        "risk": float(1 - corr_h[cov_m].mean()) if cov_m.sum() else 1.0,
        "n_covered": int(cov_m.sum()),
        "budget": RISK_TARGET,
        "verdict": "SERVE",
    }
    transfer["verdict"] = ("SERVE" if transfer["risk"] <= RISK_TARGET
                            else "RE-PICK-or-RE-SCOPE")

    artifact = {
        "T": T_FROZEN,
        "a": float(a),
        "b": float(b),
        "tau": TAU_FROZEN,
        "risk_target": RISK_TARGET,
        "coverage": transfer["coverage"],
        "margin_def": "top1-top2 of T-scaled candidate probs via p^(1/T) "
                      "renormalization (src.calibration_artifact.scaled_margin); "
                      "fit on teacher window probas, served on rank_nodes "
                      "possibility probs",
        "fit": {
            "n": int(tr.sum()),
            "held": "ASM1/ASM2/B7P/B9/C6",
            "tau_refit_at_budget": float(tau_refit),
            "input": PARQUET,
            "sha256": sha,
        },
        "lineage_11_11": {
            "T": 2.58,
            "tau": 0.739,
            "coverage": 0.337,
            "risk": 0.300,
            "n": 8945,
            "source": "docs/DIAGNOSIS_QUALITY.md transfer row (teacher windows)",
        },
        "verify": transfer,
        "scope_note": "Platt is monotone in margin (a>0): the gate is exactly "
                      "a margin threshold with a probabilistic reading. "
                      "Incident-level absolute calibration on heuristic "
                      "margins is not claimed (research R2). Never serve the "
                      "ranker tau=0.187 here (different space, Task 75).",
        "code_version": config.CODE_VERSION,
    }
    with open("artifacts/calibration.json", "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
    print(f"T={T_FROZEN} a={a:.4f} b={b:.4f} tau_refit={tau_refit:.4f} "
          f"frozen tau={TAU_FROZEN}")
    print(f"VERIFY transfer: coverage={transfer['coverage']:.3f} "
          f"risk={transfer['risk']:.3f} (n={transfer['n']}) -> "
          f"{transfer['verdict']}")
    print("saved artifacts/calibration.json")
    return artifact


if __name__ == "__main__":
    main()
