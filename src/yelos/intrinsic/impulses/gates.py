"""impulses/gates.py 在整个架构中的位置:公共硬闸链([AX-6],三策略共用)。

`GATE_CHAIN` 是组合根外不可改的元组常量(裁决顺序 = v0.1 `core.intrinsic.decide`
步骤 0/2-9 逐条同构,intrinsic_BLUEPRINT §2.2)。`apply_gates` 把任一策略的
`PolicyProposal` 与闸门输入 `GateInput` 一起裁决,返回与 v0.1 完全同形的
`IntrinsicDecision(send, occasion, reason)`。

任一策略的 want=True 必须过全链——策略配置不能绕开任何一道闸(AX-6)。
每次拒绝的 `reason` 是 moments 记账表(§2.2/§5.1)的键,scheduler 层负责
把 reason → MomentKind(gates.py 本身不依赖 moments 包,维持依赖无环:
impulses → field/circadian 而非 moments)。
"""

from __future__ import annotations

from dataclasses import dataclass

from yelos.core import sget
from yelos.core.intrinsic import IntrinsicDecision

from .policy import PolicyProposal

# 闸链顺序常量(AX-6,组合根外不可改;与 §2.2 决策表逐行对应)。
GATE_CHAIN: tuple[str, ...] = (
    "p0",
    "trigger",
    "engine_field_gate",
    "phase_dormant",
    "guard_frozen",
    "unanswered",
    "daily_cap",
    "min_gap",
    "quiet_hours",
    "night_occasion",
)

# 与 core.intrinsic 逐字一致的常量(§0.3:v0.1 契约不动产,闸值不可漂移)。
_MIN_PROACTIVE_GAP_SECONDS = 2 * 3600
_NIGHT_WINDOW_MINUTES = 30
_UNANSWERED_STREAK_CAP = 2


@dataclass(frozen=True)
class GateInput:
    """v0.1 `IntrinsicInput` 的闸门子集,字段一一对应(§2.2)。"""

    surface: dict | None
    p: float
    enabled: bool
    silenced: bool
    sealed: bool
    guard_frozen_today: bool
    now_local_minutes: int
    quiet_start_min: int
    quiet_end_min: int
    daily_cap_base: int
    sent_today: int
    last_proactive_ts: float
    now_ts: float
    unanswered_streak: int
    contact_night_sent_today: bool
    phase: str


def _in_interval(now: int, start: int, end: int) -> bool:
    """与 core.intrinsic._in_interval 逐字同构(跨零点区间判定)。"""
    start %= 1440
    end %= 1440
    if start == end:
        return False
    if start < end:
        return start <= now < end
    return now >= start or now < end


def _daily_cap(daily_cap_base: int, p: float) -> int:
    import math

    if p <= 0.0 or daily_cap_base <= 0:
        return 0
    return math.ceil(daily_cap_base * p)


def apply_gates(proposal: PolicyProposal, g: GateInput) -> IntrinsicDecision:
    """公共硬闸链(AX-6);顺序与 `GATE_CHAIN` 一致,逐条同构 v0.1 decide()。"""
    # --- 0. P0 前置 ------------------------------------------------------
    if g.sealed or g.silenced or not g.enabled:
        return IntrinsicDecision(False, reason="p0")

    # --- 1. 触发(策略已提议;此处只看 want)--------------------------------
    if not proposal.want:
        return IntrinsicDecision(False, reason="no_trigger")

    s = g.surface
    pressure = sget(s, "state.boundary.pressure", 0.0)
    quiet = sget(s, "state.needs.quiet", 0.0)
    budget = sget(s, "state.boundary.interruption_budget", 1.0)

    # --- 2. 引擎场闸 -------------------------------------------------------
    if pressure >= 0.7:
        return IntrinsicDecision(False, reason="pressure")
    if quiet >= 0.5:
        return IntrinsicDecision(False, reason="quiet_need")
    if budget < 0.3:
        return IntrinsicDecision(False, reason="budget")

    # --- 3. 关系相 dormant --------------------------------------------------
    if g.phase == "dormant":
        return IntrinsicDecision(False, reason="dormant")

    # --- 4. guard 冻结 -------------------------------------------------------
    if g.guard_frozen_today:
        return IntrinsicDecision(False, reason="guard_frozen")

    # --- 5. 未回应 ---------------------------------------------------------
    if g.unanswered_streak >= _UNANSWERED_STREAK_CAP:
        return IntrinsicDecision(False, reason="unanswered")

    # --- 6. 日配额 ---------------------------------------------------------
    cap = _daily_cap(g.daily_cap_base, g.p)
    if g.sent_today >= cap:
        return IntrinsicDecision(False, reason="daily_cap")

    # --- 7. 最小间隔 -------------------------------------------------------
    if g.now_ts - g.last_proactive_ts < _MIN_PROACTIVE_GAP_SECONDS:
        return IntrinsicDecision(False, reason="min_gap")

    # --- 8. quiet 硬窗(主权语义,恒最后否决)--------------------------------
    if _in_interval(g.now_local_minutes, g.quiet_start_min, g.quiet_end_min):
        return IntrinsicDecision(False, reason="quiet_hours")

    # --- 9. 夜窗 occasion ---------------------------------------------------
    night_start = (g.quiet_start_min - _NIGHT_WINDOW_MINUTES) % 1440
    in_night_window = _in_interval(g.now_local_minutes, night_start, g.quiet_start_min)
    if in_night_window:
        if g.contact_night_sent_today:
            return IntrinsicDecision(False, reason="night_done")
        return IntrinsicDecision(True, occasion="contact_night", reason="night")
    return IntrinsicDecision(True, occasion="contact_seek", reason="seek")


__all__ = ["GATE_CHAIN", "GateInput", "apply_gates"]
