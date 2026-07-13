"""contracts.py 在整个架构中的位置:三个可视化数据契约(蓝图 §12.1)。
纯数据整形(dataclass → dict),零 I/O、零随机——落盘/http 响应由调用方决定。

1. `shadow_deviation_band.json`:逐拍 {ts, ch, h0, 假设 min/max 包络, 基线
   day/week/month, ε_t, D_t}(偏差带图,四信号通道)。
2. `concern_timeline.json`:逐事件 {ts, ctype, armed 迁移, fire, intensity, q,
   y(结账后), tier 当值, β_c 当值, gate_trace}。
3. `calibration_reliability.json`:{bins, brier, n, per_ctype 分列}(可靠性
   图),bench 的"心疼精度"判分器读本契约(蓝图 §12.2/INTEGRATION_SPEC C10)。

三个契约都是"调用方喂点位序列,本文件只整形"——本包不持久化时间序列历史
(binding schema 只存聚合统计,§3.3),逐拍点位由调用方(测试/未来 bench 采
集器)在观测当下就地收集后一次性传入。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class DeviationPoint:
    ts: float
    ch: str
    h0: float | None
    hyp_min: float | None
    hyp_max: float | None
    baseline_day: float | None
    baseline_week: float | None
    baseline_month: float | None
    epsilon: float
    disagreement: float


@dataclass(frozen=True)
class ConcernEvent:
    ts: float
    ctype: str
    fire: bool
    intensity: float
    q: float
    y: int | None
    tier: str
    beta: float
    gate_trace: tuple[str, ...]


@dataclass(frozen=True)
class ReliabilityBin:
    q_center: float
    actual_freq: float
    count: int


def build_deviation_band(points: list[DeviationPoint]) -> dict:
    return {"schema": "shadow_deviation_band.v1", "points": [asdict(p) for p in points]}


def build_concern_timeline(events: list[ConcernEvent]) -> dict:
    return {"schema": "concern_timeline.v1", "events": [asdict(e) for e in events]}


def build_calibration_reliability(
    per_ctype: dict[str, tuple[float | None, int, tuple[ReliabilityBin, ...]]],
) -> dict:
    """`per_ctype`: ctype -> (brier, n, bins)。"""
    out: dict[str, dict] = {}
    for ctype, (brier, n, bins) in per_ctype.items():
        out[ctype] = {"brier": brier, "n": n, "bins": [asdict(b) for b in bins]}
    return {"schema": "calibration_reliability.v1", "per_ctype": out}


__all__ = [
    "DeviationPoint",
    "ConcernEvent",
    "ReliabilityBin",
    "build_deviation_band",
    "build_concern_timeline",
    "build_calibration_reliability",
]
