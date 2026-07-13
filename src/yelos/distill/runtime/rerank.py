"""在整个架构中的位置:候选重排两法(蓝图 §3.1;DA3 确定性锚点)。

维二附条件计数(v1.1):须展示可观测输出差异 + 对比评测落盘,否则如实
降格为"1 法 + 参数档"(``tests/distill/test_rerank_divergence.py`` 是
凭据测试,拿不出可区分样本即在交付报告如实记降格,不硬凑)。

键型 ``distill``(``{sid}|{day_key}|distill|{occasion}``)已登记
``primal/determinism.py::KEY_REGISTRY``(§2.1 纪律);本文件是唯一消费者。
"""

from __future__ import annotations

from typing import Protocol

from yelos.primal import determinism


class Reranker(Protocol):
    def pick(self, passed: list[str], key: str) -> str: ...


class HashRerank:
    """法①:闸后按哈希族确定性选(蓝图 §3.1 原公式:sha256(key).digest()[0]

    % len(passed)),不看候选内容,纯键驱动——同键同输出(DA3)。
    """

    def pick(self, passed: list[str], key: str) -> str:
        if not passed:
            raise ValueError("HashRerank.pick: 候选为空")
        idx = determinism.h_byte(key) % len(passed)
        return passed[idx]


class FidelityRerank:
    """法②:按风格保真分选,取最高;平分回落哈希序(仍确定)。

    评分不复用 ``eval.fidelity``(那是训练侧/报告侧的严格 JS 距离评测,
    依赖图 ``eval → runtime`` 决定了 runtime 不能反向 import eval,避免
    循环依赖);此处用一个自包含的轻量字符 trigram 重合度作代理分——
    足以在同候选集内产生排序差异,不需要完整分布距离计算。
    """

    def __init__(self, corpus: tuple[str, ...] = ()):
        self._corpus_trigrams = self._trigrams(corpus)

    @staticmethod
    def _trigrams(corpus: tuple[str, ...]) -> frozenset[str]:
        grams: set[str] = set()
        for s in corpus:
            for i in range(len(s) - 2):
                grams.add(s[i : i + 3])
        return frozenset(grams)

    def _score(self, candidate: str) -> float:
        if len(candidate) < 3 or not self._corpus_trigrams:
            return 0.0
        cand_grams = [candidate[i : i + 3] for i in range(len(candidate) - 2)]
        if not cand_grams:
            return 0.0
        hits = sum(1 for g in cand_grams if g in self._corpus_trigrams)
        return hits / len(cand_grams)

    def pick(self, passed: list[str], key: str) -> str:
        if not passed:
            raise ValueError("FidelityRerank.pick: 候选为空")
        scored = [(self._score(c), c) for c in passed]
        best_score = max(s for s, _ in scored)
        tied = [c for s, c in scored if s == best_score]
        if len(tied) == 1:
            return tied[0]
        idx = determinism.h_byte(key) % len(tied)
        return tied[idx]


def build_reranker(kind: str, corpus: tuple[str, ...] = ()) -> Reranker:
    if kind == "fidelity":
        return FidelityRerank(corpus)
    return HashRerank()


__all__ = ["Reranker", "HashRerank", "FidelityRerank", "build_reranker"]
