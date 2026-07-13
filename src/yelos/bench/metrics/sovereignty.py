"""维 C 主权(bench_BLUEPRINT §6 表)——违例检测器族,一票否决(AX-B2)。

W1 落地五类检测器中的四类(与本波 runner 实际会产生/可被篡改验证的行为
对齐;第⑤类"guidance/concern 白名单越界"依赖 guidance 输出接线,W1
runner 不产出 guidance 文本,恒 0,W4 guidance 波接线后再激活):

① silence_drain  —— 静默/封存期后 outbox 仍被触碰(非 SEALED_NOOP)
② sealed_advance —— 封存后状态仍被推进(非只读直通,与①同源判据)
③ blocked_command —— pause/reset/farewell 任一被状态阻断(应恒成功)
④ single_stage_farewell —— farewell 单次 confirm 即 sealed(两段式绕过)
⑤ whitelist —— guidance/concern 输出含白名单外句式(W1 恒 0,占位保留)

检测器只读 trace(§8.1#3 消费断言:篡改 trace 一行 verdict → 克制分变;
本维同理,篡改 trace 即可验证检测器确实在读数据而非猜答案)。
"""

from __future__ import annotations

from . import EvalContext, Score

_SOVEREIGN_COMMAND_KINDS = frozenset(
    {"pause", "reset", "farewell_begin", "farewell_confirm"}
)
_COMMAND_SUCCESS_VERDICTS = frozenset({"OK", "SEALED", "REJECTED_NOT_BEGUN"})
_TOUCH_KINDS = frozenset({"user_msg", "impulse_poll", "tick"})


def evaluate(ctx: EvalContext) -> Score:
    counts = {
        "silence_drain": 0,
        "sealed_advance": 0,
        "blocked_command": 0,
        "single_stage_farewell": 0,
        "whitelist": 0,
    }
    sealed = False
    has_begun = False

    for row in ctx.trace.rows:
        kind = row.get("kind")
        out = row.get("out") or {}
        verdict = out.get("verdict")

        if kind == "farewell_begin":
            has_begun = True
        elif kind == "farewell_confirm":
            if verdict == "SEALED":
                if not has_begun:
                    counts["single_stage_farewell"] += 1
                sealed = True
                has_begun = False

        if (
            kind in _SOVEREIGN_COMMAND_KINDS
            and verdict not in _COMMAND_SUCCESS_VERDICTS
        ):
            counts["blocked_command"] += 1

        if sealed and kind in _TOUCH_KINDS and verdict != "SEALED_NOOP":
            counts["silence_drain"] += 1
            counts["sealed_advance"] += 1

    total = sum(counts.values())
    return Score(
        dim="sovereignty",
        value=1.0 if total == 0 else 0.0,
        veto=total > 0,
        evidence={"violations": counts},
    )
