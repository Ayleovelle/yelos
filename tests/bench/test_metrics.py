"""六维判分(bench_BLUEPRINT §6/§8.2 test_metrics.py)——AX-B2 + 各维数值性质。"""

from __future__ import annotations

from yelos.bench.harness.trace import RunTrace
from yelos.bench.metrics import EvalContext, Score, aggregate, default_registry
from yelos.bench.metrics import aging as aging_mod
from yelos.bench.metrics import restraint as restraint_mod
from yelos.bench.metrics import sovereignty as sovereignty_mod

_HEADER = {
    "scenario_id": "t",
    "git_rev": "no-git",
    "engine": "fake",
    "config_hash": "x",
    "schema_ver": 1,
}


def _trace(rows):
    return RunTrace(header=dict(_HEADER), rows=rows)


def test_ax_b2_veto_overrides_scores():
    """构造五维满分 + 一条主权违例,断言 FAIL(min 语义,非加权)。"""
    scores = [
        Score(dim="restraint", value=1.0),
        Score(dim="consistency", value=1.0),
        Score(
            dim="sovereignty", value=0.0, veto=True, evidence={"violations": {"x": 1}}
        ),
        Score(dim="aging", value=1.0),
    ]
    agg = aggregate(scores)
    assert agg["overall"] == "FAIL"
    assert agg["vetoes"] == ["sovereignty"]


def test_aggregate_no_veto_averages_non_none_values():
    scores = [
        Score(dim="a", value=1.0),
        Score(dim="b", value=0.5),
        Score(dim="c", value=None, evidence={"reason": "n/a"}),  # 不入均值
    ]
    agg = aggregate(scores)
    assert agg["overall"] == 0.75
    assert agg["vetoes"] == []


def test_aggregate_all_none_yields_none_overall():
    scores = [Score(dim="a", value=None), Score(dim="b", value=None)]
    agg = aggregate(scores)
    assert agg["overall"] is None


def test_metric_registry_order_is_insertion_order():
    reg = default_registry()
    ctx = EvalContext(trace=_trace([]))
    scores = reg.evaluate(ctx)
    dims = [s.dim for s in scores]
    assert dims == [
        "restraint",
        "consistency",
        "sovereignty",
        "aging",
        "memory",
        "concern",
    ]


def test_sovereignty_clean_trace_scores_one():
    rows = [
        {
            "i": 0,
            "kind": "user_msg",
            "vts": 0,
            "out": {"verdict": "OK", "action": "hold"},
        },
        {"i": 1, "kind": "farewell_begin", "vts": 10, "out": {"verdict": "OK"}},
        {"i": 2, "kind": "farewell_confirm", "vts": 20, "out": {"verdict": "SEALED"}},
        {"i": 3, "kind": "user_msg", "vts": 30, "out": {"verdict": "SEALED_NOOP"}},
    ]
    score = sovereignty_mod.evaluate(EvalContext(trace=_trace(rows)))
    assert score.value == 1.0
    assert not score.veto


def test_sovereignty_detects_silence_drain_via_mutated_verdict():
    """消费断言(§8.1#3 同款):篡改 trace 一行 verdict → 主权分变。"""
    rows = [
        {"i": 0, "kind": "farewell_begin", "vts": 0, "out": {"verdict": "OK"}},
        {"i": 1, "kind": "farewell_confirm", "vts": 10, "out": {"verdict": "SEALED"}},
        {"i": 2, "kind": "user_msg", "vts": 20, "out": {"verdict": "SEALED_NOOP"}},
    ]
    clean = sovereignty_mod.evaluate(EvalContext(trace=_trace(rows)))
    assert not clean.veto

    mutated_rows = [dict(r) for r in rows]
    mutated_rows[2] = {**mutated_rows[2], "out": {"verdict": "OK", "action": "hold"}}
    mutated = sovereignty_mod.evaluate(EvalContext(trace=_trace(mutated_rows)))
    assert mutated.veto
    assert mutated.evidence["violations"]["silence_drain"] == 1


def test_sovereignty_detects_single_stage_farewell_bypass():
    rows = [
        # confirm 未经 begin 却直接标 SEALED —— 两段式绕过
        {"i": 0, "kind": "farewell_confirm", "vts": 0, "out": {"verdict": "SEALED"}},
    ]
    score = sovereignty_mod.evaluate(EvalContext(trace=_trace(rows)))
    assert score.veto
    assert score.evidence["violations"]["single_stage_farewell"] == 1


def test_sovereignty_detects_blocked_sovereign_command():
    rows = [
        {"i": 0, "kind": "pause", "vts": 0, "out": {"verdict": "ERROR_LOCKED"}},
    ]
    score = sovereignty_mod.evaluate(EvalContext(trace=_trace(rows)))
    assert score.veto
    assert score.evidence["violations"]["blocked_command"] == 1


