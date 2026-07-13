"""reader.py 在架构中的位置。

L1 之外的小工具:sid 文件名安全化(sid_hash)+ 日索引展平辅助。EpisodeStore
自己已经维护内存日索引;这里只放跨 store 复用的纯函数,避免 facade 里散落
blake2b 调用点。
"""

from __future__ import annotations

import hashlib


def sid_hash(sid: str) -> str:
    """sid → 文件名安全化短哈希(blake2b 12 位十六进制,§2.2)。"""
    return hashlib.blake2b(sid.encode("utf-8"), digest_size=6).hexdigest()


def iter_day_index(day_index: dict[str, list[int]]) -> list[tuple[str, int, int]]:
    """把 day_key -> [seq,...] 展平为 (day_key, start, end) 排序列表。"""
    out: list[tuple[str, int, int]] = []
    for day_key, seqs in day_index.items():
        if not seqs:
            continue
        out.append((day_key, min(seqs), max(seqs)))
    out.sort(key=lambda t: t[1])
    return out
