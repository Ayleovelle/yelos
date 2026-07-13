"""Tier-S 成员/非成员;Tier-R 五条件逐条反例;对抗集 fixture;

兜底被拒的 critical 路径。锁 A1a/A1b/§6.1。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yelos.primal.lexicon.closure import enumerate_closure
from yelos.primal.whitelist_gate import WhitelistGate, load_forbidden_patterns

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "adversarial_outputs.json"


def _closure_fn(occasion, lang, band, epoch):
    return enumerate_closure(occasion, lang, band, epoch)


def _gate() -> WhitelistGate:
    return WhitelistGate(_closure_fn, forbidden_patterns=load_forbidden_patterns("zh"))


# --- Tier-S 成员/非成员 ---------------------------------------------------


def test_tier_s_member_ok():
    gate = _gate()
    canon = enumerate_closure("concern", "zh", "B4", epoch=0)
    member = next(iter(canon))
    result = gate.check(member, "concern", "zh", "B4", 0, corpus=())
    assert result.ok
    assert result.tier == "S"
    assert result.reason == "member"


def test_tier_s_not_member_rejected():
    gate = _gate()
    result = gate.check("这不是任何一个合法句子。", "concern", "zh", "B4", 0, corpus=())
    assert not result.ok
    assert result.reason == "not_member"


def test_tier_s_applies_to_all_eight_core_occasions():
    gate = _gate()
    for occasion in (
        "withdraw_heavy",
        "withdraw_soft",
        "hold_hesitant",
        "express_warm",
        "recover",
        "concern",
        "contact_seek",
        "contact_night",
    ):
        canon = enumerate_closure(occasion, "zh", "B4", epoch=0)
        member = next(iter(canon))
        result = gate.check(member, occasion, "zh", "B4", 0, corpus=())
        assert result.ok and result.tier == "S"


# --- Tier-R 五条件逐条反例 --------------------------------------------------


def test_tier_r_too_long_rejected():
    gate = _gate()
    long_text = "这是一句刻意拼得超过二十个字符的重组梦话文本内容。"
    result = gate.check(
        long_text, "dream_murmur", "zh", "B4", 0, corpus=("测试语料。",)
    )
    assert not result.ok
    assert result.reason == "too_long"


def test_tier_r_bad_terminator_rejected():
    gate = _gate()
    result = gate.check(
        "没有终结符啊", "trim_tail", "zh", "B4", 0, corpus=("没有终结符啊哈。",)
    )
    assert not result.ok
    assert result.reason == "bad_terminator"


def test_tier_r_alien_char_rejected():
    gate = _gate()
    corpus = ("梦里好像有雨。",)
    result = gate.check("梦里ZZ。", "dream_murmur", "zh", "B4", 0, corpus=corpus)
    assert not result.ok
    assert result.reason == "alien_char"


def test_tier_r_trigram_alien_rejected():
    gate = _gate()
    corpus = ("今天天气很好。", "路上遇见了猫。")
    # 字符表都来自语料,但三元组拼接不曾出现过 —— 拼接攻击的核心反例。
    result = gate.check("好路上遇。", "trim_tail", "zh", "B4", 0, corpus=corpus)
    assert not result.ok
    assert result.reason == "trigram_alien"


def test_tier_r_full_sentence_in_canon_accepted_even_if_corpus_empty():
    gate = _gate()
    canon = enumerate_closure("trim_tail", "zh", "B4", epoch=0)
    member = next(iter(canon))
    result = gate.check(member, "trim_tail", "zh", "B4", 0, corpus=())
    assert result.ok and result.tier == "R" and result.reason == "member"


def test_tier_r_band_low_rejects_long_sentences():
    gate = _gate()
    corpus = ("一二三四五六七八九十一二三。",)
    text = "一二三四五六七八九十一二三。"  # 13 字,超过 B0/B1 的 12 字硬界
    result = gate.check(text, "trim_tail", "zh", "B0", 0, corpus=corpus)
    assert not result.ok
    assert result.reason == "too_long"


# --- 对抗集 fixture(红队样本固化,只增不删)-------------------------------


def _load_adversarial_cases():
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    return data["cases"]


@pytest.mark.parametrize("case", _load_adversarial_cases(), ids=lambda c: c["name"])
def test_adversarial_fixture_all_blocked(case):
    gate = _gate()
    corpus = ("今天天气很好。", "路上遇见了猫。", "梦里好像有雨。")
    result = gate.check(
        case["canonical"], case["occasion"], "zh", "B4", 0, corpus=corpus
    )
    assert result.ok == case["expect_ok"]
    if not case["expect_ok"]:
        assert result.reason == case["expect_reason"], (
            f"{case['name']}: expected reason={case['expect_reason']!r}, "
            f"got {result.reason!r}"
        )


# --- forbidden 表:concern 额外最严档 ----------------------------------


def test_concern_only_pattern_blocks_concern_but_not_others():
    gate = _gate()
    text = "应该没事的吧。"
    concern_result = gate.check(text, "concern", "zh", "B4", 0, corpus=())
    assert not concern_result.ok
    assert concern_result.reason == "forbidden_pattern"
