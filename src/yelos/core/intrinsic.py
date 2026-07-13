"""幕 III 内在活动:越阈触发 + 全闸门频控 + 梦语累积/投递判定。

蓝图 §5 / YELOS_SPEC §8。纯逻辑,零 astrbot / 零 sylanne_core / 零 random。
时间(now_ts、本地时刻、day_key)、状态、配置全部由 main 算好传入;
core 内禁 time.time()/datetime.now()。Surface 读取一律走防御式 sget(§2.3)。

主动只由场状态越阈驱动(P3):裸定时器不直发。判定顺序严格照 §5.2——
P0 前置 → 触发条件 → 全部闸门 → occasion 选择,任一不过即不发。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import sget

# 距上次主动的最小间隔(§5.2 闸门:2 小时)。
_MIN_PROACTIVE_GAP_SECONDS = 2 * 3600

# quiet 开始前的夜窗宽度(§5.2:晚安语义,只允许 contact_night)。
_NIGHT_WINDOW_MINUTES = 30

# 连续未回应清零阈(§5.2:达到即当日配额视同清零,收敛不刷存在感)。
_UNANSWERED_STREAK_CAP = 2


@dataclass(frozen=True)
class IntrinsicInput:
    session_id: str
    day_key: str
    surface: dict | None  # tick 后的 state() 快照(可 None)
    p: float
    enabled: bool
    silenced: bool
    sealed: bool
    guard_frozen_today: bool
    reach_out_cached: bool  # 幕 II 转交的 reach_out 信号(当日有效)
    now_local_minutes: int  # 本地时刻(0..1439),main 算好传入
    quiet_start_min: int
    quiet_end_min: int
    daily_cap_base: int  # 配置 intrinsic_daily_cap
    sent_today: int
    last_proactive_ts: float
    now_ts: float
    unanswered_streak: int  # 连续未回应的主动条数
    contact_night_sent_today: bool
    phase: str  # dynamics.relational_time.phase


@dataclass(frozen=True)
class IntrinsicDecision:
    send: bool
    occasion: str | None = None  # "contact_seek" | "contact_night"
    reason: str = ""  # 记账/日志用,非用户可见


def _in_interval(now: int, start: int, end: int) -> bool:
    """now 是否落在 [start, end) 分钟区间(mod 1440,支持跨零点)。

    start == end 视为空区间(永不命中)。
    """
    start %= 1440
    end %= 1440
    if start == end:
        return False
    if start < end:
        return start <= now < end
    # 跨零点:[start, 1440) ∪ [0, end)
    return now >= start or now < end


def _daily_cap(daily_cap_base: int, p: float) -> int:
    """插件侧每日主动上限:ceil(base × P);P=0 时为 0(§5.2)。"""
    if p <= 0.0 or daily_cap_base <= 0:
        return 0
    return math.ceil(daily_cap_base * p)


def decide(inp: IntrinsicInput) -> IntrinsicDecision:
    """幕 III 主动判定纯函数:全过才发(§5.2)。

    occasion 只在 send=True 时给出;措辞由 main 拿 occasion 问 primal。
    """
    # --- 0. P0 前置(硬编码第一梯队,任何机制不可绕过)---------------------
    if inp.sealed or inp.silenced or not inp.enabled:
        return IntrinsicDecision(False, reason="p0")

    s = inp.surface
    contact = sget(s, "state.needs.contact", 0.0)
    expression = sget(s, "state.needs.expression", 0.0)
    pressure = sget(s, "state.boundary.pressure", 0.0)
    quiet = sget(s, "state.needs.quiet", 0.0)
    budget = sget(s, "state.boundary.interruption_budget", 1.0)
    action = sget(s, "decision.action", "hold")

    # --- 1. 触发条件(满足其一)------------------------------------------
    reach_out = action == "reach_out" or inp.reach_out_cached
    need_thresh = contact >= 0.6 and expression >= 0.45
    if not (need_thresh or reach_out):
        return IntrinsicDecision(False, reason="no_trigger")

    # --- 2. 闸门(全部通过)---------------------------------------------
    # 引擎原生场闸门。
    if pressure >= 0.7:
        return IntrinsicDecision(False, reason="pressure")
    if quiet >= 0.5:
        return IntrinsicDecision(False, reason="quiet_need")
    # interruption_budget:引擎原生预算,与插件配额叠加取更严。
    if budget < 0.3:
        return IntrinsicDecision(False, reason="budget")
    # 关系长期休眠不追;cooling 允许(想念的窗口)。
    if inp.phase == "dormant":
        return IntrinsicDecision(False, reason="dormant")
    # 幕 II guard 冻结当日(P0 之外的机制副作用)。
    if inp.guard_frozen_today:
        return IntrinsicDecision(False, reason="guard_frozen")
    # 连续未回应达阈 → 当日配额视同清零。
    if inp.unanswered_streak >= _UNANSWERED_STREAK_CAP:
        return IntrinsicDecision(False, reason="unanswered")
    # 插件频控:每日配额(随 P 衰减)。
    cap = _daily_cap(inp.daily_cap_base, inp.p)
    if inp.sent_today >= cap:
        return IntrinsicDecision(False, reason="daily_cap")
    # 插件频控:距上次主动 ≥ 2h。
    if inp.now_ts - inp.last_proactive_ts < _MIN_PROACTIVE_GAP_SECONDS:
        return IntrinsicDecision(False, reason="min_gap")

    # quiet_hours 内禁发;开始前 30min 夜窗只允许 contact_night 且当日未发。
    if _in_interval(inp.now_local_minutes, inp.quiet_start_min, inp.quiet_end_min):
        return IntrinsicDecision(False, reason="quiet_hours")

    night_start = (inp.quiet_start_min - _NIGHT_WINDOW_MINUTES) % 1440
    in_night_window = _in_interval(
        inp.now_local_minutes, night_start, inp.quiet_start_min
    )

    # --- 3. occasion 选择 ------------------------------------------------
    if in_night_window:
        if inp.contact_night_sent_today:
            return IntrinsicDecision(False, reason="night_done")
        return IntrinsicDecision(True, occasion="contact_night", reason="night")
    return IntrinsicDecision(True, occasion="contact_seek", reason="seek")


# --- 梦语(§5.3;单一权威 = pending)------------------------------------


def dream_tick(
    surface: dict | None,
    in_quiet_hours: bool,
    expr_threshold: float = 0.6,
) -> bool:
    """本拍是否计一次"夜间越表达阈":in_quiet_hours 且 needs.expression ≥ 阈。

    梦不是 LLM 编的,是夜里真实场事件的残留;此处只判定累积一次与否,
    武装(count ≥ 2 → pending)与投递由 main / dream_ready 负责。
    """
    if not in_quiet_hours:
        return False
    return sget(surface, "state.needs.expression", 0.0) >= expr_threshold


def dream_ready(
    pending: bool,
    p: float,
    enabled: bool,
    delivered_today: bool,
) -> bool:
    """是否可在首次被动回复前投一句 dream_murmur。

    pending 且 P ≥ 0.3 且 enabled 且当日未投递 → True。
    单一权威:只认 pending(§5.3);P<0.3 梦语停(幕 V 效应)。
    """
    return pending and p >= 0.3 and enabled and not delivered_today
