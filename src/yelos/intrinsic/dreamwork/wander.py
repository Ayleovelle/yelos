"""dreamwork/wander.py 在整个架构中的位置:随机漫游生成器(§4.2 之二,维二计 2)。

**出身**:随机漫游——在她自己说过的话(utterances 语料)+ moments 键序列上
建**键级**马尔可夫式漫游(哈希驱动而非真随机,AX-7);产物仍是**键组合**
(不产文本)。语料空(孵化早期)⇒ 协议性不可用、干净缺席,走
`ResidueAggregation` 默认(回退链,T-DRM-04)。

"过 primal.whitelist_gate 语义校验"(§4.2)在键级别的落地:候选池先经
`residue.sanitize_theme_source` 过滤禁形片段(纵深防御第一层);漫游选出
的键组合再逐个复核(纵深防御第二层,防止漫游步骤本身从非法来源引入
候选)。任一复核不过 ⇒ 回退默认生成器,不产半成品。
"""

from __future__ import annotations

from yelos.primal.determinism import h_bytes

from ..field.state import FieldState
from ..moments.taxonomy import MomentEntry
from .residue import (
    MAX_THEME_KEYS,
    DreamResidue,
    ResidueAggregation,
    _closed_candidates,
    _night_means,
    _mood_from_ratio,
    sanitize_theme_source,
)


def _hashed_index(key: str, modulus: int) -> int:
    if modulus <= 0:
        return 0
    raw = h_bytes(key, 4)
    return int.from_bytes(raw, "big") % modulus


class MarkovWander:
    """随机漫游出身(§4.2 之二);语料空/校验不过一律回退 `ResidueAggregation`。"""

    name = "markov_wander"

    def __init__(self, fallback: ResidueAggregation | None = None) -> None:
        self._fallback = fallback or ResidueAggregation()

    def available(self, utterance_corpus: tuple[str, ...]) -> bool:
        """协议性可用判定:语料非空(潜伏 provider 纪律同款,T-DRM-05)。"""
        return len(utterance_corpus) > 0

    def generate(
        self,
        night_phi_trace: list[FieldState],
        day_moments: list[MomentEntry],
        l2_keywords: tuple[str, ...],
        hash_seed: str,
        utterance_corpus: tuple[str, ...] = (),
    ) -> DreamResidue:
        if not self.available(utterance_corpus):
            return self._fallback.generate(
                night_phi_trace, day_moments, l2_keywords, hash_seed
            )

        candidates = list(_closed_candidates(day_moments, l2_keywords))
        if not candidates:
            return self._fallback.generate(
                night_phi_trace, day_moments, l2_keywords, hash_seed
            )

        chosen: list[str] = []
        pool = list(candidates)
        step_count = min(MAX_THEME_KEYS, len(pool))
        for i in range(step_count):
            key = f"dream|{hash_seed}|mkv|{i}"
            idx = _hashed_index(key, len(pool))
            chosen.append(pool.pop(idx))

        theme_keys = sanitize_theme_source(tuple(chosen))
        if len(theme_keys) != len(chosen):
            # 复核未全过(有键被禁形表拦下)→ 不产半成品,干净回退。
            return self._fallback.generate(
                night_phi_trace, day_moments, l2_keywords, hash_seed
            )

        mean_longing, ratio = _night_means(night_phi_trace)
        intensity = max(0.0, min(1.0, mean_longing))
        mood = _mood_from_ratio(ratio)
        return DreamResidue(theme_keys=theme_keys, intensity=intensity, mood=mood)


__all__ = ["MarkovWander"]
