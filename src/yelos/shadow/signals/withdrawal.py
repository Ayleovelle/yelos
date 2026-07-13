"""withdrawal.py:检测器四,退缩模式(蓝图 §6.2 决策表第四行)。

新增检测器(多通道联合慢模式,月参照——不同时间尺度的关切有不同参照系,
§5"为什么是族而不是一个数")。三条证据,至少满足两条才判定:

1. `warmth < month 基线 - th_eff(0.2)`
2. `interactions 7 日均 < 月均 × 0.5`
3. `msg_len_ewma < 月均 × 0.6`

strength = 满足条数/3 × 各已满足条的通道偏离均值(偏离越大越强,但受"至少
两条"的门槛先行把关,不会因单条极端偏离就误判整体退缁)。
"""

from __future__ import annotations

from ..contracts import BaselineView, DayContext, RawConcern, ShadowView
from .protocol import TH_BASE

CTYPE = "withdrawal"
_MIN_CONDITIONS = 2
_INTERACTIONS_RATIO = 0.5
_MSG_LEN_RATIO = 0.6


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def detect(
    view: ShadowView, base: dict[str, BaselineView], day_ctx: DayContext
) -> RawConcern | None:
    th_eff = day_ctx.th_eff.get(CTYPE, TH_BASE[CTYPE])
    warmth_base = base.get("warmth")

    satisfied: list[str] = []
    deviations: list[float] = []

    if (
        view.warmth is not None
        and warmth_base is not None
        and warmth_base.month is not None
        and view.warmth < warmth_base.month - th_eff
    ):
        satisfied.append("warmth_month")
        deviations.append(
            _clamp01((warmth_base.month - view.warmth) / max(1e-9, th_eff))
        )

    interactions_th = day_ctx.interactions_month_avg * _INTERACTIONS_RATIO
    if (
        day_ctx.interactions_month_avg > 0
        and day_ctx.interactions_7d_avg < interactions_th
    ):
        satisfied.append("interactions_7d")
        deviations.append(
            _clamp01(1.0 - day_ctx.interactions_7d_avg / max(1e-9, interactions_th))
        )

    msg_len_th = day_ctx.msg_len_month_avg * _MSG_LEN_RATIO
    if day_ctx.msg_len_month_avg > 0 and day_ctx.msg_len_ewma < msg_len_th:
        satisfied.append("msg_len")
        deviations.append(_clamp01(1.0 - day_ctx.msg_len_ewma / max(1e-9, msg_len_th)))

    if len(satisfied) < _MIN_CONDITIONS:
        return None
    dev_mean = sum(deviations) / len(deviations) if deviations else 0.0
    strength = _clamp01((len(satisfied) / 3.0) * dev_mean)
    return RawConcern(ctype=CTYPE, strength=strength, evidence=tuple(satisfied))


__all__ = ["CTYPE", "detect"]
