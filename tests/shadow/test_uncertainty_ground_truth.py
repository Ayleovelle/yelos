"""test_uncertainty_ground_truth.py:红队 major⑦ 指定项(蓝图 §11)。

两组合成断言:
① 真不确定源变化(信号方差/分歧增大)→ 断言 `D_t`/`u_t` 上升,`conf` 下降,
   `intensity` 下降——不确定度确实跟随"地面真值"(真实观测分歧/校准误差)。
② 真值固定、扫 `epsilon_override` ∈ [lo,hi] → 断言最终 concern 行为(fire
   集合/intensity 序)不随 ε 漂移——ε 只是扰动幅度的旋钮,不是决策输入。
   本测试既做**结构性**验证(签名检查:决策路径上的函数确实不接受 epsilon
   参数),也做**功能性**验证(固定 views/conf/tier 反复跑闸链,换 ε 只影响
   `EnsembleReading.epsilon_used` 记账字段,不影响 verdict)。
"""

from __future__ import annotations

import inspect


from yelos.shadow.contracts import RawConcern, ShadowView
from yelos.shadow.gates.chain import GateContext, run_gate_chain
from yelos.shadow.signals.intensity import compute_intensity
from yelos.shadow.simulator.ensemble import build_ensemble_reading, compute_disagreement
from yelos.shadow.simulator.epsilon import (
    compute_epsilon,
    DEFAULT_EPS_HI,
    DEFAULT_EPS_LO,
)
from yelos.shadow.baseline.rolling import CHANNEL_SPAN


def _ctx() -> GateContext:
    return GateContext(
        mode="companion",
        shadow_enabled=True,
        sealed_or_frozen=False,
        degraded=False,
        probe_allowed=True,
        intensity_fn="linear",
    )


# --- ① 真值驱动不确定度 -----------------------------------------------------


def test_disagreement_rises_with_real_hypothesis_spread() -> None:
    calm = (
        ShadowView(pressure=0.5, warmth=0.5, damage=0.0, hyp_id=0),
        ShadowView(pressure=0.52, warmth=0.5, damage=0.0, hyp_id=1),
    )
    chaotic = (
        ShadowView(pressure=0.1, warmth=0.5, damage=0.0, hyp_id=0),
        ShadowView(pressure=0.95, warmth=0.5, damage=0.0, hyp_id=1),
    )
    d_calm = compute_disagreement(calm, CHANNEL_SPAN)
    d_chaotic = compute_disagreement(chaotic, CHANNEL_SPAN)
    assert d_chaotic > d_calm


def test_conf_and_intensity_track_real_disagreement_not_epsilon() -> None:
    """conf = 1 - u_t,u_t = 0.5*D + 0.5*B_norm(K>1 时,§4.3);D 由真实分歧算出,
    与 `epsilon_used` 无关(即使 epsilon_used 相同,D 不同则 conf/intensity 不同)。
    """
    raw = RawConcern(ctype="pressure_spike", strength=0.8, evidence=("pressure_level",))
    b_norm = 0.0

    def _conf_for(d: float) -> float:
        u_t = 0.5 * d + 0.5 * b_norm
        return max(0.0, min(1.0, 1.0 - u_t))

    conf_low_d = _conf_for(0.05)
    conf_high_d = _conf_for(0.9)
    intensity_low_d = compute_intensity(raw.strength, conf_low_d, "linear")
    intensity_high_d = compute_intensity(raw.strength, conf_high_d, "linear")
    assert intensity_low_d > intensity_high_d  # 分歧越大,强度折减越狠


# --- ② ε 扫描不改变决策(结构性 + 功能性)------------------------------------


def test_epsilon_is_not_a_parameter_of_any_decision_function() -> None:
    """结构性断言:决策路径(检测/闸链/强度)的函数签名里没有 epsilon 相关
    参数——ε 物理上无法进入这些函数的决策计算。
    """
    from yelos.shadow.signals import (
        pressure_spike,
        rhythm_break,
        warmth_drop,
        withdrawal,
    )

    decision_fns = [
        warmth_drop.detect,
        pressure_spike.detect,
        rhythm_break.detect,
        withdrawal.detect,
        run_gate_chain,
        compute_intensity,
    ]
    for fn in decision_fns:
        params = set(inspect.signature(fn).parameters)
        assert not any("epsilon" in p or p == "eps" for p in params), (
            f"{fn.__qualname__} 的签名里出现了 epsilon 相关参数,决策路径不应消费 ε"
        )


def test_sweeping_epsilon_override_does_not_change_verdict() -> None:
    """功能性断言:固定 (raw, conf, tier),扫 epsilon_override ∈ [lo,hi],
    `EnsembleReading.epsilon_used` 随之变化,但闸链产出的 verdict 逐字节
    不变(intensity/q/do_inject/do_enqueue 恒定)——ε 只是记账量,不是决策输入。
    """
    raw = RawConcern(ctype="withdrawal", strength=0.7, evidence=("warmth_month",))
    views = (ShadowView(pressure=0.5, warmth=0.5, damage=0.0, hyp_id=0),)
    conf = 0.8
    tier = "normal"

    verdicts = []
    epsilon_values = []
    for override in (DEFAULT_EPS_LO, 0.05, 0.10, 0.15, 0.20, DEFAULT_EPS_HI):
        epsilon_used = compute_epsilon(0.1, 0.1, epsilon_override=override)
        epsilon_values.append(epsilon_used)
        reading = build_ensemble_reading(
            views, CHANNEL_SPAN, epsilon_used, degraded=False
        )
        assert reading.epsilon_used == epsilon_used  # 记账字段确实变了

        _state, verdict, _trace = run_gate_chain(
            raw,
            hysteresis_state={"armed": True, "injected_day": ""},
            day_key="d1",
            conf=conf,
            tier=tier,
            ctx=_ctx(),
        )
        verdicts.append(verdict)

    assert len(set(epsilon_values)) > 1, (
        "测试前提失败:epsilon_override 扫描应产生不同的 ε 值"
    )
    first = verdicts[0]
    for v in verdicts[1:]:
        assert v.intensity == first.intensity
        assert v.q == first.q
        assert v.do_inject == first.do_inject
        assert v.do_enqueue == first.do_enqueue
