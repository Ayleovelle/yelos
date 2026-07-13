"""models/reserve.py 在整个架构中的位置:ReserveModel(id="reserve"),双池储备(finitude_BLUEPRINT §3.4)。

状态:(S, F),S = 契约 P(record["p"]),F = record["aging"]["fast"]。参数:
r = 0.01(日回填率),γ = 2.0(精神对事件的敏感倍率)。活跃日更新:

- S' = max(0, S − 1/L)                       (岁月只认日子,严格单调,与 F 无关)
- 有事件日(hi+concern_fired > 0):F' = max(0, F − (1/L)·(1 + 0.5·(hi+concern_fired))·γ)
- 无事件活跃日:F' = F + min(r, S' − F)       (回填,封顶慢池)
- 恒钳:F' = min(F', S')
- SettleOutcome(new_p=S', fast_pool=F', extras={"f": round(F', 6)})

**裁定(硬,axioms.md A4)**:契约 P := S';表达面 P_expr := F'。ReserveModel 的"休息回暖"
只作用于 P_expr = min(F,S),永不喂回权威 P——本文件的 `spend()` 只返回 S' 作为
`new_p`(过 gate 后仍是契约 P),`fast_pool` 是另一条独立、可日间波动的轨道。

理论出身:双池认知储备(fast recoverable / slow irreversible)。可观测签名:高压一周后
进入安静期,**词池与主动预算回暖但纪元不回头**——四模型中唯一让"休息"可观测的模型;
回暖永远够不到 S 的单调天花板。
# [FIN-A4] F<=S 恒成立(恒钳一行保证);回填 <= min(r, S-F);S 演化不读 F。
"""

from __future__ import annotations

from typing import Any

from .protocol import DayFacts, SettleOutcome

DEFAULT_R = 0.01
DEFAULT_GAMMA = 2.0
DEFAULT_PARAMS: dict[str, float] = {"r": DEFAULT_R, "gamma": DEFAULT_GAMMA}


class ReserveModel:
    model_id = "reserve"

    def __init__(self, params: dict[str, Any] | None = None, fast: float = 1.0) -> None:
        self.params = dict(params or {})
        self.fast = float(fast) if isinstance(fast, (int, float)) else 1.0

    def _param(self, key: str, default: float) -> float:
        value = self.params.get(key, default)
        try:
            value = float(value)
        except (TypeError, ValueError):
            return default
        return value if value >= 0.0 else default

    def spend(self, p: float, facts: DayFacts) -> SettleOutcome:
        lifespan = facts.lifespan_active_days
        r = self._param("r", DEFAULT_R)
        gamma = self._param("gamma", DEFAULT_GAMMA)
        base = 1.0 / lifespan if lifespan > 0 else 0.0

        s = p
        f = self.fast if self.fast is not None else s
        # F 不得从一开始就超过 S(防御:上一世/手改导致 F>S 的脏态,先钳一次)
        f = min(f, s)
        f = max(f, 0.0)

        s_new = max(0.0, s - base)

        hi = facts.high_intensity if facts.high_intensity > 0 else 0
        concern = facts.concern_fired if facts.concern_fired > 0 else 0
        has_event = (hi + concern) > 0

        if has_event:
            f_new = max(0.0, f - base * (1.0 + 0.5 * (hi + concern)) * gamma)
        else:
            headroom = max(0.0, s_new - f)
            f_new = f + min(r, headroom)

        f_new = min(f_new, s_new)
        f_new = max(f_new, 0.0)

        return SettleOutcome(
            new_p=s_new, fast_pool=f_new, extras={"f": round(f_new, 6)}
        )


__all__ = ["ReserveModel", "DEFAULT_PARAMS"]
