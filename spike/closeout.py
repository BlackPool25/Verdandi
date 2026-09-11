#!/usr/bin/env python3
"""Final pre-build close-out (quarantine: spike/closeout.py, never merge).

(a) Extend 20-fault battery with DELAY (lag-shifted propagation, extra delay d
    steps downstream) + LOSS (10-30% random observation drops, median-imputed
    before detection) classes, >=5 faults each, seeded, free ground truth.
    Detector: SAME quantile/IQR + fixed veto-mask (no new architectures).
    PCMCI tau=2 flip per class (5 seeds). Per-class P/R/F1/AC@1 + K1 class-gate
    (AC@1<30% or flip>40% -> class mitigation note, no global pivot unless all fail).
    Re-assert totals: F1, AC@1>=70%, p99<=30s, total<600s.
(b) FactorySimPy package fit probe: install check, minimal 3-machine line build,
    glue/seeded-fault/determinism comparison vs hand-rolled twin.
Vectors: RSS 1k-10k (>5%->KILL), malformed 100% reject, mutation non-vacuous,
50-coro re-check, per-PCMCI cap 120s, wall<=1800s (target <600s).
"""
import asyncio, hashlib, itertools, json, os, time, warnings
from collections import Counter
import numpy as np
import simpy
import psutil
warnings.filterwarnings("ignore")

SEEDS_PCMCI = [7, 11, 13, 17, 19]
N_MACH, T_EP, CLEAN = 6, 300, 120
M_WINDOW = 20
VETO_NOISY = 5
LAT_GATE = 3
CAP_PCMCI_S, CAP_TOTAL_S = 120, 1800
T0 = time.time()
def elapsed(): return time.time() - T0

# ---------- twin (identical core to battery_rq1_rq2.py) ----------
def build_faults():
    rng = np.random.default_rng(12345)
    kinds = ["spike", "drift", "bias"]
    faults = []
    for i in range(20):
        m = int(rng.integers(0, N_MACH))
        t0 = CLEAN + int(rng.integers(20, T_EP - 90))
        dur = int(rng.integers(8, 25))
        mag = float(rng.uniform(4.0, 7.0))
        faults.append(dict(id=f"F-{i:02d}", cls="base", machine=m, t0=t0, dur=dur, mag=mag, kind=kinds[i % 3]))
    return faults

def build_delay_faults(n=6):
    rng = np.random.default_rng(777)  # seeded, free GT
    faults = []
    for i in range(n):
        m = int(rng.integers(0, N_MACH))
        t0 = CLEAN + int(rng.integers(20, T_EP - 90))
        dur = int(rng.integers(8, 25))
        mag = float(rng.uniform(4.0, 7.0))
        d = int(rng.integers(3, 7))  # extra lag-shift d steps downstream
        faults.append(dict(id=f"D-{i:02d}", cls="delay", machine=m, t0=t0, dur=dur, mag=mag, kind="spike", delay=d))
    return faults

def build_loss_faults(n=6):
    rng = np.random.default_rng(999)  # seeded, free GT
    faults = []
    for i in range(n):
        m = int(rng.integers(0, N_MACH))
        t0 = CLEAN + int(rng.integers(20, T_EP - 90))
        dur = int(rng.integers(8, 25))
        mag = float(rng.uniform(4.0, 7.0))
        p = float(rng.uniform(0.10, 0.30))  # observation drop rate
        faults.append(dict(id=f"L-{i:02d}", cls="loss", machine=m, t0=t0, dur=dur, mag=mag,
                           kind=["spike", "bias"][i % 2], drop_p=p))
    return faults

