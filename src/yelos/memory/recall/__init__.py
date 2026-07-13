"""recall 子包在架构中的位置。

红队 major⑧ 承诺 3 的载体:两套相似度后端 × 三套打分器 × 艾宾浩斯双衰减
的多因子确定性召回。similarity.py 产 relevance,scorers.py 产最终排序,
service.py 是对 facade 的编排门面(四服务面 + affect_recall 工具面逻辑)。
"""

from __future__ import annotations

from .scorers import EmotionFirstScorer, LinearScorer, RRFScorer, get_scorer
from .similarity import GraphPath, VectorNN, build_cooc_graph

__all__ = [
    "EmotionFirstScorer",
    "LinearScorer",
    "RRFScorer",
    "get_scorer",
    "GraphPath",
    "VectorNN",
    "build_cooc_graph",
]
