"""guards 子包在整个架构中的位置:前置守卫链 + 唯一后置滤波的成员表。

供组合根(``arbiter/__init__.py``)按固定顺序装配;顺序与冻结内核
``core.arbiter.arbitrate`` 的前置守卫顺序逐字对齐(T-G2 差分测试锁)。
"""

from __future__ import annotations

from .base import (
    Guard,
    PostFilter,
    assert_guards_pass_only,
    assert_post_filters_downgrade_only,
)
from .chain_shape import guard_chain_shape
from .engine_guard import guard_engine
from .min_gap import guard_min_gap
from .p0_sovereignty import guard_p0_sovereignty
from .post_mod_gate import post_mod_gate
from .self_origin import guard_self_origin

# 固定顺序:P0 恒 index 0(A4)。
GUARD_CHAIN: tuple[Guard, ...] = (
    guard_p0_sovereignty,
    guard_self_origin,
    guard_chain_shape,
    guard_engine,
    guard_min_gap,
)

POST_FILTERS: tuple[PostFilter, ...] = (post_mod_gate,)

__all__ = [
    "Guard",
    "PostFilter",
    "GUARD_CHAIN",
    "POST_FILTERS",
    "assert_guards_pass_only",
    "assert_post_filters_downgrade_only",
    "guard_p0_sovereignty",
    "guard_self_origin",
    "guard_chain_shape",
    "guard_engine",
    "guard_min_gap",
    "post_mod_gate",
]
