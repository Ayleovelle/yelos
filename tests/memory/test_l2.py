"""test_l2.py:L2 摘要/情感/词表索引(单元)。

锁摘要模板槽位约束(无 >=8 字符原文连串)、emotion 只出自 AffectStamp
(MEM-A7,AST + 运行时)、fold-in 与 refit 决策表、assessor 降级路径专测。
"""

from __future__ import annotations

import ast
import inspect

from yelos.memory.contracts import AffectStamp, EpisodeEvent
from yelos.memory.consolidation.schedule import should_refit
from yelos.memory.l2_semantic import emotion as emotion_mod
from yelos.memory.l2_semantic.emotion import aggregate_emotion, quadrant_label
from yelos.memory.l2_semantic.entries import (
    L2Store,
    VocabIndexStore,
    build_semantic_entry,
    extract_keywords,
)
from yelos.memory.l2_semantic.summarize import (
    AssessorSummarizer,
    TemplateSummarizer,
    build_summarizer,
)
from yelos.memory.privacy.redact import is_verbatim_leak


def _ev(text: str, day_key="2024-01-01", warmth=0.6, pressure=0.2) -> EpisodeEvent:
    return EpisodeEvent(
        kind="user_turn",
        ts=0.0,
        day_key=day_key,
        text=text,
        affect=AffectStamp(warmth=warmth, pressure=pressure, contact=0.5, quiet=0.1),
    )


def test_template_summary_has_no_verbatim_run_of_l1_text():
    events = [
        _ev("今天天气特别好我们一起去公园散步聊了很多有趣的话题关于未来的计划"),
        _ev("然后又去吃了很喜欢的那家火锅店感觉整个人都被治愈了呢真好呀"),
    ]
    keywords = extract_keywords(["公园", "散步", "火锅", "计划"], top_n=4)
    summary = TemplateSummarizer().summarize(events, keywords)
    l1_texts = [e.text for e in events]
    assert not is_verbatim_leak(summary, l1_texts, min_run=8)


def test_template_summary_uses_day_and_affect_phrase():
    events = [
        _ev(
            "聊天内容随便写点什么进去凑数长度够了",
            day_key="2024-01-05",
            warmth=0.7,
            pressure=0.1,
        )
    ]
    summary = TemplateSummarizer().summarize(events, ["猫咪"])
    assert "2024-01-05" in summary
    assert "偏暖" in summary or "暖" in summary


def test_template_summary_handles_empty_events():
    assert TemplateSummarizer().summarize([], []) != ""


def test_assessor_summarizer_falls_back_without_call_fn():
    events = [_ev("一些普通的聊天内容用来测试摘要器的行为表现")]
    summarizer = AssessorSummarizer(TemplateSummarizer(), call_fn=None)
    out = summarizer.summarize(events, ["测试"])
    assert out == TemplateSummarizer().summarize(events, ["测试"])


def test_assessor_summarizer_falls_back_when_call_raises():
    events = [_ev("一些普通的聊天内容用来测试摘要器的行为表现")]

    def _boom(_events, _keywords):
        raise RuntimeError("network down")

    summarizer = AssessorSummarizer(TemplateSummarizer(), call_fn=_boom)
    out = summarizer.summarize(events, ["测试"])
    assert out == TemplateSummarizer().summarize(events, ["测试"])


def test_assessor_summarizer_falls_back_when_output_leaks_verbatim():
    original = "今天天气特别好我们一起去公园散步聊了很多有趣的话题"
    events = [_ev(original)]

    def _leaky(_events, _keywords):
        return original  # 原样照抄,应被 is_verbatim_leak 闸拦

    summarizer = AssessorSummarizer(TemplateSummarizer(), call_fn=_leaky)
    out = summarizer.summarize(events, ["话题"])
    assert out != original
    assert out == TemplateSummarizer().summarize(events, ["话题"])


def test_assessor_summarizer_accepts_clean_output():
    events = [_ev("今天天气特别好我们一起去公园散步聊了很多有趣的话题")]

    def _clean(_events, _keywords):
        return "他们聊到了公园与散步的趣事。"

    summarizer = AssessorSummarizer(TemplateSummarizer(), call_fn=_clean)
    out = summarizer.summarize(events, ["公园"])
    assert out == "他们聊到了公园与散步的趣事。"


