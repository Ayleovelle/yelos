"""models/protocol.py 在整个架构中的位置:老化模型族的公共协议(finitude_BLUEPRINT §3.0)。

`DayFacts` 是 dayfacts.py 的产出,`AgingModel` 是四个模型(linear/weibull/event/
reserve)共同实现的 Protocol,`SettleOutcome` 是 spend() 的返回值,统一经
`gate.settle_through_gate` [FIN-A1] 收口。本文件不含任何模型的具体公式
(公式各自在 models/{linear,weibull,event_weighted,reserve}.py)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, Protocol, runtime_checkable


@dataclass(frozen=True)
class DayFacts:
    """被结算日的事实快照(§3.0)。全部字段只读,由 dayfacts.extract_dayfacts 产出。"""

    day: str  # 被结算日(昨日 day_key)
    was_active_day: bool  # daily.interacted or daily.active_seen
    high_intensity: int  # 钳 >=0
    concern_fired: int  # 权威源 shadow.daily.concern_count,回退 legacy concern_state
    swallowed: int  # 当日 daily.swallowed
    proactive_sent: int
    epoch_shift_yesterday: (
        bool  # milestones 末条 day == 被结算日(见 dayfacts.py 头注疑义)
    )
    active_days_settled: int  # record.aging.active_days_settled(结算前值,本世累计)
    lifespan_active_days: int


@dataclass(frozen=True)
class SettleOutcome:
    """一次 spend() 的产出;`new_p` 是契约 P 候选(闸前,gate 会再钳一次)。"""

    new_p: float
    fast_pool: float | None = None  # ReserveModel 快池新值;其余模型恒 None
    extras: dict[str, float] = field(
        default_factory=dict
    )  # 随 settle 行落 ledger 的附加字段


@runtime_checkable
class AgingModel(Protocol):
    """四模型共同实现的协议;`model_id` 用于 MODEL_REGISTRY 键与 hatch 冻结记账。"""

    model_id: ClassVar[str]

    def spend(self, p: float, facts: DayFacts) -> SettleOutcome:
        """给定当前契约 P 与当日事实,给出结算候选(未经 gate 钳制)。"""
        ...


__all__ = ["DayFacts", "SettleOutcome", "AgingModel"]
