"""CI-fast battery runner smoke test: calibration + entry point."""

import json

import pytest

from src import twin

pytestmark = [pytest.mark.battery, pytest.mark.k5]


def test_calibrate_writes_valid_json(tmp_path):
    cal = tmp_path / "cal.json"
    twin._calibrate(str(cal))
    payload = json.loads(cal.read_text())
    assert set(payload) >= {"mean_per_episode_s", "seeds", "episodes_timed", "episodes"}
    assert payload["episodes_timed"] == 6
    assert len(payload["episodes"]) == 6
    assert payload["mean_per_episode_s"] > 0
    assert twin._load_calibration(str(cal)) == payload["mean_per_episode_s"]


def test_seed_rule():
    assert twin.battery_episode_seed(12345, 3) == 12345 * 1000 + 3
    assert twin.battery_episode_seed(7, 0) == 7000


def test_battery_entry_point_subset1(tmp_path, capsys):
    cal = tmp_path / "cal.json"
    twin._calibrate(str(cal))
    capsys.readouterr()  # drain calibrate print
    rc = twin.main(["--manifest", "full", "--subset", "1", "--jobs", "1",
                    "--calibration", str(cal)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "verdict=PASS" in out
