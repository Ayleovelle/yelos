"""opt-in 全链冒烟(律二):enabled=true + n-gram stub 权重 → 过渡路由 →

utter → 闸 → 文本;enabled=false → build 返回 None、零挂载。
"""

from __future__ import annotations

from yelos.distill import build_distill_provider
from yelos.distill.trainer import CharNgramTrainer, TrainConfig
from yelos.distill.corpus.assembler import CorpusPaths, assemble
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


def _fixed_deps():
    return {
        "p_lookup": lambda sid: 0.5,
        "epoch_lookup": lambda sid: 0,
        "lang_lookup": lambda sid: "zh",
        "corpus_reader": lambda sid, lang: (),
    }


def test_disabled_returns_none():
    provider = build_distill_provider(
        {"distill_enabled": False},
        gate=_real_gate(),
        clock=VirtualClock(0.0),
        **_fixed_deps(),
    )
    assert provider is None


def test_enabled_full_chain_smoke(tmp_path):
    """真实训练一个最小 n-gram 模型,走完整 available→utter_canonical 链路。"""
    # 语料要覆盖至少一个 8 核心场合的合法闭包成员,保证闸能放行至少一句。
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

    model_dir = tmp_path / "models" / "distill"
    CharNgramTrainer().train(corpus_path, model_dir, TrainConfig())

    provider = build_distill_provider(
        {
            "distill_enabled": True,
            "distill_model_dir": str(model_dir),
            "distill_tier": "ngram",
            "distill_k_candidates": 16,
        },
        gate=_real_gate(),
        clock=VirtualClock(0.0),
        **_fixed_deps(),
    )
    assert provider is not None
    assert provider.available("sid1", "zh") is True

    # 全闭包成员本身作为唯一训练语料,n-gram 贪心复现原句必在闭包内,
    # 保证至少一个候选过闸(否则本冒烟测试对随机语料太脆弱)。
    text = provider.utter_canonical(
        {"seed": ""},
        "sid1",
        "2026-07-11",
        "concern",
        p=0.5,
        epoch=0,
        lang="zh",
        context={"corpus": (seed_sentence,)},
    )
    assert isinstance(text, str) and text


def test_enabled_but_model_absent_is_clean_absence(tmp_path):
    provider = build_distill_provider(
        {"distill_enabled": True, "distill_model_dir": str(tmp_path / "nope")},
        gate=_real_gate(),
        clock=VirtualClock(0.0),
        **_fixed_deps(),
    )
    assert provider is not None
    assert provider.available("sid1", "zh") is False
