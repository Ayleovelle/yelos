"""entries.py 在架构中的位置。

l2_semantic 对外的组装门面:关键词抽取 + SemanticEntry 组装 + L2/词向量
索引的磁盘持久化(原子写)。consolidation.jobs 在夜窗管线里调用本文件的
函数产出/落盘 SemanticEntry,不直接摸 tokenizer/ppmi/linalg_lite。
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Iterable

from ..contracts import EpisodeEvent, SemanticEntry
from .emotion import aggregate_emotion
from .summarize import Summarizer
from .vocab import Vocab

_MAX_KEYWORD_CHARS = 6


def extract_keywords(
    tokens: Iterable[str], top_n: int = 6, *, max_chars: int = _MAX_KEYWORD_CHARS
) -> list[str]:
    """按窗口内 token 频次抽取代表关键词:降序,并列按字典序破(确定性)。"""
    counts: dict[str, int] = {}
    for t in tokens:
        if not t or len(t) > max_chars:
            continue
        counts[t] = counts.get(t, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [tok for tok, _c in ranked[:top_n]]


def entry_id(sid_hash: str, gen: int, span: tuple[int, int]) -> str:
    raw = f"{sid_hash}|{gen}|{span[0]}|{span[1]}"
    return hashlib.blake2b(raw.encode("utf-8"), digest_size=8).hexdigest()[:16]


def build_semantic_entry(
    sid_hash: str,
    gen: int,
    span: tuple[int, int],
    events: list[EpisodeEvent],
    *,
    summarizer: Summarizer,
    now_ts: float,
    vec: list[float] | None = None,
    keyword_top_n: int = 6,
) -> SemanticEntry | None:
    """把一个 L1 事件窗口压成一条 SemanticEntry;空窗口返回 None。"""
    if not events:
        return None
    from .tokenizer import tokenize  # 延迟导入,避免模块级循环耦合面扩大

    all_tokens: list[str] = []
    for ev in events:
        text = ev.text or ev.occasion
        if text:
            all_tokens.extend(tokenize(text, lang="zh"))
    keywords = extract_keywords(all_tokens, top_n=keyword_top_n)
    summary = summarizer.summarize(events, keywords)
    stamps = [e.affect for e in events if e.affect is not None]
    day_keys = [e.day_key for e in events if e.affect is not None]
    emotion = aggregate_emotion(stamps, day_keys)
    day_key = events[0].day_key
    return SemanticEntry(
        id=entry_id(sid_hash, gen, span),
        span=span,
        day_key=day_key,
        keywords=keywords,
        summary=summary,
        vec=list(vec) if vec else [],
        emotion=emotion,
        S=1.0,
        created_ts=now_ts,
        last_access_ts=now_ts,
        access_count=0,
        topic_id="",
        source_kinds=sorted({e.kind for e in events}),
    )


# --- L2Store:SemanticEntry 全量持久化(原子写)----------------------------


class L2Store:
    def __init__(self, root: Path, sid_hash: str, gen: int) -> None:
        self._path = Path(root) / "memory" / "l2" / f"{sid_hash}.g{gen}.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, SemanticEntry] = {}
        self._order: list[str] = []
        self.load()

    def load(self) -> None:
        if not self._path.is_file():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        self._entries = {}
        self._order = []
        for raw in data.get("entries", []):
            e = SemanticEntry.from_dict(raw)
            self._entries[e.id] = e
            self._order.append(e.id)

    def save(self) -> None:
        tmp = self._path.with_name(self._path.name + ".tmp")
        payload = {"entries": [self._entries[i].to_dict() for i in self._order]}
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(tmp, self._path)

    def add(self, entry: SemanticEntry) -> None:
        if entry.id not in self._entries:
            self._order.append(entry.id)
        self._entries[entry.id] = entry

    def get(self, entry_id_: str) -> SemanticEntry | None:
        return self._entries.get(entry_id_)

    def all(self) -> list[SemanticEntry]:
        return [self._entries[i] for i in self._order]

    def remove(self, entry_id_: str) -> None:
        if entry_id_ in self._entries:
            del self._entries[entry_id_]
            self._order.remove(entry_id_)

    def count(self) -> int:
        return len(self._order)


# --- VocabIndexStore:词表 + 语义向量基持久化(原子写)---------------------


class VocabIndexStore:
    def __init__(self, root: Path, sid_hash: str, gen: int) -> None:
        self._path = Path(root) / "memory" / "index" / f"{sid_hash}.g{gen}.vocab.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self.vocab = Vocab()
        self.word_vecs: dict[str, list[float]] = {}
        self.idf: dict[str, float] = {}
        self.last_refit_night: str = ""
        self.refit_count: int = 0
        self.load()

    def load(self) -> None:
        if not self._path.is_file():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        self.vocab = Vocab.from_dict(data.get("vocab"))
        self.word_vecs = {
            k: [float(x) for x in v] for k, v in (data.get("word_vecs") or {}).items()
        }
        self.idf = {k: float(v) for k, v in (data.get("idf") or {}).items()}
        self.last_refit_night = str(data.get("last_refit_night", ""))
        self.refit_count = int(data.get("refit_count", 0))

    def save(self) -> None:
        tmp = self._path.with_name(self._path.name + ".tmp")
        payload = {
            "vocab": self.vocab.to_dict(),
            "word_vecs": self.word_vecs,
            "idf": self.idf,
            "last_refit_night": self.last_refit_night,
            "refit_count": self.refit_count,
        }
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(tmp, self._path)

    def has_basis(self) -> bool:
        return bool(self.word_vecs)
