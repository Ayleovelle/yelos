"""trainer/ 在整个架构中的位置:三档训练器组合根(蓝图 §3.3)。

只 re-export 协议与零依赖档(``ngram_char``);torch 两档(``rnn_tiny``/
``transformer_tiny``)**不在此 re-export**——核心零依赖公理由
``test_no_torch_in_core``(AST 扫描 src/yelos)锁死,本文件是那条锁的
"不作弊"保证:即便调用方 `from yelos.distill.trainer import *`,也拿不到
任何 torch 符号,必须显式 `from yelos.distill.trainer import rnn_tiny`
才会触发 torch import(与守卫异常路径一致)。
"""

from __future__ import annotations

from pathlib import Path

from .ngram_char import CharNgramTrainer
from .protocol import (
    DistillExtrasMissing,
    ModelBackend,
    TrainConfig,
    TrainerBackend,
    TrainReport,
)

TIER_TRAINERS: dict[str, str] = {
    "ngram": "yelos.distill.trainer.ngram_char",
    "rnn": "yelos.distill.trainer.rnn_tiny",
    "transformer": "yelos.distill.trainer.transformer_tiny",
}


def get_trainer(tier: str) -> TrainerBackend:
    """按档懒加载训练器;torch 档到此才真正 import torch(依赖公理②)。"""
    if tier == "ngram":
        return CharNgramTrainer()
    if tier == "rnn":
        from .rnn_tiny import TinyRNNTrainer

        return TinyRNNTrainer()
    if tier == "transformer":
        from .transformer_tiny import TinyTransformerTrainer

        return TinyTransformerTrainer()
    raise ValueError(f"未知档:{tier!r}(合法值:{tuple(TIER_TRAINERS)})")


def load_backend(tier: str, model_dir: Path) -> ModelBackend:
    """按档懒加载推理后端(runtime/loader.py 消费,同款懒加载纪律)。"""
    if tier == "ngram":
        from . import ngram_char

        return ngram_char.load(model_dir)
    if tier == "rnn":
        from . import rnn_tiny

        return rnn_tiny.load(model_dir)
    if tier == "transformer":
        from . import transformer_tiny

        return transformer_tiny.load(model_dir)
    raise ValueError(f"未知档:{tier!r}(合法值:{tuple(TIER_TRAINERS)})")


_MODEL_FILENAMES: dict[str, tuple[str, ...]] = {
    "ngram": ("model.ngram.json.gz",),
    "rnn": ("model.rnn.pt", "model.rnn.meta.json"),
    "transformer": ("model.tfm.pt", "model.tfm.meta.json"),
}


def model_file_exists(tier: str, model_dir: Path) -> bool:
    """纯文件系统检查,刻意不 import 对应 tier 模块——DEPS_MISSING 探测

    (torch 未装)必须能在不触发 torch import 的前提下先判断"文件在不在",
    否则 R3(DEPS_MISSING)与"文件缺失"两种状态会被 import 副作用混淆。
    """
    names = _MODEL_FILENAMES.get(tier)
    if not names:
        return False
    return all((model_dir / name).is_file() for name in names)


__all__ = [
    "TIER_TRAINERS",
    "get_trainer",
    "load_backend",
    "model_file_exists",
    "CharNgramTrainer",
    "DistillExtrasMissing",
    "ModelBackend",
    "TrainConfig",
    "TrainerBackend",
    "TrainReport",
]
