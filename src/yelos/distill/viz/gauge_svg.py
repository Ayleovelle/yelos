"""在整个架构中的位置:越界率仪表 SVG(蓝图 §1 viz/;零依赖)。

消费 ``distill.trace.jsonl`` 逐行 outcome 计数;仪表读数 = R5(全候选被
拦)/(R5+R6) 之比 —— 与 ``eval.violation`` 的闸前测是两个不同的率(本图
是运行时观测的"实际请求里有多少次被闸最终拦到没词说"),互补而非重复。
"""

from __future__ import annotations

import math

_WIDTH = 220
_HEIGHT = 120


def render(trace_rows: list[dict]) -> str:
    ok = sum(1 for r in trace_rows if str(r.get("outcome", "")).startswith("ok"))
    rejected = sum(
        1 for r in trace_rows if str(r.get("outcome", "")).startswith("rejected_all")
    )
    skipped = sum(
        1 for r in trace_rows if str(r.get("outcome", "")).startswith("skip:")
    )
    total = ok + rejected + skipped
    rate = (rejected / total) if total else 0.0

    cx, cy, r = _WIDTH / 2, _HEIGHT - 20, 80
    # 半圆仪表:0(左,越界率 0%)-> π(右,越界率 100%)
    needle_angle = math.pi - (math.pi * rate)
    nx = cx + r * math.cos(needle_angle)
    ny = cy - r * math.sin(needle_angle)

    lines = [
        f'<svg viewBox="0 0 {_WIDTH} {_HEIGHT}" xmlns="http://www.w3.org/2000/svg">',
        f'<rect x="0" y="0" width="{_WIDTH}" height="{_HEIGHT}" fill="var(--bg, #111)"/>',
        '<text x="8" y="14" fill="var(--fg, #eee)" font-size="11">violation gauge</text>',
        f'<path d="M {cx - r} {cy} A {r} {r} 0 0 1 {cx + r} {cy}" '
        f'fill="none" stroke="var(--fg, #eee)" stroke-width="4" opacity="0.3"/>',
        f'<line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" '
        f'stroke="var(--accent, #f66)" stroke-width="3"/>',
        f'<circle cx="{cx}" cy="{cy}" r="4" fill="var(--accent, #f66)"/>',
        f'<text x="{cx - 30}" y="{cy + 24}" fill="var(--fg, #eee)" font-size="14">'
        f"{rate * 100:.1f}%</text>",
        f'<text x="8" y="{_HEIGHT - 4}" fill="var(--fg, #eee)" font-size="9">'
        f"ok={ok} rejected={rejected} skipped={skipped} total={total}</text>",
        "</svg>",
    ]
    return "\n".join(lines)


__all__ = ["render"]
