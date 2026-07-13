"""modulation/logistic.py 在整个架构中的位置。

LogisticCurve:连续渐变曲线,SmoothPolicy 深化配套(数值实现选择,不计
维二策略数,arbiter_BLUEPRINT §4)。用 sigmoid((p-0.5)/0.08) 把 StepCurve
的阶跃换成连续 S 形,幅度与 StepCurve 在 p->0/p->1 极限处对齐
(0.70 起步、+0.05 顶格),避免"连续化"变成另一套不可比的数值魔法。

两曲线的对比(P 从 0 到 1 的采样表)落盘 ``experiments/arbiter/curves.md``
(``scripts`` 之外由测试生成 / 手工核对均可,这里只放曲线本体)。
"""

from __future__ import annotations

import math

from .base import Thresholds

curve_id = "logistic"


def _sigmoid(x: float) -> float:
    # 数值稳定写法,避免 exp 溢出。
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


class LogisticCurve:
    curve_id = "logistic"

    def thresholds(self, p: float) -> Thresholds:
        s = _sigmoid((p - 0.5) / 0.08)
        return Thresholds(
            swallow_th=0.70 + 0.05 * s,
            replace_heavy_th=0.50 + 0.05 * s,
            express_expr_th=0.65 + 0.05 * s,
            gate_scale=1.0,
        )


LOGISTIC_CURVE = LogisticCurve()
