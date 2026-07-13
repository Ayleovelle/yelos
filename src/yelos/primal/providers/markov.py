"""在整个架构中的位置:她自己语料上的低阶马尔可夫表面(蓝图 §4.3)。

仅路由到 dream_murmur / trim_tail(Tier-R 专属)。前置条件:语料量 >=
min_corpus 且 enabled;不满足 raise ProviderUnavailable(A8,渐近在场)。
转移表建自 corpus(她自己被闸放行过的历史发声,不含用户文本)。
"""

from __future__ import annotations

from .. import determinism
from . import ProviderUnavailable

_TERMINATORS = ("。", "…", "?", "!")
_MAX_LEN = 20


def _build_transitions(
    corpus: tuple[str, ...],
) -> dict[tuple[str, str], tuple[str, ...]]:
    table: dict[tuple[str, str], list[str]] = {}
    for s in corpus:
        for i in range(len(s) - 2):
            key = (s[i], s[i + 1])
            table.setdefault(key, []).append(s[i + 2])
    return {k: tuple(v) for k, v in table.items()}


def _starting_bigrams(corpus: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    seen: list[tuple[str, str]] = []
    for s in corpus:
        if len(s) >= 2:
            bg = (s[0], s[1])
            if bg not in seen:
                seen.append(bg)
    return tuple(seen)


class MarkovSurfaceProvider:
    provider_id = "markov"

    def __init__(self, enabled: bool = True, min_corpus: int = 50) -> None:
        self.enabled = enabled
        self.min_corpus = min_corpus

    def available(self, sid: str, lang: str) -> bool:  # noqa: ARG002
        return self.enabled

    def _corpus_ready(self, corpus: tuple[str, ...]) -> bool:
        return len(corpus) >= self.min_corpus

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
        corpus = (context or {}).get("corpus", ())
        if not self.enabled or not self._corpus_ready(corpus):
            raise ProviderUnavailable("markov corpus below threshold")
        bigrams = _starting_bigrams(corpus)
        if not bigrams:
            raise ProviderUnavailable("markov corpus has no usable bigram")
        transitions = _build_transitions(corpus)

        start_key = f"{sid}|{day_key}|{occasion}|mkv|0"
        idx0 = determinism.h_byte(start_key) % len(bigrams)
        c1, c2 = bigrams[idx0]
        out = [c1, c2]
        if c2 in _TERMINATORS:
            return "".join(out)

        i = 2
        while len(out) < _MAX_LEN:
            step_key = f"{sid}|{day_key}|{occasion}|mkv|{i}"
            choices = transitions.get((out[-2], out[-1]))
            if not choices:
                break
            nxt = choices[determinism.h_byte(step_key) % len(choices)]
            out.append(nxt)
            if nxt in _TERMINATORS:
                break
            i += 1
        text = "".join(out)
        if not text.endswith(_TERMINATORS):
            text = text[: _MAX_LEN - 1] + "…"
        return text


__all__ = ["MarkovSurfaceProvider"]
