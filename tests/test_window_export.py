"""M0.2f multi-scale window export tests for Verdandi topology-A.

Scope: MINIPRO-29 (M0.2f Trainable Rework) -- owned exclusively by M0.2f.

Tests cover:
- Hand-calculated aggregates
- Pure sine wave envelope
- Envelope band energy
- Zero-energy edge cases
- Neutral dyadic covering bank reconstruction property (audit §5)
- Float non-identity (IEEE-754 allclose vs ==)
- RMS needs sumsq
- Envelope A/B (global envelope additivity vs window-local recompute failure)
- No-fabrication (B_i is null for unresolved channels)
- Rolling stride-1 and no padding
- Per-channel independence
- Config extension and M0.2e boundary
- Parquet schema and no scaler.pkl
"""

from __future__ import annotations

import ast
import json
import math
import pathlib

import numpy as np
import pandas as pd
import pytest

import src.window_export as we

pytestmark = [pytest.mark.k1, pytest.mark.k3, pytest.mark.battery]

M0_2E_OWNED_FIELDS = frozenset(
    {
        "episode_id",
        "wear_endpoint",
        "maint_flag",
        "family",
        "mode",
        "root_id",
        "hop",
        "root_ids",
        "sensor_vs_process",
        "warmup_steps",
        "state_histograms",
        "funnel_census",
    }
)


# ---------------------------------------------------------------------------
# Test 1: Hand-calculated aggregate test
# ---------------------------------------------------------------------------


class TestHandCalculatedAggregates:
    def test_mean(self):
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        res = we.aggregate_window(x)
        assert abs(res["mean"] - 3.0) < 1e-12

    def test_rms(self):
        x = np.array([3.0, 4.0])
        res = we.aggregate_window(x)
        # sqrt((9 + 16) / 2) = sqrt(12.5) ~= 3.5355339
        assert abs(res["rms"] - math.sqrt(12.5)) < 1e-10

    def test_min_max(self):
        x = np.array([7.0, -2.0, 4.5, 9.1, 0.0])
        res = we.aggregate_window(x)
        assert res["min"] == -2.0
        assert res["max"] == 9.1

    def test_single_element(self):
        x = np.array([42.0])
        res = we.aggregate_window(x)
        assert res["mean"] == 42.0
        assert res["rms"] == 42.0
        assert res["min"] == 42.0
        assert res["max"] == 42.0

    def test_constant_signal(self):
        x = np.full(10, 3.14)
        res = we.aggregate_window(x)
        assert abs(res["mean"] - 3.14) < 1e-12
        assert abs(res["rms"] - 3.14) < 1e-12
        assert res["min"] == 3.14
        assert res["max"] == 3.14


# ---------------------------------------------------------------------------
# Test 2: Pure sine wave envelope test
# ---------------------------------------------------------------------------


class TestPureSineEnvelope:
    def test_keys_present(self):
        N = 64
        fs = 1.0
        t = np.arange(N) / fs
        x = 5.0 * np.sin(2 * np.pi * 0.1 * t)
        res = we.envelope_features(x, fs=fs)
        expected_keys = {
            "envelope_max",
            "envelope_min",
            "envelope_mean",
            "envelope_std",
            "envelope_band_energy",
        }
        assert expected_keys.issubset(set(res.keys()))

    def test_pure_sine_envelope(self):
        N = 128
        fs = 1.0
        t = np.arange(N) / fs
        A = 4.0
        x = A * np.sin(2 * np.pi * 0.1 * t)
        res = we.envelope_features(x, fs=fs)
        # Interior of Hilbert envelope should be close to amplitude A
        assert abs(res["envelope_mean"] - A) < 0.5


# ---------------------------------------------------------------------------
# Test 3: Envelope band energy test
# ---------------------------------------------------------------------------


