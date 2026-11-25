# FINAL-f5 style — src/possibility.py conventions

Read-only review of `src/possibility.py` (379 lines) in worktree `m0b-t-build`.
A new function in this module must match the following.

## 1. Typing style
- `from __future__ import annotations` at top; builtin generics only: `dict[str, list[str]]`, `dict[str, float]`, `list[str]`, `list[tuple[list[str], float]]`, `tuple[int, int]`.
- Union with `|`: `str | None` (e.g. `trigger: str | None = None`, `dict[str, str | None]`, `int | None`).
- All params annotated, defaults inline (`radius: int = 1`, `alpha: float = 0.85`, `per_hop: tuple[int, int] = (1, 6)`).
- Locals annotated on first bind: `rev: dict[str, list[str]]`, `memo: dict[str, float]`, `extra: set[str]`, `scored: list[tuple[list[str], float]]`.
- Untyped payload dict: `evidence: dict[str, dict]` with access via `float(evidence[m].get("score", 0.0))` and `evidence[m]["onset"]`.
- Defensive coercion: `max(float(x), 0.0)`, `max(float(scores[n]), 1e-12)`.
- Private helpers `_`-prefixed (`_reverse`, `_bfs`, `_all_paths`); local `import math` inside scoring functions is accepted.

## 2. Error style: return fallbacks, never raise
- No `raise` / `assert` / `try/except` anywhere in the file (grep: no matches).
- Missing-anchor degrades to a single-node result; empty/zero totals degrade via `or 1.0`; zero scores floored via `1e-12`.
- Deterministic order via `sorted(...)` (`ms = sorted(rank_probs)`, `sorted(rev.get(...))`).

## 3. Docstring format
- Triple-quoted, first line = terse summary; optional body = formula + semantics + `Returns ...` sentence.
- No `Args:/Returns:` sections, no type repetition. Module docstring states pruning invariant (`26 -> ~3-5`).

## 4. Dict return shapes
- Probabilities: `dict[str, float]` normalized to sum 1 (`{m: v / tot ...}` with `tot = sum(...) or 1.0`).
- Paths: `tuple[list[str], float]` (`best_path`), `list[tuple[list[str], float]]` normalized over k (`kbest_paths`, `upstream_paths`).
- Rich: `tuple[list[str], float, dict[str, float]]` (`best_cause_path` → path root→anchor, value, memo copy).
- Optional second shape via flag: `rank_nodes(...) -> dict | tuple[dict, list[str]]` (`return_independent` adds `indep: list[str]`).

## 5. Naming: do NOT use `assert_` here
- Public names are snake_case verb phrases: `neighborhood`, `flow_teleport`, `best_cause_path`, `kbest_paths`, `upstream_paths`, `best_path`, `rank_nodes`.
- `def assert_*` occurs only outside this module (`dataset_export.py:62 `assert_warmup_excluded(df) -> None``, `train_pipeline.py:179 `assert_no_scaler_artifact(...) -> None``) for validation returning `None`. A new scoring/possibility function must not use the `assert_` prefix.

## 3 most relevant examples (verbatim)

1. `flow_teleport` — typing + `or 1.0` + normalized `dict[str, float]` return:
```python
def flow_teleport(
    rank_probs: dict[str, float],
    flow_mass: dict[str, float],
    alpha: float = 0.85,
) -> dict[str, float]:
    """Flow-teleport blend (task 64): personalized-teleport PPR pattern.
    ...
    """
    ms = sorted(rank_probs)
    tot_r = sum(max(float(rank_probs[m]), 0.0) for m in ms) or 1.0
    r = {m: max(float(rank_probs[m]), 0.0) / tot_r for m in ms}
    raw_t = {m: r[m] * max(float(flow_mass.get(m, 0.0)), 0.0) for m in ms}
    tot_t = sum(raw_t.values())
    t = {m: (raw_t[m] / tot_t if tot_t > 0 else r[m]) for m in ms}
    out = {m: alpha * r[m] + (1.0 - alpha) * t[m] for m in ms}
    tot = sum(out.values()) or 1.0
    return {m: v / tot for m, v in out.items()}
```

2. `best_cause_path` — docstring formula + early fallback return, no raise:
```python
def best_cause_path(
    evidence: dict[str, dict],
    edges: dict[str, list[str]],
    anchor: str,
    per_hop: tuple[int, int] = (1, 6),
    support_weight: float = 0.5,
) -> tuple[list[str], float, dict[str, float]]:
    """Recursive upstream cause search, memoized (rod-cutting form).

    B(m) = own(m) + max(0, max over upstream u of [B(u) + bonus(u->m)])
    with bonus gated on onset-delay consistency (dist*lo <= dt <= dist*hi).
    DFS backwards from anchor with memo; backpointers give the path.
    Returns (path root->anchor, path value, values dict).
    Inconsistent edges are pruned (-inf), never forced.
    """
    ...
    if anchor not in evidence:
        return [anchor], 0.0, {}
```

3. `rank_nodes` — `dict | tuple` return shape + `str | None` + softmax `or 1.0`:
```python
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
    ...
    mx = max(raw.values()) if raw else 0.0
    exps = {k: math.exp(v - mx) for k, v in raw.items()}
    tot = sum(exps.values()) or 1.0
    out = {k: v / tot for k, v in exps.items()}
    if not return_independent:
        return out
```
