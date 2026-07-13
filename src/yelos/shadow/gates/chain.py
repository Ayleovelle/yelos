"""chain.py 在整个架构中的位置:闸链组装(蓝图 §9),显式七步序,每闸产
ASCII trace 标签入 `gate_trace`(供审计/可视化)。

```
1 mode_gate   : companion ∧ shadow_enabled,否则整链短路(steward 只余 guidance 温度只读)
2 sovereignty : P0 封存/guard_frozen → 全拦(主权恒最高)
3 hysteresis  : §6.3 状态机放行才继续(状态转移在本步发生,副作用不可逆)
4 calibration : §7.3 tier 效果施加(tight 档 strength margin 不足 → 拦;q 按档位上限截断)
5 budget      : 降档拍 inject 保留、原语让位(不入队)
6 act3_probe  : concern 原语共享幕 III 主动频控槽(结果由调用方——session 未来
                 接线——预先算好传入;`ShadowSystem.beat` 的 `probe_allowed`
                 关键字参数默认 True,保持"未接线时不额外收紧"的安全默认)
7 whitelist   : 出口枚举断言(`gates/exit.py` 构造时强制)
```

**步 3 的不可逆性**(记入交付说明的一处设计决定):迟滞状态机的转移(disarm
+ 记 `injected_day`)在闸链**内部**、发生在校准/预算/probe 之前——也就是说,
即使后续闸(4/5/6)最终拦下了可见输出,"今天这个类型已经被认真考虑过一次"
这件事仍然算数,不会因为下游拦截而回滚状态。这是刻意的保守设计:防止"同一
份越阈信号,因为下游偶然放行窗口不同而在同一天反复被计入候选",与 A6"当日
一次"纪律的精神一致(见 `signals/hysteresis.py` 模块 docstring 的对应说明)。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..calibration import gate_policy
from ..contracts import ConcernVerdict, RawConcern
from ..signals import hysteresis
from ..signals.intensity import compute_intensity
from ..signals.protocol import REARM_RATIO
from . import exit as exit_mod

STEP_LABELS = (
    "mode_gate",
    "sovereignty",
    "hysteresis",
    "calibration",
    "budget",
    "act3_probe",
    "whitelist",
)


@dataclass(frozen=True)
class GateContext:
    mode: str
    shadow_enabled: bool
    sealed_or_frozen: bool
    degraded: bool
    probe_allowed: bool
    intensity_fn: str
    # X6 裁定(INTEGRATION_SPEC §3.6):familiarity continues to modulate
    # concern intensity via the W1-era formula 0.9+0.2*familiarity, computed
    # by the orchestrator from memory.BaselineContext and passed in here.
    # Default 1.0 (neutral) keeps behavior unchanged when memory is absent
    # or when familiarity has not been wired (legacy path never applies
    # this factor, matching current session.py which does not either).
    familiarity_factor: float = 1.0


def run_gate_chain(
    raw: RawConcern,
    *,
    hysteresis_state: dict[str, Any],
    day_key: str,
    conf: float,
    tier: str,
    ctx: GateContext,
) -> tuple[dict[str, Any], ConcernVerdict | None, tuple[str, ...]]:
    """七步闸链。返回 `(new_hysteresis_state, verdict_or_None, gate_trace)`。

    `gate_trace` 恒含已执行到的步名(短路点即最后一个尝试过的步),供审计。
    """
    trace: list[str] = []

    trace.append("mode_gate")
    if not (ctx.mode == "companion" and ctx.shadow_enabled):
        return hysteresis_state, None, tuple(trace)

    trace.append("sovereignty")
    if ctx.sealed_or_frozen:
        return hysteresis_state, None, tuple(trace)

    trace.append("hysteresis")
    # A6 二值化简化(见 signals/hysteresis.py docstring):越阈即 strength=1.0。
    new_state, fire = hysteresis.step(hysteresis_state, 1.0, 1.0, REARM_RATIO, day_key)
    if not fire:
        return new_state, None, tuple(trace)

    trace.append("calibration")
    effects = gate_policy.gate_effects(tier)
    if not gate_policy.passes_strength_margin(tier, raw.strength):
        return new_state, None, tuple(trace)

    intensity = (
        compute_intensity(raw.strength, conf, ctx.intensity_fn) * ctx.familiarity_factor
    )
    q = max(0.0, min(effects["q_cap"], 0.5 + 0.5 * raw.strength * conf))

    trace.append("budget")
    enqueue_ok = not ctx.degraded

    trace.append("act3_probe")
    enqueue_ok = enqueue_ok and ctx.probe_allowed

    trace.append("whitelist")
    do_enqueue = enqueue_ok and effects["allow_enqueue"]
    verdict = exit_mod.apply_exit(
        raw.ctype,
        intensity,
        q,
        do_inject=True,
        do_enqueue=do_enqueue,
        gate_trace=tuple(trace),
    )
    return new_state, verdict, tuple(trace)


__all__ = ["STEP_LABELS", "GateContext", "run_gate_chain"]
