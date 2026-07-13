"""test_viz_golden.py:三渲染器 SVG golden / 契约 schema 往返(蓝图 §11)。"""

from __future__ import annotations

import json

from yelos.shadow.viz.contracts import (
    ConcernEvent,
    DeviationPoint,
    ReliabilityBin,
    build_calibration_reliability,
    build_concern_timeline,
    build_deviation_band,
)
from yelos.shadow.viz.svg_render import (
    render_concern_timeline,
    render_deviation_band,
    render_reliability,
)


def _points() -> list[DeviationPoint]:
    return [
        DeviationPoint(
            ts=float(i),
            ch="warmth",
            h0=0.5 + 0.1 * i,
            hyp_min=0.4,
            hyp_max=0.6,
            baseline_day=0.5,
            baseline_week=0.5,
            baseline_month=0.5,
            epsilon=0.1,
            disagreement=0.2,
        )
        for i in range(3)
    ]


def _events() -> list[ConcernEvent]:
    return [
        ConcernEvent(
            ts=float(i),
            ctype="warmth_drop",
            fire=(i == 1),
            intensity=0.5,
            q=0.6,
            y=None,
            tier="normal",
            beta=0.0,
            gate_trace=("mode_gate",),
        )
        for i in range(3)
    ]


def test_deviation_band_contract_is_json_serializable() -> None:
    contract = build_deviation_band(_points())
    dumped = json.dumps(contract, ensure_ascii=False)
    reloaded = json.loads(dumped)
    assert reloaded["schema"] == "shadow_deviation_band.v1"
    assert len(reloaded["points"]) == 3


def test_concern_timeline_contract_is_json_serializable() -> None:
    contract = build_concern_timeline(_events())
    dumped = json.dumps(contract, ensure_ascii=False)
    reloaded = json.loads(dumped)
    assert reloaded["schema"] == "concern_timeline.v1"
    assert len(reloaded["events"]) == 3


def test_calibration_reliability_contract_is_json_serializable() -> None:
    bins = (ReliabilityBin(q_center=0.5, actual_freq=0.4, count=10),)
    contract = build_calibration_reliability({"warmth_drop": (0.12, 10, bins)})
    dumped = json.dumps(contract, ensure_ascii=False)
    reloaded = json.loads(dumped)
    assert reloaded["per_ctype"]["warmth_drop"]["brier"] == 0.12


def test_render_deviation_band_is_deterministic_golden() -> None:
    svg1 = render_deviation_band(_points())
    svg2 = render_deviation_band(_points())
    assert svg1 == svg2
    assert svg1.startswith("<svg")
    assert svg1.endswith("</svg>")


def test_render_concern_timeline_is_deterministic_golden() -> None:
    svg1 = render_concern_timeline(_events())
    svg2 = render_concern_timeline(_events())
    assert svg1 == svg2


def test_render_reliability_is_deterministic_golden() -> None:
    bins = (ReliabilityBin(q_center=0.5, actual_freq=0.4, count=10),)
    svg1 = render_reliability(0.12, 10, bins)
    svg2 = render_reliability(0.12, 10, bins)
    assert svg1 == svg2
    assert "brier=0.1200" in svg1


def test_render_reliability_handles_none_brier() -> None:
    svg = render_reliability(None, 0, ())
    assert "brier=nan" in svg


def test_render_empty_inputs_do_not_crash() -> None:
    assert render_deviation_band([]).startswith("<svg")
    assert render_concern_timeline([]).startswith("<svg")
    assert render_reliability(None, 0, ()).startswith("<svg")
