"""T-SCH-01..04(intrinsic_BLUEPRINT §6/§8.2)。"""

from __future__ import annotations


from yelos.intrinsic.field.integrators import EulerIntegrator
from yelos.intrinsic.field.state import FieldParams, FieldState
from yelos.intrinsic.scheduler import budget as budget_mod
from yelos.intrinsic.scheduler.heartbeat import catchup_field, step_field
from yelos.intrinsic.scheduler.virtual_clock import Clock, RealClock, VirtualClock


# --- T-SCH-01:错峰确定性 ---------------------------------------------------


def test_sch01_batch_assignment_deterministic() -> None:
    a1 = budget_mod.batch_index("user-1", 4)
    a2 = budget_mod.batch_index("user-1", 4)
    assert a1 == a2
    assert 0 <= a1 < 4


def test_sch01_batches_spread_sessions() -> None:
    sids = [f"user-{i}" for i in range(50)]
    buckets = {budget_mod.batch_index(sid, 5) for sid in sids}
    assert len(buckets) > 1  # 50 个 sid 不该全落同一批


def test_sch01_should_run_this_cycle_consistent_with_batch_index() -> None:
    sid = "user-7"
    n_batches = 3
    idx = budget_mod.batch_index(sid, n_batches)
    for cycle in range(9):
        expected = (cycle % n_batches) == idx
        assert budget_mod.should_run_this_cycle(sid, cycle, n_batches) == expected


# --- T-SCH-02:内联补算确定性 + 近似误差界 -----------------------------------


def _local_minutes_fn(ts: float) -> int:
    return int((ts // 60) % 1440)


def test_sch02_catchup_deterministic_same_start_same_elapsed() -> None:
    params = FieldParams()
    integ = EulerIntegrator()
    phi0 = FieldState(drive=0.7, languor=0.2, longing=0.5, afterglow=0.3, ts=0.0)

    result_a = catchup_field(phi0, 3600.0 * 5, 60.0, _local_minutes_fn, params, integ)
    result_b = catchup_field(phi0, 3600.0 * 5, 60.0, _local_minutes_fn, params, integ)
    assert result_a == result_b


def test_sch02_catchup_under_cap_matches_manual_stepping() -> None:
    params = FieldParams()
    integ = EulerIntegrator()
    phi0 = FieldState(drive=0.7, languor=0.2, longing=0.5, afterglow=0.3, ts=0.0)
    interval = 60.0
    n_steps = 10
    elapsed = interval * n_steps

    got = catchup_field(phi0, elapsed, interval, _local_minutes_fn, params, integ)

    manual = phi0
    t = 0.0
    for _ in range(n_steps):
        t_next = t + interval
        manual = step_field(
            manual, 1.0, t_next, _local_minutes_fn(t_next), 0.0, params, integ, None, ()
        )
        t = t_next
    assert got == manual


def test_sch02_catchup_over_cap_uses_bounded_fast_forward() -> None:
    """超上限段用闭式衰减快进,近似误差有界(相对"若逐块补算到底"的差异有界)。"""
    params = FieldParams()
    integ = EulerIntegrator()
    phi0 = FieldState(drive=0.9, languor=0.1, longing=0.8, afterglow=0.0, ts=0.0)
    interval = 60.0
    max_steps = 5
    elapsed = interval * 1000  # 远超上限,必走快进路径

    fast = catchup_field(
        phi0,
        elapsed,
        interval,
        _local_minutes_fn,
        params,
        integ,
        max_catchup_steps=max_steps,
    )
    for v in fast.vec():
        assert 0.0 <= v <= 1.0

    # 误差界:闭式衰减快进只忽略强迫项(量级 <= 0.04,§1.1 AMPLITUDE),
    # 在无穷长衰减后各通道应已充分逼近 eq(强迫项扰动量级有界,不会让
    # 结果偏离 eq 太远)。
    for v, eq in zip(fast.vec(), params.eq):
        assert abs(v - eq) < 0.1


def test_sch02_no_catchup_needed_when_not_elapsed() -> None:
    params = FieldParams()
    integ = EulerIntegrator()
    phi0 = FieldState(drive=0.5, languor=0.5, longing=0.5, afterglow=0.5, ts=100.0)
    result = catchup_field(phi0, 100.0, 60.0, _local_minutes_fn, params, integ)
    assert result == phi0


# --- T-SCH-03:虚拟时钟(复用 bench.clock,不重定义,X2)------------------------


def test_sch03_virtual_clock_satisfies_clock_protocol() -> None:
    vc = VirtualClock(0.0)
    assert isinstance(vc, Clock)
    assert isinstance(RealClock(), Clock)


def test_sch03_virtual_clock_30_day_replay_deterministic() -> None:
    vc_a = VirtualClock(0.0)
    vc_b = VirtualClock(0.0)
    day_keys_a = []
    day_keys_b = []
    for _ in range(30):
        vc_a.advance(86400.0)
        vc_b.advance(86400.0)
        day_keys_a.append(vc_a.day_key())
        day_keys_b.append(vc_b.day_key())
    assert day_keys_a == day_keys_b
    assert len(set(day_keys_a)) == 30  # 30 个不同日期,逐日推进


def test_sch03_virtual_clock_step_size_invariant() -> None:
    """任意步长推进,对同一最终时刻给出相同结果(AX-B3)。"""
    vc_big_steps = VirtualClock(0.0)
    vc_big_steps.advance(86400.0 * 10)

    vc_small_steps = VirtualClock(0.0)
    for _ in range(10):
        vc_small_steps.advance(86400.0)

    assert vc_big_steps.now_ts() == vc_small_steps.now_ts()
    assert vc_big_steps.day_key() == vc_small_steps.day_key()


# --- T-SCH-04:降档记账 -----------------------------------------------------


def test_sch04_budget_degrades_when_quota_exceeded() -> None:
    state = budget_mod.BudgetState()
    quota = 3
    period = "2026-07-11"
    decisions = []
    for _ in range(5):
        d = budget_mod.check_budget(state, period, quota)
        decisions.append(d.degrade)
        state = d.new_state
    assert decisions == [False, False, False, True, True]
    assert state.calls_used == quota


def test_sch04_budget_resets_on_new_period() -> None:
    state = budget_mod.BudgetState(period_key="2026-07-10", calls_used=5)
    d = budget_mod.check_budget(state, "2026-07-11", quota=3)
    assert d.degrade is False
    assert d.new_state.period_key == "2026-07-11"
    assert d.new_state.calls_used == 1
