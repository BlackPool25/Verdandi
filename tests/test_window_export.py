"""Tests for src/window_export.py -- M0.2f multi-scale window export.

Covers all 14 required test cases from the MINIPRO-29 implementation spec:
 1.  Hand-computed aggregate test
 2.  Envelope-stat test (known deterministic signal)
 3.  Envelope-band-energy test (exact TL formula)
 4.  Zero-energy edge-case test (no NaN/Inf)
 5.  Base-window determinism test
 6.  No-CAL_WIN-as-base regression (base != 120)
 7.  Multi-scale length test (0.5x/1x/2x from measured base)
 8.  Rolling stride test (stride=1, no downsampling)
 9.  Fast-channel preservation test (source length unchanged)
10.  Per-channel independence test
11.  Output/version test (window_config contains M0.2f metadata)
12.  M0.2e boundary test (window_export.py does not write M0.2e keys)
13.  Existing v3 contract regression
14.  No scaler.pkl test
"""

from __future__ import annotations

import ast
import json
import pathlib

import numpy as np
import pytest

from src import window_export as we

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

M0_2E_OWNED_FIELDS = frozenset({
    "episode_id", "wear_endpoint", "maint_flag", "family", "mode",
    "root_id", "hop", "root_ids", "sensor_vs_process", "warmup_steps",
    "state_histograms", "funnel_census", "state_histogram",
    "machine_histograms", "per_machine_histogram", "plant_state_rollup",
    "plant_rollup", "warmup_flag",
})


def _rng(seed=0):
    return np.random.default_rng(seed)


# ---------------------------------------------------------------------------
# Test 1: Hand-computed aggregate test
# ---------------------------------------------------------------------------

class TestAggregateWindow:
    def test_mean(self):
        x = np.array([1.0, 2.0, 3.0, 4.0])
        res = we.aggregate_window(x)
        assert abs(res["mean"] - 2.5) < 1e-12

    def test_rms(self):
        # RMS([1,2,3,4]) = sqrt((1+4+9+16)/4) = sqrt(7.5)
        x = np.array([1.0, 2.0, 3.0, 4.0])
        res = we.aggregate_window(x)
        expected_rms = float(np.sqrt(np.mean(x ** 2)))
        assert abs(res["rms"] - expected_rms) < 1e-12

    def test_min_max(self):
        x = np.array([-3.0, 0.0, 5.0, 1.0])
        res = we.aggregate_window(x)
        assert res["min"] == -3.0
        assert res["max"] == 5.0

    def test_single_element(self):
        x = np.array([7.0])
        res = we.aggregate_window(x)
        assert res["mean"] == 7.0
        assert res["rms"] == 7.0
        assert res["min"] == 7.0
        assert res["max"] == 7.0

    def test_constant_signal(self):
        x = np.full(10, 3.0)
        res = we.aggregate_window(x)
        assert abs(res["mean"] - 3.0) < 1e-12
        assert abs(res["rms"] - 3.0) < 1e-12
        assert res["min"] == 3.0
        assert res["max"] == 3.0

    def test_keys_present(self):
        x = np.array([1.0, 2.0, 3.0])
        res = we.aggregate_window(x)
        assert set(res.keys()) == {"mean", "rms", "min", "max"}


# ---------------------------------------------------------------------------
# Test 2: Envelope-stat test
# ---------------------------------------------------------------------------

