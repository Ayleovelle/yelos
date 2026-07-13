"""test_models_property.py —— 性质测试(finitude_BLUEPRINT §11,A1/A2/A3/A4 锚)。

随机事件序列(seed 固定)× 四模型:契约 P 单调不增(A1)、spend<=cap(A2)、W 单调(A2)、
事件单调(A3)、reserve F<=S/回填界/S 独立(A4)、Legacy/不活跃原样、负 hi 钳零。
"""

from __future__ import annotations

import random

import pytest

from yelos.finitude.gate import settle_through_gate
from yelos.finitude.models import MODEL_REGISTRY, build_model
from yelos.finitude.models.protocol import DayFacts
from yelos.finitude.models.weibull import weibull_w

LIFESPAN = 60


def _facts(
    day: int,
    *,
    active: bool = True,
    hi: int = 0,
    concern: int = 0,
    active_days_settled: int = 0,
    lifespan: int = LIFESPAN,
    epoch_shift: bool = False,
) -> DayFacts:
    return DayFacts(
        day=f"d{day}",
        was_active_day=active,
        high_intensity=hi,
        concern_fired=concern,
        swallowed=0,
        proactive_sent=0,
        epoch_shift_yesterday=epoch_shift,
        active_days_settled=active_days_settled,
        lifespan_active_days=lifespan,
    )


@pytest.mark.parametrize("model_id", list(MODEL_REGISTRY))
def test_monotone_all_models(model_id):
    """# [FIN-A1] 随机事件序列(1000 轨迹的精简版 × 200 日)回放,契约 P 单调不增。"""
    for seed in range(30):  # 精简自 1000 轨迹以控制测试时长,仍覆盖足够随机性
        rng = random.Random(seed)
        model, _ = build_model(model_id, {}, fast=1.0)
        p = 1.0
        active_days_settled = 0
        for day in range(200):
            active = rng.random() < 0.7
            hi = rng.randint(0, 4)
            concern = rng.randint(0, 3)
            facts = _facts(
                day,
                active=active,
                hi=hi,
                concern=concern,
                active_days_settled=active_days_settled,
                lifespan=LIFESPAN,
            )
            outcome = settle_through_gate(model, p, facts)
            new_p = outcome.new_p
            assert new_p <= p + 1e-12
            assert 0.0 <= new_p <= 1.0
            if active:
                active_days_settled += 1
                if model_id == "reserve" and outcome.fast_pool is not None:
                    model.fast = outcome.fast_pool
            p = new_p


@pytest.mark.parametrize("model_id", list(MODEL_REGISTRY))
def test_legacy_and_inactive_untouched(model_id):
    model, _ = build_model(model_id, {}, fast=1.0)
    facts_inactive = _facts(1, active=False, hi=5)
    out = settle_through_gate(model, 0.5, facts_inactive)
    assert out.new_p == 0.5

    facts_legacy = _facts(1, active=True, hi=5, lifespan=0)
    out2 = settle_through_gate(model, 0.5, facts_legacy)
    assert out2.new_p == 0.5


@pytest.mark.parametrize("model_id", list(MODEL_REGISTRY))
def test_negative_hi_clamped_to_zero(model_id):
    """负 hi 被钳到 0,不会导致 spend 变负、P 上升。"""
    model, _ = build_model(model_id, {}, fast=1.0)
    facts = _facts(1, active=True, hi=-9, concern=-9, active_days_settled=0)
    out = settle_through_gate(model, 0.8, facts)
    assert out.new_p <= 0.8


def test_spend_cap_weibull():
    """# [FIN-A2] weibull:spend<=2*base,即使 hi 很大。"""
    model, _ = build_model("weibull", {"k": 1.6}, fast=1.0)
    facts_huge = _facts(1, active=True, hi=100, active_days_settled=10)
    facts_at_cap = _facts(1, active=True, hi=2, active_days_settled=10)
    out_huge = settle_through_gate(model, 1.0, facts_huge)
    out_cap = settle_through_gate(model, 1.0, facts_at_cap)
    assert abs(out_huge.new_p - out_cap.new_p) < 1e-9


