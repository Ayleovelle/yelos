"""test_tokenizer.py:三语分词(单元 + golden)。

锁三语 golden 输出、确定性(同输入同输出)、停用表生效、非法 lang 回退 zh。
"""

from __future__ import annotations

from yelos.memory.l2_semantic.tokenizer import tokenize


def test_zh_char_bigram_and_ascii_word():
    toks = tokenize("我爱猫咪and dogs", lang="zh")
    assert toks == ["我爱", "爱猫", "猫咪", "and", "dogs"]


def test_zh_stopword_bigram_filtered():
    toks = tokenize("这个的了东西", lang="zh")
    assert "的了" not in toks


def test_en_lowercase_and_porter_lite():
    toks = tokenize("Running dogs jumped quickly", lang="en")
    # "the"/"a" 等停用词会被滤掉;porter-lite 剥离 -ing/-ed/-ly
    assert "runn" in toks or "run" in toks
    assert "dog" in toks
    assert "jump" in toks
    assert "quick" in toks


def test_en_stopword_removed():
    toks = tokenize("the cat is on the mat", lang="en")
    assert "the" not in toks
    assert "is" not in toks
    assert "cat" in toks
    assert "mat" in toks


def test_ja_char_bigram():
    toks = tokenize("猫が好きです", lang="ja")
    assert all(len(t) <= 2 for t in toks)
    assert len(toks) > 0


def test_invalid_lang_falls_back_to_zh():
    a = tokenize("我爱猫咪", lang="fr")
    b = tokenize("我爱猫咪", lang="zh")
    assert a == b


def test_empty_text_returns_empty_list():
    assert tokenize("", lang="zh") == []
    assert tokenize("", lang="en") == []


def test_determinism_same_input_same_output():
    text = "今天天气不错,適合出去走走。"
    a = tokenize(text, lang="zh")
    b = tokenize(text, lang="zh")
    assert a == b


def test_golden_zh_mixed_punctuation():
    toks = tokenize("你好,世界!123abc", lang="zh")
    assert toks == ["你好", "世界", "123abc"]
