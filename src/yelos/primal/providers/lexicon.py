"""在整个架构中的位置:default & 兜底 provider(蓝图 §4.1)。

理论出身:封闭词典 + 收缩选择算子。双 profile:v01 与 core.primal.pick
逐字节一致(维四差分闸);expanded 读 lexicon/data/lexicon_zh.json 全量。
恒 available(A5 链尾全函数);未知场合返 FALLBACK_TEXT。
"""

from __future__ import annotations

from yelos.core.primal import pick as core_pick
from yelos.core.primal import shrink_pool

from .. import determinism
from .. import lexicon as lexicon_data
from . import ProviderUnavailable  # noqa: F401  (re-export for symmetry)


class LexiconProviderV2:
    """provider_id = "lexicon"。链尾全函数,恒 available。"""

    provider_id = "lexicon"

    def __init__(self, profile: str = "expanded") -> None:
        self.profile = profile

    def available(self, sid: str, lang: str) -> bool:  # noqa: ARG002
        return True

    def utter_canonical(
        self,
        surface: dict,
        sid: str,
        day_key: str,
        occasion: str,
        *,
        p: float,
        epoch: int,
        lang: str,
        context: dict | None = None,
    ) -> str:
        if self.profile == "v01":
            return core_pick(sid, day_key, occasion, p)
        pool = lexicon_data.query(occasion, lang, epoch, profile=self.profile)
        if not pool:
            return lexicon_data.FALLBACK_TEXT
        shrunk = shrink_pool(pool, p)
        key = f"{sid}|{day_key}|{occasion}"
        idx = determinism.h_byte(key) % len(shrunk)
        return shrunk[idx]


__all__ = ["LexiconProviderV2"]