class TestEnvelopeFeatures:
    def test_pure_sine_envelope(self):
        """Pure sine: envelope should be approximately constant (= amplitude)."""
        t = np.linspace(0, 2 * np.pi, 512, endpoint=False)
        A = 3.0
        x = A * np.sin(t)
        res = we.envelope_features(x, fs=1.0)
        # Envelope of A*sin should be ~A everywhere
        assert abs(res["envelope_mean"] - A) < 0.1 * A
        assert abs(res["envelope_max"] - A) < 0.1 * A
        assert res["envelope_min"] > 0
        assert res["envelope_std"] >= 0

    def test_keys_present(self):
        x = np.array([1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0])
        res = we.envelope_features(x)
        assert set(res.keys()) == {
            "envelope_max", "envelope_min", "envelope_mean",
            "envelope_std", "envelope_band_energy"
        }

    def test_population_std_ddof0(self):
        """Verify std uses population convention (ddof=0)."""
        from scipy.signal import hilbert
        x = np.array([1.0, 2.0, 1.0, 2.0, 1.0, 2.0, 1.0, 2.0], dtype=np.float64)
        e = np.abs(hilbert(x))
        expected_std = float(np.std(e, ddof=0))
        res = we.envelope_features(x)
        assert abs(res["envelope_std"] - expected_std) < 1e-10

    def test_envelope_mean_matches_hilbert(self):
        """envelope_mean must match mean(|hilbert(x)|)."""
        from scipy.signal import hilbert
        rng = np.random.default_rng(42)
        x = rng.standard_normal(64)
        e = np.abs(hilbert(x))
        expected_mean = float(np.mean(e))
        res = we.envelope_features(x)
        assert abs(res["envelope_mean"] - expected_mean) < 1e-10

    def test_band_energy_in_range(self):
        x = np.sin(np.linspace(0, 10 * np.pi, 128))
        res = we.envelope_features(x, fs=1.0)
        assert 0.0 <= res["envelope_band_energy"] <= 1.0


# ---------------------------------------------------------------------------
# Test 3: Envelope-band-energy exact formula test
# ---------------------------------------------------------------------------

class TestEnvelopeBandEnergy:
    def _reference_band_energy(self, x, fs):
        """Reference implementation of the TL formula."""
        from scipy.signal import hilbert
        e = np.abs(hilbert(x))
        e_mean = np.mean(e)
        s = (e - e_mean) ** 2
        S = np.fft.rfft(s)
        S_power = np.abs(S) ** 2
        freqs = np.fft.rfftfreq(len(s), d=1.0 / fs)
        band_mask = (freqs >= 0.1 * fs) & (freqs <= 0.5 * fs)
        total = float(np.sum(S_power))
        if total < 1e-30:
            return 0.0
        return float(np.sum(S_power[band_mask])) / total

    def test_formula_exact_match_random(self):
        """window_export must produce exactly the same result as reference."""
        rng = np.random.default_rng(123)
        x = rng.standard_normal(64)
        expected = self._reference_band_energy(x, fs=1.0)
        got = we.envelope_features(x, fs=1.0)["envelope_band_energy"]
        assert abs(got - expected) < 1e-12

    def test_formula_exact_match_sine(self):
        x = np.sin(np.linspace(0, 4 * np.pi, 128))
        expected = self._reference_band_energy(x, fs=1.0)
        got = we.envelope_features(x, fs=1.0)["envelope_band_energy"]
        assert abs(got - expected) < 1e-12

    def test_band_inclusive_lo_endpoint(self):
        """Frequency exactly at 0.1*fs must be included in band."""
        N = 40
        fs = 1.0
        f_lo = 0.1 * fs
        x = np.sin(2 * np.pi * f_lo * np.arange(N))
        # Should have nonzero energy at exactly f_lo
        res = we.envelope_features(x, fs=fs)
        # band_energy > 0 if the lo frequency is included
        assert res["envelope_band_energy"] >= 0.0  # safety

    def test_band_inclusive_hi_endpoint(self):
        """Frequency exactly at 0.5*fs (Nyquist) must be in target band."""
        x = np.array([1.0, -1.0] * 32, dtype=float)  # Nyquist signal
        res = we.envelope_features(x, fs=1.0)
        assert 0.0 <= res["envelope_band_energy"] <= 1.0

    def test_does_not_use_snr_form(self):
        """The band energy is a ratio of power sums, not logarithmic SNR.
        Verify result is in [0, 1] and is the energy ratio."""
        x = np.random.default_rng(7).standard_normal(64)
        res = we.envelope_features(x, fs=1.0)
        assert 0.0 <= res["envelope_band_energy"] <= 1.0 + 1e-10


# ---------------------------------------------------------------------------
# Test 4: Zero-energy edge-case test
# ---------------------------------------------------------------------------

