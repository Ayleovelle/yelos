"""T4(新引擎侧):phrasebook 是封闭集;get_phrase 只能返回登记在 HintKey 里的
文本;en/ja 未解锁时恒回落 zh;三语句库没有第二人称诊断句式/占位符。"""

from __future__ import annotations

from yelos.guidance.phrasebook import HintKey, get_phrase
from yelos.guidance.phrasebook.en import PHRASES_EN, UNLOCKED as EN_UNLOCKED
from yelos.guidance.phrasebook.ja import PHRASES_JA, UNLOCKED as JA_UNLOCKED
from yelos.guidance.phrasebook.zh import PHRASES_ZH


def test_all_hint_keys_have_zh_phrase() -> None:
    for key in HintKey:
        assert key.value in PHRASES_ZH, f"{key} 缺 zh 句面"


def test_en_ja_locked_by_default() -> None:
    assert EN_UNLOCKED is False
    assert JA_UNLOCKED is False


def test_get_phrase_falls_back_to_zh_when_locked() -> None:
    for key in HintKey:
        assert get_phrase(key.value, "en") == PHRASES_ZH[key.value]
        assert get_phrase(key.value, "ja") == PHRASES_ZH[key.value]


def test_get_phrase_unknown_lang_falls_back_to_zh() -> None:
    for key in HintKey:
        assert get_phrase(key.value, "fr") == PHRASES_ZH[key.value]


def test_get_phrase_unknown_key_raises() -> None:
    import pytest

    with pytest.raises(KeyError):
        get_phrase("NOT_A_REAL_KEY", "zh")


def test_no_second_person_diagnosis_except_registered_concern_exception() -> None:
    for key, text in PHRASES_ZH.items():
        if key == "CONCERN":
            continue
        assert "你" not in text, f"zh 句 {text!r} 含第二人称诊断口吻"
    assert PHRASES_ZH["CONCERN"] == "她像是有点担心你，可以关心一句。"


def test_phrasebook_has_no_placeholders_or_interpolation() -> None:
    for table in (PHRASES_ZH, PHRASES_EN, PHRASES_JA):
        for text in table.values():
            assert "{" not in text and "}" not in text
            assert "%" not in text
