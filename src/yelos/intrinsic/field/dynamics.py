"""field/dynamics.py 在整个架构中的位置:场演化的导数项(维一 §1.1 更新算子)。

```
φ_{t+Δ} = clip( φ_t + Δ · ( −Λ⊙(φ_t−φ_eq) + C(τ_t) + Σ_j K·e_j(t) ) )
```

本文件只提供导数函数 `derivative(phi, forcing, impacts, params) -> Vec4`
(衰减项 + 强迫 + 冲击的线性合成,尚未乘 Δ、尚未 clip);积分器
(integrators.py)负责把导数按 Euler/Trapezoid 规则积分并在最后 clip。
纯函数,零 random/time.time()(AX-7)。
"""

from __future__ import annotations

from .state import FieldParams, Vec4


def decay_term(phi: Vec4, params: FieldParams) -> Vec4:
    """[AX-2] 自然衰减:−Λ⊙(φ−φ_eq),Λ 全正 ⇒ 每通道朝 φ_eq 收缩。"""
    return tuple(-lam * (x - eq) for x, lam, eq in zip(phi, params.lam, params.eq))  # type: ignore[return-value]


def derivative(phi: Vec4, forcing: Vec4, impacts: Vec4, params: FieldParams) -> Vec4:
    """合成三项(衰减 + 昼夜强迫 + 事件冲击),尚未按 Δ 积分、尚未 clip。"""
    decay = decay_term(phi, params)
    return tuple(d + c + i for d, c, i in zip(decay, forcing, impacts))  # type: ignore[return-value]


__all__ = ["decay_term", "derivative"]
