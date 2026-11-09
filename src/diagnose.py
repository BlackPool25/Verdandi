"""Diagnosis layer: attribution + sensor/process + rung/hop + onset (alongside detector).

Detector stays frozen (invariant HistGBM). This module only runs on
windows the detector fired on (silent on clean by construction).
Ground-truth columns (root_id_step, hop_step, sensor_vs_process,
mag_rung) are NEVER used here except in tests/evaluation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.twin import compute_hop

RUNG_CUT = 3.5


def episode_nominal(g: pd.DataFrame, obs_cols: list[str], n: int = 30) -> np.ndarray:
    """Per-channel nominal level from episode clean prefix (causal)."""
    return np.array(
        [g[c].to_numpy(dtype=float)[:n].mean() for c in obs_cols], dtype=float
    )


def robust_sigma(g: pd.DataFrame, obs_cols: list[str], n: int = 30) -> np.ndarray:
    """Per-channel MAD-based sigma from clean prefix (floor 1e-9)."""
    out = []
    for c in obs_cols:
        v = g[c].to_numpy(dtype=float)[:n]
        out.append(max(float(np.median(np.abs(v - np.median(v))) * 1.4826), 1e-9))
    return np.array(out, dtype=float)


def attribute_machine(
    seg: pd.DataFrame, obs_cols: list[str], nominal: np.ndarray, sigma: np.ndarray
) -> tuple[str, float]:
    """Argmax |last - nominal|/sigma over obs channels (alongside only)."""
    scores = {}
    last = seg.iloc[-1]
    for j, c in enumerate(obs_cols):
        scores[c] = abs(float(last[c]) - nominal[j]) / sigma[j]
    best = max(scores, key=lambda k: scores[k])
    machine = best.removeprefix("obs_")
    return machine, float(scores[best])


def classify_coordination(
    seg: pd.DataFrame,
    obs_cols: list[str],
    nominal: np.ndarray,
    sigma: np.ndarray,
    k: float = 3.0,
) -> str:
    """RBC-style: >=2 channels over kσ → process else sensor."""
    n_hit = 0
    last = seg.iloc[-1]
    for j, c in enumerate(obs_cols):
        if abs(float(last[c]) - nominal[j]) / sigma[j] > k:
            n_hit += 1
    return "process" if n_hit >= 2 else "sensor"


def estimate_rung(max_abs_sigma: float, cut: float = RUNG_CUT) -> str:
    """Severity readout: incipient (<cut) vs caricature (>=cut)."""
    return "caricature" if max_abs_sigma >= cut else "incipient"


def diagnose_window(
    seg: pd.DataFrame,
    obs_cols: list[str],
    nominal: np.ndarray,
    sigma: np.ndarray,
) -> dict:
    """Full per-window diagnosis dict (trigger-gated by caller)."""
    machine, score = attribute_machine(seg, obs_cols, nominal, sigma)
    coord = classify_coordination(seg, obs_cols, nominal, sigma)
    rung = estimate_rung(score)
    return {
        "machine": machine,
        "score_sigma": round(float(score), 3),
        "coord_class": coord,
        "rung": rung,
        "hop_est": 0,
    }


def _znorm(x: np.ndarray, n: int = 30) -> np.ndarray:
    """Prefix-robust z-score (median/MAD of first n ticks)."""
    pre = np.asarray(x, dtype=float)[:n]
    med = float(np.median(pre))
    mad = float(np.median(np.abs(pre - med)) * 1.4826) or 1e-9
    return (np.asarray(x, dtype=float) - med) / mad


def machine_onset(
    g: pd.DataFrame, obs_col: str, nominal_j: float, sigma_j: float, k: float = 2.5
) -> tuple[int, str]:
    """Onset tick for one machine: first state deviation else residual crossing.

    Returns (tick, kind) with kind in {state, residual, none}.
    """
    state_col = f"state_{obs_col[4:]}" if obs_col.startswith("obs_") else None
    steps = g["step"].to_numpy() if "step" in g.columns else np.arange(len(g))
    start_i = int(np.searchsorted(np.asarray(steps), 100))  # faults start >=120;
    # plant transient (30-70) is not an onset. Nominal stays prefix 0-30.
    machine = obs_col.removeprefix("obs_")
    # Counter path (delay signature): tputlag is a cycling counter, so a
    # bare positive run is normal. Fire only on runs exceeding the
    # prefix max, sustained 3+ ticks. Breakdown is covered by the state
    # path (DOWN); downrun is skipped (natural downruns look identical).
    cc = f"tputlag_{machine}"
    if cc in g.columns:
        cv = g[cc].to_numpy(dtype=float)
        pmax = float(cv[:start_i].max(initial=0.0))
        run = 0
        for i in range(start_i, len(cv)):
            run = run + 1 if cv[i] > pmax else 0
            if run >= 3:
                return int(steps[i - 2]), "counter"
    if state_col and state_col in g.columns:
        st = g[state_col].to_numpy()[start_i:]
        pre = g[state_col].to_numpy()[:start_i]
        pre_run = float((pre == "RUN").mean())
        for kk in range(len(st) - 2):
            w = st[kk : kk + 3]
            # sustained non-RUN run; DOWN always counts, STARVED/BLOCKED
            # only if prefix was clean-RUN dominated (else transient)
            if (w != "RUN").all() and ("DOWN" in w or pre_run > 0.8):
                return int(steps[start_i + kk]), "state"
    v = g[obs_col].to_numpy(dtype=float)
    score = np.abs(v - nominal_j) / sigma_j
    # Residual path: PELT on prefix-z-scored series + jump confirm.
    # (Raw-score penalty is on the wrong scale: 76 noise segments wash
    # out contrast. z-scores restore the BIC geometry.)
    from src.onset import pelt_l2

    z = _znorm(score)
    for cp in pelt_l2(z, penalty=10.0, min_size=5):
        if cp < start_i + 10 or cp >= len(v) - 20:
            continue
        pre = float(np.mean(z[cp - 10 : cp]))
        post = float(np.mean(z[cp : cp + 20]))
        # Fault shifts sustain (bias constant, drift ramp); texture reverts.
        if post - pre > 2.5 and post > k:
            return int(steps[cp]), "residual"
    return -1, "none"


def diagnose_multi_origin(
    g: pd.DataFrame, obs_cols: list[str], oracle_onset: dict[str, int] | None = None
) -> list[dict]:
    """One entry per affected machine, ordered by onset (multi-start).

    Structural coordination: own DOWN/BLOCKED at onset → process-origin
    candidate; STARVED-only → downstream symptom; obs-only residual with
    states clean → sensor. Silent on clean: machines with no onset omitted.
    oracle_onset maps machine -> GT tick (ablation only: GT as input to
    isolate onset quality from ranking quality; never in production).
    """
    g = g.sort_values("step").reset_index(drop=True) if "step" in g.columns else g
    nom = episode_nominal(g, obs_cols)
    sig = robust_sigma(g, obs_cols)
    entries = []
    for j, c in enumerate(obs_cols):
        machine = c.removeprefix("obs_")
        if oracle_onset is not None and machine in oracle_onset:
            tick, kind = int(oracle_onset[machine]), "oracle"
        else:
            tick, kind = machine_onset(g, c, float(nom[j]), float(sig[j]))
        if tick < 0:
            continue
        confirmed: int | None = tick  # machine_onset is already PELT/state-confirmed
        v = g[c].to_numpy(dtype=float)
        state_col = f"state_{machine}"
        own = (
            str(g[g["step"] == tick][state_col].iloc[0])
            if state_col in g.columns
            and "step" in g.columns
            and (g["step"] == tick).any()
            else "RUN"
        )
        seg = g[g["step"] >= tick].head(16) if "step" in g.columns else g.head(16)
        coord = classify_coordination(seg, obs_cols, nom, sig) if len(seg) else "sensor"
        # Structural override: STARVED-only with no local DOWN = symptom,
        # but keep sensor/process from coordination for the report.
        entries.append(
            {
                "machine": machine,
                "onset": tick,
                "onset_kind": kind,
                "onset_confirmed": confirmed,
                "own_state": own,
                "coord_class": coord,
                "rung": estimate_rung(float(np.abs(v - nom[j]).max() / sig[j])),
                "hop_est": 0,
            }
        )

    def _rank(r: dict) -> tuple[int, int]:
        # Direction signature first: state-DOWN origin beats texture.
        # STARVED-only = downstream symptom; residual-RUN = last resort.
        if r["onset_kind"] == "state" and r["own_state"] == "DOWN":
            return (0, r["onset"])
        # "oracle" (ablation GT tick) competes exactly like an estimated
        # state/counter onset: perfect information, same ranking rules.
        if r["onset_kind"] in ("state", "counter", "oracle"):
            return (1, r["onset"])
        return (2, r["onset"])

    entries.sort(key=_rank)
    # hop_est: 0 for earliest (root candidate), BFS hop for the rest is
    # assigned by the caller with topology; default sequential here.
    for i, r in enumerate(entries):
        r["hop_est"] = 0 if i == 0 else r["hop_est"]
    return entries


def first_trigger(
    scores: np.ndarray, starts: np.ndarray, thr: float = 0.8
) -> int | None:
    """First window-start with score >= thr (locked operating point)."""
    s = np.asarray(scores, dtype=float)
    st = np.asarray(starts, dtype=int)
    hot = np.flatnonzero(s >= thr)
    return int(st[hot[0]]) if len(hot) else None


def confirm_trigger(
    scores: np.ndarray, starts: np.ndarray, thr: float = 0.8, m: int = 2, n: int = 3
) -> int | None:
    """M-of-N persistence confirm: first window-start whose trailing N
    windows contain >= M hot scores. Unconfirmed triggers stay pending
    (caller abstains from diagnosis). k=1 is first_trigger (no confirm)."""
    s = np.asarray(scores, dtype=float)
    st = np.asarray(starts, dtype=int)
    hot = (s >= thr).astype(int)
    for i in range(len(hot)):
        if hot[max(0, i - n + 1) : i + 1].sum() >= m:
            return int(st[i])
    return None


def abstain_reason(
    scores: np.ndarray, thr: float = 0.8, hi: float = 0.9, margin: float = 0.1
) -> str | None:
    """Selective-diagnosis gate: None = confident, else reason to abstain.

    maxscore < hi → low-confidence; top1-top2 < margin → ambiguous.
    (Top-2 needs per-family scores; margin check applies where available.)
    """
    s = np.asarray(scores, dtype=float)
    if float(s.max()) < hi:
        return "low-confidence"
    top2 = np.sort(s)[-2:]
    if len(top2) == 2 and float(top2[1] - top2[0]) < margin:
        return "ambiguous-margin"
    return None


def diagnose_from_trigger(
    g: pd.DataFrame,
    obs_cols: list[str],
    trigger: int,
    back: int = 16,
    oracle_onset: dict[str, int] | None = None,
) -> list[dict]:
    """Trigger-gated multi-origin diagnosis (alongside frozen detector).

    Drops onsets before trigger-back (pre-trigger texture is not the
    fault), then ranks by direction signature and onset distance to the
    trigger. Silent on clean: caller only invokes on fired windows.
    oracle_onset maps machine -> GT tick (ablation only, see
    diagnose_multi_origin).
    """
    out = diagnose_multi_origin(g, obs_cols, oracle_onset=oracle_onset)
    # Ablation-only: oracle (GT) entries bypass the back gate so the true
    # root always competes; estimated entries are gated unchanged.
    kept = [
        r
        for r in out
        if r["onset"] >= trigger - back or r["onset_kind"] == "oracle"
    ]

    def _trank(r: dict) -> tuple[int, int, int]:
        if r["onset_kind"] == "state" and r["own_state"] == "DOWN":
            base = 0
        elif r["onset_kind"] in ("state", "counter", "oracle"):
            base = 1
        else:
            base = 2
        return (base, abs(r["onset"] - trigger), r["onset"])

    kept.sort(key=_trank)
    # hop_est from the real twin DAG: 0 at the top candidate, BFS hops
    # downstream/upstream, -1 where unreachable (no forced path).
    if kept:
        top = kept[0]["machine"]
        kept[0]["hop_est"] = 0
        for r in kept[1:]:
            h = compute_hop(top, r["machine"], max_depth=3)
            r["hop_est"] = int(h) if h is not None else -1
    return kept
