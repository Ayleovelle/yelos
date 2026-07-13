"""T-FLD-01, T-FLD-02, T-FLD-03 + 步长鲁棒 + euler/trapezoid 对比(intrinsic_BLUEPRINT §8.2)。"""

from __future__ import annotations

import math

from yelos.intrinsic.field.dynamics import decay_term
from yelos.intrinsic.field.impacts import event_impact, from_surface
from yelos.intrinsic.field.integrators import EulerIntegrator, TrapezoidIntegrator
from yelos.intrinsic.field.state import FieldParams, FieldState


def _hashed_unit(i: int, j: int) -> float:
    """确定性伪随机(结构测试用,非 AX-7 场景,不落 hash 族注册表)。"""
    x = math.sin(i * 12.9898 + j * 78.233) * 43758.5453
    return x - math.floor(x)


def test_ax1_bounded_no_nan_10k_steps() -> None:
    params = FieldParams()
    integ = EulerIntegrator()
    phi = FieldState.neutral(0.0)
    for i in range(10_000):
        forcing = (
            0.3 * math.sin(i / 37.0),
            0.2 * math.cos(i / 53.0),
            -0.1 * math.sin(i / 19.0),
            0.15 * math.cos(i / 29.0),
        )
        impacts = event_impact("concern", _hashed_unit(i, 1), params)
        phi = integ.step(phi, 1.0, forcing, impacts, params)
        for v in phi.vec():
            assert 0.0 <= v <= 1.0
            assert not math.isnan(v)


def test_ax2_convergence_no_forcing_no_impacts() -> None:
    params = FieldParams()
    integ = EulerIntegrator()
    phi = FieldState(drive=0.9, languor=0.9, longing=0.9, afterglow=0.9, ts=0.0)
    zero: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    for _ in range(2000):
        phi = integ.step(phi, 1.0, zero, zero, params)
    for v, eq in zip(phi.vec(), params.eq):
        assert abs(v - eq) < 1e-3


def test_ax2_decay_term_sign_toward_eq() -> None:
    params = FieldParams()
    phi_high = (0.9, 0.9, 0.9, 0.9)
    d = decay_term(phi_high, params)
    for dv, eq, x in zip(d, params.eq, phi_high):
        if x > eq:
            assert dv < 0.0


def test_ax4_impact_bounded() -> None:
    params = FieldParams(i_max=0.6)
    for kind in ("user_turn", "her_word", "swallowed", "concern", "reunion"):
        v = event_impact(kind, 1.0, params)
        norm = math.sqrt(sum(x * x for x in v))
        assert norm <= params.i_max + 1e-9


def test_ax4_from_surface_bounded_even_with_many_events() -> None:
    params = FieldParams(i_max=0.6)
    surface = {
        "state": {
            "needs": {"expression": 0.9, "quiet": 0.8, "contact": 0.1},
            "boundary": {"pressure": 0.9},
        }
    }
    events = tuple(
        (k, 1.0) for k in ("user_turn", "her_word", "swallowed", "concern", "reunion")
    )
    v = from_surface(surface, events, params)
    norm = math.sqrt(sum(x * x for x in v))
    assert norm <= params.i_max + 1e-9


def test_dt_halving_robustness_bounded_divergence() -> None:
    """步长减半:两条轨迹(dt=1 vs dt=0.5,累计到同一末时刻)偏差有界。"""
    params = FieldParams()
    integ = EulerIntegrator()
    phi_full = FieldState(drive=0.8, languor=0.1, longing=0.1, afterglow=0.0, ts=0.0)
    phi_half = phi_full

    forcing = (0.02, 0.01, -0.01, 0.005)
    impacts = (0.0, 0.0, 0.0, 0.0)

    for _ in range(50):
        phi_full = integ.step(phi_full, 1.0, forcing, impacts, params)
    for _ in range(100):
        phi_half = integ.step(phi_half, 0.5, forcing, impacts, params)

    for a, b in zip(phi_full.vec(), phi_half.vec()):
        assert abs(a - b) < 0.05


def test_euler_trapezoid_golden_comparison_close() -> None:
    """两积分器同输入下轨迹接近(数值方案不计维二,§2.2);差异有界。"""
    params = FieldParams()
    e = EulerIntegrator()
    t = TrapezoidIntegrator()
    phi_e = FieldState.neutral(0.0)
    phi_t = FieldState.neutral(0.0)
    forcing = (0.02, -0.01, 0.015, 0.0)
    impacts = (0.05, 0.0, 0.0, 0.1)
    for _ in range(500):
        phi_e = e.step(phi_e, 1.0, forcing, impacts, params)
        phi_t = t.step(phi_t, 1.0, forcing, impacts, params)
    for a, b in zip(phi_e.vec(), phi_t.vec()):
        assert abs(a - b) < 0.05
