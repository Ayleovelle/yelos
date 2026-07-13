"""在整个架构中的位置:韵律变换的原子操作 + 幂等守卫(蓝图 §7.1)。

幂等守卫:纯省略号句、已含"——"结尾句、prosody_hint=="no_prosody" 的
词条跳过全部变换(不叠加、不二次施加)。
"""

from __future__ import annotations

_PAUSE_CHARS = ",,、"
_STRONG_TERMINATORS = ("。", "…", "?", "!")


def is_idempotent_skip(canonical: str, hint: str) -> bool:
    if hint == "no_prosody":
        return True
    stripped = canonical.strip("…. 　")
    if stripped == "":
        return True
    if canonical.endswith("——"):
        return True
    return False


def identity(text: str) -> tuple[str, str]:
    return text, ""


def append_ellipsis(text: str) -> tuple[str, str]:
    if text.endswith("…"):
        return text, ""
    return text + "…", "trail"


def insert_breath(text: str) -> tuple[str, str]:
    for i, ch in enumerate(text):
        if ch in _PAUSE_CHARS:
            return text[: i + 1] + "……" + text[i + 1 :], "breath"
    return text, ""


def stutter_first(text: str) -> tuple[str, str]:
    if not text:
        return text, ""
    n = 1 if len(text) < 4 else 2
    head = text[:n]
    return f"{head}、{text}", "stutter"


def half_stop(text: str) -> tuple[str, str]:
    for sep in ("。", "，", ",", "、"):
        idx = text.find(sep)
        if idx > 0:
            return text[:idx] + "——", "half_stop"
    if len(text) > 1:
        return text[: max(1, len(text) // 2)] + "——", "half_stop"
    return text, ""


__all__ = [
    "is_idempotent_skip",
    "identity",
    "append_ellipsis",
    "insert_breath",
    "stutter_first",
    "half_stop",
]
