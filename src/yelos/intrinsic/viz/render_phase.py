"""viz/render_phase.py 在整个架构中的位置:昼夜相位盘 SVG(维五②,T-VIZ-03)。

极坐标盘:学到的 μ/κ 扇形 vs 强迫曲线环。零依赖(纯字符串拼接)。
"""

from __future__ import annotations

import math

from .contract import CircadianSnapshot

SIZE = 320
CENTER = SIZE / 2.0
RADIUS = SIZE / 2.0 - 20.0


def _polar_point(angle_rad: float, r: float) -> tuple[float, float]:
    return (CENTER + r * math.cos(angle_rad), CENTER + r * math.sin(angle_rad))


def render_phase(circadian: CircadianSnapshot) -> str:
    parts: list[str] = [
        f'<svg viewBox="0 0 {SIZE} {SIZE}" xmlns="http://www.w3.org/2000/svg">',
        f'<circle cx="{CENTER}" cy="{CENTER}" r="{RADIUS:.2f}" fill="none" '
        f'stroke="#ccc" stroke-width="1" />',
    ]

    # 强迫曲线环(forcing_curve 采样点,幅度映射到半径偏移)
    n = len(circadian.forcing_curve)
    if n > 0:
        max_amp = max(abs(v) for v in circadian.forcing_curve) or 1.0
        points = []
        for i, v in enumerate(circadian.forcing_curve):
            angle = 2.0 * math.pi * i / n - math.pi / 2.0
            r = RADIUS * (0.6 + 0.35 * (v / max_amp))
            x, y = _polar_point(angle, r)
            points.append(f"{x:.2f},{y:.2f}")
        parts.append(
            f'<polygon points="{" ".join(points)}" fill="none" '
            f'stroke="#3d5a80" stroke-width="1.5" data-role="forcing-curve" />'
        )

    # 学到的 μ/κ 扇形(κ 映射为半径长度,μ 映射为角度)
    mu_angle = 2.0 * math.pi * (circadian.mu_min / 1440.0) - math.pi / 2.0
    r_mu = RADIUS * max(0.05, min(1.0, circadian.kappa))
    x_mu, y_mu = _polar_point(mu_angle, r_mu)
    parts.append(
        f'<line x1="{CENTER}" y1="{CENTER}" x2="{x_mu:.2f}" y2="{y_mu:.2f}" '
        f'stroke="#e76f51" stroke-width="3" data-role="mu-kappa" '
        f'data-mu-min="{circadian.mu_min}" data-kappa="{circadian.kappa:.4f}" />'
    )

    parts.append("</svg>")
    return "".join(parts)


__all__ = ["render_phase", "SIZE"]
