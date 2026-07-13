"""svg_render.py 在整个架构中的位置:自著零依赖 SVG 渲染器(蓝图 §12.2),
三视图,golden 测试对象。零依赖:只用标准库字符串拼接;确定性:同一输入
恒产同一字节串(全部数值来自入参,零 random/时间戳读取),与 arbiter/
intrinsic 的 viz 渲染器同一手法。
"""

from __future__ import annotations

from .contracts import ConcernEvent, DeviationPoint, ReliabilityBin

_WIDTH = 640

_TIER_BG = {
    "observe": "#f5f5f5",
    "normal": "#eaf6ea",
    "tight": "#fff3cd",
    "silent": "#f8d7da",
}


def _fmt(x: float) -> str:
    return f"{x:.4f}"


def render_deviation_band(points: list[DeviationPoint]) -> str:
    """偏差带图:通道带 + 假设包络 + ε/D 记账线。"""
    height = 160
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_WIDTH} {height}">',
        f'<rect x="0" y="0" width="{_WIDTH}" height="{height}" fill="#ffffff"/>',
    ]
    n = max(len(points), 1)
    step_x = _WIDTH / n
    for i, p in enumerate(points):
        x = i * step_x
        if p.h0 is not None:
            y = height - 20 - p.h0 * (height - 40)
            parts.append(
                f'<circle cx="{_fmt(x)}" cy="{_fmt(y)}" r="2" fill="#2a3f5f"/>'
            )
        if p.hyp_min is not None and p.hyp_max is not None:
            y_min = height - 20 - p.hyp_min * (height - 40)
            y_max = height - 20 - p.hyp_max * (height - 40)
            top = min(y_min, y_max)
            h = abs(y_max - y_min)
            parts.append(
                f'<rect x="{_fmt(x - 1)}" y="{_fmt(top)}" width="2" height="{_fmt(h)}" '
                f'fill="#7a9cc6" opacity="0.5"/>'
            )
    parts.append("</svg>")
    return "".join(parts)


def render_concern_timeline(events: list[ConcernEvent]) -> str:
    """concern 时间线:armed 色带(用 tier 底色近似)+ fire 火花 + 敏感化标签。"""
    height = 80
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_WIDTH} {height}">',
        f'<rect x="0" y="0" width="{_WIDTH}" height="{height}" fill="#ffffff"/>',
    ]
    n = max(len(events), 1)
    slot_w = _WIDTH / n
    for i, ev in enumerate(events):
        x = i * slot_w
        bg = _TIER_BG.get(ev.tier, "#ffffff")
        parts.append(
            f'<rect x="{_fmt(x)}" y="0" width="{_fmt(slot_w)}" height="20" fill="{bg}"/>'
        )
        if ev.fire:
            cx = x + slot_w * 0.5
            r = 2 + ev.intensity * 4
            parts.append(
                f'<circle cx="{_fmt(cx)}" cy="40" r="{_fmt(r)}" fill="#c0392b"/>'
            )
        beta_y = 70 - ev.beta * 100
        parts.append(
            f'<circle cx="{_fmt(x + slot_w * 0.5)}" cy="{_fmt(beta_y)}" r="1.5" fill="#555555"/>'
        )
    parts.append("</svg>")
    return "".join(parts)


def render_reliability(
    brier: float | None, n: int, bins: tuple[ReliabilityBin, ...]
) -> str:
    """可靠性图:对角线(完美校准参照)+ 分箱柱。"""
    size = 200
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}">',
        f'<rect x="0" y="0" width="{size}" height="{size}" fill="#ffffff"/>',
        f'<line x1="0" y1="{size}" x2="{size}" y2="0" stroke="#cccccc" stroke-width="1"/>',
    ]
    for b in bins:
        cx = b.q_center * size
        cy = size - b.actual_freq * size
        r = 2 + min(b.count, 20) * 0.5
        parts.append(
            f'<circle cx="{_fmt(cx)}" cy="{_fmt(cy)}" r="{_fmt(r)}" fill="#7a9cc6"/>'
        )
    label = f"brier={_fmt(brier) if brier is not None else 'nan'} n={n}"
    parts.append(f'<text x="4" y="12" font-size="10">{label}</text>')
    parts.append("</svg>")
    return "".join(parts)


__all__ = ["render_deviation_band", "render_concern_timeline", "render_reliability"]
