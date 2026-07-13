"""vocab.py 在架构中的位置。

token→id 映射 + 计数统计 + 低频截断(§2.3 护栏)。确定性排序:计数降序,
并列按 token 字典序破(与全模块 tie-break 纪律 MEM-A4 同精神)。持久化用
counts 快照(id 派生是计数的纯函数,不需要单独持久化 id 顺序)。
"""

from __future__ import annotations

from typing import Iterable


class Vocab:
    def __init__(self, cap: int = 30000, min_count: int = 2) -> None:
        self._cap = max(1, cap)
        self._min_count = max(1, min_count)
        self._counts: dict[str, int] = {}
        self._token_to_id: dict[str, int] = {}
        self._id_to_token: list[str] = []
        self._rebuild_ids()

    # -- 更新 --------------------------------------------------------------

    def fit_update(self, docs: Iterable[list[str]]) -> None:
        for doc in docs:
            for tok in doc:
                self._counts[tok] = self._counts.get(tok, 0) + 1
        self._rebuild_ids()

    def _rebuild_ids(self) -> None:
        items = [(tok, c) for tok, c in self._counts.items() if c >= self._min_count]
        items.sort(key=lambda t: (-t[1], t[0]))
        items = items[: self._cap]
        self._id_to_token = [tok for tok, _ in items]
        self._token_to_id = {tok: i for i, tok in enumerate(self._id_to_token)}

    # -- 读 ------------------------------------------------------------------

    def encode(self, tokens: list[str]) -> list[int]:
        out = []
        for t in tokens:
            idx = self._token_to_id.get(t)
            if idx is not None:
                out.append(idx)
        return out

    def token(self, idx: int) -> str:
        return self._id_to_token[idx]

    def contains(self, token: str) -> bool:
        return token in self._token_to_id

    def size(self) -> int:
        return len(self._id_to_token)

    def token_count(self, token: str) -> int:
        return self._counts.get(token, 0)

    def total_distinct_seen(self) -> int:
        """截断前观测到的全部去重 token 数(refit 决策表的新 token 占比分母用)。"""
        return len(self._counts)

    def new_token_ratio(self, prev_tokens: frozenset[str]) -> float:
        """相对上次 refit 时的词表,新 id 词占当前词表比例(§3.2.3 决策表)。"""
        if not self._id_to_token:
            return 0.0
        new_count = sum(1 for t in self._id_to_token if t not in prev_tokens)
        return new_count / len(self._id_to_token)

    def current_tokens(self) -> frozenset[str]:
        return frozenset(self._id_to_token)

    # -- 持久化 --------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "cap": self._cap,
            "min_count": self._min_count,
            "counts": self._counts,
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "Vocab":
        if not d:
            return cls()
        v = cls(cap=int(d.get("cap", 30000)), min_count=int(d.get("min_count", 2)))
        v._counts = {str(k): int(c) for k, c in (d.get("counts") or {}).items()}
        v._rebuild_ids()
        return v
