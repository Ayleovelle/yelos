"""test_gates.py:七步闸链逐闸拦截矩阵 / 出口像枚举(T1)/ 主权 P0 全拦 /
steward 短路 / 降档拍原语让位(蓝图 §11)。
"""

from __future__ import annotations


from yelos.shadow.contracts import RawConcern
from yelos.shadow.gates.chain import GateContext, run_gate_chain


def _ctx(**overrides) -> GateContext:
    base = dict(
        mode="companion",
        shadow_enabled=True,
        sealed_or_frozen=False,
        degraded=False,
        probe_allowed=True,
        intensity_fn="linear",
    )
    base.update(overrides)
    return GateContext(**base)


def _raw(strength: float = 0.8) -> RawConcern:
    return RawConcern(ctype="warmth_drop", strength=strength, evidence=("day_drop",))


def _hyst_armed() -> dict:
    return {"armed": True, "injected_day": ""}


def test_steward_mode_short_circuits() -> None:
    state, verdict, trace = run_gate_chain(
        _raw(),
        hysteresis_state=_hyst_armed(),
        day_key="d1",
        conf=1.0,
        tier="normal",
        ctx=_ctx(mode="steward"),
    )
    assert verdict is None
    assert trace == ("mode_gate",)


def test_shadow_disabled_short_circuits() -> None:
    state, verdict, trace = run_gate_chain(
        _raw(),
        hysteresis_state=_hyst_armed(),
        day_key="d1",
        conf=1.0,
        tier="normal",
        ctx=_ctx(shadow_enabled=False),
    )
    assert verdict is None


def test_sovereignty_blocks_all() -> None:
    state, verdict, trace = run_gate_chain(
        _raw(),
        hysteresis_state=_hyst_armed(),
        day_key="d1",
        conf=1.0,
        tier="normal",
        ctx=_ctx(sealed_or_frozen=True),
    )
    assert verdict is None
    assert trace == ("mode_gate", "sovereignty")


def test_hysteresis_blocks_when_already_armed_low_strength() -> None:
    # raw.strength 不影响 hysteresis 的二值判定(见模块简化说明),但当日已
    # fire 过时应被拦。
    state, verdict, trace = run_gate_chain(
        _raw(),
        hysteresis_state={"armed": True, "injected_day": "d1"},
        day_key="d1",
        conf=1.0,
        tier="normal",
        ctx=_ctx(),
    )
    assert verdict is None
    assert trace == ("mode_gate", "sovereignty", "hysteresis")


def test_tight_tier_blocks_low_strength() -> None:
    state, verdict, trace = run_gate_chain(
        _raw(strength=0.05),
        hysteresis_state=_hyst_armed(),
        day_key="d1",
        conf=1.0,
        tier="tight",
        ctx=_ctx(),
    )
    assert verdict is None
    assert trace == ("mode_gate", "sovereignty", "hysteresis", "calibration")


def test_tight_tier_passes_sufficient_strength_but_caps_q() -> None:
    state, verdict, trace = run_gate_chain(
        _raw(strength=0.9),
        hysteresis_state=_hyst_armed(),
        day_key="d1",
        conf=1.0,
        tier="tight",
        ctx=_ctx(),
    )
    assert verdict is not None
    assert verdict.q <= 0.7
    assert verdict.do_enqueue is True


def test_silent_tier_injects_but_blocks_enqueue() -> None:
    state, verdict, trace = run_gate_chain(
        _raw(strength=0.9),
        hysteresis_state=_hyst_armed(),
        day_key="d1",
        conf=1.0,
        tier="silent",
        ctx=_ctx(),
    )
    assert verdict is not None
    assert verdict.do_inject is True
    assert verdict.do_enqueue is False


def test_degraded_budget_blocks_enqueue_but_not_inject() -> None:
    state, verdict, trace = run_gate_chain(
        _raw(strength=0.9),
        hysteresis_state=_hyst_armed(),
        day_key="d1",
        conf=1.0,
        tier="normal",
        ctx=_ctx(degraded=True),
    )
    assert verdict is not None
    assert verdict.do_inject is True
    assert verdict.do_enqueue is False


def test_probe_not_allowed_blocks_enqueue() -> None:
    state, verdict, trace = run_gate_chain(
        _raw(strength=0.9),
        hysteresis_state=_hyst_armed(),
        day_key="d1",
        conf=1.0,
        tier="normal",
        ctx=_ctx(probe_allowed=False),
    )
    assert verdict is not None
    assert verdict.do_enqueue is False


def test_normal_tier_passes_everything() -> None:
    state, verdict, trace = run_gate_chain(
        _raw(strength=0.9),
        hysteresis_state=_hyst_armed(),
        day_key="d1",
        conf=1.0,
        tier="normal",
        ctx=_ctx(),
    )
    assert verdict is not None
    assert verdict.do_inject is True
    assert verdict.do_enqueue is True
    assert trace == (
        "mode_gate",
        "sovereignty",
        "hysteresis",
        "calibration",
        "budget",
        "act3_probe",
        "whitelist",
    )


def test_familiarity_factor_scales_intensity() -> None:
    """X6:familiarity 折减(0.9+0.2*familiarity)应实际改变 intensity,证明
    该 memory 信号确实被消费,不是记了没人读(维五⑤精神)。
    """
    _state, low_fam, _t = run_gate_chain(
        _raw(strength=0.9),
        hysteresis_state=_hyst_armed(),
        day_key="d1",
        conf=1.0,
        tier="normal",
        ctx=_ctx(familiarity_factor=0.9),
    )
    _state, high_fam, _t = run_gate_chain(
        _raw(strength=0.9),
        hysteresis_state=_hyst_armed(),
        day_key="d1",
        conf=1.0,
        tier="normal",
        ctx=_ctx(familiarity_factor=1.1),
    )
    assert high_fam.intensity > low_fam.intensity


def test_familiarity_factor_defaults_to_neutral() -> None:
    _state, verdict, _t = run_gate_chain(
        _raw(strength=0.9),
        hysteresis_state=_hyst_armed(),
        day_key="d1",
        conf=1.0,
        tier="normal",
        ctx=_ctx(),
    )
    assert _ctx().familiarity_factor == 1.0
    assert verdict is not None


# --- 出口像枚举(SHTOM-T1)--------------------------------------------------


def test_exit_image_enumeration() -> None:
    """出口像空间有限可枚举:intensity/q 是有限精度网格,ctype 取自四检测器
    枚举闭包,do_inject/do_enqueue 是布尔。穷举一批输入,断言像落在枚举内。
    """
    from yelos.shadow.binding_v2 import CTYPES

    seen_ctypes = set()
    seen_bool_pairs = set()
    for strength in (0.0, 0.3, 0.6, 0.9, 1.0):
        for conf in (0.0, 0.5, 1.0):
            for tier in ("observe", "normal", "tight", "silent"):
                state, verdict, _ = run_gate_chain(
                    RawConcern(ctype="rhythm_break", strength=strength, evidence=()),
                    hysteresis_state=_hyst_armed(),
                    day_key="d1",
                    conf=conf,
                    tier=tier,
                    ctx=_ctx(),
                )
                if verdict is not None:
                    seen_ctypes.add(verdict.ctype)
                    seen_bool_pairs.add((verdict.do_inject, verdict.do_enqueue))
                    assert round(verdict.intensity, 3) == verdict.intensity
                    assert round(verdict.q, 3) == verdict.q
    assert seen_ctypes <= set(CTYPES)
    assert seen_bool_pairs <= {(True, True), (True, False), (False, False)}
