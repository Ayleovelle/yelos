"""维 E 记忆(bench_BLUEPRINT §6 表)——探针命中率 + MRR,W4 判分接线。

数据源恒为 trace(与全部判分器同口径,只读不重算):``harness/runner.py``
的 ``_probe_recall`` 在 ``probe_recall{role=query}`` 行的 ``out`` 里落
``verdict∈{HIT,MISS}``/``rank``(1-based 或 None)——这里只做统计,不重新
调 ``MemoryFacade``(§8.1#3 同款消费断言:篡改 trace 一行 verdict/rank,
判分必须跟着变,见 tests/bench/test_memory_dim.py)。

``value = 0.7×hit_rate + 0.3×MRR``(§6 表公式)。剧本无 ``probe_recall``
探针 → ``value=None``(n/a,不占位)。
"""

from __future__ import annotations

from . import EvalContext, Score

_HIT_WEIGHT = 0.7
_MRR_WEIGHT = 0.3


def evaluate(ctx: EvalContext) -> Score:
    queries = [
        row
        for row in ctx.trace.rows
        if row.get("kind") == "probe_recall"
        and (row.get("out") or {}).get("verdict") in ("HIT", "MISS")
    ]
    if not queries:
        return Score(
            dim="memory",
            value=None,
            veto=False,
            evidence={"reason": "no-probes(剧本未含 probe_recall 查询)"},
        )

    n = len(queries)
    hits = 0
    reciprocal_sum = 0.0
    for row in queries:
        out = row["out"]
        if out.get("verdict") == "HIT":
            hits += 1
            rank = out.get("rank")
            if rank:
                reciprocal_sum += 1.0 / rank

    hit_rate = hits / n
    mrr = reciprocal_sum / n
    value = _HIT_WEIGHT * hit_rate + _MRR_WEIGHT * mrr

    return Score(
        dim="memory",
        value=round(value, 6),
        veto=False,
        evidence={
            "probes": n,
            "hits": hits,
            "hit_rate": round(hit_rate, 6),
            "mrr": round(mrr, 6),
        },
    )
