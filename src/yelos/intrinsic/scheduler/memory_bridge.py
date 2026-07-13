"""scheduler/memory_bridge.py 在整个架构中的位置:moments → memory L1 双写(W-4)。

`moments/` 本身不认识 memory(依赖方向干净,§2.1);本文件是编排层
(scheduler,依赖全部)与 `memory.MemoryFacade` 的唯一接触点,把
`MomentEntry` 转成 `memory.EpisodeEvent`(kind="moment",已在
`memory.contracts.EVENT_KINDS` 白名单预留,§2.1 注释:"moment/dream 由
W2 起 intrinsic 写入")并经 `MemoryWriter`(鸭子类型:任何具备
`observe(sid, gen, ev) -> int` 方法的对象,通常是 `MemoryFacade` 实例)
写入 L1。

无自由文本:`text=""`(§5.1 schema 纪律),全部信息压进 `meta`(扁平小
字段,`validate_meta` 强制)。
"""

from __future__ import annotations

from typing import Protocol

from yelos.memory.contracts import AffectStamp, EpisodeEvent

from ..moments.taxonomy import MomentEntry


class MemoryWriter(Protocol):
    def observe(self, sid: str, gen: int, ev: EpisodeEvent) -> int: ...


def moment_to_episode_event(moment: MomentEntry) -> EpisodeEvent:
    """MomentEntry → memory.EpisodeEvent(kind="moment",零自由文本)。"""
    drive, languor, longing, afterglow = moment.phi
    return EpisodeEvent(
        kind="moment",
        ts=moment.ts,
        day_key=moment.day_key,
        text="",
        speaker="",
        occasion=moment.occasion_hint or "",
        affect=AffectStamp(
            warmth=afterglow, pressure=languor, contact=drive, quiet=longing
        ),
        meta={
            "kind": str(moment.kind),
            "reason_code": moment.reason_code[:32],
            "trace_hash": moment.trace_hash[:32],
        },
    )


def write_moment_to_l1(
    writer: MemoryWriter, sid: str, gen: int, moment: MomentEntry
) -> int:
    """[W-4] 双写 A:每条 moment 同步一条 L1 情景条目。返回 L1 序号(失败/关闭 -1)。"""
    ev = moment_to_episode_event(moment)
    return writer.observe(sid, gen, ev)


__all__ = ["MemoryWriter", "moment_to_episode_event", "write_moment_to_l1"]
