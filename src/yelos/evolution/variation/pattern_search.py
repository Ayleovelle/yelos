"""variation/pattern_search.py 在整个架构中的位置:保守步长模式搜索(蓝图 §0.3-2,默认/唯一硬承诺)。

坐标模式搜索:对每个可变异维,沿哈希确定的方向探一步(``+step_cap`` 或
``-step_cap``,由 ``evo`` 键型哈希定号),生成一个只改该维的候选——保守、
可解释、每代提案数 = 可变异维数,不做多维联合跳跃。
"""

from __future__ import annotations

from ..genome.registry import mutable_keys, spec_for
from ..genome.spec import Genome
from .base import clamp_step, evo_hash_unit


class PatternSearch:
    name = "pattern_search"

    def __init__(self, velocity_bound: float = 0.05) -> None:
        self.velocity_bound = velocity_bound

    def propose(self, parent: Genome, gen: int, seed: str) -> tuple[Genome, ...]:
        candidates: list[Genome] = []
        for key in sorted(mutable_keys()):
            spec = spec_for(key)
            if spec is None or key not in parent:
                continue
            old = parent[key]
            unit = evo_hash_unit(seed, gen, self.name, key)
            direction = 1.0 if unit >= 0.5 else -1.0
            if spec.kind == "enum":
                idx = spec.choices.index(old) if old in spec.choices else 0
                step = 1 if direction > 0 else -1
                new_idx = min(max(idx + step, 0), len(spec.choices) - 1)
                proposed = spec.choices[new_idx]
            else:
                lo = spec.lo if spec.lo is not None else float(old)
                hi = spec.hi if spec.hi is not None else float(old)
                step_cap = self.velocity_bound * (hi - lo)
                proposed = float(old) + direction * step_cap
            new_value = clamp_step(spec, old, proposed, self.velocity_bound)
            if new_value == old:
                continue
            candidate = dict(parent)
            candidate[key] = new_value
            candidates.append(candidate)
        return tuple(candidates)


__all__ = ["PatternSearch"]
