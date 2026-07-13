"""在整个架构中的位置:词池热图 SVG 渲染器(蓝图 §12.1,零依赖)。

消费 PoolSnapshot 契约;occasion × reachable 条形热图。仓内活消费者:
CLI `python -m yelos.primal.viz`(人用)+ golden 测试(CI 用)。
"""

from __future__ import annotations

from ..viz.contracts import PoolSnapshot

_ROW_H = 20
_BAR_MAX_W = 200
_LEFT_PAD = 140


def render(snapshot: PoolSnapshot) -> str:
    occasions = sorted(snapshot.per_occasion.keys())
    width = _LEFT_PAD + _BAR_MAX_W + 40
    height = _ROW_H * len(occasions) + 40
    max_total = max(
        (v.get("total", 0) for v in snapshot.per_occasion.values()), default=1
    )
    max_total = max(max_total, 1)
    lines = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="var(--bg, #111)"/>',
        f'<text x="8" y="16" fill="var(--fg, #eee)" font-size="12">'
        f"pool_heatmap day={snapshot.day_key} band={snapshot.band}</text>",
    ]
    for i, occasion in enumerate(occasions):
        stats = snapshot.per_occasion[occasion]
        reachable = int(stats.get("reachable", 0))
        total = max(int(stats.get("total", 0)), 1)
        y = 30 + i * _ROW_H
        bar_w = round(_BAR_MAX_W * reachable / total) if total else 0
        lines.append(
            f'<text x="8" y="{y + 14}" fill="var(--fg, #eee)" font-size="11">{occasion}</text>'
        )
        lines.append(
            f'<rect x="{_LEFT_PAD}" y="{y}" width="{bar_w}" height="{_ROW_H - 4}" '
            f'fill="var(--accent, #6cf)"/>'
        )
        lines.append(
            f'<text x="{_LEFT_PAD + bar_w + 4}" y="{y + 14}" fill="var(--fg, #eee)" '
            f'font-size="10">{reachable}/{total}</text>'
        )
    lines.append("</svg>")
    return "\n".join(lines)


__all__ = ["render"]
