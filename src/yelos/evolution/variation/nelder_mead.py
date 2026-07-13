"""variation/nelder_mead.py 在整个架构中的位置:无导数单纯形(蓝图 §0.3-2,附条件成员)。

**去留凭据未过闸(如实标注,同 ``grid_descent`` 头注)**:``test_strategy_
distinct.py`` 本波未编写,``nelder_mead`` 暂不计入维二策略数,只是可选未
验收实现。真单纯形需要跨代维护顶点集状态(本模块 runner 是单亲代→候选集
的无状态调用),此处收敛为"单代联合扰动"的简化变体:同时扰动全部可变异维
(而非 ``pattern_search`` 的逐维单变),幅度按 ``velocity_bound`` 收缩
——用以在铡刀测试到来时提供一个与 ``pattern_search``"逐维/联合"形状不同
的候选生成方式,而非声称完整 Nelder-Mead 算法。
"""

from __future__ import annotations

from ..genome.registry import mutable_keys, spec_for
from ..genome.spec import Genome
from .base import clamp_step, evo_hash_unit


class NelderMead:
    name = "nelder_mead"

    def __init__(self, velocity_bound: float = 0.05, shrink: float = 0.5) -> None:
        self.velocity_bound = velocity_bound
        self.shrink = shrink

    def propose(self, parent: Genome, gen: int, seed: str) -> tuple[Genome, ...]:
        candidate = dict(parent)
        changed = False
        for key in sorted(mutable_keys()):
            spec = spec_for(key)
            if spec is None or key not in parent:
                continue
            old = parent[key]
            unit = evo_hash_unit(seed, gen, self.name, key)
            direction = 1.0 if unit >= 0.5 else -1.0
            if spec.kind == "enum":
                idx = spec.choices.index(old) if old in spec.choices else 0
                new_idx = min(
                    max(idx + (1 if direction > 0 else -1), 0), len(spec.choices) - 1
                )
                proposed = spec.choices[new_idx]
            else:
                lo = spec.lo if spec.lo is not None else float(old)
                hi = spec.hi if spec.hi is not None else float(old)
                step_cap = self.velocity_bound * self.shrink * (hi - lo)
                proposed = float(old) + direction * step_cap
            new_value = clamp_step(spec, old, proposed, self.velocity_bound)
            if new_value != old:
                candidate[key] = new_value
                changed = True
        return (candidate,) if changed else ()


__all__ = ["NelderMead"]
