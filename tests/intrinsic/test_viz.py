"""T-VIZ-01..03(自举 golden:首跑落盘,复跑逐字节比对)+ T-CON-01(契约 schema 往返)。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yelos.intrinsic.moments.taxonomy import MomentEntry, MomentKind
from yelos.intrinsic.viz.contract import (
    CircadianSnapshot,
    CrossingEvent,
    DayTimeline,
    FieldSample,
    IntrinsicTimeline,
    downsample_field_samples,
    validate_timeline_dict,
)
from yelos.intrinsic.viz.render_day import render_day
from yelos.intrinsic.viz.render_field import render_field
from yelos.intrinsic.viz.render_phase import render_phase

_GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden_viz"


def _golden_check(name: str, actual: str) -> None:
    """自举 golden:首次运行落盘期望值,此后逐字节比对(不存在则视为已建基线)。"""
    _GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    path = _GOLDEN_DIR / name
    if not path.exists():
        path.write_text(actual, encoding="utf-8")
        return
    expected = path.read_text(encoding="utf-8")
    assert actual == expected, f"{name} golden 不一致(渲染输出变了或不确定性)"


def _sample_day() -> DayTimeline:
    samples = tuple(
        FieldSample(t=i * 5, phi=(0.3 + 0.1 * (i % 3), 0.2, 0.4 - 0.05 * (i % 2), 0.1))
        for i in range(20)
    )
    crossings = (CrossingEvent(t=50, s=0.35, policy="field_crossing"),)
    moments = (
        MomentEntry(
            100.0, "2026-07-11", MomentKind.SPOKE, "seek", (0.5, 0.2, 0.3, 0.1), "h1"
        ),
        MomentEntry(
            200.0,
            "2026-07-11",
            MomentKind.WANT_BLOCKED_QUIET,
            "quiet_hours",
            (0.4, 0.3, 0.2, 0.0),
            "h2",
        ),
    )
    circadian = CircadianSnapshot(
        mu_min=1320, kappa=0.6, forcing_curve=tuple(0.02 * i for i in range(12))
    )
    return DayTimeline(
        day_key="2026-07-11",
        field_samples=samples,
        crossings=crossings,
        moments=moments,
        circadian=circadian,
    )


def test_viz01_render_field_deterministic_golden() -> None:
    day = _sample_day()
    svg1 = render_field(day)
    svg2 = render_field(day)
    assert svg1 == svg2
    assert svg1.startswith("<svg")
    assert 'data-channel="drive"' in svg1
    _golden_check("render_field.svg", svg1)


def test_viz02_render_day_deterministic_golden() -> None:
    day = _sample_day()
    svg1 = render_day(day)
    svg2 = render_day(day)
    assert svg1 == svg2
    assert 'data-kind="spoke"' in svg1
    _golden_check("render_day.svg", svg1)


def test_viz02_render_day_mutation_changes_output() -> None:
    """§5.3 消费断言:增删一条 moment ⇒ golden 变。"""
    day = _sample_day()
    base = render_day(day)
    mutated_moments = day.moments + (
        MomentEntry(
            300.0,
            "2026-07-11",
            MomentKind.DREAM_DELIVERED,
            "night",
            (0.6, 0.1, 0.5, 0.2),
            "h3",
        ),
    )
    day_mutated = DayTimeline(
        day_key=day.day_key,
        field_samples=day.field_samples,
        crossings=day.crossings,
        moments=mutated_moments,
        circadian=day.circadian,
    )
    mutated_svg = render_day(day_mutated)
    assert mutated_svg != base


def test_viz03_render_phase_deterministic_golden() -> None:
    circadian = CircadianSnapshot(
        mu_min=1320, kappa=0.6, forcing_curve=tuple(0.02 * i for i in range(12))
    )
    svg1 = render_phase(circadian)
    svg2 = render_phase(circadian)
    assert svg1 == svg2
    assert svg1.startswith("<svg")
    _golden_check("render_phase.svg", svg1)


def test_con01_contract_roundtrip_and_schema_validation() -> None:
    day = _sample_day()
    timeline = IntrinsicTimeline(sid_hash="abc123", policy="threshold", days=(day,))
    d = timeline.to_dict()
    validate_timeline_dict(d)  # 不应抛异常

    reparsed = json.loads(json.dumps(d, ensure_ascii=False))
    validate_timeline_dict(reparsed)
    assert reparsed["version"] == 1
    assert reparsed["days"][0]["day_key"] == "2026-07-11"


def test_con01_schema_validation_rejects_missing_field() -> None:
    day = _sample_day()
    timeline = IntrinsicTimeline(sid_hash="abc", policy="threshold", days=(day,))
    d = timeline.to_dict()
    del d["policy"]
    with pytest.raises(ValueError):
        validate_timeline_dict(d)


def test_downsample_keeps_within_cap() -> None:
    samples = [FieldSample(t=i, phi=(0.1, 0.1, 0.1, 0.1)) for i in range(1000)]
    down = downsample_field_samples(samples, max_n=288)
    assert len(down) <= 288
    assert down[0].t == 0
    assert down[-1].t == samples[-1].t
