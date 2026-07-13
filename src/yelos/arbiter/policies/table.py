"""policies/table.py 在整个架构中的位置。

TablePolicy:默认策略,兼容轨与 golden 基准。直调字节冻结的
``core.arbiter.arbitrate(pin.base)``——零改动、零参数、θ 不生效
(内核阈值硬编码,N2)。T-G1 在 v0.1 迁移用例 + 穷举网格上锁逐字节一致。
"""

from __future__ import annotations

from ...core.arbiter import Verdict, arbitrate
from ..inputs import PolicyInput
from .base import register


class TablePolicy:
    policy_id = "table"

    def decide(self, pin: PolicyInput) -> Verdict:
        return arbitrate(pin.base)


TABLE_POLICY = register(TablePolicy())
