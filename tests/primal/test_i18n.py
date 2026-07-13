"""lang 不可变(重 bind 异语拒);未审语言拒载回落 zh;覆盖矩阵

(occasion × REVIEWED_LANGS 非空 + essence 在)。锁 A7/RE8。
"""

from __future__ import annotations

from yelos.core.primal import LEXICON
from yelos.primal.i18n import REVIEWED_LANGS, bind_lang_decision, resolve_lang
from yelos.primal.lexicon import LexiconLoadError, load_lexicon


def test_resolve_lang_unreviewed_falls_back_to_zh():
    assert resolve_lang("en") == "zh"
    assert resolve_lang("ja") == "zh"
    assert resolve_lang(None) == "zh"
    assert resolve_lang("zh") == "zh"


def test_bind_lang_first_bind_reviewed_lang_ok():
    effective, rejected, warn = bind_lang_decision(None, "zh")
    assert effective == "zh"
    assert not rejected
    assert warn == ""


def test_bind_lang_first_bind_unreviewed_falls_back_with_warning():
    effective, rejected, warn = bind_lang_decision(None, "en")
    assert effective == "zh"
    assert not rejected
    assert warn  # 有告警文本


def test_bind_lang_immutable_rejects_change():
    effective, rejected, warn = bind_lang_decision("zh", "en")
    assert effective == "zh"
    assert rejected
    assert "新生" in warn


def test_bind_lang_same_lang_reaffirm_ok():
    effective, rejected, warn = bind_lang_decision("zh", "zh")
    assert effective == "zh"
    assert not rejected


def test_unreviewed_lexicon_load_rejected():
    try:
        load_lexicon("en")
        raised = False
    except LexiconLoadError:
        raised = True
    assert raised


def test_coverage_matrix_all_occasions_all_reviewed_langs_nonempty_and_essence_present():
    for lang in REVIEWED_LANGS:
        entries_by_occ = load_lexicon(lang)
        for occasion in LEXICON:
            entries = entries_by_occ.get(occasion, ())
            assert entries, f"{lang}/{occasion} 无词条"
            assert any(e.register == "essence" for e in entries), (
                f"{lang}/{occasion} 无 essence 句"
            )
