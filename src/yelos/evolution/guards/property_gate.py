"""guards/property_gate.py 在整个架构中的位置:变异后性质测试闸(A2 后段,蓝图 §1/T2)。

T2 表阶段 4:全量性质套件(单调 / 白名单 / 介入率有界 / P0)以候选 overlay
起 harness 跑。

**如实标注(交付说明重复一遍)**:本波性质套件的**最小实现**——只跑
"铁域不变式"(候选的每个铁参数值必须逐字节等于 hatch 默认,A2 的直接复核)
与"域界不变式"(候选每个已注册值必须落在其 ``GeneSpec`` 域界内)。蓝图提到
的"单调 / 白名单 / 介入率有界"等跨模块性质测试,需要各 owner 模块(arbiter
白名单闸、intrinsic 单调公理等)提供可调用的性质测试插件——那些插件本身
不归本模块自著(§0.4 账本),截至本波尚无该插件接口landed,故此处不能提
供"接了线却测不到东西"的假消费。留空是诚实的边界,不是遗漏的借口。
"""

from __future__ import annotations

from ..genome.registry import iron_keys, spec_for
from ..genome.spec import Genome
from .common import GuardVerdict

STAGE = "property"


def run_property_gate(candidate: Genome) -> GuardVerdict:  # EVO-A2
    reasons: list[str] = []

    for key in iron_keys():
        spec = spec_for(key)
        if spec is None:
            continue
        value = candidate.get(key, spec.default)
        if value != spec.default:
            reasons.append(f"iron_drifted:{key}")

    for key, value in candidate.items():
        spec = spec_for(key)
        if spec is None:
            continue
        if not spec.in_domain(value):
            reasons.append(f"out_of_domain:{key}")

    return GuardVerdict(ok=not reasons, stage=STAGE, reasons=tuple(reasons))


__all__ = ["run_property_gate"]
