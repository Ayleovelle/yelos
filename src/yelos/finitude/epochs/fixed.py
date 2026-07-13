"""epochs/fixed.py 在整个架构中的位置:A 轨——固定边界纪元(finitude_BLUEPRINT §4.1,默认/兼容)。

收编 `core.finitude.epoch` / `core.finitude.epoch_transition` 的语义(委托调用,不复制
公式)。输入恒为**契约 P**。P>0.6 盛年 | >0.3 慢下来 | >0.15 安静 | >0 静止前期 | ==0 静止。
"""

from __future__ import annotations

from yelos.core.finitude import epoch as _epoch
from yelos.core.finitude import epoch_transition as _epoch_transition

EPOCH_NAMES: tuple[str, ...] = ("盛年", "慢下来", "安静", "静止前期", "静止")


def epoch_of(p: float) -> str:
    """契约 P → A 轨纪元名(委托 core.finitude.epoch,零改公式)。"""
    return _epoch(p)


def epoch_index(p: float) -> int:
    """A 轨纪元名 → 序号(0..4,盛年→静止),供与 B 轨 b_index 比较/钳制。"""
    return EPOCH_NAMES.index(_epoch(p))


def transition(old_p: float, new_p: float) -> str | None:
    """跨档时返回新纪元名,否则 None(委托 core.finitude.epoch_transition)。"""
    return _epoch_transition(old_p, new_p)


__all__ = ["EPOCH_NAMES", "epoch_of", "epoch_index", "transition"]
