"""AX-B3(bench_BLUEPRINT §2)+ Real/Virtual 公式等同(§8.2 test_clock.py)。"""

from __future__ import annotations

from datetime import datetime

import pytest

from yelos.bench.clock import RealClock, VirtualClock
from yelos.core.clock import Clock


def test_real_and_virtual_satisfy_clock_protocol():
    assert isinstance(RealClock(), Clock)
    assert isinstance(VirtualClock(0.0), Clock)


def test_virtual_clock_formulas_match_real_clock_shape():
    ts = datetime(2026, 3, 15, 9, 30, 0).timestamp()
    vc = VirtualClock(start_ts=ts)
    assert vc.now_ts() == ts
    assert vc.day_key() == "2026-03-15"
    assert vc.local_minutes() == 9 * 60 + 30
    expected_day_end = datetime(2026, 3, 16, 0, 0, 0).timestamp()
    assert vc.day_end_ts() == expected_day_end


def test_virtual_clock_advance_and_advance_to():
    vc = VirtualClock(start_ts=0.0)
    vc.advance(60.0)
    assert vc.now_ts() == 60.0
    vc.advance_to(120.0)
    assert vc.now_ts() == 120.0
    with pytest.raises(ValueError):
        vc.advance_to(60.0)
    with pytest.raises(ValueError):
        vc.advance(-1.0)


def test_next_quiet_start_ts_rolls_to_next_day_when_past():
    start = datetime(2026, 1, 1, 23, 0, 0).timestamp()
    vc = VirtualClock(start_ts=start)
    # 22:00(1320 分钟)已过 -> 顺延到次日
    nxt = vc.next_quiet_start_ts(22 * 60)
    assert nxt == datetime(2026, 1, 2, 22, 0, 0).timestamp()
    # 尚未到达的静默起点(23:30)在今天
    nxt2 = vc.next_quiet_start_ts(23 * 60 + 30)
    assert nxt2 == datetime(2026, 1, 1, 23, 30, 0).timestamp()


def _walk(clock: VirtualClock, step_seconds: float, checkpoints_seconds: list[float]):
    """从 clock 当前游标出发,用固定 step_seconds 累加推进,在每个
    checkpoint(相对 start 的秒偏移,须为 step_seconds 整数倍)采样
    (day_key, local_minutes, next_quiet_start_ts, day_end_ts)。
    """
    samples = []
    elapsed = 0.0
    for cp in checkpoints_seconds:
        while elapsed < cp:
            clock.advance(step_seconds)
            elapsed += step_seconds
        samples.append(
            (
                clock.day_key(),
                clock.local_minutes(),
                clock.next_quiet_start_ts(22 * 60),
                clock.day_end_ts(),
            )
        )
    return samples


def test_ax_b3_no_drift_fine_grained_1s_vs_60s():
    """AX-B3 细粒度档:1x(1 秒)步长 vs 60x(1 分钟)步长,在 2 小时窗口内
    每 10 分钟采样一次,derived 值逐点相同(无累计漂移)。
    """
    start = datetime(2026, 6, 1, 7, 0, 0).timestamp()
    checkpoints = [i * 600 for i in range(1, 13)]  # 每 10 分钟,共 2 小时

    c1 = VirtualClock(start_ts=start)
    s1 = _walk(c1, 1.0, checkpoints)

    c60 = VirtualClock(start_ts=start)
    s60 = _walk(c60, 60.0, checkpoints)

    assert s1 == s60


def test_ax_b3_no_drift_coarse_60s_vs_86400s_across_rollover():
    """AX-B3 粗粒度档:60x(1 分钟)步长 vs 86400x(整日)步长,跨 3 个虚拟日
    的日边界(rollover)采样,day_key 序列与 quiet 窗判定逐日一致。
    """
    start = datetime(2026, 6, 1, 0, 0, 0).timestamp()
    checkpoints = [i * 86400 for i in range(1, 4)]  # 第 1/2/3 日边界

    c_min = VirtualClock(start_ts=start)
    s_min = _walk(c_min, 60.0, checkpoints)

    c_day = VirtualClock(start_ts=start)
    s_day = _walk(c_day, 86400.0, checkpoints)

    assert s_min == s_day
    # rollover 确实发生:day_key 逐日递增,不停滞
    day_keys = [row[0] for row in s_min]
    assert day_keys == sorted(set(day_keys)) and len(set(day_keys)) == 3
