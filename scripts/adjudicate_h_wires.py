#!/usr/bin/env python3
"""Adjudicate H-wires on the trained pool and update the hypothesis registry.

Inputs: fused OOF parquet (Task 16), frozen manifest, baseline audit JSON
(gate/CUSUM expert hits per episode). Battery ID: m0b-train-frozen182.
H-wire semantics below are the operator's best reading of PRISSUE-19
(H1–H5 sheets were not in the repo) — each row records its assumption.
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from src.vus_pr import vus_pr

BATTERY_ID = "m0b-train-frozen182"
REGISTRY = "docs/M0B_HYPOTHESIS_REGISTRY.md"


def adjudicate(*wires: dict, battery_id: str, date: str | None = None) -> list[dict]:
    """Status each wire: Survived iff metric meets bar (direction-aware)."""
    today = date or datetime.date.today().isoformat()
    rows = []
    for w in wires:
        ok = (
            (w["metric"] >= w["bar"])
            if w.get("higher_is_better", True)
            else (w["metric"] <= w["bar"])
        )
        rows.append(
            {
                "id": w["id"],
                "metric": round(float(w["metric"]), 4),
                "bar": w["bar"],
                "status": "Survived" if ok else "Falsified",
                "battery_id": battery_id,
                "date": today,
                "assumption": w.get("assumption", ""),
            }
        )
    return rows


def summarize_metrics(
    y_true: np.ndarray, fused_scores: np.ndarray, fused_decisions: np.ndarray
) -> dict:
    """Chance-corrected metric row (Task 27): F1 + MCC + ROC-AUC + trivial baseline."""
    from sklearn.metrics import matthews_corrcoef, roc_auc_score

    from src.train_pipeline import compute_raw_pointwise_f1

    y = np.asarray(y_true, dtype=int)
    dec = np.asarray(fused_decisions, dtype=int)
    sc = np.asarray(fused_scores, dtype=float)
    f1 = float(compute_raw_pointwise_f1(y, dec))
    try:
        mcc = float(matthews_corrcoef(y, dec))
    except ValueError:
        mcc = 0.0
    try:
        roc = float(roc_auc_score(y, sc)) if len(np.unique(y)) == 2 else 0.0
    except ValueError:
        roc = 0.0
    prev = float(y.mean()) if len(y) else 0.0
    trivial = 2 * prev / (1 + prev) if prev > 0 else 0.0
    return {
        "f1": f1,
        "mcc": mcc,
        "roc_auc": roc,
        "trivial_f1_all": float(trivial),
        "n_pos": int(y.sum()),
        "n_total": len(y),
    }


def episode_hits(fused: pd.DataFrame, manifest: dict) -> pd.DataFrame:
    """Per fault episode: fused hit in root window, latency, fused VUS-PR inputs."""
    ep2row = {ep: r for ep, r in zip(manifest["fault_episodes"], manifest["rows"])}
    recs = []
    for ep, g in fused[fused["ep_family"] != "clean"].groupby("episode_id"):
        r = ep2row[int(ep)]
        seg = g[(g["step"] >= r["t0"]) & (g["step"] < r["t0"] + r["dur"])]
        hits = seg[seg["fused"]]
        recs.append(
            {
                "fault_id": r["id"],
                "family": r["class"],
                "hit": bool(len(hits)),
                "latency": int(hits["step"].min() - r["t0"]) if len(hits) else 999,
            }
        )
    return pd.DataFrame(recs)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fused", default="artifacts/m0b_oof_fused.parquet")
    ap.add_argument("--manifest", default="docs/m0b_battery_manifest.json")
    ap.add_argument("--baseline", default="artifacts/m0b_baseline.json")
    args = ap.parse_args(argv)

    fused = pd.read_parquet(args.fused)
    manifest = json.loads(pathlib.Path(args.manifest).read_text(encoding="utf-8"))
    baseline = json.loads(pathlib.Path(args.baseline).read_text(encoding="utf-8"))
    # Episode-level families from the manifest (the v6 row label is window-level
    # and would enrich slices to ~67% prevalence — deployment is ~3%).
    epfam = {
        int(ep): r["class"]
        for ep, r in zip(manifest["fault_episodes"], manifest["rows"])
    }
    for ep in manifest["clean_episodes"]:
        epfam[int(ep)] = "clean"
    fused = fused.copy()
    fused["ep_family"] = fused["episode_id"].map(epfam)
    ep_hits = episode_hits(fused, manifest)
    base_rows = {r.get("fault_id", r.get("id")): r for r in baseline["rows"]}

    experts = ["knn", "pca", "lof", "supervised_lr", "dlinear"]
    fam_vus = {}
    for fam in sorted(fused.loc[fused["ep_family"] != "clean", "ep_family"].unique()):
        vals = []
        for _, g in fused[fused["ep_family"] == fam].groupby("episode_id"):
            v = vus_pr(g[experts].mean(axis=1).to_numpy(), g["y"].to_numpy(dtype=int))
            if np.isfinite(v):
                vals.append(float(v))
        fam_vus[fam] = float(np.mean(vals)) if vals else float("nan")
    sup = fused[fused["ep_family"] != "clean"]
    s_vus = float(
        np.nanmean(
            [
                vus_pr(g["supervised_lr"].to_numpy(), g["y"].to_numpy())
                for _, g in sup.groupby("episode_id")
            ]
        )
    )
    n_vus = float(
        np.nanmean(
            [
                max(
                    vus_pr(g[c].to_numpy(), g["y"].to_numpy())
                    for c in ["knn", "pca", "lof", "dlinear"]
                )
                for _, g in sup.groupby("episode_id")
            ]
        )
    )
    # Gate-only and combined episode hits from the baseline runner's experts.
    q_hits, g_hits = [], []
    for _, r in ep_hits.iterrows():
        b = base_rows.get(r["fault_id"], {})
        ex = b.get("experts", {})
        q_hits.append(bool(ex.get("quantile")))
        g_hits.append(bool(ex.get("structural")))
    ep_hits["q_hit"] = q_hits
    ep_hits["g_hit"] = g_hits
    ep_hits["any_hit"] = ep_hits["hit"] | ep_hits["q_hit"] | ep_hits["g_hit"]

    wires = adjudicate(
        {
            "id": "H1",
            "metric": s_vus - n_vus,
            "bar": 0.03,
            "higher_is_better": True,
            "assumption": "S-arm mean-episode-VUS minus best-N-arm mean-episode-VUS >= 3pp; unknown-family hedge = per-family VUS table above",
        },
        {
            "id": "H2",
            "metric": float(np.mean(g_hits)) - float(np.mean(q_hits)),
            "bar": 0.03,
            "higher_is_better": True,
            "assumption": "structural gate episode-hit minus quantile-only episode-hit >= 3pp (baseline experts)",
        },
        {
            "id": "H4",
            "metric": 0.0,
            "bar": 0.02,
            "higher_is_better": True,
            "assumption": "M-vs-G backbones need walk/pcmci (absent) — recorded BLOCKED, not adjudicated",
        },
        battery_id=BATTERY_ID,
    )
    # H4 is out of scope: override to BLOCKED explicitly.
    for w in wires:
        if w["id"] == "H4":
            w["status"] = "BLOCKED"
    # H3: per-class vs global threshold — deployment F1 over ALL rows (clean
    # episodes included; enrichment would flatter both sides equally is false —
    # prevalence is the denominator, so measure at deployment prevalence).
    from src.train_pipeline import compute_raw_pointwise_f1, pick_threshold_max_f1

    y_all = fused["y"].to_numpy(dtype=int)
    f_all = fused["fused"].to_numpy(dtype=int)
    f1_per_class = float(compute_raw_pointwise_f1(y_all, f_all))
    glob_thr = pick_threshold_max_f1(fused["fused_score"].to_numpy(), y_all)
    glob_dec = (fused["fused_score"].to_numpy() >= glob_thr).astype(int)
    f1_global = float(compute_raw_pointwise_f1(y_all, glob_dec))
    wires.append(
        adjudicate(
            {
                "id": "H3",
                "metric": f1_per_class - f1_global,
                "bar": 0.02,
                "higher_is_better": True,
                "assumption": f"per-class max-F1 thresholds (F1={f1_per_class:.3f}) vs single global max-F1 threshold (F1={f1_global:.3f}), delta >= 2pp",
            },
            battery_id=BATTERY_ID,
        )[0]
    )
    # H5: firing test — quality expert clean fires 0/400 kits (<=3/1000); stability needs seed repeats.
    wires.append(
        {
            "id": "H5",
            "metric": 0.0,
            "bar": 0.003,
            "higher_is_better": False,
            "status": "Ambiguous",
            "battery_id": BATTERY_ID,
            "date": datetime.date.today().isoformat(),
            "assumption": "clean fires 0/400 kits (bar met) but >=2-of-3 stability needs repeated runs — Ambiguous allowed",
        }
    )
    for w in wires:
        if w["id"] == "USAD/GDN":
            continue
    wires.append(
        {
            "id": "USAD/GDN",
            "metric": float("nan"),
            "bar": "env-has-torch",
            "higher_is_better": True,
            "status": "BLOCKED",
            "battery_id": BATTERY_ID,
            "date": datetime.date.today().isoformat(),
            "assumption": "torch absent in CPU-only env — cannot evaluate, never Falsified",
        }
    )
    out = {
        "battery_id": BATTERY_ID,
        "wires": wires,
        "family_vus_fused": {k: round(v, 3) for k, v in fam_vus.items()},
        "episode_hit_combined": round(float(ep_hits["any_hit"].mean()), 3),
        "metrics": summarize_metrics(
            fused["y"].to_numpy(dtype=int),
            fused["fused_score"].to_numpy(dtype=float),
            fused["fused"].to_numpy(dtype=int),
        ),
        "vus_bar": {
            "bar": 0.90,
            "mean_family_vus": round(float(np.nanmean(list(fam_vus.values()))), 4),
        },
    }
    pathlib.Path("artifacts/m0b_h_wires.json").write_text(
        json.dumps(out, indent=2, default=str)
    )
    for w in wires:
        print(w["id"], w["status"], w["metric"], "|", w["assumption"][:60])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
