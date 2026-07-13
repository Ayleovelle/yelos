"""维 E 记忆(bench_BLUEPRINT §6 表)——探针命中率 + MRR,W4 判分接线。"""

from __future__ import annotations

import asyncio

from yelos.bench.harness.runner import run
from yelos.bench.harness.trace import RunTrace
from yelos.bench.metrics import EvalContext
from yelos.bench.metrics import memory_dim
from yelos.bench.scenarios.schema import Scenario, ScenarioDay, ScenarioEvent

_HEADER = {
    "scenario_id": "t",
    "git_rev": "no-git",
    "engine": "fake",
    "config_hash": "x",
    "schema_ver": 1,
}


def _trace(rows):
    return RunTrace(header=dict(_HEADER), rows=rows)


def test_memory_no_probes_scores_none():
    score = memory_dim.evaluate(EvalContext(trace=_trace([])))
    assert score.value is None
    assert "no-probes" in score.evidence["reason"]


def test_memory_all_hits_perfect_score():
    rows = [
        {
            "kind": "probe_recall",
            "out": {"verdict": "HIT", "rank": 1, "topic_key": "t1"},
        },
        {
            "kind": "probe_recall",
            "out": {"verdict": "HIT", "rank": 1, "topic_key": "t2"},
        },
    ]
    score = memory_dim.evaluate(EvalContext(trace=_trace(rows)))
    assert score.value == 1.0
    assert score.evidence["hit_rate"] == 1.0
    assert score.evidence["mrr"] == 1.0


def test_memory_mixed_hits_and_misses():
    rows = [
        {
            "kind": "probe_recall",
            "out": {"verdict": "HIT", "rank": 2, "topic_key": "a"},
        },
        {
            "kind": "probe_recall",
            "out": {"verdict": "MISS", "rank": None, "topic_key": "b"},
        },
    ]
    score = memory_dim.evaluate(EvalContext(trace=_trace(rows)))
    # hit_rate=0.5, mrr=(1/2 + 0)/2=0.25 -> value=0.7*0.5+0.3*0.25=0.425
    assert score.value == 0.425
    assert score.evidence["hits"] == 1
    assert score.evidence["probes"] == 2


def test_memory_score_changes_when_trace_row_mutated():
    """消费断言(§8.1#3 同款):篡改 trace verdict → 记忆分变。"""
    rows = [
        {
            "kind": "probe_recall",
            "out": {"verdict": "HIT", "rank": 1, "topic_key": "a"},
        },
    ]
    clean = memory_dim.evaluate(EvalContext(trace=_trace(rows)))
    mutated_rows = [
        dict(rows[0], out={"verdict": "MISS", "rank": None, "topic_key": "a"})
    ]
    mutated = memory_dim.evaluate(EvalContext(trace=_trace(mutated_rows)))
    assert clean.value != mutated.value


def _run(coro):
    return asyncio.run(coro)


def test_runner_probe_recall_end_to_end_plant_then_query_hits():
    """端到端(真 MemoryFacade,非手造 trace):plant 一个短语料键,次日 query
    同一 topic_key,应命中(keywords<=6字符纪律,§5.1.5.2 施工疑义)。
    """
    days = (
        ScenarioDay(
            day_index=0,
            events=(
                ScenarioEvent(
                    at_min=480,
                    kind="probe_recall",
                    payload={"role": "plant", "topic_key": "haixi1"},
                ),
            ),
        ),
        ScenarioDay(
            day_index=1,
            events=(
                ScenarioEvent(
                    at_min=480,
                    kind="probe_recall",
                    payload={"role": "query", "topic_key": "haixi1"},
                ),
            ),
        ),
    )
    scenario = Scenario(
        scenario_id="memory-probe-e2e",
        mode="companion",
        days=days,
        config_overrides={},
        origin="dsl",
    )
    trace = _run(run(scenario))
    query_rows = [
        r
        for r in trace.rows
        if r["kind"] == "probe_recall" and r["out"].get("verdict") in ("HIT", "MISS")
    ]
    assert len(query_rows) == 1
    assert query_rows[0]["out"]["verdict"] == "HIT"
    assert query_rows[0]["out"]["rank"] == 1


def test_runner_probe_recall_without_plant_misses():
    days = (
        ScenarioDay(
            day_index=0,
            events=(
                ScenarioEvent(
                    at_min=480,
                    kind="probe_recall",
                    payload={"role": "query", "topic_key": "ghost1"},
                ),
            ),
        ),
    )
    scenario = Scenario(
        scenario_id="memory-probe-miss",
        mode="companion",
        days=days,
        config_overrides={},
        origin="dsl",
    )
    trace = _run(run(scenario))
    row = next(r for r in trace.rows if r["kind"] == "probe_recall")
    assert row["out"]["verdict"] == "MISS"
    assert row["out"]["rank"] is None


def test_runner_probe_recall_deterministic_across_two_runs():
    """AX-B1 也覆盖记忆探针路径(真 MemoryFacade 走的是各自临时目录,但
    结果本身必须逐字节确定)。
    """
    days = (
        ScenarioDay(
            day_index=0,
            events=(
                ScenarioEvent(
                    at_min=480,
                    kind="probe_recall",
                    payload={"role": "plant", "topic_key": "tide01"},
                ),
                ScenarioEvent(
                    at_min=481,
                    kind="probe_recall",
                    payload={"role": "query", "topic_key": "tide01"},
                ),
            ),
        ),
    )
    scenario = Scenario(
        scenario_id="memory-probe-ax-b1",
        mode="companion",
        days=days,
        config_overrides={},
        origin="dsl",
    )
    trace_a = _run(run(scenario))
    trace_b = _run(run(scenario))
    assert trace_a.digest() == trace_b.digest()
