"""brier.py 在整个架构中的位置:Brier 分 + 可靠性分箱计算(蓝图 §7.3),
纯数值函数,零 I/O——输入是已经从账本读出的 `(q,y)` 行列表(ledger.py 的
职责),本文件只算数。
"""

from __future__ import annotations

_N_BINS = 5


def compute_brier(
    rows: list[dict],
) -> tuple[float | None, int, tuple[tuple[float, float, int], ...]]:
    """`B = mean((q-y)^2)`;`rows` 为空返回 `(None, 0, ())`(冷启动,诚实缺席)。"""
    n = len(rows)
    if n == 0:
        return None, 0, ()
    brier = sum((float(r["q"]) - float(r["y"])) ** 2 for r in rows) / n
    bins = reliability_bins(rows)
    return brier, n, bins


def reliability_bins(
    rows: list[dict], n_bins: int = _N_BINS
) -> tuple[tuple[float, float, int], ...]:
    """可靠性分箱:按 `q` 等宽分桶,每桶 `(桶中心, 实际频率, 计数)`。空桶不产行。"""
    buckets: list[list[int]] = [[] for _ in range(n_bins)]
    for r in rows:
        q = max(0.0, min(1.0, float(r["q"])))
        idx = min(int(q * n_bins), n_bins - 1)
        buckets[idx].append(int(r["y"]))
    out: list[tuple[float, float, int]] = []
    for i, bucket in enumerate(buckets):
        if not bucket:
            continue
        center = (i + 0.5) / n_bins
        freq = sum(bucket) / len(bucket)
        out.append((center, freq, len(bucket)))
    return tuple(out)


__all__ = ["compute_brier", "reliability_bins"]
