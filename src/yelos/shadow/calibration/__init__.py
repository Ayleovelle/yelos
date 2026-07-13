"""calibration/ 在整个架构中的位置:Brier 校准闭环(蓝图 §7),shadow 深度
叙事主轴。`ledger.py` 落账 + 结账,`outcome.py` 结果代理提取,`brier.py`
纯数值计算,`gate_policy.py` 是 [SHTOM-T3] 校准 → 闸档位。
"""

from __future__ import annotations

from . import brier, gate_policy, ledger, outcome

__all__ = ["ledger", "outcome", "brier", "gate_policy"]
