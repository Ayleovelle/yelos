"""epochs/ 在整个架构中的位置:纪元机双轨(finitude_BLUEPRINT §4)。

A 轨(fixed.py,默认/兼容)+ B 轨(order_parameter.py,序参量相变)+ 并跑器
(dualtrack.py)。对外只导出并跑器与只读工具函数,不导出内部检测状态构造细节
(调用方经 `DualTrack`/`OpDetectorState.from_dict` 接入)。
"""

from __future__ import annotations

from . import fixed
from .dualtrack import DualTrack, DualTrackOutcome, decide_notification, read_divergence
from .order_parameter import (
    MIN_SAMPLES,
    THETA,
    WINDOW,
    OpDetectorState,
    clamp_forward,
    psi,
    rho_budget,
    rho_lex,
)

__all__ = [
    "fixed",
    "DualTrack",
    "DualTrackOutcome",
    "decide_notification",
    "read_divergence",
    "OpDetectorState",
    "clamp_forward",
    "psi",
    "rho_lex",
    "rho_budget",
    "THETA",
    "WINDOW",
    "MIN_SAMPLES",
]
