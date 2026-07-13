"""viz/render_day.py 在整个架构中的位置:"她的一天"时间轴 SVG(维五②,T-VIZ-02)。

24h 横轴,SPOKE/blocked/dream 分色刻痕,intensity(phi 范数)映射刻痕高。
moments 全量渲染——增删一条即 golden 变(§5.3 消费断言)。
"""

from __future__ import annotations

from ..moments.taxonomy import MomentKind
from .contract import DayTimeline

WIDTH = 960
HEIGHT = 160
BASELINE_Y = HEIGHT - 20
MAX_TICK_HEIGHT = 120

_KIND_COLOR: dict[str, str] = {
    MomentKind.SPOKE.value: "#2a9d8f",
    MomentKind.WANT_BLOCKED_BUDGET.value: "#e9c46a",
    MomentKind.WANT_BLOCKED_GAP.value: "#e9c46a",
    MomentKind.WANT_BLOCKED_QUIET.value: "#264653",
    MomentKind.WANT_BLOCKED_RESPECT.value: "#e76f51",
    MomentKind.CROSSED_BUT_GATED.value: "#f4a261",
    MomentKind.WANT_EXPIRED.value: "#a8a8a8",
    MomentKind.DREAM_ARMED.value: "#6d597a",
    MomentKind.DREAM_DELIVERED.value: "#355070",
    MomentKind.DEGRADED.value: "#b56576",
}


def _minutes_of_day(ts: float, day_seconds_offset: float = 0.0) -> float:
    """ts 视为当日秒偏移(0..86400);渲染层不关心真实时区换算,由调用方保证
    传入的 moment.ts 已是"当日内相对秒数"或可以此规则一致解释的绝对秒(取模)。
    """
    return (ts % 86400.0) / 60.0


def _phi_norm(phi: tuple[float, float, float, float]) -> float:
    return sum(x * x for x in phi) ** 0.5 / 2.0


def render_day(day: DayTimeline) -> str:
    parts: list[str] = [
        f'<svg viewBox="0 0 {WIDTH} {HEIGHT}" xmlns="http://www.w3.org/2000/svg" '
        f'data-day="{day.day_key}">',
        f'<line x1="0" y1="{BASELINE_Y}" x2="{WIDTH}" y2="{BASELINE_Y}" stroke="#333" />',
    ]
    for m in day.moments:
        minute = _minutes_of_day(m.ts)
        x = WIDTH * (minute / 1440.0)
        intensity = _phi_norm(m.phi)
        tick_h = 8.0 + intensity * MAX_TICK_HEIGHT
        color = _KIND_COLOR.get(str(m.kind), "#999999")
        y0 = BASELINE_Y
        y1 = BASELINE_Y - tick_h
        parts.append(
            f'<line x1="{x:.2f}" y1="{y0:.2f}" x2="{x:.2f}" y2="{y1:.2f}" '
            f'stroke="{color}" stroke-width="2" data-kind="{m.kind}" '
            f'data-reason="{m.reason_code}" />'
        )
    parts.append("</svg>")
    return "".join(parts)


__all__ = ["render_day", "WIDTH", "HEIGHT"]
