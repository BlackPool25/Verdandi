"""Per-incident breakdown report: path + per-node table + up/downstream + thread."""

from __future__ import annotations


def build_report(
    root: str,
    fault_family: str,
    scores: dict[str, float],
    edges: dict[str, list[str]],
    anchor: str,
    forecast: list[tuple[str, int, int]],
    meta: dict[str, dict],
    linked: list[tuple[str, int]],
) -> dict:
    """Assemble the operator-facing incident breakdown (pure function)."""
    from src.possibility import best_path

    path, path_prob = best_path(scores, edges, anchor)
    pred_tick = {m: t for m, t, _ in forecast}
    nodes = []
    for m in path:
        md = meta.get(m, {})
        nodes.append(
            {
                "machine": m,
                "onset": md.get("onset"),
                "own_state": md.get("own_state"),
                "metrics": md.get("metrics", []),
                "pred_tick": pred_tick.get(m),
                "actual_tick": md.get("onset"),
            }
        )
    return {
        "root": root,
        "fault_family": fault_family,
        "path": path,
        "path_prob": path_prob,
        "onset": meta.get(root, {}).get("onset"),
        "nodes": nodes,
        "upstream": f"{root} origin ({fault_family})",
        "downstream": [m for m in path[1:] if m != root],
        "linked": list(linked),
        "abstain": None if len(path) > 1 else "single-node",
    }
