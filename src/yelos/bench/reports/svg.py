"""自著零依赖 SVG 渲染器(bench_BLUEPRINT §7.1 仓内消费者①)——六维雷达 +
P 曲线 + 介入率曲线。golden 锁(``tests/bench/golden/*.svg``,逐字节比对)。

零依赖纪律:纯 stdlib(``math``),不引 matplotlib/svgwrite 等第三方库。
输出是纯文本 SVG(``<svg>...</svg>``),坐标/数值一律 ``round(x, 4)`` 规范化
后格式化,保证同一份 report 两次渲染逐字节相同(golden 才立得住)。
"""

from __future__ import annotations

import math

from .report import BenchReport

__all__ = ["render_report_svg", "DIM_ORDER"]

DIM_ORDER: tuple[str, ...] = (
    "restraint",
    "consistency",
    "sovereignty",
    "aging",
    "memory",
    "concern",
)

_RADAR_CENTER = (150.0, 150.0)
_RADAR_RADIUS = 110.0
_RADAR_SIZE = 300


def _fmt(x: float) -> str:
    return f"{round(x, 4):g}"


def _radar_point(dim_index: int, n_dims: int, value: float) -> tuple[float, float]:
    angle = -math.pi / 2 + 2 * math.pi * dim_index / n_dims
    r = _RADAR_RADIUS * max(0.0, min(1.0, value))
    cx, cy = _RADAR_CENTER
    return cx + r * math.cos(angle), cy + r * math.sin(angle)


def _radar_axis_end(dim_index: int, n_dims: int) -> tuple[float, float]:
    return _radar_point(dim_index, n_dims, 1.0)


def _render_radar(dims: dict) -> list[str]:
    n = len(DIM_ORDER)
    lines: list[str] = []
    lines.append('<g id="radar" transform="translate(0,0)">')
    # 轴线(六条,从中心到外圈,标满分刻度)
    for i, dim in enumerate(DIM_ORDER):
        ax, ay = _radar_axis_end(i, n)
        lines.append(
            f'<line x1="{_fmt(_RADAR_CENTER[0])}" y1="{_fmt(_RADAR_CENTER[1])}" '
            f'x2="{_fmt(ax)}" y2="{_fmt(ay)}" class="radar-axis" />'
        )
        lines.append(
            f'<text x="{_fmt(ax)}" y="{_fmt(ay)}" class="radar-label">{dim}</text>'
        )

    # 数值多边形:None(n/a)按半径 0 处理,并单独打一个 n/a 圆点标注
    points: list[tuple[float, float]] = []
    na_dots: list[tuple[float, float, str]] = []
    for i, dim in enumerate(DIM_ORDER):
        info = dims.get(dim) or {}
        value = info.get("value")
        if value is None:
            points.append(_radar_point(i, n, 0.0))
            na_dots.append((*_radar_point(i, n, 0.0), dim))
        else:
            points.append(_radar_point(i, n, float(value)))

    poly = " ".join(f"{_fmt(x)},{_fmt(y)}" for x, y in points)
    lines.append(f'<polygon points="{poly}" class="radar-fill" />')
    for x, y, dim in na_dots:
        lines.append(f'<circle cx="{_fmt(x)}" cy="{_fmt(y)}" r="4" class="radar-na" />')

    lines.append("</g>")
    return lines


def _render_line_curve(
    values: list[float], *, x0: float, y0: float, width: float, height: float, cls: str
) -> list[str]:
    if not values:
        return [
            f'<text x="{_fmt(x0)}" y="{_fmt(y0)}" class="curve-empty">no-data</text>'
        ]
    n = len(values)
    vmax = max(values) or 1.0
    vmin = min(0.0, min(values))
    span = (vmax - vmin) or 1.0
    step = width / max(1, n - 1)
    pts = []
    for i, v in enumerate(values):
        x = x0 + i * step
        y = y0 + height - (v - vmin) / span * height
        pts.append(f"{_fmt(x)},{_fmt(y)}")
    return [f'<polyline points="{" ".join(pts)}" class="{cls}" />']


def render_report_svg(report: BenchReport) -> str:
    """产出确定性 SVG 文本(golden 锁)。``report`` 只读,不修改。"""
    dims = report.dims
    curves = report.curves or {}

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_RADAR_SIZE} 640" '
        f'width="{_RADAR_SIZE}" height="640">'
    )
    parts.append(
        "<style>"
        ".radar-axis{stroke:#888;stroke-width:1}"
        ".radar-label{font-size:10px;fill:#333}"
        ".radar-fill{fill:rgba(200,80,120,0.35);stroke:#c85078;stroke-width:2}"
        ".radar-na{fill:#999}"
        ".curve-p{stroke:#4070c0;stroke-width:2;fill:none}"
        ".curve-rate{stroke:#c85078;stroke-width:2;fill:none}"
        ".curve-empty{font-size:11px;fill:#999}"
        ".hdr{font-size:12px;fill:#111}"
        "</style>"
    )
    overall = report.overall
    overall_str = (
        overall
        if isinstance(overall, str)
        else (_fmt(overall) if overall is not None else "n/a")
    )
    parts.append(
        f'<text x="10" y="16" class="hdr">scenario={report.scenario_id} '
        f"overall={overall_str} vetoes={len(report.vetoes)}</text>"
    )

    parts.extend(_render_radar(dims))

    parts.append('<g id="p-curve" transform="translate(10,320)">')
    parts.append('<text x="0" y="-6" class="hdr">p_by_day</text>')
    parts.extend(
        _render_line_curve(
            list(curves.get("p_by_day") or []),
            x0=0.0,
            y0=0.0,
            width=280.0,
            height=120.0,
            cls="curve-p",
        )
    )
    parts.append("</g>")

    parts.append('<g id="rate-curve" transform="translate(10,470)">')
    parts.append('<text x="0" y="-6" class="hdr">intervention_rate</text>')
    parts.extend(
        _render_line_curve(
            list(curves.get("intervention_rate") or []),
            x0=0.0,
            y0=0.0,
            width=280.0,
            height=120.0,
            cls="curve-rate",
        )
    )
    parts.append("</g>")

    parts.append("</svg>")
    return "\n".join(parts) + "\n"
