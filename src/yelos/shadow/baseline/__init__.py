"""baseline/ 在整个架构中的位置:基线估计族(蓝图 §5),shadow 自著实质②。

三窗口滚动分位数(day/week/month)+ 漂移建模(σ_family)+ v0.1 单点兼容
(legacy)。消费者:simulator/epsilon.py(A5 的 σ_family 输入)、signals/*(检测
器参照窗)、viz(偏差带图)。全部纯函数 + 显式 state dict 读写,零 I/O、零
random、零 time.time()——一切"当前值"与"day_key"由调用方传入。
"""

from __future__ import annotations

from .drift import channel_drift, family_dispersion
from .legacy import legacy_single_point
from .rolling import CHANNEL_SPAN, get_baseline_view, observe_tick, rollover_day

__all__ = [
    "CHANNEL_SPAN",
    "observe_tick",
    "rollover_day",
    "get_baseline_view",
    "channel_drift",
    "family_dispersion",
    "legacy_single_point",
]
