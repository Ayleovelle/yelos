"""时钟实现(bench_BLUEPRINT §3.1 / INTEGRATION_SPEC X2)。

协议归 ``yelos.core.clock.Clock``(唯一抽象面),实现归本文件——bench
自著实质清单(bench_BLUEPRINT §1.2)明列"Clock 协议与虚拟时钟"。

``RealClock`` 是 ``session.py`` 现有五个 ``_now_ts/_day_key/
_now_local_minutes/_day_end_ts/_next_quiet_start_ts`` staticmethod
的逐字搬运(§3.2"公式原样搬进 RealClock,不改一个字"),供未来 W2 起
``SessionManager.__init__(clock: Clock | None = None)`` 注入时默认使用,
默认行为与 v0.1 逐字节一致。**本 W1 施工不改 session.py**——五幕对
session.py 的注入是另一任务的编码前置义务(见 bench_BLUEPRINT §3.2 /
INTEGRATION_SPEC §3.2),本文件先把注入目标立好。

``VirtualClock`` 是 AX-B3(时钟等价公理,bench_BLUEPRINT §2)的实现体:
内部只持一个 epoch 秒游标,``now_ts`` 恒返游标值;``local_minutes``/
``day_key``/``day_end_ts``/``next_quiet_start_ts`` 由游标纯函数导出,
与 ``RealClock`` 同一公式(把 ``datetime.now()`` 换成
``datetime.fromtimestamp(cursor)``)。游标推进方式(``advance``/
``advance_to``)不影响导出值——任意步长对同一最终时刻给出相同结果。
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

from yelos.core.clock import Clock

__all__ = ["RealClock", "VirtualClock"]


class RealClock:
    """现行为逐字下沉(bench_BLUEPRINT §3.2):公式与 v0.1 session.py 完全一致。"""

    def now_ts(self) -> float:
        return time.time()

    def day_key(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def local_minutes(self) -> int:
        now = datetime.now()
        return now.hour * 60 + now.minute

    def day_end_ts(self) -> float:
        now = datetime.now()
        start = datetime(now.year, now.month, now.day)
        return (start + timedelta(days=1)).timestamp()

    def next_quiet_start_ts(self, qstart_min: int) -> float:
        now = datetime.now()
        start = datetime(now.year, now.month, now.day) + timedelta(minutes=qstart_min)
        if start.timestamp() <= now.timestamp():
            start += timedelta(days=1)
        return start.timestamp()


class VirtualClock:
    """加速回放的地基:内部游标,``advance``/``advance_to`` 推进,零真实时间读取。

    与 ``RealClock`` 逐公式对齐(把 ``datetime.now()`` 换成
    ``datetime.fromtimestamp(self._cursor)``),满足 AX-B3:任意步长推进,
    对同一事件序列(同一组最终时刻值)给出相同的 day_key/local_minutes/
    quiet 窗判定/rollover 触发序列。
    """

    def __init__(self, start_ts: float, tz_offset_min: int = 0) -> None:
        # tz_offset_min 预留(§3.1 签名要求),W1 只支持 0(本地时区即游标时区,
        # 与 datetime.fromtimestamp 的本地解释一致);非零值在此版本原样接受但
        # 不参与换算,交由未来波次按需接线(不在此处假装支持而实际忽略静默出错——
        # 显式记录于此 docstring,红队可按行核)。
        self._cursor = float(start_ts)
        self.tz_offset_min = tz_offset_min

    # -- 推进 ---------------------------------------------------------------

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("VirtualClock.advance: seconds 不得为负")
        self._cursor += seconds

    def advance_to(self, ts: float) -> None:
        if ts < self._cursor:
            raise ValueError("VirtualClock.advance_to: 不得倒退游标")
        self._cursor = float(ts)

    # -- Clock 协议(与 RealClock 同一公式,源换成游标) -----------------------

    def now_ts(self) -> float:
        return self._cursor

    def day_key(self) -> str:
        return datetime.fromtimestamp(self._cursor).strftime("%Y-%m-%d")

    def local_minutes(self) -> int:
        now = datetime.fromtimestamp(self._cursor)
        return now.hour * 60 + now.minute

    def day_end_ts(self) -> float:
        now = datetime.fromtimestamp(self._cursor)
        start = datetime(now.year, now.month, now.day)
        return (start + timedelta(days=1)).timestamp()

    def next_quiet_start_ts(self, qstart_min: int) -> float:
        now = datetime.fromtimestamp(self._cursor)
        start = datetime(now.year, now.month, now.day) + timedelta(minutes=qstart_min)
        if start.timestamp() <= now.timestamp():
            start += timedelta(days=1)
        return start.timestamp()


# 结构自证:两实现都满足 core.clock.Clock 协议(runtime_checkable,§ax-b3 邻近)。
assert isinstance(RealClock(), Clock)
assert isinstance(VirtualClock(0.0), Clock)
