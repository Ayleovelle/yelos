"""词库加载不变式(前缀兼容/排序/epoch 过滤非空)、闭包枚举界/同源、

pool_snapshot(p) 纯函数(接缝 X5)、收缩顺序。锁 A2/A4/11.2。
"""

from __future__ import annotations

import pytest

from yelos.core.primal import LEXICON, shrink_pool
from yelos.primal import lexicon as lexicon_data
from yelos.primal import pool_snapshot
from yelos.primal.lexicon.closure import band_of, enumerate_closure


def test_expanded_lexicon_preserves_v01_prefix():
    entries_by_occ = lexicon_data.load_lexicon("zh")
    for occasion, v01_pool in LEXICON.items():
        entries = entries_by_occ[occasion]
        texts = tuple(e.text for e in entries)
        assert texts[: len(v01_pool)] == v01_pool


def test_expanded_lexicon_register_sorted_essence_first():
    entries_by_occ = lexicon_data.load_lexicon("zh")
    for occasion, entries in entries_by_occ.items():
        ranks = [{"essence": 0, "plain": 1, "vivid": 2}[e.register] for e in entries]
        assert ranks == sorted(ranks), occasion


def test_epoch_filter_nonempty_for_all_epochs():
    for occasion in LEXICON:
        for epoch in (0, 1, 2, 3, 4):
            pool = lexicon_data.query(occasion, "zh", epoch)
            assert pool, f"{occasion} epoch={epoch} 过滤后为空"


def test_all_ten_occasions_have_expanded_pools():
    entries_by_occ = lexicon_data.load_lexicon("zh")
    assert set(entries_by_occ.keys()) == set(LEXICON.keys())


# --- 闭包枚举:可枚举 + 界 + 同源(A2)-------------------------------------


def test_enumerate_closure_bounded_and_deterministic():
    for occasion in LEXICON:
        for band in ("B0", "B1", "B2", "B3", "B4"):
            canon1 = enumerate_closure(occasion, "zh", band, epoch=0)
            canon2 = enumerate_closure(occasion, "zh", band, epoch=0)
            assert canon1 == canon2  # 确定性:同源同输出
            assert len(canon1) <= 4096


def test_enumerate_closure_grows_or_stays_with_band():
    # A4/T2:band 越高(P 越高),Canon 越大或持平(收缩单调)。
    for occasion in LEXICON:
        sizes = [
            len(enumerate_closure(occasion, "zh", band, epoch=0))
            for band in ("B0", "B1", "B2", "B3", "B4")
        ]
        assert sizes == sorted(sizes)


def test_closure_max_fail_fast_on_overflow():
    with pytest.raises(ValueError):
        enumerate_closure("contact_seek", "zh", "B4", epoch=0, closure_max=1)


def test_band_of_boundaries():
    assert band_of(0.0) == "B0"
    assert band_of(0.1499) == "B0"
    assert band_of(0.15) == "B1"
    assert band_of(0.3999) == "B1"
    assert band_of(0.4) == "B2"
    assert band_of(0.5999) == "B2"
    assert band_of(0.6) == "B3"
    assert band_of(0.7999) == "B3"
    assert band_of(0.8) == "B4"
    assert band_of(1.0) == "B4"


# --- shrink 顺序(尾部先忘,复用 core 公式)--------------------------------


def test_expanded_pool_shrinks_as_prefix():
    pool = lexicon_data.base_pool("express_warm", "zh")
    shrunk_full = shrink_pool(pool, 1.0)
    shrunk_low = shrink_pool(pool, 0.15)
    assert pool[: len(shrunk_low)] == shrunk_low
    assert len(shrunk_full) >= len(shrunk_low)


# --- pool_snapshot(p) 纯函数(接缝 X5,务必落地)---------------------------


def test_pool_snapshot_pure_function_shape():
    snap = pool_snapshot(1.0)
    assert set(snap.keys()) == set(LEXICON.keys())
    for occasion, pool in snap.items():
        assert isinstance(pool, tuple)
        assert all(isinstance(s, str) for s in pool)


def test_pool_snapshot_deterministic_same_p_same_output():
    a = pool_snapshot(0.42)
    b = pool_snapshot(0.42)
    assert a == b


def test_pool_snapshot_shrinks_with_p():
    high = pool_snapshot(1.0)
    low = pool_snapshot(0.0)
    for occasion in LEXICON:
        assert len(low[occasion]) <= len(high[occasion])
        assert len(low[occasion]) == 1


def test_pool_snapshot_matches_shrink_pool_of_base_pools():
    for p in (0.0, 0.2, 0.5, 0.9, 1.0):
        snap = pool_snapshot(p)
        for occasion in LEXICON:
            expected = shrink_pool(lexicon_data.base_pool(occasion, "zh"), p)
            assert snap[occasion] == expected


def test_pool_snapshot_takes_only_p_no_hidden_state():
    import inspect

    sig = inspect.signature(pool_snapshot)
    assert list(sig.parameters.keys()) == ["p"]
