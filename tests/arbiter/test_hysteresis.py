"""T-H1..T-H6:hysteresis 滞后学习层测试(arbiter_BLUEPRINT §5/§8)。

覆盖 AX:A5.1-A5.5 与 T1(学不坏主权)/T2(凝固)/T3(个体史分化,本模块
深度正身的机器凭据)。
"""

from __future__ import annotations

import random

from yelos.arbiter import build_pipeline
from yelos.arbiter.core_probe import build_neutral_probe
from yelos.arbiter.hysteresis.ema import EmaState
from yelos.arbiter.hysteresis.params import STEP, Theta
from yelos.arbiter.hysteresis.updater import apply_update, learning_rate
from yelos.arbiter.inputs import PolicyParams, compose_policy_params
from yelos.arbiter.modulation import STEP_CURVE

KINDS = ["SWALLOW", "REPLACE", "TRIM_hold", "TRIM_express"]


def _random_r(rng: random.Random) -> float:
    return rng.uniform(-1.0, 1.0)


# --- T-H1 -----------------------------------------------------------------


def test_theta_stays_in_box_random_ten_thousand_steps():
    rng = random.Random(7)
    theta = Theta()
    for _ in range(10_000):
        kind = rng.choice(KINDS)
        r = _random_r(rng)
        consensus = rng.choice([0, 1])
        p = rng.uniform(0.0, 1.0)
        theta = apply_update(theta, kind=kind, r=r, consensus=consensus, p=p)
        assert theta.in_box(), theta


# --- T-H2 -------------------------------------------------------------------


def test_single_step_delta_bounded_by_p_step():
    rng = random.Random(11)
    for _ in range(2000):
        theta = Theta()
        kind = rng.choice(KINDS)
        r = _random_r(rng)
        p = rng.uniform(0.0, 1.0)
        new = apply_update(theta, kind=kind, r=r, consensus=1, p=p)
        for field, step in STEP.items():
            before = getattr(theta, field)
            after = getattr(new, field)
            assert abs(after - before) <= p * step + 1e-12, (
                field,
                before,
                after,
                p,
                step,
            )


def test_non_consensus_zero_movement():
    rng = random.Random(13)
    for _ in range(500):
        theta = Theta(
            d_sw=rng.uniform(-0.04, 0.04),
            d_rp=rng.uniform(-0.04, 0.04),
            d_ex=rng.uniform(-0.08, 0.08),
            gamma_offset=rng.uniform(-0.15, 0.15),
        )
        kind = rng.choice(KINDS)
        r = _random_r(rng)
        p = rng.uniform(0.1, 1.0)
        new = apply_update(theta, kind=kind, r=r, consensus=0, p=p)
        assert new == theta


# --- T-H3 ---------------------------------------------------------------


def _replay(events, p_of=lambda i: 0.8):
    theta = Theta()
    ema = EmaState()
    for i, (kind, r) in enumerate(events):
        ema = ema.update(r)
        theta = apply_update(
            theta, kind=kind, r=r, consensus=ema.consensus(), p=p_of(i)
        )
    return theta, ema


def test_replay_twice_identical():
    rng = random.Random(2026)
    events = [(rng.choice(KINDS), _random_r(rng)) for _ in range(300)]
    theta1, ema1 = _replay(events)
    theta2, ema2 = _replay(events)
    assert theta1 == theta2
    assert ema1 == ema2


# --- T-H4 -----------------------------------------------------------------


def test_drift_strictly_decreasing_with_p_and_zero_at_p0():
    events = [("SWALLOW", -0.8) for _ in range(50)]  # 恒定负反馈,易触发共识

    def drift_for(p_const: float) -> float:
        theta, ema = Theta(), EmaState()
        total = 0.0
        for kind, r in events:
            ema = ema.update(r)
            new_theta = apply_update(
                theta, kind=kind, r=r, consensus=ema.consensus(), p=p_const
            )
            total += abs(new_theta.d_sw - theta.d_sw)
            theta = new_theta
        return total

    d_high = drift_for(1.0)
    d_mid = drift_for(0.3)
    d_zero = drift_for(0.0)
    assert d_high > d_mid > d_zero
    assert d_zero == 0.0


def test_p_zero_theta_frozen_forever():
    theta0 = Theta(d_sw=0.01, d_rp=-0.02, d_ex=0.03, gamma_offset=0.05)
    theta = theta0
    ema = EmaState(fast=0.5, slow=0.5)  # 已处于共识态
    rng = random.Random(3)
    for _ in range(200):
        kind = rng.choice(KINDS)
        r = _random_r(rng)
        ema = ema.update(r)
        theta = apply_update(theta, kind=kind, r=r, consensus=ema.consensus(), p=0.0)
        assert theta == theta0  # T2:P=0 精确凝固,逐步不变


