"""tokenizer.py 在架构中的位置。

零依赖三语分词(memory_BLUEPRINT §3.2.1):zh = 字符 bigram + 连续 ASCII
词;en = 小写词 + porter-lite 后缀剥离(自著 ~40 行);ja = 字符 bigram。
停用表三语自著,随仓库(memory/data/stopwords_{zh,en,ja}.txt)。

确定性:无 locale 依赖 API(不用 str.casefold 的 locale 变体、不用 re 的
UNICODE 之外任何依赖平台的行为);同输入同 lang → 逐位同输出(golden 锁)。
"""

from __future__ import annotations

import re
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_VALID_LANGS = ("zh", "en", "ja")

_ASCII_ALNUM_RE = re.compile(r"[A-Za-z0-9]+")
_EN_WORD_RE = re.compile(r"[A-Za-z']+")


def _load_stopwords(lang: str) -> frozenset[str]:
    path = _DATA_DIR / f"stopwords_{lang}.txt"
    if not path.is_file():
        return frozenset()
    words: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        words.add(line)
    return frozenset(words)


_STOPWORDS: dict[str, frozenset[str]] = {
    lang: _load_stopwords(lang) for lang in _VALID_LANGS
}


def _is_cjk_ish(ch: str) -> bool:
    """CJK 统一表意文字 + 平假名/片假名(zh/ja 字符 bigram 的取字范围)。"""
    cp = ord(ch)
    return (
        0x4E00 <= cp <= 0x9FFF
        or 0x3400 <= cp <= 0x4DBF
        or 0x3040 <= cp <= 0x30FF
        or 0xF900 <= cp <= 0xFAFF
    )


def _char_bigrams(s: str) -> list[str]:
    if len(s) <= 1:
        return [s] if s else []
    return [s[i : i + 2] for i in range(len(s) - 1)]


# porter-lite:自著后缀剥离表,长后缀优先(避免短后缀提前吃掉更具体的后缀)。
_SUFFIX_RULES: tuple[tuple[str, str], ...] = (
    ("ational", "ate"),
    ("tional", "tion"),
    ("ization", "ize"),
    ("fulness", "ful"),
    ("ousness", "ous"),
    ("iveness", "ive"),
    ("edness", ""),
    ("ingly", ""),
    ("ities", "ity"),
    ("edly", ""),
    ("ment", ""),
    ("ness", ""),
    ("able", ""),
    ("ible", ""),
    ("ing", ""),
    ("ies", "y"),
    ("ed", ""),
    ("ly", ""),
    ("es", ""),
    ("s", ""),
)


def _porter_lite(word: str) -> str:
    """~20 条自著后缀剥离规则,保底词干长度 >= 3,避免过度剥离成空干。"""
    for suf, rep in _SUFFIX_RULES:
        if word.endswith(suf):
            stem_len = len(word) - len(suf)
            if stem_len + len(rep) >= 3:
                return word[:stem_len] + rep
    return word


def tokenize(text: str, lang: str = "zh") -> list[str]:
    """三语确定性分词;lang 非法回退 zh(保守默认)。"""
    if lang not in _VALID_LANGS:
        lang = "zh"
    if not text:
        return []
    stop = _STOPWORDS.get(lang, frozenset())

    if lang == "en":
        tokens: list[str] = []
        for m in _EN_WORD_RE.finditer(text):
            w = m.group(0).lower().strip("'")
            if not w or w in stop:
                continue
            tokens.append(_porter_lite(w))
        return tokens

    # zh / ja:字符 bigram(仅 CJK/假名连续段)+ 连续 ASCII 词。
    tokens = []
    buf: list[str] = []

    def flush() -> None:
        if not buf:
            return
        s = "".join(buf)
        for bg in _char_bigrams(s):
            if bg and bg not in stop:
                tokens.append(bg)
        buf.clear()

    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isascii() and (ch.isalnum()):
            flush()
            j = i
            while j < n and text[j].isascii() and text[j].isalnum():
                j += 1
            w = text[i:j].lower()
            if w and w not in stop:
                tokens.append(w)
            i = j
            continue
        if _is_cjk_ish(ch):
            buf.append(ch)
            i += 1
            continue
        flush()
        i += 1
    flush()
    return tokens
