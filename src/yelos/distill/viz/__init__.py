"""viz/ 在整个架构中的位置:三 SVG 渲染器,自著零依赖(蓝图 §1 D4 波)。"""

from __future__ import annotations

from . import gauge_svg, radar_svg, sankey_svg

__all__ = ["gauge_svg", "radar_svg", "sankey_svg"]
