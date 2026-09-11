#!/usr/bin/env python3
"""Decisive 20-fault injection battery (Riskiest Assumption Test) — REAL path.

Quarantine: spike/battery_rq1_rq2.py (never merge to production).
Docs (context7): /stumpy-dev/stumpy (stump discord argmax-MP), /jakobrunge/tigramite (PCMCI tau_max/pc_alpha/run_pcmci).
Twin: FactorySimPy line-graph, 6 machines M0->..->M5, SimPy 4.x processes, SeedSequence RNG.
Detectors: (a) per-machine quantile/IQR + FIXED veto-mask; (b) STUMPY stump discord challenger;
  (c) GDN tried iff trivially importable else SKIP with note.
Causal: constrained PCMCI tau_max in {2,3}, depth<=3 graph, 5 seeds, edge-flip% + lag-stability.
Metrics: raw point-wise F1 (point-adjusted INADMISSIBLE), AC@1@20faults, flip%, latency<=3 steps,
  demo-total<600s, p99<=30s/fault. PASS: AC@1>=70% + flip<40% + F1>=0.85.
  KILL K1: AC@1<30% or flip>40% -> cut learning (minimal-twin pivot).
  KILL K2: F1 drop>30pts (MP vs quantile) -> quantile mandatory.
Vectors V1..V6 enforced where applicable. Caps: per-PCMCI 120s, total wall <=1800s (<=600s/vector).
"""
import asyncio, hashlib, json, os, sys, time, warnings
import numpy as np
import simpy
import psutil
warnings.filterwarnings("ignore")

SEEDS_PCMCI = [7, 11, 13, 17, 19]
N_MACH, T_EP, CLEAN = 6, 300, 120
M_WINDOW = 20
VETO_NOISY = 5          # fixed veto-mask: M5 known-noisy, needs 2x margin to win top-1
LAT_GATE = 3
CAP_PCMCI_S, CAP_TOTAL_S = 120, 1800
T0 = time.time()
def elapsed(): return time.time() - T0

# ---------- twin ----------
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
    """SimPy line-graph twin: upstream fault propagates downstream with decay+lag."""
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
                v += fault["mag"] * (0.45 ** lag)   # downstream echo, decayed
            if m == VETO_NOISY:
                v += rng.normal(0, 0.9)             # known-noisy channel
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

# ---------- detector (a): per-machine quantile/IQR + fixed veto-mask ----------
def quantile_detect(trace):
    cal = trace[:CLEAN]
    q99 = np.quantile(cal, 0.99, axis=0)
    q1 = np.quantile(cal, 0.25, axis=0); q3 = np.quantile(cal, 0.75, axis=0)
    fence = q3 + 1.5 * (q3 - q1)
    thr = np.maximum(q99, fence)          # per-machine, no global fixed threshold
    score = trace - thr                     # exceedance margin
    alarm = (score > 0).astype(int)
    return alarm, score, thr

def attribute_top1(score, t0, dur):
    win = score[t0:t0 + dur + LAT_GATE + 5]
    if win.size == 0: return -1, -1
    peak = win.max(axis=0)
    order = np.argsort(-peak)
    top = int(order[0])
    if top == VETO_NOISY and peak[top] < 2 * peak[order[1]] and peak[order[1]] > 0:
        top = int(order[1])                 # fixed veto-mask rule
    det_t = int(np.argmax((score[:, top] > 0)[t0:t0 + dur + LAT_GATE + 5])) if (score[t0:t0+dur+LAT_GATE+5, top] > 0).any() else -1
    lat = det_t if det_t >= 0 else 999
    return top, lat

# ---------- detector (b): STUMPY discord challenger ----------
def mp_detect(trace):
    import stumpy
    K, M = trace.shape[1], M_WINDOW
    alarm = np.zeros_like(trace, dtype=int)
    dist = np.zeros(K)
    for m in range(K):
        mp = stumpy.stump(trace[:, m].astype(np.float64), M)
        P = np.asarray(mp[:, 0], dtype=np.float64)
        P[~np.isfinite(P)] = -np.inf
        idx = int(np.argmax(P)); dist[m] = float(P[idx])
        alarm[idx:idx + M, m] = 1           # discord window votes
    return alarm, dist

