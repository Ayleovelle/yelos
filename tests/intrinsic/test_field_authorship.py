"""T-FLD-04 反转录 + AX-5 字段白名单(intrinsic_BLUEPRINT §0.2/§8.2)。"""

from __future__ import annotations

from yelos.intrinsic.field.impacts import SURFACE_WHITELIST, from_surface
from yelos.intrinsic.field.integrators import EulerIntegrator
from yelos.intrinsic.field.state import FieldParams, FieldState


def test_ax5_whitelist_is_dotted_paths() -> None:
    assert len(SURFACE_WHITELIST) >= 5
    for path in SURFACE_WHITELIST:
        assert "." in path


def test_ax5_constant_surface_impact_is_deterministic_and_repeatable() -> None:
    """恒定 Surface → from_surface 恒定输出(同输入同输出,非"每次不同"的随机转录)。"""
    params = FieldParams()
    surface = {
        "state": {
            "needs": {"expression": 0.5, "quiet": 0.4, "contact": 0.3},
            "boundary": {"pressure": 0.5},
        }
    }
    v1 = from_surface(surface, (), params)
    v2 = from_surface(surface, (), params)
    assert v1 == v2


def test_fld04_field_still_evolves_when_surface_constant() -> None:
    """[T-FLD-04] Surface 恒定,场仍演化(衰减 + 强迫仍在走,不是转录)。"""
    params = FieldParams()
    integ = EulerIntegrator()
    surface = {
        "state": {
            "needs": {"expression": 0.5, "quiet": 0.4, "contact": 0.3},
            "boundary": {"pressure": 0.5},
        }
    }
    phi = FieldState(drive=0.9, languor=0.9, longing=0.9, afterglow=0.9, ts=0.0)
    trace = [phi]
    for i in range(30):
        impacts = from_surface(surface, (), params)
        forcing_term = (0.02, 0.02, 0.02, 0.02)  # 模拟持续强迫(非零,昼夜曲线恒非零)
        phi = integ.step(phi, 1.0, forcing_term, impacts, params)
        trace.append(phi)

    # Surface 输入端每步恒定(impacts 恒定),但 phi 轨迹本身不是常数——
    # 因为 decay_term 持续把 phi 拉向 eq,forcing 项持续叠加。
    distinct_values = {round(s.drive, 6) for s in trace}
    assert len(distinct_values) > 1, "场在恒定 Surface 下仍应演化,不应冻结为单一值"

    # 且 phi 不是 impacts 向量的仿射转录:impacts 恒定,但 phi 逐步单调地脱离
    # 初始值向 eq 侧移动(衰减项主导轨迹形状,而非 impacts 决定绝对值)。
    assert trace[-1].drive != trace[0].drive