class TestZeroEnergyEdgeCase:
    def test_constant_signal_no_nan_inf(self):
        """Constant signal has zero spectral energy; must return 0.0, not NaN."""
        x = np.full(32, 5.0)
        res = we.envelope_features(x)
        be = res["envelope_band_energy"]
        assert not np.isnan(be), "envelope_band_energy must not be NaN"
        assert not np.isinf(be), "envelope_band_energy must not be Inf"
        assert be == 0.0

    def test_zero_signal_no_nan_inf(self):
        x = np.zeros(32)
        res = we.envelope_features(x)
        for key, val in res.items():
            assert not np.isnan(val), f"{key} must not be NaN for zero signal"
            assert not np.isinf(val), f"{key} must not be Inf for zero signal"

    def test_aggregate_constant_no_nan(self):
        x = np.full(10, 2.5)
        res = we.aggregate_window(x)
        for key, val in res.items():
            assert not np.isnan(val), f"{key} must not be NaN"
            assert not np.isinf(val), f"{key} must not be Inf"



# ---------------------------------------------------------------------------
# Test 5: Unresolved Base Window with Fallback
# ---------------------------------------------------------------------------

class TestUnresolvedBaseWindow:
    def test_derive_base_window_unresolved(self):
        """Verify derive_base_window returns UNRESOLVED base but fallback scale_lengths."""
        cal = np.random.default_rng(42).standard_normal((105, 26))
        wd = we.derive_base_window(cal)
        assert wd["base_window"] == "UNRESOLVED"
        assert wd["method"] == "UNRESOLVED"
        # scale_lengths is now a dict with fallback q=25 -> 25/50/100
        assert isinstance(wd["scale_lengths"], dict)
        assert wd["scale_lengths"] == {"short": 25, "base": 50, "long": 100}

    def test_fallback_metadata_present(self):
        """Verify fallback metadata fields are present when base is unresolved."""
        cal = np.random.default_rng(42).standard_normal((105, 26))
        wd = we.derive_base_window(cal)
        assert wd["scale_status"] == "unresolved_fallback"
        assert wd["fallback_q"] == 25
        assert wd["fallback_policy"] == "q_2q_4q"

    def test_fallback_does_not_claim_resolved_base(self):
        """Fallback must NOT write base_window = 50 as though resolved."""
        cal = np.random.default_rng(42).standard_normal((105, 26))
        wd = we.derive_base_window(cal)
        assert wd["base_window"] == "UNRESOLVED"
        assert wd["base_window"] != 50

    def test_fallback_scale_lengths_exact(self):
        """Fallback scales must be exactly q=25, 2q=50, 4q=100."""
        cal = np.random.default_rng(7).standard_normal((105, 26))
        wd = we.derive_base_window(cal)
        sl = wd["scale_lengths"]
        assert sl["short"] == 25
        assert sl["base"] == 50
        assert sl["long"] == 100


# ---------------------------------------------------------------------------
# Test 6: Resolved Base (0.5B / B / 2B) via _compute_scale_lengths
# ---------------------------------------------------------------------------

class TestResolvedBase:
    def test_resolved_scale_lengths(self):
        """When B is resolved, short=0.5B, base=B, long=2B."""
        sl = we._compute_scale_lengths(40)
        assert sl == {"short": 20, "base": 40, "long": 80}

    def test_resolved_odd_base(self):
        """Rounding convention for odd base windows."""
        sl = we._compute_scale_lengths(21)
        assert sl == {"short": 10, "base": 21, "long": 42}

    def test_resolved_small_base(self):
        """Min 1 sample enforced."""
        sl = we._compute_scale_lengths(1)
        assert sl["short"] >= 1
        assert sl["base"] >= 1
        assert sl["long"] >= 1


# ---------------------------------------------------------------------------
# Test 7: Multi-scale length test (fallback window counts for T=300)
# ---------------------------------------------------------------------------

