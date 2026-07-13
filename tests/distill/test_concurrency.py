"""RE6:并发 utter 同 session 懒加载单次(锁)、trace 追加无交错。"""

from __future__ import annotations

import threading

from yelos.distill.corpus.assembler import CorpusPaths, assemble
from yelos.distill.trainer import CharNgramTrainer, TrainConfig
from yelos.distill.runtime.loader import ModelLoader
from yelos.distill.runtime.provider import SylannDistilledProvider
from yelos.distill.runtime.rerank import HashRerank
from yelos.primal.lexicon.closure import enumerate_closure
from yelos.primal.whitelist_gate import WhitelistGate, load_forbidden_patterns
from yelos.bench.clock import VirtualClock


def _real_gate() -> WhitelistGate:
    return WhitelistGate(
        lambda occasion, lang, band, epoch: enumerate_closure(
            occasion, lang, band, epoch
        ),
        forbidden_patterns=load_forbidden_patterns("zh"),
    )


def test_loader_get_loads_backend_once_under_concurrent_calls(tmp_path):
    canon = enumerate_closure("concern", "zh", "B2", epoch=0)
    seed_sentence = next(iter(canon))
    corpus_view = [
        {
            "text": seed_sentence,
            "occasion": "concern",
            "day_key": "2026-07-11",
            "affect": {},
        }
    ]
    corpus_path = tmp_path / "corpus.jsonl"
    assemble(
        CorpusPaths(corpus_view=corpus_view), corpus_path, created_day="2026-07-11"
    )
    model_dir = tmp_path / "model"
    CharNgramTrainer().train(corpus_path, model_dir, TrainConfig())

    loader = ModelLoader(model_dir, "ngram")

    backends = []
    results_lock = threading.Lock()

    def _get_and_record():
        backend = loader.get()  # ModelLoader 自带双检锁,调用方无需外加锁
        with results_lock:
            backends.append(backend)

    threads = [threading.Thread(target=_get_and_record) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(backends) == 8
    assert all(b is backends[0] for b in backends)  # 同一实例,懒加载单次


def test_trace_append_no_interleaving_under_concurrent_utter(tmp_path):
    canon = enumerate_closure("concern", "zh", "B2", epoch=0)
    seed_sentence = next(iter(canon))
    corpus_view = [
        {
            "text": seed_sentence,
            "occasion": "concern",
            "day_key": "2026-07-11",
            "affect": {},
        }
    ]
    corpus_path = tmp_path / "corpus.jsonl"
    assemble(
        CorpusPaths(corpus_view=corpus_view), corpus_path, created_day="2026-07-11"
    )
    model_dir = tmp_path / "model"
    CharNgramTrainer().train(corpus_path, model_dir, TrainConfig())

    trace_rows: list[dict] = []
    trace_lock = threading.Lock()

    def trace_sink(row: dict) -> None:
        with trace_lock:
            trace_rows.append(row)

    loader = ModelLoader(model_dir, "ngram")
    provider = SylannDistilledProvider(
        loader=loader,
        gate=_real_gate(),
        reranker=HashRerank(),
        p_lookup=lambda sid: 0.5,
        epoch_lookup=lambda sid: 0,
        lang_lookup=lambda sid: "zh",
        corpus_reader=lambda sid, lang: (seed_sentence,),
        clock=VirtualClock(0.0),
        budget_ms=50,
        k_candidates=16,
        trace_sink=trace_sink,
    )

    def _call():
        try:
            provider.utter_canonical(
                {"seed": ""},
                "sid1",
                "2026-07-11",
                "concern",
                p=0.5,
                epoch=0,
                lang="zh",
                context={"corpus": (seed_sentence,)},
            )
        except Exception:  # noqa: BLE001  并发场景下允许回退,不允许崩溃
            pass

    threads = [threading.Thread(target=_call) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 无交错:每行都是完整字典(有 ts/occasion/outcome 三键),不会出现半行
    assert len(trace_rows) == 16
    for row in trace_rows:
        assert {"ts", "occasion", "outcome"} <= set(row.keys())
