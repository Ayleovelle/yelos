"""guards/engine_guard.py 在整个架构中的位置。

Surface 缺失或引擎自身风控(guard.allowed=False)时放行原文、不叠加。
冻结内核 arbitrate 第 5 步的差分锁抽出件;`sget` 防御式取值,缺省 True
(保守方向:引擎没说不允许,就不额外拦)。
"""

from __future__ import annotations

from ...core import sget
from ...core.arbiter import Verdict
from ..inputs import PolicyInput

guard_id = "engine_guard"


def guard_engine(pin: PolicyInput) -> "Verdict | None":
    b = pin.base
    if b.surface is None or sget(b.surface, "guard.allowed", True) is False:
        return Verdict("PASS", reason="guard_engine_guard")
    return None


guard_engine.__name__ = guard_id  # type: ignore[attr-defined]
