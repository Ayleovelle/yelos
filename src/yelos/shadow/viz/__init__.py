"""viz/ 在整个架构中的位置:三个可视化数据契约 + 自著零依赖 SVG 渲染器
(蓝图 §12)。只读各账本(baseline/calibration/sensitization),不写。
"""

from __future__ import annotations

from . import contracts, svg_render

__all__ = ["contracts", "svg_render"]
