"""viz/contract.py 在整个架构中的位置:`intrinsic_timeline.v1` 数据契约(维五①)。

schema 版本化(`version` 字段只增不删);本文件只定义结构与校验/导出,
不做任何渲染(渲染在 render_*.py)。第四消费者(bench 判分器)与第五
消费者(WebUI)读取本契约字段,但本波不算 viz 维五交付(§7 明文)。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..field.state import Vec4
from ..moments.taxonomy import MomentEntry

SCHEMA_VERSION = 1
MAX_FIELD_SAMPLES_PER_DAY = 288


@dataclass(frozen=True)
class FieldSample:
    t: int
    phi: Vec4

    def to_dict(self) -> dict:
        return {"t": self.t, "phi": list(self.phi)}


@dataclass(frozen=True)
class CrossingEvent:
    t: int
    s: float
    policy: str

    def to_dict(self) -> dict:
        return {"t": self.t, "s": self.s, "policy": self.policy}


@dataclass(frozen=True)
class CircadianSnapshot:
    mu_min: int
    kappa: float
    forcing_curve: tuple[float, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "mu_min": self.mu_min,
            "kappa": self.kappa,
            "forcing_curve": list(self.forcing_curve),
        }


@dataclass(frozen=True)
class DayTimeline:
    day_key: str
    field_samples: tuple[FieldSample, ...]
    crossings: tuple[CrossingEvent, ...]
    moments: tuple[MomentEntry, ...]
    circadian: CircadianSnapshot

    def to_dict(self) -> dict:
        return {
            "day_key": self.day_key,
            "field_samples": [s.to_dict() for s in self.field_samples],
            "crossings": [c.to_dict() for c in self.crossings],
            "moments": [m.to_dict() for m in self.moments],
            "circadian": self.circadian.to_dict(),
        }


@dataclass(frozen=True)
class IntrinsicTimeline:
    sid_hash: str
    policy: str
    days: tuple[DayTimeline, ...]
    version: int = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "sid_hash": self.sid_hash,
            "policy": self.policy,
            "days": [d.to_dict() for d in self.days],
        }


def downsample_field_samples(
    samples: list[FieldSample], max_n: int = MAX_FIELD_SAMPLES_PER_DAY
) -> tuple[FieldSample, ...]:
    """降采样至 ≤max_n/日(§7 契约);均匀跳采,保留首尾。"""
    n = len(samples)
    if n <= max_n or max_n <= 0:
        return tuple(samples)
    if max_n == 1:
        return (samples[-1],)
    step = (n - 1) / float(max_n - 1)
    picked_idx = sorted({min(n - 1, int(round(i * step))) for i in range(max_n)})
    picked_idx[-1] = n - 1  # 显式保留末尾(首尾锚定,均匀跳采只决定中段)
    return tuple(samples[i] for i in picked_idx)


_REQUIRED_TOP = ("version", "sid_hash", "policy", "days")
_REQUIRED_DAY = ("day_key", "field_samples", "crossings", "moments", "circadian")


def validate_timeline_dict(d: dict) -> None:
    """结构校验(T-CON-01 往返测试用);不合规直接 raise ValueError。"""
    for key in _REQUIRED_TOP:
        if key not in d:
            raise ValueError(f"intrinsic_timeline.v1 缺字段: {key}")
    if d["version"] != SCHEMA_VERSION:
        raise ValueError(f"intrinsic_timeline schema 版本不支持: {d['version']}")
    for day in d["days"]:
        for key in _REQUIRED_DAY:
            if key not in day:
                raise ValueError(f"intrinsic_timeline day 缺字段: {key}")


__all__ = [
    "SCHEMA_VERSION",
    "MAX_FIELD_SAMPLES_PER_DAY",
    "FieldSample",
    "CrossingEvent",
    "CircadianSnapshot",
    "DayTimeline",
    "IntrinsicTimeline",
    "downsample_field_samples",
    "validate_timeline_dict",
]
