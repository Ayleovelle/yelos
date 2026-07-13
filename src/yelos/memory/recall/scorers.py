"""scorers.py 在架构中的位置。

三套独立理论出身的打分器(维二策略族,§4):LinearScorer(加权效用,默认)/
RRFScorer(排序融合,Cormack RRF)/ EmotionFirstScorer(情绪一致性特权,
mood-congruent retrieval)。四因子(relevance/recency/frequency/emotion)
全打分器共用、可分解审计(MEM-T2)。并列破序:blake2b(entry_id) 字典序
(MEM-A4)。
"""

from __future__ import annotations

import hashlib
import math
from typing import Protocol

from yelos.core import ordinal7

from ..contracts import AffectStamp, RecallHit, RecallQuery, SemanticEntry
from ..forgetting.retention import RetentionFamily

ACC_CAP = 10.0
_RRF_K = 60


def _tie_key(entry_id: str) -> bytes:
    return hashlib.blake2b(entry_id.encode("utf-8"), digest_size=8).digest()


def _recency(e: SemanticEntry, now_ts: float, fam: RetentionFamily) -> float:
    dt = max(0.0, now_ts - e.created_ts)
    return fam.R(dt, e.S)


def _frequency(e: SemanticEntry) -> float:
    return math.log1p(max(0, e.access_count)) / math.log1p(ACC_CAP)


def _emotion(e: SemanticEntry, q_affect: AffectStamp | None) -> float:
    if q_affect is None:
        return 0.5
    warmth_mean = 0.0
    if isinstance(e.emotion, dict):
        warmth_mean = float(e.emotion.get("warmth_mean", 0.0) or 0.0)
    return 1.0 - min(1.0, abs(q_affect.warmth - warmth_mean))


def _build_factors(
    e: SemanticEntry,
    rel: float,
    now_ts: float,
    fam: RetentionFamily,
    q_affect: AffectStamp | None,
) -> dict[str, float]:
    return {
        "relevance": max(0.0, min(1.0, rel)),
        "recency": max(0.0, min(1.0, _recency(e, now_ts, fam))),
        "frequency": max(0.0, min(1.0, _frequency(e))),
        "emotion": max(0.0, min(1.0, _emotion(e, q_affect))),
    }


def _make_hit(
    e: SemanticEntry, layer: str, score: float, factors: dict[str, float]
) -> RecallHit:
    return RecallHit(
        entry_id=e.id,
        layer=layer,
        score=score,
        factors=factors,
        summary=e.summary,
        keywords=list(e.keywords),
        day_key=e.day_key,
        topic_id=e.topic_id,
        strength_label=ordinal7(factors["recency"]),
    )


class RecallScorer(Protocol):
    name: str

    def rank(
        self,
        q: RecallQuery,
        cands: list[SemanticEntry],
        rel: dict[str, float],
        now_ts: float,
        fam: RetentionFamily,
    ) -> list[RecallHit]: ...


class LinearScorer:
    """默认打分器:score = w_rel*rel + w_rec*rec + w_freq*freq + w_emo*emo。"""

    name = "linear"

    def __init__(
        self,
        weights: tuple[float, float, float, float] = (0.45, 0.25, 0.10, 0.20),
    ) -> None:
        self._w = weights

    def rank(
        self,
        q: RecallQuery,
        cands: list[SemanticEntry],
        rel: dict[str, float],
        now_ts: float,
        fam: RetentionFamily,
    ) -> list[RecallHit]:
        w_rel, w_rec, w_freq, w_emo = self._w
        hits = []
        for e in cands:
            factors = _build_factors(e, rel.get(e.id, 0.0), now_ts, fam, q.affect)
            score = (
                w_rel * factors["relevance"]
                + w_rec * factors["recency"]
                + w_freq * factors["frequency"]
                + w_emo * factors["emotion"]
            )
            hits.append(_make_hit(e, "L2", score, factors))
        hits.sort(key=lambda h: (-h.score, _tie_key(h.entry_id)))
        return hits[: max(0, q.k)]


class RRFScorer:
    """排序融合(Cormack Reciprocal Rank Fusion):四因子各自排一榜,
    score = Σ 1/(RRF_K + rank_i);对因子标定误差鲁棒。"""

    name = "rrf"

    def rank(
        self,
        q: RecallQuery,
        cands: list[SemanticEntry],
        rel: dict[str, float],
        now_ts: float,
        fam: RetentionFamily,
    ) -> list[RecallHit]:
        if not cands:
            return []
        factor_map: dict[str, dict[str, float]] = {}
        for e in cands:
            factor_map[e.id] = _build_factors(
                e, rel.get(e.id, 0.0), now_ts, fam, q.affect
            )

        def _ranked_ids(factor_name: str) -> list[str]:
            return sorted(
                (e.id for e in cands),
                key=lambda eid: (-factor_map[eid][factor_name], _tie_key(eid)),
            )

        rrf_score: dict[str, float] = {e.id: 0.0 for e in cands}
        for factor_name in ("relevance", "recency", "frequency", "emotion"):
            for rank, eid in enumerate(_ranked_ids(factor_name)):
                rrf_score[eid] += 1.0 / (_RRF_K + rank + 1)

        by_id = {e.id: e for e in cands}
        hits = [
            _make_hit(by_id[eid], "L2", score, factor_map[eid])
            for eid, score in rrf_score.items()
        ]
        hits.sort(key=lambda h: (-h.score, _tie_key(h.entry_id)))
        return hits[: max(0, q.k)]


class EmotionFirstScorer:
    """情绪一致性特权检索(mood-congruent):emotion>=阈值的候选池内先按
    rel+rec 排;池空再全池线性(降级恒可用)。"""

    name = "emotion_first"

    def __init__(self, emo_threshold: float = 0.65) -> None:
        self._threshold = emo_threshold
        self._fallback = LinearScorer()

    def rank(
        self,
        q: RecallQuery,
        cands: list[SemanticEntry],
        rel: dict[str, float],
        now_ts: float,
        fam: RetentionFamily,
    ) -> list[RecallHit]:
        factor_map: dict[str, dict[str, float]] = {}
        for e in cands:
            factor_map[e.id] = _build_factors(
                e, rel.get(e.id, 0.0), now_ts, fam, q.affect
            )
        pool = [e for e in cands if factor_map[e.id]["emotion"] >= self._threshold]
        if not pool:
            return self._fallback.rank(q, cands, rel, now_ts, fam)
        hits = []
        for e in pool:
            f = factor_map[e.id]
            score = 0.6 * f["relevance"] + 0.4 * f["recency"]
            hits.append(_make_hit(e, "L2", score, f))
        hits.sort(key=lambda h: (-h.score, _tie_key(h.entry_id)))
        return hits[: max(0, q.k)]


_SCORERS: dict[str, RecallScorer] = {
    "linear": LinearScorer(),
    "rrf": RRFScorer(),
    "emotion_first": EmotionFirstScorer(),
}


def get_scorer(name: str) -> RecallScorer:
    """按配置键取打分器;未知名回退 linear(可解释、默认,§4)。"""
    return _SCORERS.get(name, _SCORERS["linear"])