def test_spend_cap_event_weighted():
    """event 模型的 E 内建 min(...,2),cap 天然满足。"""
    model, _ = build_model("event", {}, fast=1.0)
    facts_huge = _facts(1, active=True, hi=1000, concern=1000, active_days_settled=0)
    out = settle_through_gate(model, 1.0, facts_huge)
    base = 1.0 / LIFESPAN
    assert (1.0 - out.new_p) <= 2.0 * base + 1e-9


def test_w_monotone_weibull():
    """# [FIN-A2] W(t) 对 t 单调不减,W(0)=0,W(L)=1。"""
    lifespan = 50
    for k in (1.0, 1.6, 2.5, 4.0):
        prev = weibull_w(0, lifespan, k)
        assert prev == 0.0
        for t in range(1, lifespan + 1):
            cur = weibull_w(t, lifespan, k)
            assert cur >= prev - 1e-12
            prev = cur
        assert abs(weibull_w(lifespan, lifespan, k) - 1.0) < 1e-9


def test_event_monotone():
    """# [FIN-A3] 固定其余分量,hi/concern/epoch_shift 各自 e 与 e+1 逐点比较,耗散不减。"""
    model, _ = build_model("event", {}, fast=1.0)
    p = 1.0
    prev_spend = -1.0
    for hi in range(0, 6):
        facts = _facts(1, active=True, hi=hi, concern=0, active_days_settled=0)
        out = settle_through_gate(model, p, facts)
        spend = p - out.new_p
        assert spend >= prev_spend - 1e-12
        prev_spend = spend

    prev_spend = -1.0
    for concern in range(0, 6):
        facts = _facts(1, active=True, hi=0, concern=concern, active_days_settled=0)
        out = settle_through_gate(model, p, facts)
        spend = p - out.new_p
        assert spend >= prev_spend - 1e-12
        prev_spend = spend

    facts_no_shift = _facts(
        1, active=True, hi=0, concern=0, active_days_settled=0, epoch_shift=False
    )
    facts_shift = _facts(
        1, active=True, hi=0, concern=0, active_days_settled=0, epoch_shift=True
    )
    out_no_shift = settle_through_gate(model, p, facts_no_shift)
    out_shift = settle_through_gate(model, p, facts_shift)
    assert (p - out_shift.new_p) >= (p - out_no_shift.new_p) - 1e-12


# --- ReserveModel 三则(A4)---------------------------------------------------


def test_reserve_f_le_s():
    """# [FIN-A4] 任意事件序列,F<=S 恒成立。"""
    rng = random.Random(11)
    model, _ = build_model("reserve", {}, fast=1.0)
    s = 1.0
    active_days_settled = 0
    for day in range(300):
        hi = rng.randint(0, 3)
        concern = rng.randint(0, 3)
        facts = _facts(
            day,
            active=True,
            hi=hi,
            concern=concern,
            active_days_settled=active_days_settled,
            lifespan=200,
        )
        out = settle_through_gate(model, s, facts)
        assert out.fast_pool is not None
        assert out.fast_pool <= out.new_p + 1e-9
        s = out.new_p
        model.fast = out.fast_pool
        active_days_settled += 1


def test_reserve_refill_bound():
    """无事件日回填 <= min(r, S-F)。"""
    r = 0.01
    model, _ = build_model("reserve", {"r": r}, fast=0.5)
    facts = _facts(1, active=True, hi=0, concern=0, active_days_settled=0, lifespan=200)
    s_before = 0.9
    out = settle_through_gate(model, s_before, facts)
    s_after = out.new_p
    delta_f = out.fast_pool - 0.5
    headroom = max(0.0, s_after - 0.5)
    assert delta_f <= min(r, headroom) + 1e-9
    assert delta_f >= -1e-9


def test_reserve_s_independent_of_f():
    """S 的演化只看 lifespan,与 F 无关(两次不同 F,相同事件下 S' 相同)。"""
    facts = _facts(1, active=True, hi=2, concern=1, active_days_settled=5, lifespan=100)
    model_a, _ = build_model("reserve", {}, fast=0.1)
    model_b, _ = build_model("reserve", {}, fast=0.9)
    out_a = settle_through_gate(model_a, 0.95, facts)
    out_b = settle_through_gate(model_b, 0.95, facts)
    assert abs(out_a.new_p - out_b.new_p) < 1e-12
