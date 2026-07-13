"""epochs/order_parameter.py 在整个架构中的位置:B 轨——序参量相变检测(finitude_BLUEPRINT §4.2/§1.1 A6)。

序参量 Ψ(p) = ρ_lex(p) · ρ_budget(p)。ρ_lex 读 `primal.pool_snapshot(p)`(接缝 X5,
INTEGRATION_SPEC §3.5)算词池可达集占比;ρ_budget 是主动预算占比,cap=0 时定义为 1
(缺席即中性)。`OpDetectorState` 持久化于 `record["epoch2"]`(INTEGRATION_SPEC §2.1)。

判据(A6):(i) Δρ_lex > 0 且 Δρ_budget > 0(联动收缩,不是单边噪声);(ii) ΔΨ >= θ·median
(最近 W 个活跃日 |ΔΨ|),θ=3.0,W=14,样本 <5 不触发(冷启动护栏)。全量确定性,检测器
状态可由 ledger 回放重建(纯函数 + 持久化滚动窗)。
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

THETA = 3.0
WINDOW = 14
MIN_SAMPLES = 5

_full_pool_cache: dict[str, int] | None = None


def _full_pool_sizes() -> dict[str, int]:
    """`pool_snapshot(1.0)` 各场合词句数(分母),模块内惰性缓存一次。"""
    global _full_pool_cache
    if _full_pool_cache is None:
        from yelos.primal import pool_snapshot

        full = pool_snapshot(1.0)
        _full_pool_cache = {occ: len(pool) for occ, pool in full.items()}
    return _full_pool_cache


def rho_lex(p: float) -> float:
    """# [FIN-A6] 词池可达集占比:Σ|shrink_pool(p)| / Σ|shrink_pool(1.0)|。"""
    from yelos.primal import pool_snapshot

    snap = pool_snapshot(p)
    denom_map = _full_pool_sizes()
    total_num = sum(len(pool) for pool in snap.values())
    total_den = sum(denom_map.values())
    if total_den <= 0:
        return 1.0
    return total_num / total_den


def rho_budget(p: float, cap: int) -> float:
    """主动预算占比:max(1, floor(cap*p)) / cap;cap<=0 定义为 1(缺席即中性)。"""
    if cap <= 0:
        return 1.0
    n = max(1, math.floor(cap * p))
    return n / cap


def psi(p: float, cap: int) -> float:
    """# [FIN-A6] Ψ = ρ_lex * ρ_budget。"""
    return rho_lex(p) * rho_budget(p, cap)


@dataclass
class OpDetectorState:
    """B 轨检测器持久化态(record["epoch2"])。冷启动:全默认(空滚动窗)。"""

    last_psi: float | None = None
    deltas: list[float] = field(default_factory=list)
    b_index: int = 0
    fired_days: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "last_psi": self.last_psi,
            "deltas": list(self.deltas),
            "b_index": self.b_index,
            "fired_days": list(self.fired_days),
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "OpDetectorState":
        if not isinstance(data, dict):
            return cls()
        deltas = data.get("deltas")
        fired = data.get("fired_days")
        last_psi = data.get("last_psi")
        b_index = data.get("b_index", 0)
        return cls(
            last_psi=float(last_psi) if isinstance(last_psi, (int, float)) else None,
            deltas=[float(x) for x in deltas] if isinstance(deltas, list) else [],
            b_index=int(b_index) if isinstance(b_index, int) else 0,
            fired_days=[str(d) for d in fired] if isinstance(fired, list) else [],
        )


def clamp_forward(idx: int, nominee: int) -> int:
    """# [FIN-A5] 纪元不可逆公理:idx' = max(idx, 提名)。"""
    return max(idx, nominee)


def detect(
    state: OpDetectorState, day: str, p_old_expr: float, p_new_expr: float, cap: int
) -> tuple[OpDetectorState, bool]:
    """一次 settle 的 B 轨观测:返回 (新状态, 本次是否判定相变)。

    ρ_lex/ρ_budget 各自的 Δ 用于联动判据(i);ΔΨ 与滚动窗中位数比较用于阈值判据(ii)。
    """
    rho_lex_old = rho_lex(p_old_expr)
    rho_lex_new = rho_lex(p_new_expr)
    rho_budget_old = rho_budget(p_old_expr, cap)
    rho_budget_new = rho_budget(p_new_expr, cap)
    psi_old = rho_lex_old * rho_budget_old
    psi_new = rho_lex_new * rho_budget_new

    d_lex = rho_lex_old - rho_lex_new
    d_budget = rho_budget_old - rho_budget_new
    dpsi = psi_old - psi_new

    window = list(state.deltas)
    fire = False
    if len(window) >= MIN_SAMPLES:
        median = statistics.median(window)
        if d_lex > 0.0 and d_budget > 0.0 and dpsi >= THETA * median:
            fire = True

    new_deltas = (window + [abs(dpsi)])[-WINDOW:]
    new_b_index = (
        clamp_forward(state.b_index, state.b_index + 1) if fire else state.b_index
    )
    new_fired = list(state.fired_days) + ([day] if fire else [])

    new_state = OpDetectorState(
        last_psi=psi_new, deltas=new_deltas, b_index=new_b_index, fired_days=new_fired
    )
    return new_state, fire


__all__ = [
    "THETA",
    "WINDOW",
    "MIN_SAMPLES",
    "rho_lex",
    "rho_budget",
    "psi",
    "OpDetectorState",
    "clamp_forward",
    "detect",
]
