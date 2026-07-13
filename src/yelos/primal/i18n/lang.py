"""在整个架构中的位置:语言身份解析 + 审校闸(蓝图 §9/A7)。

REVIEWED_LANGS 写死于此(总纲 RE8:宁缺勿假)。en/ja 词库可入仓为草稿,
loader(lexicon/__init__.py)对非 REVIEWED 语言拒载;bind 时请求未审语言
回落 zh + warning(bind_lang_decision 返回 warning 文本供调用方记账)。

A7 一生一语:lang 于 hatch 定,该 incarnation 内不可变;换语言 = 新生。
"""

from __future__ import annotations

REVIEWED_LANGS: tuple[str, ...] = ("zh",)


def resolve_lang(requested: str | None) -> str:
    """未审语言 / 空值一律回落 zh(compose 时刻的兜底,不做告警记账;

    告警记账由 bind_lang_decision 在绑定时刻负责)。
    """
    lang = requested or "zh"
    return lang if lang in REVIEWED_LANGS else "zh"


def bind_lang_decision(
    existing_lang: str | None, requested_lang: str | None
) -> tuple[str, bool, str]:
    """纯函数,无 I/O:返回 (effective_lang, rejected, message)。

    - 已绑定 incarnation 请求换语言(existing 非 None 且请求值不同)→
      rejected=True,effective 保持 existing,message 明示"换语言=新生"。
    - 未绑定(新生/首次 bind)→ 走审校闸,未审语言回落 zh 并给出 warning。
    """
    if existing_lang is not None:
        req = requested_lang if requested_lang is not None else existing_lang
        if req != existing_lang:
            return existing_lang, True, "换语言 = 送别后新生"
        return existing_lang, False, ""
    req = requested_lang or "zh"
    resolved = resolve_lang(req)
    warn = "" if resolved == req else f"未审校语言 {req!r},回落 zh"
    return resolved, False, warn


__all__ = ["REVIEWED_LANGS", "resolve_lang", "bind_lang_decision"]
