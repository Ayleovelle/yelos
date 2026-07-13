"""在整个架构中的位置:档③ 微型 transformer 训练器与推理后端(蓝图 §3.3)。

理论出身:自注意力序列模型(字符级、单层、因果掩码)。torch 依赖只进
extras ``[distill]``——顶部守卫 import,与 ``rnn_tiny.py`` 同款纪律。
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from .protocol import DistillExtrasMissing, TrainConfig, TrainReport

try:  # pragma: no cover
    import torch
    from torch import nn
except ImportError as _exc:  # pragma: no cover
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]
    _IMPORT_ERROR = _exc
else:
    _IMPORT_ERROR = None

_MODEL_FILENAME = "model.tfm.pt"
_META_FILENAME = "model.tfm.meta.json"
_MAX_POS = 64


def _require_torch() -> None:
    if torch is None:  # pragma: no cover
        raise DistillExtrasMissing(
            "distill[transformer] 需要 torch;安装 extras: pip install 'yelos[distill]'"
        ) from _IMPORT_ERROR


def _build_vocab(corpus: tuple[str, ...]) -> tuple[str, ...]:
    chars = sorted({ch for text in corpus for ch in text} | {"^", "$"})
    return tuple(chars)


class _TinyTransformer(nn.Module if nn is not None else object):  # type: ignore[misc]
    def __init__(self, vocab_size: int, d_model: int = 32, n_head: int = 2) -> None:
        super().__init__()
        self.embed = nn.Embedding(vocab_size, d_model)
        self.pos = nn.Embedding(_MAX_POS, d_model)
        layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=n_head, dim_feedforward=64, batch_first=True
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=1)
        self.head = nn.Linear(d_model, vocab_size)

    def forward(self, x):  # noqa: ANN001
        seq_len = x.shape[1]
        pos_ids = torch.arange(seq_len, device=x.device).unsqueeze(0)
        h = self.embed(x) + self.pos(pos_ids)
        mask = torch.triu(torch.full((seq_len, seq_len), float("-inf")), diagonal=1)
        h = self.encoder(h, mask=mask)
        return self.head(h)


class TinyTransformerTrainer:
    tier = "transformer"

    def train(self, corpus: Path, out_dir: Path, cfg: TrainConfig) -> TrainReport:
        _require_torch()
        from ..corpus.assembler import load_corpus

        texts = load_corpus(corpus)
        if not texts:
            raise ValueError("空语料,TinyTransformerTrainer 拒训")
        texts = tuple(t[: _MAX_POS - 2] for t in texts)  # 位置编码上限内截断

        torch.manual_seed(cfg.seed)
        vocab = _build_vocab(texts)
        stoi = {ch: i for i, ch in enumerate(vocab)}
        epochs = int(cfg.tier_params.get("epochs", 3))

        model = _TinyTransformer(len(vocab))
        opt = torch.optim.Adam(model.parameters(), lr=1e-2)
        loss_fn = nn.CrossEntropyLoss()

        sequences = [f"^{t}$" for t in texts]
        final_loss = 0.0
        for _epoch in range(max(1, epochs)):
            epoch_loss = 0.0
            for seq in sequences:
                ids = torch.tensor([[stoi[c] for c in seq[:-1]]], dtype=torch.long)
                target = torch.tensor([[stoi[c] for c in seq[1:]]], dtype=torch.long)
                logits = model(ids)
                loss = loss_fn(logits.view(-1, len(vocab)), target.view(-1))
                opt.zero_grad()
                loss.backward()
                opt.step()
                epoch_loss += float(loss.item())
            final_loss = epoch_loss / max(1, len(sequences))

        out_dir.mkdir(parents=True, exist_ok=True)
        torch.save(model.state_dict(), out_dir / _MODEL_FILENAME)

        corpus_hash = hashlib.sha256("\n".join(texts).encode("utf-8")).hexdigest()
        model_hash = hashlib.sha256(
            (out_dir / _MODEL_FILENAME).read_bytes()
        ).hexdigest()
        meta = {
            "tier": self.tier,
            "vocab": list(vocab),
            "corpus_hash": corpus_hash,
            "model_hash": model_hash,
            "determinism_note": (
                "torch.manual_seed + 贪心解码 + 因果掩码;"
                "attention 数值路径非 bit-精确跨硬件确定,尽力而为声明"
            ),
        }
        (out_dir / _META_FILENAME).write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return TrainReport(
            tier=self.tier,
            corpus_hash=corpus_hash,
            model_hash=model_hash,
            eval_pre={
                "final_loss": final_loss,
                "vocab_size": len(vocab),
                "perplexity": math.exp(min(final_loss, 20.0)),
            },
        )


class TransformerBackend:
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
        out: list[str] = []
        with torch.no_grad():
            for _ in range(max_len):
                if len(ids) >= _MAX_POS:
                    break
                x = torch.tensor([ids], dtype=torch.long)
                logits = self._model(x)
                last = logits[0, -1]
                ranked = torch.argsort(last, descending=True).tolist()
                idx = ranked[variant % len(ranked)]
                ch = self._itos.get(idx, "$")
                if ch == "$":
                    break
                out.append(ch)
                ids.append(idx)
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


def load(model_dir: Path) -> TransformerBackend:
    _require_torch()
    meta = json.loads((model_dir / _META_FILENAME).read_text(encoding="utf-8"))
    vocab = tuple(meta["vocab"])
    model = _TinyTransformer(len(vocab))
    state = torch.load(model_dir / _MODEL_FILENAME, map_location="cpu")
    model.load_state_dict(state)
    return TransformerBackend(model, vocab, str(meta["model_hash"]))


def model_file_exists(model_dir: Path) -> bool:
    return (model_dir / _MODEL_FILENAME).is_file() and (
        model_dir / _META_FILENAME
    ).is_file()


MODEL_FILENAME = _MODEL_FILENAME

__all__ = [
    "TinyTransformerTrainer",
    "TransformerBackend",
    "load",
    "model_file_exists",
    "MODEL_FILENAME",
]
