"""Detector identity quarantine: variation features are attribution-only.

The detector must generalize across machines; per-machine identity
features would let it memorize which machine instead of what behavior.
This test fails closed if the flag ever leaks into a detection path.
"""
import pathlib


def test_no_variation_in_detection_paths():
    root = pathlib.Path(__file__).resolve().parent.parent
    for f in [
        "scripts/train_windows.py",
        "scripts/finalize_window_model.py",
        "scripts/diagnose_battery.py",
    ]:
        src = (root / f).read_text()
        assert "variation" not in src, f"identity leak: {f} references variation"
    # attribution side must have it
    assert "variation" in (root / "scripts" / "train_origin.py").read_text()
    assert "def _variation_block" in (root / "src" / "window_dataset.py").read_text()
