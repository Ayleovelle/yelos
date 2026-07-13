"""viz/render_field.py 在整个架构中的位置:场轨迹带状图 SVG(维五②,T-VIZ-01)。

4 通道堆叠带 + crossings 竖线标记 + quiet 窗底纹。零依赖(纯字符串拼接
SVG,不引入第三方绘图库);确定性:同输入同输出(golden 测试锁字节)。
"""

from __future__ import annotations

from ..field.state import CHANNEL_NAMES
from .contract import DayTimeline

WIDTH = 960
HEIGHT = 260
BAND_HEIGHT = HEIGHT // 4
CHANNEL_COLORS = ("#e07a5f", "#81b29a", "#3d5a80", "#f2cc8f")


def _x_of(t: int, day_minutes: int = 1440) -> float:
    return WIDTH * (t / float(day_minutes))


def render_field(
    day: DayTimeline, *, quiet_start_min: int = 60, quiet_end_min: int = 480
) -> str:
    """渲染单日场轨迹带状图。`quiet_start_min/quiet_end_min` 供底纹标注。"""
    parts: list[str] = [
        f'<svg viewBox="0 0 {WIDTH} {HEIGHT}" xmlns="http://www.w3.org/2000/svg" '
        f'data-day="{day.day_key}">'
    ]

    # quiet 窗底纹
    if quiet_start_min != quiet_end_min:
        x0 = _x_of(quiet_start_min)
        x1 = _x_of(quiet_end_min) if quiet_end_min > quiet_start_min else WIDTH
        w = max(0.0, x1 - x0)
        parts.append(
            f'<rect x="{x0:.2f}" y="0" width="{w:.2f}" height="{HEIGHT}" '
            f'fill="#00000010" data-role="quiet-window" />'
        )

    # 4 通道堆叠带
    for ci, (name, color) in enumerate(zip(CHANNEL_NAMES, CHANNEL_COLORS)):
        band_y = ci * BAND_HEIGHT
        points = []
        for sample in day.field_samples:
            x = _x_of(sample.t)
            v = sample.phi[ci]
            y = band_y + BAND_HEIGHT * (1.0 - v)
            points.append(f"{x:.2f},{y:.2f}")
        path = " ".join(points) if points else f"0,{band_y + BAND_HEIGHT}"
        parts.append(
            f'<polyline points="{path}" fill="none" stroke="{color}" '
            f'stroke-width="1.5" data-channel="{name}" />'
        )

    # crossings 竖线标记
    for crossing in day.crossings:
        x = _x_of(crossing.t)
        parts.append(
            f'<line x1="{x:.2f}" y1="0" x2="{x:.2f}" y2="{HEIGHT}" '
            f'stroke="#6d597a" stroke-width="1" stroke-dasharray="3,3" '
            f'data-policy="{crossing.policy}" />'
        )

    parts.append("</svg>")
    return "".join(parts)


__all__ = ["render_field", "WIDTH", "HEIGHT"]
