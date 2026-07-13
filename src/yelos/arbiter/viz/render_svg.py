"""viz/render_svg.py 在整个架构中的位置。

自著零依赖 SVG 渲染器(arbiter_BLUEPRINT §7.2)。三视图:
1. 裁决时间线:verdict 色带(PASS 留白/TRIM 浅/REPLACE 中/SWALLOW 深,
   重咽加烬点)+ 守卫触发火花线;
2. 阈值漂移曲线:θ 四分量随日演化——两颗不同经历的心并排画,差异肉眼
   可见(T3 的视觉版);
3. 介入率滚动窗仪表:实测率 vs 1/min_gap 硬上界横线(如实标"硬约束",
   不标"定理",呼应推论 C1 的诚实标注纪律)。

零依赖:只用标准库字符串拼接,不引入任何 SVG/绘图第三方包。确定性:
同一输入恒产同一字节串(T-V1 golden 测试的前提),故本文件不含任何
random/时间戳读取——全部数值均来自入参。
"""

from __future__ import annotations

from .contract import ArbiterTimeline, DayTimeline

_SIGMA_FILL = {
    "PASS": "none",
    "TRIM": "#cdd9ea",
    "REPLACE": "#7a9cc6",
    "SWALLOW": "#2a3f5f",
}

_WIDTH = 640


def _fmt(x: float) -> str:
    return f"{x:.4f}"


def render_verdict_timeline(day: DayTimeline) -> str:
    """单日裁决时间线色带 + 重咽烬点。"""
    height = 60
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_WIDTH} {height}">',
        f'<rect x="0" y="0" width="{_WIDTH}" height="{height}" fill="#ffffff"/>',
        f'<line x1="0" y1="{height / 2}" x2="{_WIDTH}" y2="{height / 2}" '
        f'stroke="#dddddd" stroke-width="1"/>',
    ]
    n = max(len(day.verdicts), 1)
    slot_w = _WIDTH / n
    for i, ev in enumerate(day.verdicts):
        fill = _SIGMA_FILL.get(ev.kind, "none")
        x = i * slot_w
        if fill != "none":
            parts.append(
                f'<rect x="{_fmt(x)}" y="10" width="{_fmt(slot_w * 0.8)}" '
                f'height="30" fill="{fill}"/>'
            )
        if ev.hi:
            cx = x + slot_w * 0.4
            parts.append(f'<circle cx="{_fmt(cx)}" cy="50" r="3" fill="#c0392b"/>')
    parts.append("</svg>")
    return "".join(parts)


def render_theta_drift(days: tuple[DayTimeline, ...], *, label: str = "") -> str:
    """θ 四分量随日演化折线(T3 的视觉版:两颗不同经历的心并排画)。"""
    height = 160
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_WIDTH} {height}">',
        f'<rect x="0" y="0" width="{_WIDTH}" height="{height}" fill="#ffffff"/>',
    ]
    if label:
        parts.append(f'<text x="4" y="12" font-size="10">{label}</text>')
    if not days:
        parts.append("</svg>")
        return "".join(parts)
    n = len(days)
    step_x = _WIDTH / max(n - 1, 1)

    def _series(values: list[float], lo: float, hi: float, color: str) -> str:
        span = (hi - lo) or 1.0
        pts = []
        for i, v in enumerate(values):
            x = i * step_x
            y = height - 20 - (v - lo) / span * (height - 40)
            pts.append(f"{_fmt(x)},{_fmt(y)}")
        return f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="2"/>'

    d_sw = [d.theta.d_sw for d in days]
    d_rp = [d.theta.d_rp for d in days]
    d_ex = [d.theta.d_ex for d in days]
    gamma = [d.theta.gamma for d in days]
    parts.append(_series(d_sw, -0.05, 0.05, "#2a3f5f"))
    parts.append(_series(d_rp, -0.05, 0.05, "#7a9cc6"))
    parts.append(_series(d_ex, -0.10, 0.10, "#c0392b"))
    parts.append(_series(gamma, 0.8, 1.2, "#27ae60"))
    parts.append("</svg>")
    return "".join(parts)


def render_rate_gauge(days: tuple[DayTimeline, ...], *, min_gap_seconds: int) -> str:
    """介入率滚动窗仪表:实测率 vs 1/min_gap 硬上界横线(标"硬约束")。"""
    height = 100
    cap = 1.0 / min_gap_seconds if min_gap_seconds > 0 else 0.0
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_WIDTH} {height}">',
        f'<rect x="0" y="0" width="{_WIDTH}" height="{height}" fill="#ffffff"/>',
        f'<text x="4" y="12" font-size="9">硬约束 1/min_gap = {_fmt(cap)}(非定理)</text>',
    ]
    max_rate = cap * 1.5 if cap > 0 else 1.0
    cap_y = height - 20 - (cap / max_rate) * (height - 40) if max_rate else height - 20
    parts.append(
        f'<line x1="0" y1="{_fmt(cap_y)}" x2="{_WIDTH}" y2="{_fmt(cap_y)}" '
        f'stroke="#c0392b" stroke-dasharray="4,2" stroke-width="1"/>'
    )
    n = max(len(days), 1)
    bar_w = _WIDTH / n
    for i, d in enumerate(days):
        turns = max(d.rate_window.turns, 1)
        rate = d.rate_window.interventions / turns
        bh = min(rate / max_rate, 1.0) * (height - 40) if max_rate else 0.0
        x = i * bar_w
        y = height - 20 - bh
        parts.append(
            f'<rect x="{_fmt(x)}" y="{_fmt(y)}" width="{_fmt(bar_w * 0.8)}" '
            f'height="{_fmt(bh)}" fill="#7a9cc6"/>'
        )
    parts.append("</svg>")
    return "".join(parts)


def render_full(timeline: ArbiterTimeline, *, min_gap_seconds: int) -> str:
    """三视图拼接为一份文档(golden 测试的主入口)。"""
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 400">']
    y = 0
    for day in timeline.days:
        parts.append(f'<g transform="translate(0,{y})">')
        inner = render_verdict_timeline(day)
        parts.append(_strip_outer_svg(inner))
        parts.append("</g>")
        y += 60
    parts.append(f'<g transform="translate(0,{y})">')
    parts.append(
        _strip_outer_svg(render_theta_drift(timeline.days, label=timeline.sid_digest))
    )
    parts.append("</g>")
    y += 160
    parts.append(f'<g transform="translate(0,{y})">')
    parts.append(
        _strip_outer_svg(
            render_rate_gauge(timeline.days, min_gap_seconds=min_gap_seconds)
        )
    )
    parts.append("</g>")
    parts.append("</svg>")
    return "".join(parts)


def _strip_outer_svg(svg: str) -> str:
    """把内层 ``<svg ...>...</svg>`` 拆成拼接用的内部标记(去掉外层 svg 包裹,
    保留内部绘制内容),供 ``render_full`` 组装多视图到一份文档。
    """
    start = svg.index(">") + 1
    end = svg.rindex("</svg>")
    return svg[start:end]
