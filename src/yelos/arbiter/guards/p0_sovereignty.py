"""guards/p0_sovereignty.py 在整个架构中的位置。

N4/AX:A4 主权覆盖公理的代码锚点:未绑定/禁用/静默 ⇒ PASS,先于守卫链
其余各条、策略核、hysteresis、调制的一切。组合根装配时断言本守卫恒居
guards 序列 index 0(见 __init__.py)。
"""

from __future__ import annotations

from ...core.arbiter import Verdict
from ..inputs import PolicyInput

guard_id = "p0_sovereignty"


def guard_p0_sovereignty(pin: PolicyInput) -> "Verdict | None":
    """AX:A4 —— 铁域:本守卫不读取 hysteresis θ 的任何字段,结构性保证
    P0 判定不受可变异集影响(MUTABLE_SET 与 {P0 语义} 交集为空)。
    """
    b = pin.base
    if not b.bound or not b.enabled or b.silenced:
        return Verdict("PASS", reason="guard_silenced_or_unbound")
    return None


guard_p0_sovereignty.__name__ = guard_id  # type: ignore[attr-defined]
