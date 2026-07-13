"""T-CMP-01:v0.1 `core.intrinsic.decide` 与 `ThresholdPolicy + apply_gates` 组合

在代表性格点(逐轴扫描)+ 大样本随机联合抽样下逐字节一致(intrinsic_BLUEPRINT
§2.2/§8.2)。全维笛卡尔积组合数过大(> 10^6),采用"逐轴扫描 + 大样本随机
联合抽样"的分层策略作为工程上可行的格点替身,如实记录于此(§10 诚实纪律
一脉相承)。
"""

from __future__ import annotations

import random

from yelos.core.intrinsic import IntrinsicInput, decide
from yelos.intrinsic.impulses.gates import GateInput, apply_gates
from yelos.intrinsic.impulses.policy import PolicyContext
from yelos.intrinsic.impulses.threshold import ThresholdPolicy
from yelos.intrinsic.field.state import FieldState

_tp = ThresholdPolicy()


def _run_both(params: dict) -> tuple:
    """同一组参数分别喂 core.decide() 与 ThresholdPolicy+apply_gates(),返回 (a,b)。"""
    surface = {
        "state": {
            "needs": {
                "contact": params["contact"],
                "expression": params["expression"],
                "quiet": params["quiet"],
            },
            "boundary": {
                "pressure": params["pressure"],
                "interruption_budget": params["budget"],
            },
        }
    }

    core_input = IntrinsicInput(
        session_id="s",
        day_key="2026-07-11",
        surface=surface,
        p=params["p"],
        enabled=params["enabled"],
        silenced=params["silenced"],
        sealed=params["sealed"],
        guard_frozen_today=params["guard_frozen_today"],
        reach_out_cached=params["reach_out_cached"],
        now_local_minutes=params["now_local_minutes"],
        quiet_start_min=params["quiet_start_min"],
        quiet_end_min=params["quiet_end_min"],
        daily_cap_base=params["daily_cap_base"],
        sent_today=params["sent_today"],
        last_proactive_ts=params["last_proactive_ts"],
        now_ts=params["now_ts"],
        unanswered_streak=params["unanswered_streak"],
        contact_night_sent_today=params["contact_night_sent_today"],
        phase=params["phase"],
    )
    a = decide(core_input)

    ctx = PolicyContext(
        phi=FieldState.neutral(params["now_ts"]),
        surface=surface,
        p=params["p"],
        now_ts=params["now_ts"],
        now_local_minutes=params["now_local_minutes"],
        day_key="2026-07-11",
        sent_today=params["sent_today"],
        last_proactive_ts=params["last_proactive_ts"],
        unanswered_streak=params["unanswered_streak"],
        reach_out_cached=params["reach_out_cached"],
        phase=params["phase"],
    )
    gate = GateInput(
        surface=surface,
        p=params["p"],
        enabled=params["enabled"],
        silenced=params["silenced"],
        sealed=params["sealed"],
        guard_frozen_today=params["guard_frozen_today"],
        now_local_minutes=params["now_local_minutes"],
        quiet_start_min=params["quiet_start_min"],
        quiet_end_min=params["quiet_end_min"],
        daily_cap_base=params["daily_cap_base"],
        sent_today=params["sent_today"],
        last_proactive_ts=params["last_proactive_ts"],
        now_ts=params["now_ts"],
        unanswered_streak=params["unanswered_streak"],
        contact_night_sent_today=params["contact_night_sent_today"],
        phase=params["phase"],
    )
    proposal = _tp.propose(ctx)
    b = apply_gates(proposal, gate)
    return a, b


_BASELINE = dict(
    contact=0.7,
    expression=0.5,
    pressure=0.0,
    quiet=0.0,
    budget=1.0,
    p=1.0,
    enabled=True,
    silenced=False,
    sealed=False,
    guard_frozen_today=False,
    reach_out_cached=False,
    now_local_minutes=700,
    quiet_start_min=60,
    quiet_end_min=480,
    daily_cap_base=3,
    sent_today=0,
    last_proactive_ts=-1e9,
    now_ts=0.0,
    unanswered_streak=0,
    contact_night_sent_today=False,
    phase="active",
)

_AXIS_VALUES = {
    "contact": [0.0, 0.55, 0.6, 0.65, 1.0],
    "expression": [0.0, 0.4, 0.45, 0.5, 1.0],
    "pressure": [0.0, 0.69, 0.7, 0.9],
    "quiet": [0.0, 0.49, 0.5, 0.9],
    "budget": [1.0, 0.31, 0.3, 0.0],
    "p": [0.0, 0.1, 0.5, 1.0],
    "enabled": [True, False],
    "silenced": [True, False],
    "sealed": [True, False],
    "guard_frozen_today": [True, False],
    "reach_out_cached": [True, False],
    "now_local_minutes": [0, 30, 45, 60, 300, 450, 470, 479, 480, 700, 1439],
    "daily_cap_base": [0, 1, 3],
    "sent_today": [0, 1, 3],
    "last_proactive_ts": [-1e9, 0.0],
    "now_ts": [0.0, 100.0, 7200.0],
    "unanswered_streak": [0, 1, 2, 3],
    "contact_night_sent_today": [True, False],
    "phase": ["active", "cooling", "dormant"],
}


def test_cmp01_axis_sweep_byte_identical() -> None:
    for axis, values in _AXIS_VALUES.items():
        for v in values:
            params = dict(_BASELINE)
            params[axis] = v
            a, b = _run_both(params)
            assert (a.send, a.occasion, a.reason) == (b.send, b.occasion, b.reason), (
                axis,
                v,
                a,
                b,
            )


def test_cmp01_random_joint_sample_byte_identical() -> None:
    rng = random.Random(20260711)
    mismatches = []
    for _ in range(3000):
        params = dict(_BASELINE)
        params.update(
            {axis: rng.choice(values) for axis, values in _AXIS_VALUES.items()}
        )
        a, b = _run_both(params)
        if (a.send, a.occasion, a.reason) != (b.send, b.occasion, b.reason):
            mismatches.append((params, a, b))
    assert not mismatches, mismatches[:5]
