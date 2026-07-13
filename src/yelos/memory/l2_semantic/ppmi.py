"""ppmi.py 在架构中的位置。

词-上下文共现(滑窗 w=4,距离加权)→ shifted PPMI 稀疏矩阵。是 linalg_lite
rsvd 的输入构造器;全部纯字典运算,复杂度 O(sum(len(doc)) * window)。

PPMI(i,j) = max(0, log(p(i,j)/(p(i)p(j))) - log(shift))
"""

from __future__ import annotations

import math

CoocMatrix = dict[tuple[int, int], float]


def cooccurrence(docs: list[list[int]], vocab_size: int, window: int = 4) -> CoocMatrix:
    """docs 是已编码(token id,OOV 已被上游 Vocab.encode 过滤)的文档序列。"""
    cooc: CoocMatrix = {}
    w = max(1, window)
    for doc in docs:
        n = len(doc)
        for i, wi in enumerate(doc):
            lo = max(0, i - w)
            hi = min(n, i + w + 1)
            for j in range(lo, hi):
                if j == i:
                    continue
                wj = doc[j]
                dist = abs(j - i)
                weight = 1.0 / dist
                key = (wi, wj)
                cooc[key] = cooc.get(key, 0.0) + weight
    return cooc


def row_totals(cooc: CoocMatrix) -> tuple[dict[int, float], float]:
    row_tot: dict[int, float] = {}
    total = 0.0
    for (i, _j), v in cooc.items():
        row_tot[i] = row_tot.get(i, 0.0) + v
        total += v
    return row_tot, total


def ppmi_weight(
    cooc: CoocMatrix,
    row_tot: dict[int, float],
    total: float,
    shift: float = 1.0,
) -> CoocMatrix:
    """shifted PPMI;total<=0(空语料)返回空矩阵,不 raise。"""
    if total <= 0:
        return {}
    log_shift = math.log(max(shift, 1e-9))
    out: CoocMatrix = {}
    for (i, j), v in cooc.items():
        pij = v / total
        pi = row_tot.get(i, 0.0) / total
        pj = row_tot.get(j, 0.0) / total
        if pi <= 0.0 or pj <= 0.0:
            continue
        pmi = math.log(pij / (pi * pj)) - log_shift
        if pmi > 0.0:
            out[(i, j)] = pmi
    return out
