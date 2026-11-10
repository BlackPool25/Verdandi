"""Tev-track eval: live categorization on fixed episodes (local tev1:4b)."""
import glob

import numpy as np
import pandas as pd


def main(n_eps=20, seed=0):
    import sys

    sys.path.insert(0, ".")
    from src.diagnose import diagnose_multi_origin
    from src.jev import QUESTIONS, TevClient
    from src.packet import emit_packet
    from src.twin import _DOWNSTREAM_MACHINES

    edges = {k: list(v) for k, v in _DOWNSTREAM_MACHINES.items()}
    paths = sorted(glob.glob("artifacts/m0b_mass_*.parquet"))
    df = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
    rng = np.random.default_rng(seed)
    eps = rng.choice(sorted(df["episode_id"].unique()), size=n_eps, replace=False)
    obs = [c for c in df.columns if c.startswith("obs_")]
    client = TevClient()
    import copy

    def evidence_for(g, m, t0):
        base = g[g["step"] < 120]
        post = g[(g["step"] >= t0) & (g["step"] < t0 + 40)]
        if len(post) == 0:
            return "no post-onset data"
        bits = []
        for ch, name in ((f"current_{m}", "current"), (f"obs_{m}", "obs")):
            if ch in g.columns and len(base):
                s = base[ch].std() or 1e-9
                if abs(post[ch].mean() - base[ch].mean()) > 3 * s:
                    bits.append(f"{name} moved")
        if f"tput_{m}" in g.columns and len(base):
            if post[f"tput_{m}"].mean() < base[f"tput_{m}"].mean() - 1e-9:
                bits.append("throughput dropped")
        if "cycle_lag" in g.columns and float(post["cycle_lag"].max()) > float(base["cycle_lag"].max()):
            bits.append("cycle stretched")
        return ", ".join(bits) if bits else "no channel movement"

    mh = fh = n = 0
    for ep in eps:
        g = df[df["episode_id"] == ep].sort_values("step").reset_index(drop=True)
        truth = g[g["root_id"] != "none"]
        if truth.empty:
            continue
        root = str(truth["root_id"].mode().iloc[0])
        famcol = "fault_family" if "fault_family" in g.columns else "family"
        fam = str(truth[famcol].mode().iloc[0])
        if fam == "none":
            fam = str(g[famcol][g[famcol] != "none"].mode().iloc[0]) if (g[famcol] != "none").any() else "none"
        entries = diagnose_multi_origin(g, obs)
        if not entries:
            continue
        cands = sorted({e["machine"] for e in entries})
        bym = {e["machine"]: e for e in entries}
        Q = copy.deepcopy(QUESTIONS)
        Q["machine"] = {"type": "choice",
                        "instructions": "Which machine originated the fault? "
                        "Earliest onset with DOWN/counter state originates; "
                        "STARVED-only is a downstream symptom, never the origin.",
                        "criteria": {m: f"onset tick {bym[m]['onset']}, "
                                     f"{bym[m]['onset_kind']} kind, state {bym[m].get('own_state')}"
                                     for m in cands}}
        pkt = emit_packet(
            [{"machine": e["machine"], "onset": e["onset"], "onset_kind": e["onset_kind"],
              "own_state": e.get("own_state"), "hop_est": -1,
              "evidence": evidence_for(g, e["machine"], e["onset"])} for e in entries],
            trigger=int(g["step"].max()), sensor_verdict="unknown",
            fault_family=None, ep=int(ep), paths=[], confidence={}, flow={})
        try:
            d = client.ask(pkt, Q)
        except Exception as ex:  # noqa: BLE001 - offline/model failure -> abstain path
            print(f"ep {ep}: client error {ex}", flush=True)
            continue
        n += 1
        mh += d["machine"]["choice"] == root
        fh += d["family"]["choice"] == fam
        print(f"ep {ep}: root={root} got={d['machine']['choice']} cands={cands} fam={fam} got={d['family']['choice']}", flush=True)
    print(f"tev machine top-1={mh/max(1,n):.3f} family top-1={fh/max(1,n):.3f} (MEASURED, n={n})", flush=True)


if __name__ == "__main__":
    main()
