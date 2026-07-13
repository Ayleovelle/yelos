"""在整个架构中的位置:语言身份解析/审校闸子包(蓝图 §9)。"""

from __future__ import annotations

from .lang import REVIEWED_LANGS, bind_lang_decision, resolve_lang

__all__ = ["REVIEWED_LANGS", "resolve_lang", "bind_lang_decision"]
