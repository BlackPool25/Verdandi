"""Per-family CUSUM retrieval with threshold sweep (Task 2 eval).

Operating point per family: smallest h with clean-fire <= 0.05.
Streams cached once; sweep is pure-python head re-runs.
"""

import glob

import numpy as np
import pandas as pd


def make_heads(fam, h):
    from src.cusum_bank import EWMA, SlopePersist, SpikePath, TabularCUSUM

    if fam == "drift":
        return [EWMA(0.2, 0.0, h), SlopePersist(64, 10)]
    if fam == "bias":
        return [TabularCUSUM(0.5, h, 0.0, 1.0, adaptive=True)]
    if fam == "spike":
        return [SpikePath(4, h)]
    return [TabularCUSUM(0.5, h, 0.0, 1.0, adaptive=True)]


GRIDS = {
    "drift": [1.0, 2.0, 4.0],
    "bias": [5.0, 10.0, 20.0],
    "spike": [3.0, 4.0, 5.0],
    "loss": [5.0, 10.0, 20.0],
    "quality": [5.0, 10.0, 20.0],
    "breakdown": [5.0, 10.0, 20.0],
}


def _norm(v, n=30, floor=0.1):
    v = np.asarray(v, dtype=float)
    mu = float(np.mean(v[:n]))
    sd = max(float(np.std(v[:n])), floor)
    return ((v - mu) / sd).tolist()


def _streams(g, fam, machine):
    """Normalized causal streams for a family head. Buffers: dict of channels."""
    if fam in ("loss", "quality"):
        out = {}
        for c in [c for c in g.columns if c.startswith("buffer_")]:
            out[c] = _norm(g[c].to_numpy())
        return out
    col = f"obs_{machine}"
    v = g[col].to_numpy(dtype=float) if col in g.columns else np.zeros(len(g))
    return {"main": _norm(v)}


def _fires(heads, xs):
    from src.cusum_bank import EWMA, SlopePersist

    for i, x in enumerate(xs):
        for h in heads:
            r = h.step(x)
            if isinstance(h, (EWMA, SlopePersist)):
                if r[1] if isinstance(r, tuple) else r:
                    return i
            elif r:
                return i
    return None


def main():
    paths = sorted(glob.glob("artifacts/m0b_mass_*.parquet"))
    df = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
    fams = list(GRIDS)
    streams, truth = {}, {}
    for ep, g in df.groupby("episode_id", sort=False):
        g = g.sort_values("step").reset_index(drop=True)
        t = g[g["root_id_step"].to_numpy(dtype=str) != "none"]
        if t.empty:
            truth[ep] = None
            streams[ep] = {}
            for f in fams:
                streams[ep][f] = _streams(g, f, "B2")
        else:
            fam = str(t["fault_family"].mode().iloc[0])
            origin = str(t["root_id"].mode().iloc[0])
            truth[ep] = fam
            streams[ep] = {fam: _streams(g, fam, origin)}
    for f in fams:
        feps = [e for e, t in truth.items() if t == f]
        ceps = [e for e, t in truth.items() if t is None]
        for h in GRIDS[f]:
            hits, ticks, cf = 0, [], 0
            for e in feps:
                ch = streams[e][f]
                if isinstance(ch, dict):
                    t = None
                    for xs in ch.values():
                        t = _fires([hd.__class__(**_params(hd, h)) for hd in make_heads(f, h)], xs)
                        if t is not None:
                            break
                else:
                    t = _fires(make_heads(f, h), ch)
                if t is not None:
                    hits += 1
                    ticks.append(t)
            for e in ceps:
                ch = streams[e][f]
                if isinstance(ch, dict):
                    for xs in ch.values():
                        if _fires(make_heads(f, h), xs) is not None:
                            cf += 1
                            break
                elif _fires(make_heads(f, h), ch) is not None:
                    cf += 1
            print(f"{f:<10} h={h:<5} retrieval={hits/max(1,len(feps)):.3f} "
                  f"clean-fire={cf/max(1,len(ceps)):.3f} "
                  f"med-tick={float(np.median(ticks)) if ticks else -1:.0f} "
                  f"(MEASURED, n={len(feps)}/{len(ceps)})", flush=True)


def _params(head, h):
    from src.cusum_bank import EWMA, SlopePersist, SpikePath, TabularCUSUM

    if isinstance(head, EWMA):
        return {"lam": 0.2, "mu0": 0.0, "limit": h}
    if isinstance(head, SpikePath):
        return {"w": 4, "thr": h}
    if isinstance(head, SlopePersist):
        return {"w": 64, "need": 10}
    return {"k": 0.5, "h": h, "mu0": 0.0, "sigma0": 1.0,
            "adaptive": isinstance(head, TabularCUSUM) and head.adaptive}


if __name__ == "__main__":
    main()
