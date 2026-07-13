"""viz/hourglass.py 在整个架构中的位置:剩余岁月沙漏(finitude_BLUEPRINT §9/§8.2,红队 minor⑨)。

上腔剩余活跃日、下腔已活活跃日、颈部当前日耗;None 值(或 `INFINITE_SENTINEL`/
样本不足的日历估计)渲染"未可知"记号,不假装精确。仓内活消费者:farewell 首段
摘要(运行时路径)+ anthology 卷尾章(送别日 remaining=0 的定格)+ 本渲染器自身。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..projection.contracts import INFINITE_SENTINEL
from . import svg_base as sb

if TYPE_CHECKING:
    from ..projection.contracts import ProjectionData

DEFAULT_SIZE = (200, 320)
_UNKNOWN_MARK = "未可知"


def render_hourglass(
    proj: "ProjectionData", size: tuple[int, int] = DEFAULT_SIZE
) -> str:
    width, height = size
    cx = width / 2.0
    top_y = 20.0
    bottom_y = height - 20.0
    neck_y = height / 2.0
    half_w = width / 2.0 - 15.0

    parts: list[str] = [sb.svg_open(width, height, extra='data-viz="hourglass"')]

    # 外轮廓(上下两个三角形,颈部相接)
    parts.append(sb.line(cx - half_w, top_y, cx, neck_y, color=sb.INK))
    parts.append(sb.line(cx + half_w, top_y, cx, neck_y, color=sb.INK))
    parts.append(sb.line(cx - half_w, bottom_y, cx, neck_y, color=sb.INK))
    parts.append(sb.line(cx + half_w, bottom_y, cx, neck_y, color=sb.INK))
    parts.append(sb.line(cx - half_w, top_y, cx + half_w, top_y, color=sb.INK))
    parts.append(sb.line(cx - half_w, bottom_y, cx + half_w, bottom_y, color=sb.INK))

    remaining = proj.est_remaining_active_days
    lived = max(0, proj.active_days_lived)
    unknown_remaining = remaining >= INFINITE_SENTINEL

    if unknown_remaining:
        parts.append(
            sb.text(cx, (top_y + neck_y) / 2.0, _UNKNOWN_MARK, anchor="middle")
        )
    else:
        total = max(1, remaining + lived)
        frac = min(1.0, remaining / total) if total > 0 else 0.0
        fill_y = neck_y - frac * (neck_y - top_y)
        width_at_fill = half_w * (1.0 - frac)
        parts.append(
            sb.line(
                cx - width_at_fill,
                fill_y,
                cx + width_at_fill,
                fill_y,
                color=sb.EMBER,
                width=2.0,
            )
        )
        parts.append(
            sb.text(cx, top_y - 6.0, str(remaining), anchor="middle", size=10.0)
        )

    total_for_lived = (
        max(1, remaining + lived) if not unknown_remaining else max(1, lived)
    )
    lived_frac = min(1.0, lived / total_for_lived) if total_for_lived > 0 else 0.0
    fill_y_lower = neck_y + lived_frac * (bottom_y - neck_y)
    width_at_lived = half_w * lived_frac
    parts.append(
        sb.line(
            cx - width_at_lived,
            fill_y_lower,
            cx + width_at_lived,
            fill_y_lower,
            color=sb.MOSS,
            width=2.0,
        )
    )
    parts.append(sb.text(cx, bottom_y + 14.0, str(lived), anchor="middle", size=10.0))

    spend = max(0.0, proj.est_spend_per_active_day)
    neck_r = min(6.0, 1.0 + spend * 20.0)
    parts.append(sb.circle(cx, neck_y, neck_r, fill=sb.EMBER))

    if proj.est_remaining_calendar_days is None:
        parts.append(
            sb.text(cx, height - 4.0, _UNKNOWN_MARK, anchor="middle", size=9.0)
        )
    else:
        parts.append(
            sb.text(
                cx,
                height - 4.0,
                f"~{proj.est_remaining_calendar_days}d",
                anchor="middle",
                size=9.0,
            )
        )

    parts.append(sb.svg_close())
    return "\n".join(parts)


__all__ = ["render_hourglass", "DEFAULT_SIZE"]
