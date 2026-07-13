"""dreamwork/dream_state.py 在整个架构中的位置:梦累积/武装/投递状态机(§4.1)。

`pending` 单一权威(v0.1 §5.3)不变——收编 `core.intrinsic.dream_tick` /
`dream_ready` 原语义,状态机显式化。夜间每拍(quiet 窗内)场照常步进并
采样入 `night_phi_trace`(环形缓冲,调用方维护,上限 480 拍);离开 quiet
窗且当晚 dream_tick 计数 ≥2 → 武装:调 generator 产 residue、pending=True、
count 清零。投递时把 residue 交给 primal 的 dream_murmur 渲染(W-2 接线点,
本文件不触碰 primal)。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from yelos.core.intrinsic import dream_ready as _core_dream_ready
from yelos.core.intrinsic import dream_tick as _core_dream_tick

from ..field.state import FieldState
from ..moments.taxonomy import MomentEntry
from .residue import DreamResidue

DREAM_TICK_ARM_THRESHOLD = 2
NIGHT_TRACE_CAP = 480


@dataclass(frozen=True)
class DreamState:
    count: int = 0
    night_of: str | None = None
    pending: bool = False
    delivered_today: bool = False
    residue: DreamResidue | None = None

    def to_dict(self) -> dict:
        return {
            "count": self.count,
            "night_of": self.night_of,
            "pending": self.pending,
            "delivered_today": self.delivered_today,
            "residue": self.residue.to_dict() if self.residue is not None else None,
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "DreamState":
        if not d:
            return cls()
        return cls(
            count=int(d.get("count", 0)),
            night_of=d.get("night_of"),
            pending=bool(d.get("pending", False)),
            delivered_today=bool(d.get("delivered_today", False)),
            residue=DreamResidue.from_dict(d.get("residue")),
        )


class DreamGenerator(Protocol):
    name: str

    def generate(
        self,
        night_phi_trace: list[FieldState],
        day_moments: list[MomentEntry],
        l2_keywords: tuple[str, ...],
        hash_seed: str,
    ) -> DreamResidue: ...


def tick(state: DreamState, surface: dict | None, in_quiet_hours: bool) -> DreamState:
    """[dream_tick 语义收编] 本拍是否计一次"夜间越表达阈";命中则计数+1。"""
    hit = _core_dream_tick(surface, in_quiet_hours)
    if hit:
        return replace(state, count=state.count + 1)
    return state


def push_trace(trace: list[FieldState], phi: FieldState) -> list[FieldState]:
    """环形缓冲追加(上限 NIGHT_TRACE_CAP 拍);调用方持有 trace 列表本身。"""
    out = list(trace) + [phi]
    if len(out) > NIGHT_TRACE_CAP:
        out = out[-NIGHT_TRACE_CAP:]
    return out


def arm(
    state: DreamState,
    day_key: str,
    night_phi_trace: list[FieldState],
    day_moments: list[MomentEntry],
    l2_keywords: tuple[str, ...],
    generator: DreamGenerator,
    hash_seed: str,
) -> DreamState:
    """离开 quiet 窗时调用:计数达阈 → 武装(产 residue、pending=True、count 清零)。

    未达阈:当晚计数清零(新夜从零开始),其余字段不变。
    """
    if state.count >= DREAM_TICK_ARM_THRESHOLD:
        residue = generator.generate(
            night_phi_trace, day_moments, l2_keywords, hash_seed
        )
        return replace(state, count=0, night_of=day_key, pending=True, residue=residue)
    return replace(state, count=0)


def ready(state: DreamState, p: float, enabled: bool) -> bool:
    """投递判定:pending 单一权威(v0.1 §5.3 原语义不变)。"""
    return _core_dream_ready(state.pending, p, enabled, state.delivered_today)


def deliver(state: DreamState) -> DreamState:
    """投递后:delivered_today=True,pending 消费清零,residue 清空(防重投)。"""
    return replace(state, pending=False, delivered_today=True, residue=None)


def rollover_day(state: DreamState) -> DreamState:
    """日翻转:delivered_today 重置(intrinsic_field.dream 收编了此字段的所有权,
    §6.4/INTEGRATION_SPEC §2.1——不再依赖 binding.daily 的旧重置路径)。
    """
    return replace(state, delivered_today=False)


__all__ = [
    "DreamState",
    "DreamGenerator",
    "DREAM_TICK_ARM_THRESHOLD",
    "NIGHT_TRACE_CAP",
    "tick",
    "push_trace",
    "arm",
    "ready",
    "deliver",
    "rollover_day",
]
