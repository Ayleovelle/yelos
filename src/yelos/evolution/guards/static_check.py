"""guards/static_check.py 在整个架构中的位置:变异前静态守卫(A1/A2 前段,蓝图 §1/T2)。

T2 表阶段 1-3:未注册键拒 → 铁域键拒 → 越域界/超步长拒。顺序不可调换
(便宜的先拒)。
"""

from __future__ import annotations

from ..genome.registry import REGISTRY, iron_keys, spec_for
from ..genome.spec import Genome
from .common import GuardVerdict

STAGE = "static"


def check_mutation_set(  # EVO-A1 EVO-A2
    parent: Genome, candidate: Genome, *, velocity_bound: float = 0.05
) -> GuardVerdict:
    """A1 可变异域公理 + A2 铁域公理的静态段。

    候选与亲代的差集(变异集 M_g)必须是:①全部已注册,②全部 mutable,
    ③落在域界内且步长不超上界(A3 的静态复核,真正裁剪出口在
    ``variation.base.clamp_step``——这里只做"提案是否已守规矩"的验收)。
    """
    reasons: list[str] = []
    registry_keys = {spec.key for spec in REGISTRY}
    iron = iron_keys()

    changed_keys = [
        key
        for key in set(parent.keys()) | set(candidate.keys())
        if parent.get(key) != candidate.get(key)
    ]

    for key in changed_keys:
        if key not in registry_keys:
            reasons.append(f"unregistered:{key}")
            continue
        if key in iron:
            reasons.append(f"iron:{key}")
            continue
        spec = spec_for(key)
        if spec is None:
            reasons.append(f"unregistered:{key}")
            continue
        new_value = candidate.get(key)
        if not spec.in_domain(new_value):
            reasons.append(f"domain:{key}")
            continue
        old_value = parent.get(key, spec.default)
        if spec.kind != "enum":
            lo = spec.lo if spec.lo is not None else float(old_value)
            hi = spec.hi if spec.hi is not None else float(old_value)
            step_cap = velocity_bound * (hi - lo)
            try:
                delta = abs(float(new_value) - float(old_value))
            except (TypeError, ValueError):
                reasons.append(f"domain/step:{key}")
                continue
            if delta > step_cap + 1e-9:
                reasons.append(f"domain/step:{key}")

    return GuardVerdict(ok=not reasons, stage=STAGE, reasons=tuple(reasons))


__all__ = ["check_mutation_set"]
