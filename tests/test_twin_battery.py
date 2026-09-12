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


def test_calibrate_f21_faultdev_label(tmp_path):
    cal = tmp_path / "cal.json"
    twin._calibrate(str(cal))
    payload = json.loads(cal.read_text())
    by_tag = {e["fault"]: e for e in payload["episodes"]}
    assert by_tag["F-21-drift-shape"]["faultdev_applied"] is True
    assert by_tag["clean"]["faultdev_applied"] is False


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


def test_subset1_coverage_reflects_executed_row(tmp_path, capsys):
    cal = tmp_path / "cal.json"
    twin._calibrate(str(cal))
    capsys.readouterr()  # drain calibrate print
    evdir = tmp_path / "ev"
    rc = twin.main(["--manifest", "full", "--subset", "1", "--jobs", "1",
                    "--calibration", str(cal), "--wall-report",
                    "--evidence-dir", str(evdir)])
    assert rc == 0
    capsys.readouterr()  # drain battery print
    payload = json.loads((evdir / "coverage_matrix.json").read_text())
    total_rows = sum(c["n_rows"] for c in payload["cells"].values())
    total_faults = sum(c["n_faults"] for c in payload["cells"].values())
    assert total_rows == 1
    assert total_faults == 1


def test_missing_default_calibration_fails_loud_with_bootstrap(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)  # clean checkout: no default calibration file
    rc = twin.main(["--manifest", "full", "--subset", "1", "--jobs", "1"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "--calibrate" in err
    assert twin._BATTERY_CALIBRATION in err


def test_quick_validates_full_manifest_before_slice():
    full = twin.build_faults()
    assert len(full) == 224
    assert twin.validate_manifest(full) == []
    manifest, label = twin._load_manifest("quick", 12345)
    assert label == "quick"
    # quick loads FULL 224 for validation; execution slices 16 after.
    assert len(manifest) == 224
    assert twin.validate_manifest(manifest) == []
    assert len(manifest[: twin._BATTERY_QUICK_ROWS]) == 16


def test_quick_hole_in_truncated_region_fails():
    full = twin.build_faults()
    holey = [r for r in full if r["id"] != "F-21"]
    assert len(holey) == 223
    gaps = twin.validate_manifest(holey)
    assert any("F-21" in g for g in gaps)
    # truncated-16 execution slice still fails because FULL is validated first.
    exec_slice = holey[: twin._BATTERY_QUICK_ROWS]
    assert len(exec_slice) == 16
    assert twin.validate_manifest(holey) != []
