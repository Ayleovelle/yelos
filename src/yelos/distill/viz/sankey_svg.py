"""在整个架构中的位置:语料构成桑基 SVG(蓝图 §1 viz/;零依赖)。

消费 ``CorpusManifest.sources``(逐来源计数,§5 数据契约)。
"""

from __future__ import annotations

from ..corpus.manifest import CorpusManifest

_ROW_H = 20
_BAR_MAX_W = 240
_LEFT_PAD = 100


def render(manifest: CorpusManifest) -> str:
    sources = sorted(manifest.sources.items())
    width = _LEFT_PAD + _BAR_MAX_W + 60
    height = _ROW_H * max(len(sources), 1) + 40
    max_count = max((c for _, c in sources), default=1) or 1

    lines = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="var(--bg, #111)"/>',
        f'<text x="8" y="16" fill="var(--fg, #eee)" font-size="12">'
        f"corpus sankey n={manifest.n_entries}</text>",
    ]
    for i, (source, count) in enumerate(sources):
        y = 28 + i * _ROW_H
        bar_w = round(_BAR_MAX_W * count / max_count)
        lines.append(
            f'<text x="8" y="{y + 14}" fill="var(--fg, #eee)" font-size="11">{source}</text>'
        )
        lines.append(
            f'<rect x="{_LEFT_PAD}" y="{y}" width="{bar_w}" height="{_ROW_H - 4}" '
            f'fill="var(--accent, #6cf)"/>'
        )
        lines.append(
            f'<text x="{_LEFT_PAD + bar_w + 4}" y="{y + 14}" fill="var(--fg, #eee)" '
            f'font-size="10">{count}</text>'
        )
    lines.append("</svg>")
    return "\n".join(lines)


__all__ = ["render"]
