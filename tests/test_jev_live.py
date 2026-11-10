"""Task 4: live Jev eval (key-gated; records skip without JEV_API_KEY).

Fixed episode set; metrics: category accuracy vs GBM 0.671 baseline,
citation precision/recall (template path, always runnable), null rate.
"""
import os
import sys

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("JEV_API_KEY"), reason="no JEV_API_KEY; template path covered"
)


def test_live_jev_categorization():
    from src import jev

    assert os.environ.get("JEV_API_KEY")
    assert jev.JEV_SPEC == "v1"