def test_build_summarizer_unknown_name_falls_back_to_template():
    s = build_summarizer("nonexistent")
    assert s.name == "template"


def test_emotion_never_consumes_text_parameter():
    """AST 锁:emotion.py 任何函数签名都不含 text 参数(MEM-A7)。"""
    src = inspect.getsource(emotion_mod)
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            arg_names = [a.arg for a in node.args.args]
            assert "text" not in arg_names, f"{node.name} 不应接受 text 参数"


def test_aggregate_emotion_from_stamps_only():
    stamps = [
        AffectStamp(warmth=0.8, pressure=0.1, contact=0.5, quiet=0.1),
        AffectStamp(warmth=0.6, pressure=0.2, contact=0.5, quiet=0.1),
    ]
    out = aggregate_emotion(stamps)
    assert abs(out["warmth_mean"] - 0.7) < 1e-9
    assert out["label"] == quadrant_label(0.7, 0.15)


def test_aggregate_emotion_empty_is_neutral():
    out = aggregate_emotion([])
    assert out["label"] == "平静"
    assert out["warmth_mean"] == 0.0


def test_build_semantic_entry_assembles_keywords_and_summary(tmp_path):
    events = [_ev("我们聊到了很多关于旅行的计划真的很期待呢")]
    entry = build_semantic_entry(
        "sidhash",
        0,
        (0, 0),
        events,
        summarizer=TemplateSummarizer(),
        now_ts=100.0,
    )
    assert entry is not None
    assert entry.day_key == "2024-01-01"
    assert entry.summary
    assert entry.S == 1.0


def test_build_semantic_entry_empty_events_returns_none():
    assert (
        build_semantic_entry(
            "sid", 0, (0, 0), [], summarizer=TemplateSummarizer(), now_ts=0.0
        )
        is None
    )


def test_l2_store_roundtrip_atomic_write(tmp_path):
    store = L2Store(tmp_path, "sidx", 0)
    events = [_ev("聊到了猫咪和音乐的事情觉得很开心呢")]
    entry = build_semantic_entry(
        "sidx", 0, (0, 0), events, summarizer=TemplateSummarizer(), now_ts=1.0
    )
    store.add(entry)
    store.save()

    reloaded = L2Store(tmp_path, "sidx", 0)
    assert reloaded.count() == 1
    assert reloaded.get(entry.id).summary == entry.summary


def test_vocab_index_store_roundtrip(tmp_path):
    idx = VocabIndexStore(tmp_path, "sidy", 0)
    idx.vocab.fit_update([["a", "b", "a"], ["b", "c"]])
    idx.word_vecs = {"a": [1.0, 0.0], "b": [0.0, 1.0]}
    idx.idf = {"a": 1.0, "b": 1.0}
    idx.last_refit_night = "2024-01-01"
    idx.save()

    reloaded = VocabIndexStore(tmp_path, "sidy", 0)
    assert reloaded.has_basis()
    assert reloaded.word_vecs["a"] == [1.0, 0.0]
    assert reloaded.last_refit_night == "2024-01-01"


def test_should_refit_decision_table():
    assert (
        should_refit(
            has_basis=False, l2_count=10, new_token_ratio=0.0, nights_since_refit=0
        )
        == "skip"
    )
    assert (
        should_refit(
            has_basis=False, l2_count=40, new_token_ratio=0.0, nights_since_refit=0
        )
        == "refit"
    )
    assert (
        should_refit(
            has_basis=True, l2_count=40, new_token_ratio=0.5, nights_since_refit=0
        )
        == "refit"
    )
    assert (
        should_refit(
            has_basis=True, l2_count=40, new_token_ratio=0.0, nights_since_refit=20
        )
        == "refit"
    )
    assert (
        should_refit(
            has_basis=True, l2_count=40, new_token_ratio=0.0, nights_since_refit=1
        )
        == "fold_in"
    )