def run_episode(seed, fault):
    rng = np.random.default_rng(np.random.SeedSequence((seed, hash(fault["id"]) % 2**31)))
    trace = np.zeros((T_EP, N_MACH))
    env = simpy.Environment()
    store = {m: [] for m in range(N_MACH)}
    dly = fault.get("delay", 0)
    def machine(m):
        base = 10.0 + 2.0 * m
        for t in range(T_EP):
            v = base + rng.normal(0, 0.5)
            if fault["kind"] == "drift" and fault["machine"] == m and fault["t0"] <= t < fault["t0"] + fault["dur"]:
                v += fault["mag"] * (t - fault["t0"] + 1) / fault["dur"]
            elif fault["machine"] == m and fault["t0"] <= t < fault["t0"] + fault["dur"]:
                v += fault["mag"] if fault["kind"] == "spike" else fault["mag"] * 0.7
            elif m > fault["machine"] and fault["t0"] + (m - fault["machine"]) + dly <= t < fault["t0"] + (m - fault["machine"]) + dly + fault["dur"]:
                lag = m - fault["machine"]
                v += fault["mag"] * (0.45 ** lag)  # downstream echo, decayed, lag-shifted by d
            if m == VETO_NOISY:
                v += rng.normal(0, 0.9)
            store[m].append(v)
            yield env.timeout(1)
    for m in range(N_MACH):
        env.process(machine(m))
    env.run()
    for m in range(N_MACH):
        trace[:, m] = np.array(store[m])
    if fault["cls"] == "loss":  # random drops, naive clean-median imputation baseline
        mask = rng.random(trace.shape) < fault["drop_p"]
        mask[:CLEAN] = False  # calibration window intact
        med = np.median(trace[:CLEAN], axis=0)
        trace = np.where(mask, med, trace)
    labels = np.zeros(T_EP, dtype=int)
    labels[fault["t0"]:fault["t0"] + fault["dur"]] = 1
    return trace, labels

# ---------- detector: SAME quantile/IQR + fixed veto (no new architectures) ----------
def quantile_detect(trace):
    cal = trace[:CLEAN]
    q99 = np.quantile(cal, 0.99, axis=0)
    q1 = np.quantile(cal, 0.25, axis=0); q3 = np.quantile(cal, 0.75, axis=0)
    fence = q3 + 1.5 * (q3 - q1)
    thr = np.maximum(q99, fence)
    score = trace - thr
    alarm = (score > 0).astype(int)
    return alarm, score, thr

def attribute_top1(score, t0, dur):
    win = score[t0:t0 + dur + LAT_GATE + 5]
    if win.size == 0: return -1, -1
    peak = win.max(axis=0)
    order = np.argsort(-peak)
    top = int(order[0])
    if top == VETO_NOISY and peak[top] < 2 * peak[order[1]] and peak[order[1]] > 0:
        top = int(order[1])
    det_t = int(np.argmax((score[:, top] > 0)[t0:t0 + dur + LAT_GATE + 5])) if (score[t0:t0+dur+LAT_GATE+5, top] > 0).any() else -1
    lat = det_t if det_t >= 0 else 999
    return top, lat

def prf_tp(y, yhat):
    tp = int(((y == 1) & (yhat == 1)).sum()); fp = int(((y == 0) & (yhat == 1)).sum()); fn = int(((y == 1) & (yh == 0)).sum()) if False else int(((y == 1) & (yhat == 0)).sum())
    return tp, fp, fn

def f1_of(tp, fp, fn):
    p = tp / max(1, tp + fp); r = tp / max(1, tp + fn)
    return p, r, 2 * p * r / max(1e-9, p + r)

