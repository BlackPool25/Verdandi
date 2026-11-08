"""Phase-1 detector (PRISSUE-10): per-machine quantile/IQR + VETO_ASM2 + versioned artifact.

Thresholds fit on clean calibration obs only (time-major [T_cal, N]).
Artifact pins code_version + cal seed so the M0b battery re-baselines on a
frozen twin with a recorded refit provenance.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np

from src import config

ARTIFACT_VERSION = "quantile-artifact-v1"
VETO_MACHINE = "ASM2"
VETO_MARGIN = 2.0


def fit_quantile_thresholds(
    cal_obs: np.ndarray,
    machine_names: list[str],
    *,
    q_high: float = 0.99,
    clean_mask: np.ndarray | None = None,
) -> dict[str, dict[str, float]]:
    """Fit per-machine max(q99, Tukey fence) thresholds on clean steps only."""
    x = np.asarray(cal_obs, dtype=float)
    if x.ndim != 2 or x.shape[1] != len(machine_names):
        raise ValueError(
            f"cal_obs must be [T, N={len(machine_names)}], got shape {x.shape}"
        )
    mask = (
        np.ones(x.shape[0], dtype=bool)
        if clean_mask is None
        else np.asarray(clean_mask, dtype=bool)
    )
    if mask.shape == (x.shape[0],):
        masks = np.repeat(mask[:, None], x.shape[1], axis=1)
    elif mask.shape == (x.shape[0], x.shape[1]):
        masks = mask
    else:
        raise ValueError(
            f"clean_mask shape {mask.shape} != T {(x.shape[0],)} or (T, N) {x.shape}"
        )
    if int(masks.sum()) < 1:
        raise ValueError("fit needs >= 1 clean step")
    out: dict[str, dict[str, float]] = {}
    for j, m in enumerate(machine_names):
        used = masks[:, j]
        if int(used.sum()) < 10:
            # Degenerate RUN history: fall back to the full column for this
            # machine (documented via n == T) rather than fitting on dust.
            used = np.ones(x.shape[0], dtype=bool)
        col = x[used, j]
        q99 = float(np.quantile(col, q_high))
        q01 = float(np.quantile(col, 1.0 - q_high))
        q1 = float(np.quantile(col, 0.25))
        q3 = float(np.quantile(col, 0.75))
        fence = float(q3 + 1.5 * (q3 - q1))
        low_fence = float(q1 - 1.5 * (q3 - q1))
        out[m] = {
            "q99": q99,
            "q01": q01,
            "q1": q1,
            "q3": q3,
            "fence": fence,
            "low_fence": low_fence,
            "thr": max(q99, fence),
            "thr_low": min(q01, low_fence),
            "n": float(int(used.sum())),
        }
    return out


def clean_run_mask(states: np.ndarray, start: int, end: int) -> np.ndarray:
    """Steps in [start, end) where every machine is RUN (all-RUN clean steps)."""
    s = np.asarray(states)
    if s.ndim != 2 or not (0 <= start <= end <= s.shape[1]):
        raise ValueError(
            f"states must be [N, T] with 0 <= {start} <= {end} <= {s.shape[1]}"
        )
    return np.array([(s[:, t] == "RUN").all() for t in range(start, end)], dtype=bool)


def save_artifact(
    path: str | pathlib.Path,
    thresholds: dict[str, dict[str, float]],
    *,
    cal_seed: int,
) -> dict:
    """Write versioned quantile-refit artifact (thresholds + provenance)."""
    artifact = {
        "version": ARTIFACT_VERSION,
        "code_version": config.CODE_VERSION,
        "twin_schema": config.TWIN_SCHEMA,
        "cal_seed": cal_seed,
        "machines": sorted(thresholds),
        "thresholds": thresholds,
    }
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
    return artifact


def load_artifact(path: str | pathlib.Path) -> dict:
    """Load artifact; fail closed on version/schema/machine mismatch."""
    p = pathlib.Path(path)
    try:
        artifact = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise ValueError(f"quantile artifact unreadable at {p}: {err}") from err
    if artifact.get("version") != ARTIFACT_VERSION:
        raise ValueError(
            f"quantile artifact version {artifact.get('version')!r} != {ARTIFACT_VERSION!r}"
        )
    if set(artifact.get("machines", [])) != set(config.MACHINE_NAMES):
        raise ValueError("quantile artifact machine roster != topology-A 26")
    return artifact


def detect_exceedance(
    obs: np.ndarray,
    thresholds: dict[str, dict[str, float]],
    machine_names: list[str],
    *,
    suppress: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Exceedance alarms + margins over a time-major [T, N] obs window.

    suppress (optional [T, N] bool, e.g. DOWN steps) clears alarms but keeps scores.
    """
    x = np.asarray(obs, dtype=float)
    if x.ndim != 2 or x.shape[1] != len(machine_names):
        raise ValueError(f"obs must be [T, N={len(machine_names)}], got {x.shape}")
    thr = np.array([float(thresholds[m]["thr"]) for m in machine_names])
    # thr_low missing (hand-built dicts, pre-fence artifacts) -> -inf: the low-side
    # margin (thr_low - x) stays negative, i.e. exactly the old upper-only behavior.
    # fit_quantile_thresholds always emits thr_low.
    thr_low = np.array(
        [float(thresholds[m].get("thr_low", float("-inf"))) for m in machine_names]
    )
    scores = np.maximum(x - thr, thr_low - x)
    alarms = scores > 0
    if suppress is not None:
        sup = np.asarray(suppress, dtype=bool)
        if sup.shape != alarms.shape:
            raise ValueError(
                f"suppress shape {sup.shape} != alarms shape {alarms.shape}"
            )
        alarms = alarms & ~sup
    return alarms, scores


def apply_veto_asm2(peaks: dict[str, float]) -> str:
    """Fixed veto-mask: noisy ASM2 wins top-1 only at >= 2x runner-up margin."""
    order = sorted(peaks, key=lambda m: peaks[m], reverse=True)
    top = order[0]
    if top == VETO_MACHINE and len(order) > 1:
        runner = order[1]
        if peaks[top] < VETO_MARGIN * peaks[runner] and peaks[runner] > 0:
            return runner
    return top


def attribute_top1(
    scores: np.ndarray,
    t0: int,
    dur: int,
    machine_names: list[str],
    *,
    lat_gate: int = 3,
    veto: bool = True,
) -> tuple[str, int]:
    """Rank top-1 machine by peak exceedance in [t0, t0+dur+lat_gate+5); latency in steps (999 = miss)."""
    s = np.asarray(scores, dtype=float)
    win = s[t0 : t0 + dur + lat_gate + 5]
    if win.size == 0:
        return machine_names[0], 999
    peaks = {m: float(win[:, j].max()) for j, m in enumerate(machine_names)}
    top = apply_veto_asm2(peaks) if veto else max(peaks, key=lambda m: peaks[m])
    hits = np.argwhere(s[t0 : t0 + dur + lat_gate + 5, machine_names.index(top)] > 0)
    lat = int(hits[0][0]) if len(hits) else 999
    return top, lat
