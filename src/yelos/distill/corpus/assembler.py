"""在整个架构中的位置:蒸馏语料装配(蓝图 §3.2 / INTEGRATION_SPEC §3.7 X7)。

只读消费上游账面工件,全本地,零网络:

- ``memory.facade.corpus_view(sid, gen)`` —— 她的话的**唯一权威源**
  (INTEGRATION_SPEC C4/§3.7 裁定),已含 provider 谱系与 affect 特征。
- anthology 说话史(M5,W3 并行在建)—— 只补 corpus_view 覆盖不到的
  **历史归档段**;本模块不 import finitude 代码,调用方按 INTEGRATION_SPEC
  契约把 anthology 记录整理成同形 dict 传入(接缝方向:distill 不侵入
  finitude)。

去重键 = ``(text, occasion, day_key)``(§3.7 裁定原文),防"她的定稿言语
入 L1"与"anthology utterances 记账"同源双计。moments(M3)与 duel 样本
(M2)是不同语料,不在本函数消费范围,不涉本去重逻辑。
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from .manifest import CorpusEntry, CorpusManifest
from .sanitizer import RejectedEntry, sanitize


@dataclass(frozen=True)
class CorpusPaths:
    """装配输入的两条只读通道;皆可省略(空语料合法,§3.2)。"""

    corpus_view: Iterable[dict] | None = None  # memory.facade.corpus_view(...) 的产出
    anthology_entries: Iterable[dict] | None = None  # 历史归档段,同形 dict


def _dedup_key(entry: CorpusEntry) -> tuple:
    return (entry.text, entry.occasion, entry.day_key)


def _iter_entries(paths: CorpusPaths) -> Iterator[tuple[str, CorpusEntry]]:
    """产出 (来源标签, 条目);来源顺序固定(corpus_view 先于 anthology),

    使得同键碰撞时 corpus_view(权威源)总是先落账,anthology 的重复条目
    被去重逻辑自然吞掉,不倒置权威(§3.7)。
    """
    for raw in paths.corpus_view or ():
        raw = dict(raw)
        raw.setdefault("_source", "memory_l1")
        try:
            yield "memory_l1", sanitize(raw)
        except RejectedEntry:
            continue
    for raw in paths.anthology_entries or ():
        raw = dict(raw)
        raw.setdefault("_source", "anthology")
        try:
            yield "anthology", sanitize(raw)
        except RejectedEntry:
            continue


def assemble(paths: CorpusPaths, out: Path, *, created_day: str) -> CorpusManifest:
    """汇编语料 → ``corpus.jsonl`` + ``corpus.manifest.json``。

    幂等:同输入同 manifest 哈希(排序后序列化,不依赖迭代顺序的偶然性)。
    空语料合法:``manifest.n_entries == 0``,trainer 侧按此拒训并明说。
    """
    seen: dict[tuple, CorpusEntry] = {}
    sources: dict[str, int] = {}
    for source_label, entry in _iter_entries(paths):
        key = _dedup_key(entry)
        if key in seen:
            continue  # 同一句不双计(§3.7 消费断言)
        seen[key] = entry
        sources[source_label] = sources.get(source_label, 0) + 1

    ordered = sorted(seen.values(), key=lambda e: (e.day_key, e.occasion, e.text))

    out.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for entry in ordered:
        lines.append(
            json.dumps(
                {
                    "text": entry.text,
                    "occasion": entry.occasion,
                    "day_key": entry.day_key,
                    "source": entry.source,
                    "features": entry.features,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    corpus_text = "\n".join(lines)
    out.write_text(corpus_text + ("\n" if corpus_text else ""), encoding="utf-8")

    corpus_hash = hashlib.sha256(corpus_text.encode("utf-8")).hexdigest()
    manifest = CorpusManifest(
        corpus_hash=corpus_hash,
        n_entries=len(ordered),
        sources=sources,
        created_day=created_day,
    )
    manifest_path = out.with_name(out.stem + ".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest


def load_corpus(path: Path) -> tuple[str, ...]:
    """读回 ``corpus.jsonl`` 的纯文本序列(trainer 输入)。"""
    if not path.is_file():
        return ()
    texts = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        texts.append(str(row.get("text", "")))
    return tuple(t for t in texts if t)


__all__ = ["CorpusPaths", "assemble", "load_corpus"]
