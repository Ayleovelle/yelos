"""在整个架构中的位置:三档训练器的公共协议(蓝图 §3.3)。

三档(``ngram_char``/``rnn_tiny``/``transformer_tiny``)各自独立理论出身,
共用本文件的 ``TrainerBackend`` 协议、``TrainConfig``/``TrainReport`` 数据
结构,使 CLI(``trainer/cli.py``)与 ``packaging`` 不必按档分叉签名。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Protocol


class DistillExtrasMissing(RuntimeError):
    """torch 档缺 extras 依赖时的显式信号(依赖公理②的运行期证据)。"""


@dataclass(frozen=True)
class TrainConfig:
    seed: int = 0  # 训练确定性(torch 档 set_seed + deterministic algos,尽力而为)
    max_minutes: int = 30
    tier_params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class TrainReport:
    tier: str
    corpus_hash: str
    model_hash: str
    eval_pre: dict = field(default_factory=dict)  # 训练侧自评,不与 eval/ 混分

    def to_dict(self) -> dict:
        return {
            "tier": self.tier,
            "corpus_hash": self.corpus_hash,
            "model_hash": self.model_hash,
            "eval_pre": dict(self.eval_pre),
        }


class TrainerBackend(Protocol):
    tier: ClassVar[str]

    def train(self, corpus: Path, out_dir: Path, cfg: TrainConfig) -> TrainReport: ...


class ModelBackend(Protocol):
    """三档模型加载后的公共推理面(runtime/loader.py 消费)。"""

    def generate(self, seed: str, k: int, budget_ms: int) -> list[str]: ...

    @property
    def model_hash(self) -> str: ...


__all__ = [
    "DistillExtrasMissing",
    "TrainConfig",
    "TrainReport",
    "TrainerBackend",
    "ModelBackend",
]