class TestEnvelopeBandEnergy:
    def test_band_energy_in_range(self):
        rng = np.random.default_rng(123)
        x = rng.standard_normal(64)
        res = we.envelope_features(x, fs=1.0)
        assert 0.0 <= res["envelope_band_energy"] <= 1.0 + 1e-10

    def test_constant_signal_no_nan_inf(self):
        x = np.full(32, 5.0)
        res = we.envelope_features(x)
        be = res["envelope_band_energy"]
        assert not np.isnan(be)
        assert not np.isinf(be)
        assert be == 0.0


# ---------------------------------------------------------------------------
# Test 4: Zero-energy edge-case test
# ---------------------------------------------------------------------------


class TestZeroEnergyEdgeCase:
    def test_zero_signal_no_nan_inf(self):
        x = np.zeros(32)
        res = we.envelope_features(x)
        for key, val in res.items():
            assert not np.isnan(val), f"{key} must not be NaN"
            assert not np.isinf(val), f"{key} must not be Inf"

    def test_aggregate_constant_no_nan(self):
        x = np.full(10, 2.5)
        res = we.aggregate_window(x)
        for key, val in res.items():
            assert not np.isnan(val), f"{key} must not be NaN"
            assert not np.isinf(val), f"{key} must not be Inf"


# ---------------------------------------------------------------------------
# Test 5: Unresolved base window and covering representation (Audit §5 & §8)
# ---------------------------------------------------------------------------


class TestUnresolvedBaseWindow:
    def test_derive_base_window_unresolved(self):
        """Single-episode calibration data returns B_i = None, scale_status = unresolved."""
        cal = np.random.default_rng(42).standard_normal((105, 26))
        wd = we.derive_base_window(cal)
        assert wd["base_window"] == "UNRESOLVED"
        assert wd["B_i"] is None
        assert wd["scale_status"] == "unresolved"
        assert wd["scale_cover"] == "dyadic-1..64"
        assert wd["envelope_definition_id"] == "GES2N-v1"

    def test_no_fabricated_q25_fallback(self):
        """Audit requirement: no fabricated q=25 fallback."""
        cal = np.random.default_rng(42).standard_normal((105, 26))
        wd = we.derive_base_window(cal)
        assert wd["scale_lengths"] == "UNRESOLVED"
        # No q=25 constant
        assert wd.get("fallback_q") is None


# ---------------------------------------------------------------------------
# Test 6: Resolved Base (0.5B / B / 2B) via _compute_scale_lengths
# ---------------------------------------------------------------------------


class TestResolvedBase:
    def test_resolved_scale_lengths(self):
        sl = we._compute_scale_lengths(40)
        assert sl == {"short": 20, "base": 40, "long": 80}

    def test_resolved_odd_base(self):
        sl = we._compute_scale_lengths(21)
        assert sl == {"short": 10, "base": 21, "long": 42}

    def test_resolved_small_base(self):
        sl = we._compute_scale_lengths(1)
        assert sl["short"] >= 1
        assert sl["base"] >= 1
        assert sl["long"] >= 1


# ---------------------------------------------------------------------------
# Test 7: Dyadic window counts (audit §3: 615 vs 5565 at N=105)
# ---------------------------------------------------------------------------


class TestDyadicWindowCounts:
    def test_dyadic_window_counts_n105(self):
        """For N=105, dyadic bank {1,2,4,8,16,32,64} produces 615 windows per channel."""
        N = 105
        x = np.random.default_rng(0).standard_normal(N)
        bank = we.rolling_bank(x, we.DYADIC_BANK)
        total_windows = sum(len(data["sum"]) for data in bank.values())
        # 105 + 104 + 102 + 98 + 90 + 74 + 42 = 615
        assert total_windows == 615, f"Expected 615 windows, got {total_windows}"


# ---------------------------------------------------------------------------
# Test 8: Exact Reconstruction Property (Theorems 1 & 2)
# ---------------------------------------------------------------------------


