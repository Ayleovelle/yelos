"""在整个架构中的位置:档① 字符级 n-gram 训练器与推理后端(蓝图 §3.3)。

理论出身:计数平滑语言模型,Katz 风格回退(高阶上下文缺计数时退到低阶,
§9 自著实质"n-gram 训练器(全自写)")。纯 stdlib,零第三方依赖——依赖
公理②(核心/零依赖档)由 ``test_no_torch_in_core`` 锁死,本文件不 import
torch。

确定性(DA3):生成过程零真随机;同上下文的候选并列时按
``(-count, char)`` 排序取前 k,tie-break 完全由计数与字符码点决定。
"""

from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from .protocol import TrainConfig, TrainReport

_TERMINATORS = ("。", "!", "?", "…", "~")
_DEFAULT_ORDER = 3
_DEFAULT_MAX_LEN = 24
_MODEL_FILENAME = "model.ngram.json.gz"


def _build_counts(corpus: tuple[str, ...], order: int) -> dict[str, dict[str, int]]:
    """context(长度 <= order 的字符串)→ Counter(next_char)。"""
    counts: dict[str, Counter] = defaultdict(Counter)
    for text in corpus:
        padded = ("^" * order) + text + "$"
        for i in range(len(padded) - 1):
            for n in range(1, order + 1):
                start = i - n + 1
                if start < 0:
                    continue
                context = padded[start : i + 1]
                counts[context][padded[i + 1]] += 1
    return {ctx: dict(c) for ctx, c in counts.items()}


def _corpus_hash(corpus: tuple[str, ...]) -> str:
    joined = "\n".join(corpus)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


class CharNgramTrainer:
    tier = "ngram"

    def train(self, corpus: Path, out_dir: Path, cfg: TrainConfig) -> TrainReport:
        from ..corpus.assembler import load_corpus

        texts = load_corpus(corpus)
        if not texts:
            raise ValueError("空语料,CharNgramTrainer 拒训(§10 诚实自评)")

        order = int(cfg.tier_params.get("order", _DEFAULT_ORDER))
        counts = _build_counts(texts, order)
        corpus_hash = _corpus_hash(texts)

        out_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "tier": self.tier,
            "order": order,
            "corpus_hash": corpus_hash,
            "counts": counts,
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        model_hash = hashlib.sha256(raw).hexdigest()
        payload["model_hash"] = model_hash
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        (out_dir / _MODEL_FILENAME).write_bytes(gzip.compress(raw))

        n_states = len(counts)
        n_events = sum(sum(c.values()) for c in counts.values())
        return TrainReport(
            tier=self.tier,
            corpus_hash=corpus_hash,
            model_hash=model_hash,
            eval_pre={"n_states": n_states, "n_events": n_events, "order": order},
        )


class NgramBackend:
    """训练产物加载后的推理面(ModelBackend 协议)。"""

    def __init__(self, order: int, counts: dict[str, dict[str, int]], model_hash: str):
        self._order = order
        self._counts = counts
        self._model_hash = model_hash

    @property
    def model_hash(self) -> str:
        return self._model_hash

    @property
    def order(self) -> int:
        return self._order

    def _next_char_ranked(self, context: str) -> list[str]:
        """context 从长到短回退(Katz 风格),取有计数的最长上下文。"""
        for n in range(min(self._order, len(context)), 0, -1):
            ctx = context[-n:]
            table = self._counts.get(ctx)
            if table:
                return [
                    ch
                    for ch, _ in sorted(table.items(), key=lambda kv: (-kv[1], kv[0]))
                ]
        return []

    def _generate_one(self, seed: str, variant: int, max_len: int) -> str:
        context = ("^" * self._order) + seed
        out: list[str] = []
        for _ in range(max_len):
            ranked = self._next_char_ranked(context)
            if not ranked:
                break
            # 确定性变体:同一上下文按 variant 旋转候选序,产出候选间可
            # 观测差异,但仍是纯计数派生,零真随机(DA3)。
            idx = variant % len(ranked)
            ch = ranked[idx]
            if ch == "$":
                break
            out.append(ch)
            context = context + ch
            if ch in _TERMINATORS:
                break
        text = "".join(out)
        return text

    def generate(self, seed: str, k: int, budget_ms: int) -> list[str]:  # noqa: ARG002
        """budget_ms 不在此后验校验(推理是本地计数查表,天然远快于预算);

        超时判定由 ``runtime/budget.py`` 用调用方注入的时钟包裹本函数完成。
        """
        max_len = _DEFAULT_MAX_LEN
        seen: set[str] = set()
        out: list[str] = []
        for variant in range(max(1, k)):
            cand = self._generate_one(seed, variant, max_len)
            if cand and cand not in seen:
                seen.add(cand)
                out.append(cand)
        return out


def load(model_dir: Path) -> NgramBackend:
    path = model_dir / _MODEL_FILENAME
    raw = gzip.decompress(path.read_bytes())
    payload = json.loads(raw.decode("utf-8"))
    return NgramBackend(
        order=int(payload["order"]),
        counts=payload["counts"],
        model_hash=str(payload["model_hash"]),
    )


def model_file_exists(model_dir: Path) -> bool:
    return (model_dir / _MODEL_FILENAME).is_file()


MODEL_FILENAME = _MODEL_FILENAME

__all__ = [
    "CharNgramTrainer",
    "NgramBackend",
    "load",
    "model_file_exists",
    "MODEL_FILENAME",
]
