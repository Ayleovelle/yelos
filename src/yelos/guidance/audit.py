"""A3 溯源组装:``HintTrace`` 构造 helper + 频谱聚合(蓝图 §5.3 bench/viz 消费者)。

审计不开影子后门(P4):concern 类条目的 ``path`` 恒为 ``"concern_active"``,
绝不透出 shadow 内部字段名。
"""

from __future__ import annotations

from collections import Counter

from .model import HintTrace


def make_trace(
    *,
    hint_key: str,
    rule_id: str,
    path: str,
    op: str,
    threshold,
    observed,
    suppressed_by: str | None = None,
) -> HintTrace:
    """组装单条 :class:`HintTrace`,margin 按 op 语义计算(数值规则才有意义)。"""
    margin: float | None = None
    if (
        op == "ge"
        and isinstance(observed, (int, float))
        and isinstance(threshold, (int, float))
    ):
        margin = float(observed) - float(threshold)
    elif (
        op == "le"
        and isinstance(observed, (int, float))
        and isinstance(threshold, (int, float))
    ):
        margin = float(threshold) - float(observed)
    return HintTrace(
        hint_key=hint_key,
        rule_id=rule_id,
        path=path,
        op=op,  # type: ignore[arg-type]
        threshold=threshold,
        observed=observed,
        margin=margin,
        suppressed_by=suppressed_by,
    )


def aggregate_spectrum(traces: list[HintTrace] | tuple[HintTrace, ...]) -> dict:
    """频谱聚合:入选/被抑制的 hint_key 计数(bench reports / viz 消费)。

    如实标注:这是"回放期 audit 聚合",不是生产统计(§9 诚实自评 3)。
    """
    selected: Counter[str] = Counter()
    suppressed: Counter[str] = Counter()
    suppressed_reasons: Counter[str] = Counter()
    for t in traces:
        if t.suppressed_by is None:
            selected[t.hint_key] += 1
        else:
            suppressed[t.hint_key] += 1
            suppressed_reasons[t.suppressed_by] += 1
    return {
        "selected": dict(selected),
        "suppressed": dict(suppressed),
        "suppressed_reasons": dict(suppressed_reasons),
        "total_candidates": len(traces),
    }


__all__ = ["make_trace", "aggregate_spectrum"]
