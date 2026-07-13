"""guards/chain_shape.py 在整个架构中的位置。

链形状守卫:空链/无 Plain 文本 ⇒ PASS;链含非 Plain 组件(issue26,防吞掉
多模态消息)⇒ PASS。冻结内核 arbitrate 第 3/4 步的差分锁抽出件。
"""

from __future__ import annotations

from ...core.arbiter import Verdict
from ..inputs import PolicyInput

guard_id = "chain_shape"


def guard_chain_shape(pin: PolicyInput) -> "Verdict | None":
    b = pin.base
    if not b.has_plain or not b.draft.strip():
        return Verdict("PASS", reason="guard_no_plain")
    if b.has_non_plain:
        return Verdict("PASS", reason="guard_non_plain")
    return None


guard_chain_shape.__name__ = guard_id  # type: ignore[attr-defined]
