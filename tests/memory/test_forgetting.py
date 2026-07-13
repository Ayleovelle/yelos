"""test_forgetting.py:艾宾浩斯双衰减(性质)。

锁 R 单调不增(MEM-A1)、复述增益有界(MEM-A2/MEM-T1)、双族参数域、
90 虚拟日双族分位差(维二凭据)。
"""

from __future__ import annotations

from yelos.memory.forgetting.retention import (
    S_CAP,
    ExpRetention,
    PowRetention,
    get_family,
    rehearse,
)

DAY = 86400.0


def test_r_at_zero_is_one():
    for fam in (ExpRetention(), PowRetention()):
        assert fam.R(0.0, 1.0) == 1.0


def test_r_monotone_nonincreasing_random_grid():
    import random

    rng = random.Random(7)
    for fam in (ExpRetention(), PowRetention()):
        s = rng.uniform(0.1, 10.0)
        dts = sorted(rng.uniform(0.0, 100 * DAY) for _ in range(50))
        rs = [fam.R(dt, s) for dt in dts]
        for a, b in zip(rs, rs[1:]):
            assert a >= b - 1e-12


def test_r_bounds_in_zero_one():
    import random

    rng = random.Random(11)
    for fam in (ExpRetention(), PowRetention()):
        for _ in range(50):
            dt = rng.uniform(0.0, 1000 * DAY)
            s = rng.uniform(0.01, 100.0)
            r = fam.R(dt, s)
            assert 0.0 <= r <= 1.0 + 1e-12


def test_rehearsal_gain_bounded_and_monotone_in_r_now():
    s0 = 2.0
    s_low_r = rehearse(s0, R_now=0.1, g=0.6)  # 快忘时被想起
    s_high_r = rehearse(s0, R_now=0.9, g=0.6)  # 还记得很清楚时被想起
    assert s_low_r >= s0
    assert s_high_r >= s0
    assert s_low_r >= s_high_r  # 越快忘、被想起时增益越大(MEM-A2)
    assert s_low_r <= S_CAP


def test_rehearsal_caps_at_s_cap():
    s = S_CAP
    for _ in range(20):
        s = rehearse(s, R_now=0.01, g=0.9, s_cap=S_CAP)
    assert s <= S_CAP + 1e-9


def test_s_monotone_nondecreasing_under_rehearse_sequence():
    """MEM-T1:复述有界——任意访问序列下 S 单调不减且 <= S_CAP。"""
    import random

    rng = random.Random(3)
    s = 1.0
    for _ in range(100):
        r_now = rng.uniform(0.0, 1.0)
        new_s = rehearse(s, r_now)
        assert new_s >= s - 1e-12
        assert new_s <= S_CAP + 1e-9
        s = new_s


def test_get_family_unknown_falls_back_to_exp():
    fam = get_family("nonexistent")
    assert fam.name == "exp"
    assert get_family("exp").name == "exp"
    assert get_family("pow").name == "pow"


def test_90_day_family_quantile_difference():
    """维二凭据:90 虚拟日回放,同访问序列下旧条目 exp/pow 的 R 值分位显著不同。"""
    exp_fam = ExpRetention()
    pow_fam = PowRetention()
    dts = [i * DAY for i in range(1, 91)]
    s = 1.0
    exp_values = [exp_fam.R(dt, s) for dt in dts]
    pow_values = [pow_fam.R(dt, s) for dt in dts]

    def median(vals):
        s_vals = sorted(vals)
        n = len(s_vals)
        mid = n // 2
        return s_vals[mid] if n % 2 else (s_vals[mid - 1] + s_vals[mid]) / 2.0

    exp_med = median(exp_values)
    pow_med = median(pow_values)
    # 幂律重尾:90 日后应比指数保留更多记忆(pow 中位数显著更高)
    assert pow_med > exp_med * 2.0


def test_pow_retains_more_than_exp_at_long_horizon():
    exp_fam = ExpRetention()
    pow_fam = PowRetention()
    dt = 60 * DAY
    assert pow_fam.R(dt, 1.0) > exp_fam.R(dt, 1.0)
