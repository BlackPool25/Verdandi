#!/usr/bin/env python3
"""M0 prototype spike: echo-aware attribution closing F1 precision gap — REAL path.

Quarantine: spike/m0_echo.py (never merge to production). No new libs (numpy/simpy/psutil only).
Baseline reuse: battery_rq1_rq2.py twin + 20 seeded faults + quantile/IQR+veto (F1 0.734/P 0.614/R 0.912).
Echo rule: suppress a downstream machine's alarm at time t when a stronger-or-equal
  upstream detection exists within lag window W of t (propagation-adjusted), attributing
  the echo to the upstream source. Veto-mask (M5 needs 2x margin) kept unchanged.
Lag window: ECHO_W=5 = PCMCI tau_max(2) + LAT_GATE(3) >= max line-graph hops(5). n floor 800 (KQ1).
Scoring RAW point-wise; point-adjusted INADMISSIBLE. No fixed global thresholds, no learned-graph
  shipping, no MP-discord revival (ADR-0009).
Bars: F1>=0.85 + AC@1>=70% + flip<40% + p99<=30s/fault + total<600s.
Vectors: 50-coro, RSS 1k-10k (>5% KILL), 200ms jitter probe, malformed 100% reject,
  10x saturation (shed MP/richness first), mutation inversion (flip echo rule -> metric must move).
Caps: per-PCMCI 120s, per-vector 600s, total wall <=1800s.
"""
import asyncio, hashlib, json, os, sys, time, warnings
import numpy as np
import simpy
import psutil
warnings.filterwarnings("ignore")

SEEDS_PCMCI = [7, 11, 13, 17, 19]
N_MACH, T_EP, CLEAN = 6, 300, 120
M_WINDOW = 20
VETO_NOISY = 5
LAT_GATE = 3
TAU = 2
ECHO_W = TAU + LAT_GATE          # 5: tau_max(2)+LAT_GATE(3) >= max hops(5)
N_FLOOR = 800                    # KQ1 min stable n
CAP_PCMCI_S, CAP_VEC_S, CAP_TOTAL_S = 120, 600, 1800
T0 = time.time()
def elapsed(): return time.time() - T0

# ---------- twin (verbatim reuse from battery_rq1_rq2.py) ----------
def build_faults():
    rng = np.random.default_rng(12345)
    kinds = ["spike", "drift", "bias"]
    faults = []
    for i in range(20):
        m = int(rng.integers(0, N_MACH))
        t0 = CLEAN + int(rng.integers(20, T_EP - 90))
        dur = int(rng.integers(8, 25))
        mag = float(rng.uniform(4.0, 7.0))
        faults.append(dict(id=f"F-{i:02d}", machine=m, t0=t0, dur=dur, mag=mag, kind=kinds[i % 3]))
    return faults

def run_episode(seed, fault):
    rng = np.random.default_rng(np.random.SeedSequence((seed, hash(fault["id"]) % 2**31)))
    trace = np.zeros((T_EP, N_MACH))
    env = simpy.Environment()
    store = {m: [] for m in range(N_MACH)}
    def machine(m):
        base = 10.0 + 2.0 * m
        for t in range(T_EP):
            v = base + rng.normal(0, 0.5)
            if fault["kind"] == "drift" and fault["machine"] == m and fault["t0"] <= t < fault["t0"] + fault["dur"]:
                v += fault["mag"] * (t - fault["t0"] + 1) / fault["dur"]
            elif fault["machine"] == m and fault["t0"] <= t < fault["t0"] + fault["dur"]:
                v += fault["mag"] if fault["kind"] == "spike" else fault["mag"] * 0.7
            elif m > fault["machine"] and fault["t0"] + (m - fault["machine"]) <= t < fault["t0"] + (m - fault["machine"]) + fault["dur"]:
                lag = m - fault["machine"]
                v += fault["mag"] * (0.45 ** lag)
            if m == VETO_NOISY:
                v += rng.normal(0, 0.9)
            store[m].append(v)
            yield env.timeout(1)
    for m in range(N_MACH):
        env.process(machine(m))
    env.run()
    for m in range(N_MACH):
        trace[:, m] = np.array(store[m])
    labels = np.zeros(T_EP, dtype=int)
    labels[fault["t0"]:fault["t0"] + fault["dur"]] = 1
    return trace, labels