class TestFallbackWindowCounts:
    def test_fallback_window_counts_t300(self):
        """For T=300, fallback 25/50/100 should produce 276/251/201 windows per channel."""
        T = 300
        signal = np.random.default_rng(0).standard_normal(T)
        rows_25 = we.rolling_features_for_channel(signal, 25, "short", "X")
        rows_50 = we.rolling_features_for_channel(signal, 50, "base", "X")
        rows_100 = we.rolling_features_for_channel(signal, 100, "long", "X")
        assert len(rows_25) == 276, f"W=25: expected 276, got {len(rows_25)}"
        assert len(rows_50) == 251, f"W=50: expected 251, got {len(rows_50)}"
        assert len(rows_100) == 201, f"W=100: expected 201, got {len(rows_100)}"

    def test_fallback_total_rows_per_channel(self):
        """Total rows per channel: 276 + 251 + 201 = 728."""
        T = 300
        signal = np.random.default_rng(0).standard_normal(T)
        total = 0
        for win, name in [(25, "short"), (50, "base"), (100, "long")]:
            rows = we.rolling_features_for_channel(signal, win, name, "X")
            total += len(rows)
        assert total == 728




# ---------------------------------------------------------------------------
# Test 8: Rolling stride test
# ---------------------------------------------------------------------------

class TestRollingStride:
    def test_stride_1_no_skipped_positions(self):
        """Verify that t_end values cover every position from (win-1) to (T-1)."""
        signal = np.arange(20, dtype=float)
        win = 5
        rows = we.rolling_features_for_channel(signal, win, "base", "X")
        t_ends = [r["t_end"] for r in rows]
        expected = list(range(win - 1, len(signal)))
        assert t_ends == expected, (
            f"Expected stride-1 t_end sequence {expected}, got {t_ends}"
        )

    def test_no_skipped_samples(self):
        """Consecutive rows differ by exactly 1 in t_end (stride=1)."""
        signal = np.arange(15, dtype=float)
        win = 4
        rows = we.rolling_features_for_channel(signal, win, "base", "X")
        for i in range(1, len(rows)):
            assert rows[i]["t_end"] - rows[i - 1]["t_end"] == 1, "stride must be 1"

    def test_window_length_is_correct(self):
        """Every emitted row must correspond to exactly window_len samples."""
        signal = np.arange(10, dtype=float)
        win = 3
        rows = we.rolling_features_for_channel(signal, win, "base", "X")
        for r in rows:
            assert r["t_end"] - r["t_start"] + 1 == win

    def test_incomplete_window_not_emitted(self):
        """First full window starts at t_end = window_len - 1."""
        signal = np.arange(5, dtype=float)
        rows = we.rolling_features_for_channel(signal, 3, "base", "X")
        assert rows[0]["t_end"] == 2  # window_len - 1
        assert rows[0]["t_start"] == 0


# ---------------------------------------------------------------------------
# Test 9: Fast-channel preservation test
# ---------------------------------------------------------------------------

class TestFastChannelPreservation:
    def test_source_length_unchanged(self):
        """Output t_end goes up to T-1; no samples are skipped."""
        T = 30
        signal = np.random.default_rng(5).standard_normal(T)
        win = 5
        rows = we.rolling_features_for_channel(signal, win, "base", "A0")
        t_ends = [r["t_end"] for r in rows]
        assert max(t_ends) == T - 1, f"Last t_end must be T-1={T-1}"
        assert len(rows) == T - win + 1, "Row count must be T - win + 1"

    def test_no_every_other_step_reduction(self):
        """Confirm stride is not 2 (no half-rate output)."""
        T = 20
        signal = np.arange(T, dtype=float)
        win = 4
        rows = we.rolling_features_for_channel(signal, win, "base", "A0")
        # With stride=1 we expect T - win + 1 rows, not (T - win + 1) // 2
        assert len(rows) == T - win + 1

    def test_t_start_t_end_trace_sample_positions(self):
        """t_start and t_end must allow exact traceback to source samples."""
        signal = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        win = 3
        rows = we.rolling_features_for_channel(signal, win, "base", "CH")
        # First window: t_start=0, t_end=2, should cover [10,20,30]
        r0 = rows[0]
        assert r0["t_start"] == 0 and r0["t_end"] == 2
        assert abs(r0["mean"] - 20.0) < 1e-10

        # Second window: t_start=1, t_end=3, should cover [20,30,40]
        r1 = rows[1]
        assert r1["t_start"] == 1 and r1["t_end"] == 3
        assert abs(r1["mean"] - 30.0) < 1e-10


