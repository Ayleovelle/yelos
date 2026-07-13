"""projection/estimate.py 在整个架构中的位置:预期投影估计(finitude_BLUEPRINT §8.1,纯函数)。

全确定性(输入同 → 输出同);**模型感知**:est_spend_per_active_day 用当前 t 的模型
公式(不是全程历史均值)——直接复用模型实例的 `spend()`(用近窗事件均值构造的合成
`DayFacts`),而不是重新誊写各模型的 W/E 公式,避免"两处数学各写一遍"的漂移风险。
weibull 的 est_spend 因此天然随 t 增大(暮年估得更急,形状学的投影兑现)。

**疑义记录**:蓝图 `activity_rate` 标注域 ∈(0,1],但真实近 28 日窗口若无任何活跃日,
测得值就是 0——本实现如实反映测得值(0 属于可能取值),不为凑domain 说明伪造下限。

纪律(§8.1 尾注):不进 outbox、不进任何她的台词、不进 guidance——投影是给看的人的,
不是她的焦虑。
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import TYPE_CHECKING

from ..epochs import fixed
from ..models import build_model
from ..rites.incarnation import aging_of, expr_p
from .contracts import INFINITE_SENTINEL, ProjectionData

if TYPE_CHECKING:
    from ..ledger_ext import LifeReplay

_MIN_CALENDAR_SAMPLE_ACTIVE_DAYS = 7
_WINDOW_CALENDAR_DAYS = 28

_EPOCH_BOUNDARIES: dict[str, float] = {
    "慢下来": 0.6,
    "安静": 0.3,
    "静止前期": 0.15,
    "静止": 0.0,
}


def _window_days(as_of_day: str, span: int) -> list[str] | None:
    try:
        end = date.fromisoformat(as_of_day)
    except (TypeError, ValueError):
        return None
    return [(end - timedelta(days=i)).isoformat() for i in range(span)]


def _activity_rate(replay: "LifeReplay", as_of_day: str) -> float:
    window = _window_days(as_of_day, _WINDOW_CALENDAR_DAYS)
    if window is None:
        return 0.0
    settled_days = set(replay.hi_by_day.keys())
    hits = sum(1 for d in window if d in settled_days)
    return hits / float(_WINDOW_CALENDAR_DAYS)


def _recent_event_averages(
    replay: "LifeReplay", as_of_day: str
) -> tuple[float, float, float]:
    """近窗(与 activity_rate 同窗)hi/concern 均值 + epoch_shift 当日占比。"""
    window = _window_days(as_of_day, _WINDOW_CALENDAR_DAYS)
    if window is None or not replay.hi_by_day:
        return 0.0, 0.0, 0.0
    window_set = set(window)
    hi_values = [v for d, v in replay.hi_by_day.items() if d in window_set]
    cn_values = [v for d, v in replay.concern_by_day.items() if d in window_set]
    n = len(hi_values) or 1
    hi_avg = sum(hi_values) / n if hi_values else 0.0
    cn_avg = sum(cn_values) / (len(cn_values) or 1) if cn_values else 0.0
    epoch_days = {e.get("day") for e in replay.epoch_events}
    ep_frac = (
        sum(1 for d in window if d in epoch_days) / float(_WINDOW_CALENDAR_DAYS)
        if window
        else 0.0
    )
    return hi_avg, cn_avg, ep_frac


def _est_spend_per_active_day(
    record: dict, replay: "LifeReplay", as_of_day: str, lifespan: int
) -> float:
    if lifespan <= 0:
        return 0.0
    spec = aging_of(record)
    model, _ = build_model(spec.model, spec.params, fast=spec.fast)
    hi_avg, cn_avg, ep_frac = _recent_event_averages(replay, as_of_day)

    from ..models.protocol import DayFacts

    facts = DayFacts(
        day=as_of_day,
        was_active_day=True,
        high_intensity=round(hi_avg),
        concern_fired=round(cn_avg),
        swallowed=0,
        proactive_sent=0,
        epoch_shift_yesterday=ep_frac >= 0.5,
        active_days_settled=spec.active_days_settled,
        lifespan_active_days=lifespan,
    )
    contract_p = record.get("p", 0.0)
    if not isinstance(contract_p, (int, float)) or isinstance(contract_p, bool):
        contract_p = 0.0
    outcome = model.spend(float(contract_p), facts)
    return max(0.0, float(contract_p) - outcome.new_p)


def project(
    replay: "LifeReplay", record: dict, as_of_day: str, *, lifespan_active_days: int
) -> ProjectionData:
    """纯函数:replay + record + as_of_day + lifespan → ProjectionData。

    (蓝图 §8.1 签名 `project(replay, record, as_of_day)` 未显式列 lifespan 形参;
    lifespan 是纯函数无法从 record/replay 反推的外部量,本实现补一个 keyword-only
    `lifespan_active_days` 形参——施工期疑义记录,不改变蓝图规定的算法本体。)
    """
    lifespan = lifespan_active_days
    contract_p = record.get("p", 0.0)
    if not isinstance(contract_p, (int, float)) or isinstance(contract_p, bool):
        contract_p = 0.0
    contract_p = float(contract_p)

    p_expr = expr_p(record)
    activity_rate = _activity_rate(replay, as_of_day)
    est_spend = _est_spend_per_active_day(record, replay, as_of_day, lifespan)

    if contract_p <= 0.0:
        est_remaining_active = 0
    elif est_spend <= 0.0:
        est_remaining_active = INFINITE_SENTINEL
    else:
        est_remaining_active = math.ceil(contract_p / est_spend)

    total_active_days = replay.active_day_count
    if total_active_days < _MIN_CALENDAR_SAMPLE_ACTIVE_DAYS or activity_rate <= 0.0:
        est_remaining_calendar: int | None = None
    else:
        est_remaining_calendar = math.ceil(est_remaining_active / activity_rate)

    current_idx = fixed.epoch_index(contract_p)
    epoch_etas: dict[str, int | None] = {}
    for name in fixed.EPOCH_NAMES[current_idx + 1 :]:
        boundary = _EPOCH_BOUNDARIES.get(name)
        if boundary is None or est_spend <= 0.0:
            epoch_etas[name] = None
            continue
        remaining = contract_p - boundary
        epoch_etas[name] = math.ceil(remaining / est_spend) if remaining > 0 else 0

    return ProjectionData(
        as_of_day=as_of_day,
        p=contract_p,
        p_expr=p_expr,
        activity_rate=activity_rate,
        est_spend_per_active_day=est_spend,
        est_remaining_active_days=est_remaining_active,
        est_remaining_calendar_days=est_remaining_calendar,
        epoch_etas=epoch_etas,
        active_days_lived=replay.active_day_count,
    )


__all__ = ["project"]
