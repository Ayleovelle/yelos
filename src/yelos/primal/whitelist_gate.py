"""在整个架构中的位置:一切 provider 输出的唯一出口(蓝图 §6/A1a/A1b)。

双层闸:8 个核心场合走 Tier-S(frozenset 成员判定,查表源 =
lexicon.closure.enumerate_closure);dream_murmur/trim_tail 走 Tier-R
(语料闭包五条件,§6.1/§6.2)。禁形表(forbidden_zh.json)在两层之前先过
一遍,作为对未来 provider(distilled 等)的纵深防御(§6.3:concern 额外
启用最严档——concern_only 规则只在 concern 场合生效)。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

TIER_R_OCCASIONS = frozenset({"dream_murmur", "trim_tail"})
_TERMINATORS = ("。", "…", "?", "!")
_LONG_BAND_LIMIT = 12
_MAX_RECOMBINATION_LEN = 20

_DATA_DIR = Path(__file__).resolve().parent / "lexicon" / "data"


@dataclass(frozen=True)
class GateResult:
    ok: bool
    tier: str
    reason: str


def load_forbidden_patterns(lang: str = "zh") -> tuple[tuple[re.Pattern, bool], ...]:
    """装载禁形表(数据不是代码,§6.3);拒载/损坏 → 空表(不阻断发声)。"""
    path = _DATA_DIR / f"forbidden_{lang}.json"
    if not path.is_file():
        return ()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    out = []
    for item in raw.get("patterns", ()):
        try:
            pat = re.compile(str(item["regex"]))
        except (re.error, KeyError):
            continue
        out.append((pat, bool(item.get("concern_only", False))))
    return tuple(out)


def _corpus_trigrams(corpus: tuple[str, ...]) -> frozenset[str]:
    grams: set[str] = set()
    for s in corpus:
        for i in range(len(s) - 2):
            grams.add(s[i : i + 3])
    return frozenset(grams)


def _corpus_alphabet(corpus: tuple[str, ...]) -> frozenset[str]:
    alphabet: set[str] = set("。,,.!?…——、 \n")
    for s in corpus:
        alphabet.update(s)
    return frozenset(alphabet)


class WhitelistGate:
    """A1a/A1b 的可执行形式:check() 是全部 provider 输出的唯一出口。"""

    def __init__(
        self,
        closure_fn: Callable[[str, str, str, int], frozenset[str]],
        *,
        forbidden_patterns: tuple[tuple[re.Pattern, bool], ...] = (),
    ) -> None:
        self._closure_fn = closure_fn
        self._forbidden = forbidden_patterns

    def check(
        self,
        canonical: str,
        occasion: str,
        lang: str,
        band: str,
        epoch: int,
        corpus: tuple[str, ...],
    ) -> GateResult:
        tier = "R" if occasion in TIER_R_OCCASIONS else "S"
        for pat, concern_only in self._forbidden:
            if concern_only and occasion != "concern":
                continue
            if pat.search(canonical):
                return GateResult(False, tier, "forbidden_pattern")
        if tier == "R":
            return self._check_recombination(
                canonical, occasion, lang, band, epoch, corpus
            )
        return self._check_strict(canonical, occasion, lang, band, epoch)

    def _check_strict(
        self, canonical: str, occasion: str, lang: str, band: str, epoch: int
    ) -> GateResult:
        canon = self._closure_fn(occasion, lang, band, epoch)
        if canonical in canon:
            return GateResult(True, "S", "member")
        return GateResult(False, "S", "not_member")

    def _check_recombination(
        self,
        canonical: str,
        occasion: str,
        lang: str,
        band: str,
        epoch: int,
        corpus: tuple[str, ...],
    ) -> GateResult:
        if not canonical:
            return GateResult(False, "R", "too_long")
        if len(canonical) > _MAX_RECOMBINATION_LEN:
            return GateResult(False, "R", "too_long")
        if band in ("B0", "B1") and len(canonical) > _LONG_BAND_LIMIT:
            return GateResult(False, "R", "too_long")

        canon = self._closure_fn(occasion, lang, band, epoch)
        if canonical in canon:
            return GateResult(True, "R", "member")

        ends_ok = canonical.endswith(_TERMINATORS) or canonical.endswith("——")
        if not ends_ok:
            return GateResult(False, "R", "bad_terminator")

        alphabet = _corpus_alphabet(corpus)
        if any(ch not in alphabet for ch in canonical):
            return GateResult(False, "R", "alien_char")

        corpus_trigrams = _corpus_trigrams(corpus)
        for i in range(len(canonical) - 2):
            if canonical[i : i + 3] not in corpus_trigrams:
                return GateResult(False, "R", "trigram_alien")

        return GateResult(True, "R", "member")


__all__ = ["GateResult", "WhitelistGate", "TIER_R_OCCASIONS", "load_forbidden_patterns"]
