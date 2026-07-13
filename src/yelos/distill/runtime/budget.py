"""在整个架构中的位置:推理超时预算(蓝图 §3.1;DA2 R4 行的判定点)。

时钟复用 ``yelos.core.clock.Clock``(``core.RealClock``/``bench.VirtualClock``
均满足该协议),本文件不重定义时钟、不 ``time.time()``——elapsed 由调用方
注入的时钟前后两次 ``now_ts()`` 差值算出。测试用假时钟推进游标模拟耗时,
不真睡(bench_BLUEPRINT AX-B3 的消费者)。
"""

from __future__ import annotations

from typing import Callable, TypeVar

from yelos.core.clock import Clock

T = TypeVar("T")


class BudgetExceeded(Exception):
    """推理耗时超过预算;调用方(provider.utter_canonical)据此判 R4 超时。"""


def run_with_budget(
    fn: Callable[[], T], clock: Clock, budget_ms: int
) -> tuple[T, float]:
    """执行 ``fn()``,超预算抛 ``BudgetExceeded``;否则返回 (结果, 耗时ms)。

    后验式判定(非抢占式):同步 stdlib 无法安全抢占任意函数,与
    ``VirtualClock`` 的"假时钟不真睡"惯例一致——测试里 stub 后端可在
    ``fn`` 内部主动推进假时钟游标以模拟耗时,此处据前后差值裁决。
    """
    start = clock.now_ts()
    result = fn()
    elapsed_ms = (clock.now_ts() - start) * 1000.0
    if elapsed_ms > budget_ms:
        raise BudgetExceeded(f"推理耗时 {elapsed_ms:.1f}ms 超预算 {budget_ms}ms")
    return result, elapsed_ms


__all__ = ["BudgetExceeded", "run_with_budget"]
