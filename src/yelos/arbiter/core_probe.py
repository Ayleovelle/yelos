"""core_probe.py 在整个架构中的位置。

装配期自检 / 测试共用的合成探针构造器。与 ``guards/base.py`` 的
``_synthetic_probe_grid``(守卫专用、覆盖布尔分支网格)不同,这里只
提供**一枚**中性探针,给后置滤波自检、以及测试里"随便造一个能跑的
PolicyInput 再改字段"的场景省样板代码。
"""

from __future__ import annotations

from ..core.arbiter import ArbiterInput
from .inputs import PolicyInput, PolicyParams


def build_neutral_probe(
    *,
    action: str = "hold",
    pressure: float = 0.5,
    expr: float = 0.5,
    p: float = 0.8,
    now_ts: float = 100000.0,
    last_intervention_ts: float = 0.0,
    min_gap_seconds: int = 180,
    draft: str = "今天天气不错。",
    surface_age_s: float = 0.0,
    daily_interventions: int = 0,
    params: PolicyParams | None = None,
) -> PolicyInput:
    base = ArbiterInput(
        session_id="probe_sid",
        day_key="2026-07-11",
        draft=draft,
        surface={
            "decision": {"action": action},
            "state": {
                "boundary": {"pressure": pressure},
                "needs": {"expression": expr},
            },
            "guard": {"allowed": True},
        },
        p=p,
        bound=True,
        enabled=True,
        silenced=False,
        is_self=False,
        has_plain=True,
        has_non_plain=False,
        now_ts=now_ts,
        last_intervention_ts=last_intervention_ts,
        min_gap_seconds=min_gap_seconds,
    )
    return PolicyInput(
        base=base,
        surface_age_s=surface_age_s,
        daily_interventions=daily_interventions,
        params=params if params is not None else PolicyParams(0.75, 0.55, 0.70, 1.0),
    )