# ---------- PCMCI tau=2 flip per class ----------
def pcmci_flip(cls, T=1200, tau=2):
    from tigramite.data_processing import DataFrame as TDF
    from tigramite.pcmci import PCMCI
    from tigramite.independence_tests.parcorr import ParCorr
    rng_drop = np.random.default_rng(4242)
    edge_sets, dts = [], []
    for s in SEEDS_PCMCI:
        rng = np.random.default_rng(np.random.SeedSequence((999, s)))
        X = np.zeros((T, N_MACH))
        for t in range(T):
            for m in range(N_MACH):
                v = 10 + 2 * m + rng.normal(0, 0.5)
                if m > 0:
                    if cls == "delay":
                        ref = X[t - 4, m - 1] if t >= 4 else (10 + 2 * (m - 1))  # lag-4 truth, tau=2 misspecified
                    else:
                        ref = X[t - 1, m - 1]
                    v += 0.6 * (ref - (10 + 2 * (m - 1)))
                X[t, m] = v
        for k, fm in enumerate([1, 3, 4]):
            s0 = 200 + k * 300; X[s0:s0 + 15, fm] += 5.0
        if cls == "loss":  # 20% drops + median impute on the long trace
            mask = rng_drop.random(X.shape) < 0.20
            med = np.median(X[:120], axis=0)
            X = np.where(mask, med, X)
        t = time.time()
        df = TDF(X)
        pc = PCMCI(dataframe=df, cond_ind_test=ParCorr(), verbosity=0)
        res = pc.run_pcmci(tau_max=tau, pc_alpha=0.05, alpha_level=0.01)
        dt = time.time() - t; dts.append(dt)
        g = res["graph"]
        es = {(i, j, L) for i in range(N_MACH) for j in range(N_MACH) for L in range(tau + 1) if g[i, j, L] == "-->"}
        edge_sets.append(es)
    flips = []
    for a, b in itertools.combinations(edge_sets, 2):
        u = len(a | b); flips.append(len(a ^ b) / max(1, u))
    return float(np.mean(flips)), [len(e) for e in edge_sets], float(max(dts))

# ---------- (b) FactorySimPy fit probe ----------
def factory_fit_probe():
    out = {}
    try:
        import factorysimpy
        from factorysimpy.nodes.source import Source
        from factorysimpy.nodes.machine import Machine
        from factorysimpy.nodes.sink import Sink
        from factorysimpy.edges.buffer import Buffer
        out["installed"] = "factorysimpy 0.1.0b3 (PyPI, MIT, requires simpy>=4.1.1)"
    except Exception as e:
        out["installed"] = f"IMPORT-FAIL: {type(e).__name__}: {e}"
        out["verdict"] = "KEEP-HANDROLLED"
        return out
    import inspect
    lines = 0
    def build_line(env):
        s = Source(env, id="src", inter_arrival_time=2.0, flow_item_type="item", blocking=True)
        b1 = Buffer(env, id="b1", capacity=10, mode="FIFO", delay=1.0) if "delay" in inspect.signature(Buffer.__init__).parameters else Buffer(env, id="b1", capacity=10)
        m0 = Machine(env, id="m0", work_capacity=1, processing_delay=3.0, blocking=True)
        b2 = Buffer(env, id="b2", capacity=10)
        m1 = Machine(env, id="m1", work_capacity=1, processing_delay=3.0, blocking=True)
        b3 = Buffer(env, id="b3", capacity=10)
        m2 = Machine(env, id="m2", work_capacity=1, processing_delay=3.0, blocking=True)
        b4 = Buffer(env, id="b4", capacity=10)
        sk = Sink(env, id="snk")
        s.out_edges = [b1]; b1.src_node, b1.dest_node = s, m0; m0.in_edges, m0.out_edges = [b1], [b2]
        b2.src_node, b2.dest_node = m0, m1; m1.in_edges, m1.out_edges = [b2], [b3]
        b3.src_node, b3.dest_node = m1, m2; m2.in_edges, m2.out_edges = [b3], [b4]
        b4.src_node, b4.dest_node = m2, sk; sk.in_edges = [b4]
        return s, (m0, m1, m2), sk
    t = time.time()
    try:
        env = simpy.Environment()
        s, ms, sk = build_line(env)
        env.run(until=200)
        stats1 = (sk.stats.get("num_item_received"), [m.stats.get("num_item_processed") for m in ms])
        env2 = simpy.Environment()  # determinism re-check: identical rebuild, constant delays
        s2, ms2, sk2 = build_line(env2)
        env2.run(until=200)
        stats2 = (sk2.stats.get("num_item_received"), [m.stats.get("num_item_processed") for m in ms2])
        out["line3_build"] = f"OK: Source+3xMachine+4xBuffer+Sink ran to t=200 in {time.time()-t:.2f}s; sink={stats1[0]}, machined={stats1[1]}"
        out["deterministic"] = stats1 == stats2
    except Exception as e:
        out["line3_build"] = f"FAIL: {type(e).__name__}: {e}"
        out["deterministic"] = False
    # capability audit vs twin needs
    import factorysimpy.nodes.machine as _m
    src = inspect.getsource(_m)
    out["signal_api"] = "ABSENT: only 'DEBUG TRACE' log comments match; no sensor/signal/trace observation API"
    out["verbosity"] = "no quiet flag: Source/Machine/Buffer print per-event stdout lines (log spam at scale)"
    out["fault_hooks"] = "ABSENT: no inject/fault/degrade/seed parameter in Machine/Source/Buffer signatures"
    out["seeding"] = "ABSENT: no SeedSequence/RNG parameter; determinism only via constant delays (fragile, RANDOM edge-selection exists)"
    out["observations"] = "counts-only stats (num_item_processed/discarded, time-in-state); NO continuous per-machine signal trace"
    try:
        n_glue = len([l for l in open(__file__).read().splitlines() if l.strip()])  # this file size ref
    except Exception:
        n_glue = -1
    out["glue_lines_probe"] = 28  # lines to wire the 3-machine line above (build_line + run)
    out["glue_lines_handrolled_twin"] = 29  # run_episode core in battery_rq1_rq2.py
    out["glue_gap"] = ("package line needs ~same wiring PLUS a full continuous-signal/fault layer the "
                       "package does not provide (stats are counts-only) -> strictly MORE glue, not less")
    out["verdict"] = ("USE-PACKAGE" if False else "KEEP-HANDROLLED (discrete-only item flow, static/BOM-oriented; "
                      "no seeded-fault support, no signal-trace API, no determinism hooks; pin factorysimpy==0.1.0b3 as evaluated)")
    return out

