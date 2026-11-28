"""Ranker-level T+Platt calibration + exclude-held-5 retrain (Task 2).

Reads artifacts/stage2-oof.npz (seed-pinned LambdaRank OOF) +
artifacts/oof_identity.parquet (ep -> root/fam/votable mapping).

Design (no test leakage):
- All ranker scores are OOF (never saw their own fold). The fit/eval split
  below is a *second* disjoint episode split (stratified by fam, seed-pinned):
  T+Platt+tau fit on FIT episodes only, all reported numbers on EVAL episodes.
- Platt over isotonic: eval-scale n is ~1.3k episodes (small-n regime where
  the 2-param sigmoid wins; research-calibration §2).
- tau is picked on FIT at risk<=0.3 and frozen, then applied to EVAL
  (never tuned on the reporting split).
- Serving artifacts untouched: no train_final/save calls.

Writes artifacts/ranker-calibration.json {T,a,b,tau,...} with n/seed/lineage.
"""

import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from src import config
from src.confidence import (
    coverage_curve,
    ece_score,
    fit_temperature,
    nll,
    pick_threshold,
    platt_fit,
    platt_predict,
)

HELD5 = ("ASM1", "ASM2", "B7P", "B9", "C6")
RISK_TARGET = 0.3
SPLIT_SEED = 0


def _softmax_rows(S: np.ndarray, T: float) -> np.ndarray:
    z = np.asarray(S, dtype=float) / max(T, 1e-12)
    z -= z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def episode_stats(oof_pred, y, groups):
    """Per-episode ranker stats: score matrix + true candidate index."""
    eps = np.unique(np.asarray(groups))
    S, true_idx = [], []
    for ep in eps:
        m = np.asarray(groups) == ep
        S.append(np.asarray(oof_pred, dtype=float)[m])
        true_idx.append(int(np.argmax(np.asarray(y)[m])))
    return eps, np.array(S), np.array(true_idx)


def split_episodes(eps, fam_arr, seed=SPLIT_SEED, frac=0.5):
    """Disjoint fam-stratified fit/eval episode split (seed-pinned)."""
    rng = np.random.default_rng(seed)
    eps = np.asarray(eps)
    fam_arr = np.asarray(fam_arr, dtype=str)
    fit, ev = [], []
    for f in sorted(set(fam_arr.tolist())):
        sub = eps[fam_arr == f].copy()
        rng.shuffle(sub)
        k = max(1, int(len(sub) * frac))
        fit += sub[:k].tolist()
        ev += sub[k:].tolist()
    return np.array(fit), np.array(ev)


def _ep_metrics(S_eval, true_eval, conf_eval, tau):
    forced = (S_eval.argmax(axis=1) == true_eval)
    cov_m = conf_eval >= tau
    cov = float(cov_m.mean()) if len(conf_eval) else 0.0
    risk = float(1 - forced[cov_m].mean()) if cov_m.sum() else 1.0
    gated_acc = float(forced[cov_m].mean()) if cov_m.sum() else 0.0
    return {
        "forced_top1": float(forced.mean()),
        "coverage": cov,
        "risk": risk,
        "gated_top1": gated_acc,
        "n": len(true_eval),
        "n_covered": int(cov_m.sum()),
    }


