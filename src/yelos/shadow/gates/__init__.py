"""gates/ 在整个架构中的位置:输出闸集中(蓝图 §9),shadow 自著实质⑥,
唯一出口(SHTOM-A2/T1)。`chain.py` 组装七步闸链,`exit.py` 是链尾唯一构造
`ConcernVerdict` 的函数。
"""

from __future__ import annotations

from . import chain, exit

__all__ = ["chain", "exit"]
