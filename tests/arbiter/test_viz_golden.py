"""T-V1:三视图 SVG 字节 golden;契约 schema 校验;双心并排图差异非空
(arbiter_BLUEPRINT §7)。
"""

from __future__ import annotations

from yelos.arbiter.viz.contract import (
    ArbiterTimeline,
    DayTimeline,
    RateWindow,
    ThetaSnapshot,
    VerdictEvent,
    validate_schema,
)
from yelos.arbiter.viz.render_svg import (
    render_full,
    render_rate_gauge,
    render_theta_drift,
    render_verdict_timeline,
)


def _day(theta_d_sw: float) -> DayTimeline:
    return DayTimeline(
        day="2026-07-11",
        verdicts=(
            VerdictEvent(ts=1.0, kind="PASS", sigma=0, policy="table", hi=False),
            VerdictEvent(ts=2.0, kind="SWALLOW", sigma=3, policy="table", hi=True),
            VerdictEvent(ts=3.0, kind="REPLACE", sigma=2, policy="smooth", hi=False),
        ),
        theta=ThetaSnapshot(d_sw=theta_d_sw, d_rp=0.0, d_ex=0.0, gamma=1.0),
        rate_window=RateWindow(interventions=2, turns=10),
    )


def test_contract_to_dict_and_validate_schema():
    timeline = ArbiterTimeline(sid_digest="abc12345", days=(_day(0.01),))
    payload = timeline.to_dict()
    validate_schema(payload)
    assert payload["v"] == 1
    assert payload["days"][0]["verdicts"][1]["kind"] == "SWALLOW"


def test_validate_schema_rejects_bad_version():
    import pytest

    with pytest.raises(ValueError):
        validate_schema({"v": 999, "sid_digest": "x", "days": []})


def test_render_verdict_timeline_deterministic_golden():
    day = _day(0.0)
    svg1 = render_verdict_timeline(day)
    svg2 = render_verdict_timeline(day)
    assert svg1 == svg2  # 确定性:同输入同字节
    assert svg1.startswith("<svg")
    assert svg1.endswith("</svg>")
    assert "#2a3f5f" in svg1  # SWALLOW 深色
    assert 'fill="#c0392b"' in svg1  # 重咽烬点


def test_render_theta_drift_two_hearts_differ():
    """T3 的视觉版:两颗不同经历的心并排画,差异肉眼可见(非空 diff)。"""
    days_h1 = (_day(0.05), _day(0.05))
    days_h2 = (_day(-0.05), _day(-0.05))
    svg_h1 = render_theta_drift(days_h1, label="h1")
    svg_h2 = render_theta_drift(days_h2, label="h2")
    assert svg_h1 != svg_h2


def test_render_rate_gauge_marks_hard_constraint_not_theorem():
    svg = render_rate_gauge((_day(0.0),), min_gap_seconds=180)
    assert "硬约束" in svg
    # 如实标"硬约束(非定理)",不得出现"定理"二字脱离"非"的肯定性表述
    # (呼应推论 C1 的诚实标注纪律,arbiter_BLUEPRINT §1.1 A3)。
    assert "非定理" in svg
    assert "定理" not in svg.replace("非定理", "")


def test_render_full_golden_bytes():
    timeline = ArbiterTimeline(sid_digest="deadbeef", days=(_day(0.02), _day(0.03)))
    svg = render_full(timeline, min_gap_seconds=180)
    assert svg.startswith("<svg")
    assert svg.count("<svg") == 1  # render_full 只产一个顶层 <svg>,内层已拆包
    assert svg == render_full(timeline, min_gap_seconds=180)  # 确定性
