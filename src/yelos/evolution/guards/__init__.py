"""guards/ 在整个架构中的位置:变异前后双段守卫(蓝图 §1 A2)。"""

from __future__ import annotations

from .common import GuardVerdict
from .property_gate import run_property_gate
from .static_check import check_mutation_set

__all__ = ["GuardVerdict", "check_mutation_set", "run_property_gate"]
