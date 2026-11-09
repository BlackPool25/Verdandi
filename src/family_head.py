"""7-class fault typing (Head-A type) with per-family thresholds.

Closed-set is legitimate here: families are fixed (new ones need new
batteries). Open-set machinery stays on the origin side.
"""

from __future__ import annotations

import numpy as np


def train_family_head(X: np.ndarray, y: np.ndarray, seed: int = 0):
    from sklearn.ensemble import HistGradientBoostingClassifier  # type: ignore[import-untyped]

    classes = np.array(sorted(set(np.asarray(y).tolist())))
    clf = HistGradientBoostingClassifier(max_iter=300, random_state=seed)
    clf.fit(np.asarray(X), np.searchsorted(classes, np.asarray(y)))
    return clf, classes


def predict_family(model, classes, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    proba = model.predict_proba(np.asarray(X))
    idx = np.argmax(proba, axis=1)
    return np.asarray(classes)[idx], proba[np.arange(len(idx)), idx]


def tune_thresholds(
    y_true: np.ndarray, proba: np.ndarray, classes: np.ndarray
) -> dict[str, float]:
    """Per-family argmax-adjustment: threshold maximizing F1 per family.

    Returns {family: thr} on predicted-probability of that family.
    Quiet families land low (recall-first), loud families high.
    """
    out: dict[str, float] = {}
    for i, c in enumerate(classes):
        yt = (np.asarray(y_true) == c).astype(int)
        p = np.asarray(proba)[:, i]
        best_t, best_f1 = 0.5, -1.0
        for t in np.linspace(0.05, 0.95, 19):
            pred = (p >= t).astype(int)
            tp = int(((pred == 1) & (yt == 1)).sum())
            fp = int(((pred == 1) & (yt == 0)).sum())
            fn = int(((pred == 0) & (yt == 1)).sum())
            f1 = 2 * tp / max(1, 2 * tp + fp + fn)
            if f1 > best_f1:
                best_f1, best_t = f1, float(t)
        out[str(c)] = best_t
    return out
