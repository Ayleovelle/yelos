"""warmth_drop.py:检测器一,暖度跌幅(蓝图 §6.2 决策表第一行)。

收编 v0.1 F11a 语义(core/shadow.py `_WARMTH_DROP_TH`/`_WARMTH_ABS_FLOOR`)+
基线族增强:v0.1 用"日首拍单点"当参照,这里用 day 窗基线(可能已是 EWMA,
day_ticks>3 时),阈值改用 `th_eff = th_base + beta_c`(SHTOM-A7 敏感化)。

触发谓词:`base.day - warmth >= th_eff` 且 `warmth < 0.45`(绝对下限,红队
F11a——从 0.9 掉到 0.6 仍是暖、不该心疼,压掉首拍峰值采样的系统性误报)。
"""

from __future__ import annotations

from ..contracts import BaselineView, DayContext, RawConcern, ShadowView
from .protocol import TH_BASE

CTYPE = "warmth_drop"
_ABS_FLOOR = 0.45
_DROP_SCALE = 0.5


def detect(
    view: ShadowView, base: dict[str, BaselineView], day_ctx: DayContext
) -> RawConcern | None:
    warmth = view.warmth
    baseline = base.get("warmth")
    if warmth is None or baseline is None or baseline.day is None:
        return None
    th_eff = day_ctx.th_eff.get(CTYPE, TH_BASE[CTYPE])
    drop = baseline.day - warmth
    if drop >= th_eff and warmth < _ABS_FLOOR:
        strength = max(0.0, min(drop / _DROP_SCALE, 1.0))
        return RawConcern(
            ctype=CTYPE, strength=strength, evidence=("day_drop", "abs_floor")
        )
    return None


__all__ = ["CTYPE", "detect"]
