"""emotion.py 在架构中的位置。

L2 情感标注只来自引擎 Surface 伴随的 AffectStamp 聚合,永不从文本猜测情绪
(MEM-A7)。本文件不含任何情感词典、不接受 text 参数——AST 测试锁此边界。
"""

from __future__ import annotations

from ..contracts import AffectStamp

# 白名单象限 label(warmth×pressure 四象限查表,非文本推断,MEM-A7)。
_WARM_HI = 0.55
_PRESSURE_HI = 0.55


def quadrant_label(warmth_mean: float, pressure_mean: float) -> str:
    """warmth×pressure 四象限查表(公开,供 recall/service.py 算主题情感 label 复用)。"""
    warm = warmth_mean >= _WARM_HI
    tense = pressure_mean >= _PRESSURE_HI
    if warm and not tense:
        return "偏暖"
    if warm and tense:
        return "暖但绷"
    if not warm and tense:
        return "偏紧"
    return "平静"


_quadrant_label = quadrant_label  # noqa: E731  向后兼容别名(内部曾用私有名)


def aggregate_emotion(
    stamps: list[AffectStamp], day_keys: list[str] | None = None
) -> dict:
    """聚合一批 AffectStamp:{"warmth_mean","pressure_mean","label"}。

    day_keys(与 stamps 等长,可选)存在时附带 peak_day(warmth 极值日)。
    空输入返回中性结果,不 raise。
    """
    if not stamps:
        return {"warmth_mean": 0.0, "pressure_mean": 0.0, "label": "平静"}
    n = len(stamps)
    warmth_mean = sum(s.warmth for s in stamps) / n
    pressure_mean = sum(s.pressure for s in stamps) / n
    out = {
        "warmth_mean": warmth_mean,
        "pressure_mean": pressure_mean,
        "label": _quadrant_label(warmth_mean, pressure_mean),
    }
    if day_keys and len(day_keys) == n:
        peak_idx = max(range(n), key=lambda i: stamps[i].warmth)
        out["peak_day"] = day_keys[peak_idx]
    return out
