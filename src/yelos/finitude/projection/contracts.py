"""projection/contracts.py 在整个架构中的位置:ProjectionData schema(finitude_BLUEPRINT §8.1,成文数据契约)。

只放形状,不放算法(算法在 estimate.py)。JSON 导出用于 anthology 数据附录 + WebUI
契约(第 N 个消费者,不是唯一)。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

# lifespan<=0(不老化)时 est_remaining_active_days 的"实质无穷"哨兵(estimate.py 复用,
# viz/hourglass.py 据此渲染"未可知"记号,而不是画一根巨长的沙柱)。
INFINITE_SENTINEL = 10**9


@dataclass(frozen=True)
class ProjectionData:
    as_of_day: str
    p: float  # 契约 P
    p_expr: float
    activity_rate: float  # 近 28 自然日窗口内活跃日占比,实测值(见 estimate.py 头注疑义)
    est_spend_per_active_day: float
    est_remaining_active_days: int  # P==0 -> 0;lifespan<=0(不老化)-> INFINITE_SENTINEL
    est_remaining_calendar_days: (
        int | None
    )  # 样本不足(<7 活跃日)或 activity_rate<=0 -> None
    epoch_etas: dict[str, int | None]
    active_days_lived: int = (
        0  # 蓝图 §8.1 字段表未列此键;hourglass 渲染"下腔已活活跃日"
    )
    # 离不开这个量,施工期补一个非破坏性增量字段(仅追加,不改动既列字段语义,§7.3 疑义记录)。

    def to_json(self) -> dict:
        return asdict(self)


__all__ = ["ProjectionData", "INFINITE_SENTINEL"]
