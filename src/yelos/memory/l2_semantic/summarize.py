"""summarize.py 在架构中的位置。

两套摘要策略(维二策略族之一):TemplateSummarizer(默认,零 LLM,结构性禁止
整句原文复述)/ AssessorSummarizer(可选增强,闸后回退,不是闸前信任)。
是隐私公理 MEM-A5 的构造性保证落点——Template 的槽位值只放关键词 token
(≤6 字),不可能拼出 ≥8 字符的原文连串。
"""

from __future__ import annotations

from typing import Callable, Protocol

from ..contracts import EpisodeEvent
from ..privacy.redact import is_verbatim_leak
from .emotion import aggregate_emotion

# 白名单情感短语表(≤12 句固定表,§3.2.4;来自 emotion.py 的四象限 label)。
_AFFECT_PHRASES: dict[str, str] = {
    "偏暖": "那阵子她心里偏暖。",
    "暖但绷": "暖是暖,但绷着一点。",
    "偏紧": "气氛有点紧。",
    "平静": "那几天平平淡淡的。",
}

_DEFAULT_PHRASE = "平静"


class Summarizer(Protocol):
    name: str

    def summarize(self, events: list[EpisodeEvent], keywords: list[str]) -> str: ...


class TemplateSummarizer:
    """默认摘要器:槽位模板确定性填充,零 LLM(D11)。"""

    name = "template"

    def summarize(self, events: list[EpisodeEvent], keywords: list[str]) -> str:
        day = events[0].day_key if events else ""
        kw = [k[:6] for k in keywords if k][:2]
        stamps = [e.affect for e in events if e.affect is not None]
        emo = aggregate_emotion(stamps)
        phrase = _AFFECT_PHRASES.get(emo["label"], _AFFECT_PHRASES[_DEFAULT_PHRASE])
        if len(kw) >= 2:
            topic_clause = f"聊到{kw[0]}、{kw[1]}"
        elif len(kw) == 1:
            topic_clause = f"聊到{kw[0]}"
        else:
            topic_clause = "聊了些事"
        day_clause = f"{day}前后" if day else "那几天"
        return f"{day_clause},{topic_clause};{phrase}"


class AssessorSummarizer:
    """增强摘要器(opt-in):把 L1 区间压成第三人称摘要,闸后回退(§3.2.4)。

    ``call_fn`` 是外呼客户端的依赖注入点(本波不含真实网络客户端实现,
    memory_assessor_summary=false 时永不构造/调用此类——零外呼由配置门控,
    非本文件职责);``call_fn`` 缺席即视为不可用,立即回退 Template。
    """

    name = "assessor"

    def __init__(
        self,
        fallback: Summarizer,
        call_fn: Callable[[list[EpisodeEvent], list[str]], str] | None = None,
        *,
        max_chars: int = 120,
    ) -> None:
        self._fallback = fallback
        self._call_fn = call_fn
        self._max_chars = max_chars

    def summarize(self, events: list[EpisodeEvent], keywords: list[str]) -> str:
        if self._call_fn is None:
            return self._fallback.summarize(events, keywords)
        try:
            text = self._call_fn(events, keywords)
        except Exception:
            return self._fallback.summarize(events, keywords)
        if not isinstance(text, str) or not text.strip():
            return self._fallback.summarize(events, keywords)
        text = text.strip()[: self._max_chars]
        l1_texts = [e.text for e in events if e.text]
        if is_verbatim_leak(text, l1_texts):
            return self._fallback.summarize(events, keywords)
        return text


def build_summarizer(
    name: str,
    *,
    assessor_call: Callable[[list[EpisodeEvent], list[str]], str] | None = None,
) -> Summarizer:
    """按配置键装配摘要器;非法名回退 template(保守默认)。"""
    template = TemplateSummarizer()
    if name == "assessor":
        return AssessorSummarizer(template, assessor_call)
    return template