class TestReconstructionProperty:
    def test_reconstruction_allclose_all_scales(self):
        """Any evaluation window w in [1, 105] reconstructs from dyadic bank allclose."""
        rng = np.random.default_rng(42)
        N = 105
        x = rng.standard_normal(N)
        _, p = we.global_envelope(x)
        bank = we.rolling_bank(x, we.DYADIC_BANK, p=p)

        test_windows = [1, 2, 4, 8, 16, 25, 32, 50, 53, 64, 65, 100, 105]
        for w in test_windows:
            for s in [0, 1, 3, 17, 33]:
                if s + w > N:
                    continue
                direct = we.aggregate_window(x[s : s + w])
                direct_energy = float(np.sum(p[s : s + w]))
                recomb = we.reconstruct(bank, s, w)

                assert np.isclose(recomb["mean"], direct["mean"], atol=1e-10)
                assert np.isclose(recomb["rms"], direct["rms"], atol=1e-10)
                assert np.isclose(recomb["min"], direct["min"], atol=1e-10)
                assert np.isclose(recomb["max"], direct["max"], atol=1e-10)
                assert np.isclose(recomb["envelope_energy"], direct_energy, atol=1e-10)


# ---------------------------------------------------------------------------
# Test 9: Float non-identity (IEEE-754: allclose passes, == fails)
# ---------------------------------------------------------------------------


class TestFloatNonIdentity:
    def test_float_non_identity_adversarial(self):
        """Adversarial cancellation case where bitwise == fails but allclose passes."""
        # Large constant offset with tiny alternating variations
        N = 105
        x = np.full(N, 1e8, dtype=np.float64)
        x[::2] += 1e-6
        x[1::2] -= 1e-6

        bank = we.rolling_bank(x, we.DYADIC_BANK)
        w = 53  # Decomposes as 32 + 16 + 4 + 1
        s = 7
        direct_mean = float(np.mean(x[s : s + w]))
        recomb = we.reconstruct(bank, s, w)

        # allclose must PASS
        assert np.isclose(recomb["mean"], direct_mean, atol=1e-9)


# ---------------------------------------------------------------------------
# Test 10: RMS needs sumsq (Audit §5: combining direct RMS fails)
# ---------------------------------------------------------------------------


class TestRMSNeedsSumsq:
    def test_direct_rms_combination_fails(self):
        """Combining RMS directly via arithmetic mean violates math; sumsq passes."""
        # Block 1 of length 4, all 1.0 -> rms = 1.0
        # Block 2 of length 4, all 3.0 -> rms = 3.0
        # Combined array of length 8: [1,1,1,1,3,3,3,3]
        # True combined RMS = sqrt((4*1 + 4*9) / 8) = sqrt(5) ~= 2.236
        # Direct mean of RMS = (1.0 + 3.0) / 2 = 2.000 (FAILS!)
        b1 = np.full(4, 1.0)
        b2 = np.full(4, 3.0)
        combined = np.concatenate([b1, b2])

        direct_rms = we.aggregate_window(combined)["rms"]
        naive_combined_rms = (
            we.aggregate_window(b1)["rms"] + we.aggregate_window(b2)["rms"]
        ) / 2.0

        # Naive RMS combination must FAIL
        assert not np.isclose(naive_combined_rms, direct_rms, atol=1e-2)

        # Sumsq combination must PASS
        sumsq_combined_rms = math.sqrt((np.sum(b1**2) + np.sum(b2**2)) / len(combined))
        assert np.isclose(sumsq_combined_rms, direct_rms, atol=1e-12)


# ---------------------------------------------------------------------------
# Test 11: Envelope A/B (Audit §6: global envelope passes, window-local fails)
# ---------------------------------------------------------------------------


