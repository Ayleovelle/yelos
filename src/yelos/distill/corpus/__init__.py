"""corpus/ 在整个架构中的位置:语料装配与脱敏(蓝图 §1 D1 波)。

对外只暴露装配入口与数据结构;闸/训练/打包不 import 本包的私有细节。
"""

from __future__ import annotations

from .assembler import CorpusPaths, assemble, load_corpus
from .manifest import CorpusEntry, CorpusManifest
from .sanitizer import RejectedEntry, sanitize

__all__ = [
    "CorpusPaths",
    "assemble",
    "load_corpus",
    "CorpusEntry",
    "CorpusManifest",
    "RejectedEntry",
    "sanitize",
]
