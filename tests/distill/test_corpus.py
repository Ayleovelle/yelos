"""装配幂等(同输入同哈希)/ 空语料合法路径 / 来源计数 = 桑基输入(→DA4 前半)。

§3.7(X7):去重键 (text, occasion, day_key),同一句不双计。
"""

from __future__ import annotations

from yelos.distill.corpus.assembler import CorpusPaths, assemble, load_corpus


def test_assemble_idempotent_same_input_same_hash(tmp_path):
    corpus_view = [
        {
            "text": "你好呀。",
            "occasion": "contact_seek",
            "day_key": "2026-07-11",
            "affect": {},
        },
        {
            "text": "在的呢。",
            "occasion": "express_warm",
            "day_key": "2026-07-11",
            "affect": {},
        },
    ]
    m1 = assemble(
        CorpusPaths(corpus_view=corpus_view),
        tmp_path / "run1" / "corpus.jsonl",
        created_day="2026-07-11",
    )
    m2 = assemble(
        CorpusPaths(corpus_view=corpus_view),
        tmp_path / "run2" / "corpus.jsonl",
        created_day="2026-07-12",  # created_day 不入哈希
    )
    assert m1.corpus_hash == m2.corpus_hash
    assert m1.n_entries == m2.n_entries == 2


def test_assemble_empty_corpus_is_legal(tmp_path):
    manifest = assemble(
        CorpusPaths(), tmp_path / "corpus.jsonl", created_day="2026-07-11"
    )
    assert manifest.n_entries == 0
    assert manifest.sources == {}


def test_dedup_key_text_occasion_day_key_no_double_count(tmp_path):
    """§3.7:corpus_view 与 anthology 对同一句"她说过的话"的双源重叠,

    去重后只计一次;corpus_view 权威源优先落账(source 标签为 memory_l1)。
    """
    shared = {
        "text": "今天也想你呀。",
        "occasion": "express_warm",
        "day_key": "2026-07-11",
        "affect": {},
    }
    manifest = assemble(
        CorpusPaths(corpus_view=[shared], anthology_entries=[dict(shared)]),
        tmp_path / "corpus.jsonl",
        created_day="2026-07-11",
    )
    assert manifest.n_entries == 1
    assert manifest.sources == {"memory_l1": 1}


def test_source_counts_match_written_corpus(tmp_path):
    corpus_view = [
        {"text": "甲。", "occasion": "concern", "day_key": "2026-07-11", "affect": {}},
    ]
    anthology = [
        {
            "text": "乙(历史)。",
            "occasion": "recover",
            "day_key": "2026-01-01",
            "affect": {},
        },
    ]
    out = tmp_path / "corpus.jsonl"
    manifest = assemble(
        CorpusPaths(corpus_view=corpus_view, anthology_entries=anthology),
        out,
        created_day="2026-07-11",
    )
    assert manifest.sources == {"memory_l1": 1, "anthology": 1}
    texts = load_corpus(out)
    assert set(texts) == {"甲。", "乙(历史)。"}
