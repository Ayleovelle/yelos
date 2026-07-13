"""impulses/field_crossing.py 在整个架构中的位置:场轨迹越阈曲面策略(维二 2/3)。

**出身**:动力系统事件检测。标量势 `s(t) = ReLU(w_norm · φ(t))`(w 归一后
取正部)向上穿越阈 `θ_hi`,且此前处于迟滞带下界 `θ_lo` 之下(Schmitt
触发,防抖)。触发后场回冲:`φ_d, φ_g` 乘以回冲系数 ρ(表达泄压,独立于
min_gap 硬闸的软机制)。**有记忆**:触发依赖 φ 的积累史,冲击后延迟触发。
"""

from __future__ import annotations

from ..field.state import FieldState, Vec4
from .policy import PolicyContext, PolicyProposal

# 默认权重(§3.1):drive 正向、languor 负向、longing 正向、afterglow 弱正向。
_DEFAULT_WEIGHTS: Vec4 = (0.5, -0.3, 0.4, 0.2)


def _normalize_l1(w: Vec4) -> Vec4:
    total = sum(abs(x) for x in w)
    if total == 0.0:
        return w
    return tuple(x / total for x in w)  # type: ignore[return-value]


def scalar_potential(phi: FieldState, weights: Vec4 = _DEFAULT_WEIGHTS) -> float:
    """s(t) = ReLU(w_norm · φ(t)),w 先按 L1 归一再取正部(§3.1)。"""
    w = _normalize_l1(weights)
    dot = sum(a * b for a, b in zip(w, phi.vec()))
    return max(0.0, dot)


class FieldCrossingPolicy:
    name = "field_crossing"

    def __init__(
        self,
        theta_hi: float = 0.32,
        theta_lo: float = 0.18,
        rho: float = 0.6,
        weights: Vec4 = _DEFAULT_WEIGHTS,
    ) -> None:
        if not (0.0 <= theta_lo < theta_hi):
            raise ValueError("FieldCrossingPolicy: 需要 0 <= theta_lo < theta_hi")
        if not (0.0 < rho <= 1.0):
            raise ValueError("FieldCrossingPolicy: rho 须落在 (0,1]")
        self.theta_hi = theta_hi
        self.theta_lo = theta_lo
        self.rho = rho
        self.weights = weights

    def propose(self, ctx: PolicyContext) -> PolicyProposal:
        s = scalar_potential(ctx.phi, self.weights)
        armed = bool(ctx.policy_state.get("armed", True))

        want = False
        if armed and s >= self.theta_hi:
            want = True
            armed = False
        elif not armed and s <= self.theta_lo:
            armed = True

        trace = {
            "policy": self.name,
            "s": s,
            "theta_hi": self.theta_hi,
            "theta_lo": self.theta_lo,
            "armed_before": ctx.policy_state.get("armed", True),
            "armed_after": armed,
        }
        return PolicyProposal(
            want=want,
            intensity=min(1.0, s / self.theta_hi) if self.theta_hi else 0.0,
            trace=trace,
            new_policy_state={"armed": armed, "s_prev": s},
        )

    def recoil(self, phi: FieldState) -> FieldState:
        """触发后场回冲(表达泄压):φ_d, φ_g 乘以 ρ;独立于 min_gap 硬闸的软机制。

        由 scheduler 在 `decision.send=True` 且当前策略为本策略时调用,
        紧接场步进之后、moments 记账之前(W-3 接线点)。
        """
        return FieldState(
            drive=phi.drive * self.rho,
            languor=phi.languor,
            longing=phi.longing * self.rho,
            afterglow=phi.afterglow,
            ts=phi.ts,
        ).clipped()


__all__ = ["FieldCrossingPolicy", "scalar_potential"]
