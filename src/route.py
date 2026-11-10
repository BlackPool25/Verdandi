"""Ground-truth route extraction: onset order constrained to DAG reachability."""

from __future__ import annotations


def extract_route(df, root: str, edges: dict[str, list[str]]) -> list[str]:
    """Ordered list of machines that left RUN, reachable from root.

    Onset = first non-RUN tick per `state_<m>` column. A machine joins
    the route iff it is downstream-reachable from root (BFS on edges)
    and its onset is at/after the root's. Silent branches excluded.
    """
    states = [c for c in df.columns if c.startswith("state_")]
    onset: dict[str, int] = {}
    for c in states:
        m = c[len("state_"):]
        v = df[c].to_numpy(dtype=str)
        idx = __import__("numpy").flatnonzero(v != "RUN")
        if len(idx):
            onset[m] = int(df["step"].iloc[int(idx[0])]) if "step" in df.columns else int(idx[0])
    if root not in onset:
        return [root] if root else []
    # BFS downstream from root
    seen = {root}
    queue = [root]
    while queue:
        u = queue.pop(0)
        for w in edges.get(u, []):
            if w not in seen:
                seen.add(w)
                queue.append(w)
    t0 = onset[root]
    route = [m for m in seen if m in onset and onset[m] >= t0]
    route.sort(key=lambda m: (onset[m], m))
    if route and route[0] != root:
        route = [root] + [m for m in route if m != root]
    return route
