"""在整个架构中的位置:provider 路由桑基 SVG(蓝图 §12.3,零依赖)。

消费 record["utter_provenance"] 环缓冲(不含文本原文,隐私纪律)。
occasion → provider → outcome 三层流量条。
"""

from __future__ import annotations


def render(provenance: list[dict]) -> str:
    edges: dict[tuple[str, str], int] = {}
    for entry in provenance or ():
        occasion = str(entry.get("occasion", "unknown"))
        for pid, outcome in entry.get("chain", ()):
            key = (occasion, f"{pid}:{outcome}")
            edges[key] = edges.get(key, 0) + 1

    rows = sorted(edges.items())
    row_h = 16
    width = 400
    height = row_h * max(len(rows), 1) + 24
    max_count = max((c for _, c in rows), default=1) or 1
    lines = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="var(--bg, #111)"/>',
        '<text x="8" y="14" fill="var(--fg, #eee)" font-size="11">routing sankey</text>',
    ]
    for i, ((occasion, edge_label), count) in enumerate(rows):
        y = 24 + i * row_h
        bar_w = round(200 * count / max_count)
        label = f"{occasion} -> {edge_label}"
        lines.append(
            f'<text x="8" y="{y + 11}" fill="var(--fg, #eee)" font-size="9">{label}</text>'
        )
        lines.append(
            f'<rect x="220" y="{y}" width="{bar_w}" height="{row_h - 3}" '
            f'fill="var(--accent, #6cf)"/>'
        )
        lines.append(
            f'<text x="{220 + bar_w + 4}" y="{y + 11}" fill="var(--fg, #eee)" '
            f'font-size="9">{count}</text>'
        )
    lines.append("</svg>")
    return "\n".join(lines)


__all__ = ["render"]
