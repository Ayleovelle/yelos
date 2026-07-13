"""lifecycle.py 在架构中的位置。

隐私主权动作的执行面:reset(清 L2/L3/index/journal,L1 默认留档)、
seal_export(farewell 导出,export_raw 默认 False,M8)、corpus_view(蒸馏语料,
只吐 her_word/dream)。只操作磁盘路径与只读迭代,不持有跨调用可变状态。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator, Protocol


class _L1Readable(Protocol):
    def iter_all(self, *, kinds: tuple[str, ...] = ()) -> Iterator[tuple]: ...


def _load_json(path: Path, default: dict) -> dict:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


class PrivacyLifecycle:
    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def _memory_dir(self) -> Path:
        return self._root / "memory"

    def _paths(self, sid_hash: str, gen: int) -> dict[str, Path]:
        base = self._memory_dir()
        return {
            "l2": base / "l2" / f"{sid_hash}.g{gen}.json",
            "l3": base / "l3" / f"{sid_hash}.g{gen}.json",
            "vocab": base / "index" / f"{sid_hash}.g{gen}.vocab.json",
        }

    # -- MEM-A5 主权动作 ------------------------------------------------

    def reset(self, sid_hash: str, gen: int, *, keep_l1_archive: bool = True) -> None:
        """清 L2/L3/index/journal;L1 默认留档,keep_l1_archive=False 才全清。"""
        for p in self._paths(sid_hash, gen).values():
            if p.exists():
                p.unlink()
        journal_dir = self._memory_dir() / "journal"
        if journal_dir.is_dir():
            for p in journal_dir.glob(f"{sid_hash}.g{gen}.*.json"):
                p.unlink()
        if not keep_l1_archive:
            l1_dir = self._memory_dir() / "l1"
            if l1_dir.is_dir():
                for p in l1_dir.glob(f"{sid_hash}.g{gen}*.jsonl"):
                    p.unlink()

    def seal_export(
        self,
        sid_hash: str,
        gen: int,
        *,
        export_raw: bool = False,
        l1_store: _L1Readable | None = None,
    ) -> dict:
        """farewell 导出:主题史 + L2 摘要 + 统计;export_raw 显式 opt-in(M8)。"""
        paths = self._paths(sid_hash, gen)
        l2 = _load_json(paths["l2"], {"entries": []})
        l3 = _load_json(paths["l3"], {"topics": []})
        out: dict = {
            "topics": l3.get("topics", []),
            "l2_summaries": [
                {
                    "summary": e.get("summary", ""),
                    "keywords": e.get("keywords", []),
                    "day_key": e.get("day_key", ""),
                    "topic_id": e.get("topic_id", ""),
                }
                for e in l2.get("entries", [])
            ],
            "stats": {
                "l2_count": len(l2.get("entries", [])),
                "l3_count": len(l3.get("topics", [])),
            },
        }
        if export_raw and l1_store is not None:
            out["l1_raw"] = [ev.to_dict() for _, ev in l1_store.iter_all()]
        return out

    def corpus_view(self, l1_store: _L1Readable) -> Iterator[dict]:
        """蒸馏语料:只吐 her_word/dream,只含她的话(§5.4)。"""
        for _seq, ev in l1_store.iter_all(kinds=("her_word", "dream")):
            yield {
                "text": ev.text,
                "occasion": ev.occasion,
                "affect": ev.affect.to_dict() if ev.affect is not None else {},
                "day_key": ev.day_key,
            }
