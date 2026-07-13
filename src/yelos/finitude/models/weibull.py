"""models/weibull.py 在整个架构中的位置:WeibullWear(id="weibull"),磨损形状学(finitude_BLUEPRINT §3.2)。

参数 k ∈ [1.0, 4.0],默认 1.6。t = active_days_settled + 1(本次为第 t 个活跃日)。
W(t) = min(1, (t/L)^k);base_t = W(t) − W(t−1);spend = min(base_t·(1+0.5·hi), 2·base_t)。

理论出身:Weibull 累积损伤/hazard 形状学——k>1 时 base_t 随 t 递增,**早缓晚急**,
"暮年加速"有显式形状参数。T1:无事件全活跃一生恰在第 L 活跃日归零(Σ base_t = W(L) = 1
当 t 恰好跑满 L 步;数值上 W 的伸缩构造保证 W(L)=1)。k=1 退化为 linear(参数域允许但
默认避开)。可观测签名:同一事件轨迹下,前半生 P 高于 linear、后半生曲线陡降。
"""

from __future__ import annotations

from typing import Any

from .protocol import DayFacts, SettleOutcome

K_MIN = 1.0
K_MAX = 4.0
DEFAULT_K = 1.6
DEFAULT_PARAMS: dict[str, float] = {"k": DEFAULT_K}


def _clamp(value: float, lo: float, hi: float) -> float:
    return lo if value < lo else hi if value > hi else value


def weibull_w(t: float, lifespan: int, k: float) -> float:
    """# [FIN-A2] W(t) = min(1, (t/L)^k):单调不减,W(0)=0,W(L)=1(k>=1 时严格递增到 1)。"""
    if lifespan <= 0:
        return 0.0
    ratio = max(t, 0.0) / lifespan
    if ratio <= 0.0:
        return 0.0
    return min(1.0, ratio**k)


class WeibullWear:
    model_id = "weibull"

    def __init__(self, params: dict[str, Any] | None = None, fast: float = 1.0) -> None:
        self.params = dict(params or {})
        self.fast = fast
        k = self.params.get("k", DEFAULT_K)
        try:
            k = float(k)
        except (TypeError, ValueError):
            k = DEFAULT_K
        self.k = _clamp(k, K_MIN, K_MAX)

    def spend(self, p: float, facts: DayFacts) -> SettleOutcome:
        lifespan = facts.lifespan_active_days
        t = facts.active_days_settled + 1
        w_prev = weibull_w(t - 1, lifespan, self.k)
        w_cur = weibull_w(t, lifespan, self.k)
        base = max(0.0, w_cur - w_prev)
        hi = facts.high_intensity if facts.high_intensity > 0 else 0
        # [FIN-A3]-like 事件项(本模型仅用 hi,称重公理正身在 EventWeighted)
        raw = base * (1.0 + 0.5 * hi)
        cap = 2.0 * base
        spend_amt = min(raw, cap) if raw > cap else raw
        spend_amt = max(0.0, spend_amt)
        new_p = max(0.0, p - spend_amt)
        return SettleOutcome(new_p=new_p, fast_pool=None, extras={})


__all__ = ["WeibullWear", "DEFAULT_PARAMS", "weibull_w", "K_MIN", "K_MAX", "DEFAULT_K"]
