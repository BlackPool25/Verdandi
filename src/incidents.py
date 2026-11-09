"""Open-incident registry: link triggers to incidents, or open new ones.

A new trigger attaches to an open incident only if reachable from that
incident's region within delay bounds; otherwise it opens a new incident.
Evidence the incident's forecast can't explain raises possible-second-fault.
"""

from __future__ import annotations


def _reachable(
    edges: dict[str, list[str]], src: str, dst: str, max_depth: int = 6
) -> int | None:
    dist = {src: 0}
    queue = [src]
    while queue:
        u = queue.pop(0)
        for v in edges.get(u, []):
            if v not in dist:
                dist[v] = dist[u] + 1
                queue.append(v)
    return dist.get(dst)


def _upstream(edges: dict[str, list[str]]) -> dict[str, list[str]]:
    rev: dict[str, list[str]] = {}
    for u, vs in edges.items():
        for v in vs:
            rev.setdefault(v, []).append(u)
    return rev


class Registry:
    """Open incident registry keyed by incident id."""

    def __init__(self) -> None:
        self._open: dict[str, dict] = {}
        self._used: set[str] = set()
        self._n = 0

    def _fresh_id(self) -> str:
        while True:
            self._n += 1
            cid = f"inc{self._n}"
            if cid not in self._used:
                self._used.add(cid)
                return cid

    def open(self, inc_id: str, root: str, onset: int, machines: set[str]) -> str:
        self._used.add(inc_id)
        self._open[inc_id] = {"root": root, "onset": onset, "machines": set(machines)}
        return inc_id

    def close(self, inc_id: str) -> None:
        del self._open[inc_id]

    def get(self, inc_id: str) -> dict:
        return self._open[inc_id]

    def link(
        self,
        machine: str,
        tick: int,
        edges: dict[str, list[str]],
        bounds: tuple[int, int] = (1, 6),
        flag_second: bool = False,
    ) -> str | tuple[str, str | None]:
        """Attach (machine, tick) to an open incident or open a new one.

        Tight attach: reachable within [dist*lo, dist*hi] of incident onset.
        Reachable but outside tight bounds + flag_second: attach with
        possible-second-fault (late unexplained evidence, not absorbed).
        Unreachable: always a new incident.
        """
        lo, hi = bounds
        rev = _upstream(edges)
        for inc_id, inc in self._open.items():
            for m in inc["machines"]:
                for a, b in ((m, machine), (machine, m)):
                    d = _reachable(edges, a, b)
                    if d is None:
                        d = _reachable(rev, a, b)
                    if d is None:
                        continue
                    dt = tick - inc["onset"]
                    span = max(d, 1)
                    if span * lo <= dt <= span * hi or (a == b and dt >= 0):
                        inc["machines"].add(machine)
                        if flag_second:
                            return inc_id, None
                        return inc_id
                    if flag_second and dt > 0:
                        inc["machines"].add(machine)
                        return inc_id, "possible-second-fault"
        new_id = self._fresh_id()
        self.open(new_id, machine, tick, {machine})
        if flag_second:
            return new_id, None
        return new_id
