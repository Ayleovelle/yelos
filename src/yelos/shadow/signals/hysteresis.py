"""hysteresis.py 在整个架构中的位置:[SHTOM-A6] armed/disarmed 状态机唯一
实现(蓝图 §6.3),四检测器共用同一份状态转移函数,各自持独立 state
(binding `shadow.hysteresis.<ctype>`)。

```
armed     + strength>=trigger_th ∧ 当日未 fire → disarmed, fire=True, injected_day=today
armed     + strength>=trigger_th ∧ 当日已 fire → armed(保持), fire=False
armed     + strength<trigger_th                → armed(保持,无副作用), fire=False
disarmed  + strength<rearm_th                  → armed, fire=False
disarmed  + 其余                                → disarmed(跨日持久,F11b), fire=False
```

`step()` 是纯状态转移函数,不管"fire 之后该不该真的可见"——那是 gates 链
(§9)的职责;本状态机只回答"这次越阈算不算今天第一次"。

**本波的一处刻意简化(记入交付说明)**:严格意义上的"渐进式 re-arm"需要
检测器在未越阈时也能给出连续强度代理,才能区分"贴着阈值下方徘徊"与"已
显著回落";四个检测器当前只在越阈时产出 `RawConcern.strength`(蓝图 §6.1
协议本就如此定义)。`orchestrator.py` 的实际调用点因此把 `strength` 粗化为
二值(`1.0` 命中 / `0.0` 未命中)、`trigger_th` 固定 `1.0`——`rearm_th`(A6
规定的 `trigger_th * REARM_RATIO = 0.6`)在此二值化下等价于"下一次未命中
即可重新武装",保留了 A6 的三个核心可观测行为(跨日持久 / 当日一次 /
回落重新武装),细粒度的"半途缓冲区"留作后续细化。`step()` 函数本身完整
支持连续强度输入,不受此简化限制——简化只发生在调用点。
"""

from __future__ import annotations

from typing import Any


def step(
    state: dict[str, Any],
    strength: float,
    trigger_th: float,
    rearm_th: float,
    day_key: str,
) -> tuple[dict[str, Any], bool]:
    """[SHTOM-A6] 单次状态转移。返回 `(new_state, fire)`。"""
    armed = bool(state.get("armed", True))
    injected_day = str(state.get("injected_day", ""))

    if armed:
        if strength >= trigger_th:
            if injected_day == day_key:
                return {"armed": True, "injected_day": injected_day}, False
            return {"armed": False, "injected_day": day_key}, True
        return {"armed": True, "injected_day": injected_day}, False

    # disarmed
    if strength < rearm_th:
        return {"armed": True, "injected_day": injected_day}, False
    return {"armed": False, "injected_day": injected_day}, False


__all__ = ["step"]
