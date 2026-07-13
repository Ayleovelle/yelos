"""intensity.py 在整个架构中的位置:[SHTOM-A4] 强度函数两套,唯一实现地
(蓝图 §6.4)。`intensity = 信号强度 × 校准置信`——任何下游消费 inject 强度
的路径都必须经本文件的 `compute_intensity`,不得绕过折减直接用
`RawConcern.strength`(A4 诚实条款,"不确定就少说")。
"""

from __future__ import annotations

import math

_FLOOR = 0.3
_SPAN = 0.7
_NDIGITS = 3
_SAT_K = 2.2


def linear_intensity(strength: float, conf: float) -> float:
    """v0.1 谱系,默认:`0.3 + 0.7 * strength * conf`。"""
    return _FLOOR + _SPAN * strength * conf


def saturating_intensity(strength: float, conf: float) -> float:
    """低强度更敏、高强度饱和:`0.3 + 0.7 * (1 - exp(-2.2*strength)) * conf`。"""
    return _FLOOR + _SPAN * (1.0 - math.exp(-_SAT_K * strength)) * conf


_FN_REGISTRY = {"linear": linear_intensity, "saturating": saturating_intensity}


def compute_intensity(strength: float, conf: float, fn_name: str = "linear") -> float:
    """[SHTOM-A4] 强度 = 信号强度 × 校准置信,量化到 3 位,钳到 `[0,1]`。

    `conf` 折减是强制的:传入 `conf=0` 时任意 `strength` 都产出 floor 值
    (0.3,不是 0——floor 本身是"有感"下限,不是"不确定就归零",诚实但不
    过度悲观)。`conf` 越低,`strength` 对最终强度的影响越弱(A4 单调折减)。
    """
    fn = _FN_REGISTRY.get(fn_name)
    if fn is None:
        raise ValueError(
            f"unknown shadow_intensity_fn={fn_name!r}; choices: {tuple(_FN_REGISTRY)}"
        )
    strength = max(0.0, min(1.0, strength))
    conf = max(0.0, min(1.0, conf))
    raw = fn(strength, conf)
    return round(max(0.0, min(1.0, raw)), _NDIGITS)


def intensity_ab_grid(
    strengths: tuple[float, ...] = (0.0, 0.25, 0.5, 0.75, 1.0),
    confs: tuple[float, ...] = (0.0, 0.25, 0.5, 0.75, 1.0),
) -> dict:
    """两套强度函数在同一 (strength, conf) 网格上的输出差异(蓝图 §6.4 A/B
    对比评测凭据)。纯数值计算,零 I/O——落盘由调用方(测试)负责,保持本
    文件对文件系统零依赖。
    """
    rows = []
    for s in strengths:
        for c in confs:
            lin = compute_intensity(s, c, "linear")
            sat = compute_intensity(s, c, "saturating")
            rows.append(
                {
                    "strength": s,
                    "conf": c,
                    "linear": lin,
                    "saturating": sat,
                    "delta": round(sat - lin, _NDIGITS),
                }
            )
    return {"grid": rows}


__all__ = [
    "linear_intensity",
    "saturating_intensity",
    "compute_intensity",
    "intensity_ab_grid",
]
