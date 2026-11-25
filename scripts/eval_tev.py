"""Tev-track eval: live categorization on fixed episodes (local tev1:4b)."""
import argparse
import glob

import numpy as np
import pandas as pd

TEACHER_TOP1 = 0.671  # stage-1 majority-vote teacher, same battery (kill-bar ref)
KILL_BAR = 0.3  # machine top-1 below this -> one gated SC re-measure, then KILL
EVAL_TIMEOUT = 30  # per-call eval timeout; class default (300s) stays untouched
SC_N = 5  # self-consistency votes, machine-only, eval-only (never prod path)
DECISION_TIMEOUT = 60  # per-ask subprocess timeout for the CLI transport
EVAL_MODEL = "tev1:4b"  # decision-model build: answers ONLY via `ollama run --ask/--choice`


def parse_decision_output(text, options):
    """Parse `ollama run --ask` stdout ("M1 72%" or bare label)."""
    import re

    for opt in options:
        m = re.search(r"\b" + re.escape(opt) + r"\b\s*(\d+)?\s*%", text)
        if m:
            return opt, (int(m.group(1)) / 100.0 if m.group(1) else 1.0)
    for opt in options:
        if re.search(r"\b" + re.escape(opt) + r"\b", text):
            return opt, 1.0
    return None, 0.0


class CliDecisionClient:
    """Eval-only transport for decision-model builds (no /api/generate, no chat).

    Same ask() shape as TevClient; one `ollama run --ask/--choice` per question.
    """

    def __init__(self, model=EVAL_MODEL, timeout=DECISION_TIMEOUT, runner=None):
        import subprocess as _sp

        self.model, self.timeout = model, timeout
        self._run = runner or _sp.run

    def _ask_one(self, state, question, options):
        import re

        argv = ["ollama", "run", self.model, "--ask", question]
        descs = options if isinstance(options, dict) else {}
        for o in (list(descs) if descs else options):
            argv += ["--choice", f"{o}={descs.get(o, o)}"]
        p = self._run(argv, input=state.encode(), capture_output=True, timeout=self.timeout)
        text = p.stdout.decode("utf-8", errors="replace") if isinstance(p.stdout, bytes) else p.stdout
        opts = list(descs) if descs else list(options)
        return parse_decision_output(re.sub(r"\s+", " ", text), opts)

    def ask(self, packet, questions):
        from src.jev import render_state as _render

        state = _render(packet)
        out = {}
        for q, spec_q in questions.items():
            crit = spec_q.get("criteria", {}) if isinstance(spec_q, dict) else {}
            opts = list(crit.keys()) or ["null"]
            descs = {o: str(crit[o])[:200] for o in opts} if crit else {}
            choice, prob = self._ask_one(
                state, spec_q.get("instructions", q) if isinstance(spec_q, dict) else q,
                descs or opts)
            out[q] = {"choice": choice if choice in opts else None,
                      "probability": prob if choice in opts else 0.0}
        return out


def shuffled_criteria(criteria, rng):
    """Return criteria dict with keys permuted via rng (deterministic given seed).

    Dict insertion order is the option order handed to the decision client
    (--choice argv order), so permuting here permutes presented option order.
    """
    keys = list(criteria)
    return {k: criteria[k] for k in rng.permutation(keys)}


def apply_order(questions, order, rng):
    """Apply criteria order to every choice question. 'fixed' is a no-op."""
    import copy

    if order == "fixed":
        return questions
    if order != "shuffled":
        raise ValueError(f"unknown order {order!r}")
    out = copy.deepcopy(questions)
    for spec in out.values():
        crit = spec.get("criteria", {}) if isinstance(spec, dict) else {}
        if len(crit) > 1:
            spec["criteria"] = shuffled_criteria(crit, rng)
    return out


def kill_verdict(machine_top1):
    """Win-or-kill disposition vs the teacher bar (62)."""
    if machine_top1 >= TEACHER_TOP1:
        return "WIN"
    if machine_top1 < KILL_BAR:
        return "KILL"
    return "HOLD"


def machine_sc_vote(client, pkt, q_machine, n=SC_N):
    """Majority vote over n machine-only asks; None if no vote lands."""
    votes = []
    for _ in range(n):
        try:
            d = client.ask(pkt, {"machine": q_machine})
        except Exception:  # noqa: BLE001 - one hung vote must not stall SC
            continue
        c = (d.get("machine") or {}).get("choice")
        if c is not None:
            votes.append(c)
    if not votes:
        return None
    return max(sorted(set(votes)), key=votes.count)


def sample_episodes(paths, n_eps, seed):
    """Episode ids sampled seed-deterministically; reads only the id column.

    Same episode set as the old full-concat path (sorted unique ids +
    default_rng(seed).choice), at a fraction of the memory.
    """
    import pandas as pd

    ep_ids = sorted({e for p in paths
                     for e in pd.read_parquet(p, columns=["episode_id"])["episode_id"].unique()})
    return np.random.default_rng(seed).choice(ep_ids, size=n_eps, replace=False)