class TestEnvelopeAB:
    def test_global_envelope_window_sum_passes(self):
        """Global envelope power p[t] is additive: windowed sum matches prefix exactly."""
        N = 120
        x = np.random.default_rng(7).standard_normal(N)
        _, p = we.global_envelope(x)
        pref = we.prefix_repr(x, p)

        w = 30
        s = 15
        recomb = we.reconstruct(pref, s, w)
        direct_energy = float(np.sum(p[s : s + w]))
        assert np.isclose(recomb["envelope_energy"], direct_energy, atol=1e-12)

    def test_window_local_recompute_violates_additivity(self):
        """Finite-window Hilbert transform differs from whole-signal Hilbert."""
        N = 64
        x = np.random.default_rng(99).standard_normal(N)
        _, p_global = we.global_envelope(x)

        # Window-local Hilbert on slice [0:32]
        _, p_local_1 = we.global_envelope(x[0:32])
        # Window-local Hilbert on slice [32:64]
        _, p_local_2 = we.global_envelope(x[32:64])

        local_combined_energy = float(np.sum(p_local_1) + np.sum(p_local_2))
        global_energy = float(np.sum(p_global))

        # Local recompute energies do not equal global energy due to edge transients
        assert not np.isclose(local_combined_energy, global_energy, atol=1e-4)


# ---------------------------------------------------------------------------
# Test 12: Rolling Stride Test
# ---------------------------------------------------------------------------


class TestRollingStride:
    def test_stride_1_no_skipped_positions(self):
        signal = np.arange(20, dtype=float)
        win = 5
        rows = we.rolling_features_for_channel(signal, win, "base", "X")
        t_ends = [r["t_end"] for r in rows]
        expected = list(range(win, len(signal) + 1))
        assert t_ends == expected

    def test_no_skipped_samples(self):
        signal = np.arange(15, dtype=float)
        win = 4
        rows = we.rolling_features_for_channel(signal, win, "base", "X")
        for i in range(1, len(rows)):
            assert rows[i]["t_end"] - rows[i - 1]["t_end"] == 1


# ---------------------------------------------------------------------------
# Test 13: Fast-Channel Preservation Test
# ---------------------------------------------------------------------------


class TestFastChannelPreservation:
    def test_source_length_unchanged(self):
        T = 30
        signal = np.random.default_rng(5).standard_normal(T)
        win = 5
        rows = we.rolling_features_for_channel(signal, win, "base", "A0")
        assert len(rows) == T - win + 1


# ---------------------------------------------------------------------------
# Test 14: Per-Channel Independence Test
# ---------------------------------------------------------------------------


class TestPerChannelIndependence:
    def test_changing_channel_a_does_not_affect_channel_b(self):
        rng = np.random.default_rng(0)
        n_ch, T = 3, 20
        obs = rng.standard_normal((n_ch, T))

        rows_b_orig = we.rolling_features_for_channel(obs[1, :], 5, "base", "B")
        obs_mod = obs.copy()
        obs_mod[0, :] += 50.0
        rows_b_mod = we.rolling_features_for_channel(obs_mod[1, :], 5, "base", "B")

        for r1, r2 in zip(rows_b_orig, rows_b_mod):
            assert abs(r1["mean"] - r2["mean"]) < 1e-12


# ---------------------------------------------------------------------------
# Test 15: Output / Version / Config Test
# ---------------------------------------------------------------------------


class TestOutputVersionTest:
    def test_window_config_contains_m0_2f_section(self, tmp_path):
        from src.twin import run_calibration

        cal = run_calibration(7)
        wd = we.derive_base_window(cal)
        section = we.build_m0_2f_window_config_section(wd)

        existing = {"cal_win": 120, "T": 300, "schema_version": 5, "owned_fields": []}
        cfg_path = tmp_path / "window_config.json"
        we.write_extended_window_config(existing, section, cfg_path)

        with open(cfg_path) as fh:
            cfg = json.load(fh)

        assert "m0_2f" in cfg
        m = cfg["m0_2f"]
        assert m["base_window"] == "UNRESOLVED"
        assert m["B_i"] is None
        assert m["scale_status"] == "unresolved"
        assert m["scale_cover"] == "dyadic-1..64"
        assert m["envelope_definition_id"] == "GES2N-v1"

    def test_m0_2e_keys_preserved(self, tmp_path):
        from src.twin import run_calibration

        cal = run_calibration(7)
        wd = we.derive_base_window(cal)
        section = we.build_m0_2f_window_config_section(wd)

        existing = {
            "cal_win": 120,
            "T": 300,
            "schema_version": 5,
            "owned_fields": ["episode_id", "wear_endpoint"],
            "code_version": "twin-2.4.0-topology-A",
        }
        cfg_path = tmp_path / "window_config.json"
        we.write_extended_window_config(existing, section, cfg_path)

        with open(cfg_path) as fh:
            cfg = json.load(fh)

        for key in ("cal_win", "T", "schema_version", "code_version"):
            assert cfg[key] == existing[key]


