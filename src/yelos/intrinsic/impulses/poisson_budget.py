"""impulses/poisson_budget.py 在整个架构中的位置:非齐次泊松触发策略(维二 3/3)。

**出身**:点过程理论。强度 `λ(t) = λ_max · ‖φ(t)‖₂ / 2`(‖·‖₂/2 ∈ [0,1],
φ∈[0,1]^4 时 ‖φ‖₂ 最大为 2);每心跳拍以概率 `1 − exp(−λ·Δ)` 触发(Δ 取
1.0,即以心跳拍为单位时间,λ_max 已按此标定,§10 域界 [0.05,0.5])。伪随机
数 = 哈希族 `h("poisson", sid, day_key, tick_index)`(键型见
`primal/determinism.py::KEY_REGISTRY["poisson"]`),同态同日同拍同决定,
core 禁 random 纪律不破([AX-7])。**离散化触发**:高场期内触发时刻弥散,
不钉在越面瞬间(与 FieldCrossing 的区分观测量 O3,§3.2)。
"""

from __future__ import annotations

import math

from yelos.primal.determinism import h_bytes

from ..field.state import FieldState
from .policy import PolicyContext, PolicyProposal

LAMBDA_MAX_MIN = 0.05
LAMBDA_MAX_MAX = 0.5
_DT = 1.0  # 每次 propose 视作一个心跳拍(单位时间),λ_max 已按此标定


def _norm2(phi: FieldState) -> float:
    return math.sqrt(sum(x * x for x in phi.vec()))


def _thin(key: str) -> float:
    """哈希族确定性 [0,1) 变量([AX-7]),4 字节精度。"""
    raw = h_bytes(key, 4)
    value = int.from_bytes(raw, "big")
    return value / float(1 << 32)


class PoissonBudgetPolicy:
    name = "poisson_budget"

    def __init__(self, lambda_max: float = 0.2) -> None:
        if not (LAMBDA_MAX_MIN <= lambda_max <= LAMBDA_MAX_MAX):
            raise ValueError(
                f"PoissonBudgetPolicy: lambda_max 须落在 [{LAMBDA_MAX_MIN},{LAMBDA_MAX_MAX}]"
            )
        self.lambda_max = lambda_max

    def propose(self, ctx: PolicyContext) -> PolicyProposal:
        norm = _norm2(ctx.phi)
        lam = self.lambda_max * norm / 2.0
        p_fire = 1.0 - math.exp(-lam * _DT)

        key = f"poisson|{ctx.sid}|{ctx.day_key}|{ctx.tick_index}"
        u = _thin(key)
        want = u < p_fire

        trace = {
            "policy": self.name,
            "lambda": lam,
            "p_fire": p_fire,
            "u": u,
            "norm2": norm,
        }
        return PolicyProposal(
            want=want,
            intensity=min(1.0, lam / self.lambda_max) if self.lambda_max else 0.0,
            trace=trace,
            new_policy_state=dict(ctx.policy_state),
        )


__all__ = ["PoissonBudgetPolicy", "LAMBDA_MAX_MIN", "LAMBDA_MAX_MAX"]
