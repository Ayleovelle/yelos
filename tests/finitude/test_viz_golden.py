"""test_viz_golden.py —— 三渲染器 golden(finitude_BLUEPRINT §11/§9)。

同款纪律(见 test_anthology_golden.py 头注):golden = 同输入产同字节输出。
含 reserve 双线、裸环、未可知沙漏;浮点格式化稳定性(`f"{v:.4f}"`)。
"""

from __future__ import annotations

from yelos.finitude.ledger_ext import LifeReplay
from yelos.finitude.projection.contracts import INFINITE_SENTINEL, ProjectionData
from yelos.finitude.viz import render_hourglass, render_p_curve, render_rings
from yelos.finitude.viz.svg_base import fmt


def test_fmt_is_stable_four_decimals():
    assert fmt(1.0) == "1.0000"
    assert fmt(0.0) == "0.0000"
    assert fmt(0.123456789) == "0.1235"


def _replay_reserve() -> LifeReplay:
    return LifeReplay(
        sid="u1",
        gen=1,
        model_id="reserve",
        p_series=[("d0", 1.0), ("d1", 0.9), ("d2", 0.8), ("d3", 0.7)],
        f_series=[("d1", 0.85), ("d2", 0.6), ("d3", 0.65)],
        epoch_events=[{"day": "d2", "epoch_to": "慢下来", "track": "A"}],
        hi_by_day={"d1": 2, "d2": 0, "d3": 0},
        concern_by_day={"d1": 0, "d2": 0, "d3": 0},
        active_day_count=3,
    )


def test_p_curve_golden_bytewise_with_reserve_dual_lines():
    replay = _replay_reserve()
    divergence = [
        {
            "day": "d3",
            "event": "b_only",
            "p": 0.7,
            "p_expr": 0.65,
            "psi": 0.2,
            "dpsi": 0.05,
            "a_epoch": "慢下来",
            "b_index": 1,
            "sid": "u1",
            "gen": 1,
        },
    ]
    svg_a = render_p_curve(replay, divergence)
    svg_b = render_p_curve(replay, divergence)
    assert svg_a == svg_b
    assert svg_a.startswith("<svg")
    assert svg_a.endswith("</svg>")
    assert 'stroke="var(--yl-moss' in svg_a  # P_expr 细线(苔)存在
    assert 'data-viz="p_curve"' in svg_a


def test_p_curve_handles_empty_replay():
    replay = LifeReplay(sid="u1", gen=1, model_id="linear")
    svg = render_p_curve(replay, [])
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")


def test_rings_golden_with_bare_ring_no_pools():
    history = [
        {
            "day": "d1",
            "epoch": "盛年",
            "active_days": 5,
            "pools": {"withdraw_heavy": ("……",)},
        },
        {"day": "d2", "epoch": "慢下来", "active_days": 3},  # 无 pools → 裸环
    ]
    svg_a = render_rings(history)
    svg_b = render_rings(history)
    assert svg_a == svg_b
    assert ">?</text>" in svg_a  # 裸环词注
    assert 'data-viz="rings"' in svg_a


def test_rings_empty_history():
    svg = render_rings([])
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")


def test_hourglass_golden_two_states_charge_and_late_life():
    proj_charge = ProjectionData(
        as_of_day="2026-01-01",
        p=0.9,
        p_expr=0.9,
        activity_rate=0.8,
        est_spend_per_active_day=0.002,
        est_remaining_active_days=450,
        est_remaining_calendar_days=560,
        epoch_etas={},
        active_days_lived=10,
    )
    proj_late = ProjectionData(
        as_of_day="2026-06-01",
        p=0.05,
        p_expr=0.05,
        activity_rate=0.3,
        est_spend_per_active_day=0.01,
        est_remaining_active_days=5,
        est_remaining_calendar_days=None,
        epoch_etas={},
        active_days_lived=400,
    )
    svg_charge = render_hourglass(proj_charge)
    svg_late = render_hourglass(proj_late)
    assert svg_charge != svg_late
    assert svg_charge == render_hourglass(proj_charge)
    assert svg_late == render_hourglass(proj_late)
    assert "未可知" in svg_late  # 日历估计缺席记号


def test_hourglass_unknown_remaining_when_lifespan_disabled():
    proj = ProjectionData(
        as_of_day="2026-01-01",
        p=0.9,
        p_expr=0.9,
        activity_rate=0.0,
        est_spend_per_active_day=0.0,
        est_remaining_active_days=INFINITE_SENTINEL,
        est_remaining_calendar_days=None,
        epoch_etas={},
        active_days_lived=0,
    )
    svg = render_hourglass(proj)
    assert "未可知" in svg