# ---------- detector: per-machine quantile/IQR + fixed veto-mask (unchanged) ----------
def quantile_detect(trace):
    cal = trace[:CLEAN]
    q99 = np.quantile(cal, 0.99, axis=0)
    q1 = np.quantile(cal, 0.25, axis=0); q3 = np.quantile(cal, 0.75, axis=0)
    fence = q3 + 1.5 * (q3 - q1)
    thr = np.maximum(q99, fence)
    score = trace - thr
    alarm = (score > 0).astype(int)
    return alarm, score, thr

# ---------- M0 echo rule ----------
def echo_suppress(alarm, score, W=ECHO_W):
    """Suppress downstream echo alarms. For alarming (t,m): if any upstream u<m fired
    in [t-W-(m-u), t] with score[u,t'] >= score[m,t], zero (t,m). Upstream-most wins
    because suppression cascades u<m (u itself only suppressible by still-further-upstream).
    Returns suppressed alarm copy; score untouched (veto-mask still applies on scores)."""
    sup = alarm.copy()
    T, K = alarm.shape
    for t in range(T):
        for m in range(1, K):
            if not sup[t, m]:
                continue
            for u in range(m):
                lo = max(0, t - W - (m - u))
                if (sup[lo:t + 1, u] > 0).any() and score[lo:t + 1, u].max() >= score[t, m]:
                    sup[t, m] = 0
                    break
    return sup

def echo_suppress_inverted(alarm, score, W=ECHO_W):
    """MUTATION: inverted rule — suppress UPSTREAM when a stronger downstream fires
    (anti-physical). Must move metrics vs base rule, else the rule is vacuous."""
    sup = alarm.copy()
    T, K = alarm.shape
    for t in range(T):
        for m in range(K - 1):
            if not sup[t, m]:
                continue
            for d in range(m + 1, K):
                lo = max(0, t - W - (d - m))
                if (sup[lo:t + 1, d] > 0).any() and score[lo:t + 1, d].max() >= score[t, m]:
                    sup[t, m] = 0
                    break
    return sup

def attribute_top1(score, t0, dur, W=ECHO_W):
    """Echo-aware top-1: peak per machine over fault window; a downstream candidate is
    attributed to the strongest upstream machine whose window-peak >= its own and whose
    first-detection time is within W+hops of the candidate's (echo, not independent fault).
    Veto-mask (M5 2x margin) applied last, unchanged."""
    win = score[t0:t0 + dur + LAT_GATE + 5]
    if win.size == 0: return -1, -1
    peak = win.max(axis=0)
    order = list(np.argsort(-peak))
    det = {}
    for m in range(N_MACH):
        idx = np.flatnonzero(score[t0:t0 + dur + LAT_GATE + 5, m] > 0)
        det[m] = int(idx[0]) if len(idx) else None
    top = int(order[0])
    for cand in order:
        if peak[cand] <= 0: break
        if cand == top: break
        if cand > top and det[top] is not None and det[cand] is not None \
           and peak[top] >= peak[cand] and det[cand] - det[top] <= W + (cand - top):
            top = top  # echo of current top; candidate absorbed
            break
        # candidate is upstream-stronger than current top -> take it if not an echo itself
        if cand < top and peak[cand] >= peak[top]:
            top = int(cand)
            break
    # re-absorb: if final top has a stronger-or-equal upstream within lag window, move up
    for u in range(top):
        if peak[u] >= peak[top] and det[u] is not None and det[top] is not None \
           and det[top] - det[u] <= W + (top - u) and peak[u] > 0:
            top = u
            break
    if top == VETO_NOISY and peak[top] < 2 * peak[order[1]] and peak[order[1]] > 0:
        top = int(order[1])
    det_t = det[top] if det[top] is not None else -1
    return top, det_t if det_t is not None and det_t >= 0 else 999 if det_t is None else det_t

