"""在整个架构中的位置:"她一生说过的话"词频时间线 SVG(蓝图 §12.2,零依赖)。

消费 contracts.timeline_export(record) 的输出;分纪元分场合词频条形。
"""

from __future__ import annotations

_ROW_H = 16


def render(timeline: dict) -> str:
    by_epoch = timeline.get("by_epoch", {}) if isinstance(timeline, dict) else {}
    epochs = sorted(by_epoch.keys())
    rows: list[tuple[str, str, int]] = []
    for epoch in epochs:
        for occasion in sorted(by_epoch[epoch].keys()):
            total = sum(by_epoch[epoch][occasion].values())
            rows.append((epoch, occasion, total))
    width = 360
    height = _ROW_H * max(len(rows), 1) + 30
    max_total = max((r[2] for r in rows), default=1) or 1
    lines = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="var(--bg, #111)"/>',
        '<text x="8" y="14" fill="var(--fg, #eee)" font-size="11">utterance timeline</text>',
    ]
    for i, (epoch, occasion, total) in enumerate(rows):
        y = 24 + i * _ROW_H
        bar_w = round(200 * total / max_total)
        lines.append(
            f'<text x="8" y="{y + 11}" fill="var(--fg, #eee)" font-size="9">'
            f"epoch{epoch}:{occasion}</text>"
        )
        lines.append(
            f'<rect x="140" y="{y}" width="{bar_w}" height="{_ROW_H - 3}" '
            f'fill="var(--accent, #6cf)"/>'
        )
        lines.append(
            f'<text x="{140 + bar_w + 4}" y="{y + 11}" fill="var(--fg, #eee)" '
            f'font-size="9">{total}</text>'
        )
    lines.append("</svg>")
    return "\n".join(lines)


__all__ = ["render"]
