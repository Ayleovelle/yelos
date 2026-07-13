"""viz 子包在架构中的位置。

维五自有可视化:三视图数据契约(export.py)+ 自著零依赖 SVG 渲染器
(svg.py)。仓内 golden 测试是活消费者(维五⑤精神);WebUI 只读消费三契约
JSON,WebUI 缺席不影响本模块维五验收。
"""

from __future__ import annotations

from .export import build_curves, build_heatmap, build_sankey, export_all
from .svg import svg_curves, svg_heatmap, svg_sankey

__all__ = [
    "build_curves",
    "build_heatmap",
    "build_sankey",
    "export_all",
    "svg_curves",
    "svg_heatmap",
    "svg_sankey",
]
