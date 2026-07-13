"""gate.py 在整个架构中的位置:MonotoneGate——一切老化模型的唯一出口(finitude_BLUEPRINT §3.0)。

`settle_through_gate` 是四模型 + 未来任何新增模型的**结构性单调闸**:短路条件(不活跃日/
无老化)原样放行;否则调模型 `spend()`,再钳一次 `min(p, max(0.0, out.new_p))`,并用
`assert` 做双保险(与 `core.finitude.settle_day` 同款纪律)。恶意模型(返回 p+0.1 之类)
在这里被结构性钳死,不依赖模型自觉。
"""

from __future__ import annotations

from dataclasses import replace

from .models.protocol import AgingModel, DayFacts, SettleOutcome


def settle_through_gate(model: AgingModel, p: float, facts: DayFacts) -> SettleOutcome:
    """# [FIN-A1] 唯一出口:P' <= P 结构性保证,恶意/bug 模型无法使其返老还童。"""
    if facts.lifespan_active_days <= 0 or not facts.was_active_day:
        return SettleOutcome(new_p=p, fast_pool=None, extras={})
    out = model.spend(p, facts)
    new_p = min(p, max(0.0, out.new_p))
    assert new_p <= p  # noqa: S101  结构性单调双保险
    return replace(out, new_p=new_p)


__all__ = ["settle_through_gate"]
