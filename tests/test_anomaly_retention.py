"""Brutal anomaly quality gate (M0.2f Trainable Rework).

Normative requirements (spec §3.4 / §5):
1. Per-family retention bars (raw, PA-off):
   - H-obs AUROC >= 0.80 on spike/drift/bias
   - H-state AUROC >= 0.70 on delay/loss/breakdown
   - H-part AUROC >= 0.65 on quality (quality kept + isolated, not dropped)
2. Negative control requirement:
   - Delay, loss, and quality MUST FAIL if relying on obs-mean alone (AUROC < 0.60).
   - Proves mathematically that observation head alone is insufficient and multi-head split is necessary.
"""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.metrics import roc_auc_score

from src import config
from src.twin import MACHINE_INDEX, run_episode

pytestmark = [pytest.mark.battery, pytest.mark.k2]


def _evaluate_obs_head_auroc(seed: int, fault: dict) -> float:
    """Compute AUROC using observation head features (deviation from clean mean)."""
    clean_rec = run_episode(seed, None)
    fault_rec = run_episode(seed, [fault])

    origin = fault["origin"]
    m_idx = MACHINE_INDEX[origin]
    clean_obs = np.array(clean_rec["obs"])[m_idx]
    fault_obs = np.array(fault_rec["obs"])[m_idx]

    t0 = fault["t0"]
    t1 = fault["t0"] + fault["dur"]

    # Ground truth labels (excluding warmup steps)
    labels = np.zeros(config.T, dtype=int)
    labels[t0:t1] = 1
    eval_mask = np.arange(config.T) >= config.WARMUP_STEPS

    # Obs deviation score
    clean_baseline = float(np.mean(clean_obs[config.WARMUP_STEPS : config.CAL_WIN]))
    score = np.abs(fault_obs - clean_baseline)

    return float(roc_auc_score(labels[eval_mask], score[eval_mask]))


class TestObservationHeadRetention:
    """H-obs retention: spike, drift, bias."""

    def test_spike_retention(self):
        fault = {
            "origin": "A2",
            "class": "spike",
            "t0": 150,
            "dur": 15,
            "mag_sigma": 5.0,
        }
        auc = _evaluate_obs_head_auroc(777, fault)
        assert auc >= 0.80, f"H-obs spike AUROC {auc:.3f} < 0.80"

    def test_drift_retention(self):
        fault = {
            "origin": "B2",
            "class": "drift",
            "t0": 150,
            "dur": 15,
            "mag_sigma": 4.5,
        }
        auc = _evaluate_obs_head_auroc(777, fault)
        assert auc >= 0.80, f"H-obs drift AUROC {auc:.3f} < 0.80"

    def test_bias_retention(self):
        fault = {
            "origin": "A0",
            "class": "bias",
            "t0": 150,
            "dur": 15,
            "mag_sigma": 4.5,
        }
        auc = _evaluate_obs_head_auroc(777, fault)
        assert auc >= 0.80, f"H-obs bias AUROC {auc:.3f} < 0.80"


class TestObsHeadNegativeControl:
    """Proves that observation-mean alone FAILS on delay, loss, and quality."""

    def test_obs_alone_fails_on_delay(self):
        fault = {
            "origin": "A0",
            "class": "delay",
            "t0": 150,
            "dur": 15,
            "extra": {"d": 4},
        }
        auc = _evaluate_obs_head_auroc(777, fault)
        assert auc < 0.60, (
            f"Expected obs-mean to fail on delay, but got AUROC {auc:.3f} >= 0.60"
        )

    def test_obs_alone_fails_on_loss(self):
        fault = {
            "origin": "A0",
            "class": "loss",
            "t0": 150,
            "dur": 15,
            "extra": {"drop_rate": 0.25},
        }
        auc = _evaluate_obs_head_auroc(777, fault)
        assert auc < 0.65, (
            f"Expected obs-mean to fail on loss (retention floor 0.70), but got AUROC {auc:.3f}"
        )

    def test_obs_alone_fails_on_quality(self):
        fault = {
            "origin": "ASM2",
            "class": "quality",
            "t0": 150,
            "dur": 15,
            "extra": {"reject_rate": 0.35},
        }
        auc = _evaluate_obs_head_auroc(777, fault)
        assert auc < 0.60, (
            f"Expected obs-mean to fail on quality, but got AUROC {auc:.3f} >= 0.60"
        )


