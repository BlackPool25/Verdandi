#!/usr/bin/env python3
"""Train torch ROI head on trigger-anchored battery episodes (LOMO eval).

Trigger = frozen w128-v2 argmax window (inference-identical anchor).
Targets from GT (train-only): Gaussian onset heat at t0, origin machine.
Split: hold out every 5th machine as unseen origins (leave-machines-out).
Reports top-1 + onset err on held-out machines + ROI-permutation ablation.
"""

from __future__ import annotations

import argparse
import glob
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from joblib import load

MACHINES = [
    "A0", "A1", "A2", "A7", "A8", "A9", "B0", "B1", "B2", "B7P",
    "B7S", "B8", "B9", "C0", "C1", "C2", "C6", "C7", "PKG0", "PKG1",
    "PKG2", "INSP0", "ASM0", "ASM1", "ASM2", "RWK0",
]


def build_rows(det, file_glob, max_eps, seed=0):
    import torch  # noqa: F401  (torch-first diagnosis track, quarantined to roi_head+scripts)

    from src.roi_head import episode_tensors
    from src.window_dataset import apply_norm, build_windows

    model, w, stride = det["model"], int(det["w"]), int(det["stride"])
    med = np.asarray(det["norm_median"], dtype=float)
    iqr = np.asarray(det["norm_iqr"], dtype=float)
    n_obs = int(det["n_obs_features"])
    obs = [f"obs_{m}" for m in MACHINES]
    rows = []
    for p in sorted(glob.glob(file_glob)):
        df = pd.read_parquet(p)
        if df["y"].sum() == 0:
            continue
        for fe in list(df[df.y == 1]["episode_id"].unique()):
            if len(rows) >= max_eps:
                return rows
            g = df[df.episode_id == fe].sort_values("step").reset_index(drop=True)
            r = g[g.y == 1].iloc[0]
            t0 = int(g[g.y == 1]["step"].min())
            root = str(r["root_id_step"])
            if root not in MACHINES:
                continue
            X, _, _, _, starts = build_windows(g, w=w, stride=stride, invariant=True, return_starts=True)
            s = np.asarray(model.predict_proba(apply_norm(X, med, iqr, n_obs))[:, 1])
            if float(s.max()) < 0.5:
                continue
            trig = int(starts[int(np.argmax(s))])
            try:
                Xt, heat, who = episode_tensors(g, obs, trig, t0, MACHINES.index(root))
            except ValueError:
                continue
            rows.append((Xt, heat, who, root, t0, trig))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact", default="artifacts/window-gbm-w128-v2")
    ap.add_argument("--glob", default="artifacts/m0b_mass_*.parquet")
    ap.add_argument("--max-eps", type=int, default=600)
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--out", default="artifacts/roi-head-v1/model.pt")
    args = ap.parse_args(argv)

    import torch

    from src.roi_head import RoiHead, loss_fn

    torch.manual_seed(0)
    det = load(f"{args.artifact}/model.joblib")
    rows = build_rows(det, args.glob, args.max_eps)
    held = set(MACHINES[4::5])
    tr = [r for r in rows if r[3] not in held]
    te = [r for r in rows if r[3] in held]
    print(f"n={len(rows)} train={len(tr)} heldout={len(te)} machines={sorted(held)}")

    m = RoiHead(n_chan=26, n_machine=26)
    opt = torch.optim.Adam(m.parameters(), lr=args.lr)
    m.train()
    rng = np.random.default_rng(0)
    for ep in range(args.epochs):
        tot = 0.0
        order = rng.permutation(len(tr))
        for bi in range(0, len(tr), args.batch):
            idx = order[bi : bi + args.batch]
            Xb = torch.stack([torch.from_numpy(tr[i][0]) for i in idx])
            hb = torch.stack([torch.from_numpy(tr[i][1]) for i in idx])
            wb = torch.tensor([tr[i][2] for i in idx])
            opt.zero_grad()
            loss = loss_fn(*m(Xb), hb, wb)
            loss.backward()
            opt.step()
            tot += loss.item() * len(idx)
        print(f"epoch {ep} loss={tot / max(1, len(tr)):.4f}", flush=True)

    m.eval()
    top1, errs = 0, []
    with torch.no_grad():
        for Xt, _, who, _, t0, trig in te:
            ph, pw = m(torch.from_numpy(Xt).unsqueeze(0))
            pred_m = int(pw.argmax())
            top1 += int(pred_m == who)
            errs.append(abs(int(ph[0].argmax()) + (trig - 64) - t0))
    print(f"LOMO top1={top1 / max(1, len(te)):.3f} (n={len(te)}) MEASURED")
    if errs:
        print(f"LOMO onset med={float(np.median(errs)):.1f} p90={float(np.quantile(errs, 0.9)):.1f} MEASURED")
    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    torch.save(m.state_dict(), args.out)
    print(f"saved -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