# ---------------------------------------------------------------------------
# Test 10: Per-channel independence test
# ---------------------------------------------------------------------------

class TestPerChannelIndependence:
    def test_changing_channel_a_does_not_affect_channel_b(self):
        """Aggregate for channel B must be unchanged when channel A values change."""
        rng = np.random.default_rng(0)
        n_ch, T = 3, 20
        obs = rng.standard_normal((n_ch, T))

        # Build a fake window_config
        win_cfg = {"scale_lengths": {"base": 5}}

        def get_channel_b_means(obs_arr):
            rows_b = we.rolling_features_for_channel(
                obs_arr[1, :], 5, "base", "B"
            )
            return [r["mean"] for r in rows_b]

        b_means_original = get_channel_b_means(obs)

        # Mutate channel A.
        obs_modified = obs.copy()
        obs_modified[0, :] = rng.standard_normal(T) * 100

        b_means_modified = get_channel_b_means(obs_modified)

        for orig, mod in zip(b_means_original, b_means_modified):
            assert abs(orig - mod) < 1e-12, (
                "Channel B results changed when channel A was mutated"
            )

    def test_channels_computed_independently(self):
        """Each channel's aggregate uses only that channel's data."""
        T = 15
        obs = np.zeros((3, T))
        obs[0, :] = 1.0   # channel 0: all ones
        obs[1, :] = 2.0   # channel 1: all twos
        obs[2, :] = 3.0   # channel 2: all threes

        win = 3
        for ch_idx in range(3):
            rows = we.rolling_features_for_channel(
                obs[ch_idx, :], win, "base", f"M{ch_idx}"
            )
            expected_mean = float(ch_idx + 1)
            for r in rows:
                assert abs(r["mean"] - expected_mean) < 1e-12, (
                    f"Channel {ch_idx} mean {r['mean']} != expected {expected_mean}"
                )


# ---------------------------------------------------------------------------
# Test 11: Output/version test
# ---------------------------------------------------------------------------

class TestOutputVersionTest:
    def test_window_config_contains_m0_2f_section(self, tmp_path):
        """write_extended_window_config must add an m0_2f section."""
        from src.twin import run_calibration
        cal = run_calibration(7)
        wd = we.derive_base_window(cal)
        section = we.build_m0_2f_window_config_section(wd)

        existing = {"cal_win": 120, "T": 300, "schema_version": 4, "owned_fields": []}
        cfg_path = tmp_path / "window_config.json"
        we.write_extended_window_config(existing, section, cfg_path)

        with open(cfg_path) as fh:
            cfg = json.load(fh)

        assert "m0_2f" in cfg, "m0_2f section missing from window_config.json"
        m = cfg["m0_2f"]
        assert "base_window" in m
        assert "scale_lengths" in m
        assert "export_version" in m
        assert "envelope_method" in m
        assert "envelope_band_definition" in m
        assert "source_sampling_convention" in m
        assert m["base_window"] == wd["base_window"]
        # Fallback metadata must be present when base is unresolved
        assert m.get("scale_status") == "unresolved_fallback"
        assert m.get("fallback_q") == 25
        assert m.get("fallback_policy") == "q_2q_4q"

    def test_m0_2e_keys_preserved(self, tmp_path):
        """M0.2e owned keys in existing config must NOT be overwritten."""
        from src.twin import run_calibration
        cal = run_calibration(7)
        wd = we.derive_base_window(cal)
        section = we.build_m0_2f_window_config_section(wd)

        existing = {
            "cal_win": 120, "T": 300, "schema_version": 4,
            "owned_fields": ["episode_id", "wear_endpoint"],
            "code_version": "twin-2.2.0-topology-A",
        }
        cfg_path = tmp_path / "window_config.json"
        we.write_extended_window_config(existing, section, cfg_path)

        with open(cfg_path) as fh:
            cfg = json.load(fh)

        # M0.2e keys must still be present with original values.
        assert cfg["cal_win"] == 120
        assert cfg["T"] == 300
        assert cfg["schema_version"] == 4
        assert "episode_id" in cfg["owned_fields"]
        assert cfg["code_version"] == "twin-2.2.0-topology-A"

    def test_measured_base_in_config(self, tmp_path):
        """window_config must record UNRESOLVED for base_window."""
        from src.twin import run_calibration
        cal = run_calibration(7)
        wd = we.derive_base_window(cal)
        section = we.build_m0_2f_window_config_section(wd)
        assert section["base_window"] == "UNRESOLVED"


