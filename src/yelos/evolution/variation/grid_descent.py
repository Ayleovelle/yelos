"""variation/grid_descent.py 在整个架构中的位置:坐标网格下降(蓝图 §0.3-2,附条件成员)。

**去留凭据未过闸(如实标注)**:本策略是否比 ``pattern_search`` 提供可区分
的被接受轨迹,须由 ``tests/evolution/test_strategy_distinct.py`` 裁决——
该测试本波未编写(施工预算约束,交付说明如实记为缺口)。在铡刀测试落地并
通过之前,``grid_descent`` 按蓝图纪律**不计入维二策略数**,仅作为
``evolution_strategy`` 枚举下可选但未被验收的实现存在;默认策略恒为
``pattern_search``。

实现:固定网格步长(``velocity_bound`` 的整数倍格点),逐维尝试网格内一步,
与 ``pattern_search`` 的差异在于步长量化到网格而非哈希连续值。
"""

from __future__ import annotations

from ..genome.registry import mutable_keys, spec_for
from ..genome.spec import Genome
from .base import clamp_step, evo_hash_unit


class GridDescent:
    name = "grid_descent"

    def __init__(self, velocity_bound: float = 0.05, grid_divisions: int = 4) -> None:
        self.velocity_bound = velocity_bound
        self.grid_divisions = max(1, grid_divisions)

    def propose(self, parent: Genome, gen: int, seed: str) -> tuple[Genome, ...]:
        candidates: list[Genome] = []
        grid_bound = self.velocity_bound / self.grid_divisions
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
                grid_step = grid_bound * (hi - lo)
                proposed = float(old) + direction * grid_step
            new_value = clamp_step(spec, old, proposed, grid_bound)
            if new_value == old:
                continue
            candidate = dict(parent)
            candidate[key] = new_value
            candidates.append(candidate)
        return tuple(candidates)


__all__ = ["GridDescent"]
