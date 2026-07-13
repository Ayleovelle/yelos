"""selection/judge.py 在整个架构中的位置:selection 判决器(蓝图 §2.1/T3)。

T3 四行按序短路:主权违例一票否决 → 劣不落地 → 平手保守 → 唯有严格更优才
accept。**不立"适应度单调改进定理"**(负清单,§1)——本函数只保证"劣不落
地",不保证代代更好。
"""

from __future__ import annotations

from typing import Literal

from .fitness import Fitness, total

Verdict = Literal["accept", "reject"]

_EPS = 1e-9


def judge(
    candidate: Fitness, incumbent: Fitness, *, online_weight: float = 0.0
) -> Verdict:
    if candidate.sovereignty_violations > 0:
        return "reject"
    cand_total = total(candidate, online_weight)
    inc_total = total(incumbent, online_weight)
    if cand_total < inc_total - _EPS:
        return "reject"
    if abs(cand_total - inc_total) <= _EPS:
        return "reject"
    return "accept"


__all__ = ["Verdict", "judge"]
