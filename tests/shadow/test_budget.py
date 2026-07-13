"""test_budget.py:超配降档 K→1 / 降档记账可观测(degraded 位)/ 次日恢复
评估(蓝图 §11,§4.4)。
"""

from __future__ import annotations

from yelos.shadow.simulator.budget import BudgetTracker, calls_for_k


def test_calls_for_k_formula() -> None:
    assert calls_for_k(1) == 2  # tick_state(1) + shadow_state(1)
    assert calls_for_k(3) == 4  # tick_state(1) + shadow_state(3) = 默认配额上限


def test_no_history_no_degrade() -> None:
    bt = BudgetTracker()
    k, degraded = bt.decide_k(3, quota=4)
    assert k == 3
    assert degraded is False


def test_overspend_rolling_window_degrades_to_k1() -> None:
    bt = BudgetTracker()
    for _ in range(5):
        bt.record(6)  # 持续超配额(quota=4)
    k, degraded = bt.decide_k(3, quota=4)
    assert k == 1
    assert degraded is True


def test_underspend_history_does_not_degrade() -> None:
    bt = BudgetTracker()
    for _ in range(5):
        bt.record(2)
    k, degraded = bt.decide_k(3, quota=4)
    assert k == 3
    assert degraded is False


def test_reset_clears_history() -> None:
    bt = BudgetTracker()
    for _ in range(5):
        bt.record(10)
    bt.reset()
    k, degraded = bt.decide_k(3, quota=4)
    assert degraded is False
    assert k == 3


def test_window_only_keeps_recent_history() -> None:
    bt = BudgetTracker(window=3)
    for _ in range(2):
        bt.record(100)  # 会被挤出窗口
    for _ in range(3):
        bt.record(1)
    assert bt.history == [1, 1, 1]
    k, degraded = bt.decide_k(3, quota=4)
    assert degraded is False


def test_requested_k1_never_degrades() -> None:
    bt = BudgetTracker()
    bt.record(999)
    k, degraded = bt.decide_k(1, quota=4)
    assert k == 1
    assert degraded is False
