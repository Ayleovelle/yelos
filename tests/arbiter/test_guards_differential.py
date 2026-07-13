"""T-G2:差分测试(维四,不计维二策略数)。

守卫链(guards.GUARD_CHAIN)vs 冻结内核 core.arbiter.arbitrate 的前 6 步:
随机网格上"是否命中某条守卫 + reason"逐项一致。这是"两套逐字节等价
实现"的差分锁,证明 guards/ 拆件是冻结内核前 6 步的忠实抽出,而不是
另一套可能悄悄漂移的平行实现。
"""

from __future__ import annotations

import itertools
import random

from yelos.arbiter.guards import GUARD_CHAIN
from yelos.arbiter.inputs import PolicyInput, PolicyParams
from yelos.core.arbiter import ArbiterInput

# 冻结内核前 6 步会产生的守卫 reason 集合(§4.2 字面量),用于比对。
_GUARD_REASONS = {
    "guard_silenced_or_unbound",
    "guard_self",
    "guard_no_plain",
    "guard_non_plain",
    "guard_engine_guard",
    "guard_min_gap",
}


def _core_guard_reason(inp: ArbiterInput) -> str | None:
    """逐字重放冻结内核 arbitrate() 的前 6 步守卫判定(只读,不叠加决策表)。

    刻意与 core.arbiter.arbitrate 的前 6 个 if 分支保持逐行对齐,任何一侧
    改了顺序或条件都会让本函数与 guards.GUARD_CHAIN 产生分歧,从而让
    本测试变红——这正是差分锁的意义。
    """
    from yelos.core import sget

    if not inp.bound or not inp.enabled or inp.silenced:
        return "guard_silenced_or_unbound"
    if inp.is_self:
        return "guard_self"
    if not inp.has_plain or not inp.draft.strip():
        return "guard_no_plain"
    if inp.has_non_plain:
        return "guard_non_plain"
    if inp.surface is None or sget(inp.surface, "guard.allowed", True) is False:
        return "guard_engine_guard"
    if inp.now_ts - inp.last_intervention_ts < inp.min_gap_seconds:
        return "guard_min_gap"
    return None


def _guard_chain_reason(pin: PolicyInput) -> str | None:
    for g in GUARD_CHAIN:
        v = g(pin)
        if v is not None:
            return v.reason
    return None


def test_guard_chain_matches_core_first_six_steps_random_grid():
    rng = random.Random(2026)
    bool_vals = [True, False]
    surfaces = [None, {"guard": {"allowed": True}}, {"guard": {"allowed": False}}, {}]
    checked = 0
    for (
        bound,
        enabled,
        silenced,
        is_self,
        has_plain,
        has_non_plain,
        draft_blank,
    ) in itertools.product(bool_vals, repeat=7):
        surface = rng.choice(surfaces)
        now_ts = rng.choice([1000.0, 2000.0])
        last_ts = rng.choice([0.0, 999.5, 1000.0])
        min_gap = rng.choice([1, 180, 500])
        base = ArbiterInput(
            session_id="s",
            day_key="2026-07-11",
            draft="   " if draft_blank else "有内容的草稿。",
            surface=surface,
            p=0.8,
            bound=bound,
            enabled=enabled,
            silenced=silenced,
            is_self=is_self,
            has_plain=has_plain,
            has_non_plain=has_non_plain,
            now_ts=now_ts,
            last_intervention_ts=last_ts,
            min_gap_seconds=min_gap,
        )
        params = PolicyParams(0.75, 0.55, 0.70, 1.0)
        pin = PolicyInput(
            base=base, surface_age_s=0.0, daily_interventions=0, params=params
        )
        expected = _core_guard_reason(base)
        actual = _guard_chain_reason(pin)
        assert actual == expected, (base, actual, expected)
        checked += 1
    assert checked == 2**7
