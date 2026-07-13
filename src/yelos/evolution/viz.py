"""viz.py 在整个架构中的位置:lineage 谱系树 / 漂移轨迹 / 适应度史 SVG 渲染器(蓝图 §6)。

零依赖,自著。CLI ``lineage --svg`` 的直接产物,也是 §6 数据契约
(``evolution_lineage.json``/``evolution_drift.json``)的仓内活消费者
(维五⑤,red-team wiring manifest 要求"仓内消费者"而非只是声明)。
"""

from __future__ import annotations

from .genome.registry import iron_keys, mutable_keys
from .lineage.ledger import ACCEPTED
from .lineage.records import LineageRecord

_W = 720
_ROW_H = 36


def _esc(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_lineage_tree(records: list[LineageRecord]) -> str:
    """代为节点,accepted 实线、rejected/墓碑虚线灰节点、rollback 回边。"""
    height = max(_ROW_H * (len(records) + 1), 80)
    lines: list[str] = [
        f'<svg viewBox="0 0 {_W} {height}" xmlns="http://www.w3.org/2000/svg">'
    ]
    lines.append(f'<rect width="{_W}" height="{height}" fill="var(--bg,#0b0b12)"/>')
    prev_y = None
    for i, record in enumerate(records):
        y = _ROW_H * (i + 1)
        accepted = record.verdict == ACCEPTED
        color = "#5fd68a" if accepted else "#888"
        dash = "" if accepted else ' stroke-dasharray="4,3"'
        if prev_y is not None:
            lines.append(
                f'<line x1="60" y1="{prev_y}" x2="60" y2="{y}" '
                f'stroke="{color}"{dash} stroke-width="2"/>'
            )
        summary = ", ".join(f"{c.key}:{c.before}->{c.after}" for c in record.changes)
        label = f"gen {record.gen} [{record.verdict}] {summary}"
        lines.append(
            f'<circle cx="60" cy="{y}" r="8" fill="{color}"/>'
            f'<text x="80" y="{y + 4}" font-size="12" fill="var(--fg,#eee)">'
            f"{_esc(label)}</text>"
        )
        if record.verdict == "rollback":
            lines.append(
                f'<path d="M60,{y} C20,{y - 20} 20,{prev_y or y} 60,{prev_y or y}" '
                f'stroke="#e0b84a" fill="none" stroke-width="2"/>'
            )
        prev_y = y
    lines.append("</svg>")
    return "\n".join(lines)


def render_drift_trajectory(records: list[LineageRecord]) -> str:
    """每可变参数一条折线(代 x 值);铁域参数画为平直基线(视觉证明 A2)。"""
    accepted = [r for r in records if r.verdict == ACCEPTED]
    height = 260
    lines: list[str] = [
        f'<svg viewBox="0 0 {_W} {height}" xmlns="http://www.w3.org/2000/svg">'
    ]
    lines.append(f'<rect width="{_W}" height="{height}" fill="var(--bg,#0b0b12)"/>')

    tracked = sorted(mutable_keys())
    palette = ["#5fd68a", "#5fa8d6", "#d65f9b", "#d6b85f", "#9b5fd6"]
    for idx, key in enumerate(tracked):
        color = palette[idx % len(palette)]
        points: list[str] = []
        current = None
        for i, record in enumerate(accepted):
            for change in record.changes:
                if change.key == key:
                    current = change.after
            if isinstance(current, (int, float)):
                x = 20 + i * (max(_W - 40, 1) / max(len(accepted), 1))
                y = height - 20 - (float(current) * (height - 60))
                points.append(f"{x:.1f},{y:.1f}")
        if points:
            lines.append(
                f'<polyline points="{" ".join(points)}" fill="none" '
                f'stroke="{color}" stroke-width="2"/>'
            )
            lines.append(
                f'<text x="20" y="{20 + idx * 14}" font-size="10" fill="{color}">{_esc(key)}</text>'
            )

    for idx, key in enumerate(sorted(iron_keys())):
        y = height - 20 - idx
        lines.append(
            f'<line x1="20" y1="{y}" x2="{_W - 20}" y2="{y}" stroke="#555" '
            f'stroke-dasharray="2,2" stroke-width="1"/>'
        )
    lines.append("</svg>")
    return "\n".join(lines)


def render_fitness_history(records: list[LineageRecord]) -> str:
    """bench 分随代曲线 + 被拒代散点。"""
    height = 200
    lines: list[str] = [
        f'<svg viewBox="0 0 {_W} {height}" xmlns="http://www.w3.org/2000/svg">'
    ]
    lines.append(f'<rect width="{_W}" height="{height}" fill="var(--bg,#0b0b12)"/>')

    ordered = sorted(records, key=lambda r: r.gen)
    n = max(len(ordered), 1)
    accepted_pts: list[str] = []
    for i, record in enumerate(ordered):
        score = record.fitness.get("bench_score") if record.fitness else None
        if not isinstance(score, (int, float)):
            continue
        x = 20 + i * (max(_W - 40, 1) / n)
        y = height - 20 - (float(score) / 100.0) * (height - 40)
        if record.verdict == ACCEPTED:
            accepted_pts.append(f"{x:.1f},{y:.1f}")
        else:
            lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#888"/>')
    if accepted_pts:
        lines.append(
            f'<polyline points="{" ".join(accepted_pts)}" fill="none" '
            f'stroke="#5fd68a" stroke-width="2"/>'
        )
    lines.append("</svg>")
    return "\n".join(lines)


def export_lineage_json(records: list[LineageRecord]) -> list[dict]:
    """``evolution_lineage.json`` 数据契约(§3.3 的数组形态)。"""
    return [r.to_dict() for r in records]


def export_drift_json(records: list[LineageRecord]) -> dict[str, list]:
    """``evolution_drift.json``:key -> [per-gen value]。"""
    accepted = sorted(
        (r for r in records if r.verdict == ACCEPTED), key=lambda r: r.gen
    )
    out: dict[str, list] = {key: [] for key in sorted(mutable_keys())}
    current: dict[str, object] = {}
    for record in accepted:
        for change in record.changes:
            current[change.key] = change.after
        for key in out:
            if key in current:
                out[key].append([record.gen, current[key]])
    return out


__all__ = [
    "render_lineage_tree",
    "render_drift_trajectory",
    "render_fitness_history",
    "export_lineage_json",
    "export_drift_json",
]
