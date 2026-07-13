"""impulses/threshold.py 在整个架构中的位置:v0.1 兼容默认策略(维二 1/3)。

**出身**:v0.1 决策表(瞬时阈值合取)。`propose.want = (contact≥0.6 ∧
expression≥0.45) ∨ reach_out`。**无记忆**(不读 φ 历史,只读当拍 Surface)。

**零改动包装**(intrinsic_BLUEPRINT §0.3):真正调用 `core.intrinsic.decide`
本体来判定触发,而不是把 0.6/0.45 阈值在本文件里重复一份——单一事实源
仍是 core/intrinsic.py。做法:用**全通行**的闸门值(P0 打开、quiet 窗设为
空区间、cap/gap/unanswered 全部放行)构造一个 `IntrinsicInput`,decide()
在这套输入下的 send/no_trigger 结果只可能由触发条件本身决定——借此把
"触发段"从 decide() 里干净地抽出来复用,不重复维护阈值常量。真实闸门由
`gates.py::apply_gates`(AX-6)在下游统一裁决,本策略的 want 只是提议。
"""

from __future__ import annotations

from yelos.core import sget
from yelos.core.intrinsic import IntrinsicInput, decide

from .policy import PolicyContext, PolicyProposal

name = "threshold"

_PERMISSIVE_KWARGS = dict(
    silenced=False,
    sealed=False,
    guard_frozen_today=False,
    quiet_start_min=0,
    quiet_end_min=0,  # start==end → 空区间,quiet_hours 恒不命中(core._in_interval 语义)
    daily_cap_base=10_000,
    sent_today=0,
    last_proactive_ts=-1.0e18,  # 保证 now_ts - last >= min_gap
    unanswered_streak=0,
    contact_night_sent_today=False,
)


class ThresholdPolicy:
    name = "threshold"

    def propose(self, ctx: PolicyContext) -> PolicyProposal:
        contact = sget(ctx.surface, "state.needs.contact", 0.0)
        expression = sget(ctx.surface, "state.needs.expression", 0.0)
        action = sget(ctx.surface, "decision.action", "hold")
        # 探针 Surface:只保留触发段真正读取的字段(contact/expression/action),
        # 引擎场闸字段(pressure/quiet/budget)一并中性化——这几个字段与触发
        # 字段同源于 ctx.surface,若直接透传会让 decide() 内部的闸门步骤
        # (§5.2 步 2)提前介入,污染"只测触发"的探针语义;真实闸门仍在
        # gates.py::apply_gates 统一裁决(下游,AX-6),不受此探针影响。
        probe_surface = {
            "state": {
                "needs": {"contact": contact, "expression": expression, "quiet": 0.0},
                "boundary": {"pressure": 0.0, "interruption_budget": 1.0},
            },
            "decision": {"action": action},
        }
        probe = IntrinsicInput(
            session_id="",
            day_key=ctx.day_key,
            surface=probe_surface,
            p=1.0,
            enabled=True,
            now_local_minutes=0,
            now_ts=0.0,
            phase="active",  # dormant 判定不属于"触发",探针恒非 dormant
            reach_out_cached=ctx.reach_out_cached,
            **_PERMISSIVE_KWARGS,
        )
        decision = decide(probe)
        want = bool(decision.send)

        trace = {
            "policy": self.name,
            "contact": contact,
            "expression": expression,
            "reach_out": ctx.reach_out_cached,
            "contact_margin": contact - 0.6,
            "expression_margin": expression - 0.45,
            "core_reason": decision.reason,
        }
        return PolicyProposal(want=want, intensity=1.0 if want else 0.0, trace=trace)


__all__ = ["ThresholdPolicy"]
