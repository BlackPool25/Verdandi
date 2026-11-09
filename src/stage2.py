"""Stage-2 serving: train/save/load the stacked LambdaRank artifact."""

from __future__ import annotations

import numpy as np


def train_final(X: np.ndarray, y: np.ndarray, groups: np.ndarray, seed: int = 0):
    from src.ranker import train_ranker

    return train_ranker(np.asarray(X), np.asarray(y), np.asarray(groups), seed=seed)


def save(model, path: str) -> str:
    model.booster_.save_model(path)
    return path


def load(path: str):
    import lightgbm as lgb  # type: ignore[import-untyped]

    return lgb.Booster(model_file=path)