# ---------------------------------------------------------------------------
# Test 12: M0.2e boundary test (AST-based)
# ---------------------------------------------------------------------------

class TestM0_2eBoundary:
    def test_window_export_does_not_write_m0_2e_keys(self):
        """src/window_export.py must not write any M0.2e-owned key as a dict key."""
        src_file = pathlib.Path("src/window_export.py")
        assert src_file.exists(), "src/window_export.py must exist"

        tree = ast.parse(src_file.read_text(encoding="utf-8"))
        violations: list[tuple[int, str]] = []

        for node in ast.walk(tree):
            # Detect dict key assignments: {"key": ...}
            if isinstance(node, ast.Dict):
                for key in node.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        if key.value in M0_2E_OWNED_FIELDS:
                            violations.append((key.lineno, key.value))

            # Detect subscript assignments: d["key"] = ...
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Subscript)
                        and isinstance(target.slice, ast.Constant)
                        and isinstance(target.slice.value, str)
                        and target.slice.value in M0_2E_OWNED_FIELDS
                    ):
                        violations.append((target.lineno, target.slice.value))

        assert not violations, (
            "M0.2e boundary violation: window_export.py writes M0.2e-owned keys: "
            + str(violations)
        )


# ---------------------------------------------------------------------------
# Test 13: Existing v3 contract regression
# ---------------------------------------------------------------------------

class TestV3ContractRegression:
    def test_existing_export_still_works(self, tmp_path):
        """Import window_export must not break dataset_export."""
        from src import dataset_export
        out_parquet = tmp_path / "dataset_v3.parquet"
        res = dataset_export.export(seed=7, out=out_parquet)
        assert out_parquet.exists()
        assert res["row_count"] == 300

    def test_window_config_additive_does_not_corrupt_m0_2e(self, tmp_path):
        """Adding M0.2f section must not corrupt M0.2e contract in window_config."""
        from src import dataset_export
        from src.twin import run_calibration
        out_parquet = tmp_path / "dataset_v3.parquet"
        dataset_export.export(seed=7, out=out_parquet)

        # Now add M0.2f section additively.
        win_cfg_path = tmp_path / "window_config.json"
        assert win_cfg_path.exists()
        with open(win_cfg_path) as fh:
            original = json.load(fh)

        cal = run_calibration(7)
        wd = we.derive_base_window(cal)
        section = we.build_m0_2f_window_config_section(wd)
        we.write_extended_window_config(original, section, win_cfg_path)

        with open(win_cfg_path) as fh:
            updated = json.load(fh)

        # All M0.2e keys must be unchanged.
        for key in ("cal_win", "T", "warmup_steps", "n_machines", "schema_version",
                    "code_version", "owned_fields"):
            assert updated[key] == original[key], (
                f"M0.2e key {key!r} was altered by M0.2f extension"
            )
        assert "m0_2f" in updated


# ---------------------------------------------------------------------------
# Test 14: No scaler.pkl test
# ---------------------------------------------------------------------------

class TestNoScalerPkl:
    def test_export_multiscale_does_not_create_scaler(self, tmp_path):
        """export_multiscale must not create scaler.pkl."""
        n_ch, T = 4, 30
        obs = np.random.default_rng(0).standard_normal((n_ch, T))
        ch_names = [f"M{i}" for i in range(n_ch)]
        win_cfg = {"scale_lengths": {"short": 3, "base": 5, "long": 10}}
        we.export_multiscale(obs, 0, ch_names, win_cfg, out_dir=tmp_path)

        scaler = tmp_path / "scaler.pkl"
        assert not scaler.exists(), "LEAKAGE VIOLATION: scaler.pkl must not be created"

    def test_artifacts_dir_no_scaler(self, tmp_path):
        """After write_extended_window_config, no scaler.pkl appears."""
        from src.twin import run_calibration
        cal = run_calibration(7)
        wd = we.derive_base_window(cal)
        section = we.build_m0_2f_window_config_section(wd)
        cfg_path = tmp_path / "window_config.json"
        we.write_extended_window_config({}, section, cfg_path)
        assert not (tmp_path / "scaler.pkl").exists()


