"""Structural gate tests (per-class experts): delay/loss/breakdown + Bernoulli CUSUM quality."""

from __future__ import annotations

import math

import numpy as np
import pytest

from src import gates

pytestmark = [pytest.mark.k2, pytest.mark.k3, pytest.mark.battery]


def test_delay_gate_fires_on_lag_not_down():
    assert gates.delay_gate(12, "STARVED")
    assert gates.delay_gate(10, "RUN")
    assert not gates.delay_gate(9, "STARVED")
    # DOWN-owned: breakdown gate's jurisdiction, no double-fire.
    assert not gates.delay_gate(50, "DOWN")


def test_loss_gate_matches_shf_dropout():
    assert gates.loss_gate(6)
    assert gates.loss_gate(12)
    assert not gates.loss_gate(5)


def test_breakdown_gate_debounce():
    assert gates.breakdown_gate(3)
    assert gates.breakdown_gate(20)
    assert not gates.breakdown_gate(2)


def test_bernoulli_cusum_weights_sign():
    w_fail, w_pass = gates.bernoulli_cusum_weights(0.05, 0.30)
    assert w_fail == pytest.approx(math.log(6.0))
    assert w_pass == pytest.approx(math.log(0.7 / 0.95))
    assert w_fail > 0 > w_pass


def test_bernoulli_cusum_quiet_stream_no_alarm():
    w_fail, w_pass = gates.bernoulli_cusum_weights(0.05, 0.30)
    s, alarm = 0.0, False
    for _ in range(50):
        s, alarm = gates.bernoulli_cusum_update(s, True, w_fail, w_pass, h=2.5)
        assert not alarm
    assert s == pytest.approx(0.0)


def test_bernoulli_cusum_burst_alarms():
    w_fail, w_pass = gates.bernoulli_cusum_weights(0.05, 0.30)
    s, alarm = 0.0, False
    for _ in range(2):
        s, alarm = gates.bernoulli_cusum_update(s, False, w_fail, w_pass, h=2.5)
    assert alarm


def test_kit_outcomes_reject_is_fail_and_paired_route_deduped():
    events = [
        {"t": 10, "event": "LATE_VERDICT", "detail": {"part": "k1", "verdict": "OK"}},
        {"t": 11, "event": "BOGUS_TYPE", "detail": {"verdict": "OK"}},
        {
            "t": 12,
            "event": "LATE_VERDICT",
            "detail": {"part": "k2", "verdict": "REJECT"},
        },
        {"t": 13, "event": "REJECT_ROUTE", "detail": {"part": "k2", "to": "scrap"}},
    ]
    assert gates.kit_outcomes_from_events(events) == [(10, True), (12, False)]


def test_kit_outcomes_retest_after_rework_counts_again():
    events = [
        {
            "t": 10,
            "event": "LATE_VERDICT",
            "detail": {"part": "k1", "verdict": "REJECT"},
        },
        {"t": 11, "event": "REJECT_ROUTE", "detail": {"part": "k1", "to": "RWK0"}},
        {"t": 40, "event": "LATE_VERDICT", "detail": {"part": "k1", "verdict": "OK"}},
    ]
    assert gates.kit_outcomes_from_events(events) == [(10, False), (40, True)]


def test_track_counters_mirrors_export_semantics():
    states = np.array([["RUN", "RUN", "STARVED", "DOWN", "DOWN", "RUN"]])
    tput = np.array([[1, 0, 0, 0, 0, 1]])
    obs = np.array([[1.0, 2.0, 2.0, 0.5, 0.5, 1.5]])
    c = gates.track_counters(obs, states, tput, [1.0])
    assert list(c["dwell"][0]) == [1, 2, 1, 1, 2, 1]
    assert list(c["tputlag"][0]) == [0, 1, 2, 3, 4, 0]
    assert list(c["downrun"][0]) == [0, 0, 0, 1, 2, 0]
    assert list(c["stale"][0]) == [0, 0, 1, 0, 1, 0]


def test_kit_outcomes_carry_event_time():
    events = [
        {"t": 10, "event": "LATE_VERDICT", "detail": {"part": "k1", "verdict": "OK"}},
        {
            "t": 12,
            "event": "LATE_VERDICT",
            "detail": {"part": "k2", "verdict": "REJECT"},
        },
        {"t": 13, "event": "REJECT_ROUTE", "detail": {"part": "k2", "to": "scrap"}},
    ]
    assert gates.kit_outcomes_from_events(events) == [(10, True), (12, False)]
