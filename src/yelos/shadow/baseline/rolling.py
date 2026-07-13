"""rolling.py 在整个架构中的位置:三窗口滚动分位数基线族的数值内核(蓝图
§5)。状态全存 `shadow.baselines.<ch>`(见 `..binding_v2._new_baseline_channel`
的字段形状),重启无损。

day 窗:EWMA 近似中位数,日翻转重置;首拍单点 = legacy 成员(v0.1 兼容路径,
`day_ticks <= 3` 内退化为 legacy 首拍值)。

week/month 窗:固定 8 桶计数的分位 sketch——每次日翻转(`rollover_day`)把
"昨日最终 day 估计值"计入桶,旧计数按窗口长度做指数衰减(近似矩形窗;零
依赖、有界存储、确定性)。分位数取桶上累积权重过半处插值。

`CHANNEL_SPAN` 是每个通道的值域宽度(用于 §4.3/§5 公式里的 `span_ch` 归一
除数与桶边界):pressure/warmth/damage 是引擎 Surface 通道,天然值域
`[0,1]`;rhythm 是交互间隔秒数,值域取 `[0, 86400]`(一天);msg_len/
interactions 是活动量通道,值域按经验上限取(超出上限截断,不影响相对排序)。
"""

from __future__ import annotations

from typing import Any

from ..contracts import BaselineView
from .drift import family_dispersion

_BUCKETS = 8
_DAY_EWMA_ALPHA = 0.3

CHANNEL_SPAN: dict[str, float] = {
    "pressure": 1.0,
    "warmth": 1.0,
    "damage": 1.0,
    "rhythm": 86400.0,  # 交互间隔秒数,一天封顶
    "msg_len": 500.0,  # 消息长度(字符数)经验上限
    "interactions": 20.0,  # 单日互动次数经验上限
}


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _bucket_index(value: float, span: float) -> int:
    v = _clamp(value, 0.0, span)
    idx = int(v / span * _BUCKETS) if span > 0 else 0
    return min(idx, _BUCKETS - 1)


def _bucket_midpoint(idx: int, span: float) -> float:
    width = span / _BUCKETS
    return (idx + 0.5) * width


def _decayed_push(
    bins: list[float], active_days: int, window: int, value: float, span: float
) -> None:
    """把一个"日代表值"计入桶:旧权重按窗口衰减,新值加权重 1(原地改 bins)。"""
    decay = (window - 1) / window if window > 1 else 0.0
    for i in range(len(bins)):
        bins[i] *= decay
    bins[_bucket_index(value, span)] += 1.0


def _quantile_from_bins(bins: list[float], span: float, q: float = 0.5) -> float | None:
    total = sum(bins)
    if total <= 0:
        return None
    target = total * q
    acc = 0.0
    for idx, w in enumerate(bins):
        acc += w
        if acc >= target:
            return _bucket_midpoint(idx, span)
    return _bucket_midpoint(_BUCKETS - 1, span)


def observe_tick(
    channel_state: dict[str, Any], value: float, *, alpha: float = _DAY_EWMA_ALPHA
) -> None:
    """同一天内的一拍观测:更新 EWMA 均值/方差与 day 估计(原地改
    `channel_state`)。调用前应已经过 `rollover_day`(若跨日)。
    """
    prev_mean = channel_state.get("ewma_mean")
    prev_var = float(channel_state.get("ewma_var", 0.0) or 0.0)
    if prev_mean is None:
        new_mean, new_var = value, 0.0
    else:
        delta = value - prev_mean
        new_mean = prev_mean + alpha * delta
        new_var = (1 - alpha) * (prev_var + alpha * delta * delta)
    channel_state["ewma_mean"] = new_mean
    channel_state["ewma_var"] = new_var

    ticks = int(channel_state.get("day_ticks", 0)) + 1
    channel_state["day_ticks"] = ticks
    if ticks == 1:
        channel_state["_legacy_anchor"] = value  # 首拍单点(legacy 兼容路径)
    if ticks <= 3:
        channel_state["day"] = channel_state.get("_legacy_anchor", value)
    else:
        channel_state["day"] = new_mean


def rollover_day(channel_state: dict[str, Any], day_key: str, ch: str) -> None:
    """日翻转:把昨日最终 day 估计计入 week/month 桶,重置 day 级累积。

    幂等按 day_key 判断(同 day_key 重复调用不重复计入)。
    """
    span = CHANNEL_SPAN.get(ch, 1.0)
    last_day_val = channel_state.get("day")
    if channel_state.get("week_last_day") != day_key and last_day_val is not None:
        bins_w = channel_state.setdefault("week_bins", [0.0] * _BUCKETS)
        _decayed_push(
            bins_w, int(channel_state.get("week_active_days", 0)), 7, last_day_val, span
        )
        channel_state["week_active_days"] = min(
            int(channel_state.get("week_active_days", 0)) + 1, 7
        )
        channel_state["week"] = _quantile_from_bins(bins_w, span)

        bins_m = channel_state.setdefault("month_bins", [0.0] * _BUCKETS)
        _decayed_push(
            bins_m,
            int(channel_state.get("month_active_days", 0)),
            30,
            last_day_val,
            span,
        )
        channel_state["month_active_days"] = min(
            int(channel_state.get("month_active_days", 0)) + 1, 30
        )
        channel_state["month"] = _quantile_from_bins(bins_m, span)

    channel_state["week_last_day"] = day_key
    channel_state["month_last_day"] = day_key
    channel_state["day_ticks"] = 0
    channel_state["ewma_mean"] = None
    channel_state["ewma_var"] = 0.0
    channel_state["_legacy_anchor"] = None
    channel_state["day"] = None


def get_baseline_view(channel_state: dict[str, Any], ch: str) -> BaselineView:
    """把 channel_state 折成只读的 `BaselineView`(消费面接口)。"""
    span = CHANNEL_SPAN.get(ch, 1.0)
    day = channel_state.get("day")
    week = channel_state.get("week")
    month = channel_state.get("month")
    dispersion = family_dispersion(day, week, month, span)
    return BaselineView(day=day, week=week, month=month, dispersion=dispersion)


__all__ = [
    "CHANNEL_SPAN",
    "observe_tick",
    "rollover_day",
    "get_baseline_view",
]
