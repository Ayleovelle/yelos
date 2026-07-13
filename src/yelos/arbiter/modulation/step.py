"""modulation/step.py 在整个架构中的位置。

StepCurve:现行阶跃曲线,默认曲线,与冻结内核 core.arbiter 的字面量
逐字节对齐——swallow_th 0.75(P>=0.5)/0.70(P<0.5),replace_heavy_th/
express_expr_th 是 v0.1 里本就与 P 无关的常量(0.55/0.70)。θ≡0 时,
compose_policy_params(StepCurve(), p, Theta()) 的输出与冻结内核硬编码
的阈值逐字节一致(T-G1 兼容闸的前提之一)。
"""

from __future__ import annotations

from .base import Thresholds

curve_id = "step"


class StepCurve:
    curve_id = "step"

    def thresholds(self, p: float) -> Thresholds:
        return Thresholds(
            swallow_th=0.75 if p >= 0.5 else 0.70,
            replace_heavy_th=0.55,
            express_expr_th=0.70,
            gate_scale=1.0,
        )


STEP_CURVE = StepCurve()
