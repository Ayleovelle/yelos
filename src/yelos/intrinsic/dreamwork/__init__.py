"""dreamwork/ 在整个架构中的位置:梦境生成子系统(维一自著,§4)。

`dream_state.py` 收编 v0.1 `core.intrinsic.dream_tick/dream_ready` 的
pending 单一权威语义,显式化状态机;`residue.py` 是默认生成器(聚合统计
出身);`wander.py` 是随机漫游生成器(马尔可夫出身),回退链指向前者。

跨模块依赖(依赖方向表允许:dreamwork → field/moments + primal 闸):
`residue.py`/`wander.py` 从 `yelos.primal.whitelist_gate` 借用禁形表扫描,
把主题来源封闭集(§4.2)里混入的禁形片段拦在选择器层面,不进入渲染。
"""

from __future__ import annotations
