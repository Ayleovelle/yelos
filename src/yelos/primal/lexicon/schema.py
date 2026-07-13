"""在整个架构中的位置:词库/文法的数据结构定义(蓝图 §3)。

纯 dataclass,零校验逻辑(校验在 lexicon/__init__.py 的 loader 里,
schema 只定形状)。
"""

from __future__ import annotations

from dataclasses import dataclass

REGISTER_ORDER: dict[str, int] = {"essence": 0, "plain": 1, "vivid": 2}


@dataclass(frozen=True)
class LexEntry:
    """词条:句本体 + 元数据。

    不变式(load 时校验,见 lexicon/__init__.py):
    - 每场合组按 register 排序(essence 优先);
    - 组内 v0.1 原句保持 v0.1 原序为前缀(§11.2 前缀兼容律);
    - epoch 过滤后组仍非空(essence 句 epoch 全开)。
    """

    text: str
    register: str = "plain"
    prosody_hint: str = ""
    intensity: int = 1
    epoch_min: int = 0
    epoch_max: int = 99


@dataclass(frozen=True)
class GrammarSpec:
    """场合的有限槽位文法(受限上下文无关文法,深度 1)。"""

    occasion: str
    patterns: tuple[tuple[str, ...], ...]
    slots: dict[str, tuple[str, ...]]
    max_len: int = 24
