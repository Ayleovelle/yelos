"""service.py 在架构中的位置。

recall 子包对 facade 的编排门面:四服务面(recall/theme_digest/
baseline_context/continuity_flags)的纯函数实现 + affect_recall 工具面
(§5.6)的双模式×状态门控编排逻辑。facade.py 只转发,不在此外重复业务规则。

本文件不注册 MCP 工具(server.py 注册留给后续集成波,交建纪律);
``build_affect_recall_response`` 是纯函数,输入的 sealed/paused/bound/mode
由未来的 session 层接线时从 binding record 提取,本波先把决策表钉死。
"""

from __future__ import annotations

import hashlib
import math
from typing import Iterable

from yelos.core import ordinal7

from ..contracts import (
    AffectStamp,
    BaselineContext,
    ContinuityFlags,
    EpisodeEvent,
    RecallHit,
    RecallQuery,
    RecallResult,
    SemanticEntry,
    ThemeDigest,
    TopicNode,
)
from ..forgetting.retention import RetentionFamily
from ..l2_semantic.emotion import quadrant_label
from ..l2_semantic.entries import extract_keywords
from ..l2_semantic.linalg_lite import embed_doc
from ..l2_semantic.tokenizer import tokenize
from .scorers import RecallScorer
from .similarity import GraphPath, SimilarityBackend, VectorNN, build_cooc_graph

# --- 相似度后端装配(维二融合权,§3.5/§7)----------------------------------


class FusedBackend:
    """VectorNN 主通道 + GraphPath 融合权(memory_similarity_fusion,0=纯向量)。"""

    name = "fused"

    def __init__(
        self, primary: SimilarityBackend, secondary: SimilarityBackend, weight: float
    ) -> None:
        self._primary = primary
        self._secondary = secondary
        self._w = max(0.0, min(1.0, weight))

    def relevance(
        self, q_tokens: list[str], q_vec: list[float], e: SemanticEntry
    ) -> float:
        a = self._primary.relevance(q_tokens, q_vec, e)
        if self._w <= 0.0:
            return a
        b = self._secondary.relevance(q_tokens, q_vec, e)
        return (1.0 - self._w) * a + self._w * b


def similarity_backend_for(
    entries: list[SemanticEntry], fusion_weight: float
) -> SimilarityBackend:
    vector_nn = VectorNN()
    if fusion_weight <= 0.0:
        return vector_nn
    graph = GraphPath(build_cooc_graph(entries))
    return FusedBackend(vector_nn, graph, fusion_weight)


# --- recall 服务面(facade.recall 的正身)---------------------------------


def recall_l2(
    q: RecallQuery,
    entries: list[SemanticEntry],
    *,
    scorer: RecallScorer,
    backend: SimilarityBackend,
    fam: RetentionFamily,
    word_vecs: dict[str, list[float]],
    idf: dict[str, float],
) -> RecallResult:
    """确定性召回(MEM-A4):同库态+同 query+同 now → 逐条同分同序。"""
    q_tokens = tokenize(q.text, lang="zh") if q.text else []
    q_vec = embed_doc(q_tokens, word_vecs, idf) if q_tokens and word_vecs else []
    rel = {e.id: backend.relevance(q_tokens, q_vec, e) for e in entries}
    hits = scorer.rank(q, entries, rel, q.now_ts, fam)
    det_raw = f"{q.day_key}|{q.text}|{scorer.name}|{len(entries)}"
    det_key = hashlib.blake2b(det_raw.encode("utf-8"), digest_size=4).hexdigest()
    return RecallResult(hits=tuple(hits), scorer=scorer.name, deterministic_key=det_key)


def apply_rehearse(
    hits: Iterable[RecallHit],
    by_id: dict[str, SemanticEntry],
    now_ts: float,
    fam: RetentionFamily,
    *,
    g: float = 0.6,
) -> None:
    """访问即复述(MEM-A2):只有进入 top-k 的命中才 rehearse(MEM-A16)。"""
    from ..forgetting.retention import rehearse

    for h in hits:
        e = by_id.get(h.entry_id)
        if e is None:
            continue
        r_now = fam.R(max(0.0, now_ts - e.created_ts), e.S)
        e.S = rehearse(e.S, r_now, g=g)
        e.access_count += 1
        e.last_access_ts = now_ts


# --- theme_digest(§5.1)---------------------------------------------------


def _topic_emotion_label(
    topic: TopicNode, entries_by_id: dict[str, SemanticEntry]
) -> str:
    members = [entries_by_id[m] for m in topic.members if m in entries_by_id]
    if not members:
        return "平静"
    warm = sum(float((m.emotion or {}).get("warmth_mean", 0.0)) for m in members) / len(
        members
    )
    press = sum(
        float((m.emotion or {}).get("pressure_mean", 0.0)) for m in members
    ) / len(members)
    return quadrant_label(warm, press)


def build_theme_digest(
    day_key: str,
    topics: list[TopicNode],
    entries_by_id: dict[str, SemanticEntry],
    l1_day_events: list[EpisodeEvent],
    *,
    max_themes: int = 3,
    max_moments_kw: int = 6,
) -> ThemeDigest:
    """只读前夜已固化态(裁决 M13);themes 按当日活跃度(strength 降序)。"""
    ranked = sorted(
        (t for t in topics if t.state != "dead"), key=lambda t: (-t.strength, t.id)
    )
    themes = []
    for t in ranked[:max_themes]:
        themes.append(
            {
                "topic_id": t.id,
                "label_kw": list(t.label_kw),
                "strength_label": ordinal7(max(0.0, min(1.0, t.strength))),
                "emotion_label": _topic_emotion_label(t, entries_by_id),
            }
        )
    tokens: list[str] = []
    for ev in l1_day_events:
        if ev.kind in ("moment", "her_word"):
            text = ev.text or ev.occasion
            if text:
                tokens.extend(tokenize(text, lang="zh"))
    moments_kw = tuple(extract_keywords(tokens, top_n=max_moments_kw))
    return ThemeDigest(day_key=day_key, themes=tuple(themes), moments_kw=moments_kw)


