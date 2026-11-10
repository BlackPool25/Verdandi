"""Jev-track eval: template faithfulness (always) + live categorization (key-gated)."""
import glob

import numpy as np
import pandas as pd


def main(n_eps=60, seed=0):
    import sys

    sys.path.insert(0, ".")
    from src import jev
    from src.packet import emit_packet
    from src.reporter import build_card

    from src.diagnose import diagnose_multi_origin
    from src.twin import _DOWNSTREAM_MACHINES

    edges = {k: list(v) for k, v in _DOWNSTREAM_MACHINES.items()}
    paths = sorted(glob.glob("artifacts/m0b_mass_*.parquet"))
    df = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
    rng = np.random.default_rng(seed)
    eps = rng.choice(sorted(df["episode_id"].unique()), size=n_eps, replace=False)
    obs = [c for c in df.columns if c.startswith("obs_")]
    n_cit_ok = n_cit = n_abst = 0
    for ep in eps:
        g = df[df["episode_id"] == ep].sort_values("step").reset_index(drop=True)
        entries = diagnose_multi_origin(g, obs)
        ids = {e["machine"] for e in entries}
        pkt = emit_packet(
            [{"machine": e["machine"], "onset": e["onset"], "onset_kind": e["onset_kind"],
              "own_state": e.get("own_state"), "hop_est": -1} for e in entries],
            trigger=int(g["step"].max()), sensor_verdict="unknown",
            fault_family=None, ep=int(ep),
            paths=__import__("src.possibility", fromlist=["upstream_paths"]).upstream_paths(
                {e["machine"]: {"onset": e["onset"], "score": 0.5} for e in entries},
                edges, max(entries, key=lambda r: r["onset"])["machine"]) if entries else [],
            confidence={}, flow={})
        try:
            d = jev.decide(pkt, client=None)
        except jev.JevUnavailable:
            d = {"verdict": "abstain", "machine": None}
        card = build_card(pkt, d)
        if card["verdict"] == "abstain":
            n_abst += 1
            continue
        for c in card["claims"]:
            n_cit += 1
            n_cit_ok += c["evidence_id"] in ({t["id"] for t in pkt["trace"]} | {p["id"] for p in pkt["paths"]} | {pkt["id"]})
    print(f"template citation precision={n_cit_ok/max(1,n_cit):.3f} abstain_rate={n_abst/n_eps:.3f} (MEASURED, n={n_eps})", flush=True)
    print("live Jev categorization: SKIPPED (no JEV_API_KEY)", flush=True)


if __name__ == "__main__":
    main()
