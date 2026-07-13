"""三 SVG 渲染器 golden(维五③);结构性断言(viewBox/关键元素),

不做像素级 diff——与 primal/finitude 侧 viz 测试同款轻量惯例。
"""

from __future__ import annotations

from yelos.distill.corpus.manifest import CorpusManifest
from yelos.distill.viz import gauge_svg, radar_svg, sankey_svg


def test_gauge_svg_renders_valid_svg_with_rate():
    trace_rows = [
        {"outcome": "ok:passed/k"},
        {"outcome": "ok:passed/k"},
        {"outcome": "rejected_all:k"},
        {"outcome": "skip:absent"},
    ]
    svg = gauge_svg.render(trace_rows)
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    assert "violation gauge" in svg
    assert "ok=2 rejected=1 skipped=1 total=4" in svg


def test_gauge_svg_empty_trace_is_valid():
    svg = gauge_svg.render([])
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert "0.0%" in svg


def test_sankey_svg_renders_sources():
    manifest = CorpusManifest(
        corpus_hash="abc",
        n_entries=3,
        sources={"memory_l1": 2, "anthology": 1},
        created_day="2026-07-11",
    )
    svg = sankey_svg.render(manifest)
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert "memory_l1" in svg
    assert "anthology" in svg
    assert "n=3" in svg


def test_radar_svg_renders_occasions():
    svg = radar_svg.render({"concern": 0.2, "recover": 0.5})
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert "concern" in svg
    assert "recover" in svg


def test_radar_svg_empty_is_valid():
    svg = radar_svg.render({})
    assert svg.startswith("<svg") and svg.endswith("</svg>")
