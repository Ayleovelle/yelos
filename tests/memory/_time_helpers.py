"""tests/memory 共享的 day_key<->ts 一致换算小工具(非 conftest,普通模块)。

事件的 ts 与 day_key 必须一致(否则 baseline/continuity 的日历算术会算出
荒谬的"距上次联系天数")——本文件把换算集中一处,所有测试文件复用。
不叫 conftest.py,避免与顶层 tests/conftest.py 模块名冲突。
"""

from __future__ import annotations

from datetime import date, timedelta

_EPOCH_ORDINAL = date(1970, 1, 1).toordinal()
BASE_DAY = "2024-01-01"


def day_key_for_index(i: int, start: str = BASE_DAY) -> str:
    d = date.fromisoformat(start) + timedelta(days=i)
    return d.isoformat()


def day_key_to_ts(day_key: str, hour: float = 12.0) -> float:
    d = date.fromisoformat(day_key)
    return float((d.toordinal() - _EPOCH_ORDINAL) * 86400 + hour * 3600)


def ts_for_index(i: int, hour: float = 12.0, start: str = BASE_DAY) -> float:
    return day_key_to_ts(day_key_for_index(i, start=start), hour=hour)
