"""field/integrators.py 在整个架构中的位置:两套数值积分器(维一,明示不计维二)。

`Integrator` 协议 + `EulerIntegrator`(默认,一阶显式)/ `TrapezoidIntegrator`
(二阶,梯形法/改进 Euler)。数值实现选择——蓝图 §2.2 明文:数值方案不计
维二策略数,维二正身是 impulses/ 三套主动策略。

两者都在最后一步调用 `FieldState.clipped()`([AX-1]);步长 Δ 由调用方
(scheduler)传入,可为心跳周期或内联补算的子块 dt(AX-8)。
"""

from __future__ import annotations

from typing import Protocol

from .dynamics import derivative
from .state import FieldParams, FieldState, Vec4


class Integrator(Protocol):
    name: str

    def step(
        self,
        phi: FieldState,
        dt: float,
        forcing: Vec4,
        impacts: Vec4,
        params: FieldParams,
    ) -> FieldState: ...


def _add(a: Vec4, b: Vec4, scale: float = 1.0) -> Vec4:
    return tuple(x + scale * y for x, y in zip(a, b))  # type: ignore[return-value]


class EulerIntegrator:
    """一阶显式 Euler(默认):φ_{t+Δ} = clip(φ_t + Δ·f(φ_t))。"""

    name = "euler"

    def step(
        self,
        phi: FieldState,
        dt: float,
        forcing: Vec4,
        impacts: Vec4,
        params: FieldParams,
    ) -> FieldState:
        if dt < 0:
            raise ValueError("EulerIntegrator.step: dt 不得为负")
        d = derivative(phi.vec(), forcing, impacts, params)
        new_vec = _add(phi.vec(), d, dt)
        return FieldState.from_vec(new_vec, phi.ts + dt)


class TrapezoidIntegrator:
    """二阶梯形法(改进 Euler / Heun):先用 Euler 预测,再用两端导数均值修正。

    `φ_{t+Δ} = clip(φ_t + Δ/2·(f(φ_t) + f(φ_pred)))`,`φ_pred` 由 Euler
    预测(不 clip 的中间值,避免预测阶段提前截断影响修正精度;最终结果
    仍在此步末尾统一 clip,[AX-1] 不破)。
    """

    name = "trapezoid"

    def step(
        self,
        phi: FieldState,
        dt: float,
        forcing: Vec4,
        impacts: Vec4,
        params: FieldParams,
    ) -> FieldState:
        if dt < 0:
            raise ValueError("TrapezoidIntegrator.step: dt 不得为负")
        phi_vec = phi.vec()
        d0 = derivative(phi_vec, forcing, impacts, params)
        pred_vec = _add(phi_vec, d0, dt)
        d1 = derivative(pred_vec, forcing, impacts, params)
        avg = tuple((a + b) / 2.0 for a, b in zip(d0, d1))
        new_vec = _add(phi_vec, avg, dt)
        return FieldState.from_vec(new_vec, phi.ts + dt)


__all__ = ["Integrator", "EulerIntegrator", "TrapezoidIntegrator"]
