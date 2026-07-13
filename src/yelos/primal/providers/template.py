"""在整个架构中的位置:受限上下文无关文法 provider(蓝图 §4.2)。

理论出身:受限上下文无关文法,深度 1,槽位有限。dream_murmur 的
d_theme 槽支持 context={"theme": ...} 的封闭集"取整"直通(仍是槽位内
成员,不破封闭)。
"""

from __future__ import annotations

from yelos.core.primal import shrink_pool

from .. import determinism
from .. import lexicon as lexicon_data
from . import ProviderUnavailable


class TemplateGrammarProvider:
    provider_id = "template"

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def available(self, sid: str, lang: str) -> bool:  # noqa: ARG002
        return self.enabled

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
        spec = lexicon_data.grammar_spec(occasion, lang)
        if spec is None or not spec.patterns:
            raise ProviderUnavailable(f"no grammar for occasion={occasion!r}")
        context = context or {}
        theme = context.get("theme") if occasion == "dream_murmur" else None

        pat_key = f"{sid}|{day_key}|{occasion}|tpl|pat"
        start = determinism.h_byte(pat_key) % len(spec.patterns)
        for offset in range(len(spec.patterns)):
            pattern = spec.patterns[(start + offset) % len(spec.patterns)]
            parts: list[str] = []
            ok = True
            for slot_id in pattern:
                pool = spec.slots.get(slot_id, ())
                if not pool:
                    ok = False
                    break
                if slot_id == "d_theme" and theme is not None and theme in pool:
                    filler = theme
                else:
                    shrunk = shrink_pool(pool, p)
                    if not shrunk:
                        ok = False
                        break
                    slot_key = f"{sid}|{day_key}|{occasion}|tpl|{slot_id}"
                    filler = shrunk[determinism.h_byte(slot_key) % len(shrunk)]
                parts.append(filler)
            if not ok:
                continue
            text = "".join(parts)
            if text and len(text) <= spec.max_len:
                return text
        raise ProviderUnavailable(
            f"all patterns violated constraints for occasion={occasion!r}"
        )


__all__ = ["TemplateGrammarProvider"]
