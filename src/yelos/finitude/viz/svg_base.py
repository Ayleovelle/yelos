"""viz/svg_base.py 在整个架构中的位置:零依赖 SVG 基元(finitude_BLUEPRINT §9)。

只提供 line/circle/arc/text/viewBox 拼装,约束:仅服务本模块三渲染器(p_curve/
rings/hourglass),不长成通用绘图库(虚胖自查点,§14.3-4)。颜色用 CSS 变量名
(WebUI 蓝图 §0.1 色板同源),独立打开(不经 WebUI 样式表)时有十六进制 fallback。
确定性:浮点格式化统一 `f"{v:.4f}"`,禁 repr 漂移(golden 的字节级前提)。
"""

from __future__ import annotations

import math

# CSS 变量名 + fallback 十六进制(与 WebUI 蓝图 §0.1 色板同源;不在此处定义调色板本体)。
INK = "var(--yl-ink, #2b2b2b)"
MOSS = "var(--yl-moss, #6a8f6a)"
EMBER = "var(--yl-ember, #c96a4b)"
FOG = "var(--yl-fog, #b9b9b9)"


def fmt(value: float) -> str:
    """统一浮点格式化:`f"{v:.4f}"`,golden 字节级前提。"""
    return f"{value:.4f}"


def svg_open(width: int | float, height: int | float, *, extra: str = "") -> str:
    return (
        f'<svg viewBox="0 0 {fmt(width)} {fmt(height)}" '
        f'xmlns="http://www.w3.org/2000/svg"{" " + extra if extra else ""}>'
    )


def svg_close() -> str:
    return "</svg>"


def line(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    color: str = INK,
    width: float = 1.0,
    dash: str | None = None,
    extra: str = "",
) -> str:
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    extra_attr = f" {extra}" if extra else ""
    return (
        f'<line x1="{fmt(x1)}" y1="{fmt(y1)}" x2="{fmt(x2)}" y2="{fmt(y2)}" '
        f'stroke="{color}" stroke-width="{fmt(width)}"{dash_attr}{extra_attr} />'
    )


def circle(
    cx: float,
    cy: float,
    r: float,
    *,
    fill: str = "none",
    stroke: str | None = None,
    stroke_width: float = 1.0,
    extra: str = "",
) -> str:
    stroke_attr = (
        f' stroke="{stroke}" stroke-width="{fmt(stroke_width)}"' if stroke else ""
    )
    extra_attr = f" {extra}" if extra else ""
    return (
        f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(r)}" '
        f'fill="{fill}"{stroke_attr}{extra_attr} />'
    )


def arc(
    cx: float,
    cy: float,
    r: float,
    start_deg: float,
    end_deg: float,
    *,
    color: str = INK,
    width: float = 1.0,
    extra: str = "",
) -> str:
    """圆弧路径(角度制,0 度在 +x 轴,顺时针);大弧标志按跨度是否 > 180 度判定。"""
    start_rad = math.radians(start_deg)
    end_rad = math.radians(end_deg)
    x1 = cx + r * math.cos(start_rad)
    y1 = cy + r * math.sin(start_rad)
    x2 = cx + r * math.cos(end_rad)
    y2 = cy + r * math.sin(end_rad)
    large_arc = 1 if (end_deg - start_deg) % 360 > 180 else 0
    extra_attr = f" {extra}" if extra else ""
    d = f"M {fmt(x1)} {fmt(y1)} A {fmt(r)} {fmt(r)} 0 {large_arc} 1 {fmt(x2)} {fmt(y2)}"
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{fmt(width)}"{extra_attr} />'


def text(
    x: float,
    y: float,
    content: str,
    *,
    size: float = 12.0,
    color: str = INK,
    anchor: str = "start",
    extra: str = "",
) -> str:
    escaped = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    extra_attr = f" {extra}" if extra else ""
    return (
        f'<text x="{fmt(x)}" y="{fmt(y)}" font-size="{fmt(size)}" fill="{color}" '
        f'text-anchor="{anchor}"{extra_attr}>{escaped}</text>'
    )


__all__ = [
    "INK",
    "MOSS",
    "EMBER",
    "FOG",
    "fmt",
    "svg_open",
    "svg_close",
    "line",
    "circle",
    "arc",
    "text",
]
