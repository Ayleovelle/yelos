"""viz/p_curve.py 在整个架构中的位置:P 曲线与纪元相变图(finitude_BLUEPRINT §9,双轨对比)。

内容:契约 P 折线(墨)、P_expr 细线(reserve 时,苔)、A 轨边界横 rule、A 跃迁竖线
(实线)、B 跃迁虚竖线(来自 `epoch_divergence.jsonl`,因为非权威轨的跃迁不会落
ledger epoch_shift 行)、hi>0 日烬点。x 轴用"第 n 条已记录 settle 行"的序数
(活跃日索引),不是自然日历(与 v0.1"P 曲线只在活跃日下折"的语义一致)。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import svg_base as sb

if TYPE_CHECKING:
    from ..ledger_ext import LifeReplay

DEFAULT_SIZE = (720, 240)
_MARGIN_L = 40.0
_MARGIN_R = 20.0
_MARGIN_T = 20.0
_MARGIN_B = 30.0
_A_BOUNDARIES = (0.6, 0.3, 0.15)  # 与 epochs.fixed 的边界值同源(纯展示,非判据)


def _day_order(replay: "LifeReplay") -> list[str]:
    order: list[str] = []
    seen: set[str] = set()
    for day, _ in replay.p_series:
        if day and day not in seen:
            seen.add(day)
            order.append(day)
    return order


def render_p_curve(
    replay: "LifeReplay",
    divergence: list[dict],
    size: tuple[int, int] = DEFAULT_SIZE,
) -> str:
    width, height = size
    plot_w = width - _MARGIN_L - _MARGIN_R
    plot_h = height - _MARGIN_T - _MARGIN_B

    order = _day_order(replay)
    index_of = {day: i for i, day in enumerate(order)}
    span = max(1, len(order) - 1)

    def x_of(day: str) -> float | None:
        idx = index_of.get(day)
        if idx is None:
            return None
        return _MARGIN_L + (idx / span) * plot_w

    def y_of(p: float) -> float:
        p_clamped = min(1.0, max(0.0, p))
        return _MARGIN_T + (1.0 - p_clamped) * plot_h

    parts: list[str] = [sb.svg_open(width, height, extra='data-viz="p_curve"')]

    # A 轨边界横 rule(雾灰虚线)
    for boundary in _A_BOUNDARIES:
        y = y_of(boundary)
        parts.append(
            sb.line(
                _MARGIN_L, y, width - _MARGIN_R, y, color=sb.FOG, width=1.0, dash="4,3"
            )
        )

    # 契约 P 折线(墨)
    pts = [(x_of(day), y_of(p)) for day, p in replay.p_series if x_of(day) is not None]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        parts.append(sb.line(x1, y1, x2, y2, color=sb.INK, width=1.6))

    # P_expr 细线(reserve 时,苔;来自 f_series)
    if replay.f_series:
        fpts = [
            (x_of(day), y_of(f)) for day, f in replay.f_series if x_of(day) is not None
        ]
        for (x1, y1), (x2, y2) in zip(fpts, fpts[1:]):
            parts.append(sb.line(x1, y1, x2, y2, color=sb.MOSS, width=1.0))

    # A 跃迁竖线(实线,墨)+ B 跃迁虚竖线(来自 epoch_events 里 track=="B" 的行,
    # 以及 divergence 中 b_only/both 但未必落 ledger 的行——两源合并去重按 day)
    a_days: set[str] = set()
    b_days: set[str] = set()
    for ev in replay.epoch_events:
        day = ev.get("day")
        track = ev.get("track")
        if track == "A":
            a_days.add(day)
        elif track == "B":
            b_days.add(day)
    for row in divergence:
        event = row.get("event")
        day = row.get("day")
        if event in ("a_only", "both"):
            a_days.add(day)
        if event in ("b_only", "both"):
            b_days.add(day)

    for day in sorted(a_days):
        x = x_of(day)
        if x is not None:
            parts.append(
                sb.line(x, _MARGIN_T, x, height - _MARGIN_B, color=sb.INK, width=1.0)
            )
    for day in sorted(b_days):
        x = x_of(day)
        if x is not None:
            parts.append(
                sb.line(
                    x,
                    _MARGIN_T,
                    x,
                    height - _MARGIN_B,
                    color=sb.MOSS,
                    width=1.0,
                    dash="2,2",
                )
            )

    # hi>0 日烬点(赭橙)
    p_by_day = dict(replay.p_series)
    for day, hi in sorted(replay.hi_by_day.items()):
        if hi <= 0:
            continue
        x = x_of(day)
        if x is None or day not in p_by_day:
            continue
        y = y_of(p_by_day[day])
        parts.append(sb.circle(x, y, 2.2, fill=sb.EMBER))

    parts.append(sb.svg_close())
    return "\n".join(parts)


__all__ = ["render_p_curve", "DEFAULT_SIZE"]
