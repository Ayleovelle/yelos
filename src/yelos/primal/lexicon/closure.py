"""在整个架构中的位置:A2 可枚举性的唯一事实源(蓝图 §1.2/§4.2)。

enumerate_closure 把"给定 (occasion, lang, band, epoch) 时全部可采纳的
canonical 文本"机械展开为一个 frozenset;whitelist_gate 的 Tier-S 查表
与本函数同源(gate 永远调用它,不自己另算)。

band → 代表性 p:用 band 的上界(BAND_UPPER)。shrink_pool 对 p 单调不减,
band 内任意实际 p 都 <= 上界,所以以上界展开出的 Canon 是该 band 内任何
实际收缩结果的超集——T1/T2 的"经闸仍单调"证明梗概即建立在此单调包含
关系上。
"""

from __future__ import annotations

import itertools

from yelos.core.primal import shrink_pool

from . import grammar_spec, query

BAND_UPPER: dict[str, float] = {
    "B0": 0.15,
    "B1": 0.4,
    "B2": 0.6,
    "B3": 0.8,
    "B4": 1.0,
}
BAND_ORDER: tuple[str, ...] = ("B0", "B1", "B2", "B3", "B4")

DEFAULT_CLOSURE_MAX = 4096


def band_of(p: float) -> str:
    """P 带离散化(蓝图 §1.1,边界固定,不入配置)。"""
    if p < 0.15:
        return "B0"
    if p < 0.4:
        return "B1"
    if p < 0.6:
        return "B2"
    if p < 0.8:
        return "B3"
    return "B4"


def _expand_grammar(spec, p_repr: float) -> set[str]:
    results: set[str] = set()
    for pattern in spec.patterns:
        slot_pools = []
        ok = True
        for slot_id in pattern:
            pool = spec.slots.get(slot_id, ())
            shrunk = shrink_pool(pool, p_repr) if pool else ()
            if not shrunk:
                ok = False
                break
            slot_pools.append(shrunk)
        if not ok:
            continue
        for combo in itertools.product(*slot_pools):
            text = "".join(combo)
            if text and len(text) <= spec.max_len:
                results.add(text)
    return results


def enumerate_closure(
    occasion: str,
    lang: str,
    band: str,
    epoch: int,
    *,
    profile: str = "expanded",
    closure_max: int = DEFAULT_CLOSURE_MAX,
) -> frozenset[str]:
    """A2 唯一事实源:机械枚举 (occasion,lang,band,epoch) 的 Canon。

    超限(词库/文法组合数 > closure_max)在此 raise——词库作者的错误
    在装配期暴露,不在运行时暴露(§4.2)。
    """
    p_repr = BAND_UPPER[band]
    lex_pool = query(occasion, lang, epoch, profile=profile)
    canon: set[str] = set(shrink_pool(lex_pool, p_repr))
    if profile != "v01":
        spec = grammar_spec(occasion, lang)
        if spec is not None:
            combos = _expand_grammar(spec, p_repr)
            if len(combos) > closure_max:
                raise ValueError(
                    f"closure too large for occasion={occasion!r}: "
                    f"{len(combos)} > closure_max={closure_max}"
                )
            canon.update(combos)
    return frozenset(canon)


__all__ = [
    "band_of",
    "enumerate_closure",
    "BAND_UPPER",
    "BAND_ORDER",
    "DEFAULT_CLOSURE_MAX",
]
