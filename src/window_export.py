"""M0.2f multi-scale window export for Verdandi topology-A.

Scope: MINIPRO-29 (Gowtham) -- owned exclusively by M0.2f.

This module is self-contained and deterministic. It MUST NOT:
- Write any M0.2e-owned stratification keys.
- Import or depend on values from src/twin.py or src/config.py that are
  not strictly required for signal processing.
- Create scaler.pkl.
- Downsample fast channels.
- Pad incomplete rolling windows.

Base-window derivation (authoritative decision path):
    clean calibration data
    -> detrend (per-channel linear)
    -> per-channel autocorrelation (biased, ignoring lag 0)
    -> per-channel DFT power spectrum peak
    -> AC-DFT agreement: candidate lag appears as both AC peak and DFT peak
    -> deterministic median of agreed candidates (tie-break: smallest)
    -> measured base_window (integer samples)
    -> short = max(1, round(0.5 * base))
       base  = max(1, round(1.0 * base))
       long  = max(1, round(2.0 * base))

Envelope definition (TL-provided, exact):
    z(t) = x(t) + j*H{x(t)}        (H = Hilbert transform)
    e(t) = |z(t)|
    envelope_max  = max(e)
    envelope_min  = min(e)
    envelope_mean = mean(e)
    envelope_std  = population std(e)  [ddof=0]
    s(t) = (e(t) - mean(e))^2
    S(f) = |FFT(s(t))|
    target band: 0.1*fs <= f <= 0.5*fs   (inclusive)
    envelope_band_energy = sum(target |S(f)|^2) / sum(all |S(f)|^2)
    If total spectral energy is zero/near-zero, returns 0.0 (safe deterministic).

Output artifacts (additive, do not overwrite M0.2e contract):
    artifacts/window_features.parquet  -- M0.2f rolling feature rows
    artifacts/window_config.json       -- extended with "m0_2f" section
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from scipy.signal import detrend as scipy_detrend
from scipy.signal import hilbert

# ---------------------------------------------------------------------------
# M0.2f version constants (never copy from config.py)
# ---------------------------------------------------------------------------
M0_2F_EXPORT_VERSION = "1.0.0"
M0_2F_CODE_VERSION = "window-export-1.0.0-m0.2f"

# Scale factors (the spec calls these "step-equivalent" aggregates).
_SCALE_FACTORS = (0.5, 1.0, 2.0)
_SCALE_NAMES = ("short", "base", "long")

# Envelope band endpoints (inclusive, fraction of fs).
_BAND_LO_FRAC = 0.1
_BAND_HI_FRAC = 0.5

# Minimum spectral energy denominator to avoid NaN/Inf.
_ENERGY_ZERO_THRESHOLD = 1e-30

# Fallback base-window logic: when no dominant period is detected, use a
# fixed engineering fallback q=25 to generate three scales:
#   short = q   = 25
#   base  = 2q  = 50
#   long  = 4q  = 100
# q=25 is an ENGINEERING FALLBACK CHOICE, not a proven optimal value.
# A future project stage (out of scope) may train a model for scale selection.
_FALLBACK_Q = 25


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detrend_signal(x: np.ndarray) -> np.ndarray:
    """Remove linear trend from a 1-D signal (per-channel deterministic).

    Parameters
    ----------
    x:
        1-D float array of length T.

    Returns
    -------
    np.ndarray
        Detrended signal of same shape, float64.
    """
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 1:
        raise ValueError(f"detrend_signal expects 1-D input, got shape {x.shape}")
    return scipy_detrend(x, type="linear")


def _compute_fallback_scale_lengths() -> dict[str, int]:
    """Compute fallback scale lengths from the engineering fallback q.

    Returns {"short": q, "base": 2*q, "long": 4*q} with q = _FALLBACK_Q = 25.
    """
    q = _FALLBACK_Q
    return {"short": q, "base": 2 * q, "long": 4 * q}


def derive_base_window(
    calibration: np.ndarray,
    **kwargs: Any,
) -> dict[str, Any]:
    """Derive a deterministic base-window period from clean calibration data.

    Currently, the Verdandi repo has no authoritative numeric base-window value.
    The base window is UNRESOLVED, and the fallback engineering scales
    q=25 -> {short=25, base=50, long=100} are used.

    When a resolved base window B is available (future), returns:
        scale_lengths = {short: 0.5B, base: B, long: 2B}

    When unresolved (current state), returns:
        scale_lengths = {short: 25, base: 50, long: 100}
        scale_status = "unresolved_fallback"
    """
    cal = np.asarray(calibration, dtype=np.float64)
    if cal.ndim != 2:
        raise ValueError(
            f"calibration must be 2-D [time, channel], got shape {cal.shape}"
        )
    T_cal, n_ch = cal.shape

    fallback_lengths = _compute_fallback_scale_lengths()

    return {
        "base_window": "UNRESOLVED",
        "scale_lengths": fallback_lengths,
        "method": "UNRESOLVED",
        "dominant": False,
        "candidate_pool": [],
        "candidate_votes": {},
        "cal_shape": [T_cal, n_ch],
        "scale_status": "unresolved_fallback",
        "fallback_q": _FALLBACK_Q,
        "fallback_policy": "q_2q_4q",
        "fallback_note": (
            "No authoritative base-window value found in repo. "
            f"Using engineering fallback q={_FALLBACK_Q} -> "
            f"short={fallback_lengths['short']}, base={fallback_lengths['base']}, "
            f"long={fallback_lengths['long']}."
        ),
    }


def _compute_scale_lengths(base_window: int) -> dict[str, int]:
    """Convert 0.5/1.0/2.0 scale factors to deterministic integer sample lengths.

    short = max(1, round(0.5 * base_window))
    base  = max(1, round(1.0 * base_window))
    long  = max(1, round(2.0 * base_window))
    """
    result: dict[str, int] = {}
    for scale, name in zip(_SCALE_FACTORS, _SCALE_NAMES):
        result[name] = max(1, round(scale * base_window))
    return result


def aggregate_window(x: np.ndarray) -> dict[str, float]:
    """Compute mean, RMS, min, max for a 1-D signal window.

    Parameters
    ----------
    x:
        1-D float array (a single rolling window slice for one channel).

    Returns
    -------
    dict with keys: mean, rms, min, max
    """
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
    """Compute envelope statistics for a 1-D signal window.

    Uses scipy.signal.hilbert to form the analytic signal:
        z(t) = x(t) + j*H{x(t)}
        e(t) = |z(t)|

    Returns:
        envelope_max   = max(e)
        envelope_min   = min(e)
        envelope_mean  = mean(e)
        envelope_std   = population std(e)  [ddof=0]
        envelope_band_energy = sum(target |S(f)|^2) / sum(all |S(f)|^2)
            where s(t) = (e(t) - mean(e))^2
                  S(f) = |FFT(s(t))|
                  target band: 0.1*fs <= f <= 0.5*fs (inclusive)
            If total energy is zero/near-zero, returns 0.0 (safe deterministic).

    Parameters
    ----------
    x:
        1-D float array (signal window).
    fs:
        Sampling frequency. Defaults to 1.0 (sample-domain).
    """
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 1 or len(x) == 0:
        raise ValueError(
            f"envelope_features expects non-empty 1-D input, got shape {x.shape}"
        )

    # Analytic signal and envelope
    analytic = hilbert(x)
    e = np.abs(analytic)

    e_mean = float(np.mean(e))
    e_std = float(np.std(e, ddof=0))  # population std
    e_max = float(np.max(e))
    e_min = float(np.min(e))

    # Envelope-band energy via squared-deviation spectrum
    s = (e - e_mean) ** 2
    S = np.fft.rfft(s)
    S_power = np.abs(S) ** 2

    freqs = np.fft.rfftfreq(len(s), d=1.0 / fs)  # actual frequencies

    # Target band: inclusive
    band_mask = (freqs >= _BAND_LO_FRAC * fs) & (freqs <= _BAND_HI_FRAC * fs)

    total_energy = float(np.sum(S_power))
    if total_energy < _ENERGY_ZERO_THRESHOLD:
        band_energy = 0.0  # deterministic safe value
    else:
        band_energy = float(np.sum(S_power[band_mask])) / total_energy

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
) -> list[dict[str, Any]]:
    """Compute rolling stride-1 features for a single channel.

    Only emits a row when a full window of length window_len exists.
    No padding; no downsampling.

    Parameters
    ----------
    signal:
        1-D float array, full episode length.
    window_len:
        Number of samples in the rolling window.
    scale_name:
        One of "short", "base", "long".
    channel_name:
        Machine/channel identifier.
    fs:
        Sampling frequency (defaults to 1.0 = 1 sample/step).

    Returns
    -------
    list of dicts, one per complete rolling window position. Each dict has:
        channel, scale, window_len, t_end (last sample index, 0-based),
        t_start (first sample index), mean, rms, min, max,
        envelope_max, envelope_min, envelope_mean, envelope_std, envelope_band_energy
    """
    sig = np.asarray(signal, dtype=np.float64)
    if sig.ndim != 1:
        raise ValueError(f"signal must be 1-D, got shape {sig.shape}")
    T = len(sig)
    rows: list[dict[str, Any]] = []

    for t_end in range(window_len - 1, T):
        t_start = t_end - window_len + 1
        window = sig[t_start : t_end + 1]  # inclusive, length == window_len

        agg = aggregate_window(window)
        env = envelope_features(window, fs=fs)

        row: dict[str, Any] = {
            "channel": channel_name,
            "scale": scale_name,
            "window_len": window_len,
            "t_start": t_start,
            "t_end": t_end,
        }
        row.update(agg)
        row.update(env)
        rows.append(row)

    return rows


def export_multiscale(
    episode_obs: np.ndarray,
    episode_id: int,
    channel_names: list[str],
    window_config: dict[str, Any],
    *,
    out_dir: str | pathlib.Path = "artifacts",
    fs: float = 1.0,
    compression: str = "snappy",
) -> dict[str, Any]:
    """Generate M0.2f multi-scale rolling features for one episode.

    Parameters
    ----------
    episode_obs:
        Float array of shape (n_channels, T).
    episode_id:
        Integer episode seed identifier (for row provenance only;
        stored as episode_id_ref, NOT as the M0.2e-owned episode_id key).
    channel_names:
        List of channel names aligned with axis-0 of episode_obs.
    window_config:
        Output of derive_base_window(...). Must contain "scale_lengths".
    out_dir:
        Output directory for artifacts. Created if absent.
    fs:
        Sampling frequency. Defaults to 1.0.
    compression:
        Parquet compression codec.

    Returns
    -------
    dict with: out, row_count, scale_lengths
    """
    obs = np.asarray(episode_obs, dtype=np.float64)
    if obs.ndim != 2:
        raise ValueError(
            f"episode_obs must be 2-D [n_channels, T], got shape {obs.shape}"
        )
    n_ch, _T = obs.shape
    if n_ch != len(channel_names):
        raise ValueError(
            f"channel_names length {len(channel_names)} != obs n_channels {n_ch}"
        )

    scale_lengths = window_config.get("scale_lengths", "UNRESOLVED")
    out_dir_p = pathlib.Path(out_dir)
    out_dir_p.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, Any]] = []

    # Both resolved and unresolved-fallback paths use the same pipeline.
    # scale_lengths is a dict of {scale_name: window_len} in both cases.
    if isinstance(scale_lengths, dict):
        for ch_idx, ch_name in enumerate(channel_names):
            signal = obs[ch_idx, :]
            for scale_name, win_len in scale_lengths.items():
                rows = rolling_features_for_channel(
                    signal, win_len, scale_name, ch_name, fs=fs
                )
                for r in rows:
                    # Provenance reference (NOT the M0.2e-owned "episode_id" key).
                    r["episode_id_ref"] = int(episode_id)
                all_rows.extend(rows)

    if not all_rows:
        df = pd.DataFrame(
            columns=[
                "episode_id_ref",
                "channel",
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
        # Determinism: sort columns.
        df = df[sorted(df.columns)]

    out_path = out_dir_p / "window_features.parquet"
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, str(out_path), compression=compression)

    # Absolute rule: never create scaler.pkl.
    scaler_path = out_dir_p / "scaler.pkl"
    assert not scaler_path.exists(), (
        "LEAKAGE VIOLATION: scaler.pkl must not exist in M0.2f output directory."
    )

    return {
        "out": str(out_path),
        "row_count": len(df),
        "scale_lengths": scale_lengths,
    }


def build_m0_2f_window_config_section(
    window_derivation: dict[str, Any],
    *,
    fs: float = 1.0,
) -> dict[str, Any]:
    """Build the M0.2f section to be added to window_config.json.

    This section is ADDITIVE -- it must not overwrite M0.2e-owned keys.
    Callers should merge this into the existing window_config dict under
    the key "m0_2f".

    Parameters
    ----------
    window_derivation:
        Output of derive_base_window(...).
    fs:
        Sampling frequency (1.0 = 1 sample/step, matching twin base tick).

    Returns
    -------
    dict -- M0.2f metadata section.
    """
    scale_lengths = window_derivation["scale_lengths"]
    base_window = window_derivation["base_window"]
    is_unresolved = base_window == "UNRESOLVED"

    if isinstance(scale_lengths, dict):
        if is_unresolved:
            # Fallback: record as fallback scales, NOT as resolved base
            sl_dict = {
                name: {
                    "fallback_q": window_derivation.get("fallback_q", _FALLBACK_Q),
                    "samples": scale_lengths[name],
                }
                for name in _SCALE_NAMES
            }
            sf_dict = "UNRESOLVED"
        else:
            sf_dict = {name: scale for name, scale in zip(_SCALE_NAMES, _SCALE_FACTORS)}
            sl_dict = {
                name: {
                    "scale_factor": scale,
                    "samples": scale_lengths[name],
                }
                for name, scale in zip(_SCALE_NAMES, _SCALE_FACTORS)
            }
    else:
        sl_dict = "UNRESOLVED"
        sf_dict = "UNRESOLVED"

    section: dict[str, Any] = {
        "export_version": M0_2F_EXPORT_VERSION,
        "code_version": M0_2F_CODE_VERSION,
        "base_window": base_window,
        "scale_factors": sf_dict,
        "scale_lengths": sl_dict,
        "base_window_method": window_derivation["method"],
        "base_window_dominant": window_derivation["dominant"],
        "base_window_candidate_pool": window_derivation["candidate_pool"],
        "base_window_candidate_votes": window_derivation["candidate_votes"],
        "fallback_note": window_derivation.get("fallback_note"),
        "cal_shape": window_derivation["cal_shape"],
        "envelope_method": "hilbert",
        "envelope_std_convention": "population (ddof=0)",
        "envelope_band_definition": {
            "formula": "sum(|S(f)|^2 for f in band) / sum(all |S(f)|^2)",
            "signal_s": "s(t) = (e(t) - mean(e))^2",
            "target_band_lo_frac_fs": _BAND_LO_FRAC,
            "target_band_hi_frac_fs": _BAND_HI_FRAC,
            "band_inclusive": True,
        },
        "source_sampling_convention": {
            "fs": fs,
            "stride": 1,
            "downsampling": False,
            "padding": False,
            "description": (
                "stride-1 rolling windows; no padding of incomplete windows; "
                "source time/sample identity preserved via t_start/t_end columns"
            ),
        },
        "ownership": "M0.2f (MINIPRO-29)",
        "m0_2e_fields_untouched": True,
    }

    # Add explicit fallback metadata when base is unresolved
    if is_unresolved:
        section["scale_status"] = window_derivation.get(
            "scale_status", "unresolved_fallback"
        )
        section["fallback_q"] = window_derivation.get("fallback_q", _FALLBACK_Q)
        section["fallback_policy"] = window_derivation.get("fallback_policy", "q_2q_4q")

    return section


def write_extended_window_config(
    existing_window_config: dict[str, Any],
    m0_2f_section: dict[str, Any],
    out_path: str | pathlib.Path,
) -> None:
    """Write window_config.json with M0.2f section added under key "m0_2f".

    Preserves all existing M0.2e-owned keys; adds "m0_2f" without overwriting.

    Parameters
    ----------
    existing_window_config:
        The existing window_config dict (from dataset_export.build_window_config()).
    m0_2f_section:
        Output of build_m0_2f_window_config_section(...).
    out_path:
        Destination path for window_config.json.
    """
    merged = dict(existing_window_config)
    merged["m0_2f"] = m0_2f_section

    out_p = pathlib.Path(out_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, indent=2, sort_keys=True)


def run_m0_2f_export(
    seed: int,
    *,
    out_dir: str | pathlib.Path = "artifacts",
    cal_seed: int | None = None,
    fs: float = 1.0,
) -> dict[str, Any]:
    """Top-level M0.2f export: calibrate, derive window, export features.

    This is the canonical M0.2f entry-point. It:
    1. Runs twin.run_calibration(cal_seed) to obtain clean calibration data.
    2. Derives the base window from calibration data.
    3. Runs twin.run_episode(seed) to get episode observations.
    4. Exports rolling multi-scale features.
    5. Extends window_config.json with M0.2f metadata.

    Parameters
    ----------
    seed:
        Episode seed.
    out_dir:
        Output artifacts directory.
    cal_seed:
        Seed for calibration run. Defaults to seed.
    fs:
        Sampling frequency (1.0 = 1 sample/step).

    Returns
    -------
    dict with keys:
        base_window, scale_lengths, window_derivation,
        features_path, row_count, window_config_path
    """
    # Lazy imports to avoid circular deps at module level.
    from src.config import MACHINE_INDEX
    from src.dataset_export import build_window_config
    from src.twin import run_calibration, run_episode

    _cal_seed = cal_seed if cal_seed is not None else seed

    # Step 1: obtain clean calibration data.
    calibration = run_calibration(_cal_seed)  # shape (T_cal, N_MACHINES)

    # Step 2: derive base window from calibration data.
    window_derivation = derive_base_window(calibration)

    # Step 3: run episode.
    rec = run_episode(seed, None)

    # Extract observation matrix: shape (N_MACHINES, T).
    obs = np.asarray(rec["obs"], dtype=np.float64)
    channel_names = sorted(MACHINE_INDEX, key=lambda m: MACHINE_INDEX[m])

    # Step 4: export multi-scale features.
    export_result = export_multiscale(
        obs,
        episode_id=seed,
        channel_names=channel_names,
        window_config=window_derivation,
        out_dir=out_dir,
        fs=fs,
    )

    # Step 5: extend window_config.json.
    out_dir_p = pathlib.Path(out_dir)
    win_cfg_path = out_dir_p / "window_config.json"

    existing_cfg: dict[str, Any] = {}
    if win_cfg_path.exists():
        with open(win_cfg_path, encoding="utf-8") as fh:
            existing_cfg = json.load(fh)
    else:
        existing_cfg = build_window_config()

    m0_2f_section = build_m0_2f_window_config_section(window_derivation, fs=fs)
    write_extended_window_config(existing_cfg, m0_2f_section, win_cfg_path)

    return {
        "base_window": window_derivation["base_window"],
        "scale_lengths": window_derivation["scale_lengths"],
        "window_derivation": window_derivation,
        "features_path": export_result["out"],
        "row_count": export_result["row_count"],
        "window_config_path": str(win_cfg_path),
    }