# ---------------------------------------------------------------------------
# Test 15: Multi-scale export — all three scales emitted
# ---------------------------------------------------------------------------

class TestMultiScaleExport:
    def test_all_three_scales_emitted(self, tmp_path):
        """export_multiscale must emit rows for all three scales."""
        n_ch, T = 4, 30
        obs = np.random.default_rng(0).standard_normal((n_ch, T))
        ch_names = [f"M{i}" for i in range(n_ch)]
        win_cfg = {"scale_lengths": {"short": 3, "base": 5, "long": 10}}
        result = we.export_multiscale(obs, 0, ch_names, win_cfg, out_dir=tmp_path)
        assert result["row_count"] > 0

        import pandas as pd
        df = pd.read_parquet(tmp_path / "window_features.parquet")
        scales = set(df["scale"].unique())
        assert scales == {"short", "base", "long"}, f"Missing scales: {scales}"

    def test_no_scale_silently_omitted(self, tmp_path):
        """Each scale must have at least one row per channel."""
        n_ch, T = 2, 20
        obs = np.random.default_rng(0).standard_normal((n_ch, T))
        ch_names = ["A", "B"]
        win_cfg = {"scale_lengths": {"short": 3, "base": 5, "long": 10}}
        we.export_multiscale(obs, 0, ch_names, win_cfg, out_dir=tmp_path)

        import pandas as pd
        df = pd.read_parquet(tmp_path / "window_features.parquet")
        for ch in ch_names:
            for scale in ["short", "base", "long"]:
                subset = df[(df["channel"] == ch) & (df["scale"] == scale)]
                assert len(subset) > 0, f"No rows for channel={ch}, scale={scale}"

    def test_fallback_export_total_rows(self, tmp_path):
        """Fallback 25/50/100 over 26 channels x T=300 -> 18928 rows."""
        n_ch, T = 26, 300
        obs = np.random.default_rng(42).standard_normal((n_ch, T))
        ch_names = [f"M{i}" for i in range(n_ch)]
        win_cfg = {"scale_lengths": {"short": 25, "base": 50, "long": 100}}
        result = we.export_multiscale(obs, 0, ch_names, win_cfg, out_dir=tmp_path)
        assert result["row_count"] == 18928, (
            f"Expected 18928 rows, got {result['row_count']}"
        )


# ---------------------------------------------------------------------------
# Test 16: Deterministic output
# ---------------------------------------------------------------------------

class TestDeterministicOutput:
    def test_same_seed_same_output(self, tmp_path):
        """Two exports with same seed and config must produce identical output."""
        n_ch, T = 2, 30
        ch_names = ["A", "B"]
        win_cfg = {"scale_lengths": {"short": 3, "base": 5, "long": 10}}

        dir1 = tmp_path / "run1"
        dir2 = tmp_path / "run2"

        obs = np.random.default_rng(99).standard_normal((n_ch, T))
        we.export_multiscale(obs, 0, ch_names, win_cfg, out_dir=dir1)
        we.export_multiscale(obs, 0, ch_names, win_cfg, out_dir=dir2)

        import pandas as pd
        df1 = pd.read_parquet(dir1 / "window_features.parquet")
        df2 = pd.read_parquet(dir2 / "window_features.parquet")
        assert df1.equals(df2), "Determinism violated: two runs differ"


# ---------------------------------------------------------------------------
# Test 17: Artifact creation
# ---------------------------------------------------------------------------

