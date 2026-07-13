"""models/linear.py 在整个架构中的位置:LinearDecay(id="linear"),v0.1 兼容轨(finitude_BLUEPRINT §3.1)。

W(t) = t/L(匀速磨损);E = 1 + 0.5·hi,cap 2×base。**实现委托** `core.finitude.settle_day`
——同一策略的同一公式,不是双实现充数(维二反换皮铁条):默认策略与 v0.1 逐字节一致是
兼容义务,由 golden 锁死(`tests/finitude/test_compat_v01.py::test_linear_bytewise_settle_day`)。

理论出身:日历均匀损耗(v0.1 原生)。可观测签名:P 曲线是等斜率折线(仅活跃日下折)。
# [FIN-A2] W(t)=t/L 是本模型的耗散形状(常数斜率),E=1+0.5*hi 是本模型的事件称重(委托)。
"""

from __future__ import annotations

from typing import Any

from yelos.core.finitude import settle_day

from .protocol import DayFacts, SettleOutcome

DEFAULT_PARAMS: dict[str, float] = {}


class LinearDecay:
    model_id = "linear"

    def __init__(self, params: dict[str, Any] | None = None, fast: float = 1.0) -> None:
        self.params = dict(params or {})
        self.fast = fast  # 未使用(非 reserve 模型),保留统一构造签名

    def spend(self, p: float, facts: DayFacts) -> SettleOutcome:
        new_p = settle_day(
            p,
            was_active_day=facts.was_active_day,
            high_intensity_events=facts.high_intensity,
            lifespan_active_days=facts.lifespan_active_days,
        )
        return SettleOutcome(new_p=new_p, fast_pool=None, extras={})


__all__ = ["LinearDecay", "DEFAULT_PARAMS"]
