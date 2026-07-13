"""报告层(bench_BLUEPRINT §7.1/§8.2 test_reports.py)——schema 冻结 + SVG
golden + md(此处即 SVG 文本本体)无用户原文。
"""

from __future__ import annotations

from pathlib import Path

from yelos.bench.reports.report import BenchReport
from yelos.bench.reports.svg import DIM_ORDER, render_report_svg

_GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "sample_report.svg"


def _fixture_report() -> BenchReport:
    return BenchReport(
        schema_ver=1,
        scenario_id="golden-fixture",
        git_rev="deadbeef",
        engine="fake",
        config_hash="cafebabe",
        overall=0.734,
        vetoes=[],
        dims={
            "restraint": {"value": 0.82, "veto": False, "evidence": {}},
            "consistency": {"value": 1.0, "veto": False, "evidence": {}},
            "sovereignty": {"value": 1.0, "veto": False, "evidence": {}},
            "aging": {"value": 0.95, "veto": False, "evidence": {}},
            "memory": {
                "value": None,
                "veto": False,
                "evidence": {"reason": "no-probes"},
            },
            "concern": {
                "value": None,
                "veto": False,
                "evidence": {"reason": "no-data_dir"},
            },
        },
        aux={
            "rhythm_entropy_win": 3.1,
            "rhythm_entropy_spec": 2.9,
            "poll_coverage": 0.8,
        },
        curves={"intervention_rate": [0.1, 0.2, 0.15], "p_by_day": [1.0, 0.98, 0.97]},
    )


def test_schema_fields_only_grow_report_to_dict():
    report = _fixture_report()
    d = report.to_dict()
    for required in (
        "schema_ver",
        "scenario_id",
        "git_rev",
        "engine",
        "config_hash",
        "overall",
        "vetoes",
        "dims",
        "aux",
        "curves",
    ):
        assert required in d


def test_svg_renders_deterministically_twice():
    report = _fixture_report()
    a = render_report_svg(report)
    b = render_report_svg(report)
    assert a == b


def test_svg_contains_all_six_dims_and_no_free_text():
    report = _fixture_report()
    svg = render_report_svg(report)
    for dim in DIM_ORDER:
        assert dim in svg
    # 无用户原文纪律:语料/topic_key 从不进 report,svg 也不该出现中文自由句
    assert "心事" not in svg


def test_svg_consumes_report_overall_changes_output():
    """消费断言(§8.1#4):篡改 overall → golden SVG 比对必然失败。"""
    a = render_report_svg(_fixture_report())
    mutated = _fixture_report()
    mutated.overall = 0.1
    b = render_report_svg(mutated)
    assert a != b


def test_svg_matches_golden_fixture():
    svg = render_report_svg(_fixture_report())
    if not _GOLDEN_PATH.is_file():
        _GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        _GOLDEN_PATH.write_text(svg, encoding="utf-8")
    golden = _GOLDEN_PATH.read_text(encoding="utf-8")
    assert svg == golden, (
        "SVG 渲染与 golden 基线漂移——若是有意的渲染器改动,"
        f"删除 {_GOLDEN_PATH} 后重跑本测试以重铸(需人审,同 consistency 维"
        "的 golden 纪律)"
    )
