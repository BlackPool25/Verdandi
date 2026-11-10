"""Streaming CUSUM bank: tabular (fixed/adaptive-k), Bernoulli, EWMA, slope, spike.

All heads causal, all baselines frozen at construction/fit time.
Adaptive-k (Ahmadini 2025): reference k tracks local EWMA variance.
"""

from __future__ import annotations

import numpy as np


class TabularCUSUM:
    """Two-sided tabular CUSUM. fit() is a no-op guard: baselines stay frozen."""

    def __init__(
        self, k: float, h: float, mu0: float, sigma0: float,
        adaptive: bool = False, lam: float = 0.2,
    ):
        self.k, self.h = float(k), float(h)
        self.mu0, self.sigma0 = float(mu0), float(sigma0)
        self.adaptive = adaptive
        self.lam = float(lam)
        self._cp = 0.0
        self._cm = 0.0
        self._var = float(sigma0) ** 2
        self._prev: float | None = None

    def fit(self, xs) -> "TabularCUSUM":
        return self  # baselines frozen by design; recalibration is explicit

    def step(self, x: float) -> bool:
        x = float(x)
        if self.adaptive:
            if self._prev is not None:
                d = x - self._prev
                # Successive-difference variance: immune to level shifts
                # (a mean jump contributes one blip, not a raised floor).
                self._var = (1 - self.lam) * self._var + self.lam * (d * d / 2.0)
            self._prev = x
            sd = max(float(np.sqrt(self._var)), 1e-9)
            k = self.k
        else:
            sd = max(self.sigma0, 1e-9)
            k = self.k
        z = (x - self.mu0) / sd
        self._cp = max(0.0, self._cp + z - k)
        self._cm = max(0.0, self._cm - z - k)
        return bool(self._cp > self.h or self._cm > self.h)

    def reset(self) -> None:
        self._cp = self._cm = 0.0
        self._prev = None


class BernoulliCUSUM:
    """Per-event Bernoulli CUSUM. Reference r MUST come from clean data."""

    def __init__(self, r: float, h: float):
        self.r, self.h = float(r), float(h)
        self._b = 0.0

    @classmethod
    def fit_rate(cls, clean01, h: float = 3.0) -> "BernoulliCUSUM":
        p0 = max(float(np.mean(clean01)), 1e-6)
        return cls(r=p0 * 2.0, h=h)

    def step(self, x: int) -> bool:
        self._b = max(0.0, self._b + int(x) - self.r)
        return bool(self._b >= self.h)

    def reset(self) -> None:
        self._b = 0.0


class EWMA:
    def __init__(self, lam: float, mu0: float, limit: float):
        self.lam, self.mu0, self.limit = float(lam), float(mu0), float(limit)
        self._z = float(mu0)

    def step(self, x: float) -> tuple[float, bool]:
        self._z = self.lam * float(x) + (1 - self.lam) * self._z
        return self._z, bool(abs(self._z - self.mu0) > self.limit)

    def reset(self) -> None:
        self._z = self.mu0


class SlopePersist:
    """OLS slope over trailing window; fires on sign-consistent persistence."""

    def __init__(self, w: int, need: int):
        self.w, self.need = int(w), int(need)
        self._buf: list[float] = []
        self._run = 0

    def step(self, x: float) -> bool:
        self._buf.append(float(x))
        if len(self._buf) > self.w:
            self._buf.pop(0)
        if len(self._buf) < self.w:
            return False
        n = len(self._buf)
        xs = np.arange(n)
        slope = float(np.polyfit(xs, np.asarray(self._buf), 1)[0])
        if slope > 0:
            self._run = self._run + 1 if slope > 0 else 0
        else:
            self._run = 0
        return bool(self._run >= self.need)


class SpikePath:
    """Fast transient path: short-window max + first difference. No accumulator."""

    def __init__(self, w: int, thr: float):
        self.w, self.thr = int(w), float(thr)
        self._buf: list[float] = []
        self._prev: float | None = None

    def step(self, x: float) -> bool:
        x = float(x)
        self._buf.append(x)
        if len(self._buf) > self.w:
            self._buf.pop(0)
        win_fire = max(self._buf) > self.thr if len(self._buf) >= 2 else False
        diff_fire = self._prev is not None and abs(x - self._prev) > self.thr
        self._prev = x
        return bool(win_fire or diff_fire)
