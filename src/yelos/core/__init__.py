"""YELOS 纯逻辑层公共工具:防御式取值、七级序数词、句子切分。

蓝图 §2.3 / §2.4 / §4.3。三个纯函数,dict/标量进、标量/列表出。
[强制] 本包零 astrbot import、零 sylanne_core import、零 random import;
时间/状态/配置一律入参传入,core 内不触碰 time/datetime/random/持久化。
"""

from __future__ import annotations

# --- §2.3 防御式取值器 -------------------------------------------------------


def sget(surface: dict | None, path: str, default):
    """点路径安全取值:``sget(s, "state.boundary.pressure", 0.0)``。

    沿 ``path`` 的 ``.`` 分段逐层下钻 dict;任一段缺失、或中途遇到非 dict、
    或 ``surface`` 本身为 None,一律返回 ``default``,绝不抛异常。
    Surface 字段缺失不该让插件崩,只该退回保守默认(保守方向 = 不触发干预)。

    调用方默认值约定(蓝图 §2.3,保守方向;由调用方按需传入):
        state.boundary.pressure         -> 0.0
        state.needs.*                   -> 0.0
        state.interruption_budget       -> 1.0
        guard.allowed                   -> True
        dynamics.relational_time.phase  -> "active"
        warmth (基线/当前)              -> None   (None 时跳过跌幅判定)
        shadow damage.open              -> 0.0
        decision.action                 -> "hold"
        pad.label                       -> "neutral"

    注:仅当路径无法解析时才回退 ``default``;若字段确实存在且值为 None,
    返回真实的 None(例如 warmth 显式为 None 与"未采样"在语义上等价)。
    """
    if surface is None:
        return default
    cur = surface
    for seg in path.split("."):
        if not isinstance(cur, dict) or seg not in cur:
            return default
        cur = cur[seg]
    return cur


# --- §2.4 七级序数词 ---------------------------------------------------------

_ORDINAL7: tuple[str, ...] = (
    "几乎没有",
    "很低",
    "偏低",
    "中",
    "偏高",
    "很高",
    "满满",
)


def ordinal7(x: float) -> str:
    """把 ``[0,1]`` 均分 7 档映射到序数词,给状态/年轮展示用(禁浮点噪声)。

    档位:几乎没有 / 很低 / 偏低 / 中 / 偏高 / 很高 / 满满。
    越界输入先钳到 ``[0,1]``;``x == 1.0`` 归入最高档"满满"。
    """
    if x <= 0.0:
        return _ORDINAL7[0]
    if x >= 1.0:
        return _ORDINAL7[-1]
    idx = int(x * 7)
    if idx > 6:
        idx = 6
    return _ORDINAL7[idx]


# --- §4.3 句子切分 -----------------------------------------------------------

# 终止标点:中文/英文句末标点 + 省略号。换行另作切分点但不保留换行字符。
_TERMINATORS = frozenset("。！？!?…")


def split_sentences(text: str) -> list[str]:
    """按句末标点与换行切句,保留标点,连续省略号(及连续句末标点)算一处。

    切分点:``。！？!?…`` 与换行 ``\\n`` / ``\\r``。句末标点保留在句尾;
    连续的句末标点(如 ``……``、``？！``)整体算一个边界,不产生空句。
    换行是边界但本身不计入正文。逐句去首尾空白,丢弃空句。

    幕 II 仲裁据此取"首句 / 前两句 / 句数",故须确定性、无副作用。
    """
    sentences: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        s = "".join(buf).strip()
        if s:
            sentences.append(s)
        buf.clear()

    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in ("\n", "\r"):
            flush()
            i += 1
            continue
        if ch in _TERMINATORS:
            # 吸收整段连续句末标点为一个边界。
            while i < n and text[i] in _TERMINATORS:
                buf.append(text[i])
                i += 1
            flush()
            continue
        buf.append(ch)
        i += 1
    flush()
    return sentences
