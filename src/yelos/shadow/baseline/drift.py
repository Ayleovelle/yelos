"""drift.py 在整个架构中的位置:基线漂移显式建模(蓝图 §5),喂 A5 的
σ_family 与 rhythm_break/withdrawal 检测器的偏离参照,以及可视化偏差带图。

`drift_ch = |day - month| / span_ch`;`family_dispersion` = 三窗口(day/week/
month)极差 / span_ch——都是纯算术,任一窗口缺失(None,冷启动早期)按
"跳过该项、用可用项计算"处理,全部窗口缺失时返回 0.0(诚实的零离散度,
不是虚假确定,§5 冷启动纪律)。
"""

from __future__ import annotations


def channel_drift(day: float | None, month: float | None, span: float) -> float:
    """`|day - month| / span`,任一为 None 时返回 0.0(冷启动无漂移可言)。"""
    if day is None or month is None or span <= 0:
        return 0.0
    return abs(day - month) / span


def family_dispersion(
    day: float | None, week: float | None, month: float | None, span: float
) -> float:
    """`max(day,week,month) - min(...)`,按 span 归一,钳到 `[0,1]`。

    冷启动:样本数 < 2 时无法定义离散度,诚实返回 0.0(而非编造一个非零值)。
    """
    values = [v for v in (day, week, month) if v is not None]
    if len(values) < 2 or span <= 0:
        return 0.0
    spread = (max(values) - min(values)) / span
    return max(0.0, min(1.0, spread))


__all__ = ["channel_drift", "family_dispersion"]
