"""modulation/base.py 在整个架构中的位置。

调制层协议:P(可塑性预算)-> 阈值曲线。曲线族属数值实现选择(同 intrinsic
积分器),**不计维二策略数**(arbiter_BLUEPRINT §4)。narrow_p 边界不在
本协议输出内——它是幕 V 语义铁域常量,任何曲线成员不得移动它
(见 ``inputs.NARROW_P``)。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Thresholds:
    """P 处的基线阈值包(未叠加 hysteresis θ)。"""

    swallow_th: float
    replace_heavy_th: float
    express_expr_th: float
    gate_scale: float = 1.0


class ModulationCurve(Protocol):
    curve_id: str

    def thresholds(self, p: float) -> Thresholds: ...
