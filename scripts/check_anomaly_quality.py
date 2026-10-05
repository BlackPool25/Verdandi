#!/usr/bin/env python3
"""Brutal CI Anomaly Quality Gate Script (M0.2f Trainable Rework).

Usage:
    python scripts/check_anomaly_quality.py --families all
    python scripts/check_anomaly_quality.py --min-auroc-obs 0.80 --min-auroc-state 0.70 --min-auroc-part 0.65

Exits with code 0 if all retention bars pass; exits with code 1 (fail-closed) on any failure.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np
from sklearn.metrics import roc_auc_score

from src import config
from src.twin import MACHINE_INDEX, run_episode


def evaluate_family_retention(family: str, seed: int = 777) -> float:
    """Evaluate retention AUROC for a given fault family."""
    if family == "spike":
        fault = {
            "origin": "A2",
            "class": "spike",
            "t0": 150,
            "dur": 15,
            "mag_sigma": 5.0,
        }
        c_rec = run_episode(seed, None)
        f_rec = run_episode(seed, [fault])
        m_idx = MACHINE_INDEX["A2"]
        score = np.abs(
            np.array(f_rec["obs"][m_idx]) - np.mean(c_rec["obs"][m_idx][15:120])
        )
        labels = np.zeros(config.T, dtype=int)
        labels[150:165] = 1
        mask = np.arange(config.T) >= config.WARMUP_STEPS
        return float(roc_auc_score(labels[mask], score[mask]))

    elif family == "drift":
        fault = {
            "origin": "B2",
            "class": "drift",
            "t0": 150,
            "dur": 15,
            "mag_sigma": 4.5,
        }
        c_rec = run_episode(seed, None)
        f_rec = run_episode(seed, [fault])
        m_idx = MACHINE_INDEX["B2"]
        score = np.abs(
            np.array(f_rec["obs"][m_idx]) - np.mean(c_rec["obs"][m_idx][15:120])
        )
        labels = np.zeros(config.T, dtype=int)
        labels[150:165] = 1
        mask = np.arange(config.T) >= config.WARMUP_STEPS
        return float(roc_auc_score(labels[mask], score[mask]))

    elif family == "bias":
        fault = {
            "origin": "A0",
            "class": "bias",
            "t0": 150,
            "dur": 15,
            "mag_sigma": 4.5,
        }
        c_rec = run_episode(seed, None)
        f_rec = run_episode(seed, [fault])
        m_idx = MACHINE_INDEX["A0"]
        score = np.abs(
            np.array(f_rec["obs"][m_idx]) - np.mean(c_rec["obs"][m_idx][15:120])
        )
        labels = np.zeros(config.T, dtype=int)
        labels[150:165] = 1
        mask = np.arange(config.T) >= config.WARMUP_STEPS
        return float(roc_auc_score(labels[mask], score[mask]))

    elif family == "delay":
        # H-state: downstream starvation signal
        clean_scores, fault_scores = [], []
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
            m_a1 = MACHINE_INDEX["A1"]
            clean_scores.append(c_rec["states"][m_a1][150:165].count("STARVED"))
            fault_scores.append(f_rec["states"][m_a1][150:165].count("STARVED"))
        y = [0] * len(clean_scores) + [1] * len(fault_scores)
        return float(roc_auc_score(y, clean_scores + fault_scores))

    elif family == "loss":
        # H-state: stale-hold detector
        fault = {
            "origin": "A0",
            "class": "loss",
            "t0": 150,
            "dur": 20,
            "extra": {"drop_rate": 0.30},
        }
        rec = run_episode(seed, [fault])
        obs_row = rec["obs"][MACHINE_INDEX["A0"]]
        stale_ind = np.zeros(config.T)
        for t in range(1, config.T):
            if obs_row[t] == obs_row[t - 1]:
                stale_ind[max(0, t - 2) : min(config.T, t + 8)] = 1.0
        labels = np.zeros(config.T, dtype=int)
        labels[150:170] = 1
        mask = np.arange(config.T) >= config.WARMUP_STEPS
        return float(roc_auc_score(labels[mask], stale_ind[mask]))

    elif family == "breakdown":
        # H-state: DOWN duration
        fault = {
            "origin": "B1",
            "class": "breakdown",
            "t0": 140,
            "dur": 15,
            "extra": {"mttr_mult": 1.5},
        }
        rec = run_episode(seed, [fault])
        m_idx = MACHINE_INDEX["B1"]
        down_score = np.array(
            [1.0 if st == "DOWN" else 0.0 for st in rec["states"][m_idx]]
        )
        labels = np.zeros(config.T, dtype=int)
        labels[140:155] = 1
        mask = np.arange(config.T) >= config.WARMUP_STEPS
        return float(roc_auc_score(labels[mask], down_score[mask]))

    elif family == "quality":
        # H-part: reject routing events
        clean_scores, fault_scores = [], []
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
            c_rejects = sum(
                1 for e in c_rec.get("events", []) if e.get("event") == "REJECT_ROUTE"
            )
            f_rejects = sum(
                1 for e in f_rec.get("events", []) if e.get("event") == "REJECT_ROUTE"
            )
            clean_scores.append(c_rejects)
            fault_scores.append(f_rejects)
        y = [0] * len(clean_scores) + [1] * len(fault_scores)
        return float(roc_auc_score(y, clean_scores + fault_scores))

    raise ValueError(f"Unknown family: {family}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check anomaly quality gates.")
    parser.add_argument(
        "--families", default="all", help="Families to check (default: all)"
    )
    parser.add_argument(
        "--min-auroc-obs",
        type=float,
        default=0.80,
        help="Min AUROC for H-obs (default: 0.80)",
    )
    parser.add_argument(
        "--min-auroc-state",
        type=float,
        default=0.70,
        help="Min AUROC for H-state (default: 0.70)",
    )
    parser.add_argument(
        "--min-auroc-part",
        type=float,
        default=0.65,
        help="Min AUROC for H-part (default: 0.65)",
    )
    args = parser.parse_args()

    targets = {
        "spike": ("H-obs", args.min_auroc_obs),
        "drift": ("H-obs", args.min_auroc_obs),
        "bias": ("H-obs", args.min_auroc_obs),
        "delay": ("H-state", args.min_auroc_state),
        "loss": ("H-state", args.min_auroc_state),
        "breakdown": ("H-state", args.min_auroc_state),
        "quality": ("H-part", args.min_auroc_part),
    }

    print("=" * 60)
    print("VERDANDI M0.2F BRUTAL ANOMALY RETENTION GATE")
    print("=" * 60)

    failed = False
    for fam, (head, bar) in targets.items():
        auc = evaluate_family_retention(fam)
        passed = auc >= bar
        status = "PASS" if passed else "FAIL"
        print(
            f"[{status}] {fam:10s} ({head:7s}) -> AUROC: {auc:6.3f} (bar >= {bar:.2f})"
        )
        if not passed:
            failed = True

    print("=" * 60)
    if failed:
        print("FAILED: One or more anomaly families failed the quality gate.")
        return 1

    print("SUCCESS: All anomaly families cleared pre-registered retention bars.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
