"""DA4:注入已知用户原文到上游账面 → 装配产物运行时扫描零出现;

``CorpusEntry.features`` 无自由文本字段(schema 断言)。
"""

from __future__ import annotations

from yelos.distill.corpus.assembler import CorpusPaths, assemble
from yelos.distill.corpus.manifest import CorpusEntry
from yelos.distill.corpus.sanitizer import RejectedEntry, sanitize

_KNOWN_USER_TEXT = "我今天在公司被老板骂了心情很差用户绝密原文标记XJ9K"


def test_corpus_no_user_text_after_assembly(tmp_path):
    corpus_view = [
        {
            "text": "她说的话。",
            "occasion": "concern",
            "day_key": "2026-07-11",
            "affect": {},
        },
        # 上游误传:混入疑似用户侧标记字段(纵深防御目标)。
        {
            "text": _KNOWN_USER_TEXT,
            "occasion": "concern",
            "day_key": "2026-07-11",
            "affect": {},
            "user_text": _KNOWN_USER_TEXT,
        },
    ]
    out = tmp_path / "corpus.jsonl"
    manifest = assemble(
        CorpusPaths(corpus_view=corpus_view), out, created_day="2026-07-11"
    )
    written = out.read_text(encoding="utf-8")
    assert _KNOWN_USER_TEXT not in written
    assert manifest.n_entries == 1  # 疑似用户侧条目被拒收,不计入


def test_sanitize_rejects_user_side_markers():
    raw = {"text": "任意文本", "occasion": "concern", "day_key": "d", "raw_user": "x"}
    try:
        sanitize(raw)
        assert False, "应抛 RejectedEntry"
    except RejectedEntry:
        pass


def test_sanitize_rejects_empty_text():
    raw = {"text": "", "occasion": "concern", "day_key": "d"}
    try:
        sanitize(raw)
        assert False, "应抛 RejectedEntry"
    except RejectedEntry:
        pass


def test_features_schema_no_free_text_field():
    raw = {
        "text": "她说的话。",
        "occasion": "concern",
        "day_key": "2026-07-11",
        "affect": {
            "p_band": "B2",
            "verdict": "warm",
            "free_text_leak": "这不该出现",  # 不在白名单键内
        },
    }
    entry = sanitize(raw)
    assert isinstance(entry, CorpusEntry)
    assert "free_text_leak" not in entry.features
    assert set(entry.features.keys()) <= {
        "p_band",
        "verdict",
        "armed",
        "intensity",
        "valence",
        "arousal",
        "kind",
    }
    for value in entry.features.values():
        assert isinstance(value, (str, int, float, bool))
