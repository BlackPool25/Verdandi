"""Sensor-path randomization + twin realism audits (sim2real lane).

All transforms apply to recorded observations AFTER the episode runs: they
model the sensor path (floors, drift, gain, dropouts, clipping), never plant
dynamics — so the twin core stays byte-identical and every transform is
opt-in. In-loop effects (duty cycle, load shifts) are explicitly out of
scope here; they need variant plumbing, not post-hoc math.
"""

from __future__ import annotations

import numpy as np

WIDE_PRESET = {
    "floor_mult": (1.0, 3.0),
    "drift_abs": 0.05,
    "gain": (0.95, 1.05),
    "dropout_rate": 0.01,
    "clip_sigma": 8.0,
}


def apply_sensor_rug(
    obs: np.ndarray,
    sigmas: np.ndarray,
    *,
    rng: np.random.Generator | None = None,
    spec: dict | None = None,
) -> np.ndarray:
    """Randomize sensor path per machine: floor widening, drift, gain, dropouts.

    obs: (n_steps, n_chan); sigmas: per-channel clean std. Returns new array.
    Deterministic on (seed, inputs). Identity iff spec is None.
    """
    if spec is None:
        return np.array(obs, dtype=float)
    r = rng or np.random.default_rng()
    x = np.asarray(obs, dtype=float)
    n, d = x.shape
    sig = np.asarray(sigmas, dtype=float).reshape(1, d)
    flo, fhi = spec.get("floor_mult", (1.0, 1.0))
    mult = r.uniform(flo, fhi, size=(1, d))
    extra = np.sqrt(np.maximum(mult**2 - 1.0, 0.0)) * sig
    x = x + r.normal(0.0, 1.0, size=(n, d)) * np.broadcast_to(extra, (n, d))
    drift_abs = float(spec.get("drift_abs", 0.0))
    if drift_abs > 0:
        walk = np.cumsum(r.normal(0, drift_abs / 10, size=(n, d)), axis=0)
        walk -= np.linspace(0, 1, n)[:, None] * walk[-1:]
        x = x + walk * sig
    glo, ghi = spec.get("gain", (1.0, 1.0))
    x = x * r.uniform(glo, ghi, size=(1, d))
    drop = float(spec.get("dropout_rate", 0.0))
    if drop > 0:
        mask = r.random((n, d)) < drop
        for j in range(d):
            idx = np.flatnonzero(mask[:, j])
            for i in idx:
                if i > 0:
                    x[i, j] = x[i - 1, j]  # hold-last; i==0 keeps its sample
    clip = float(spec.get("clip_sigma", np.inf))
    if np.isfinite(clip):
        med = np.median(x, axis=0, keepdims=True)
        x = np.clip(x, med - clip * sig, med + clip * sig)
    return x


def noise_floor_table(obs: np.ndarray) -> dict[int, float]:
    """Per-channel std — the twin-vs-real audit row (flags uniform floors)."""
    x = np.asarray(obs, dtype=float)
    return {j: float(np.std(x[:, j])) for j in range(x.shape[1])}


def twin_discriminator_auc(Xa: np.ndarray, Xb: np.ndarray, *, seed: int = 0) -> float:
    """Can a linear probe tell batch A from batch B? ~0.5 = indistinguishable.

    Used twin-vs-twin (origin signatures, augmentation ablations) and, with
    real data, twin-vs-real. AUC >> 0.5 means the model can cheat on batch
    identity instead of learning faults.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import cross_val_predict

    X = np.vstack([np.asarray(Xa, dtype=float), np.asarray(Xb, dtype=float)])
    y = np.array([0] * len(Xa) + [1] * len(Xb))
    p = cross_val_predict(
        LogisticRegression(max_iter=200), X, y, cv=3, method="predict_proba"
    )[:, 1]
    return float(roc_auc_score(y, p))
