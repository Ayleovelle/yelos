"""在整个架构中的位置:档② 微型 RNN 训练器与推理后端(蓝图 §3.3)。

理论出身:循环神经序列模型(字符级 GRU 语言模型)。torch 依赖只进
extras ``[distill]``,核心零依赖公理由本文件顶部的守卫 import 与
``test_no_torch_in_core``(AST 扫描)联合锁死——除本文件与
``transformer_tiny.py`` 外,``src/yelos`` 任何地方不得 import torch。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .protocol import DistillExtrasMissing, TrainConfig, TrainReport

try:  # pragma: no cover - extras 存在与否由 CI 两个 job 分别覆盖
    import torch
    from torch import nn
except ImportError as _exc:  # pragma: no cover
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]
    _IMPORT_ERROR = _exc
else:
    _IMPORT_ERROR = None

_MODEL_FILENAME = "model.rnn.pt"
_META_FILENAME = "model.rnn.meta.json"


def _require_torch() -> None:
    if torch is None:  # pragma: no cover
        raise DistillExtrasMissing(
            "distill[rnn] 需要 torch;安装 extras: pip install 'yelos[distill]'"
        ) from _IMPORT_ERROR


def _build_vocab(corpus: tuple[str, ...]) -> tuple[str, ...]:
    chars = sorted({ch for text in corpus for ch in text} | {"^", "$"})
    return tuple(chars)


class _CharGRU(nn.Module if nn is not None else object):  # type: ignore[misc]
    def __init__(self, vocab_size: int, hidden: int = 64, embed: int = 32) -> None:
        super().__init__()
        self.embed = nn.Embedding(vocab_size, embed)
        self.gru = nn.GRU(embed, hidden, batch_first=True)
        self.head = nn.Linear(hidden, vocab_size)

    def forward(self, x, hidden=None):  # noqa: ANN001
        e = self.embed(x)
        out, hidden = self.gru(e, hidden)
        logits = self.head(out)
        return logits, hidden


class TinyRNNTrainer:
    tier = "rnn"

    def train(self, corpus: Path, out_dir: Path, cfg: TrainConfig) -> TrainReport:
        _require_torch()
        from ..corpus.assembler import load_corpus

        texts = load_corpus(corpus)
        if not texts:
            raise ValueError("空语料,TinyRNNTrainer 拒训")

        torch.manual_seed(cfg.seed)
        vocab = _build_vocab(texts)
        stoi = {ch: i for i, ch in enumerate(vocab)}
        hidden_size = int(cfg.tier_params.get("hidden", 64))
        epochs = int(cfg.tier_params.get("epochs", 3))

        model = _CharGRU(len(vocab), hidden=hidden_size)
        opt = torch.optim.Adam(model.parameters(), lr=1e-2)
        loss_fn = nn.CrossEntropyLoss()

        sequences = [f"^{t}$" for t in texts]
        final_loss = 0.0
        for _epoch in range(max(1, epochs)):
            epoch_loss = 0.0
            for seq in sequences:
                ids = torch.tensor([[stoi[c] for c in seq[:-1]]], dtype=torch.long)
                target = torch.tensor([[stoi[c] for c in seq[1:]]], dtype=torch.long)
                logits, _ = model(ids)
                loss = loss_fn(logits.view(-1, len(vocab)), target.view(-1))
                opt.zero_grad()
                loss.backward()
                opt.step()
                epoch_loss += float(loss.item())
            final_loss = epoch_loss / max(1, len(sequences))

        out_dir.mkdir(parents=True, exist_ok=True)
        torch.save(model.state_dict(), out_dir / _MODEL_FILENAME)

        corpus_hash = hashlib.sha256("\n".join(texts).encode("utf-8")).hexdigest()
        weights_bytes = (out_dir / _MODEL_FILENAME).read_bytes()
        model_hash = hashlib.sha256(weights_bytes).hexdigest()
        meta = {
            "tier": self.tier,
            "vocab": list(vocab),
            "hidden": hidden_size,
            "corpus_hash": corpus_hash,
            "model_hash": model_hash,
            "determinism_note": (
                "torch.manual_seed + 贪心解码;cudnn 非确定性算子未使用"
                "(CPU 训练/推理路径),尽力而为声明入模型卡"
            ),
        }
        (out_dir / _META_FILENAME).write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        return TrainReport(
            tier=self.tier,
            corpus_hash=corpus_hash,
            model_hash=model_hash,
            eval_pre={"final_loss": final_loss, "vocab_size": len(vocab)},
        )


class RNNBackend:
    def __init__(self, model, vocab: tuple[str, ...], model_hash: str) -> None:  # noqa: ANN001
        self._model = model
        self._vocab = vocab
        self._stoi = {ch: i for i, ch in enumerate(vocab)}
        self._itos = {i: ch for i, ch in enumerate(vocab)}
        self._model_hash = model_hash

    @property
    def model_hash(self) -> str:
        return self._model_hash

    def _generate_one(self, seed: str, variant: int, max_len: int) -> str:
        _require_torch()
        self._model.eval()
        ids = [self._stoi.get(c, self._stoi.get("^")) for c in f"^{seed}"]
        x = torch.tensor([ids], dtype=torch.long)
        hidden = None
        out: list[str] = []
        with torch.no_grad():
            for _ in range(max_len):
                logits, hidden = self._model(x, hidden)
                last = logits[0, -1]
                ranked = torch.argsort(last, descending=True).tolist()
                idx = ranked[variant % len(ranked)]
                ch = self._itos.get(idx, "$")
                if ch == "$":
                    break
                out.append(ch)
                x = torch.tensor([[idx]], dtype=torch.long)
        return "".join(out)

    def generate(self, seed: str, k: int, budget_ms: int) -> list[str]:  # noqa: ARG002
        seen: set[str] = set()
        results: list[str] = []
        for variant in range(max(1, k)):
            cand = self._generate_one(seed, variant, max_len=24)
            if cand and cand not in seen:
                seen.add(cand)
                results.append(cand)
        return results


def load(model_dir: Path) -> RNNBackend:
    _require_torch()
    meta = json.loads((model_dir / _META_FILENAME).read_text(encoding="utf-8"))
    vocab = tuple(meta["vocab"])
    model = _CharGRU(len(vocab), hidden=int(meta["hidden"]))
    state = torch.load(model_dir / _MODEL_FILENAME, map_location="cpu")
    model.load_state_dict(state)
    return RNNBackend(model, vocab, str(meta["model_hash"]))


def model_file_exists(model_dir: Path) -> bool:
    return (model_dir / _MODEL_FILENAME).is_file() and (
        model_dir / _META_FILENAME
    ).is_file()


MODEL_FILENAME = _MODEL_FILENAME

__all__ = [
    "TinyRNNTrainer",
    "RNNBackend",
    "load",
    "model_file_exists",
    "MODEL_FILENAME",
]
