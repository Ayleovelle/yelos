"""(extras job)RNN/transformer 档同上 + DistillExtrasMissing 路径。

标 ``@pytest.mark.distill_extras``:核心 job 不跑 torch,extras job 单独
跑本文件;若当前环境未装 torch,自动 skip(不是失败——两个 CI job 分离
覆盖,本地无 torch 时不应红)。
"""

from __future__ import annotations

import importlib.util

import pytest

pytestmark = pytest.mark.distill_extras

_HAS_TORCH = importlib.util.find_spec("torch") is not None


def _write_corpus(tmp_path):
    from yelos.distill.corpus.assembler import CorpusPaths, assemble

    corpus_view = [
        {
            "text": "你好呀。",
            "occasion": "concern",
            "day_key": "2026-07-11",
            "affect": {},
        },
        {
            "text": "我在的。",
            "occasion": "recover",
            "day_key": "2026-07-11",
            "affect": {},
        },
        {
            "text": "晚安啦。",
            "occasion": "contact_night",
            "day_key": "2026-07-11",
            "affect": {},
        },
    ]
    out = tmp_path / "corpus.jsonl"
    assemble(CorpusPaths(corpus_view=corpus_view), out, created_day="2026-07-11")
    return out


@pytest.mark.skipif(not _HAS_TORCH, reason="torch extras 未安装")
def test_rnn_train_load_generate_round_trip(tmp_path):
    from yelos.distill.trainer import TrainConfig
    from yelos.distill.trainer.rnn_tiny import TinyRNNTrainer, load

    corpus_path = _write_corpus(tmp_path)
    out_dir = tmp_path / "model_rnn"
    report = TinyRNNTrainer().train(
        corpus_path, out_dir, TrainConfig(tier_params={"hidden": 8, "epochs": 1})
    )
    assert report.tier == "rnn"

    backend = load(out_dir)
    assert backend.model_hash == report.model_hash
    candidates = backend.generate("你", k=2, budget_ms=200)
    assert isinstance(candidates, list)


@pytest.mark.skipif(not _HAS_TORCH, reason="torch extras 未安装")
def test_transformer_train_load_generate_round_trip(tmp_path):
    from yelos.distill.trainer import TrainConfig
    from yelos.distill.trainer.transformer_tiny import TinyTransformerTrainer, load

    corpus_path = _write_corpus(tmp_path)
    out_dir = tmp_path / "model_tfm"
    report = TinyTransformerTrainer().train(
        corpus_path, out_dir, TrainConfig(tier_params={"epochs": 1})
    )
    assert report.tier == "transformer"

    backend = load(out_dir)
    assert backend.model_hash == report.model_hash
    candidates = backend.generate("你", k=2, budget_ms=200)
    assert isinstance(candidates, list)


@pytest.mark.skipif(
    _HAS_TORCH, reason="仅在无 torch 环境验证 DistillExtrasMissing 路径"
)
def test_deps_missing_path_without_torch(tmp_path):
    from yelos.distill.trainer.protocol import DistillExtrasMissing
    from yelos.distill.trainer.rnn_tiny import TinyRNNTrainer

    corpus_path = _write_corpus(tmp_path)
    with pytest.raises(DistillExtrasMissing):
        TinyRNNTrainer().train(corpus_path, tmp_path / "model", object())
