"""protocol.py 在整个架构中的位置:四检测器共同的协议与阈值常量表(蓝图
§6.1/§6.2)。检测器**只读正典轨迹 h0** 的 `ShadowView` 判触发——假设轨迹只
贡献 `EnsembleReading.disagreement`,不直接触发(防"扰动自证关切"回路,
蓝图 §6.1 明文)。
"""

from __future__ import annotations

from typing import Protocol

from ..binding_v2 import CTYPES
from ..contracts import BaselineView, DayContext, RawConcern, ShadowView

# th_base(蓝图 §6.2 决策表第一列阈值;th_eff = th_base + beta_c,SHTOM-A7)。
TH_BASE: dict[str, float] = {
    "warmth_drop": 0.25,
    "pressure_spike": 0.6,
    "rhythm_break": 3.0,
    "withdrawal": 0.2,
}

# re-arm 阈比例(A6):re_arm_th = 触发阈 * REARM_RATIO。触发阈本身依检测器
# 语义各异(warmth_drop/withdrawal 用 th_eff 直接比较,pressure_spike/
# rhythm_break 用 strength 的归一比较)——各检测器模块自行定义"触发阈"取值,
# 本表只统一比例常量,供 hysteresis.py 消费。
REARM_RATIO = 0.6


class ConcernDetector(Protocol):
    ctype: str

    def detect(
        self, view: ShadowView, base: dict[str, BaselineView], day_ctx: DayContext
    ) -> RawConcern | None: ...


assert set(TH_BASE) == set(CTYPES), (
    "TH_BASE keys must match the four detector ctype enum"
)


__all__ = ["TH_BASE", "REARM_RATIO", "ConcernDetector"]
