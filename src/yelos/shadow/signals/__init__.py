"""signals/ 在整个架构中的位置:四类关切检测器 + 迟滞 + 强度 + Legacy 兼容
壳(蓝图 §6),shadow 自著实质③。检测器只读正典轨迹 h0(见
`protocol.ConcernDetector`)。`DETECTOR_REGISTRY` 是 `orchestrator.py` v2
路径的组合根装配点,顺序即评估顺序(不影响正确性,只影响 gate_trace 的
可读顺序)。
"""

from __future__ import annotations

from . import (
    hysteresis,
    intensity,
    legacy_compat,
    pressure_spike,
    protocol,
    rhythm_break,
    warmth_drop,
    withdrawal,
)

DETECTOR_REGISTRY = {
    warmth_drop.CTYPE: warmth_drop.detect,
    pressure_spike.CTYPE: pressure_spike.detect,
    rhythm_break.CTYPE: rhythm_break.detect,
    withdrawal.CTYPE: withdrawal.detect,
}

__all__ = [
    "protocol",
    "warmth_drop",
    "pressure_spike",
    "rhythm_break",
    "withdrawal",
    "hysteresis",
    "intensity",
    "legacy_compat",
    "DETECTOR_REGISTRY",
]
