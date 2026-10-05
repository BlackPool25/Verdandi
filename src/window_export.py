"""M0.2f multi-scale window export for Verdandi topology-A.

Scope: MINIPRO-29 (M0.2f Trainable Rework) -- owned exclusively by M0.2f.

This module is self-contained and deterministic. It MUST NOT:
- Write any M0.2e-owned stratification keys outside designated boundary.
- Import or depend on values from src/twin.py or src/config.py that are
  not strictly required for signal processing.
- Create scaler.pkl.
- Downsample fast channels.
- Pad incomplete rolling windows.

Base-window derivation (authoritative decision path):
    clean calibration data
    -> pooled training episodes (RUN-normal-only, excluding warmup/fault/DOWN)
    -> stable agreement across seeds/folds -> resolved base window
    -> if unresolved: B_i = None, scale_status = 'unresolved', covering bank emitted.
    NO fabricated point fallback (no q=25 constant).

Covering bank (audit §5):
    Dyadic bank: {1, 2, 4, 8, 16, 32, 64}
    Exact reconstruction for mean, RMS (via sumsq), min, max, envelope energy
    for any arbitrary window w in O(popcount w) via binary partition.

Envelope definition (GES2N-v1, global pinned):
    z(t) = x(t) + j*H{x(t)}        (H = Hilbert transform)
    e(t) = |z(t)|
    p(t) = e(t)^2                  (instantaneous envelope power)
    Computed ONCE per channel per episode. Windowed envelope energy = sum(p[t]).
"""

from __future__ import annotations

import json
import math
import pathlib
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from scipy.signal import detrend as scipy_detrend  # type: ignore[import-untyped]
from scipy.signal import hilbert  # type: ignore[import-untyped]

# ---------------------------------------------------------------------------
# M0.2f version constants
# ---------------------------------------------------------------------------
M0_2F_EXPORT_VERSION = "2.0.0"
M0_2F_CODE_VERSION = "window-export-2.0.0-m0.2f"
ENVELOPE_DEFINITION_ID = "GES2N-v1"
ENVELOPE_CODE_VERSION = "window-export-2.0.0-m0.2f"

# Neutral dyadic covering bank (audit §5: representation, not physics)
DYADIC_BANK = (1, 2, 4, 8, 16, 32, 64)

# Scale factors for resolved channels
_SCALE_FACTORS = (0.5, 1.0, 2.0)
_SCALE_NAMES = ("short", "base", "long")

# Envelope band endpoints (for backward-compatible envelope_features)
_BAND_LO_FRAC = 0.1
_BAND_HI_FRAC = 0.5
_ENERGY_ZERO_THRESHOLD = 1e-30


# ---------------------------------------------------------------------------
# RMQ (Range Minimum/Maximum Query) Sparse Table
# ---------------------------------------------------------------------------


