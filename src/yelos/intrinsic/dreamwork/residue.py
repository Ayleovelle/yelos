"""dreamwork/residue.py 在整个架构中的位置:DreamResidue schema + 默认生成器(§4.1/§4.2)。

**白名单纪律的梦语版**:`theme_keys` ⊆(当日 moments 的 MomentKind 键)∪
(memory L2 关键词接口经编排层展平而来的 top-k 键)——residue **不含任何
自由文本**,theme_keys/mood/intensity 只是**选择器**;primal 侧 dream_murmur
按 `h("dream", sid, day_key, theme_keys)` 从封闭句集里确定性选句,主题
决定选哪一族,永不插值进句子(本文件不生成、不触碰任何句子文本)。

`sanitize_theme_source` 是两套生成器共用的前置过滤:借 primal 禁形表
把候选池里混入的伪造原文片段拦在候选阶段(对抗集测试 T-DRM-03)。
"""

from __future__ import annotations

from dataclasses import dataclass

from yelos.primal.whitelist_gate import load_forbidden_patterns

from ..field.state import FieldState
from ..moments.taxonomy import MomentEntry

_MOOD_BANDS = ("warm", "wistful", "heavy")
MAX_THEME_KEYS = 3


@dataclass(frozen=True)
class DreamResidue:
    theme_keys: tuple[str, ...]
    intensity: float
    mood: str

    def to_dict(self) -> dict:
        return {
            "theme_keys": list(self.theme_keys),
            "intensity": self.intensity,
            "mood": self.mood,
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "DreamResidue | None":
        if not d:
            return None
        return cls(
            theme_keys=tuple(d.get("theme_keys", ())),
            intensity=float(d.get("intensity", 0.0)),
            mood=str(d.get("mood", "wistful")),
        )


def sanitize_theme_source(
    keys: tuple[str, ...], *, lang: str = "zh"
) -> tuple[str, ...]:
    """把候选主题键池按禁形表过滤(§4.2 三锁之一)。

    Tier-R/S 的完整闸门是给整句用的(primal.composer 才有 band/epoch/corpus
    语境);此处只借禁形表这一层(load_forbidden_patterns 与 concern_only
    标记),做候选**键**级别的纵深防御——键本身若含被禁片段(对抗集构造),
    直接被剔除,不进入任一生成器的候选池。
    """
    patterns = load_forbidden_patterns(lang)
    if not patterns:
        return keys
    out = []
    for key in keys:
        blocked = False
        for pat, concern_only in patterns:
            if concern_only:
                continue  # concern_only 规则只在 concern 场合生效,dream 场合跳过
            if pat.search(key):
                blocked = True
                break
        if not blocked:
            out.append(key)
    return tuple(out)


def _closed_candidates(
    day_moments: tuple[MomentEntry, ...] | list[MomentEntry],
    l2_keywords: tuple[str, ...],
) -> tuple[str, ...]:
    """主题来源封闭集(§4.2):当日 moments 键 ∪ L2 关键词,去重保序,先过滤禁形。"""
    moment_keys = [str(m.kind) for m in day_moments]
    combined = list(dict.fromkeys(moment_keys + list(l2_keywords)))
    return sanitize_theme_source(tuple(combined))


def _night_means(night_phi_trace: list[FieldState]) -> tuple[float, float]:
    if not night_phi_trace:
        return 0.0, 0.0
    n = len(night_phi_trace)
    mean_longing = sum(s.longing for s in night_phi_trace) / n
    mean_afterglow = sum(s.afterglow for s in night_phi_trace) / n
    mean_languor = sum(s.languor for s in night_phi_trace) / n
    return mean_longing, (mean_afterglow / (mean_languor + 1e-6))


def _mood_from_ratio(ratio: float) -> str:
    if ratio >= 1.0:
        return "warm"
    if ratio >= 0.4:
        return "wistful"
    return "heavy"


def _rank_score(
    key: str, moment_freq: dict[str, int], l2_rank: dict[str, int], n_l2: int
) -> tuple[float, str]:
    """确定性排序键:(分数降序, 字母序打平)。"""
    score = float(moment_freq.get(key, 0)) * 2.0
    if key in l2_rank:
        score += float(n_l2 - l2_rank[key])
    return (-score, key)


class ResidueAggregation:
    """默认生成器 —— 聚合统计出身(§4.2 之一):频次 × L2 权重的确定性 top-k。"""

    name = "residue_aggregation"

    def generate(
        self,
        night_phi_trace: list[FieldState],
        day_moments: list[MomentEntry],
        l2_keywords: tuple[str, ...],
        hash_seed: str,
    ) -> DreamResidue:
        candidates = _closed_candidates(day_moments, l2_keywords)
        moment_freq: dict[str, int] = {}
        for m in day_moments:
            moment_freq[str(m.kind)] = moment_freq.get(str(m.kind), 0) + 1
        l2_rank = {k: i for i, k in enumerate(l2_keywords)}
        ranked = sorted(
            candidates,
            key=lambda k: _rank_score(k, moment_freq, l2_rank, len(l2_keywords)),
        )
        theme_keys = tuple(ranked[:MAX_THEME_KEYS])

        mean_longing, ratio = _night_means(night_phi_trace)
        intensity = max(0.0, min(1.0, mean_longing))
        mood = _mood_from_ratio(ratio)
        return DreamResidue(theme_keys=theme_keys, intensity=intensity, mood=mood)


def residue_to_render_context(residue: DreamResidue) -> dict:
    """[W-2] DreamResidue → primal.composer.compose 的 `context` 载荷。

    `primal.providers.template.TemplateGrammarProvider` 对 `occasion=
    "dream_murmur"` 认 `context["theme"]` 这一个键(§4.2"选择器,不插值
    文本"——只给 primal 一个封闭集内的候选词,句子本身仍由 primal 侧攒)。
    `theme_keys` 可能有多个,取首位(排序已由生成器决定优先级);residue
    为 None(尚无武装)时返回空 dict,composer 侧自然走无主题的兜底路由。
    """
    if residue is None or not residue.theme_keys:
        return {}
    return {
        "theme": residue.theme_keys[0],
        "mood": residue.mood,
        "intensity": residue.intensity,
    }


__all__ = [
    "DreamResidue",
    "ResidueAggregation",
    "sanitize_theme_source",
    "MAX_THEME_KEYS",
    "residue_to_render_context",
]
