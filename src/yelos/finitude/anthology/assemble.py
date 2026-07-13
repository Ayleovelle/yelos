"""anthology/assemble.py 在整个架构中的位置:assemble_anthology_v2(finitude_BLUEPRINT §6.1)。

`build_context` 是 registry 探针与 chapters/templates 共同的**唯一数据视图组装点**
(合并 record + ledger replay + divergence + moments + projection 的读侧数据)。
`assemble_anthology_v2` 编排"组装 ctx → 三模板渲染 → 三 SVG → 落盘"全链;
`legacy_assemble` 是 v1 签名外壳(`(record, day_key) -> (dict, str)`),直接转发
`core.finitude.assemble_anthology`——v0.1 调用方(若有)零改动可用,不假装深化版
能在只有 record 没有 ledger 的场景下凭空生成 ledger 派生字段。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..rites.incarnation import aging_of
from . import chapters as ch
from . import templates
from .registry import EXCLUDED, FIELD_REGISTRY  # noqa: F401  (T3 CI 依赖点,保持可达)

if TYPE_CHECKING:
    from ..ledger_ext import LifeReplay
    from ..projection.contracts import ProjectionData

MAX_MOMENTS_TOTAL = ch.MAX_MOMENTS_TOTAL
_MOMENTS_ABSENT_MARKER = "她没有留下这样的记录"


def _sid_hash(sid: str) -> str:
    """文件名安全化短哈希(与 intrinsic.moments.ledger.sid_hash 同算法,独立实现

    避免跨模块耦合,仅求文件名习惯一致——参见 intrinsic/moments/ledger.py 头注同款说明。
    """
    return hashlib.blake2b(sid.encode("utf-8"), digest_size=6).hexdigest()


def _describe_moment(entry: Any) -> str:
    if isinstance(entry, dict):
        day = entry.get("day_key") or entry.get("day") or ""
        kind = entry.get("kind", "")
    else:
        day = getattr(entry, "day_key", "")
        kind = getattr(entry, "kind", "")
    return f"{kind}@{day}"


def _select_moments(moments: list | None, sid: str, gen: int) -> list[str]:
    if not moments:
        return []
    picked = ch._sample(list(moments), sid, gen, "moments", MAX_MOMENTS_TOTAL)  # noqa: SLF001
    return [_describe_moment(m) for m in picked]


def _rings_word_total(epoch_history: list) -> int:
    total = 0
    for item in epoch_history:
        if not isinstance(item, dict):
            continue
        pools = item.get("pools")
        if isinstance(pools, dict):
            total += sum(len(v) for v in pools.values() if isinstance(v, (list, tuple)))
    return total


def build_context(
    record: dict,
    replay: "LifeReplay",
    divergence_rows: list[dict],
    moments: list | None,
    proj: "ProjectionData",
    sid: str,
    gen: int,
    day_key: str,
) -> dict:
    """T3 正向/反向测试与 chapters/templates 共用的唯一数据视图组装点。"""
    aging_spec = aging_of(record)
    epoch2_raw = record.get("epoch2") if isinstance(record.get("epoch2"), dict) else {}
    epoch2_view = {
        "b_index": epoch2_raw.get("b_index", 0),
        "fired_days": list(epoch2_raw.get("fired_days") or []),
    }

    utterances = record.get("utterances") or []
    dreams = record.get("dreams") or []
    milestones = record.get("milestones") or []
    epoch_history = record.get("epoch_history") or []
    swallowed_total = record.get("swallowed_total", 0)
    if not isinstance(swallowed_total, int) or isinstance(swallowed_total, bool):
        swallowed_total = 0

    selected_descriptions = _select_moments(moments, sid, gen)
    moments_marker = (
        _MOMENTS_ABSENT_MARKER
        if not selected_descriptions
        else "、".join(selected_descriptions)
    )

    contract_p = record.get("p", 0.0)
    if not isinstance(contract_p, (int, float)) or isinstance(contract_p, bool):
        contract_p = 0.0

    return {
        "sid": sid,
        "gen": gen,
        "day_key": day_key,
        "name": record.get("name") or "她",
        "born_day": record.get("born_day") or "",
        "born_at": record.get("born_at"),
        "incarnation": record.get("incarnation", 1),
        "p": float(contract_p),
        "epoch_history": epoch_history,
        "milestones": milestones,
        "utterances": utterances,
        "dreams": dreams,
        "swallowed_total": swallowed_total,
        "aging": {
            "model": aging_spec.model,
            "params": aging_spec.params,
            "active_days_settled": aging_spec.active_days_settled,
            "fast": aging_spec.fast,
        },
        "epoch2": epoch2_view,
        "mode": record.get("mode", "steward"),
        "ledger": {
            "final_p": replay.final_p(),
            "hi_by_day": dict(replay.hi_by_day),
            "concern_by_day": dict(replay.concern_by_day),
        },
        "divergence_summary": {"count": len(divergence_rows)},
        "rings_word_total": _rings_word_total(epoch_history),
        "moments_marker": moments_marker,
        "moments_selected": [],
        "projection": proj.to_json(),
    }


def write_anthology(
    data_dir: str | Path,
    sid: str,
    ctx: dict,
    long_md: str,
    short_md: str,
    appendix_dict: dict,
    svgs: dict[str, str],
) -> dict[str, str]:
    """落盘(§6.1 输出面)。返回各文件路径(str)。"""
    name = ctx.get("name", "她")
    root = Path(data_dir) / "anthologies" / f"{name}-{_sid_hash(sid)}"
    svg_dir = root / "svg"
    svg_dir.mkdir(parents=True, exist_ok=True)

    long_path = root / "她的一生.md"
    short_path = root / "她的一生·短笺.md"
    json_path = root / "她的一生.json"

    long_path.write_text(long_md, encoding="utf-8")
    short_path.write_text(short_md, encoding="utf-8")
    json_path.write_text(
        json.dumps(appendix_dict, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    paths = {
        "anthology_path": str(long_path),
        "short_path": str(short_path),
        "json_path": str(json_path),
    }
    for svg_name, svg_content in svgs.items():
        svg_path = svg_dir / f"{svg_name}.svg"
        svg_path.write_text(svg_content, encoding="utf-8")
        paths[f"{svg_name}_svg_path"] = str(svg_path)
    return paths


def assemble_anthology_v2(
    record: dict,
    replay: "LifeReplay",
    divergence_rows: list[dict],
    moments: list | None,
    proj: "ProjectionData",
    sid: str,
    gen: int,
    day_key: str,
    data_dir: str | Path | None = None,
) -> dict:
    """全链组装:ctx → 三模板 → (可选)三 SVG 落盘。`affect_farewell` 契约锚:

    返回体含 `anthology_path`(长卷 md 路径,v0.1 工具契约零改动的字段名)。
    """
    from ..viz import render_hourglass, render_p_curve, render_rings

    ctx = build_context(
        record, replay, divergence_rows, moments, proj, sid, gen, day_key
    )
    long_md = templates.render_long(ctx)
    short_md = templates.render_short(ctx)
    appendix_dict = templates.render_appendix(ctx)

    svgs = {
        "p_curve": render_p_curve(replay, divergence_rows),
        "rings": render_rings(ctx["epoch_history"]),
        "hourglass": render_hourglass(proj),
    }

    result: dict = {
        "ctx": ctx,
        "long_md": long_md,
        "short_md": short_md,
        "appendix": appendix_dict,
        "svgs": svgs,
    }
    if data_dir is not None:
        paths = write_anthology(
            data_dir, sid, ctx, long_md, short_md, appendix_dict, svgs
        )
        result.update(paths)
    else:
        result["anthology_path"] = None
    return result


def legacy_assemble(record: dict, day_key: str) -> tuple[dict, str]:
    """v1 签名外壳(finitude_BLUEPRINT §7 措辞"v1 签名外壳保留转发")。

    只有 record + day_key、没有 ledger/moments/projection 时的兼容路径:直接转发
    `core.finitude.assemble_anthology`(v0.1 逐字节实现,零改动)。
    """
    from yelos.core.finitude import assemble_anthology as _v1_assemble

    return _v1_assemble(record, day_key)


__all__ = [
    "build_context",
    "write_anthology",
    "assemble_anthology_v2",
    "legacy_assemble",
]
