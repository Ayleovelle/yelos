"""guards/self_origin.py 在整个架构中的位置。

防自仲裁守卫:草稿来自她自己(event extra yelos_l0)时直接放行,不叠加
任何策略/hysteresis 判定。冻结内核 core.arbiter.arbitrate 第 2 步的
差分锁抽出件(reason 字符串逐字对齐,T-G2 覆盖)。
"""

from __future__ import annotations

from ...core.arbiter import Verdict
from ..inputs import PolicyInput

guard_id = "self_origin"


def guard_self_origin(pin: PolicyInput) -> "Verdict | None":
    if pin.base.is_self:
        return Verdict("PASS", reason="guard_self")
    return None


guard_self_origin.__name__ = guard_id  # type: ignore[attr-defined]
