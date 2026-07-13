"""在整个架构中的位置:纪元固化(蓝图 §8.2)——年轻多变,年老口头禅化。

epoch 0-1:全池;epoch 2:收缩至前 2(靠 essence 端);epoch 3+:单例固化
(该 incarnation 的口头禅粒子,由 morph_seed 键一次性选定,终生不再变)。
固化 = 收缩代数的极限点,与 A4 同构,不是新机制。
"""

from __future__ import annotations

from .. import determinism


def epoch_pool(
    base_pool: tuple[str, ...], epoch: int, sid: str, incarnation: int
) -> tuple[str, ...]:
    if not base_pool:
        return ()
    if epoch <= 1:
        return base_pool
    if epoch == 2:
        n = max(1, min(2, len(base_pool)))
        return base_pool[:n]
    # epoch >= 3:单例固化,一生一份(morph_seed 键,§10 登记)。
    key = f"{sid}|{incarnation}|morph_seed"
    idx = determinism.h_byte(key) % len(base_pool)
    return (base_pool[idx],)


__all__ = ["epoch_pool"]
