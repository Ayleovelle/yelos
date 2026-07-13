"""在整个架构中的位置:三份数据契约 schema + to_json(蓝图 §12)。

契约一 PoolSnapshot(词池状态)、契约二 UtteranceTimeline(timeline_export)、
契约三 ProvenanceRecord(谱系,record["utter_provenance"] 环缓冲项的形状,
本文件只给往返 helper,环缓冲本身由 session 层维护)。
"""

from __future__ import annotations

from dataclasses import dataclass, field

PROVENANCE_CAP = 200


@dataclass(frozen=True)
class PoolSnapshot:
    day_key: str
    sid_hash: str
    lang: str
    epoch: int
    p: float
    band: str
    per_occasion: dict = field(default_factory=dict)


def pool_snapshot_to_json(snap: PoolSnapshot) -> dict:
    return {
        "day_key": snap.day_key,
        "sid_hash": snap.sid_hash,
        "lang": snap.lang,
        "epoch": snap.epoch,
        "p": snap.p,
        "band": snap.band,
        "per_occasion": dict(snap.per_occasion),
    }


def pool_snapshot_from_json(data: dict) -> PoolSnapshot:
    return PoolSnapshot(
        day_key=str(data.get("day_key", "")),
        sid_hash=str(data.get("sid_hash", "")),
        lang=str(data.get("lang", "zh")),
        epoch=int(data.get("epoch", 0)),
        p=float(data.get("p", 0.0)),
        band=str(data.get("band", "B0")),
        per_occasion=dict(data.get("per_occasion", {})),
    )


def timeline_export(record: dict) -> dict:
    """契约二导出器:record["utterances"](既有)+ provider 字段 → 分纪元

    分场合词频。record 结构缺失时返回空结构(不 raise,viz 只读契约数据)。
    """
    utterances = record.get("utterances", []) if isinstance(record, dict) else []
    by_epoch: dict[str, dict[str, dict[str, int]]] = {}
    for item in utterances:
        if not isinstance(item, dict):
            continue
        epoch = str(item.get("epoch", 0))
        occasion = str(item.get("occasion", "unknown"))
        text = str(item.get("text", ""))
        if not text:
            continue
        epoch_block = by_epoch.setdefault(epoch, {})
        occ_block = epoch_block.setdefault(occasion, {})
        occ_block[text] = occ_block.get(text, 0) + 1
    return {"by_epoch": by_epoch}


def make_provenance_entry(
    ts: float,
    occasion: str,
    provider: str,
    chain: tuple[tuple[str, str], ...],
    band: str,
    transforms: tuple[str, ...],
) -> dict:
    """契约三条目构造(隐私纪律:不含 canonical/text 原文)。"""
    return {
        "ts": ts,
        "occasion": occasion,
        "provider": provider,
        "chain": [[pid, outcome] for pid, outcome in chain],
        "band": band,
        "transforms": list(transforms),
    }


__all__ = [
    "PROVENANCE_CAP",
    "PoolSnapshot",
    "pool_snapshot_to_json",
    "pool_snapshot_from_json",
    "timeline_export",
    "make_provenance_entry",
]