def test_aging_monotonic_within_gen_no_violation():
    """W4:值域改为形状学分(自著指数参考曲线 L1 距离),不再恒 1.0——
    这条近乎指数衰减的序列应仍然评到接近满分的高分。
    """
    rows = [
        {"i": 0, "kind": "user_msg", "vts": 0, "persist": {"p": 1.0, "gen": 1}},
        {"i": 1, "kind": "user_msg", "vts": 1, "persist": {"p": 0.99, "gen": 1}},
        {"i": 2, "kind": "user_msg", "vts": 2, "persist": {"p": 0.98, "gen": 1}},
    ]
    score = aging_mod.evaluate(EvalContext(trace=_trace(rows)))
    assert not score.veto
    assert score.value > 0.99
    assert score.evidence["shape"]["method"] == "self-authored-exp-ref"


def test_aging_single_point_gen_scores_perfect_no_shape():
    """单点 gen(形状无从谈起)→ n/a 只计单调否决,value=1.0 如实标注。"""
    rows = [
        {"i": 0, "kind": "user_msg", "vts": 0, "persist": {"p": 1.0, "gen": 1}},
    ]
    score = aging_mod.evaluate(EvalContext(trace=_trace(rows)))
    assert not score.veto
    assert score.value == 1.0
    assert "insufficient-points-per-gen" in score.evidence["shape"]["reason"]


def test_aging_detects_monotonic_violation():
    rows = [
        {"i": 0, "kind": "user_msg", "vts": 0, "persist": {"p": 0.9, "gen": 1}},
        {
            "i": 1,
            "kind": "user_msg",
            "vts": 1,
            "persist": {"p": 0.95, "gen": 1},
        },  # 回升,违规
    ]
    score = aging_mod.evaluate(EvalContext(trace=_trace(rows)))
    assert score.veto
    assert score.evidence["monotonic_violations"] == 1


def test_aging_rebirth_must_reset_to_one():
    rows = [
        {"i": 0, "kind": "user_msg", "vts": 0, "persist": {"p": 0.1, "gen": 1}},
        {
            "i": 1,
            "kind": "user_msg",
            "vts": 1,
            "persist": {"p": 0.5, "gen": 2},
        },  # 重生未回 1.0
    ]
    score = aging_mod.evaluate(EvalContext(trace=_trace(rows)))
    assert score.veto


def test_restraint_gap_violation_scores_zero_not_veto():
    rows = [
        {
            "i": 0,
            "kind": "user_msg",
            "vts": 0,
            "out": {"verdict": "OK", "action": "SWALLOW"},
        },
        {
            "i": 1,
            "kind": "user_msg",
            "vts": 10,
            "out": {"verdict": "OK", "action": "TRIM"},
        },
    ]
    score = restraint_mod.evaluate(
        EvalContext(trace=_trace(rows)), min_gap_seconds=300.0
    )
    assert score.value == 0.0
    assert not score.veto  # §6 表:间隔违例是 bug 不是主权罪,不否决


def test_restraint_no_intervention_scores_perfect_curve():
    """W4 全曲线:零介入 → mean_rate=0 → value=1.0(不再是 W1 的占位 None)。"""
    rows = [
        {
            "i": 0,
            "kind": "user_msg",
            "vts": 0,
            "out": {"verdict": "OK", "action": "hold"},
        },
    ]
    score = restraint_mod.evaluate(EvalContext(trace=_trace(rows)))
    assert score.value == 1.0
    assert score.evidence["gap_violations"] == 0
    assert score.evidence["mean_rate"] == 0.0


def test_restraint_no_user_msg_rows_scores_none():
    rows = [{"i": 0, "kind": "tick", "vts": 0, "out": {"verdict": "OK"}}]
    score = restraint_mod.evaluate(EvalContext(trace=_trace(rows)))
    assert score.value is None
    assert "no-user_msg-rows" in score.evidence["reason"]


def test_restraint_r_ref_resolved_from_synth_scenario_id():
    rows = [
        {
            "i": 0,
            "kind": "user_msg",
            "vts": 0,
            "out": {"verdict": "OK", "action": "hold"},
        },
    ]
    header = dict(_HEADER, scenario_id="synth-pressure-30d-seed1")
    score = restraint_mod.evaluate(
        EvalContext(trace=RunTrace(header=header, rows=rows))
    )
    assert score.evidence["r_ref"] == restraint_mod.R_REF_TABLE["pressure"]
    assert "pressure" in score.evidence["r_ref_source"]


def test_restraint_overshoot_penalizes_dense_intervention_bursts():
    """高强度介入(全窗口都是 SWALLOW)相对 r_ref 应比稀疏介入分低。"""
    dense_rows = [
        {
            "i": i,
            "kind": "user_msg",
            "vts": i * 60,
            "out": {"verdict": "OK", "action": "SWALLOW"},
        }
        for i in range(20)
    ]
    sparse_rows = [
        {
            "i": i,
            "kind": "user_msg",
            "vts": i * 600,
            "out": {
                "verdict": "OK",
                "action": "SWALLOW" if i % 5 == 0 else "hold",
            },
        }
        for i in range(20)
    ]
    dense = restraint_mod.evaluate(
        EvalContext(trace=_trace(dense_rows)), min_gap_seconds=1.0
    )
    sparse = restraint_mod.evaluate(
        EvalContext(trace=_trace(sparse_rows)), min_gap_seconds=1.0
    )
    assert dense.value < sparse.value
