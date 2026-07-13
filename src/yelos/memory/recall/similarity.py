"""similarity.py 在架构中的位置。

两套独立理论出身的相似度后端(维二策略族之一,§4):VectorNN(分布语义
PPMI+SVD 主通道,无向量退关键词 Jaccard)/ GraphPath(词共现图路径衰减和,
PPR-lite,深<=2,捕获向量丢失的组合关联)。
"""

from __future__ import annotations

from typing import Protocol

from ..contracts import SemanticEntry
from ..l2_semantic.linalg_lite import cosine


class SimilarityBackend(Protocol):
    name: str

    def relevance(
        self, q_tokens: list[str], q_vec: list[float], e: SemanticEntry
    ) -> float: ...


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


class VectorNN:
    """语义近邻主通道:cos(q_vec, e.vec);无向量退关键词 Jaccard(降级恒可用)。"""

    name = "vector_nn"

    def relevance(
        self, q_tokens: list[str], q_vec: list[float], e: SemanticEntry
    ) -> float:
        if q_vec and e.vec:
            return max(0.0, min(1.0, cosine(q_vec, e.vec)))
        return _jaccard(set(q_tokens), set(e.keywords))


def build_cooc_graph(entries: list[SemanticEntry]) -> dict[str, dict[str, float]]:
    """从 L2 条目关键词共现构图(同条目内两两连边,权重=共现次数)。"""
    graph: dict[str, dict[str, float]] = {}
    for e in entries:
        kws = list(dict.fromkeys(e.keywords))
        for i in range(len(kws)):
            for j in range(i + 1, len(kws)):
                a, b = kws[i], kws[j]
                graph.setdefault(a, {})
                graph[a][b] = graph[a].get(b, 0.0) + 1.0
                graph.setdefault(b, {})
                graph[b][a] = graph[b].get(a, 0.0) + 1.0
    return graph


class GraphPath:
    """图路径关联:q 关键词与 e 关键词的路径衰减和(PPR-lite,深<=2,确定性)。

    深 1(直接命中)权重 1.0;深 2(经一个共现邻居可达)权重 decay;
    未命中权重 0。按 query token 数归一到 [0,1]。
    """

    name = "graph_path"

    def __init__(
        self,
        graph: dict[str, dict[str, float]] | None = None,
        *,
        decay: float = 0.5,
    ) -> None:
        self._graph = graph or {}
        self._decay = decay

    def relevance(
        self, q_tokens: list[str], q_vec: list[float], e: SemanticEntry
    ) -> float:
        targets = set(e.keywords)
        if not targets or not q_tokens:
            return 0.0
        total = 0.0
        for qt in q_tokens:
            if qt in targets:
                total += 1.0
                continue
            neighbors = self._graph.get(qt, {})
            hit = any(nb in targets for nb in neighbors)
            if hit:
                total += self._decay
        return min(1.0, total / len(q_tokens))
