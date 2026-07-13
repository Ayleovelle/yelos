"""models/event_weighted.py 在整个架构中的位置:EventWeighted(id="event"),事件称重的岁月

(finitude_BLUEPRINT §3.3)。W(t) = t/L 仅作尺度;
E = min(α0 + w_hi·hi + w_cn·concern_fired + w_ep·[epoch_shift_yesterday], 2)。
默认权重谱:α0=0.25(平静活跃日只老四分之一),w_hi=0.5,w_cn=0.35,w_ep=0.4。
spend = base·E,base = 1/L,cap 由 E 的 min(·,2) 内建。

理论出身:岁月由事件称重,不由日历称重——重咽的日子、被心疼刺穿的日子、跨纪元的日子
各有权重谱。T1 签名:无事件一生 P(L) = 1 − α0 = 0.75 > 0——**平静的陪伴活得比寿数长**,
这是该模型独有的可观测行为(不是参数档,是语义差)。
"""

from __future__ import annotations

from typing import Any

from .protocol import DayFacts, SettleOutcome

DEFAULT_ALPHA0 = 0.25
DEFAULT_W_HI = 0.5
DEFAULT_W_CN = 0.35
DEFAULT_W_EP = 0.4
DEFAULT_PARAMS: dict[str, float] = {
    "alpha0": DEFAULT_ALPHA0,
    "w_hi": DEFAULT_W_HI,
    "w_cn": DEFAULT_W_CN,
    "w_ep": DEFAULT_W_EP,
}


class EventWeighted:
    model_id = "event"

    def __init__(self, params: dict[str, Any] | None = None, fast: float = 1.0) -> None:
        self.params = dict(params or {})
        self.fast = fast

    def _weight(self, key: str, default: float) -> float:
        value = self.params.get(key, default)
        try:
            value = float(value)
        except (TypeError, ValueError):
            return default
        return value if value >= 0.0 else default

    def spend(self, p: float, facts: DayFacts) -> SettleOutcome:
        lifespan = facts.lifespan_active_days
        base = 1.0 / lifespan if lifespan > 0 else 0.0  # [FIN-A2] W(t)=t/L 仅作尺度
        alpha0 = self._weight("alpha0", DEFAULT_ALPHA0)
        w_hi = self._weight("w_hi", DEFAULT_W_HI)
        w_cn = self._weight("w_cn", DEFAULT_W_CN)
        w_ep = self._weight("w_ep", DEFAULT_W_EP)

        hi = facts.high_intensity if facts.high_intensity > 0 else 0
        concern = facts.concern_fired if facts.concern_fired > 0 else 0
        ep = 1.0 if facts.epoch_shift_yesterday else 0.0

        # [FIN-A3] 事件可称重公理:e 越大 E 越不减(封顶前);hi/concern/ep 各自单调加权。
        e_raw = alpha0 + w_hi * hi + w_cn * concern + w_ep * ep
        e = min(max(e_raw, 0.0), 2.0)

        spend_amt = base * e
        new_p = max(0.0, p - spend_amt)
        return SettleOutcome(new_p=new_p, fast_pool=None, extras={})


__all__ = ["EventWeighted", "DEFAULT_PARAMS"]