def main():
    z = np.load("artifacts/stage2-oof.npz", allow_pickle=True)
    stacked_seed = int(np.asarray(z["seed"]).ravel()[0])
    oof_pred, y, groups = z["oof_pred"], z["y"], z["groups"]
    oof = pd.read_parquet("artifacts/oof_identity.parquet")

    truth, fam_ep, votable = {}, {}, {}
    for ep, g in oof.groupby("ep"):
        t = g[g["y"] == 1]
        if t.empty or str(t["root"].mode().iloc[0]) == "none":
            continue
        truth[int(ep)] = str(t["root"].mode().iloc[0])
        fam_ep[int(ep)] = str(t["fam"].mode().iloc[0])
        votable[int(ep)] = bool((g["pred"] != "none").any())

    eps, S, true_idx = episode_stats(oof_pred, y, groups)
    eps = np.array([int(e) for e in eps])
    keep = np.array([e in truth for e in eps])
    eps, S, true_idx = eps[keep], S[keep], true_idx[keep]
    fam_arr = np.array([fam_ep[e] for e in eps])
    # Row order in build_rows follows machines order; true idx cross-checked
    # against teacher root below via forced-top1 agreement (printed).

    fit_eps, eval_eps = split_episodes(eps, fam_arr, seed=SPLIT_SEED)
    fi = np.isin(eps, fit_eps)
    ei = np.isin(eps, eval_eps)

    # Fit T on FIT episodes (NLL of true candidate under softmax(s/T)).
    T = fit_temperature(S[fi], true_idx[fi])
    Pf = _softmax_rows(S[fi], T)
    srt = np.sort(Pf, axis=1)
    margins_fit = srt[:, -1] - (srt[:, -2] if S.shape[1] > 1 else 0.0)
    correct_fit = (Pf.argmax(axis=1) == true_idx[fi]).astype(int)
    a, b = platt_fit(margins_fit, correct_fit)
    conf_fit = platt_predict(margins_fit, a, b)
    tau = pick_threshold(conf_fit, correct_fit, RISK_TARGET)

    # Eval: ECE/NLL before/after + gated numbers on EVAL only.
    Pe1 = _softmax_rows(S[ei], 1.0)
    PeT = _softmax_rows(S[ei], T)
    ece_before, ece_after = ece_score(Pe1, true_idx[ei]), ece_score(PeT, true_idx[ei])
    nll_before, nll_after = nll(S[ei], 1.0, true_idx[ei]), nll(S[ei], T, true_idx[ei])
    srt_e = np.sort(PeT, axis=1)
    margins_eval = srt_e[:, -1] - srt_e[:, -2]
    conf_eval = platt_predict(margins_eval, a, b)
    correct_eval = (PeT.argmax(axis=1) == true_idx[ei]).astype(int)
    curve = coverage_curve(conf_eval, correct_eval)

    vot_m = np.array([votable[e] for e in eps[ei]])
    m_all = _ep_metrics(PeT, true_idx[ei], conf_eval, tau)
    m_vot = _ep_metrics(PeT[vot_m], true_idx[ei][vot_m], conf_eval[vot_m], tau)
    print(f"ranker T={T:.3f} (fit n_eps={fi.sum()})", flush=True)
    print(f"  ECE {ece_before:.3f}->{ece_after:.3f} NLL {nll_before:.3f}->{nll_after:.3f}"
          f" (EVAL n_eps={ei.sum()})", flush=True)
    print(f"  Platt a={a:.3f} b={b:.3f} tau={tau:.3f} @risk<={RISK_TARGET}", flush=True)
    print(f"  EVAL votable: forced={m_vot['forced_top1']:.3f} gated={m_vot['gated_top1']:.3f}"
          f" cov={m_vot['coverage']:.3f} risk={m_vot['risk']:.3f} (n={m_vot['n']})", flush=True)
    print(f"  EVAL pooled: forced={m_all['forced_top1']:.3f} gated={m_all['gated_top1']:.3f}"
          f" cov={m_all['coverage']:.3f} risk={m_all['risk']:.3f} (n={m_all['n']})", flush=True)

    # Exclude-held-5 teacher retrain: true unknown-reject (never trained on held-5).
    held = exclude_held5_retrain(oof)

    out = {
        "T": T, "a": a, "b": b, "tau": tau, "risk_target": RISK_TARGET,
        "margin_def": "top1-top2 of T-scaled ranker candidate softmax probs",
        "ece_before": ece_before, "ece_after": ece_after,
        "nll_before": nll_before, "nll_after": nll_after,
        "eval_votable": m_vot, "eval_pooled": m_all,
        "risk_coverage_eval": [[c, r] for c, r in curve[:: max(1, len(curve) // 20)]],
        "fit": {"n_eps": int(fi.sum()), "split_seed": SPLIT_SEED, "frac": 0.5,
                "stratified_by": "fam", "oof_only": True},
        "eval": {"n_eps": int(ei.sum())},
        "exclude_held5": held,
        "lineage": {
            "battery_id": "m0b-mass-balanced-v1", "battery_seed": 0,
            "n_per_cell": 300, "n_clean": 600,
            "stacked_seed": stacked_seed, "split_seed": SPLIT_SEED,
            "held5": list(HELD5),
            "code_version": config.CODE_VERSION,
        },
    }
    with open("artifacts/ranker-calibration.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print("saved artifacts/ranker-calibration.json", flush=True)
    return out


def exclude_held5_retrain(oof: pd.DataFrame) -> dict:
    """Teacher retrained excluding held-5-rooted episodes; eval on held-5.

    Same features/hyperparams as scripts/train_origin._oof_predict
    (identity HistGBM, max_iter=300, seed=0, clean-fit norm) minus the CV
    loop: single fit on non-held fault+clean windows, forced window top-1 +
    episode majority-vote top-1 reported on held-5 only.
    """
    from sklearn.ensemble import HistGradientBoostingClassifier

    from src.window_dataset import (
        OBS_STRUCT_COLS,
        apply_norm,
        fit_clean_norm,
    )

    X = np.load("artifacts/window_cache/X_identity.npy")
    meta = pd.read_parquet("artifacts/window_cache/meta.parquet")
    roots = meta["root"].to_numpy(dtype=str)
    ep = meta["ep"].to_numpy()
    n_struct = len(OBS_STRUCT_COLS)
    n_obs = X.shape[1] - 2 * n_struct
    held_ep = set(oof.loc[oof["root"].isin(HELD5), "ep"].unique().tolist())
    held_m = np.isin(ep, list(held_ep)) & (roots != "none")
    train_m = ~np.isin(ep, list(held_ep))
    classes = np.array(sorted(set(roots.tolist())))
    y_all = np.searchsorted(classes, roots)
    med, iqr = fit_clean_norm(X[train_m], (roots[train_m] != "none").astype(int), n_obs)
    clf = HistGradientBoostingClassifier(max_iter=300, random_state=0)
    clf.fit(apply_norm(X[train_m], med, iqr, n_obs), y_all[train_m])
    pred_h = classes[clf.predict(apply_norm(X[held_m], med, iqr, n_obs))]
    fault_h = roots[held_m] != "none"
    w_hit = float(((pred_h == roots[held_m]) & fault_h).sum())
    w_tot = int(fault_h.sum())
    # Episode majority vote on held-5 fault episodes.
    ep_hit, ep_n, vot_hit, vot_n = 0, 0, 0, 0
    dfh = pd.DataFrame({"ep": ep[held_m], "pred": pred_h, "root": roots[held_m]})
    for _, g in dfh.groupby("ep"):
        truth = g[g["root"] != "none"]
        if truth.empty:
            continue
        troot = str(truth["root"].mode().iloc[0])
        pm = g[g["pred"] != "none"]
        ep_n += 1
        if len(pm) == 0:
            continue
        vot_n += 1
        if str(pm["pred"].value_counts().idxmax()) == troot:
            ep_hit += 1
            vot_hit += 1
    # Teacher-margin Platt gate transfer: fit on non-held OOF fault windows,
    # tau @risk<=0.3 frozen there, applied to held-5 (true unknown machines).
    # margin_def: top1-top2 of RAW teacher machine probas (no T: logits not
    # persisted in oof_identity.parquet; distinct from the T=2.58 window row).
    from src.confidence import pick_threshold as _pick
    from src.confidence import platt_fit as _pfit
    from src.confidence import platt_predict as _ppred

    mcols = [c for c in oof.columns if c.startswith("proba_") and c != "proba_none"]
    Pm = oof[mcols].to_numpy(dtype=float)
    srt = np.sort(Pm, axis=1)
    margins = srt[:, -1] - srt[:, -2]
    is_fault = (oof["y"].to_numpy() == 1)
    is_held = oof["root"].isin(list(HELD5)).to_numpy()
    correct = ((oof["pred"].to_numpy(dtype=str) == oof["root"].to_numpy(dtype=str))
               & is_fault).astype(int)
    tr_m = is_fault & ~is_held
    a5, b5 = _pfit(margins[tr_m], correct[tr_m])
    tau5 = _pick(_ppred(margins[tr_m], a5, b5), correct[tr_m], RISK_TARGET)
    conf_h = _ppred(margins[is_fault & is_held], a5, b5)
    corr_h = correct[is_fault & is_held]
    cov_h = float((conf_h >= tau5).mean()) if len(conf_h) else 0.0
    covered = conf_h >= tau5
    risk_h = float(1 - corr_h[covered].mean()) if covered.sum() else 1.0
    infleet_h = float(corr_h.mean()) if len(corr_h) else 0.0
    res = {
        "window_forced_top1": w_hit / max(1, w_tot), "window_n": w_tot,
        "episode_forced_top1_pooled": ep_hit / max(1, ep_n), "episode_n": ep_n,
        "episode_forced_top1_votable": vot_hit / max(1, vot_n),
        "episode_votable_n": vot_n,
        "train_windows_n": int(train_m.sum()), "seed": 0,
        "infleet_window_forced_top1_held5": infleet_h, "infleet_window_n_held5": len(corr_h),
        "gate_fit_windows_n": int(tr_m.sum()),
        "gate": {"a": a5, "b": b5, "tau": tau5, "risk_target": RISK_TARGET,
                 "margin_def": "top1-top2 of raw teacher machine probas",
                 "held5_coverage": cov_h, "held5_risk": risk_h,
                 "held5_abstain": 1 - cov_h,
                 "held5_n": len(corr_h),
                 "held5_n_covered": int(covered.sum())},
    }
    print(f"  exclude-held5: window top1={res['window_forced_top1']:.3f} (n={w_tot})"
          f" ep pooled={res['episode_forced_top1_pooled']:.3f} (n={ep_n})"
          f" ep votable={res['episode_forced_top1_votable']:.3f} (n={vot_n})", flush=True)
    print(f"  held5 gate transfer: infleet-forced={infleet_h:.3f} (n={len(corr_h)})"
          f" tau={tau5:.3f} cov={cov_h:.3f} risk={risk_h:.3f}"
          f" abstain={1 - cov_h:.3f}", flush=True)
    return res


if __name__ == "__main__":
    main()
