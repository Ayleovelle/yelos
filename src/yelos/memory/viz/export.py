"""export.py 在架构中的位置。

三视图数据契约的生产者(§8):记忆热度图 / 主题演化桑基 / 遗忘曲线族。
夜窗 viz_export 步调用 ``export_all`` 原子写三份 JSON 到 memory/viz/。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

from ..contracts import SemanticEntry, TopicNode
from ..forgetting.retention import RetentionFamily

DAY_SECONDS = 86400.0


def build_heatmap(
    entries: Iterable[SemanticEntry],
    now_ts: float,
    fam: RetentionFamily,
    *,
    sample_points: int = 6,
) -> dict:
    """条目×时间×R 值:heatmap.json。"""
    entries = list(entries)
    days = sorted({e.day_key for e in entries})
    out_entries = []
    for e in entries:
        span = max(1.0, now_ts - e.created_ts)
        series = []
        for i in range(sample_points):
            denom = max(1, sample_points - 1)
            t = e.created_ts + span * i / denom
            dt = max(0.0, now_ts - t)
            series.append(round(fam.R(dt, e.S), 4))
        out_entries.append(
            {"id": e.id, "day": e.day_key, "R_series": series, "topic_id": e.topic_id}
        )
    return {"days": days, "entries": out_entries}


def build_sankey(topics: Iterable[TopicNode]) -> dict:
    """主题演化桑基:直接由 L3 事件流生成,"断裂可考古"的人眼验收面。"""
    topics = list(topics)
    topics_out = [
        {"id": t.id, "label_kw": list(t.label_kw), "born": t.born_day, "state": t.state}
        for t in topics
    ]
    flows = []
    for t in topics:
        for ev in t.events:
            if ev.kind == "grow":
                flows.append(
                    {
                        "from": ev.payload.get("entry_id", ""),
                        "to": t.id,
                        "kind": "grow",
                        "day": ev.day_key,
                    }
                )
            elif ev.kind == "merge_in":
                flows.append(
                    {
                        "from": ev.payload.get("absorbed_id", ""),
                        "to": t.id,
                        "kind": "merge",
                        "day": ev.day_key,
                    }
                )
            elif ev.kind == "split":
                flows.append(
                    {
                        "from": t.id,
                        "to": ev.payload.get("child_id", ""),
                        "kind": "split",
                        "day": ev.day_key,
                    }
                )
    return {"topics": topics_out, "flows": flows}


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, max(0, int(round(p * (len(sorted_vals) - 1)))))
    return sorted_vals[idx]


def build_curves(
    entries: Iterable[SemanticEntry],
    family_name: str,
    fam: RetentionFamily,
    *,
    theory_points: int = 20,
    sample_span_days: float = 60.0,
) -> dict:
    """实测 S 分位曲线 vs 理论曲线(遗忘曲线族对比,bench 衰减族报告消费)。"""
    entries = list(entries)
    step = (sample_span_days * DAY_SECONDS) / max(1, theory_points - 1)
    dts = [round(i * step, 1) for i in range(theory_points)]
    theory = [[dt, round(fam.R(dt, 1.0), 6)] for dt in dts]

    s_values = sorted(e.S for e in entries)
    measured = []
    for p in (0.25, 0.5, 0.75):
        s_q = _percentile(s_values, p)
        points = [[dt, round(fam.R(dt, s_q), 6)] for dt in dts]
        measured.append({"s_quantile": p, "s_value": s_q, "points": points})

    return {"family": family_name, "theory": theory, "measured": measured}


def _atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def export_all(
    root: Path,
    sid_hash: str,
    gen: int,
    entries: Iterable[SemanticEntry],
    topics: Iterable[TopicNode],
    now_ts: float,
    fam: RetentionFamily,
    family_name: str,
) -> dict[str, Path]:
    """夜窗 viz_export 步:原子写三契约,返回写出的路径(供 consolidation 报告)。"""
    entries = list(entries)
    topics = list(topics)
    viz_dir = Path(root) / "memory" / "viz"
    paths = {
        "heatmap": viz_dir / f"{sid_hash}.g{gen}.heatmap.json",
        "sankey": viz_dir / f"{sid_hash}.g{gen}.sankey.json",
        "curves": viz_dir / f"{sid_hash}.g{gen}.curves.json",
    }
    _atomic_write(paths["heatmap"], build_heatmap(entries, now_ts, fam))
    _atomic_write(paths["sankey"], build_sankey(topics))
    _atomic_write(paths["curves"], build_curves(entries, family_name, fam))
    return paths
