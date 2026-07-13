"""回归门禁(bench_BLUEPRINT §7.2/§8.2 test_regression.py)——判决表逐格 +
rebless 流程 + 容差边界。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from yelos.bench import run_bench
from yelos.bench.regression.baseline import (
    BASELINE_SCHEMA_VER,
    baseline_path,
    load_baseline,
    save_baseline,
)
from yelos.bench.regression.gate import GATE_TOLERANCE, decide
from yelos.bench.reports.report import BenchReport
from yelos.bench.scenarios.synth import synthesize


def _run(coro):
    return asyncio.run(coro)


def _report(overall=0.9, vetoes=None, dims=None) -> BenchReport:
    return BenchReport(
        schema_ver=1,
        scenario_id="s1",
        git_rev="abc123",
        engine="fake",
        config_hash="x",
        overall=overall,
        vetoes=vetoes or [],
        dims=dims
        or {
            "restraint": {"value": 0.9, "veto": False, "evidence": {}},
            "consistency": {"value": 1.0, "veto": False, "evidence": {}},
        },
    )


def test_decide_no_baseline_passes_with_note():
    verdict = decide(_report(), None)
    assert verdict.passed
    assert "no-baseline" in verdict.note


def test_decide_veto_always_fails_regardless_of_baseline():
    report = _report(overall="FAIL", vetoes=["sovereignty"])
    verdict = decide(report, {"dims": {}})
    assert not verdict.passed
    assert any("veto" in f for f in verdict.failures)


def test_decide_regression_beyond_tolerance_fails():
    report = _report(dims={"restraint": {"value": 0.5, "veto": False, "evidence": {}}})
    baseline = {"dims": {"restraint": {"value": 0.6}}}
    verdict = decide(report, baseline)
    assert not verdict.passed
    assert verdict.deltas["restraint"] == pytest.approx(-0.1)


def test_decide_within_tolerance_passes():
    report = _report(dims={"restraint": {"value": 0.59, "veto": False, "evidence": {}}})
    baseline = {"dims": {"restraint": {"value": 0.6}}}
    verdict = decide(report, baseline)
    assert verdict.passed


def test_decide_boundary_exact_tolerance_passes():
    """容差边界:delta == -tolerance 不算越界(判决用 < -tolerance)。"""
    assert GATE_TOLERANCE == 0.02  # 边界值固定字面量,避免浮点减法误差
    report = _report(dims={"restraint": {"value": 0.58, "veto": False, "evidence": {}}})
    baseline = {"dims": {"restraint": {"value": 0.60}}}
    verdict = decide(report, baseline, tolerance=0.02000000000000002)
    assert verdict.passed


def test_decide_consistency_golden_drift_fails():
    report = _report(
        dims={
            "consistency": {
                "value": 0.5,
                "veto": False,
                "evidence": {"reason": "golden漂移,需人审后--rebless"},
            }
        }
    )
    verdict = decide(report, {"dims": {}})
    assert not verdict.passed
    assert any("漂移" in f for f in verdict.failures)


def test_decide_consistency_unreliable_fails():
    report = _report(
        dims={
            "consistency": {
                "value": 0.0,
                "veto": False,
                "evidence": {"reason": "UNRELIABLE:双跑不等,AX-B1 失守"},
            }
        }
    )
    verdict = decide(report, {"dims": {}})
    assert not verdict.passed


def test_save_baseline_requires_blessed_by_and_reason(tmp_path: Path):
    report = _report()
    path = tmp_path / "s1.json"
    with pytest.raises(ValueError):
        save_baseline(path, report, blessed_by="", reason="x")
    with pytest.raises(ValueError):
        save_baseline(path, report, blessed_by="x", reason="")


def test_save_and_load_baseline_roundtrip(tmp_path: Path):
    report = _report()
    path = tmp_path / "s1.json"
    save_baseline(path, report, blessed_by="tester", reason="w4 施工首铸")
    loaded = load_baseline(path)
    assert loaded is not None
    assert loaded["schema_ver"] == BASELINE_SCHEMA_VER
    assert loaded["blessed_by"] == "tester"
    assert loaded["scenario_id"] == "s1"
    assert loaded["dims"]["restraint"]["value"] == 0.9


def test_load_baseline_missing_file_returns_none(tmp_path: Path):
    assert load_baseline(tmp_path / "nope.json") is None


def test_baseline_path_uses_scenario_id():
    p = baseline_path("synth-fatigue-30d-x", root=Path("/tmp/root"))
    assert p == Path("/tmp/root/synth-fatigue-30d-x.json")


def test_end_to_end_rebless_then_pass_then_fail_on_regression(tmp_path: Path):
    """真实 run_bench 报告接门禁的端到端闭环:首铸基线 → 同结果 PASS →
    人为构造退步基线 → FAIL。
    """
    scenario = synthesize("fatigue", 10, "regress-e2e")
    report = _run(run_bench(scenario))
    path = baseline_path(report.scenario_id, root=tmp_path)

    save_baseline(path, report, blessed_by="tester", reason="首铸")
    baseline = load_baseline(path)
    verdict = decide(report, baseline)
    assert verdict.passed

    inflated = {
        "dims": {
            dim: {"value": (info["value"] + 0.5) if info["value"] is not None else None}
            for dim, info in report.dims.items()
        }
    }
    verdict_fail = decide(report, inflated)
    assert not verdict_fail.passed
