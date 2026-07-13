"""HintKey 枚举 + ``get_phrase(key, lang)`` 带 zh 兜底(A1 封闭句库)。

三语句库都是封闭 dict:任何 ``key`` 必须在 :data:`HintKey` 枚举里,
``get_phrase`` 对未解锁语言(``UNLOCKED=False``)或未知 key 一律回落 zh,
绝不抛出让调用方看见半成品文案(保守默认)。
"""

from __future__ import annotations

from enum import Enum

from . import en as _en
from . import ja as _ja
from . import zh as _zh

_TABLES: dict[str, tuple[dict[str, str], bool]] = {
    "zh": (_zh.PHRASES_ZH, True),
    "en": (_en.PHRASES_EN, _en.UNLOCKED),
    "ja": (_ja.PHRASES_JA, _ja.UNLOCKED),
}


class HintKey(str, Enum):
    """封闭句库键集合(18 键,逐字对齐 v0.1 §4.2 白名单)。"""

    WITHDRAW = "WITHDRAW"
    RECOVER = "RECOVER"
    REACH_OUT = "REACH_OUT"
    EXPLORE = "EXPLORE"
    GUARD_DECISION = "GUARD_DECISION"
    EXPRESS = "EXPRESS"
    STRAIN = "STRAIN"
    FATIGUE = "FATIGUE"
    WARM_HIGH = "WARM_HIGH"
    WARM_LOW = "WARM_LOW"
    DAMAGE = "DAMAGE"
    AUTONOMY = "AUTONOMY"
    QUIET = "QUIET"
    EXPRESSION = "EXPRESSION"
    DORMANT = "DORMANT"
    CAUTION = "CAUTION"
    CONCERN = "CONCERN"
    GUARD_BLOCKED = "GUARD_BLOCKED"


def get_phrase(key: str, lang: str = "zh") -> str:
    """封闭句库取句:``lang`` 未解锁或未知一律回落 zh;``key`` 非法抛
    ``KeyError``(规则集内部错误,不该在正常运行时发生,不做静默兜底掩盖)。
    """
    if key not in HintKey.__members__:
        raise KeyError(f"未登记的 hint key: {key!r}(不在 HintKey 白名单内)")
    table, unlocked = _TABLES.get(lang, (_zh.PHRASES_ZH, True))
    if not unlocked:
        table = _zh.PHRASES_ZH
    return table.get(key, _zh.PHRASES_ZH[key])


__all__ = ["HintKey", "get_phrase"]