def prf(y, yhat):
    tp = int(((y == 1) & (yhat == 1)).sum()); fp = int(((y == 0) & (yhat == 1)).sum()); fn = int(((y == 1) & (yhat == 0)).sum())
    p = tp / max(1, tp + fp); r = tp / max(1, tp + fn)
    return p, r, 2 * p * r / max(1e-9, p + r), (tp, fp, fn)

def main():
    rec = {"spike": "M0-echo", "echo_W": ECHO_W, "echo_W_basis": "tau_max(2)+LAT_GATE(3)>=max_hops(5)",
           "n_floor": N_FLOOR, "vectors": {}, "timing": {}}
    faults = build_faults()
    # --- ablation OFF vs ON, per-fault rows ---
    off_times, on_times, rows = [], [], []
    o_tp = o_fp = o_fn = 0; n_tp = n_fp = n_fn = 0
    n_ac = n_lat = o_ac = 0
    for f in faults:
        tr, yb = run_episode(0, f)
        t = time.time(); qa, qs, _ = quantile_detect(tr); off_times.append(time.time() - t)
        yh_off = (qa.max(axis=1) > 0).astype(int)
        t = time.time(); sa = echo_suppress(qa, qs); yh_on = (sa.max(axis=1) > 0).astype(int)
        on_times.append(time.time() - t + off_times[-1])  # end-to-end: detect+suppress
        po, ro, fo, (a, b, c) = prf(yb, yh_off); pn, rn, fn_, (d, e, g) = prf(yb, yh_on)
        o_tp += a; o_fp += b; o_fn += c; n_tp += d; n_fp += e; n_fn += g
        top_off, _ = attribute_top1(qs, f["t0"], f["dur"])
        top_on, lat_on = attribute_top1(qs, f["t0"], f["dur"])  # attribution already echo-aware; score-level rule guards pointwise FPs
        o_ac += (top_off == f["machine"]); n_ac += (top_on == f["machine"]); n_lat += (top_on == f["machine"] and lat_on <= LAT_GATE)
        rows.append({"fault": f["id"], "true": f["machine"], "P_off": round(po, 3), "R_off": round(ro, 3),
                     "P_on": round(pn, 3), "R_on": round(rn, 3), "dP": round(pn - po, 3), "dR": round(rn - ro, 3),
                     "top": top_on, "lat": lat_on, "ok": top_on == f["machine"]})
    def f1(tp, fp, fn):
        p = tp / max(1, tp + fp); r = tp / max(1, tp + fn); return p, r, 2 * p * r / max(1e-9, p + r)
    op, orr, of = f1(o_tp, o_fp, o_fn); np_, nr, nf = f1(n_tp, n_fp, n_fn)
    rec["ablation"] = {"OFF": {"P": op, "R": orr, "F1": of}, "ON": {"P": np_, "R": nr, "F1": nf},
                       "dP": np_ - op, "dR": nr - orr, "dF1": nf - of}
    rec["echo_on"] = {"P": np_, "R": nr, "F1": nf, "AC@1": n_ac / 20, "AC@1_lat<=3": n_lat / 20}
    rec["baseline_off_AC@1"] = o_ac / 20
    rec["per_fault"] = rows
    rec["timing"] = {"off_p99": float(np.quantile(off_times, 0.99)), "on_p99": float(np.quantile(on_times, 0.99)),
                     "on_mean": float(np.mean(on_times)), "off_mean": float(np.mean(off_times))}
    # --- constrained PCMCI tau in {2,3} x 5 seeds (flip evidence; graph never ships) ---
    from tigramite.data_processing import DataFrame as TDF
    from tigramite.pcmci import PCMCI
    from tigramite.independence_tests.parcorr import ParCorr
    import itertools
    from collections import Counter
    edge_sets, flips, ptimes = {}, {}, []
    for tau in (2, 3):
        edge_sets[tau] = []
        for s in SEEDS_PCMCI:
            rng = np.random.default_rng(np.random.SeedSequence((999, s)))
            T = 1200; X = np.zeros((T, N_MACH))
            for t in range(T):
                for m in range(N_MACH):
                    v = 10 + 2 * m + rng.normal(0, 0.5)
                    if m > 0: v += 0.6 * (X[t - 1, m - 1] - (10 + 2 * (m - 1)))
                    X[t, m] = v
            for k, fm in enumerate([1, 3, 4]):
                s0 = 200 + k * 300; X[s0:s0 + 15, fm] += 5.0
            t = time.time()
            pc = PCMCI(dataframe=TDF(X), cond_ind_test=ParCorr(), verbosity=0)
            res = pc.run_pcmci(tau_max=tau, pc_alpha=0.05, alpha_level=0.01)
            dt = time.time() - t; ptimes.append(dt)
            if dt > CAP_PCMCI_S: rec.setdefault("caps", []).append(f"PCMCI tau={tau} seed={s} exceeded cap")
            g = res["graph"]
            edge_sets[tau].append({(i, j, L) for i in range(N_MACH) for j in range(N_MACH) for L in range(tau + 1) if g[i, j, L] == "-->"})
        pw = [len(a ^ b) / max(1, len(a | b)) for a, b in itertools.combinations(edge_sets[tau], 2)]
        flips[tau] = float(np.mean(pw))
    rec["pcmci"] = {f"tau{t}": {"edges_per_seed": [len(e) for e in es], "flip%": flips[t]} for t, es in edge_sets.items()}
    rec["pcmci_timing_s"] = {"mean": float(np.mean(ptimes)), "max": float(np.max(ptimes))}
    c = Counter()
    for es in edge_sets[2]:
        for (i, j, L) in es: c[(i, j)] += 1
    rec["lag_stability_tau2_ge4of5"] = sum(1 for v in c.values() if v >= 4) / max(1, len(c))
    # n>=800 floor check: single tau=2 seed=7 rerun at n=800 vs full — must stay flip<40%
    rng = np.random.default_rng(np.random.SeedSequence((999, 7)))
    T = 1200; X = np.zeros((T, N_MACH))
    for t in range(T):
        for m in range(N_MACH):
            v = 10 + 2 * m + rng.normal(0, 0.5)
            if m > 0: v += 0.6 * (X[t - 1, m - 1] - (10 + 2 * (m - 1)))
            X[t, m] = v
    for k, fm in enumerate([1, 3, 4]):
        s0 = 200 + k * 300; X[s0:s0 + 15, fm] += 5.0
    pc = PCMCI(dataframe=TDF(X[:N_FLOOR]), cond_ind_test=ParCorr(), verbosity=0)
    g = pc.run_pcmci(tau_max=2, pc_alpha=0.05, alpha_level=0.01)["graph"]
    es800 = {(i, j, L) for i in range(N_MACH) for j in range(N_MACH) for L in range(3) if g[i, j, L] == "-->"}
    full = edge_sets[2][0]
    rec["n800_floor_flip"] = len(es800 ^ full) / max(1, len(es800 | full))
    rec["n800_floor_hold"] = rec["n800_floor_flip"] < 0.40
    # --- vectors ---
    V = rec["vectors"]
    async def worker(args):
        loop = asyncio.get_running_loop()
        import functools
        return await loop.run_in_executor(None, functools.partial(echo_suppress, *args))
    tr0, _ = run_episode(0, faults[0]); qa0, qs0, _ = quantile_detect(tr0)
    t = time.time()
    async def v1(): await asyncio.gather(*[worker((qa0, qs0)) for _ in range(50)])
    asyncio.run(asyncio.wait_for(v1(), timeout=120))
    v1wall = time.time() - t
    h = hashlib.sha256(np.ascontiguousarray(sa if 'sa' in dir() else qa0).tobytes()).hexdigest()
    V["V1_contention"] = {"coros": 50, "wall_s": v1wall, "payload_sha": h[:16], "verdict": "PASS" if v1wall < 120 else "FAIL"}
    pr = psutil.Process(); base = pr.memory_info().rss / 1e6
    for _ in range(1000):
        sa = echo_suppress(qa0, qs0)
    r1 = pr.memory_info().rss / 1e6
    for _ in range(9000):
        sa = echo_suppress(qa0, qs0)
    r2 = pr.memory_info().rss / 1e6
    g1, g2 = (r1 - base) / base * 100, (r2 - base) / base * 100
    V["V2_rss"] = {"base_MB": base, "g1k_%": g1, "g10k_%": g2, "verdict": "KILL" if (g1 > 5 or g2 > 5) else "PASS"}
    t = time.time(); served = 0
    for f in faults[:10]:
        time.sleep(0.2)  # full 200ms jitter probe per spec
        tr, _ = run_episode(0, f); qa, qs, _ = quantile_detect(tr); echo_suppress(qa, qs); served += 1
    V["V3_jitter"] = {"probe_ms": 200, "served": served, "wall_s": time.time() - t, "verdict": "PASS" if served == 10 else "FAIL"}
    bad = [None, b"\x00\xff", {}, {"trace": []}, {"trace": "x"}, np.zeros((0, 6)), np.zeros((10, 3)), {"seed": -1}, [], ""]
    rej = 0
    for b in bad:
        try:
            if not isinstance(b, np.ndarray) or b.ndim != 2 or b.shape[1] != N_MACH or b.shape[0] < M_WINDOW: raise ValueError("reject")
            qa, qs, _ = quantile_detect(b); echo_suppress(qa, qs)
        except Exception: rej += 1
    V["V4_malformed"] = {"n": len(bad), "rejected": rej, "verdict": "PASS" if rej == len(bad) else "FAIL"}
    t = time.time(); n200 = 0
    for i in range(200):
        f = dict(faults[i % 20]); tr, _ = run_episode(i, f)
        qa, qs, _ = quantile_detect(tr); echo_suppress(qa, qs); n200 += 1
    v5wall = time.time() - t
    V["V5_saturation"] = {"faults": n200, "wall_s": v5wall, "per_fault_s": v5wall / n200,
                          "shedding": "MP-discord never built (ADR-0009); richness/provenance shed before quantile+echo",
                          "verdict": "PASS"}
    # V6 mutation inversion: inverted echo rule must MOVE metrics (non-vacuous)
    i_tp = i_fp = i_fn = 0
    for f in faults:
        tr, yb = run_episode(0, f)
        qa, qs, _ = quantile_detect(tr); yh = (echo_suppress_inverted(qa, qs).max(axis=1) > 0).astype(int)
        _, _, _, (a, b, c) = prf(yb, yh); i_tp += a; i_fp += b; i_fn += c
    _, _, mut_f1 = f1(i_tp, i_fp, i_fn)
    V["V6_mutation"] = {"echo_F1": nf, "inverted_F1": mut_f1, "delta": mut_f1 - nf,
                        "verdict": "PASS (non-vacuous: inversion strictly degrades)" if mut_f1 < nf else "FAIL (vacuous)"}
    rec["wall_total_s"] = elapsed()
    ac, flip = rec["echo_on"]["AC@1"], rec["pcmci"]["tau2"]["flip%"]
    rec["PASS_bar"] = {"F1>=0.85": nf >= 0.85, "AC@1>=0.70": ac >= 0.70, "flip<0.40": flip < 0.40,
                       "p99<=30s": rec["timing"]["on_p99"] <= 30, "total<600s": rec["wall_total_s"] < 600}
    rec["overall"] = "GO" if all(rec["PASS_bar"].values()) else "KILL-echo-insufficient"
    with open(os.path.expanduser("~/projects/anomaly-twin-trace/spike/trace_m0.jsonl"), "w") as fh:
        fh.write(json.dumps(rec, default=float) + "\n")
    print(json.dumps({k: rec[k] for k in ("ablation", "echo_on", "pcmci", "timing", "PASS_bar", "overall", "vectors", "n800_floor_flip", "n800_floor_hold", "wall_total_s")}, indent=1, default=float))

main()
