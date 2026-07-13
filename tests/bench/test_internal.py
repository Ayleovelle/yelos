"""aux 辅助观测(bench_BLUEPRINT §6 表 internal.py)——维四差分测试。

节律熵双实现(滑窗直方图熵 / 谱平坦度法)在合成基准信号上必须序数一致
(``test_entropy_differential``,§6 表"此为维四差分测试,明示不计维二")。
"""

from __future__ import annotations

import hashlib

from yelos.bench.metrics.internal import (
    evaluate_aux,
    rhythm_entropy_spectral,
    rhythm_entropy_window,
)


def _h(seed: str, i: int, mod: int) -> int:
    """哈希驱动的确定性抖动(零 random,与 bench 全仓纪律一致)。"""
    return (
        hashlib.blake2b(f"{seed}|{i}".encode("utf-8"), digest_size=2).digest()[0] % mod
    )


def _gen(
    seed: str, buckets: tuple[int, ...], base_n: int, n_days: int = 10
) -> list[int]:
    """跨 ``n_days`` 天在给定桶集合里哈希驱动撒点(带抖动,避免完美对称退化)。

    刻意避免"事件全部落在单一一个桶"的数学退化态:单桶(only-one-nonzero-bin)
    序列的离散傅里叶变换必然是精确平坦谱(Fourier 对偶的数学事实),会让
    谱法与直方图法在这个极端处反直觉地同时给出"高熵",不是实现 bug,而是
    该指标本身在完全退化输入下的已知局限——差分测试改用"集中在少数几个
    桶但非单桶"的合成信号,更贴近真实 trace 的节律形态。
    """
    out: list[int] = []
    for day in range(n_days):
        for b in buckets:
            n = base_n + _h(f"{seed}{day}", b, base_n)
            for k in range(n):
                out.append((day * 1440 + b * 60 + _h(f"{seed}{day}{b}", k, 60)) % 1440)
    return out


def _spread_signal() -> list[int]:
    return _gen("u", tuple(range(24)), base_n=3)


def _mild_signal() -> list[int]:
    return _gen("m", (1, 4, 8, 12, 16, 20, 22), base_n=5)


def _narrow_signal() -> list[int]:
    return _gen("n", (8, 9, 10, 11), base_n=12)


def test_entropy_differential_ordinal_agreement_across_concentration_levels():
    """三档"越集中→熵越低"的合成信号,两套实现必须给出相同的序数排序。"""
    spread = _spread_signal()
    mild = _mild_signal()
    narrow = _narrow_signal()

    win_scores = [rhythm_entropy_window(s) for s in (spread, mild, narrow)]
    spec_scores = [rhythm_entropy_spectral(s) for s in (spread, mild, narrow)]

    # 越均匀熵越高:spread > mild > narrow,两套实现同序。
    assert win_scores[0] > win_scores[1] > win_scores[2]
    assert spec_scores[0] > spec_scores[1] > spec_scores[2]


def test_entropy_window_empty_signal_is_zero():
    assert rhythm_entropy_window([]) == 0.0
    assert rhythm_entropy_spectral([]) == 0.0


def test_evaluate_aux_poll_coverage_and_outbox_drop_rate():
    rows = [
        {"kind": "user_msg", "vts": 0, "persist": {"outbox": 0}},
        {"kind": "impulse_poll", "vts": 60, "persist": {"outbox": 2}},
        {"kind": "user_msg", "vts": 120, "persist": {"outbox": 3}},
        {"kind": "impulse_poll", "vts": 180, "persist": {"outbox": 1}},
    ]
    aux = evaluate_aux(rows)
    assert aux["poll_coverage"] == 1.0  # 2 poll / 2 user_msg
    assert aux["outbox_drop_rate"] == (3 - 1) / 3
    assert "rhythm_entropy_win" in aux
    assert "rhythm_entropy_spec" in aux


def test_evaluate_aux_handles_no_user_msg_rows():
    rows = [{"kind": "tick", "vts": 0, "persist": {"outbox": 0}}]
    aux = evaluate_aux(rows)
    assert aux["poll_coverage"] is None
