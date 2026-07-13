"""l1_episodic 子包在架构中的位置。

情景流水:她一生的原始账(MEM-A3 append-only,MEM-A10 世代键)。全模块唯一
写入原文的地方(MEM-A5:原文只驻 L1 本地)。EpisodeStore 是磁盘面,reader
提供只读区间/日迭代;二者都不做语义处理,语义在 l2_semantic。
"""

from __future__ import annotations

from .reader import iter_day_index, sid_hash
from .store import EpisodeStore

__all__ = ["EpisodeStore", "iter_day_index", "sid_hash"]