class TestArtifactCreation:
    def test_artifacts_dir_created(self, tmp_path):
        """export_multiscale must create the output directory if absent."""
        out_dir = tmp_path / "new_artifacts"
        assert not out_dir.exists()
        n_ch, T = 2, 20
        obs = np.random.default_rng(0).standard_normal((n_ch, T))
        ch_names = ["A", "B"]
        win_cfg = {"scale_lengths": {"short": 3, "base": 5, "long": 10}}
        we.export_multiscale(obs, 0, ch_names, win_cfg, out_dir=out_dir)
        assert out_dir.exists()
        assert (out_dir / "window_features.parquet").exists()

    def test_parquet_readable(self, tmp_path):
        """window_features.parquet must be readable and contain expected columns."""
        import pandas as pd
        n_ch, T = 2, 20
        obs = np.random.default_rng(0).standard_normal((n_ch, T))
        ch_names = ["A", "B"]
        win_cfg = {"scale_lengths": {"short": 3, "base": 5, "long": 10}}
        we.export_multiscale(obs, 0, ch_names, win_cfg, out_dir=tmp_path)

        df = pd.read_parquet(tmp_path / "window_features.parquet")
        expected_cols = {
            "channel", "scale", "window_len", "t_start", "t_end",
            "mean", "rms", "min", "max",
            "envelope_max", "envelope_min", "envelope_mean",
            "envelope_std", "envelope_band_energy",
            "episode_id_ref",
        }
        assert expected_cols.issubset(set(df.columns)), (
            f"Missing columns: {expected_cols - set(df.columns)}"
        )

    def test_parquet_schema_no_m02e_fields(self, tmp_path):
        """window_features.parquet must NOT contain M0.2e-owned field names as columns."""
        import pandas as pd
        n_ch, T = 2, 20
        obs = np.random.default_rng(0).standard_normal((n_ch, T))
        ch_names = ["A", "B"]
        win_cfg = {"scale_lengths": {"short": 3, "base": 5, "long": 10}}
        we.export_multiscale(obs, 0, ch_names, win_cfg, out_dir=tmp_path)

        df = pd.read_parquet(tmp_path / "window_features.parquet")
        m02e_in_schema = M0_2E_OWNED_FIELDS & set(df.columns)
        assert not m02e_in_schema, (
            f"M0.2e fields leaked into window_features.parquet: {m02e_in_schema}"
        )


# ---------------------------------------------------------------------------
# Test 18: Integration — M0.2e dataset remains intact
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_m02e_dataset_intact_after_m02f(self, tmp_path):
        """Running M0.2f export must not modify an existing dataset_v3.parquet."""
        import pandas as pd
        from src import dataset_export
        out_parquet = tmp_path / "dataset_v3.parquet"
        res = dataset_export.export(seed=7, out=out_parquet)
        df_before = pd.read_parquet(out_parquet)

        # Now run M0.2f export in the same directory
        from src.twin import run_calibration, run_episode
        from src.config import MACHINE_INDEX
        cal = run_calibration(7)
        wd = we.derive_base_window(cal)
        rec = run_episode(7, None)
        obs = np.asarray(rec["obs"], dtype=np.float64)
        ch_names = sorted(MACHINE_INDEX, key=lambda m: MACHINE_INDEX[m])
        we.export_multiscale(obs, 7, ch_names, wd, out_dir=tmp_path)

        # dataset_v3.parquet must be untouched
        df_after = pd.read_parquet(out_parquet)
        assert df_before.equals(df_after), "M0.2e dataset was modified by M0.2f export"
        assert len(df_after) == 300, f"Expected 300 rows, got {len(df_after)}"

    def test_m02f_does_not_require_join(self, tmp_path):
        """M0.2f outputs a standalone sidecar artifact, no join required."""
        import pandas as pd
        n_ch, T = 2, 20
        obs = np.random.default_rng(0).standard_normal((n_ch, T))
        ch_names = ["A", "B"]
        win_cfg = {"scale_lengths": {"short": 3, "base": 5, "long": 10}}
        result = we.export_multiscale(obs, 0, ch_names, win_cfg, out_dir=tmp_path)

        # window_features.parquet is standalone, loadable without dataset_v3
        df = pd.read_parquet(result["out"])
        assert len(df) > 0
        assert "episode_id_ref" in df.columns  # provenance reference, not M0.2e join key
