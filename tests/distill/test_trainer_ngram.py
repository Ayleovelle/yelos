"""零依赖档:训练往返(训→载→generate 非空)/ 拒训空语料 / TrainReport 哈希一致。"""

from __future__ import annotations

import pytest

from yelos.distill.corpus.assembler import CorpusPaths, assemble
from yelos.distill.trainer import CharNgramTrainer, TrainConfig, load_backend
from yelos.distill.trainer.ngram_char import load, model_file_exists


def _write_corpus(tmp_path):
    corpus_view = [
        {
            "text": "你好呀今天怎么样。",
            "occasion": "concern",
            "day_key": "2026-07-11",
            "affect": {},
        },
        {
            "text": "我在的别担心。",
            "occasion": "recover",
            "day_key": "2026-07-11",
            "affect": {},
        },
        {
            "text": "晚安,做个好梦。",
            "occasion": "contact_night",
            "day_key": "2026-07-11",
            "affect": {},
        },
    ]
    out = tmp_path / "corpus.jsonl"
    assemble(CorpusPaths(corpus_view=corpus_view), out, created_day="2026-07-11")
    return out


def test_train_load_generate_round_trip(tmp_path):
    corpus_path = _write_corpus(tmp_path)
    out_dir = tmp_path / "model"
    trainer = CharNgramTrainer()
    report = trainer.train(corpus_path, out_dir, TrainConfig())

    assert report.tier == "ngram"
    assert model_file_exists(out_dir)

    backend = load(out_dir)
    assert backend.model_hash == report.model_hash
    candidates = backend.generate("你好", k=3, budget_ms=50)
    assert candidates
    assert all(isinstance(c, str) and c for c in candidates)


def test_load_backend_dispatch_matches_direct_load(tmp_path):
    corpus_path = _write_corpus(tmp_path)
    out_dir = tmp_path / "model"
    CharNgramTrainer().train(corpus_path, out_dir, TrainConfig())
    backend = load_backend("ngram", out_dir)
    assert backend.generate("你", k=1, budget_ms=50)


def test_empty_corpus_rejected(tmp_path):
    out = tmp_path / "corpus.jsonl"
    assemble(CorpusPaths(), out, created_day="2026-07-11")
    trainer = CharNgramTrainer()
    with pytest.raises(ValueError):
        trainer.train(out, tmp_path / "model", TrainConfig())


def test_train_report_hash_consistent_across_runs(tmp_path):
    corpus_path = _write_corpus(tmp_path)
    r1 = CharNgramTrainer().train(corpus_path, tmp_path / "m1", TrainConfig())
    r2 = CharNgramTrainer().train(corpus_path, tmp_path / "m2", TrainConfig())
    assert r1.corpus_hash == r2.corpus_hash
    assert r1.model_hash == r2.model_hash
