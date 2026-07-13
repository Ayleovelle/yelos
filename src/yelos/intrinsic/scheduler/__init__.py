"""scheduler/ 在整个架构中的位置:心跳编排层(维一自著,依赖全部子包)。

`virtual_clock.py` 不重定义时钟(X2 裁定:协议归 `core.clock.Clock`,实现
归 `bench.clock`,本包只复用);`heartbeat.py` 把 MCP 蓝图 §3.4 步 0–9
收编为显式步表(只新增 2b、替换 4/7 内部);`budget.py` 是 RE11 引擎调用
预算模型 + 错峰批次划分。
"""

from __future__ import annotations
