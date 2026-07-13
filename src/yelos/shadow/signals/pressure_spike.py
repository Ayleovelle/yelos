"""pressure_spike.py:检测器二,压力尖峰(蓝图 §6.2 决策表第二行)。

收编 v0.1 pressure 触发 + 新增短窗斜率支;v0.1 的 `damage_open>=0.5` 触发
并入本家族(evidence 带 `damage` 标签,§6.2 明文"damage 并入 pressure_spike
家族",供 `legacy_compat.LegacyDetector` 走原路兼容)。

触发谓词:`pressure >= th_eff` ∨ (`短窗斜率 >= 0.15` ∧ `pressure >= 0.5`)
∨ `damage_open >= 0.5`(v0.1 谱系并入)。strength 取三路 ratio 的 max。
"""

from __future__ import annotations

from ..contracts import BaselineView, DayContext, RawConcern, ShadowView
from .protocol import TH_BASE

CTYPE = "pressure_spike"
_SLOPE_TH = 0.15
_SLOPE_GUARD_PRESSURE = 0.5
_SLOPE_SCALE = 0.3
_DAMAGE_TH = 0.5


def detect(
    view: ShadowView, base: dict[str, BaselineView], day_ctx: DayContext
) -> RawConcern | None:
    pressure = view.pressure
    damage = view.damage
    th_eff = day_ctx.th_eff.get(CTYPE, TH_BASE[CTYPE])
    evidence: list[str] = []
    ratios: list[float] = []

    if pressure is not None and pressure >= th_eff:
        evidence.append("pressure_level")
        ratios.append(max(0.0, (pressure - th_eff) / max(1e-9, 1.0 - th_eff)))

    if (
        pressure is not None
        and pressure >= _SLOPE_GUARD_PRESSURE
        and day_ctx.pressure_slope >= _SLOPE_TH
    ):
        evidence.append("pressure_slope")
        ratios.append(min(day_ctx.pressure_slope / _SLOPE_SCALE, 1.0))

    if damage is not None and damage >= _DAMAGE_TH:
        evidence.append("damage")
        ratios.append(max(0.0, (damage - _DAMAGE_TH) / (1.0 - _DAMAGE_TH)))

    if not ratios:
        return None
    strength = max(0.0, min(max(ratios), 1.0))
    return RawConcern(ctype=CTYPE, strength=strength, evidence=tuple(evidence))


__all__ = ["CTYPE", "detect"]
