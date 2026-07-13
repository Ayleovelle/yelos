"""test_compat_v01.py —— 兼容闸(finitude_BLUEPRINT §11,131 迁移闸)。

`LinearDecay` ≡ `core.finitude.settle_day` 逐字节(网格 p × e × L);
`epochs.fixed` 对 `core.finitude.epoch`/`epoch_transition` 的委托一致。
`tests/test_finitude.py`(既有 131 迁移闸)本文件不触碰、不重复其内容,只在
`test_existing_v01_suite_still_passes_smoke` 里用 subprocess 之外的直接调用
做一次轻量交叉抽查(避免维护两份重叠断言)。
"""

from __future__ import annotations

from yelos.core import finitude as core_finitude
from yelos.finitude.epochs import fixed
from yelos.finitude.gate import settle_through_gate
from yelos.finitude.models.linear import LinearDecay
from yelos.finitude.models.protocol import DayFacts


def _facts(active_day: bool, hi: int, lifespan: int) -> DayFacts:
    return DayFacts(
        day="d1",
        was_active_day=active_day,
        high_intensity=hi,
        concern_fired=0,
        swallowed=0,
        proactive_sent=0,
        epoch_shift_yesterday=False,
        active_days_settled=0,
        lifespan_active_days=lifespan,
    )


def test_linear_bytewise_settle_day():
    """LinearDecay(经 gate)与 core.finitude.settle_day 直调,网格上逐字节一致。"""
    model = LinearDecay()
    p_grid = [0.0, 0.05, 0.15, 0.3, 0.5, 0.6, 0.73, 0.9, 1.0]
    e_grid = [0, 1, 2, 3, 4, 10]
    l_grid = [1, 2, 10, 30, 100, 545]
    for p in p_grid:
        for hi in e_grid:
            for lifespan in l_grid:
                for active in (True, False):
                    expected = core_finitude.settle_day(
                        p,
                        was_active_day=active,
                        high_intensity_events=hi,
                        lifespan_active_days=lifespan,
                    )
                    facts = _facts(active, hi, lifespan)
                    out = settle_through_gate(model, p, facts)
                    assert out.new_p == expected, (
                        f"p={p} hi={hi} L={lifespan} active={active}: "
                        f"gate={out.new_p} core={expected}"
                    )


def test_linear_legacy_and_zero_lifespan_bytewise():
    model = LinearDecay()
    for lifespan in (0, -1, -100):
        facts = _facts(True, 3, lifespan)
        expected = core_finitude.settle_day(
            0.42,
            was_active_day=True,
            high_intensity_events=3,
            lifespan_active_days=lifespan,
        )
        out = settle_through_gate(model, 0.42, facts)
        assert out.new_p == expected == 0.42


def test_epoch_delegation_bytewise():
    for p in [0.0, 0.0001, 0.1, 0.15, 0.15001, 0.3, 0.3001, 0.6, 0.6001, 1.0]:
        assert fixed.epoch_of(p) == core_finitude.epoch(p)


def test_epoch_transition_delegation_bytewise():
    pairs = [(0.9, 0.65), (0.65, 0.6), (0.3, 0.3), (0.3, 0.15), (0.15, 0.0)]
    for old_p, new_p in pairs:
        assert fixed.transition(old_p, new_p) == core_finitude.epoch_transition(
            old_p, new_p
        )


def test_epoch_index_matches_name_order():
    for idx, name in enumerate(fixed.EPOCH_NAMES):
        assert fixed.EPOCH_NAMES[idx] == name
    assert fixed.epoch_index(1.0) == fixed.EPOCH_NAMES.index("盛年")
    assert fixed.epoch_index(0.0) == fixed.EPOCH_NAMES.index("静止")