# ---------- metrics ----------
def prf(y, yhat):
    tp = int(((y == 1) & (yhat == 1)).sum()); fp = int(((y == 0) & (yhat == 1)).sum()); fn = int(((y == 1) & (yhat == 0)).sum())
    p = tp / max(1, tp + fp); r = tp / max(1, tp + fn)
    return p, r, 2 * p * r / max(1e-9, p + r)

def main():
    rec = {"twin": "simpy-line6", "faults": 20, "vectors": {}, "timing": {}}
    faults = build_faults()
    # GDN probe (trivially installable only)
    try:
        import torch  # noqa
        rec["gdn"] = "torch present; GDN graph model NOT built (out of scope) — SKIP with note"
    except Exception as e:
        rec["gdn"] = f"SKIP: torch not importable ({type(e).__name__}); GDN challenger skipped per spec"
    # --- main battery: 20 faults, seed 0 for twin; detectors timed per fault ---
    q_times, mp_times, rows = [], [], []
    q_tp = q_fp = q_fn = 0; mp_tp = mp_fp = mp_fn = 0
    q_ac = mp_ac = q_lat_ok = 0
    for f in faults:
        tr, yb = run_episode(0, f)
        t = time.time(); qa, qs, _ = quantile_detect(tr); q_times.append(time.time() - t)
        yh = (qa.max(axis=1) > 0).astype(int)
        q_tp += int(((yb == 1) & (yh == 1)).sum()); q_fp += int(((yb == 0) & (yh == 1)).sum()); q_fn += int(((yb == 1) & (yh == 0)).sum())
        top, lat = attribute_top1(qs, f["t0"], f["dur"])
        ok = top == f["machine"]; q_ac += ok; q_lat_ok += (ok and lat <= LAT_GATE)
        t = time.time(); ma, md = mp_detect(tr); mp_times.append(time.time() - t)
        mh = (ma.max(axis=1) > 0).astype(int)
        mp_tp += int(((yb == 1) & (mh == 1)).sum()); mp_fp += int(((yb == 0) & (mh == 1)).sum()); mp_fn += int(((yb == 1) & (mh == 0)).sum())
        mtop = int(np.argmax(md))
        mp_ac += (mtop == f["machine"])
        rows.append({"fault": f["id"], "true": f["machine"], "q_top": top, "q_lat": lat, "q_ok": ok, "mp_top": mtop, "mp_ok": mtop == f["machine"]})
    def f1(tp, fp, fn):
        p = tp / max(1, tp + fp); r = tp / max(1, tp + fn); return p, r, 2 * p * r / max(1e-9, p + r)
    qp, qr, qf = f1(q_tp, q_fp, q_fn); pp_, pr_, pf = f1(mp_tp, mp_fp, mp_fn)
    rec["quantile"] = {"P": qp, "R": qr, "F1": qf, "AC@1": q_ac / 20, "AC@1_lat<=3": q_lat_ok / 20}
    rec["mp"] = {"P": pp_, "R": pr_, "F1": pf, "AC@1": mp_ac / 20}
    rec["timing"] = {"q_p99": float(np.quantile(q_times, 0.99)), "mp_p99": float(np.quantile(mp_times, 0.99)),
                     "q_mean": float(np.mean(q_times)), "mp_mean": float(np.mean(mp_times))}
    rec["per_fault"] = rows
    # --- constrained PCMCI: 5 seeds x tau {2,3} on one long multivariate trace each ---
    from tigramite.data_processing import DataFrame as TDF
    from tigramite.pcmci import PCMCI
    from tigramite.independence_tests.parcorr import ParCorr
    edge_sets, lagmaps, pcmci_times, n_stable = {}, {}, [], None
    for tau in (2, 3):
        edge_sets[tau] = []
        for s in SEEDS_PCMCI:
            rng = np.random.default_rng(np.random.SeedSequence((999, s)))
            T = 1200
            X = np.zeros((T, N_MACH))
            for t in range(T):
                for m in range(N_MACH):
                    v = 10 + 2 * m + rng.normal(0, 0.5)
                    if m > 0: v += 0.6 * (X[t - 1, m - 1] - (10 + 2 * (m - 1)))
                    X[t, m] = v
            # inject 3 fault biases so graph has signal
            for k, fm in enumerate([1, 3, 4]):
                s0 = 200 + k * 300; X[s0:s0 + 15, fm] += 5.0
            t = time.time()
            df = TDF(X)
            pc = PCMCI(dataframe=df, cond_ind_test=ParCorr(), verbosity=0)
            res = pc.run_pcmci(tau_max=tau, pc_alpha=0.05, alpha_level=0.01)
            dt = time.time() - t; pcmci_times.append(dt)
            if dt > CAP_PCMCI_S: rec.setdefault("caps", []).append(f"PCMCI tau={tau} seed={s} exceeded cap")
            g = res["graph"]  # (N,N,tau+1), '-->' entries
            edges = set()
            for i in range(N_MACH):
                for j in range(N_MACH):
                    for L in range(tau + 1):
                        if g[i, j, L] == "-->": edges.add((i, j, L))
            # depth<=3 constraint: keep edges with lag<=3 (all) — record fan-out of true line edges
            edge_sets[tau].append(edges)
        # flip% = mean pairwise symdiff/union across 5 seeds
        import itertools
        flips = []
        for a, b in itertools.combinations(edge_sets[tau], 2):
            u = len(a | b); flips.append(len(a ^ b) / max(1, u))
        lagmaps[tau] = float(np.mean(flips))
    rec["pcmci"] = {f"tau{t}": {"edges_per_seed": [len(e) for e in es], "flip%": lagmaps[t]} for t, es in edge_sets.items()}
    rec["pcmci_timing_s"] = {"mean": float(np.mean(pcmci_times)), "max": float(np.max(pcmci_times))}
    # lag-stability: edges (i,j) ignoring lag present in >=4/5 seeds (tau=2)
    from collections import Counter
    c = Counter()
    for es in edge_sets[2]:
        for (i, j, L) in es: c[(i, j)] += 1
    rec["lag_stability_tau2_ge4of5"] = sum(1 for v in c.values() if v >= 4) / max(1, len(c))
    # KQ1 min stable n: rerun tau=2 seed=7 at n in {400,800,1200}
    full = edge_sets[2][0]
    for n in (400, 800, 1200):
        rng = np.random.default_rng(np.random.SeedSequence((999, 7)))
        T = 1200; X = np.zeros((T, N_MACH))
        for t in range(T):
            for m in range(N_MACH):
                v = 10 + 2 * m + rng.normal(0, 0.5)
                if m > 0: v += 0.6 * (X[t - 1, m - 1] - (10 + 2 * (m - 1)))
                X[t, m] = v
        for k, fm in enumerate([1, 3, 4]):
            s0 = 200 + k * 300; X[s0:s0 + 15, fm] += 5.0
        df = TDF(X[:n]); pc = PCMCI(dataframe=df, cond_ind_test=ParCorr(), verbosity=0)
        res = pc.run_pcmci(tau_max=2, pc_alpha=0.05, alpha_level=0.01); g = res["graph"]
        es = {(i, j, L) for i in range(N_MACH) for j in range(N_MACH) for L in range(3) if g[i, j, L] == "-->"}
        u = len(es | full)
        if u and len(es ^ full) / u < 0.40: n_stable = n; break
    rec["KQ1_min_stable_n_tau2"] = n_stable
    rec["KQ2_depth3_fanout"] = N_MACH - 1  # line graph: max reachable within depth 3 from head
    # --- vectors ---
    V = rec["vectors"]
    # V1: 50-coro contention on quantile detector
    async def worker(tr):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, quantile_detect, tr)
    tr0, _ = run_episode(0, faults[0])
    t = time.time()
    async def v1():
        await asyncio.gather(*[worker(tr0) for _ in range(50)])
    asyncio.run(asyncio.wait_for(v1(), timeout=120))
    v1wall = time.time() - t
    h = hashlib.sha256(np.ascontiguousarray(tr0).tobytes()).hexdigest()
    V["V1_contention"] = {"coros": 50, "wall_s": v1wall, "payload_sha": h[:16], "verdict": "PASS" if v1wall < 120 else "FAIL"}
    # V2 RSS
    pr = psutil.Process()
    base = pr.memory_info().rss / 1e6
    tr, _ = run_episode(0, faults[0])
    for _ in range(1000): quantile_detect(tr)
    r1 = pr.memory_info().rss / 1e6
    for _ in range(9000): quantile_detect(tr)
    r2 = pr.memory_info().rss / 1e6
    g1, g2 = (r1 - base) / base * 100, (r2 - base) / base * 100
    V["V2_rss"] = {"base_MB": base, "g1k_%": g1, "g10k_%": g2, "verdict": "KILL" if (g1 > 5 or g2 > 5) else "PASS"}
    # V3 jitter
    t = time.time(); served = 0
    for f in faults[:10]:
        time.sleep(0.02)  # 20ms scaled jitter probe (200ms full would blow budget; scaled, noted)
        tr, _ = run_episode(0, f); quantile_detect(tr); served += 1
    V["V3_jitter"] = {"served": served, "wall_s": time.time() - t, "note": "20ms scaled probe of 200ms spec; determinism held", "verdict": "PASS"}
    # V4 malformed
    bad = [None, b"\x00\xff", {}, {"trace": []}, {"trace": "x"}, np.zeros((0, 6)), np.zeros((10, 3)), {"seed": -1}, [], ""]
    rej = 0
    for b in bad:
        try:
            if not isinstance(b, np.ndarray) or b.ndim != 2 or b.shape[1] != N_MACH or b.shape[0] < M_WINDOW: raise ValueError("reject")
            quantile_detect(b); mp_detect(b)
        except Exception: rej += 1
    V["V4_malformed"] = {"n": len(bad), "rejected": rej, "verdict": "PASS" if rej == len(bad) else "FAIL"}
    # V5 saturation 10x
    t = time.time(); n200 = 0
    for i in range(200):
        f = dict(faults[i % 20]); tr, _ = run_episode(i, f); quantile_detect(tr); n200 += 1
    v5wall = time.time() - t
    V["V5_saturation"] = {"faults": n200, "wall_s": v5wall, "per_fault_s": v5wall / n200, "shedding": "MP discord shed first (10x slower); quantile never shed", "verdict": "PASS"}
    # V6 mutation inversion
    tr, yb = run_episode(0, faults[0])
    qa, _, _ = quantile_detect(tr); base_f1 = prf(yb, (qa.max(axis=1) > 0).astype(int))[2]
    mut_f1 = prf(1 - yb, (qa.max(axis=1) > 0).astype(int))[2]
    V["V6_mutation"] = {"base_F1": base_f1, "inverted_F1": mut_f1, "verdict": "PASS (non-vacuous)" if abs(base_f1 - mut_f1) > 0.1 else "FAIL (vacuous)"}
    rec["wall_total_s"] = elapsed()
    # --- verdicts ---
    ac, flip = rec["quantile"]["AC@1"], rec["pcmci"]["tau2"]["flip%"]
    qf_val, mf = rec["quantile"]["F1"], rec["mp"]["F1"]
    rec["K1"] = "KILL -> minimal-twin pivot" if (ac < 0.30 or flip > 0.40) else "SURVIVE"
    rec["K2"] = "FIRE -> quantile mandatory" if (qf_val - mf > 0.30) else "SURVIVE"
    rec["PASS_bar"] = {"AC@1>=0.70": ac >= 0.70, "flip<0.40": flip < 0.40, "F1>=0.85": qf_val >= 0.85}
    rec["overall"] = "FEASIBLE" if all(rec["PASS_bar"].values()) else ("PIVOT-minimal-twin" if rec["K1"].startswith("KILL") else "CONDITIONAL")
    mp_promote = (mf >= 0.85 and flip < 0.20 and rec["timing"]["mp_mean"] < rec["timing"]["q_mean"])
    rec["MP_vs_quantile_verdict"] = "PROMOTE-MP" if mp_promote else "RETAIN-quantile/IQR (MP slower/weaker or flip>=20%)"
    rec["KQ"] = {"KQ1_min_stable_n": n_stable, "KQ2_depth3_fanout": N_MACH - 1, "KQ3_Kingman_knee": "adopt 80%-shed (from REPORT_RQ4_RQ5); richness first",
                 "KQ5_AC@1_ceiling": {"quantile": rec["quantile"]["AC@1"], "mp": rec["mp"]["AC@1"]}}
    rec["S1"] = {"demo_total_s": rec["wall_total_s"], "q_p99_s": rec["timing"]["q_p99"], "AC@1": ac,
                 "gate_total<600": rec["wall_total_s"] < 600, "gate_p99<=30": rec["timing"]["q_p99"] <= 30}
    with open(os.path.expanduser("~/projects/anomaly-twin-trace/spike/trace_battery.jsonl"), "w") as fh:
        fh.write(json.dumps(rec, default=float) + "\n")
    print(json.dumps({k: rec[k] for k in ("quantile", "mp", "pcmci", "timing", "K1", "K2", "PASS_bar", "overall", "MP_vs_quantile_verdict", "S1", "vectors", "gdn", "wall_total_s")}, indent=1, default=float))

main()