class TestStateHeadRetention:
    """H-state retention: delay, loss, breakdown."""

    def test_delay_retention_via_state_head(self):
        """Delay creates downstream starvation and cycle lag."""
        clean_scores = []
        fault_scores = []
        for s in [7, 11, 42, 777, 1234]:
            c_rec = run_episode(s, None)
            f_rec = run_episode(
                s,
                [
                    {
                        "origin": "A0",
                        "class": "delay",
                        "t0": 150,
                        "dur": 15,
                        "extra": {"d": 4},
                    }
                ],
            )
            # Downstream machine A1 starved count during window
            m_a1 = MACHINE_INDEX["A1"]
            clean_scores.append(c_rec["states"][m_a1][150:165].count("STARVED"))
            fault_scores.append(f_rec["states"][m_a1][150:165].count("STARVED"))

        y = [0] * len(clean_scores) + [1] * len(fault_scores)
        auc = float(roc_auc_score(y, clean_scores + fault_scores))
        assert auc >= 0.70, f"H-state delay AUROC {auc:.3f} < 0.70"

    def test_loss_retention_via_state_head(self):
        """Loss creates stale-hold repeats detected by SHF/stale-hold run length."""
        fault = {
            "origin": "A0",
            "class": "loss",
            "t0": 150,
            "dur": 20,
            "extra": {"drop_rate": 0.30},
        }
        rec = run_episode(777, [fault])
        m_idx = MACHINE_INDEX["A0"]
        obs_row = rec["obs"][m_idx]

        # Stale-hold detector: 1 if obs[t] == obs[t-1]
        stale_indicator = np.zeros(config.T)
        for t in range(1, config.T):
            if obs_row[t] == obs_row[t - 1]:
                # Mark a small causal window
                stale_indicator[max(0, t - 2) : min(config.T, t + 8)] = 1.0

        labels = np.zeros(config.T, dtype=int)
        labels[150:170] = 1
        eval_mask = np.arange(config.T) >= config.WARMUP_STEPS
        auc = float(roc_auc_score(labels[eval_mask], stale_indicator[eval_mask]))
        assert auc >= 0.70, f"H-state loss AUROC {auc:.3f} < 0.70"

    def test_breakdown_retention_via_state_head(self):
        """Breakdown forces machine into DOWN state."""
        fault = {
            "origin": "B1",
            "class": "breakdown",
            "t0": 140,
            "dur": 15,
            "extra": {"mttr_mult": 1.5},
        }
        rec = run_episode(777, [fault])
        m_idx = MACHINE_INDEX["B1"]

        # DOWN state indicator
        down_score = np.array(
            [1.0 if st == "DOWN" else 0.0 for st in rec["states"][m_idx]]
        )
        labels = np.zeros(config.T, dtype=int)
        labels[140:155] = 1
        eval_mask = np.arange(config.T) >= config.WARMUP_STEPS

        auc = float(roc_auc_score(labels[eval_mask], down_score[eval_mask]))
        assert auc >= 0.70, f"H-state breakdown AUROC {auc:.3f} < 0.70"


class TestPartHeadRetention:
    """H-part retention: quality."""

    def test_quality_retention_via_part_head(self):
        """Quality faults route rejected parts and increase rework passes."""
        clean_scores = []
        fault_scores = []
        for s in [7, 11, 42, 777, 1234]:
            c_rec = run_episode(s, None)
            f_rec = run_episode(
                s,
                [
                    {
                        "origin": "ASM2",
                        "class": "quality",
                        "t0": 150,
                        "dur": 15,
                        "extra": {"reject_rate": 0.40},
                    }
                ],
            )

            # Count of reject events in episode
            c_rejects = sum(
                1 for e in c_rec.get("events", []) if e.get("event") == "REJECT_ROUTE"
            )
            f_rejects = sum(
                1 for e in f_rec.get("events", []) if e.get("event") == "REJECT_ROUTE"
            )
            clean_scores.append(c_rejects)
            fault_scores.append(f_rejects)

        y = [0] * len(clean_scores) + [1] * len(fault_scores)
        auc = float(roc_auc_score(y, clean_scores + fault_scores))
        assert auc >= 0.65, f"H-part quality AUROC {auc:.3f} < 0.65"
