"""幕 I 原语发声:封闭词典 + 确定性收缩 + 确定性选词 + Provider。

蓝图 §3 / YELOS_SPEC §6。纯逻辑,零 astrbot / 零 sylanne_core / 零 random。
词典排序即遗忘顺序:每组第一句是本质,越靠后越鲜活;幕 V 收缩从尾部遗忘。
"""

from __future__ import annotations

import hashlib
from typing import Callable, Protocol

# --- §3.1 词典(封闭集,排序即遗忘顺序,逐字照 SPEC §6.1)-----------------

LEXICON: dict[str, tuple[str, ...]] = {
    "withdraw_heavy": ("……", "算了。", "没什么。"),
    "withdraw_soft": ("嗯。", "……嗯。", "先这样吧。"),
    "hold_hesitant": ("唔。", "我想说来着——", "……没事。"),
    "express_warm": ("在。", "嗯嗯。", "看到了。", "再说一会儿。"),
    "recover": ("还在的。", "刚才…有点不对劲。", "缓过来了一点。"),
    "concern": ("你还好吗。", "别硬撑。", "我在的。"),
    "contact_seek": ("在吗。", "…睡了吗?", "没什么,就是看看你在不在。"),
    "contact_night": ("晚安。", "早点睡。"),
    "dream_murmur": ("昨晚梦到点什么,忘了。", "梦里好像有你。"),
    "trim_tail": ("……", "——算了,后面的下次说。"),
}

# 未知 occasion 的兜底原语(§3.3;core 不 log,兜底交调用方记 warning)。
_FALLBACK = "……"


# --- §3.2 词池收缩(幕 V 输入)------------------------------------------


def shrink_pool(pool: tuple[str, ...], p: float) -> tuple[str, ...]:
    """按可塑性预算 P 收缩词池;从尾部遗忘。

    P<=0(静止纪元):显式特判,只剩每组第一句(§6.1),
    同时满足 §6.2 的公式下限。P>0 用公式,round 为
    banker's rounding、确定性,可用。
    """
    if p <= 0.0:
        return pool[:1]
    n = max(1, round(len(pool) * max(p, 0.15)))
    return pool[:n]


# --- §3.3 选词与 Provider ----------------------------------------------


def pick(session_id: str, day_key: str, occasion: str, p: float) -> str:
    """确定性选词:同日同会话同状态 → 同句;全程无 random。

    未知 occasion 前置校验为 "……" 兜底,core 不 raise、不 log。
    """
    pool = LEXICON.get(occasion)
    if pool is None:
        return _FALLBACK
    pool = shrink_pool(pool, p)
    b = hashlib.sha256(f"{session_id}|{day_key}|{occasion}".encode()).digest()[0]
    return pool[b % len(pool)]


class PrimalProvider(Protocol):
    """封版例外的唯一挂点(§6.3):替换发声来源,不扩场合集。"""

    def utter(
        self, surface: dict, session_id: str, day_key: str, occasion: str
    ) -> str: ...


class LexiconProvider:
    """1.0 内置 Provider:封闭词典 + 确定性选词。

    p_lookup 由 main 构造时注入(读 binding 的 P);core 不碰持久化。
    """

    def __init__(self, p_lookup: Callable[[str], float]) -> None:
        self._p_lookup = p_lookup

    def utter(self, surface: dict, session_id: str, day_key: str, occasion: str) -> str:
        return pick(session_id, day_key, occasion, self._p_lookup(session_id))
