"""store.py 在架构中的位置。

L1 情景流水的磁盘面:追加写(append-only,MEM-A3)+ 段滚动归档(§2.2)+
崩溃安全的尾行截断恢复(§2.2)。是全模块唯一持有原文写权限的文件
(MEM-A5:用户原文只驻此处)。

零 astrbot/sylanne_core/random;时间(ts/day_key)全部由调用方(EpisodeEvent)
传入,本文件不触碰 time.time()。
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Iterator

from ..contracts import EpisodeEvent

logger = logging.getLogger(__name__)


class EpisodeStore:
    """一个 (sid, gen) 的 L1 情景流水:追加/归档/截尾恢复/区间读取。"""

    def __init__(
        self, root: Path, sid_hash: str, gen: int, *, segment_max: int = 5000
    ) -> None:
        self._dir = Path(root) / "memory" / "l1"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._sid_hash = sid_hash
        self._gen = gen
        self._segment_max = max(1, segment_max)
        self._active_path = self._dir / f"{sid_hash}.g{gen}.jsonl"
        self._day_index: dict[str, list[int]] = {}
        self._last_ts: dict[str, float] = {}
        self._active_lines = 0
        self._total = 0
        self._load_existing()

    # -- 路径 ----------------------------------------------------------

    def _archive_path(self, seg: int) -> Path:
        return self._dir / f"{self._sid_hash}.g{self._gen}.{seg}.arc.jsonl"

    def _next_archive_seg(self) -> int:
        seg = 0
        while self._archive_path(seg).exists():
            seg += 1
        return seg

    def _all_files_in_order(self) -> list[Path]:
        files: list[Path] = []
        seg = 0
        while self._archive_path(seg).exists():
            files.append(self._archive_path(seg))
            seg += 1
        if self._active_path.exists():
            files.append(self._active_path)
        return files

    # -- 加载 / 崩溃恢复(MEM-A3 的对偶:恢复不丢已提交的完整行)---------

    def _load_existing(self) -> None:
        gseq = 0
        seg = 0
        while self._archive_path(seg).exists():
            gseq = self._scan_file(self._archive_path(seg), gseq, repair=False)
            seg += 1
        if self._active_path.exists():
            gseq = self._scan_file(self._active_path, gseq, repair=True)
        self._total = gseq

    def _scan_file(self, path: Path, start_seq: int, *, repair: bool) -> int:
        raw = path.read_text(encoding="utf-8")
        lines = raw.split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        good_lines: list[str] = []
        seq = start_seq
        broke = False
        for line in lines:
            if not line.strip():
                continue
            try:
                ev = EpisodeEvent.from_dict(json.loads(line))
            except (ValueError, KeyError, TypeError, IndexError):
                broke = True
                break
            good_lines.append(line)
            self._day_index.setdefault(ev.day_key, []).append(seq)
            self._last_ts[ev.kind] = ev.ts
            seq += 1
        if broke and repair:
            logger.warning(
                "l1 tail truncated: sid_hash=%s gen=%s recovered=%d",
                self._sid_hash,
                self._gen,
                seq - start_seq,
            )
            tmp = path.with_name(path.name + ".tmp")
            text = "".join(line + "\n" for line in good_lines)
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, path)
        if path == self._active_path:
            self._active_lines = seq - start_seq
        return seq

    # -- 写 --------------------------------------------------------------

    def append(self, ev: EpisodeEvent) -> int:
        """追加一条事件,返回全局序号。kind 白名单由 EpisodeEvent 构造时校验。"""
        line = json.dumps(ev.to_dict(), ensure_ascii=False)
        with self._active_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())
        gseq = self._total
        self._day_index.setdefault(ev.day_key, []).append(gseq)
        self._last_ts[ev.kind] = ev.ts
        self._total += 1
        self._active_lines += 1
        if self._active_lines >= self._segment_max:
            self._roll_segment()
        return gseq

    def _roll_segment(self) -> None:
        seg = self._next_archive_seg()
        os.replace(self._active_path, self._archive_path(seg))
        self._active_lines = 0

    # -- 读(只读,不做语义处理)-------------------------------------------

    def _iter_raw(self) -> Iterator[tuple[int, EpisodeEvent]]:
        seq = 0
        for path in self._all_files_in_order():
            raw = path.read_text(encoding="utf-8")
            for line in raw.split("\n"):
                if not line.strip():
                    continue
                try:
                    ev = EpisodeEvent.from_dict(json.loads(line))
                except (ValueError, KeyError, TypeError, IndexError):
                    continue
                yield seq, ev
                seq += 1

    def read_span(self, start: int, end: int) -> list[EpisodeEvent]:
        """闭区间 [start, end] 的事件列表(按全局序号)。"""
        out: list[EpisodeEvent] = []
        for seq, ev in self._iter_raw():
            if seq > end:
                break
            if seq >= start:
                out.append(ev)
        return out

    def read_day(self, day_key: str) -> list[EpisodeEvent]:
        seqs = self._day_index.get(day_key, [])
        if not seqs:
            return []
        target = set(seqs)
        out: list[EpisodeEvent] = []
        for seq, ev in self._iter_raw():
            if seq in target:
                out.append(ev)
        return out

    def iter_all(
        self, *, kinds: tuple[str, ...] = ()
    ) -> Iterator[tuple[int, EpisodeEvent]]:
        for seq, ev in self._iter_raw():
            if kinds and ev.kind not in kinds:
                continue
            yield seq, ev

    def last_ts(self, kind: str = "user_turn") -> float | None:
        return self._last_ts.get(kind)

    def latest_ts(self) -> float:
        """全部 kind 中最新的 ts;空库返回 0.0(供 viz_export 无 now_ts 入参时兜底)。"""
        if not self._last_ts:
            return 0.0
        return max(self._last_ts.values())

    def count(self) -> int:
        return self._total

    def day_keys(self) -> list[str]:
        """按首次出现顺序返回全部已记录 day_key(供 consolidation 巡检用)。"""
        return list(self._day_index.keys())

    def day_span(self, day_key: str) -> tuple[int, int] | None:
        seqs = self._day_index.get(day_key)
        if not seqs:
            return None
        return (min(seqs), max(seqs))
