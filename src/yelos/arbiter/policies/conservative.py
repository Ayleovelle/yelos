"""policies/conservative.py 在整个架构中的位置。

ConservativePolicy:理论出身 = 证据弃权 + 介入预算,**非**"Table 调高
阈值"。两条独立机制,均非阈值参数化(arbiter_BLUEPRINT §3.3):
1. 证据弃权:Surface 缓存超龄(``surface_age_s > stale_after_s``)⇒ PASS。
2. 当日介入预算耗尽 ⇒ 对 σ>=1 的候选降格 PASS。
预算内、证据新鲜时,内核判定委托 TablePolicy。

诚实自评(蓝图 §11.2 第 1 条,原样保留):本策略的独立实质是弃权+预算
这两条决策原则,不是第三张决策表;若红队判其为"复合策略",维二计数
如实改口"3 套 + 1 复合",架构无需改动。
"""

from __future__ import annotations

from ...core.arbiter import Verdict
from ..inputs import PolicyInput
from ..lattice import sigma_of
from .base import register
from .table import TABLE_POLICY

DEFAULT_STALE_AFTER_S = 600.0
DEFAULT_DAILY_BUDGET = 2


class ConservativePolicy:
    policy_id = "conservative"

    def __init__(
        self,
        stale_after_s: float = DEFAULT_STALE_AFTER_S,
        daily_budget: int = DEFAULT_DAILY_BUDGET,
    ) -> None:
        self.stale_after_s = stale_after_s
        self.daily_budget = daily_budget

    def decide(self, pin: PolicyInput) -> Verdict:
        if pin.surface_age_s > self.stale_after_s:
            return Verdict("PASS", reason="conservative_stale_abstain")
        candidate = TABLE_POLICY.decide(pin)
        if pin.daily_interventions >= self.daily_budget and sigma_of(candidate) >= 1:
            return Verdict("PASS", reason="conservative_budget_exhausted")
        return candidate


CONSERVATIVE_POLICY = register(ConservativePolicy())
