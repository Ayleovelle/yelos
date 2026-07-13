"""simulator/ 在整个架构中的位置:多假设影子编排(蓝图 §4),自著实质①。

`ensemble.py` 管轨迹生命周期,`epsilon.py` 是 A5 唯一公式实现,`budget.py`
是 RE11 预算降档。三者只互相纯函数调用,零 import `orchestrator.py`
(上向依赖禁止,蓝图 §2 依赖图)。
"""

from __future__ import annotations

from . import budget, ensemble, epsilon

__all__ = ["ensemble", "epsilon", "budget"]
