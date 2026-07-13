"""moments/ledger.py 在整个架构中的位置:MomentsLedger 追加式流水(维一自著,§5.2)。

本体:`data_dir/moments/{sid_hash}.jsonl` 追加式;按月滚动归档
`moments/{sid_hash}/{yyyymm}.jsonl.gz`;永不删(可考古)。本文件只管落盘/
读取/归档,不认识 memory/finitude——双写 L1 与 daily.moments_counts 的
编排在 scheduler/(该层依赖全部),保持 moments 依赖方向干净(仅 core/
stdlib,intrinsic_BLUEPRINT §2.1)。

`sid_hash()` 与 `memory.l1_episodic.reader.sid_hash` 同一算法(blake2b
12 位十六进制),不 import 对方包,避免跨模块耦合,只求文件名习惯一致。
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path

from .taxonomy import MomentEntry


def sid_hash(sid: str) -> str:
    """sid → 文件名安全化短哈希(与 memory 侧同算法,不同实现落点)。"""
    return hashlib.blake2b(sid.encode("utf-8"), digest_size=6).hexdigest()


def compute_trace_hash(trace: dict) -> str:
    """PolicyProposal.trace 的哈希指纹(§5.1:全 trace 落 viz 契约,此处只留指纹)。"""
    canonical = json.dumps(trace, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


class MomentsLedger:
    """追加式 jsonl + 滚动归档;心跳单 session 临界区内调用(per-session lock)。"""

    def __init__(self, data_dir: str | Path, sid_hash_value: str) -> None:
        self._root = Path(data_dir) / "moments"
        self._root.mkdir(parents=True, exist_ok=True)
        self._sid_hash = sid_hash_value
        self._path = self._root / f"{sid_hash_value}.jsonl"

    @property
    def path(self) -> Path:
        return self._path

    def append(self, entry: MomentEntry) -> None:
        line = json.dumps(entry.to_dict(), ensure_ascii=False)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def read_all(self) -> list[MomentEntry]:
        if not self._path.exists():
            return []
        out: list[MomentEntry] = []
        with self._path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                out.append(MomentEntry.from_dict(json.loads(raw)))
        return out

    def read_day(self, day_key: str) -> list[MomentEntry]:
        return [e for e in self.read_all() if e.day_key == day_key]

    def archive_before(self, cutoff_day_key: str) -> int:
        """把 day_key < cutoff 的行按月滚动进 `{sid_hash}/{yyyymm}.jsonl.gz`。

        本体只留 >= cutoff 的行;归档只增不删(gz 追加式打开)。返回归档行数。
        """
        entries = self.read_all()
        to_archive = [e for e in entries if e.day_key < cutoff_day_key]
        to_keep = [e for e in entries if e.day_key >= cutoff_day_key]
        if not to_archive:
            return 0

        by_month: dict[str, list[MomentEntry]] = {}
        for e in to_archive:
            digits = e.day_key.replace("-", "")
            yyyymm = digits[:6] if len(digits) >= 6 else "unknown"
            by_month.setdefault(yyyymm, []).append(e)

        archive_dir = self._root / self._sid_hash
        archive_dir.mkdir(parents=True, exist_ok=True)
        for yyyymm, es in by_month.items():
            gz_path = archive_dir / f"{yyyymm}.jsonl.gz"
            mode = "at" if gz_path.exists() else "wt"
            with gzip.open(gz_path, mode, encoding="utf-8") as fh:
                for e in es:
                    fh.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")

        tmp = self._path.with_name(self._path.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            for e in to_keep:
                fh.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")
        os.replace(tmp, self._path)
        return len(to_archive)


def read_moments(data_dir: str | Path, sid: str, gen: int = 0) -> list[MomentEntry]:
    """C8 只读流水契约(INTEGRATION_SPEC §1.1):`intrinsic.moments.read_moments`。

    `gen`(世代)当前不切分文件(moments 不随 incarnation 重置,§0.3 未提及
    需重置;跨世保留是"可考古"纪律的自然延伸),形参保留以对齐契约签名,
    供未来若需要按世代切分时不必改调用方。
    """
    ledger = MomentsLedger(data_dir, sid_hash(sid))
    return ledger.read_all()


__all__ = ["MomentsLedger", "sid_hash", "compute_trace_hash", "read_moments"]
