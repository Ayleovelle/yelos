"""rites/epoch_notice.py 在整个架构中的位置:纪元跃迁通告 payload(finitude_BLUEPRINT §7.2)。

跃迁通告**文本**恒走既有 `pending_epoch_notice → outbox → primal` 白名单链路
(幕 V 的嘴也是幕 I 的嘴);本模块只产生机器结构 payload,不产任何用户可见自由文本。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EpochNoticePayload:
    epoch_to: str
    track: str  # "A" | "B"
    day: str

    def to_dict(self) -> dict:
        return {"epoch_to": self.epoch_to, "track": self.track, "day": self.day}


def build_notice(epoch_to: str, track: str, day: str) -> EpochNoticePayload:
    """构造跃迁通告 payload;B 轨权威时 track="B",通告文本序列不变(同一纪元名序列)。"""
    return EpochNoticePayload(epoch_to=epoch_to, track=track, day=day)


__all__ = ["EpochNoticePayload", "build_notice"]
