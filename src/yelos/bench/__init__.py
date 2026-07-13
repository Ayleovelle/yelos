"""SylanneBench(bench_BLUEPRINT v1.0)——W1 先行骨架公开面。

公开面(bench_BLUEPRINT §11,W1 落地部分):``run_bench``/``load_scenario``/
``synthesize``/``compare_reports``。CLI(``__main__.py``)、regression 门禁
CLI(``--rebless`` 等)、SVG 报告留 W4;``compare_reports`` 本波是精简版
(只读两份 report 的 dims/vetoes 做差,容差常量沿用 §7.2 的 0.02 初值),
不落盘 baseline 存取(那是 W4 ``regression/baseline.py`` 的职责)。
"""

from __future__ import annotations

from pathlib import Path

from .clock import RealClock, VirtualClock
from .harness import runner as _runner
from .harness.trace import RunTrace
from .metrics import EvalContext, default_registry
from .reports.report import BenchReport, build as _build_report
from .scenarios import Scenario
from .scenarios.dsl import parse as _dsl_parse
from .scenarios.synth import synthesize as _synthesize

__all__ = [
    "RealClock",
    "VirtualClock",
    "RunTrace",
    "Scenario",
    "run_bench",
    "load_scenario",
    "synthesize",
    "compare_reports",
    "GATE_TOLERANCE",
]

GATE_TOLERANCE = 0.02


async def run_bench(
    scenario: Scenario,
    *,
    engine: str = "fake",
    data_dir: Path | None = None,
    out_dir: Path | None = None,
) -> BenchReport:
    """组合根(§11):``runner.run`` → ``metrics.aggregate`` → ``reports.build``。"""
    trace = await _runner.run(scenario, engine=engine, data_dir=data_dir)
    registry = default_registry()
    scores = registry.evaluate(EvalContext(trace=trace, data_dir=data_dir))
    report = _build_report(trace, scores)
    if out_dir is not None:
        out_dir = Path(out_dir)
        trace.dump(out_dir / scenario.scenario_id / "trace.jsonl")
        (out_dir / scenario.scenario_id / "report.json").parent.mkdir(
            parents=True, exist_ok=True
        )
        import json

        (out_dir / scenario.scenario_id / "report.json").write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return report


def load_scenario(path: Path) -> Scenario:
    """``dsl.parse`` 薄壳(§11)。"""
    return _dsl_parse(Path(path).read_text(encoding="utf-8"))


def synthesize(
    archetype: str, days: int, seed: str, poll_discipline: str = "faithful"
) -> Scenario:
    return _synthesize(archetype, days, seed, poll_discipline=poll_discipline)


def compare_reports(current: BenchReport, baseline: dict) -> dict:
    """``GateVerdict = {passed, failures, deltas}``(§11)。W1 精简版,见本文件顶部说明。"""
    failures: list[str] = []
    deltas: dict[str, float] = {}

    if current.vetoes:
        failures.append(f"veto: {current.vetoes}")

    base_dims = baseline.get("dims", {}) if isinstance(baseline, dict) else {}
    for dim, info in current.dims.items():
        val = info.get("value") if isinstance(info, dict) else None
        base_info = base_dims.get(dim) or {}
        base_val = base_info.get("value") if isinstance(base_info, dict) else None
        if val is None or base_val is None:
            continue
        delta = val - base_val
        deltas[dim] = delta
        if delta < -GATE_TOLERANCE:
            failures.append(f"{dim} 退步 {delta:.4f}(容差 {GATE_TOLERANCE})")

    return {"passed": not failures, "failures": failures, "deltas": deltas}
