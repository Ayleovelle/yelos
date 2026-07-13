"""forgetting 子包在架构中的位置。

艾宾浩斯保持函数两族(MEM-A1)+ 复述增益(MEM-A2)。纯数学,零状态,时间/S
全部入参传入;是 recall 因子与 l3 strength 计算的共同下游。
"""

from __future__ import annotations

from .retention import (
    ExpRetention,
    PowRetention,
    RetentionFamily,
    S_CAP,
    get_family,
    rehearse,
)

__all__ = [
    "ExpRetention",
    "PowRetention",
    "RetentionFamily",
    "S_CAP",
    "get_family",
    "rehearse",
]
