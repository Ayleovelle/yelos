"""redact.py 在架构中的位置。

隐私公理 MEM-A5 的界定函数:``is_verbatim_leak`` 判定候选字符串是否命中
任一 L1 原文的连续 ≥min_run 字符子串。零 astrbot/sylanne_core/random,
纯字符串扫描,O(len(candidate)+sum(len(l1_texts))) 滚动哈希实现。

这是全模块隐私红线的唯一界定处:关键词 token(≤6 字)放行,连续 ≥8 字符
原句子串一律判定为泄漏(M2 裁决)。
"""

from __future__ import annotations

from typing import Iterable

_BASE = 257
_MOD = (1 << 61) - 1


def _poly_hash(s: str) -> int:
    h = 0
    for ch in s:
        h = (h * _BASE + ord(ch)) % _MOD
    return h


def is_verbatim_leak(candidate: str, l1_texts: Iterable[str], min_run: int = 8) -> bool:
    """candidate 是否命中 l1_texts 中任一原文的连续 ≥min_run 字符子串。

    空 candidate / candidate 短于 min_run 一律判 False(无法构成"整句复述")。
    """
    if not candidate or len(candidate) < min_run:
        return False

    candidate_windows: dict[int, set[str]] = {}
    for i in range(len(candidate) - min_run + 1):
        w = candidate[i : i + min_run]
        candidate_windows.setdefault(_poly_hash(w), set()).add(w)
    if not candidate_windows:
        return False

    power = pow(_BASE, min_run - 1, _MOD)
    for text in l1_texts:
        if not text or len(text) < min_run:
            continue
        h = _poly_hash(text[:min_run])
        if h in candidate_windows and text[:min_run] in candidate_windows[h]:
            return True
        for i in range(1, len(text) - min_run + 1):
            h = (h - ord(text[i - 1]) * power) % _MOD
            h = (h * _BASE + ord(text[i + min_run - 1])) % _MOD
            if h in candidate_windows:
                window = text[i : i + min_run]
                if window in candidate_windows[h]:
                    return True
    return False
