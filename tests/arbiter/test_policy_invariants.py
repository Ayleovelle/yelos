"""T-P1/T-P2/T-P3:全策略公共不变量(arbiter_BLUEPRINT §3.6)。

T-P1:P0 ⇒ PASS,∀策略 × θ∈Box 顶点网格。
T-P2:千轮随机轨迹回放,不应期恒守 + 介入率 <= 1/min_gap(推论 C1 的
      统计验证,如实标"推论",不称定理)。
T-P3:同 action 输入单调:pressure 升 σ 不降;narrow(P<=0.15)下 σ 不升。
"""

from __future__ import annotations

import random

import pytest

from yelos.arbiter import build_pipeline
from yelos.arbiter.hysteresis.params import BOX_VERTICES
from yelos.arbiter.inputs import PolicyInput, PolicyParams, compose_policy_params
from yelos.arbiter.lattice import sigma_of
from yelos.arbiter.modulation import STEP_CURVE
from yelos.core.arbiter import ArbiterInput

POLICY_IDS = ["table", "smooth", "conservative", "duel"]


# --- T-P1 -------------------------------------------------------------


@pytest.mark.parametrize("policy_id", POLICY_IDS)
def test_p0_pass_all_policies_all_theta_box_vertices(policy_id):
    pipe_by_theta = [
        (theta, build_pipeline(policy_id, theta=theta)) for theta in BOX_VERTICES
    ]
    rng = random.Random(1)
    for _ in range(20):
        base = ArbiterInput(
            session_id="s",
            day_key="2026-07-11",
            draft="很长的草稿内容。第二句在这里。第三句在这里。第四句在这里。",
            surface={
                "decision": {"action": rng.choice(["withdraw", "hold", "express"])},
                "state": {
                    "boundary": {"pressure": rng.random()},
                    "needs": {"expression": rng.random()},
                },
                "guard": {"allowed": True},
            },
            p=rng.random(),
            bound=rng.choice([False, True]),
            enabled=rng.choice([False, True]) if True else True,
            silenced=rng.choice([True, False]),
            is_self=False,
            has_plain=True,
            has_non_plain=False,
            now_ts=100000.0,
            last_intervention_ts=0.0,
            min_gap_seconds=180,
        )
        # 强制至少一个 P0 条件为真(未绑定/禁用/静默三选一)
        if base.bound and base.enabled and not base.silenced:
            base = ArbiterInput(**{**base.__dict__, "silenced": True})
        for theta, pipe in pipe_by_theta:
            params = compose_policy_params(STEP_CURVE, base.p, theta)
            pin = PolicyInput(
                base=base, surface_age_s=0.0, daily_interventions=0, params=params
            )
            verdict, _ = pipe.run(pin)
            assert verdict.kind == "PASS", (policy_id, theta, base)


# --- T-P2 ---------------------------------------------------------------


@pytest.mark.parametrize("policy_id", POLICY_IDS)
def test_refractory_all_policies_random_trajectory(policy_id):
    rng = random.Random(42)
    pipe = build_pipeline(policy_id)
    min_gap = 180
    now = 0.0
    last_intervention_ts = -10_000.0
    n_turns = 1000
    n_interventions = 0
    for _ in range(n_turns):
        now += rng.uniform(1, 60)
        base = ArbiterInput(
            session_id="s",
            day_key="2026-07-11",
            draft="今天的内容。第二句。第三句。第四句。",
            surface={
                "decision": {"action": rng.choice(["withdraw", "hold"])},
                "state": {
                    "boundary": {"pressure": rng.random()},
                    "needs": {"expression": rng.random()},
                },
                "guard": {"allowed": True},
            },
            p=rng.uniform(0.2, 1.0),
            bound=True,
            enabled=True,
            silenced=False,
            is_self=False,
            has_plain=True,
            has_non_plain=False,
            now_ts=now,
            last_intervention_ts=last_intervention_ts,
            min_gap_seconds=min_gap,
        )
        params = PolicyParams(0.75, 0.55, 0.70, 1.0)
        pin = PolicyInput(
            base=base, surface_age_s=0.0, daily_interventions=0, params=params
        )
        verdict, _ = pipe.run(pin)
        if sigma_of(verdict) >= 1:
            # 不应期必须已过(A3):否则说明某策略绕过了守卫/内核的 min_gap。
            assert now - last_intervention_ts >= min_gap, (
                policy_id,
                now,
                last_intervention_ts,
            )
            last_intervention_ts = now
            n_interventions += 1
    elapsed = now
    rate = n_interventions / elapsed
    # 推论 C1(平凡推论,非定理):长程介入率 <= 1/min_gap。
    assert rate <= 1.0 / min_gap + 1e-9, (policy_id, rate)


# --- T-P3 -----------------------------------------------------------------


def _build(action, pressure, expr, p, params):
    base = ArbiterInput(
        session_id="s",
        day_key="2026-07-11",
        draft="今天的内容。第二句。第三句。第四句。",
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
        now_ts=100000.0,
        last_intervention_ts=0.0,
        min_gap_seconds=180,
    )
    return PolicyInput(
        base=base, surface_age_s=0.0, daily_interventions=0, params=params
    )


@pytest.mark.parametrize("policy_id", POLICY_IDS)
def test_pressure_monotone_sigma_non_decreasing(policy_id):
    rng = random.Random(7)
    pipe = build_pipeline(policy_id)
    params = PolicyParams(0.75, 0.55, 0.70, 1.0)
    for _ in range(200):
        action = rng.choice(["withdraw", "hold"])
        expr = rng.random()
        p = rng.uniform(0.2, 1.0)  # 保持非收窄区间,narrow 是独立的第二条断言
        pressures = sorted(rng.random() for _ in range(4))
        sigmas = []
        for pr in pressures:
            pin = _build(action, pr, expr, p, params)
            v, _ = pipe.run(pin)
            sigmas.append(sigma_of(v))
        assert sigmas == sorted(sigmas), (policy_id, action, expr, p, pressures, sigmas)


@pytest.mark.parametrize("policy_id", POLICY_IDS)
def test_narrow_sigma_non_increasing(policy_id):
    """P<=0.15(narrow)相对同一输入 P 更高时,σ 不升。"""
    rng = random.Random(11)
    pipe = build_pipeline(policy_id)
    params = PolicyParams(0.75, 0.55, 0.70, 1.0)
    for _ in range(200):
        action = rng.choice(["withdraw", "hold"])
        pressure = rng.random()
        expr = rng.random()
        p_high = rng.uniform(0.5, 1.0)
        p_narrow = rng.uniform(0.0, 0.15)
        v_high, _ = pipe.run(_build(action, pressure, expr, p_high, params))
        v_narrow, _ = pipe.run(_build(action, pressure, expr, p_narrow, params))
        assert sigma_of(v_narrow) <= sigma_of(v_high), (
            policy_id,
            action,
            pressure,
            expr,
            p_high,
            p_narrow,
            v_high,
            v_narrow,
        )
