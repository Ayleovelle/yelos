"""projection/ 在整个架构中的位置:预期投影(finitude_BLUEPRINT §8)——只读,不外显自由文本。"""

from __future__ import annotations

from .contracts import ProjectionData
from .estimate import project

__all__ = ["ProjectionData", "project"]
