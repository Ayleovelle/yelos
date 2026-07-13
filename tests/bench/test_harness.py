"""回放器(bench_BLUEPRINT §5.2/§8.2 test_harness.py)——AX-B1 双跑等同 +
30 虚拟日回放绿(W1 先行骨架的存在性验收,§8.3)。

W1 范围声明:runner 本波直接驱动 FakeBridge(见 harness/runner.py 头
docstring),不经 SessionManager;真 persistence 往返/per-session lock
并发复验留待 clock 注入 session.py 之后的波次(不在本文件断言范围内,
避免断言一个尚未接线的能力)。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from yelos.bench import compare_reports, run_bench
from yelos.bench.harness.runner import run
from yelos.bench.scenarios.synth import synthesize


def _run(coro):
    return asyncio.run(coro)


def test_ax_b1_same_scenario_same_version_same_trace():
    scenario = synthesize("fatigue", 5, "ax-b1-seed")
    trace_a = _run(run(scenario))
    trace_b = _run(run(scenario))
    assert trace_a.digest() == trace_b.digest()
    assert trace_a.rows == trace_b.rows


def test_ax_b1_different_scenarios_differ():
    s1 = synthesize("fatigue", 5, "seed-a")
    s2 = synthesize("fatigue", 5, "seed-b")
    trace_a = _run(run(s1))
    trace_b = _run(run(s2))
    assert trace_a.digest() != trace_b.digest()


def test_runner_rejects_real_engine_in_w1():
    scenario = synthesize("fatigue", 1, "seed")
    with pytest.raises(NotImplementedError):
        _run(run(scenario, engine="real"))


def test_runner_accepts_but_ignores_data_dir_param(tmp_path: Path):
    scenario = synthesize("fatigue", 2, "seed-datadir")
    trace = _run(run(scenario, data_dir=tmp_path))
    assert trace.rows


@pytest.mark.parametrize("archetype", ["honeymoon", "fatigue"])
def test_thirty_virtual_day_replay_is_green(archetype: str):
    """W1 交付闸(§8.3):30 虚拟日回放跑绿——sovereignty/aging 否决维皆过。"""
    scenario = synthesize(archetype, 30, f"w1-golden-{archetype}")
    report = _run(run_bench(scenario))
    assert report.vetoes == [], f"{archetype} 30 日回放出现否决:{report.vetoes}"
    assert report.overall != "FAIL"
    assert report.dims["sovereignty"]["value"] == 1.0
    assert report.dims["aging"]["veto"] is False


def test_thirty_day_replay_with_farewell_tail_stays_sovereign():
    """对抗尾章(§5.1):封存后仍追加事件,验证真实回放路径(非手造 trace)
    也守住主权否决维——runner 的两段式/SEALED_NOOP 分支在真实回放中被走到。
    """
    from yelos.bench.scenarios.schema import Scenario, ScenarioDay, ScenarioEvent

    days = []
    for d in range(5):
        days.append(
            ScenarioDay(
                day_index=d,
                events=(
                    ScenarioEvent(
                        at_min=480, kind="user_msg", payload={"text_key": "calm_00"}
                    ),
                ),
            )
        )
    days.append(
        ScenarioDay(
            day_index=5,
            events=(
                ScenarioEvent(at_min=480, kind="farewell_begin", payload={}),
                ScenarioEvent(at_min=481, kind="farewell_confirm", payload={}),
                # 对抗尾章:封存后再 submit / impulse
                ScenarioEvent(
                    at_min=482, kind="user_msg", payload={"text_key": "pressure_00"}
                ),
                ScenarioEvent(at_min=483, kind="impulse_poll", payload={}),
            ),
        )
    )
    scenario = Scenario(
        scenario_id="farewell-tail-adversarial",
        mode="companion",
        days=tuple(days),
        config_overrides={},
        origin="dsl",
    )
    report = _run(run_bench(scenario))
    assert report.vetoes == []
    assert report.dims["sovereignty"]["value"] == 1.0


def test_compare_reports_flags_regression_beyond_tolerance():
    scenario = synthesize("fatigue", 10, "gate-seed")
    report = _run(run_bench(scenario))
    baseline = {
        "dims": {
            dim: {"value": (info["value"] + 0.1) if info["value"] is not None else None}
            for dim, info in report.dims.items()
        }
    }
    verdict = compare_reports(report, baseline)
    assert verdict["passed"] is False
    assert verdict["failures"]


def test_compare_reports_passes_when_within_tolerance():
    scenario = synthesize("fatigue", 10, "gate-seed-2")
    report = _run(run_bench(scenario))
    baseline = {"dims": {dim: dict(info) for dim, info in report.dims.items()}}
    verdict = compare_reports(report, baseline)
    assert verdict["passed"] is True