def load_episodes(paths, eps):
    """Load only rows for sampled episodes (shared-machine OOM guard).

    Column projection covers every family the eval + diagnose touch
    (ids/truth/step, obs/state/current/tput/tputlag channels, cycle_lag);
    all other uses are guarded `in g.columns` checks over these families.
    """
    import pandas as pd

    import pyarrow.parquet as pq

    schema = pq.read_schema(paths[0])
    keep = [f for f in schema.names
            if f in ("episode_id", "step", "root_id", "fault_family", "cycle_lag")
            or f.startswith(("obs_", "state_", "current_", "tput_", "tputlag_"))]
    want = set(eps)
    frames = []
    for p in paths:
        g = pd.read_parquet(p, columns=keep)
        g = g[g["episode_id"].isin(want)]
        if len(g):
            frames.append(g)
    return pd.concat(frames, ignore_index=True)


def main(n_eps=60, seed=0, transport="cli", order="fixed", order_seed=0):
    import sys

    sys.path.insert(0, ".")
    from src.diagnose import diagnose_multi_origin
    from src.jev import QUESTIONS, TevClient
    from src.packet import emit_packet
    from src.twin import _DOWNSTREAM_MACHINES

    edges = {k: list(v) for k, v in _DOWNSTREAM_MACHINES.items()}
    paths = sorted(glob.glob("artifacts/m0b_mass_*.parquet"))
    order_rng = np.random.default_rng(order_seed)  # separate stream: episode set pinned by seed
    eps = sample_episodes(paths, n_eps, seed)
    df = load_episodes(paths, eps)
    obs = [c for c in df.columns if c.startswith("obs_")]
    def make_client(temperature=0.0):
        if transport == "cli":
            return CliDecisionClient()
        return TevClient(timeout=EVAL_TIMEOUT, temperature=temperature)

    client = make_client()
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

    mh = fh = n = nulls = 0
    sc_episodes = []  # (ep, root, sc_choice) for the gated re-measure
    for ep in eps:
        g = df[df["episode_id"] == ep].sort_values("step").reset_index(drop=True)
        truth = g[g["root_id"] != "none"]
        if truth.empty:
            continue
        root = str(truth["root_id"].mode().iloc[0])
        famcol = "fault_family" if "fault_family" in g.columns else "fault_family"
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
            d = client.ask(pkt, apply_order(Q, order, order_rng))
        except Exception as ex:  # noqa: BLE001 - offline/model failure -> abstain path
            print(f"ep {ep}: client error {ex}", flush=True)
            n += 1
            nulls += 1
            continue
        n += 1
        mc = d["machine"]["choice"]
        if mc is None:
            nulls += 1
        mh += mc == root
        fh += d["fault_family"]["choice"] == fam
        print(f"ep {ep}: root={root} got={mc} cands={cands} fam={fam} got={d['fault_family']['choice']}", flush=True)
    mt1 = mh / max(1, n)
    ft1 = fh / max(1, n)
    print(f"tev machine top-1={mt1:.3f} family top-1={ft1:.3f} null_rate={nulls/max(1,n):.3f} (MEASURED, n={n}, order={order}, order_seed={order_seed})", flush=True)
    print(f"kill-bar: machine {mt1:.3f} vs teacher {TEACHER_TOP1:.3f} -> {kill_verdict(mt1)}", flush=True)
    if mt1 < KILL_BAR:
        sc_client = make_client(temperature=0.7)
        sc_hits = 0
        for ep in eps:
            g = df[df["episode_id"] == ep].sort_values("step").reset_index(drop=True)
            truth = g[g["root_id"] != "none"]
            if truth.empty:
                continue
            root = str(truth["root_id"].mode().iloc[0])
            entries = diagnose_multi_origin(g, obs)
            if not entries:
                continue
            cands = sorted({e["machine"] for e in entries})
            bym = {e["machine"]: e for e in entries}
            qm = {"type": "choice",
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
            sc = machine_sc_vote(sc_client, pkt, apply_order({"machine": qm}, order, order_rng)["machine"])
            sc_episodes.append((int(ep), root, sc))
            sc_hits += sc == root
            print(f"sc ep {ep}: root={root} sc5={sc}", flush=True)
        sc1 = sc_hits / max(1, len(sc_episodes))
        print(f"tev self-consistency machine top-1={sc1:.3f} (MEASURED, n={len(sc_episodes)}, votes={SC_N})", flush=True)
        print(f"kill-bar after SC: {sc1:.3f} vs {KILL_BAR} -> {kill_verdict(sc1)}; ranker stays decider", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--transport", default="cli", choices=("cli", "http"))
    ap.add_argument("--order", default="fixed", choices=("fixed", "shuffled"))
    ap.add_argument("--order-seed", type=int, default=0)
    a = ap.parse_args()
    main(n_eps=a.n, seed=a.seed, transport=a.transport, order=a.order, order_seed=a.order_seed)
