"""Possibility engine: forward-backward node marginals over a DAG neighborhood.

Candidates = trigger machine +/-1 hop, expanded one more hop only through
changed machines (topology prunes 26 -> ~3-5). Each node scores its own
change evidence plus downstream explanatory support (cause explains
effects): reachable changed machines with onsets inside per-hop delay
bounds. Scores normalize to possibilities (sum 1); unreachable loud nodes
are flagged independent, never forced into the path.
"""

from __future__ import annotations

import math


def _reverse(edges: dict[str, list[str]]) -> dict[str, list[str]]:
    rev: dict[str, list[str]] = {m: [] for m in edges}
    for u, vs in edges.items():
        for v in vs:
            rev.setdefault(v, []).append(u)
    return rev


def _bfs(start: str, adj: dict[str, list[str]]) -> dict[str, int]:
    dist = {start: 0}
    queue = [start]
    while queue:
        u = queue.pop(0)
        for v in adj.get(u, []):
            if v not in dist:
                dist[v] = dist[u] + 1
                queue.append(v)
    return dist


def neighborhood(
    trigger: str, changed: set[str], edges: dict[str, list[str]], radius: int = 1
) -> set[str]:
    """Trigger +/-radius hops, expanded one more hop through changed nodes."""
    rev = _reverse(edges)
    adj = {
        m: sorted(set(edges.get(m, []) + rev.get(m, []))) for m in set(edges) | set(rev)
    }
    base = {trigger}
    frontier = {trigger}
    for _ in range(radius):
        nxt = set()
        for u in frontier:
            nxt.update(adj.get(u, []))
        base |= nxt
        frontier = nxt
    # conditional expansion: one more hop through changed nodes only
    extra: set[str] = set()
    for u in base:
        if u in changed:
            extra.update(adj.get(u, []))
    return base | extra


def rank_nodes(
    evidence: dict[str, dict],
    edges: dict[str, list[str]],
    per_hop: tuple[int, int] = (1, 6),
    support_weight: float = 0.5,
    return_independent: bool = False,
    trigger: str | None = None,
) -> dict | tuple[dict, list[str]]:
    """Node possibility = own evidence + downstream explanatory support.

    support(r) = sum over changed v reachable downstream from r with
    onset_v - onset_r inside [dist*lo, dist*hi] of w * score(v).
    Normalized with softmax to possibilities summing to 1.
    """
    lo, hi = per_hop
    cands = sorted(evidence)
    raw: dict[str, float] = {}
    for r in cands:
        er = evidence[r]
        total = float(er.get("score", 0.0))
        dists = _bfs(r, edges)
        for v in cands:
            if v == r or v not in dists:
                continue
            dt = evidence[v]["onset"] - er["onset"]
            if dt >= 0 and dists[v] * lo <= dt <= dists[v] * hi:
                total += support_weight * float(evidence[v].get("score", 0.0))
        raw[r] = total
    mx = max(raw.values()) if raw else 0.0
    exps = {k: math.exp(v - mx) for k, v in raw.items()}
    tot = sum(exps.values()) or 1.0
    out = {k: v / tot for k, v in exps.items()}
    if not return_independent:
        return out
    # Independence anchors on the trigger (the event under diagnosis):
    # evidenced but unreachable-from-trigger nodes are separate faults,
    # not victims. Falls back to top-1 only when trigger is unknown.
    anchor = (
        trigger if trigger in out else (max(out, key=lambda k: out[k]) if out else None)
    )
    indep = []
    if anchor is not None:
        down = _bfs(anchor, edges)
        up = _bfs(anchor, _reverse(edges))
        for v in cands:
            if v != anchor and v not in down and v not in up:
                indep.append(v)
    return out, indep
