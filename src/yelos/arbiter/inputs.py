"""inputs.py 在整个架构中的位置。

策略入参的数据契约。N2 铁律:`core.arbiter.ArbiterInput` 字节冻结,零改动;
本文件把它包裹进 `PolicyInput`,新信息(surface_age_s / daily_interventions /
θ 生效后的阈值包)只加在包裹层,绝不碰冻结内核的字段集。

`PolicyParams` 是 modulation 曲线 ∘ hysteresis θ 的合成产物(§2.1);
`compose_policy_params` 是合成点的唯一权威实现,供组合根与测试共用。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.arbiter import ArbiterInput

__all__ = [
    "PolicyInput",
    "PolicyParams",
    "compose_policy_params",
    "clip",
]


def clip(x: float, lo: float, hi: float) -> float:
    """夹紧到 [lo, hi],hysteresis/modulation 共用的纯函数。"""
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


# narrow_p 铁域常量(幕 V 语义,任何曲线/θ 都不得移动它,arbiter_BLUEPRINT §5.3)
NARROW_P = 0.15


@dataclass(frozen=True)
class PolicyParams:
    """modulation 曲线 ∘ hysteresis θ 的合成产物;TablePolicy 忽略之。"""

    swallow_th: float
    replace_heavy_th: float
    express_expr_th: float
    gate_scale: float
    narrow_p: float = NARROW_P


@dataclass(frozen=True)
class PolicyInput:
    """策略入参:包裹冻结的 ArbiterInput,不改其一字(N2)。"""

    base: ArbiterInput
    surface_age_s: float
    daily_interventions: int
    params: PolicyParams


def compose_policy_params(curve, p: float, theta) -> PolicyParams:
    """AX:A5.1/A5.2 落点之一 —— θ 的 Box 早已由 updater 保证,这里只再合成 +
    clip 到 §5.3 表定义的最终阈值范围(与 θ 的 Box 是两层不同的界)。

    ``curve`` 满足 ``modulation.base.ModulationCurve`` 协议;``theta`` 满足
    ``hysteresis.params.Theta`` 形状(鸭子类型,避免循环 import)。
    """
    base = curve.thresholds(p)
    return PolicyParams(
        swallow_th=clip(base.swallow_th + theta.d_sw, 0.60, 0.90),
        replace_heavy_th=clip(base.replace_heavy_th + theta.d_rp, 0.45, 0.65),
        express_expr_th=clip(base.express_expr_th + theta.d_ex, 0.55, 0.85),
        gate_scale=clip(base.gate_scale * theta.gamma, 0.8, 1.2),
        narrow_p=NARROW_P,
    )
