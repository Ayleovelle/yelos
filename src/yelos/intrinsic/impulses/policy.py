"""impulses/policy.py 在整个架构中的位置:策略协议 + 上下文/提议数据类(维二契约)。

`ProactivePolicy.propose(ctx) -> PolicyProposal` 只提议 want/intensity/trace,
不做闸门裁决——裁决全部收口在 gates.py([AX-6])。三套策略实现见
threshold.py / field_crossing.py / poisson_budget.py。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..field.state import FieldState


@dataclass(frozen=True)
class PolicyContext:
    """策略提议所需的全部只读上下文;`policy_state` 是策略私有持久态(binding)。"""

    phi: FieldState
    surface: dict | None
    p: float
    now_ts: float
    now_local_minutes: int
    day_key: str
    sent_today: int
    last_proactive_ts: float
    unanswered_streak: int
    reach_out_cached: bool
    phase: str
    policy_state: dict = field(default_factory=dict)
    sid: str = ""
    tick_index: int = 0


@dataclass(frozen=True)
class PolicyProposal:
    """策略输出:是否想主动 + 触发轨迹(供 moments/viz 记账,对标 arbiter.explain)。"""

    want: bool
    intensity: float = 0.0
    trace: dict = field(default_factory=dict)
    new_policy_state: dict = field(default_factory=dict)


class ProactivePolicy(Protocol):
    name: str

    def propose(self, ctx: PolicyContext) -> PolicyProposal: ...


__all__ = ["PolicyContext", "PolicyProposal", "ProactivePolicy"]
