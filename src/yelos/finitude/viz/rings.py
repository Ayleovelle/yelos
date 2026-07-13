"""viz/rings.py 在整个架构中的位置:词汇年轮图(finitude_BLUEPRINT §6.4/§9,同心环)。

一环一纪元,环宽 ∝ 该纪元活跃日数(entry["active_days"],缺失时按等宽退化——与
"无 pools 的旧环裸画"同一降级动机);环色随纪元序号循环;环注该纪元剩余词数
(entry["pools"] 各场合词句数之和,pools 缺席 → 环注"?"、裸画,不补演)。

`epoch_history` 条目形状(与 v0.1 `{day, epoch}` 兼容,增量字段全可选):
`{"day","epoch","track"?,"active_days"?,"pools"?: {occ: [word,...]},"lost"?: [...]}`。
"""

from __future__ import annotations

from . import svg_base as sb

DEFAULT_SIZE = 480
_PALETTE = (sb.INK, sb.MOSS, sb.EMBER, sb.FOG)
_INNER_HOLE = 10.0
_OUTER_MARGIN = 20.0


def render_rings(epoch_history: list[dict], size: int = DEFAULT_SIZE) -> str:
    cx = cy = size / 2.0
    max_r = size / 2.0 - _OUTER_MARGIN

    parts: list[str] = [sb.svg_open(size, size, extra='data-viz="rings"')]

    if not epoch_history:
        parts.append(sb.svg_close())
        return "\n".join(parts)

    weights = []
    for entry in epoch_history:
        w = entry.get("active_days") if isinstance(entry, dict) else None
        if not isinstance(w, int) or isinstance(w, bool) or w <= 0:
            w = 1
        weights.append(w)
    total = sum(weights)
    band_total = max(1.0, max_r - _INNER_HOLE)

    running = _INNER_HOLE
    for i, (entry, weight) in enumerate(zip(epoch_history, weights)):
        band = band_total * (weight / total)
        r = running + band / 2.0
        color = _PALETTE[i % len(_PALETTE)]
        parts.append(sb.circle(cx, cy, r, stroke=color, stroke_width=band, fill="none"))

        pools = entry.get("pools") if isinstance(entry, dict) else None
        if isinstance(pools, dict):
            count = sum(len(v) for v in pools.values() if isinstance(v, (list, tuple)))
            label = str(count)
        else:
            label = "?"
        parts.append(sb.text(cx + r + 2.0, cy, label, size=9.0))
        running += band

    parts.append(sb.svg_close())
    return "\n".join(parts)


__all__ = ["render_rings", "DEFAULT_SIZE"]
