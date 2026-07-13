"""guards/min_gap.py 在整个架构中的位置。

AX:A3 不应期时序公理的代码锚点。N5 铁律:min_gap 硬约束保持,不入
hysteresis 可变异集。冻结内核 arbitrate 第 6 步(最后一道前置守卫)的
差分锁抽出件——语义与 core.arbiter 同款,故意不作任何"深化",这条
守卫存在的意义就是逐字节等价,供 TablePolicy 之外的策略复用。

推论 C1(如实标注"推论",不称定理,arbiter_BLUEPRINT §1.1 A3):
本守卫直接蕴含长程介入率 <= 1/min_gap,这是平凡推论,不产生新可观测
行为,不入深度账——统计验证见 tests/arbiter/test_policy_invariants.py。
"""

from __future__ import annotations

from ...core.arbiter import Verdict
from ..inputs import PolicyInput

guard_id = "min_gap"


def guard_min_gap(pin: PolicyInput) -> "Verdict | None":
    b = pin.base
    if b.now_ts - b.last_intervention_ts < b.min_gap_seconds:
        return Verdict("PASS", reason="guard_min_gap")
    return None


guard_min_gap.__name__ = guard_id  # type: ignore[attr-defined]
