"""在整个架构中的位置:词库/文法数据访问 API(蓝图 §2/§11)。

load/query/池排序不变式校验;v01 profile 直读 core.primal.LEXICON
逐字节不改(维四差分闸的地基),expanded profile 读本包 data/*.json。

零 hashlib(选词哈希由 providers 层调用 determinism.h_byte,本模块
只管"数据是什么",不管"怎么选")。
"""

from __future__ import annotations

import json
from pathlib import Path

from yelos.core.primal import LEXICON as CORE_LEXICON

from .schema import REGISTER_ORDER, GrammarSpec, LexEntry

_DATA_DIR = Path(__file__).resolve().parent / "data"

FALLBACK_TEXT = "……"

REVIEWED_LEXICON_LANGS = ("zh",)

_lexicon_cache: dict[str, dict[str, tuple[LexEntry, ...]]] = {}
_themes_cache: dict[str, tuple[str, ...]] = {}
_grammar_cache: dict[str, dict[str, GrammarSpec]] = {}


class LexiconLoadError(ValueError):
    """词库/文法装载期不变式违反(fail-fast,不在她嘴上暴露)。"""


def _entry_from_dict(d: dict) -> LexEntry:
    return LexEntry(
        text=str(d["text"]),
        register=str(d.get("register", "plain")),
        prosody_hint=str(d.get("prosody_hint", "")),
        intensity=int(d.get("intensity", 1)),
        epoch_min=int(d.get("epoch_min", 0)),
        epoch_max=int(d.get("epoch_max", 99)),
    )


def _validate_prefix(occasion: str, entries: tuple[LexEntry, ...]) -> None:
    """§11.2 前缀兼容律:v0.1 原句逐字保留且保持组内前缀原序(essence 端)。"""
    v01_pool = CORE_LEXICON.get(occasion, ())
    if not v01_pool:
        return
    texts = tuple(e.text for e in entries)
    if texts[: len(v01_pool)] != v01_pool:
        raise LexiconLoadError(
            f"{occasion}: expanded 词库未把 v0.1 原句作为前缀保留"
            f"(v01={v01_pool!r}, got prefix={texts[: len(v01_pool)]!r})"
        )


def _validate_register_order(occasion: str, entries: tuple[LexEntry, ...]) -> None:
    ranks = [REGISTER_ORDER.get(e.register, 99) for e in entries]
    if ranks != sorted(ranks):
        raise LexiconLoadError(f"{occasion}: 词条未按 register 序排列(essence 优先)")


def _validate_epoch_nonempty(occasion: str, entries: tuple[LexEntry, ...]) -> None:
    for epoch in range(0, 5):
        if not any(e.epoch_min <= epoch <= e.epoch_max for e in entries):
            raise LexiconLoadError(f"{occasion}: epoch={epoch} 过滤后组为空")


def load_lexicon(lang: str) -> dict[str, tuple[LexEntry, ...]]:
    """装载 lang 的全量词库;非 REVIEWED 语言拒载(§9 审校闸,由 i18n 层裁决

    是否回落 zh——本函数只管"能不能读到数据",不做语言回落决策)。
    """
    if lang in _lexicon_cache:
        return _lexicon_cache[lang]
    path = _DATA_DIR / f"lexicon_{lang}.json"
    if not path.is_file() or lang not in REVIEWED_LEXICON_LANGS:
        raise LexiconLoadError(f"lang={lang!r} 未审校或无数据文件,拒载")
    raw = json.loads(path.read_text(encoding="utf-8"))
    occasions: dict[str, tuple[LexEntry, ...]] = {}
    for occasion, block in raw.get("occasions", {}).items():
        entries = tuple(_entry_from_dict(d) for d in block.get("entries", []))
        _validate_register_order(occasion, entries)
        _validate_prefix(occasion, entries)
        _validate_epoch_nonempty(occasion, entries)
        occasions[occasion] = entries
    _lexicon_cache[lang] = occasions
    _themes_cache[lang] = tuple(raw.get("themes_dream", ()))
    return occasions


def themes_dream(lang: str) -> tuple[str, ...]:
    """dream_murmur 主题槽的封闭主题词表(§11.3)。"""
    if lang not in _themes_cache:
        load_lexicon(lang)
    return _themes_cache.get(lang, ())


def load_grammar(lang: str) -> dict[str, GrammarSpec]:
    """装载 lang 的全量文法;dream_murmur 的 d_theme 槽在此注入(单一事实源

    = themes_dream,不在 grammar_zh.json 里重复维护)。
    """
    if lang in _grammar_cache:
        return _grammar_cache[lang]
    path = _DATA_DIR / f"grammar_{lang}.json"
    specs: dict[str, GrammarSpec] = {}
    if path.is_file():
        raw = json.loads(path.read_text(encoding="utf-8"))
        for occasion, block in raw.get("occasions", {}).items():
            slots = {k: tuple(v) for k, v in block.get("slots", {}).items()}
            patterns = tuple(tuple(p) for p in block.get("patterns", []))
            if occasion == "dream_murmur":
                patterns = tuple(
                    tuple("d_theme" if s == "d_theme" else s for s in p)
                    for p in patterns
                )
                slots = dict(slots)
                slots["d_theme"] = themes_dream(lang)
            specs[occasion] = GrammarSpec(
                occasion=occasion,
                patterns=patterns,
                slots=slots,
                max_len=int(block.get("max_len", 24)),
            )
    _grammar_cache[lang] = specs
    return specs


def grammar_spec(occasion: str, lang: str) -> GrammarSpec | None:
    return load_grammar(lang).get(occasion)


def query(
    occasion: str, lang: str, epoch: int, *, profile: str = "expanded"
) -> tuple[str, ...]:
    """按 (occasion, lang, epoch) 过滤后、按 register 序排列的文本池。

    v01 profile 直读 core.LEXICON(不做 epoch 过滤,v0.1 无该概念)。
    """
    if profile == "v01":
        return CORE_LEXICON.get(occasion, ())
    entries = load_lexicon(lang).get(occasion, ())
    filtered = tuple(e.text for e in entries if e.epoch_min <= epoch <= e.epoch_max)
    return filtered if filtered else CORE_LEXICON.get(occasion, (FALLBACK_TEXT,))


def base_pool(occasion: str, lang: str = "zh") -> tuple[str, ...]:
    """occasion 的完整有序词句池(不做 epoch 过滤,register 序排列)。

    是 pool_snapshot(p) 纯函数(接缝 X5)的数据源:她一生的词汇年轮
    要看的是"这个场合她曾经会说的全部话",不是当下纪元的子集。
    """
    entries = load_lexicon(lang).get(occasion)
    if entries:
        return tuple(e.text for e in entries)
    return CORE_LEXICON.get(occasion, ())


def all_base_pools(lang: str = "zh") -> dict[str, tuple[str, ...]]:
    """全部 10 场合的 base_pool,供 pool_snapshot(p) 一次性取用。"""
    return {occasion: base_pool(occasion, lang) for occasion in CORE_LEXICON}


__all__ = [
    "LexEntry",
    "GrammarSpec",
    "LexiconLoadError",
    "FALLBACK_TEXT",
    "REVIEWED_LEXICON_LANGS",
    "load_lexicon",
    "themes_dream",
    "load_grammar",
    "grammar_spec",
    "query",
    "base_pool",
    "all_base_pools",
]