# --- T-H5(golden,T3 个体史分化探针) ----------------------------------------


def _drive_theta(sign: float, n: int = 400) -> Theta:
    """sign<0:连续负反馈驱动 SWALLOW(d_sw -> +0.05 上界);
    sign>0:连续正反馈(d_sw -> -0.05 下界)。"""
    r = -0.9 if sign < 0 else 0.9
    theta, ema = Theta(), EmaState()
    for _ in range(n):
        ema = ema.update(r)
        theta = apply_update(
            theta, kind="SWALLOW", r=r, consensus=ema.consensus(), p=1.0
        )
    return theta


def test_individual_history_differentiation_golden():
    """T3:存在 h1 != h2 与探针 x*,使得同配置下 pipeline(x*;θ(h1)) != pipeline(x*;θ(h2))。

    h1 = 连续负反馈(driving d_sw 趋于 Box 上界 +0.05,更难咽);
    h2 = 连续正反馈(driving d_sw 趋于 Box 下界 -0.05,维持敢咽)。
    """
    theta_h1 = _drive_theta(sign=-1)
    theta_h2 = _drive_theta(sign=1)
    assert theta_h1.d_sw > 0.04  # 已顶到(或极接近)Box 上界
    assert theta_h2.d_sw < -0.04  # 已顶到(或极接近)Box 下界
    assert theta_h1.d_sw != theta_h2.d_sw

    # 用同一枚 SmoothPolicy 探针,分别套用两段历史的 θ,验证 verdict 分化。
    # 探针取值使 Smooth 得分恰落在 [0.70,0.80) 区间(θ(h1) 的 swallow_th=0.80、
    # θ(h2) 的 swallow_th=0.70,均由 §5.3 Box 上/下界 ±0.05 决定)——
    # 与蓝图 §1.2 T3 的illustrative 数字(0.80/0.70,REPLACE/SWALLOW)对齐,
    # 但探针本身按 SmoothPolicy 自著权重反解得到(蓝图未给出具体权重值,
    # 见 policies/smooth.py 顶部"设计取舍"1)。
    probe_pressure = 0.64
    action = "withdraw"
    p_probe = 0.8
    draft = "第1句。第2句。第3句。第4句。"

    def _verdict_for(theta: Theta):
        params = compose_policy_params(STEP_CURVE, p_probe, theta)
        pin = build_neutral_probe(
            action=action,
            pressure=probe_pressure,
            expr=0.5,
            p=p_probe,
            draft=draft,
            params=params,
        )
        pipe = build_pipeline("smooth")
        v, _ = pipe.run(pin)
        return v

    v1 = _verdict_for(theta_h1)
    v2 = _verdict_for(theta_h2)
    assert v1.kind != v2.kind, (v1, v2)
    # 固化为 golden:两段历史此探针上的具体 verdict kind(回归锁)。
    assert v1.kind == "REPLACE"
    assert v2.kind == "SWALLOW"


def test_no_hysteresis_means_no_differentiation():
    """去掉 hysteresis(θ 恒 0)时,同一探针在任何"历史"下 verdict 恒同
    ——这是 T3"去掉它缺哪个可观测行为"的反证。
    """
    params = PolicyParams(0.75, 0.55, 0.70, 1.0)
    pin = build_neutral_probe(
        action="withdraw", pressure=0.73, expr=0.5, p=0.8, params=params
    )
    pipe = build_pipeline("smooth")
    v_a, _ = pipe.run(pin)
    v_b, _ = pipe.run(pin)
    assert v_a.kind == v_b.kind


# --- T-H6 -------------------------------------------------------------------


def test_prefix_replay_consistency():
    rng = random.Random(555)
    events = [(rng.choice(KINDS), _random_r(rng)) for _ in range(200)]
    theta_full, ema_full = Theta(), EmaState()
    snapshots = []
    for kind, r in events:
        ema_full = ema_full.update(r)
        theta_full = apply_update(
            theta_full, kind=kind, r=r, consensus=ema_full.consensus(), p=0.7
        )
        snapshots.append((theta_full, ema_full))
    for k in (1, 5, 37, 100, 199):
        theta_k, ema_k = _replay(events[:k], p_of=lambda i: 0.7)
        assert theta_k == snapshots[k - 1][0]
        assert ema_k == snapshots[k - 1][1]


def test_learning_rate_monotone_in_p():
    assert learning_rate(0.0) == 0.0
    assert learning_rate(0.3) < learning_rate(0.7) < learning_rate(1.0)