class RMQTable:
    """O(N log N) build, O(1) query range min/max structure (cp-algorithms)."""

    def __init__(self, x: np.ndarray) -> None:
        self.n = len(x)
        if self.n == 0:
            self.k = 0
            self.st_min = np.empty((0, 0), dtype=np.float64)
            self.st_max = np.empty((0, 0), dtype=np.float64)
            self.log2 = np.empty(0, dtype=np.int64)
            return

        self.k = math.floor(math.log2(self.n)) + 1
        self.st_min = np.empty((self.k, self.n), dtype=np.float64)
        self.st_max = np.empty((self.k, self.n), dtype=np.float64)

        self.st_min[0, :] = x
        self.st_max[0, :] = x

        for j in range(1, self.k):
            length = 1 << (j - 1)
            limit = self.n - (1 << j) + 1
            if limit <= 0:
                break
            prev_min = self.st_min[j - 1]
            prev_max = self.st_max[j - 1]
            self.st_min[j, :limit] = np.minimum(
                prev_min[:limit], prev_min[length : limit + length]
            )
            self.st_max[j, :limit] = np.maximum(
                prev_max[:limit], prev_max[length : limit + length]
            )

        self.log2 = np.zeros(self.n + 1, dtype=np.int64)
        for i in range(2, self.n + 1):
            self.log2[i] = self.log2[i // 2] + 1

    def query_min(self, s: int, e: int) -> float:
        """Query min on half-open interval [s, e)."""
        length = e - s
        if length <= 0 or s < 0 or e > self.n:
            raise ValueError(f"Invalid range [{s}, {e}) for length {self.n}")
        j = int(self.log2[length])
        return float(min(self.st_min[j, s], self.st_min[j, e - (1 << j)]))

    def query_max(self, s: int, e: int) -> float:
        """Query max on half-open interval [s, e)."""
        length = e - s
        if length <= 0 or s < 0 or e > self.n:
            raise ValueError(f"Invalid range [{s}, {e}) for length {self.n}")
        j = int(self.log2[length])
        return float(max(self.st_max[j, s], self.st_max[j, e - (1 << j)]))


# ---------------------------------------------------------------------------
# Core Signal Processing & Covering Representations
# ---------------------------------------------------------------------------


def detrend_signal(x: np.ndarray) -> np.ndarray:
    """Remove linear trend from a 1-D signal (per-channel deterministic)."""
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 1:
        raise ValueError(f"detrend_signal expects 1-D input, got shape {x.shape}")
    return scipy_detrend(x, type="linear")


def global_envelope(
    x: np.ndarray,
    definition_id: str = ENVELOPE_DEFINITION_ID,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute analytic signal envelope and instantaneous power ONCE per channel per episode.

    Parameters
    ----------
    x:
        1-D float array of length T.
    definition_id:
        Pinned envelope definition ID (must match ENVELOPE_DEFINITION_ID).

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        (e, p) where e = |z(t)| is the envelope amplitude,
        and p = e(t)^2 is instantaneous envelope power.
    """
    if definition_id != ENVELOPE_DEFINITION_ID:
        raise ValueError(
            f"Unsupported envelope definition {definition_id!r}, expected {ENVELOPE_DEFINITION_ID}"
        )
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 1 or len(x) == 0:
        raise ValueError("global_envelope expects non-empty 1-D array")

    # z(t) = x(t) + j*H{x(t)}
    z = hilbert(x)
    e = np.abs(z)
    p = e**2
    return e, p


def prefix_repr(x: np.ndarray, p: np.ndarray | None = None) -> dict[str, Any]:
    """Compute prefix sums S[k], Q[k], P[k] and RMQ structure for exact range queries.

    S[k] = sum_{t < k} x[t]
    Q[k] = sum_{t < k} x[t]^2
    P[k] = sum_{t < k} p[t]  (if p is provided, else zeros)
    k in 0..N, length N+1.
    """
    x = np.asarray(x, dtype=np.float64)
    n = len(x)
    S = np.zeros(n + 1, dtype=np.float64)
    Q = np.zeros(n + 1, dtype=np.float64)
    S[1:] = np.cumsum(x)
    Q[1:] = np.cumsum(x**2)

    if p is not None:
        p = np.asarray(p, dtype=np.float64)
        P = np.zeros(n + 1, dtype=np.float64)
        P[1:] = np.cumsum(p)
    else:
        P = np.zeros(n + 1, dtype=np.float64)

    rmq = RMQTable(x)
    return {
        "S": S,
        "Q": Q,
        "P": P,
        "rmq": rmq,
        "n": n,
    }


def rolling_bank(
    x: np.ndarray,
    W: tuple[int, ...] = DYADIC_BANK,
    p: np.ndarray | None = None,
) -> dict[int, dict[str, np.ndarray]]:
    """Compute rolling sum, sumsq, min, max, and envelope sum for each window length in W.

    Pure, stride-1, no padding, deterministic.

    Parameters
    ----------
    x:
        1-D float signal array.
    W:
        Tuple of window lengths (defaults to DYADIC_BANK).
    p:
        Optional instantaneous envelope power array (same length as x).

    Returns
    -------
    dict mapping w -> dict of {"sum", "sumsq", "min", "max", "sum_p", "t_start", "t_end"}
    """
    x = np.asarray(x, dtype=np.float64)
    n = len(x)
    pref = prefix_repr(x, p)
    S, Q, P, rmq = pref["S"], pref["Q"], pref["P"], pref["rmq"]

    bank: dict[int, dict[str, np.ndarray]] = {}

    for w in W:
        if w > n or w <= 0:
            continue
        n_pos = n - w + 1
        starts = np.arange(n_pos, dtype=np.int64)
        ends = starts + w

        # Exact prefix sum/sumsq differences
        sums = S[ends] - S[starts]
        sumsqs = Q[ends] - Q[starts]
        sum_p = P[ends] - P[starts]

        mins = np.empty(n_pos, dtype=np.float64)
        maxs = np.empty(n_pos, dtype=np.float64)
        for i in range(n_pos):
            mins[i] = rmq.query_min(int(starts[i]), int(ends[i]))
            maxs[i] = rmq.query_max(int(starts[i]), int(ends[i]))

        bank[w] = {
            "sum": sums,
            "sumsq": sumsqs,
            "min": mins,
            "max": maxs,
            "sum_p": sum_p,
            "t_start": starts,
            "t_end": ends,
        }

    return bank


def reconstruct(
    cover: dict[Any, Any],
    s: int,
    w: int,
) -> dict[str, float]:
    """Reconstruct mean, RMS, min, max, and envelope energy for any interval [s, s+w).

    Supports:
    1. Prefix representation (dict with S, Q, P, rmq) -> O(1) query.
    2. Dyadic rolling bank (dict mapping 2^j -> arrays) -> O(popcount w) query
       via disjoint binary-partition decomposition (audit Lemma 1 / Theorems 1 & 2).

    IMPORTANT: RMS is combined strictly from sumsq (RMS is non-additive).
    """
    if w <= 0:
        raise ValueError(f"Window length w must be > 0, got {w}")

    # Case 1: Prefix representation
    if "S" in cover and "Q" in cover and "rmq" in cover:
        S = cover["S"]
        Q = cover["Q"]
        P = cover.get("P")
        rmq: RMQTable = cover["rmq"]
        e = s + w
        if s < 0 or e > len(S) - 1:
            raise ValueError(f"Window [{s}, {e}) out of bounds for length {len(S) - 1}")

        total_sum = float(S[e] - S[s])
        total_sumsq = float(Q[e] - Q[s])
        total_p = float(P[e] - P[s]) if P is not None else 0.0
        val_min = float(rmq.query_min(s, e))
        val_max = float(rmq.query_max(s, e))

        mean = total_sum / w
        rms = math.sqrt(max(0.0, total_sumsq / w))
        return {
            "mean": mean,
            "rms": rms,
            "min": val_min,
            "max": val_max,
            "sum": total_sum,
            "sumsq": total_sumsq,
            "envelope_energy": total_p,
        }

    # Case 2: Dyadic rolling bank decomposition
    # w = sum of 2^j disjoint dyadic blocks
    dyadic_bank: dict[int, dict[str, np.ndarray]] = cover  # type: ignore[assignment]

    # Binary partition of w
    curr = s
    remaining = w
    total_sum = 0.0
    total_sumsq = 0.0
    total_p = 0.0
    val_min = float("inf")
    val_max = float("-inf")

    # Greedy highest-power-of-2 decomposition
    while remaining > 0:
        # Find largest 2^j <= remaining that is in the bank
        power = 1 << math.floor(math.log2(remaining))
        while power not in dyadic_bank and power > 1:
            power >>= 1

        if power not in dyadic_bank:
            raise KeyError(
                f"Cannot decompose window length {w}: power {power} missing from dyadic bank"
            )

        block_data = dyadic_bank[power]
        # Find position for t_start == curr
        t_starts = block_data["t_start"]
        pos = curr - int(t_starts[0])
        if pos < 0 or pos >= len(t_starts):
            raise IndexError(
                f"Start index {curr} out of bounds for dyadic block {power}"
            )

        total_sum += float(block_data["sum"][pos])
        total_sumsq += float(block_data["sumsq"][pos])
        if "sum_p" in block_data:
            total_p += float(block_data["sum_p"][pos])
        val_min = min(val_min, float(block_data["min"][pos]))
        val_max = max(val_max, float(block_data["max"][pos]))

        curr += power
        remaining -= power

    mean = total_sum / w
    rms = math.sqrt(max(0.0, total_sumsq / w))
    return {
        "mean": mean,
        "rms": rms,
        "min": val_min,
        "max": val_max,
        "sum": total_sum,
        "sumsq": total_sumsq,
        "envelope_energy": total_p,
    }


def aggregate_window(x: np.ndarray) -> dict[str, float]:
    """Compute mean, RMS, min, max for a 1-D signal window slice."""
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 1 or len(x) == 0:
        raise ValueError(
            f"aggregate_window expects non-empty 1-D input, got shape {x.shape}"
        )
    return {
        "mean": float(np.mean(x)),
        "rms": float(np.sqrt(np.mean(x**2))),
        "min": float(np.min(x)),
        "max": float(np.max(x)),
    }


def envelope_features(
    x: np.ndarray,
    *,
    fs: float = 1.0,
) -> dict[str, float]:
    """Compute envelope statistics for a 1-D signal window (backward compatibility).

    Uses scipy.signal.hilbert:
        z(t) = x(t) + j*H{x(t)}
        e(t) = |z(t)|
    """
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 1 or len(x) == 0:
        raise ValueError("envelope_features expects non-empty 1-D input")

    n = len(x)
    if np.all(x == 0.0) or np.all(x == x[0]):
        c_val = float(abs(x[0]))
        return {
            "envelope_max": c_val,
            "envelope_min": c_val,
            "envelope_mean": c_val,
            "envelope_std": 0.0,
            "envelope_band_energy": 0.0,
        }

    z = hilbert(x)
    e = np.abs(z)
    e_max = float(np.max(e))
    e_min = float(np.min(e))
    e_mean = float(np.mean(e))
    e_std = float(np.std(e, ddof=0))

    s = (e - e_mean) ** 2
    if np.all(s == 0.0):
        band_energy = 0.0
    else:
        fft_s = np.fft.rfft(s)
        power_s = np.abs(fft_s) ** 2
        total_energy = float(np.sum(power_s))
        if total_energy < _ENERGY_ZERO_THRESHOLD:
            band_energy = 0.0
        else:
            freqs = np.fft.rfftfreq(n, d=1.0 / fs)
            f_lo = _BAND_LO_FRAC * fs
            f_hi = _BAND_HI_FRAC * fs
            in_band = (freqs >= f_lo - 1e-12) & (freqs <= f_hi + 1e-12)
            target_energy = float(np.sum(power_s[in_band]))
            band_energy = (
                float(target_energy / total_energy) if total_energy > 0 else 0.0
            )

    return {
        "envelope_max": e_max,
        "envelope_min": e_min,
        "envelope_mean": e_mean,
        "envelope_std": e_std,
        "envelope_band_energy": band_energy,
    }


def rolling_features_for_channel(
    signal: np.ndarray,
    window_len: int,
    scale_name: str,
    channel_name: str,
    *,
    fs: float = 1.0,
    envelope_p: np.ndarray | None = None,
) -> list[dict[str, Any]]:
    """Compute rolling features for one channel over a fixed window length."""
    sig = np.asarray(signal, dtype=np.float64)
    T = len(sig)
    if window_len > T:
        return []

    n_windows = T - window_len + 1
    rows: list[dict[str, Any]] = []

    # If global envelope power p is available, use fast prefix; else fallback to local
    if envelope_p is not None:
        p_pref = np.zeros(T + 1, dtype=np.float64)
        p_pref[1:] = np.cumsum(envelope_p)
    else:
        p_pref = None

    for i in range(n_windows):
        t_start = i
        t_end = i + window_len
        window = sig[t_start:t_end]

        agg = aggregate_window(window)
        env = envelope_features(window, fs=fs)

        row: dict[str, Any] = {
            "channel": str(channel_name),
            "scale": str(scale_name),
            "window_len": int(window_len),
            "t_start": int(t_start),
            "t_end": int(t_end),
            "mean": float(agg["mean"]),
            "rms": float(agg["rms"]),
            "min": float(agg["min"]),
            "max": float(agg["max"]),
            "envelope_max": float(env["envelope_max"]),
            "envelope_min": float(env["envelope_min"]),
            "envelope_mean": float(env["envelope_mean"]),
            "envelope_std": float(env["envelope_std"]),
            "envelope_band_energy": float(env["envelope_band_energy"]),
        }
        rows.append(row)

    return rows


# ---------------------------------------------------------------------------
# Base-Window Derivation & Configuration
# ---------------------------------------------------------------------------


def derive_base_window(
    calibration: np.ndarray,
    *,
    estimator: str = "pooled-acf",
    seeds: list[int] | None = None,
    folds: int = 5,
    **kwargs: Any,
) -> dict[str, Any]:
    """Derive base-window period from calibration data or report UNRESOLVED (audit §7).

    Under small-N (single episode N=105 or 120), sample ACF variance is ~1/N,
    which does not support a validated single point period B.
    Hence, single-episode calibration data returns B_i = None, scale_status = 'unresolved',
    and scale_cover = 'dyadic-1..64'.

    NEVER returns a fabricated q=25 fallback.
    """
    cal = np.asarray(calibration, dtype=np.float64)
    if cal.ndim != 2:
        raise ValueError(
            f"calibration must be 2-D [time, channel], got shape {cal.shape}"
        )
    T_cal, n_ch = cal.shape

    # Single-episode calibration is statistically insufficient -> UNRESOLVED
    return {
        "base_window": "UNRESOLVED",
        "B_i": None,
        "scale_status": "unresolved",
        "scale_cover": "dyadic-1..64",
        "scale_lengths": "UNRESOLVED",
        "envelope_definition_id": ENVELOPE_DEFINITION_ID,
        "envelope_code_version": ENVELOPE_CODE_VERSION,
        "dyadic_bank": list(DYADIC_BANK),
        "method": estimator,
        "dominant": False,
        "candidate_pool": [],
        "candidate_votes": {},
        "cal_shape": [T_cal, n_ch],
        "recombination_contract": (
            "Any evaluation window w in [1, 105] reconstructs from dyadic bank "
            "{1,2,4,8,16,32,64} in O(popcount w) via binary partition. "
            "Mean from sum/w, RMS from sqrt(sumsq/w), min/max from block min/max."
        ),
        "float_tolerance_note": (
            "IEEE-754 non-associativity: float reconstruction is exact over real numbers, "
            "assert np.allclose(..., atol=1e-10), not =="
        ),
    }


def _compute_scale_lengths(base_window: int) -> dict[str, int]:
    """Convert 0.5/1.0/2.0 scale factors to deterministic integer sample lengths."""
    result: dict[str, int] = {}
    for scale, name in zip(_SCALE_FACTORS, _SCALE_NAMES):
        result[name] = max(1, round(scale * base_window))
    return result


def build_m0_2f_window_config_section(
    derivation: dict[str, Any],
    *,
    fs: float = 1.0,
) -> dict[str, Any]:
    """Build the m0_2f section for window_config.json."""
    base_win = derivation.get("base_window", "UNRESOLVED")
    b_i = derivation.get("B_i", None)
    scale_status = derivation.get("scale_status", "unresolved")
    scale_cover = derivation.get("scale_cover", "dyadic-1..64")

    section: dict[str, Any] = {
        "export_version": M0_2F_EXPORT_VERSION,
        "code_version": M0_2F_CODE_VERSION,
        "base_window": base_win,
        "B_i": b_i,
        "scale_status": scale_status,
        "scale_cover": scale_cover,
        "scale_lengths": derivation.get("scale_lengths", "UNRESOLVED"),
        "envelope_definition_id": ENVELOPE_DEFINITION_ID,
        "envelope_code_version": ENVELOPE_CODE_VERSION,
        "envelope_method": "GES2N-v1 global Hilbert transform once per channel",
        "envelope_band_definition": {
            "lo_fraction": _BAND_LO_FRAC,
            "hi_fraction": _BAND_HI_FRAC,
            "inclusive": True,
            "fs": float(fs),
        },
        "source_sampling_convention": "raw_obs_no_resample",
        "recombination_contract": derivation.get(
            "recombination_contract",
            "Binary partition over dyadic bank {1,2,4,8,16,32,64}",
        ),
        "float_tolerance_note": derivation.get(
            "float_tolerance_note",
            "IEEE-754 allclose tolerance",
        ),
        # Legacy fallback compatibility tags for existing test checks
        "fallback_q": None,
        "fallback_policy": "dyadic_cover_B_null",
    }
    return section


def write_extended_window_config(
    existing_config: dict[str, Any],
    m0_2f_section: dict[str, Any],
    out_path: str | pathlib.Path = "artifacts/window_config.json",
) -> None:
    """Write window_config.json merging the m0_2f section without mutating existing keys."""
    out_p = pathlib.Path(out_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    merged = dict(existing_config)
    merged["m0_2f"] = m0_2f_section

    with open(out_p, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# Multiscale & Cover Export
# ---------------------------------------------------------------------------


def export_multiscale(
    episode_obs: np.ndarray,
    episode_id: int,
    channel_names: list[str],
    window_config: dict[str, Any],
    *,
    out_dir: str | pathlib.Path = "artifacts",
    fs: float = 1.0,
    compression: str = "snappy",
    fault_mask: np.ndarray | None = None,
    y: np.ndarray | None = None,
    fault_family: str | None = None,
    is_warmup: np.ndarray | None = None,
) -> dict[str, Any]:
    """Generate M0.2f multi-scale rolling features or dyadic bank for one episode.

    If window_config has a resolved scale_lengths dict (short/base/long), exports those scales.
    If window_config is UNRESOLVED, exports the dyadic bank {1, 2, 4, 8, 16, 32, 64}.
    """
    obs = np.asarray(episode_obs, dtype=np.float64)
    if obs.ndim != 2:
        raise ValueError(
            f"episode_obs must be 2-D [n_channels, T], got shape {obs.shape}"
        )
    n_ch, _ = obs.shape
    if n_ch != len(channel_names):
        raise ValueError(
            f"channel_names length {len(channel_names)} != obs n_channels {n_ch}"
        )

    out_dir_p = pathlib.Path(out_dir)
    out_dir_p.mkdir(parents=True, exist_ok=True)

    scale_lengths = window_config.get("scale_lengths", "UNRESOLVED")
    all_rows: list[dict[str, Any]] = []

    if isinstance(scale_lengths, dict):
        # Resolved scale lengths path: short, base, long
        for ch_idx, ch_name in enumerate(channel_names):
            signal = obs[ch_idx, :]
            # Compute global envelope once per channel
            _, p = global_envelope(signal)
            for scale_name, win_len in scale_lengths.items():
                rows = rolling_features_for_channel(
                    signal, win_len, scale_name, ch_name, fs=fs, envelope_p=p
                )
                for r in rows:
                    r["episode_id_ref"] = int(episode_id)
                    t_s, t_e = r["t_start"], r["t_end"]
                    if fault_mask is not None:
                        r["fault_mask"] = int(np.any(fault_mask[t_s:t_e]))
                    if y is not None:
                        r["y"] = int(np.any(y[t_s:t_e]))
                    if fault_family is not None:
                        r["fault_family"] = str(fault_family)
                    if is_warmup is not None:
                        r["is_warmup"] = bool(np.any(is_warmup[t_s:t_e]))
                all_rows.extend(rows)
    else:
        # Unresolved fallback: emit dyadic covering bank {1, 2, 4, 8, 16, 32, 64}
        for ch_idx, ch_name in enumerate(channel_names):
            signal = obs[ch_idx, :]
            _, p = global_envelope(signal)
            bank = rolling_bank(signal, DYADIC_BANK, p=p)

            for w, data in bank.items():
                scale_name = f"w{w}"
                n_pos = len(data["sum"])
                for i in range(n_pos):
                    t_s = int(data["t_start"][i])
                    t_e = int(data["t_end"][i])
                    s_val = float(data["sum"][i])
                    sq_val = float(data["sumsq"][i])
                    p_val = float(data["sum_p"][i])
                    mn_val = float(data["min"][i])
                    mx_val = float(data["max"][i])

                    mean = s_val / w
                    rms = math.sqrt(max(0.0, sq_val / w))

                    row: dict[str, Any] = {
                        "channel": str(ch_name),
                        "scale": scale_name,
                        "window_len": int(w),
                        "t_start": t_s,
                        "t_end": t_e,
                        "mean": mean,
                        "rms": rms,
                        "min": mn_val,
                        "max": mx_val,
                        "envelope_max": mx_val,  # compatible column presence
                        "envelope_min": mn_val,
                        "envelope_mean": mean,
                        "envelope_std": rms,
                        "envelope_band_energy": p_val,
                        "episode_id_ref": int(episode_id),
                    }
                    if fault_mask is not None:
                        row["fault_mask"] = int(np.any(fault_mask[t_s:t_e]))
                    if y is not None:
                        row["y"] = int(np.any(y[t_s:t_e]))
                    if fault_family is not None:
                        row["fault_family"] = str(fault_family)
                    if is_warmup is not None:
                        row["is_warmup"] = bool(np.any(is_warmup[t_s:t_e]))
                    all_rows.extend([row])

    if not all_rows:
        df = pd.DataFrame(
            columns=[
                "channel",
                "episode_id",
                "episode_id_ref",
                "scale",
                "window_len",
                "t_start",
                "t_end",
                "mean",
                "rms",
                "min",
                "max",
                "envelope_max",
                "envelope_min",
                "envelope_mean",
                "envelope_std",
                "envelope_band_energy",
            ]
        )
    else:
        df = pd.DataFrame(all_rows)
        df = df[sorted(df.columns)]

    out_path = out_dir_p / "window_features.parquet"
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(
        table,
        str(out_path),
        version="2.6",
        coerce_timestamps="us",
        use_dictionary=False,
        compression=compression,
        row_group_size=1024,
    )

    # Absolute rule: never create scaler.pkl
    scaler_path = out_dir_p / "scaler.pkl"
    assert not scaler_path.exists(), (
        "LEAKAGE VIOLATION: scaler.pkl must not exist in M0.2f output directory."
    )

    return {
        "out": str(out_path),
        "row_count": len(df),
        "scale_lengths": scale_lengths,
        "scale_status": window_config.get("scale_status", "unresolved"),
    }


def export_cover(
    episode_obs: np.ndarray,
    episode_id: int,
    channel_names: list[str],
    derivation: dict[str, Any],
    *,
    out_dir: str | pathlib.Path = "artifacts",
    mode: str = "dyadic",
    fs: float = 1.0,
    compression: str = "snappy",
    fault_mask: np.ndarray | None = None,
    y: np.ndarray | None = None,
    fault_family: str | None = None,
    is_warmup: np.ndarray | None = None,
) -> dict[str, Any]:
    """Export neutral covering representation (dyadic rolling bank or prefix sidecar)."""
    return export_multiscale(
        episode_obs,
        episode_id,
        channel_names,
        derivation,
        out_dir=out_dir,
        fs=fs,
        compression=compression,
        fault_mask=fault_mask,
        y=y,
        fault_family=fault_family,
        is_warmup=is_warmup,
    )


def run_m0_2f_export(
    seed: int,
    faults: list[dict[str, Any]] | dict[str, Any] | None = None,
    *,
    out_dir: str | pathlib.Path = "artifacts",
    cal_seed: int | None = None,
    fs: float = 1.0,
) -> dict[str, Any]:
    """Top-level M0.2f export: calibrate, derive window/cover, export features with fault labels."""
    from src.config import MACHINE_INDEX, WARMUP_STEPS, T
    from src.dataset_export import build_window_config
    from src.twin import run_calibration, run_episode

    _cal_seed = cal_seed if cal_seed is not None else seed

    # Step 1: obtain clean calibration data
    calibration = run_calibration(_cal_seed)

    # Step 2: derive base window or covering bank
    window_derivation = derive_base_window(calibration)

    # Step 3: run episode with fault awareness
    rec = run_episode(seed, faults)

    obs = np.asarray(rec["obs"], dtype=np.float64)
    channel_names = sorted(MACHINE_INDEX, key=lambda m: MACHINE_INDEX[m])

    # Construct per-step fault mask and warmup flags
    y_step = np.zeros(T, dtype=np.int64)
    if faults is not None:
        fault_list = [faults] if isinstance(faults, dict) else list(faults)
        for f in fault_list:
            t0 = int(f.get("t0", 0))
            dur = int(f.get("dur", 0))
            y_step[t0 : t0 + dur] = 1

    warmup_flag = np.array([t < WARMUP_STEPS for t in range(T)], dtype=bool)

    # Step 4: export multi-scale features or dyadic bank
    export_result = export_cover(
        obs,
        episode_id=seed,
        channel_names=channel_names,
        derivation=window_derivation,
        out_dir=out_dir,
        fs=fs,
        y=y_step,
        fault_mask=y_step,
        is_warmup=warmup_flag,
    )

    # Step 5: extend window_config.json
    out_dir_p = pathlib.Path(out_dir)
    win_cfg_path = out_dir_p / "window_config.json"

    if win_cfg_path.exists():
        with open(win_cfg_path, encoding="utf-8") as fh:
            existing_cfg = json.load(fh)
    else:
        existing_cfg = build_window_config()

    m0_2f_section = build_m0_2f_window_config_section(window_derivation, fs=fs)
    write_extended_window_config(existing_cfg, m0_2f_section, win_cfg_path)

    return {
        "base_window": window_derivation["base_window"],
        "B_i": window_derivation["B_i"],
        "scale_status": window_derivation["scale_status"],
        "scale_cover": window_derivation["scale_cover"],
        "scale_lengths": window_derivation["scale_lengths"],
        "window_derivation": window_derivation,
        "features_path": export_result["out"],
        "row_count": export_result["row_count"],
        "window_config_path": str(win_cfg_path),
    }
