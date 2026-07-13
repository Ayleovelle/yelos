"""rhythm_break.py:检测器三,节奏骤变(蓝图 §6.2 决策表第三行)。

新增检测器(非引擎通道——数据源是 session 记账:交互间隔分布对周基线的
偏离,纯自著)。触发谓词:`last_gap / week 基线 gap 中位 >= th_eff(3.0)`
∧ `当日无交互` ∧ `非 quiet 窗`(quiet 窗内她"睡着"没互动是正常的,不该
被判节奏骤变)。
"""

from __future__ import annotations

from ..contracts import BaselineView, DayContext, RawConcern, ShadowView
from .protocol import TH_BASE

CTYPE = "rhythm_break"
_RATIO_SCALE = 6.0


def detect(
    view: ShadowView, base: dict[str, BaselineView], day_ctx: DayContext
) -> RawConcern | None:
    if day_ctx.in_quiet:
        return None
    if day_ctx.interactions_today > 0:
        return None
    week_gap = day_ctx.week_gap_median
    if week_gap <= 0:
        return None  # 冷启动无基线,保守不判(§5 冷启动纪律)
    th_eff = day_ctx.th_eff.get(CTYPE, TH_BASE[CTYPE])
    ratio = day_ctx.last_gap_seconds / week_gap
    if ratio >= th_eff:
        strength = max(0.0, min(ratio / _RATIO_SCALE, 1.0))
        return RawConcern(ctype=CTYPE, strength=strength, evidence=("gap_ratio",))
    return None


__all__ = ["CTYPE", "detect"]
