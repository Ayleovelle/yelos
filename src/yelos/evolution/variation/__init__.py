"""variation/ 在整个架构中的位置:变异策略族(蓝图 §2)。"""

from __future__ import annotations

from .base import VariationStrategy, clamp_step, evo_hash_unit, evo_tie_hash_unit
from .grid_descent import GridDescent
from .nelder_mead import NelderMead
from .pattern_search import PatternSearch

STRATEGIES: dict[str, type] = {
    "pattern_search": PatternSearch,
    "grid_descent": GridDescent,
    "nelder_mead": NelderMead,
}


def build_strategy(name: str, velocity_bound: float) -> VariationStrategy:
    """按名装配策略实例;未知名回退 ``pattern_search``(保守默认)。"""
    cls = STRATEGIES.get(name, PatternSearch)
    return cls(velocity_bound=velocity_bound)


__all__ = [
    "VariationStrategy",
    "clamp_step",
    "evo_hash_unit",
    "evo_tie_hash_unit",
    "PatternSearch",
    "GridDescent",
    "NelderMead",
    "STRATEGIES",
    "build_strategy",
]
