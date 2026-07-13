"""在整个架构中的位置:风格保真评测(蓝图 §1)。

与词典语料的 n-gram 分布距离(Jensen-Shannon),逐场合计算。这是训练/
打包后的报告侧评测,与 ``runtime.rerank.FidelityRerank`` 的轻量代理分
是两回事(依赖图 ``eval → runtime`` 单向,runtime 不反向 import 本模块,
见 ``runtime/rerank.py`` 头注说明)。
"""

from __future__ import annotations

import math
from collections import Counter


def _char_trigram_dist(texts: tuple[str, ...]) -> Counter:
    counts: Counter = Counter()
    for text in texts:
        for i in range(len(text) - 2):
            counts[text[i : i + 3]] += 1
    return counts


def _normalize(counts: Counter) -> dict[str, float]:
    total = sum(counts.values())
    if total == 0:
        return {}
    return {k: v / total for k, v in counts.items()}


def js_divergence(p: dict[str, float], q: dict[str, float]) -> float:
    """Jensen-Shannon 散度,底为 2(值域 [0, 1]);两分布皆空 ⇒ 0(自距离性质)。"""
    keys = set(p) | set(q)
    if not keys:
        return 0.0

    def _kl(a: dict[str, float], b: dict[str, float]) -> float:
        total = 0.0
        for k in keys:
            pa = a.get(k, 0.0)
            if pa <= 0.0:
                continue
            pb = b.get(k, 0.0)
            total += pa * math.log2(pa / pb) if pb > 0 else float("inf")
        return total

    m = {k: 0.5 * (p.get(k, 0.0) + q.get(k, 0.0)) for k in keys}
    kl_pm = _kl(p, m)
    kl_qm = _kl(q, m)
    if math.isinf(kl_pm) or math.isinf(kl_qm):
        return 1.0
    return 0.5 * kl_pm + 0.5 * kl_qm


def fidelity_js(generated: tuple[str, ...], corpus: tuple[str, ...]) -> float:
    """越小越保真;两者皆空 ⇒ 0.0(数值性质:自距离为 0、对称)。"""
    p = _normalize(_char_trigram_dist(generated))
    q = _normalize(_char_trigram_dist(corpus))
    return js_divergence(p, q)


def fidelity_by_occasion(
    generated_by_occasion: dict[str, tuple[str, ...]],
    corpus_by_occasion: dict[str, tuple[str, ...]],
) -> dict[str, float]:
    out: dict[str, float] = {}
    for occasion, generated in generated_by_occasion.items():
        corpus = corpus_by_occasion.get(occasion, ())
        out[occasion] = fidelity_js(generated, corpus)
    return out


__all__ = ["js_divergence", "fidelity_js", "fidelity_by_occasion"]
