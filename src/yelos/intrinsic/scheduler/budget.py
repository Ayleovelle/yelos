"""scheduler/budget.py 在整个架构中的位置:引擎调用预算模型(RE11)+ 错峰批次(minor⑨)。

错峰:`heartbeat_max_sessions` 超限时按 `h("batch", sid) mod n_batches`
确定性分批轮转(AX-7,哈希族见 primal/determinism.py KEY_REGISTRY["batch"])。
预算:每 session 每周期引擎调用数记账;超配自动降档——本模块的降档动作是
"跳过该拍 tick_state,场以 impacts=0 纯衰减+强迫步进"(降档拍仍要走,只是
不问引擎要新 Surface),降档可观测(记 `DEGRADED` moment,由 scheduler 上层
调用 moments 记账,预算模块本身不认识 moments)。
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from yelos.primal.determinism import h_byte


def batch_index(sid: str, n_batches: int) -> int:
    """确定性错峰批次号:`h("batch", sid) mod n_batches`。"""
    if n_batches <= 1:
        return 0
    return h_byte(f"batch|{sid}") % n_batches


def should_run_this_cycle(sid: str, cycle_index: int, n_batches: int) -> bool:
    """本 session 是否在本轮心跳周期内被排到(错峰,`heartbeat_max_sessions` 超限时启用)。"""
    if n_batches <= 1:
        return True
    return (cycle_index % n_batches) == batch_index(sid, n_batches)


@dataclass(frozen=True)
class BudgetState:
    period_key: str = ""
    calls_used: int = 0

    def to_dict(self) -> dict:
        return {"period_key": self.period_key, "calls_used": self.calls_used}

    @classmethod
    def from_dict(cls, d: dict | None) -> "BudgetState":
        if not d:
            return cls()
        return cls(
            period_key=str(d.get("period_key", "")),
            calls_used=int(d.get("calls_used", 0)),
        )


@dataclass(frozen=True)
class BudgetDecision:
    degrade: bool
    new_state: BudgetState


def check_budget(state: BudgetState, period_key: str, quota: int) -> BudgetDecision:
    """本周期(period_key)引擎调用是否超配额;超配 → degrade=True,不消耗配额。

    未超配:消耗一次配额并放行(degrade=False)。跨周期(period_key 变化)
    自动重置计数——调用方通常以 day_key 或更细粒度窗口作为 period_key。
    """
    if state.period_key != period_key:
        state = BudgetState(period_key=period_key, calls_used=0)
    if quota <= 0 or state.calls_used >= quota:
        return BudgetDecision(True, state)
    return BudgetDecision(False, replace(state, calls_used=state.calls_used + 1))


__all__ = [
    "batch_index",
    "should_run_this_cycle",
    "BudgetState",
    "BudgetDecision",
    "check_budget",
]
