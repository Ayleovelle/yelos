"""viz/ 在整个架构中的位置:数据契约 + 三个仓内自著零依赖 SVG 渲染器(维五)。

依赖方向(§2.1):`viz → moments/field(只读)`。三渲染器各带 golden 测试;
第四/第五消费者(bench 判分器 / WebUI)不计入本模块维五验收(§7)。
"""

from __future__ import annotations