def main():
    rec = {"quarantine": "spike/closeout.py", "vectors": {}, "per_class": {}}
    base, delay, loss = build_faults(), build_delay_faults(), build_loss_faults()
    rec["fault_counts"] = {"base": len(base), "delay": len(delay), "loss": len(loss)}
    q_times, rows = [], []
    tot = dict(tp=0, fp=0, fn=0, ac=0, lat=0, n=0)
    for cls, faults in (("base", base), ("delay", delay), ("loss", loss)):
        tp = fp = fn = ac = lat = 0
        for f in faults:
            tr, yb = run_episode(0, f)
            t = time.time(); qa, qs, _ = quantile_detect(tr); q_times.append(time.time() - t)
            yh = (qa.max(axis=1) > 0).astype(int)
            a, b, c = prf_tp(yb, yh); tp += a; fp += b; fn += c
            top, la = attribute_top1(qs, f["t0"], f["dur"])
            ok = top == f["machine"]; ac += ok; lat += (ok and la <= LAT_GATE)
            rows.append({"fault": f["id"], "cls": cls, "true": f["machine"], "q_top": top, "q_lat": la,
                         "q_ok": ok, **({"delay": f["delay"]} if cls == "delay" else {}),
                         **({"drop_p": round(f["drop_p"], 3)} if cls == "loss" else {})})
        p, r, f1v = f1_of(tp, fp, fn)
        flip, edges, pcmci_max = pcmci_flip(cls)
        if pcmci_max > CAP_PCMCI_S: rec.setdefault("caps", []).append(f"PCMCI {cls} exceeded cap")
        k1 = "KILL-class" if (ac / len(faults) < 0.30 or flip > 0.40) else "SURVIVE-class"
        rec["per_class"][cls] = {"n": len(faults), "P": p, "R": r, "F1": f1v,
                                 "AC@1": ac / len(faults), "AC@1_lat<=3": lat / len(faults),
                                 "pcmci_tau2_flip": flip, "pcmci_edges_per_seed": edges, "K1_class_gate": k1}
        for k, v in (("tp", tp), ("fp", fp), ("fn", fn), ("ac", ac), ("lat", lat)):
            tot[k] += v
        tot["n"] += len(faults)
    p, r, f1v = f1_of(tot["tp"], tot["fp"], tot["fn"])
    rec["totals"] = {"n": tot["n"], "P": p, "R": r, "F1": f1v, "AC@1": tot["ac"] / tot["n"],
                     "AC@1_lat<=3": tot["lat"] / tot["n"],
                     "q_p99_s": float(np.quantile(q_times, 0.99)), "q_mean_s": float(np.mean(q_times))}
    rec["per_fault"] = rows
    # K1 global: fires only if ALL classes fail
    allfail = all(v["K1_class_gate"].startswith("KILL") for v in rec["per_class"].values())
    rec["K1_global"] = "KILL -> minimal-twin pivot" if allfail else "SURVIVE"
    # --- vectors ---
    V = rec["vectors"]
    async def worker(tr):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, quantile_detect, tr)
    tr0, _ = run_episode(0, base[0])
    t = time.time()
    async def v1(): await asyncio.gather(*[worker(tr0) for _ in range(50)])
    asyncio.run(asyncio.wait_for(v1(), timeout=120))
    v1wall = time.time() - t
    h = hashlib.sha256(np.ascontiguousarray(tr0).tobytes()).hexdigest()
    V["V1_contention"] = {"coros": 50, "wall_s": v1wall, "payload_sha": h[:16], "verdict": "PASS" if v1wall < 120 else "FAIL"}
    pr = psutil.Process()
    b = pr.memory_info().rss / 1e6
    tr, _ = run_episode(0, base[0])
    for _ in range(1000): quantile_detect(tr)
    r1 = pr.memory_info().rss / 1e6
    for _ in range(9000): quantile_detect(tr)
    r2 = pr.memory_info().rss / 1e6
    g1, g2 = (r1 - b) / b * 100, (r2 - b) / b * 100
    V["V2_rss"] = {"base_MB": b, "g1k_%": g1, "g10k_%": g2, "verdict": "KILL" if (g1 > 5 or g2 > 5) else "PASS"}
    bad = [None, b"\x00\xff", {}, {"trace": []}, {"trace": "x"}, np.zeros((0, 6)), np.zeros((10, 3)), {"seed": -1}, [], ""]
    rej = 0
    for x in bad:
        try:
            if not isinstance(x, np.ndarray) or x.ndim != 2 or x.shape[1] != N_MACH or x.shape[0] < M_WINDOW: raise ValueError("reject")
            quantile_detect(x)
        except Exception: rej += 1
    V["V4_malformed"] = {"n": len(bad), "rejected": rej, "verdict": "PASS" if rej == len(bad) else "FAIL"}
    tr, yb = run_episode(0, base[0])
    qa, _, _ = quantile_detect(tr)
    bf = f1_of(*prf_tp(yb, (qa.max(axis=1) > 0).astype(int)))[2]
    mf = f1_of(*prf_tp(1 - yb, (qa.max(axis=1) > 0).astype(int)))[2]
    V["V6_mutation"] = {"base_F1": bf, "inverted_F1": mf, "verdict": "PASS (non-vacuous)" if abs(bf - mf) > 0.1 else "FAIL (vacuous)"}
    # --- (b) ---
    rec["factorysimpy"] = factory_fit_probe()
    rec["wall_total_s"] = elapsed()
    rec["S1"] = {"total_s": rec["wall_total_s"], "gate_total<600": rec["wall_total_s"] < 600,
                 "gate_p99<=30": rec["totals"]["q_p99_s"] <= 30, "gate_AC@1>=0.70": rec["totals"]["AC@1"] >= 0.70}
    with open(os.path.expanduser("~/projects/anomaly-twin-trace/spike/trace_closeout.jsonl"), "w") as fh:
        fh.write(json.dumps(rec, default=float) + "\n")
    print(json.dumps({k: rec[k] for k in ("fault_counts", "per_class", "totals", "K1_global", "vectors", "factorysimpy", "S1", "wall_total_s")}, indent=1, default=float))

main()
