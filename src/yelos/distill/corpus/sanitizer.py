"""在整个架构中的位置:DA4(语料出身)的纵深防御闸(蓝图 §1)。

上游 ``memory.facade.corpus_view`` 已按 kind∈{her_word,dream} 过滤(她的
话唯一权威源,只吐她说过的话),本文件是第二道闸:即便上游契约漂移或
误传,``sanitize`` 也只放行"文本字段 + 结构化特征",拒绝任何自由文本
之外的字段进入 ``CorpusEntry.features``,并对已知用户侧标记做否决式扫描。
"""

from __future__ import annotations

from typing import Any

from .manifest import CorpusEntry

# 结构化特征允许的键(§3.2:P 值档、verdict、armed 状态等;无自由文本)。
_ALLOWED_FEATURE_KEYS = frozenset(
    {"p_band", "verdict", "armed", "intensity", "valence", "arousal", "kind"}
)

# 上游误传时的纵深防御:含这些键名的原始记录一律判定"疑似用户侧",丢弃。
_USER_SIDE_MARKERS = frozenset({"user_text", "user_turn", "speaker_user", "raw_user"})


class RejectedEntry(ValueError):
    """条目未通过 DA4 纵深防御,调用方应跳过而非抛出到装配主流程外。"""


def _clean_features(raw: dict) -> dict:
    affect = raw.get("affect")
    features: dict[str, Any] = {}
    if isinstance(affect, dict):
        for key in _ALLOWED_FEATURE_KEYS:
            if key in affect:
                value = affect[key]
                if isinstance(value, (str, int, float, bool)):
                    features[key] = value
    return features


def sanitize(raw: dict) -> CorpusEntry:  # DA4
    """把上游一条 corpus_view/anthology 记录收窄为 ``CorpusEntry``。

    只提取 ``text``(她说过的话本体)、``occasion``、``day_key`` 三个白名单
    字段与结构化 ``features``;任何其余字段(尤其疑似用户侧标记)一律丢弃,
    不进权重、不进 manifest。空/非字符串 text 判定为拒绝条目。
    """
    if any(marker in raw for marker in _USER_SIDE_MARKERS):
        raise RejectedEntry("疑似用户侧字段,DA4 拒收")
    text = raw.get("text")
    if not isinstance(text, str) or not text.strip():
        raise RejectedEntry("空文本,DA4 拒收")
    occasion = str(raw.get("occasion", ""))
    day_key = str(raw.get("day_key", ""))
    source = str(raw.get("_source", "memory_l1"))
    return CorpusEntry(
        text=text,
        occasion=occasion,
        day_key=day_key,
        source=source,
        features=_clean_features(raw),
    )


__all__ = ["sanitize", "RejectedEntry"]
