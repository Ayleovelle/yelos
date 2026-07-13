"""svg.py 在架构中的位置。

自著零依赖 SVG 渲染器×3(维五):记忆热度图/主题演化桑基/遗忘曲线族。
纯字符串拼接,零第三方绘图库;空库空态也要渲染出合法 SVG,不崩(§9)。
"""

from __future__ import annotations

_WIDTH = 640
_HEIGHT = 360
_MARGIN = 24


def _svg_open(width: int = _WIDTH, height: int = _HEIGHT) -> str:
    return (
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
        f'<rect width="{width}" height="{height}" fill="#12131a"/>'
    )


def _svg_close() -> str:
    return "</svg>"


def _r_color(r: float) -> str:
    """R∈[0,1] → 冷(蓝,遗忘)到暖(橙,记得)的确定性色阶。"""
    r = max(0.0, min(1.0, r))
    red = int(40 + r * 200)
    green = int(60 + r * 120)
    blue = int(180 - r * 140)
    return f"rgb({red},{green},{blue})"


def svg_heatmap(data: dict, *, width: int = _WIDTH, height: int = _HEIGHT) -> str:
    entries = data.get("entries", [])
    parts = [_svg_open(width, height)]
    if not entries:
        parts.append(
            f'<text x="{width / 2}" y="{height / 2}" fill="#888" '
            f'text-anchor="middle" font-size="14">(空库)</text>'
        )
        parts.append(_svg_close())
        return "".join(parts)

    n_rows = len(entries)
    row_h = max(2.0, (height - 2 * _MARGIN) / n_rows)
    n_cols = max((len(e.get("R_series", [])) for e in entries), default=1)
    col_w = (width - 2 * _MARGIN) / max(1, n_cols)
    for ri, e in enumerate(entries):
        series = e.get("R_series", [])
        for ci, r in enumerate(series):
            x = _MARGIN + ci * col_w
            y = _MARGIN + ri * row_h
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{col_w:.1f}" '
                f'height="{row_h:.1f}" fill="{_r_color(float(r))}"/>'
            )
    parts.append(_svg_close())
    return "".join(parts)


def svg_sankey(data: dict, *, width: int = _WIDTH, height: int = _HEIGHT) -> str:
    topics = data.get("topics", [])
    flows = data.get("flows", [])
    parts = [_svg_open(width, height)]
    if not topics:
        parts.append(
            f'<text x="{width / 2}" y="{height / 2}" fill="#888" '
            f'text-anchor="middle" font-size="14">(空库)</text>'
        )
        parts.append(_svg_close())
        return "".join(parts)

    n = len(topics)
    node_x = width - _MARGIN - 8
    step = max(1.0, (height - 2 * _MARGIN) / max(1, n))
    pos: dict[str, tuple[float, float]] = {}
    state_color = {
        "nascent": "#6b7280",
        "active": "#f59e0b",
        "dormant": "#3b82f6",
        "dead": "#4b5563",
    }
    for i, t in enumerate(topics):
        y = _MARGIN + i * step
        pos[t["id"]] = (node_x, y)
        color = state_color.get(t.get("state", ""), "#9ca3af")
        parts.append(f'<circle cx="{node_x}" cy="{y:.1f}" r="5" fill="{color}"/>')
        label = "".join(t.get("label_kw", [])[:2]) or t.get("id", "")[:6]
        parts.append(
            f'<text x="{node_x + 8}" y="{y + 4:.1f}" fill="#e5e7eb" '
            f'font-size="10">{label}</text>'
        )

    kind_color = {"grow": "#22c55e", "merge": "#a855f7", "split": "#ef4444"}
    for flow in flows:
        to_pos = pos.get(flow.get("to", ""))
        if to_pos is None:
            continue
        from_pos = pos.get(flow.get("from", ""), (_MARGIN, to_pos[1]))
        color = kind_color.get(flow.get("kind", ""), "#666")
        parts.append(
            f'<line x1="{from_pos[0]:.1f}" y1="{from_pos[1]:.1f}" '
            f'x2="{to_pos[0]:.1f}" y2="{to_pos[1]:.1f}" stroke="{color}" '
            f'stroke-width="1.5" opacity="0.7"/>'
        )
    parts.append(_svg_close())
    return "".join(parts)


def svg_curves(data: dict, *, width: int = _WIDTH, height: int = _HEIGHT) -> str:
    theory = data.get("theory", [])
    measured = data.get("measured", [])
    parts = [_svg_open(width, height)]
    if not theory:
        parts.append(
            f'<text x="{width / 2}" y="{height / 2}" fill="#888" '
            f'text-anchor="middle" font-size="14">(空库)</text>'
        )
        parts.append(_svg_close())
        return "".join(parts)

    max_dt = max((p[0] for p in theory), default=1.0) or 1.0
    plot_w = width - 2 * _MARGIN
    plot_h = height - 2 * _MARGIN

    def _to_xy(dt: float, r: float) -> tuple[float, float]:
        x = _MARGIN + (dt / max_dt) * plot_w
        y = _MARGIN + (1.0 - r) * plot_h
        return x, y

    def _polyline(points: list, color: str, width_px: float = 2.0) -> str:
        pts = " ".join(
            f"{x:.1f},{y:.1f}" for x, y in (_to_xy(dt, r) for dt, r in points)
        )
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width_px}"/>'

    parts.append(_polyline(theory, "#f59e0b", 2.5))
    measured_colors = ["#3b82f6", "#22c55e", "#a855f7"]
    for i, m in enumerate(measured):
        pts = m.get("points", [])
        if pts:
            parts.append(_polyline(pts, measured_colors[i % len(measured_colors)], 1.5))
    parts.append(_svg_close())
    return "".join(parts)
