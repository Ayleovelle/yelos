"""cluster.py 在架构中的位置。

夜窗归类/合并/分裂判定(全确定性,阈值全入参,§3.3 决策表)。双证据原则:
向量近邻 + 关键词交集同时满足才归入既有主题(防向量幻聚);无向量时只做
关键词共现社区维持,不 merge/split(双证据缺一不动刀,保守优先)。
"""

from __future__ import annotations

from ..contracts import SemanticEntry, TopicNode
from ..l2_semantic.linalg_lite import cosine


def compute_centroid(vecs: list[list[float]]) -> list[float]:
    """成员向量质心(均值 + L2 归一);空表返回空表。"""
    vecs = [v for v in vecs if v]
    if not vecs:
        return []
    dim = len(vecs[0])
    acc = [0.0] * dim
    for v in vecs:
        if len(v) != dim:
            continue
        for i in range(dim):
            acc[i] += v[i]
    n = len(vecs)
    acc = [x / n for x in acc]
    norm = sum(x * x for x in acc) ** 0.5
    if norm < 1e-12:
        return acc
    return [x / norm for x in acc]


def assign_topic(
    entry: SemanticEntry, topics: list[TopicNode], theta_assign: float
) -> str | None:
    """双证据归入判定:cos>=theta_assign 且关键词交集>=1;并列取 cos 最高,
    再并列取 topic id 字典序最小(确定性 tie-break)。"""
    if not entry.vec:
        return None
    best_id: str | None = None
    best_cos = -2.0
    for t in topics:
        if t.state == "dead" or not t.centroid:
            continue
        cos_val = cosine(entry.vec, t.centroid)
        if cos_val < theta_assign:
            continue
        if not (set(entry.keywords) & set(t.label_kw)):
            continue
        if cos_val > best_cos or (
            cos_val == best_cos and (best_id is None or t.id < best_id)
        ):
            best_cos = cos_val
            best_id = t.id
    return best_id


def connected_components(
    entries: list[SemanticEntry], theta_assign: float
) -> list[list[SemanticEntry]]:
    """未归入条目间两两 cos>=theta_assign 的连通团(并查集),仅返回 size>=2 团。"""
    n = len(entries)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            if entries[i].vec and entries[j].vec:
                if cosine(entries[i].vec, entries[j].vec) >= theta_assign:
                    union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return [
        [entries[i] for i in sorted(idxs)]
        for _root, idxs in sorted(groups.items())
        if len(idxs) >= 2
    ]


def _elder_younger(a: TopicNode, b: TopicNode) -> tuple[TopicNode, TopicNode]:
    """长幼判定:born_day 更早者为长者;并列按 id 字典序破(确定性)。"""
    if a.born_day != b.born_day:
        return (a, b) if a.born_day < b.born_day else (b, a)
    return (a, b) if a.id < b.id else (b, a)


def merge_candidates(
    topics: list[TopicNode],
    theta_merge: float,
    streak: dict[str, int],
    *,
    required_nights: int = 3,
) -> tuple[list[tuple[str, str]], dict[str, int]]:
    """连续 required_nights 夜质心 cos>=theta_merge 才判定 merge;streak 是
    跨夜持久计数(由调用方 TopicStore.merge_streak 传入并回收更新结果)。"""
    active = [t for t in topics if t.state in ("active", "nascent")]
    new_streak: dict[str, int] = {}
    fires: list[tuple[str, str]] = []
    for i in range(len(active)):
        for j in range(i + 1, len(active)):
            a, b = active[i], active[j]
            if not a.centroid or not b.centroid:
                continue
            key = "|".join(sorted([a.id, b.id]))
            cos_val = cosine(a.centroid, b.centroid)
            count = (streak.get(key, 0) + 1) if cos_val >= theta_merge else 0
            if count > 0:
                new_streak[key] = count
            if count >= required_nights:
                elder, younger = _elder_younger(a, b)
                fires.append((elder.id, younger.id))
    return fires, new_streak


def split_candidates(
    topic: TopicNode,
    member_entries: list[SemanticEntry],
    theta_split: float,
    theta_assign: float,
) -> list[list[str]] | None:
    """质心距离中位 < theta_split 且成员图分裂为 >=2 个 size>=3 连通块才分裂。

    返回按块分组的 entry_id 列表(第 0 块留给母题,其余各自成新子题);
    条件不满足返回 None(双证据缺一不动刀)。
    """
    usable = [e for e in member_entries if e.vec]
    if len(usable) < 6 or not topic.centroid:
        return None
    dists = sorted(cosine(e.vec, topic.centroid) for e in usable)
    n = len(dists)
    mid = dists[n // 2] if n % 2 == 1 else (dists[n // 2 - 1] + dists[n // 2]) / 2.0
    if mid >= theta_split:
        return None

    m = len(usable)
    parent = list(range(m))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(m):
        for j in range(i + 1, m):
            if cosine(usable[i].vec, usable[j].vec) >= theta_assign:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(m):
        groups.setdefault(find(i), []).append(i)
    blocks = [idxs for idxs in groups.values() if len(idxs) >= 3]
    if len(blocks) < 2:
        return None
    blocks.sort(key=lambda idxs: min(usable[i].id for i in idxs))
    return [[usable[i].id for i in sorted(idxs)] for idxs in blocks]
