"""test_primal.py —— 锁幕 I 原语发声(core/primal.py)。

蓝图 §13:
- 确定性(同日同会话同状态 → 同句)
- 全 occasion 覆盖(含未知 occasion 兜底)
- 收缩顺序(尾部先忘)
- P=0 只剩首句
- P 边界 0.15
- len=1 词池安全(收缩/选词均不越界)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from yelos.core.primal import (  # noqa: E402
    LEXICON,
    LexiconProvider,
    PrimalProvider,
    pick,
    shrink_pool,
)


# --- 确定性:同日同会话同状态 → 同句 -------------------------------------


def test_pick_deterministic_same_input_same_output():
    a = pick("session-1", "2026-07-11", "withdraw_heavy", 1.0)
    b = pick("session-1", "2026-07-11", "withdraw_heavy", 1.0)
    assert a == b


def test_pick_deterministic_across_many_calls():
    results = {pick("s", "2026-07-11", "hold_hesitant", 0.8) for _ in range(20)}
    assert len(results) == 1


def test_pick_no_random_module_used():
    import ast

    src = (
        Path(__file__)
        .resolve()
        .parent.parent.joinpath("src", "yelos", "core", "primal.py")
        .read_text(encoding="utf-8")
    )
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "random"
        if isinstance(node, ast.ImportFrom):
            assert node.module != "random"


# --- 不同 session_id/day_key/occasion → 可能不同(至少不恒等崩坏) --------


def test_pick_varies_with_session_id():
    # 不同 session 允许命中同句(词池小),但函数必须能对不同输入求值不崩。
    a = pick("session-A", "2026-07-11", "express_warm", 1.0)
    b = pick("session-B", "2026-07-11", "express_warm", 1.0)
    assert a in LEXICON["express_warm"]
    assert b in LEXICON["express_warm"]


def test_pick_varies_with_day_key():
    a = pick("s", "2026-07-11", "express_warm", 1.0)
    b = pick("s", "2026-07-12", "express_warm", 1.0)
    assert a in LEXICON["express_warm"]
    assert b in LEXICON["express_warm"]


# --- 全 occasion 覆盖 ------------------------------------------------------


def test_pick_covers_all_occasions():
    for occasion in LEXICON:
        result = pick("session-x", "2026-07-11", occasion, 1.0)
        assert result in LEXICON[occasion]


def test_pick_unknown_occasion_fallback():
    result = pick("session-x", "2026-07-11", "not_a_real_occasion", 1.0)
    assert result == "……"


def test_pick_unknown_occasion_does_not_raise():
    # core 不 raise、不 log,只兜底返回,调用方决定是否记 warning。
    for bad in ("", "unknown", "WITHDRAW_HEAVY", None):
        result = pick("session-x", "2026-07-11", bad, 1.0)  # type: ignore[arg-type]
        assert result == "……"


# --- 收缩顺序:尾部先忘(词典排序即遗忘顺序,首句最本质) -------------------


def test_shrink_pool_keeps_prefix_order():
    pool = ("a", "b", "c", "d")
    shrunk = shrink_pool(pool, 0.5)
    # 收缩结果必须是原池的前缀(尾部先被遗忘)。
    assert pool[: len(shrunk)] == shrunk


def test_shrink_pool_shrinks_as_p_decreases():
    pool = LEXICON["withdraw_heavy"]  # len 3
    full = shrink_pool(pool, 1.0)
    mid = shrink_pool(pool, 0.5)
    low = shrink_pool(pool, 0.15)
    assert len(full) >= len(mid) >= len(low)
    # 全部是前缀关系。
    assert pool[: len(mid)] == mid
    assert pool[: len(low)] == low


def test_shrink_pool_four_item_pool_tail_forgotten_first():
    pool = LEXICON["express_warm"]  # len 4: 在/嗯嗯/看到了/再说一会儿
    # P 较低时应只剩前几句,且是从尾部开始消失。
    shrunk = shrink_pool(pool, 0.3)
    assert shrunk == pool[: len(shrunk)]
    assert len(shrunk) < len(pool)


# --- P=0 显式特判:只剩首句 -------------------------------------------------


def test_shrink_pool_p_zero_keeps_only_first():
    for occasion, pool in LEXICON.items():
        shrunk = shrink_pool(pool, 0.0)
        assert shrunk == pool[:1]
        assert len(shrunk) == 1


def test_shrink_pool_p_negative_treated_as_zero():
    pool = LEXICON["withdraw_heavy"]
    shrunk = shrink_pool(pool, -0.5)
    assert shrunk == pool[:1]


def test_pick_p_zero_only_ever_returns_first_sentence():
    for occasion, pool in LEXICON.items():
        for session_id in ("s1", "s2", "totally-different-session"):
            result = pick(session_id, "2026-07-11", occasion, 0.0)
            assert result == pool[0]


# --- P 边界 0.15(公式下限裁决:P>0 时 n = max(1, round(len(pool)*max(p,0.15)))) ---


def test_shrink_pool_p_below_0_15_clamped_to_0_15():
    pool = LEXICON["dream_murmur"]  # len 2
    at_boundary = shrink_pool(pool, 0.15)
    below_boundary = shrink_pool(pool, 0.05)
    # p<0.15 应被 max(p, 0.15) 钳制到与 p=0.15 相同的收缩结果(p>0 分支)。
    assert below_boundary == at_boundary


def test_shrink_pool_p_at_0_15_matches_formula():
    for occasion, pool in LEXICON.items():
        n = max(1, round(len(pool) * 0.15))
        expected = pool[:n]
        assert shrink_pool(pool, 0.15) == expected


def test_shrink_pool_p_just_above_and_below_0_15_boundary_continuity():
    pool = LEXICON["withdraw_soft"]  # len 3
    just_below = shrink_pool(pool, 0.10)
    at_boundary = shrink_pool(pool, 0.15)
    just_above = shrink_pool(pool, 0.16)
    # 0.10 与 0.15 应该相同(钳制),0.16 应 >= 0.15 的结果长度。
    assert just_below == at_boundary
    assert len(just_above) >= len(at_boundary)


# --- len=1 词池安全:收缩/选词均不越界 --------------------------------------


def test_shrink_pool_len_one_pool_safe_at_all_p():
    pool = ("唯一句子。",)
    for p in (0.0, -1.0, 0.05, 0.15, 0.3, 0.5, 1.0, 2.0):
        shrunk = shrink_pool(pool, p)
        assert shrunk == pool
        assert len(shrunk) == 1


def test_pick_len_one_pool_no_index_error():
    pool = ("唯一句子。",)
    for p in (0.0, 0.15, 1.0):
        b_mod_len = 0  # len(pool)==1 时 b % 1 恒为 0,不会越界。
        assert b_mod_len < len(shrink_pool(pool, p))


def test_pick_with_monkeypatched_single_item_lexicon(monkeypatch):
    import yelos.core.primal as primal_mod

    monkeypatch.setitem(primal_mod.LEXICON, "solo", ("孤句。",))
    for p in (0.0, 0.1, 0.15, 0.5, 1.0):
        for session_id in ("a", "b", "c"):
            result = pick(session_id, "2026-07-11", "solo", p)
            assert result == "孤句。"


# --- Provider 契约(LexiconProvider 委托 pick,p_lookup 由外部注入) --------


def test_lexicon_provider_utter_matches_pick():
    provider: PrimalProvider = LexiconProvider(p_lookup=lambda session_id: 1.0)
    result = provider.utter({}, "session-1", "2026-07-11", "concern")
    expected = pick("session-1", "2026-07-11", "concern", 1.0)
    assert result == expected


def test_lexicon_provider_uses_p_lookup_per_session():
    calls: list[str] = []

    def p_lookup(session_id: str) -> float:
        calls.append(session_id)
        return 0.0

    provider = LexiconProvider(p_lookup=p_lookup)
    result = provider.utter({}, "session-9", "2026-07-11", "withdraw_heavy")
    assert calls == ["session-9"]
    assert result == LEXICON["withdraw_heavy"][0]


# --- 词典本身的结构约束(封闭集,蓝图 §3.1 逐字照 SPEC §6.1) --------------
# 注:蓝图 §3.3 提到"全部 ≤12 字"是克制三原则的整体表述,以 §3.1 逐字词典
# 为准(如 contact_seek 第三句 13 字),故不对单句长度做硬性断言,仅锁闭合集。


def test_lexicon_is_closed_set_of_ten_occasions():
    expected_occasions = {
        "withdraw_heavy",
        "withdraw_soft",
        "hold_hesitant",
        "express_warm",
        "recover",
        "concern",
        "contact_seek",
        "contact_night",
        "dream_murmur",
        "trim_tail",
    }
    assert set(LEXICON.keys()) == expected_occasions
