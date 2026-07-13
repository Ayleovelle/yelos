"""moments/taxonomy.py 在整个架构中的位置:MomentKind 枚举 + schema(维一自著)。

无自由文本,只放 reason code / 封闭键(§5.1)。`REASON_TO_MOMENT` 是闸链
reason(gates.py §2.2 表)→ MomentKind 的映射表——记账义务的正身在此,
gates.py 本身不产出 MomentKind(依赖无环:impulses 不依赖 moments)。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from yelos.core.intrinsic import IntrinsicDecision


class MomentKind(StrEnum):
    SPOKE = "spoke"  # 想说且说了(对照组,含 occasion)
    WANT_BLOCKED_BUDGET = "want_blocked_budget"  # 想主动,日配额不够
    WANT_BLOCKED_GAP = "want_blocked_gap"  # 想主动,min_gap 未到
    WANT_BLOCKED_QUIET = "want_blocked_quiet"  # 想主动,quiet 硬窗/夜窗拦下
    WANT_BLOCKED_RESPECT = "want_blocked_respect"  # 想主动,连续未回应而识趣
    CROSSED_BUT_GATED = "crossed_but_gated"  # 场越面,被引擎场闸/dormant/guard 拦
    WANT_EXPIRED = "want_expired"  # 入了 outbox 但过期未被取走(补句过期)
    DREAM_ARMED = "dream_armed"
    DREAM_DELIVERED = "dream_delivered"
    DEGRADED = "degraded"  # scheduler 预算降档拍(RE11 可观测)


# 闸链 reason → MomentKind(§2.2 决策表;None = 不记账,她"不想"或未触发)。
REASON_TO_MOMENT: dict[str, MomentKind | None] = {
    "p0": None,
    "no_trigger": None,
    "pressure": MomentKind.CROSSED_BUT_GATED,
    "quiet_need": MomentKind.CROSSED_BUT_GATED,
    "budget": MomentKind.CROSSED_BUT_GATED,
    "dormant": MomentKind.CROSSED_BUT_GATED,
    "guard_frozen": MomentKind.CROSSED_BUT_GATED,
    "unanswered": MomentKind.WANT_BLOCKED_RESPECT,
    "daily_cap": MomentKind.WANT_BLOCKED_BUDGET,
    "min_gap": MomentKind.WANT_BLOCKED_GAP,
    "quiet_hours": MomentKind.WANT_BLOCKED_QUIET,
    "night_done": MomentKind.WANT_BLOCKED_QUIET,
}


def moment_kind_for_decision(decision: IntrinsicDecision) -> MomentKind | None:
    """`apply_gates` 的裁决结果 → 记账义务(scheduler 消费,§2.2/§5.1)。"""
    if decision.send:
        return MomentKind.SPOKE
    return REASON_TO_MOMENT.get(decision.reason)


@dataclass(frozen=True)
class MomentEntry:
    ts: float
    day_key: str
    kind: MomentKind
    reason_code: str
    phi: tuple[float, float, float, float]
    trace_hash: str
    occasion_hint: str | None = None

    def to_dict(self) -> dict:
        return {
            "ts": self.ts,
            "day_key": self.day_key,
            "kind": str(self.kind),
            "reason_code": self.reason_code,
            "phi": list(self.phi),
            "trace_hash": self.trace_hash,
            "occasion_hint": self.occasion_hint,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MomentEntry":
        phi = d.get("phi", [0.0, 0.0, 0.0, 0.0])
        return cls(
            ts=float(d.get("ts", 0.0)),
            day_key=str(d.get("day_key", "")),
            kind=MomentKind(d.get("kind", MomentKind.CROSSED_BUT_GATED.value)),
            reason_code=str(d.get("reason_code", "")),
            phi=tuple(float(x) for x in phi),  # type: ignore[assignment]
            trace_hash=str(d.get("trace_hash", "")),
            occasion_hint=d.get("occasion_hint"),
        )


__all__ = ["MomentKind", "REASON_TO_MOMENT", "moment_kind_for_decision", "MomentEntry"]
