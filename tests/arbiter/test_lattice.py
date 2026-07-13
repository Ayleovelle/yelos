"""T-lattice:A1 全序公理的机器凭据。"""

from __future__ import annotations

from yelos.arbiter.lattice import SIGMA, min_sigma_verdict, sigma, sigma_of
from yelos.core.arbiter import Verdict


def test_sigma_total_order():
    assert sigma("PASS") < sigma("TRIM") < sigma("REPLACE") < sigma("SWALLOW")
    assert SIGMA["PASS"] == 0
    assert SIGMA["SWALLOW"] == 3


def test_sigma_of_verdict():
    v = Verdict("REPLACE", reason="x")
    assert sigma_of(v) == 2


def test_min_sigma_verdict_picks_conservative():
    a = Verdict("SWALLOW", reason="a")
    b = Verdict("REPLACE", reason="b")
    assert min_sigma_verdict(a, b) is b
    assert min_sigma_verdict(b, a) is b


def test_min_sigma_verdict_tie_prefers_first():
    a = Verdict("PASS", reason="a")
    b = Verdict("PASS", reason="b")
    assert min_sigma_verdict(a, b) is a
