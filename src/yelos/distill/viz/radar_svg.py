"""在整个架构中的位置:风格保真雷达 SVG(蓝图 §1 viz/;零依赖)。

逐场合展示 ``EvalReport.fidelity_js``(越小越保真,渲染时取 1-JS 作为
"保真度"半径,使雷达图直觉与"越靠外越像她"一致)。
"""

from __future__ import annotations

import math

_SIZE = 240
_CENTER = _SIZE / 2
_MAX_R = 90


def render(fidelity_js: dict) -> str:
    occasions = sorted(fidelity_js.keys())
    n = len(occasions)
    lines = [
        f'<svg viewBox="0 0 {_SIZE} {_SIZE}" xmlns="http://www.w3.org/2000/svg">',
        f'<rect x="0" y="0" width="{_SIZE}" height="{_SIZE}" fill="var(--bg, #111)"/>',
        '<text x="8" y="14" fill="var(--fg, #eee)" font-size="11">fidelity radar</text>',
    ]
    if n == 0:
        lines.append("</svg>")
        return "\n".join(lines)

    points = []
    for i, occasion in enumerate(occasions):
        js = max(0.0, min(1.0, float(fidelity_js[occasion])))
        fidelity = 1.0 - js
        angle = (2 * math.pi * i / n) - (math.pi / 2)
        radius = _MAX_R * fidelity
        x = _CENTER + radius * math.cos(angle)
        y = _CENTER + radius * math.sin(angle)
        points.append((x, y))
        label_x = _CENTER + (_MAX_R + 14) * math.cos(angle)
        label_y = _CENTER + (_MAX_R + 14) * math.sin(angle)
        lines.append(
            f'<text x="{label_x:.1f}" y="{label_y:.1f}" fill="var(--fg, #eee)" '
            f'font-size="8" text-anchor="middle">{occasion}</text>'
        )

    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    lines.append(
        f'<circle cx="{_CENTER}" cy="{_CENTER}" r="{_MAX_R}" fill="none" '
        f'stroke="var(--fg, #eee)" stroke-width="1" opacity="0.2"/>'
    )
    lines.append(
        f'<polygon points="{poly}" fill="var(--accent, #6cf)" fill-opacity="0.3" '
        f'stroke="var(--accent, #6cf)" stroke-width="1.5"/>'
    )
    lines.append("</svg>")
    return "\n".join(lines)


__all__ = ["render"]
