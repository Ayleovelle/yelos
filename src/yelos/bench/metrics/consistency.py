"""维 B 一致(bench_BLUEPRINT §6 表 / AX-B1 的判分侧消费)。

同剧本同版本双跑,trace 逐字节等同(``RunTrace.digest()``,已规范化);
外加 golden(入库剧本 trace 哈希基线)。判分决策表(§6):
- 双跑等同 且 golden 命中 -> 1
- 双跑等同 且 golden 漂移/缺席 -> 0.5(W1 无 golden 入库时按"缺席"处理,
  不判 1 分也不判 FAIL——如实标注,留人审 rebless 空间)
- 双跑不等 -> 0,且报告应整体标 UNRELIABLE(AX-B1 失守,调用方按
  ``evidence.reason`` 判断是否要整份报告降级)
"""

from __future__ import annotations

from . import EvalContext, Score


def evaluate(ctx: EvalContext) -> Score:
    if ctx.repeat_trace is None:
        return Score(
            dim="consistency",
            value=None,
            veto=False,
            evidence={"reason": "no-repeat-run(单跑,AX-B1 未被验证)"},
        )

    d1 = ctx.trace.digest()
    d2 = ctx.repeat_trace.digest()
    if d1 != d2:
        return Score(
            dim="consistency",
            value=0.0,
            veto=False,
            evidence={
                "reason": "UNRELIABLE:双跑不等,AX-B1 失守",
                "digest_a": d1,
                "digest_b": d2,
            },
        )
    if ctx.golden_digest is None:
        return Score(
            dim="consistency",
            value=0.5,
            veto=False,
            evidence={"digest": d1, "golden": "absent(W1未入库,视同缺席不满分)"},
        )
    if d1 == ctx.golden_digest:
        return Score(dim="consistency", value=1.0, veto=False, evidence={"digest": d1})
    return Score(
        dim="consistency",
        value=0.5,
        veto=False,
        evidence={
            "digest": d1,
            "golden": ctx.golden_digest,
            "reason": "golden漂移,需人审后--rebless",
        },
    )
