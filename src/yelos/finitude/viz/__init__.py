"""viz/ 在整个架构中的位置:零依赖 SVG 渲染器三件(finitude_BLUEPRINT §9)。"""

from __future__ import annotations

from .hourglass import render_hourglass
from .p_curve import render_p_curve
from .rings import render_rings

__all__ = ["render_p_curve", "render_rings", "render_hourglass"]