# --- baseline_context(§5.2)------------------------------------------------


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def _collect_recent_affect(
    l1_iter: Iterable[tuple[int, EpisodeEvent]], now_ts: float, window_days: float
) -> list[AffectStamp]:
    cutoff = now_ts - window_days * 86400.0
    out = []
    for _seq, ev in l1_iter:
        if ev.affect is not None and ev.ts >= cutoff:
            out.append(ev.affect)
    return out


def build_baseline_context(
    *,
    last_user_ts: float | None,
    active_day_count: int,
    l2_count: int,
    now_ts: float,
    week_events: Iterable[tuple[int, EpisodeEvent]],
    month_events: Iterable[tuple[int, EpisodeEvent]],
) -> BaselineContext:
    """familiarity=关系厚度饱和函数;typical_* 取 7/30 日双窗更保守值(§5.2)。"""
    days_since = 9999
    if last_user_ts is not None:
        days_since = int(max(0.0, now_ts - last_user_ts) // 86400.0)

    raw = math.log1p(max(0, l2_count)) * max(0, active_day_count)
    familiarity = 1.0 - math.exp(-raw / 50.0)
    familiarity = max(0.0, min(1.0, familiarity))

    week_stamps = _collect_recent_affect(week_events, now_ts, 7)
    month_stamps = _collect_recent_affect(month_events, now_ts, 30)
    warmth_candidates = []
    pressure_candidates = []
    if week_stamps:
        warmth_candidates.append(_median([s.warmth for s in week_stamps]))
        pressure_candidates.append(_median([s.pressure for s in week_stamps]))
    if month_stamps:
        warmth_candidates.append(_median([s.warmth for s in month_stamps]))
        pressure_candidates.append(_median([s.pressure for s in month_stamps]))
    typical_warmth = min(warmth_candidates) if warmth_candidates else 0.0
    typical_pressure = min(pressure_candidates) if pressure_candidates else 0.0

    return BaselineContext(
        familiarity=familiarity,
        days_since_last_contact=days_since,
        typical_warmth=typical_warmth,
        typical_pressure=typical_pressure,
        sample_days=active_day_count,
    )


# --- continuity_flags(§5.3)------------------------------------------------


def build_continuity_flags(
    baseline: BaselineContext,
    topics: list[TopicNode],
    *,
    reunion_days: int = 7,
    min_history_days: int = 3,
    long_bond_familiarity: float = 0.6,
) -> ContinuityFlags:
    reunion = (
        baseline.days_since_last_contact >= reunion_days
        and baseline.sample_days >= min_history_days
    )
    long_bond = baseline.familiarity >= long_bond_familiarity
    active_themes = sum(1 for t in topics if t.state == "active")
    return ContinuityFlags(
        reunion=reunion, long_bond=long_bond, active_themes=active_themes
    )


# --- affect_recall 工具面(§5.6,双模式×状态门控决策表)--------------------

NOTE_WHITELIST: tuple[str, ...] = (
    "这段日子聊得多的,大概是这些。",
    "有些事她记得比你以为的久。",
    "隔了些日子了,她还留着上次的印象。",
    "",
)


def _pick_note(reunion: bool, active_themes: int, hits: tuple[RecallHit, ...]) -> str:
    if reunion:
        return NOTE_WHITELIST[2]
    if active_themes >= 3:
        return NOTE_WHITELIST[0]
    if hits and hits[0].factors.get("recency", 1.0) < 0.3:
        return NOTE_WHITELIST[1]
    return NOTE_WHITELIST[3]


def build_affect_recall_response(
    *,
    memory_enabled: bool,
    sealed: bool,
    bound: bool,
    paused: bool,
    mode: str,
    hits: tuple[RecallHit, ...],
    themes_active: tuple[str, ...],
    continuity: ContinuityFlags,
    days_since_last_contact: int,
    topics_by_id: dict[str, TopicNode] | None = None,
) -> dict:
    """§5.6 决策表的编排正身:memory_enabled > sealed > 未绑定 > steward/paused。"""
    if not memory_enabled:
        return {"disabled": True}
    if sealed:
        return {"sealed": True}
    if not bound:
        return {
            "hits": [],
            "themes_active": [],
            "continuity": {
                "days_since_last_contact": 0,
                "reunion": False,
            },
            "note": "",
        }

    topics_by_id = topics_by_id or {}
    steward_like = (mode == "steward") or paused
    note = (
        ""
        if steward_like
        else _pick_note(continuity.reunion, continuity.active_themes, hits)
    )

    hit_dicts = []
    for h in hits:
        topic_label = topics_by_id.get(h.topic_id)
        topic_str = (
            "".join(topic_label.label_kw[:2])
            if topic_label is not None
            else "、".join(h.keywords[:2])
        )
        hit_dicts.append(
            {
                "summary": h.summary,
                "keywords": list(h.keywords),
                "when": h.day_key,
                "topic": topic_str,
                "strength": h.strength_label,
                "affect_label": "",
            }
        )

    return {
        "hits": hit_dicts,
        "themes_active": list(themes_active)[:5],
        "continuity": {
            "days_since_last_contact": days_since_last_contact,
            "reunion": continuity.reunion,
        },
        "note": note,
    }