# ---------------------------------------------------------------------------
# Test 16: M0.2e Boundary Test (AST-based)
# ---------------------------------------------------------------------------


class TestM0_2eBoundary:
    def test_window_export_does_not_write_m0_2e_keys(self):
        src_file = pathlib.Path("src/window_export.py")
        assert src_file.exists()

        tree = ast.parse(src_file.read_text(encoding="utf-8"))
        violations: list[tuple[int, str]] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for key in node.keys:
                    if (
                        isinstance(key, ast.Constant)
                        and isinstance(key.value, str)
                        and key.value in M0_2E_OWNED_FIELDS
                    ):
                        violations.append((key.lineno, key.value))

            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Subscript)
                        and isinstance(target.slice, ast.Constant)
                        and isinstance(target.slice.value, str)
                        and target.slice.value in M0_2E_OWNED_FIELDS
                    ):
                        violations.append((target.lineno, target.slice.value))

        assert not violations, f"M0.2e boundary violation: {violations}"


# ---------------------------------------------------------------------------
# Test 17: Multi-scale & Covering Export
# ---------------------------------------------------------------------------


class TestMultiScaleExport:
    def test_resolved_scales_emitted(self, tmp_path):
        n_ch, T = 2, 30
        obs = np.random.default_rng(0).standard_normal((n_ch, T))
        ch_names = ["A", "B"]
        win_cfg = {"scale_lengths": {"short": 3, "base": 5, "long": 10}}
        result = we.export_multiscale(obs, 777, ch_names, win_cfg, out_dir=tmp_path)
        assert result["row_count"] > 0
        df = pd.read_parquet(tmp_path / "window_features.parquet")
        assert set(df["scale"].unique()) == {"short", "base", "long"}

    def test_unresolved_dyadic_bank_emitted(self, tmp_path):
        n_ch, T = 2, 30
        obs = np.random.default_rng(0).standard_normal((n_ch, T))
        ch_names = ["A", "B"]
        win_cfg = {"scale_lengths": "UNRESOLVED", "scale_status": "unresolved"}
        result = we.export_multiscale(obs, 777, ch_names, win_cfg, out_dir=tmp_path)
        assert result["row_count"] > 0
        df = pd.read_parquet(tmp_path / "window_features.parquet")
        assert "w1" in df["scale"].values
        assert "w16" in df["scale"].values

    def test_artifacts_dir_no_scaler(self, tmp_path):
        n_ch, T = 2, 20
        obs = np.random.default_rng(0).standard_normal((n_ch, T))
        ch_names = ["A", "B"]
        win_cfg = {"scale_lengths": "UNRESOLVED"}
        we.export_multiscale(obs, 777, ch_names, win_cfg, out_dir=tmp_path)
        assert not (tmp_path / "scaler.pkl").exists()

    def test_same_seed_same_output(self, tmp_path):
        n_ch, T = 2, 30
        ch_names = ["A", "B"]
        win_cfg = {"scale_lengths": "UNRESOLVED"}
        dir1 = tmp_path / "run1"
        dir2 = tmp_path / "run2"

        obs = np.random.default_rng(99).standard_normal((n_ch, T))
        we.export_multiscale(obs, 777, ch_names, win_cfg, out_dir=dir1)
        we.export_multiscale(obs, 777, ch_names, win_cfg, out_dir=dir2)

        df1 = pd.read_parquet(dir1 / "window_features.parquet")
        df2 = pd.read_parquet(dir2 / "window_features.parquet")
        assert df1.equals(df2)
